#!/usr/bin/env python3
"""Replay the agents' real Bash commands through the old and new guard, and show what changed.

Usage: replay_guard.py [--before 2026-09-15T09:14] [--base c7adaf4] [--glob PATTERN]

Reads every Bash command from the subagent transcripts last modified before --before (the default
selects the 48 present when the guard's assignment rule was specified, so the result is stable as
new runs add transcripts), runs each through hooks/agent-guard.py as committed at --base and as it
is now, and prints the commands whose verdict changed, with the new guard's reason.

Then it replays every Read, Grep and Glob call the guarded agents have made, from all their
transcripts to date (--reads-glob), through the guard's `read` mode, and lists the ones it would
now refuse.

Since 2026-09-25 the agents run as headless sessions (hooks/run-agent.sh), whose transcripts are
ordinary session files, not subagent ones. run-agent.sh logs each session's agent and ID in
~/.cache/agent-runs/sessions.log, and each run dir keeps its latest session_id; both halves of
the replay add those transcripts (the Bash half subject to --before, like the rest). The guard had no `read` mode before, so there's no old verdict to compare with, and
this half grows as new runs add transcripts. It prints commands and paths, which come from the
user's own transcripts: don't paste its output anywhere public.

Last, it replays every Bash command from the headless runs, of any date, through the guard as it
is now, and compares that with what the guard decided at the time: a transcript records the hook's
"Blocked by agent-guard" reply. This half keeps up with the agents as they run today.

Exits 1 if a command the guard at --base blocked is allowed now, if any recorded Read, Grep or
Glob call is refused now, or if a headless run's command gets a different verdict now than it got
then: all are changes to look at before committing. It prints SKIP and exits
0 when there's nothing to replay, as on a machine whose transcripts these aren't.
"""

import argparse
import contextlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# Claude Code names a project's transcript folder after its path, with every other character
# than a letter or digit as `-`: /Users/<name> becomes -Users-<name>.
HOME_PROJECT = re.sub(r"[^A-Za-z0-9]", "-", str(Path.home()))
DEFAULT_GLOB = f"projects/{HOME_PROJECT}/*/subagents/agent-*.jsonl"
READS_GLOB = "projects/*/*/subagents/agent-*.jsonl"
# The agents whose frontmatter runs agent-guard.py; spec-reviewer was merged into cold-reviewer.
GUARDED = {
    "researcher",
    "research-verifier",
    "spec-verifier",
    "spec-reviewer",
    "cold-reviewer",
}
READ_TOOLS = ("Read", "Grep", "Glob")
RUNS = Path.home() / ".cache" / "agent-runs"


def headless_sessions():
    """{transcript path: agent} for the guarded agents' headless runs: every session in
    run-agent.sh's log, and the latest in each run dir (runs from before the log existed)."""
    ids = {}
    log = RUNS / "sessions.log"
    if log.exists():
        for line in log.read_text().splitlines():
            parts = line.split()
            if len(parts) == 3:
                ids[parts[2]] = parts[1]
    for f in RUNS.glob("*/*/session_id"):
        # The run dir is named for its agent, with a round suffix: research-verifier-2.
        agent = max(
            (n for n in GUARDED if f.parent.name == n or f.parent.name.startswith(n + "-")),
            key=len,
            default=None,
        )
        ids.setdefault(f.read_text().strip(), agent)
    found = {}
    for session, agent in ids.items():
        if agent in GUARDED:
            for path in (Path.home() / ".claude" / "projects").glob(f"*/{session}.jsonl"):
                found[path] = agent
    return found


def load_guard(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def session_results(path):
    """The saved tool output folder of the session a transcript belongs to, which the guard lets
    that agent read: <session>/tool-results beside a headless run's <session>.jsonl, and the
    parent session's for a subagent's <session>/subagents/agent-*.jsonl."""
    if path.parent.name == "subagents":
        return str(path.parents[1] / "tool-results")
    return str(path.with_suffix("") / "tool-results")


def guard_root(path):
    """The plugin root the guard of a headless run lived in, or None: run-agent.sh renders it
    into the run dir's agents.json, which is where the run's hooks were configured from."""
    for f in RUNS.glob("*/*/session_id"):
        if f.read_text().strip() == path.stem:
            try:
                text = (f.parent / "agents.json").read_text()
            except OSError:
                return None
            found = re.search(r'python3 \\"([^"\\]+)/hooks/agent-guard\.py\\"', text)
            return found and found.group(1)
    return None


def with_root(guard, root):
    """Point the guard's own-root exemption where the run's guard had it: the plugin root, if
    that lives under ~/.claude/plugins, as the guard itself decides."""
    guard.OWN_ROOT = (
        root
        if root
        and any(p in (guard.PLUGINS_HOME, guard.PLUGINS_HOME.resolve()) for p in Path(root).parents)
        else None
    )


def verdict(guard, command, results=None, root=None):
    """('allowed', '') or ('blocked', reason)."""
    guard.SESSION_RESULTS = results
    with_root(guard, root)
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            guard.check_command(command)
    except SystemExit as stop:
        if stop.code == 2:
            return "blocked", err.getvalue().strip().removeprefix(
                "Blocked by agent-guard: "
            )
        raise
    finally:
        with_root(guard, None)
    return "allowed", ""


def read_verdict(guard, tool, tool_input, cwd, results=None, root=None):
    """('allowed', '') or ('blocked', reason) for one Read, Grep or Glob call."""
    saved = guard.CWD
    guard.CWD = cwd
    guard.SESSION_RESULTS = results
    with_root(guard, root)
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err):
            guard.check_read(tool, tool_input)
    except SystemExit as stop:
        if stop.code == 2:
            return "blocked", err.getvalue().strip().removeprefix(
                "Blocked by agent-guard: "
            )
        raise
    finally:
        # The next call is judged where the guard was loaded, not where this one ran.
        guard.CWD = saved
        with_root(guard, None)
    return "allowed", ""


def read_calls(path, agent=None):
    """(tool, input, cwd, own results folder, guard root) for each Read, Grep and Glob call in a guarded agent's transcript. A
    subagent's type is in the .meta.json beside it; a headless run's comes from `agent`."""
    if agent is None:
        meta = path.with_name(path.name.removesuffix(".jsonl") + ".meta.json")
        try:
            agent = json.loads(meta.read_text()).get("agentType")
        except (OSError, json.JSONDecodeError):
            return
    if agent not in GUARDED:
        return
    root = guard_root(path)
    for line in path.read_text(errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (entry.get("message") or {}).get("content")
        for item in content if isinstance(content, list) else []:
            if item.get("type") == "tool_use" and item.get("name") in READ_TOOLS:
                yield (
                    item["name"],
                    item.get("input") or {},
                    entry.get("cwd") or "",
                    session_results(path),
                    root,
                )


def recorded_bash(path):
    """(command, blocked then) for each Bash call in a transcript, from the hook's reply."""
    commands, blocked = {}, set()
    for line in path.read_text(errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (entry.get("message") or {}).get("content")
        for item in content if isinstance(content, list) else []:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_use" and item.get("name") == "Bash":
                if command := (item.get("input") or {}).get("command"):
                    commands[item.get("id")] = command
            elif item.get("type") == "tool_result":
                reply = item.get("content")
                if isinstance(reply, list):
                    reply = "".join(p.get("text", "") for p in reply if isinstance(p, dict))
                # The hook's own error, not a file that quotes the phrase (agent-sandbox.md does).
                if (
                    item.get("is_error")
                    and isinstance(reply, str)
                    and reply.lstrip().startswith("PreToolUse:")
                    and "Blocked by agent-guard" in reply
                ):
                    blocked.add(item.get("tool_use_id"))
    return [(command, key in blocked) for key, command in commands.items()]


def bash_commands(obj):
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and obj.get("name") == "Bash":
            command = (obj.get("input") or {}).get("command")
            if command:
                yield command
        for value in obj.values():
            yield from bash_commands(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from bash_commands(value)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--before", default="2026-09-15T09:14")
    parser.add_argument("--base", default="c7adaf4")
    parser.add_argument("--glob", default=DEFAULT_GLOB, help="relative to ~/.claude")
    parser.add_argument(
        "--reads-glob", default=READS_GLOB, help="relative to ~/.claude, all dates"
    )
    args = parser.parse_args()

    cutoff = datetime.fromisoformat(args.before).timestamp()
    headless = headless_sessions()
    files = sorted(
        f
        for f in [*(Path.home() / ".claude").glob(args.glob), *headless]
        if f.stat().st_mtime < cutoff
    )
    commands = []
    for f in files:
        for line in f.read_text(errors="replace").splitlines():
            try:
                commands.extend((c, session_results(f)) for c in bash_commands(json.loads(line)))
            except json.JSONDecodeError:
                continue
    unique = list(dict.fromkeys(commands))

    old_source = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{args.base}:hooks/agent-guard.py"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    with tempfile.TemporaryDirectory() as tmp:
        old_path = Path(tmp) / "agent_guard_old.py"
        old_path.write_text(old_source)
        old = load_guard(old_path, "agent_guard_old")
        # The old guard compared unresolved script paths, which never match now that
        # ~/.claude/skills is a symlink into this repo. Resolve them, so the replay shows rule
        # changes rather than that install-layout difference.
        old.SCRIPTS = {path.resolve() for path in old.SCRIPTS}
        new = load_guard(REPO / "hooks" / "agent-guard.py", "agent_guard_new")
        tally = {"allowed": 0, "blocked": 0}
        newly_blocked, newly_allowed = [], []
        for command, results in unique:
            before, _ = verdict(old, command)
            after, reason = verdict(new, command, results)
            tally[after] += 1
            if before == "allowed" and after == "blocked":
                newly_blocked.append((command, reason))
            elif before == "blocked" and after == "allowed":
                newly_allowed.append(command)

    print(
        f"{len(files)} transcripts before {args.before} ({sum(f in headless for f in files)} "
        f"headless runs); {len(unique)} unique Bash commands"
    )
    print(f"new guard: {tally['allowed']} allowed, {tally['blocked']} blocked")
    print(f"\nallowed at {args.base}, blocked now: {len(newly_blocked)}")
    for command, reason in newly_blocked:
        print(f"  - {command[:160]!r}\n    {reason[:160]}")
    print(f"\nblocked at {args.base}, allowed now: {len(newly_allowed)}")
    for command in newly_allowed:
        print(f"  - {command[:160]!r}")

    reads = [
        call
        for f in sorted((Path.home() / ".claude").glob(args.reads_glob))
        for call in read_calls(f)
    ] + [call for f, agent in sorted(headless.items()) for call in read_calls(f, agent)]
    unique_reads = list(
        {json.dumps(call, sort_keys=True): call for call in reads}.values()
    )
    refused = []
    for tool, tool_input, cwd, results, root in unique_reads:
        after, reason = read_verdict(new, tool, tool_input, cwd, results, root)
        if after == "blocked":
            refused.append((tool, tool_input, reason))
    print(
        f"\n{len(unique_reads)} unique Read, Grep and Glob calls by guarded agents "
        f"({len(headless)} headless runs included); "
        f"refused now: {len(refused)}"
    )
    for tool, tool_input, reason in refused:
        target = tool_input.get("file_path") or tool_input.get("path") or ""
        print(f"  - {tool} {target[:140]}\n    {reason[:160]}")
    changed = []
    seen = set()
    for f in sorted(headless):
        for command, blocked_then in recorded_bash(f):
            if (command, blocked_then) in seen:
                continue
            seen.add((command, blocked_then))
            now, reason = verdict(new, command, session_results(f), guard_root(f))
            if (now == "blocked") != blocked_then:
                changed.append((command, "blocked" if blocked_then else "allowed", now, reason))
    print(
        f"\n{len(seen)} unique Bash commands from {len(headless)} headless runs, any date; "
        f"verdict changed since they ran: {len(changed)}"
    )
    for command, then, now, reason in changed:
        print(f"  - {then} then, {now} now: {command[:140]!r}\n    {(reason or '')[:160]}")
    if not unique and not unique_reads and not seen:
        print("\nSKIP: no recorded agent transcripts here, so nothing was checked")
        return 0
    if newly_allowed or refused or changed:
        print(
            f"\nFAIL: {len(newly_allowed)} commands allowed that --base blocked, "
            f"{len(refused)} recorded reads refused, {len(changed)} headless commands "
            "with a different verdict now"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

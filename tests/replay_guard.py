#!/usr/bin/env python3
"""Replay the agents' real Bash commands through the old and new guard, and show what changed.

Usage: replay_guard.py [--before 2026-09-15T09:14] [--base c7adaf4] [--glob PATTERN]

Reads every Bash command from the subagent transcripts last modified before --before (the default
selects the 48 present when the guard's assignment rule was specified, so the result is stable as
new runs add transcripts), runs each through hooks/agent-guard.py as committed at --base and as it
is now, and prints the commands whose verdict changed, with the new guard's reason.

Then it replays every Read, Grep and Glob call the guarded agents have made, from all their
transcripts to date (--reads-glob), through the guard's `read` mode, and lists the ones it would
now refuse. The guard had no `read` mode before, so there's no old verdict to compare with, and
this half grows as new runs add transcripts. It prints commands and paths, which come from the
user's own transcripts: don't paste its output anywhere public.
"""

import argparse
import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_GLOB = "projects/-Users-chrisadkin/*/subagents/agent-*.jsonl"
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


def load_guard(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verdict(guard, command):
    """('allowed', '') or ('blocked', reason)."""
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
    return "allowed", ""


def read_verdict(guard, tool, tool_input, cwd):
    """('allowed', '') or ('blocked', reason) for one Read, Grep or Glob call."""
    guard.CWD = cwd
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
    return "allowed", ""


def read_calls(path):
    """(tool, input, cwd) for each Read, Grep and Glob call in a guarded agent's transcript."""
    meta = path.with_name(path.name.removesuffix(".jsonl") + ".meta.json")
    try:
        agent = json.loads(meta.read_text()).get("agentType")
    except (OSError, json.JSONDecodeError):
        return
    if agent not in GUARDED:
        return
    for line in path.read_text(errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        content = (entry.get("message") or {}).get("content")
        for item in content if isinstance(content, list) else []:
            if item.get("type") == "tool_use" and item.get("name") in READ_TOOLS:
                yield item["name"], item.get("input") or {}, entry.get("cwd") or ""


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
    files = sorted(
        f
        for f in (Path.home() / ".claude").glob(args.glob)
        if f.stat().st_mtime < cutoff
    )
    commands = []
    for f in files:
        for line in f.read_text(errors="replace").splitlines():
            try:
                commands.extend(bash_commands(json.loads(line)))
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
        for command in unique:
            before, _ = verdict(old, command)
            after, reason = verdict(new, command)
            tally[after] += 1
            if before == "allowed" and after == "blocked":
                newly_blocked.append((command, reason))
            elif before == "blocked" and after == "allowed":
                newly_allowed.append(command)

    print(
        f"{len(files)} transcripts before {args.before}; {len(unique)} unique Bash commands"
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
    ]
    unique_reads = list(
        {json.dumps(call, sort_keys=True): call for call in reads}.values()
    )
    refused = []
    for tool, tool_input, cwd in unique_reads:
        after, reason = read_verdict(new, tool, tool_input, cwd)
        if after == "blocked":
            refused.append((tool, tool_input, reason))
    print(
        f"\n{len(unique_reads)} unique Read, Grep and Glob calls by guarded agents; "
        f"refused now: {len(refused)}"
    )
    for tool, tool_input, reason in refused:
        target = tool_input.get("file_path") or tool_input.get("path") or ""
        print(f"  - {tool} {target[:140]}\n    {reason[:160]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

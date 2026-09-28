#!/usr/bin/env python3
"""Mines Claude Code's session logs for how the skills and their agents went in real use.

Usage: tests/mine-sessions.py [--since YYYY-MM-DD] [--examples N] [--projects DIR] [--sessions-log FILE]

Reads every session log under ~/.claude/projects (one .jsonl per session) and prints a report:
  - per skill (/research, /spec, /cold-review, /idea): how many runs, by mode; turns and tokens;
    the agents it launched, their follow-ups, and launches joined to another command, which a
    sandbox that exempts run-agent.sh doesn't exempt; failed tool calls, grouped; and the
    messages you typed while it ran, which show where you had to step in.
  - per agent (researcher, research-verifier, spec-verifier, cold-reviewer), from the headless
    sessions ~/.cache/agent-runs/sessions.log lists: sessions, turns, tokens and failed tool
    calls, guard refusals included.
A skill run starts where its command was typed, or where the Skill tool started it, and lasts
until the next command or the end of the session. Eval runs aren't in the logs: they run with
--no-session-persistence.

It only reads, and prints to stdout. The logs hold everything the sessions saw, so the report can
too: examples are cut to 120 characters, but read it before you share it. Don't run it from a
sandboxed agent: the guard refuses reads of these logs (hooks/agent-guard.py HISTORY_HOME).

Exits 0, or 2 on a bad argument or no logs to read.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

SKILLS = ("research", "spec", "cold-review", "idea")
MODES = {
    "research": ("quick", "ideas", "finish"),
    "spec": ("quick", "finish", "spike", "done"),
    "cold-review": ("prompt",),
    "idea": (),
}
AGENTS = ("researcher", "research-verifier", "spec-verifier", "cold-reviewer")
COMMAND = re.compile(r"<command-name>/?([\w:.-]+)</command-name>")
ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.DOTALL)
# A real launch: the command starts with run-agent.sh (after an optional `cd <dir> &&`) and names
# one of the agents. Group 2 is the rest of the command, where a joined `; echo $?` would be.
LAUNCH = re.compile(
    r"\s*(?:cd\s+\S+\s*&&\s*)?(?:\S*/)?run-agent\.sh\s+("
    + "|".join(AGENTS)
    + r")\b((?:&>|>&|[^;&|\n])*)(.*)",
    re.DOTALL,
)
EXAMPLE_WIDTH = 120


def clip(text, width=EXAMPLE_WIDTH):
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + "…"


def read_events(path):
    """The session's events in order; a line that isn't JSON is skipped."""
    events = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    return events


def user_text(event):
    """The text of a message the user typed, or None for tool results and meta messages."""
    if event.get("type") != "user" or event.get("isMeta"):
        return None
    content = (event.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list) and not any(
        b.get("type") == "tool_result" for b in content
    ):
        return (
            "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
            or None
        )
    return None


def blocks(event, kind):
    content = (event.get("message") or {}).get("content")
    return (
        [b for b in content if b.get("type") == kind]
        if isinstance(content, list)
        else []
    )


def result_text(block):
    content = block.get("content")
    if isinstance(content, list):
        content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
    return str(content or "")


def error_kind(text):
    """A short name for why a tool call failed, so alike failures group together."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    guard = re.search(r"Blocked by agent-guard: (.*)", text)
    if guard:
        return f"guard: {clip(guard.group(1), 70)}"
    if "hook error" in first:
        return "hook: " + clip(first.split("]:", 1)[-1], 60)
    if "classifier" in text and "no verdict" in text:
        return "auto mode gave no verdict"
    if re.search(
        r"doesn't want to proceed|was rejected|[Pp]ermission.*denied|denied by", text
    ):
        return "permission refused"
    code = re.match(r"Exit code (\d+)", first)
    if code:
        return f"exit {code.group(1)}"
    return clip(first, 60) or "no message"


def start_of_skill(event):
    """(skill, args) if this event starts a skill run, else None."""
    text = user_text(event)
    if text:
        name = COMMAND.search(text)
        if name:
            args = ARGS.search(text)
            return name.group(1), (args.group(1).strip() if args else "")
    for use in blocks(event, "tool_use"):
        if use.get("name") == "Skill":
            skill = str((use.get("input") or {}).get("skill", ""))
            if skill in SKILLS:
                return skill, str((use.get("input") or {}).get("args", ""))
    return None


def mode_of(skill, args):
    first = args.split()[0] if args.split() else ""
    return first if first in MODES.get(skill, ()) else "main"


class Tally:
    """What one skill, or one agent, did across all its runs."""

    def __init__(self):
        self.runs = 0
        self.modes = Counter()
        self.turns = 0
        self.tokens_in = 0
        self.tokens_cached = 0
        self.tokens_out = 0
        self.errors = Counter()
        self.error_examples = defaultdict(list)
        self.launches = Counter()
        self.resumes = Counter()
        self.joined = []
        self.stepped_in = []

    def add_usage(self, messages):
        for usage in messages.values():
            self.turns += 1
            self.tokens_in += usage.get("input_tokens", 0) + usage.get(
                "cache_creation_input_tokens", 0
            )
            self.tokens_cached += usage.get("cache_read_input_tokens", 0)
            self.tokens_out += usage.get("output_tokens", 0)


def tally_events(tally, events, where, examples):
    """Adds one run's events (a skill's slice of a session, or an agent's whole session)."""
    uses, usage = {}, {}
    for event in events:
        for use in blocks(event, "tool_use"):
            uses[use.get("id")] = use
            if use.get("name") == "Bash":
                command = str((use.get("input") or {}).get("command", ""))
                launch = LAUNCH.match(command)
                if launch:
                    tally.launches[launch.group(1)] += 1
                    if "--resume" in command:
                        tally.resumes[launch.group(1)] += 1
                    if launch.group(3).strip():
                        tally.joined.append(f"{where} {clip(command)}")
        for result in blocks(event, "tool_result"):
            if not result.get("is_error"):
                continue
            use = uses.get(result.get("tool_use_id"), {})
            tool = use.get("name", "?")
            kind = f"{tool} · {error_kind(result_text(result))}"
            tally.errors[kind] += 1
            if len(tally.error_examples[kind]) < examples:
                what = (
                    (use.get("input") or {}).get("command")
                    or (use.get("input") or {}).get("file_path")
                    or ""
                )
                tally.error_examples[kind].append(
                    f"{where} {clip(what or result_text(result))}"
                )
        message = event.get("message") or {}
        if event.get("type") == "assistant" and message.get("usage"):
            usage[message.get("id") or event.get("uuid")] = message["usage"]
    tally.add_usage(usage)


def when(events, session):
    """The date of the first timestamped event, and the session's short ID."""
    stamp = next((str(e["timestamp"]) for e in events if e.get("timestamp")), "")
    return f"{stamp[:10] or '????-??-??'} {session[:8]}"


def load_agent_sessions(path):
    """Session ID -> agent name, from run-agent.sh's log."""
    found = {}
    if path.is_file():
        for line in path.read_text(errors="replace").splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[1] in AGENTS:
                found[parts[2]] = parts[1]
    return found


def mine(projects, sessions_log, since, examples):
    agent_ids = load_agent_sessions(sessions_log)
    skills = defaultdict(Tally)
    agents = defaultdict(Tally)
    files = sorted(projects.glob("*/*.jsonl"))
    read, agents_found = 0, 0
    for path in files:
        events = read_events(path)
        stamps = [str(e.get("timestamp", "")) for e in events if e.get("timestamp")]
        if since and (not stamps or max(stamps)[:10] < since):
            continue
        read += 1
        session = path.stem
        if session in agent_ids:
            agents_found += 1
            tally = agents[agent_ids[session]]
            tally.runs += 1
            tally_events(tally, events, when(events, session), examples)
            continue
        current, start = None, 0
        for i, event in enumerate(events + [None]):
            started = start_of_skill(event) if event else None
            text = user_text(event) if event else None
            if current and (
                event is None or started or (text and COMMAND.search(text))
            ):
                tally_events(
                    skills[current],
                    events[start:i],
                    when(events[start:i], session),
                    examples,
                )
                current = None
            if started and started[0] in SKILLS:
                current, start = started[0], i
                skills[current].runs += 1
                skills[current].modes[mode_of(*started)] += 1
            elif current and text and not text.lstrip().startswith("<"):
                if len(skills[current].stepped_in) < 1000:
                    skills[current].stepped_in.append(
                        f'{when([event], session)} "{clip(text)}"'
                    )
    return read, len(files), len(agent_ids), agents_found, skills, agents


def report(tally, examples, out):
    out.append(
        f"Turns {tally.turns} · tokens in {tally.tokens_in:,} (plus {tally.tokens_cached:,} read"
        f" from cache) · out {tally.tokens_out:,}"
    )
    if tally.launches:
        launched = ", ".join(
            f"{a} {n}"
            + (f" ({tally.resumes[a]} follow-ups)" if tally.resumes[a] else "")
            for a, n in tally.launches.most_common()
        )
        out.append(f"Agent launches: {launched}")
        out.append(f"Launches joined to another command: {len(tally.joined)}")
        out.extend(f"    {j}" for j in tally.joined[:examples])
    total = sum(tally.errors.values())
    out.append(f"Failed tool calls: {total}")
    for kind, n in tally.errors.most_common(10):
        out.append(f"  {n:4}  {kind}")
        out.extend(f"          e.g. {e}" for e in tally.error_examples[kind])
    if len(tally.errors) > 10:
        out.append(f"        … and {len(tally.errors) - 10} more kinds")


def main(argv=None):
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument(
        "--projects", type=Path, default=Path.home() / ".claude" / "projects"
    )
    parser.add_argument(
        "--sessions-log",
        type=Path,
        default=Path.home() / ".cache" / "agent-runs" / "sessions.log",
    )
    parser.add_argument(
        "--since", help="only sessions active on or after this date, YYYY-MM-DD"
    )
    parser.add_argument(
        "--examples", type=int, default=3, help="examples per group (default 3)"
    )
    args = parser.parse_args(argv)
    if args.since and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.since):
        parser.error("--since takes YYYY-MM-DD")
    if not args.projects.is_dir():
        print(f"mine-sessions: no session logs at {args.projects}", file=sys.stderr)
        return 2
    read, total, listed, found, skills, agents = mine(
        args.projects, args.sessions_log, args.since, args.examples
    )
    out = [
        f"Session logs: read {read} of {total}"
        + (f" (active since {args.since})" if args.since else ""),
        f"Headless agent sessions: {found} found of {listed} in {args.sessions_log}",
        "A skill run lasts until the next typed command, so later work in the same session counts too.",
    ]
    for skill in SKILLS:
        tally = skills.get(skill)
        if not tally:
            out += ["", f"## /{skill}: no runs"]
            continue
        modes = ", ".join(f"{m} {n}" for m, n in tally.modes.most_common())
        out += ["", f"## /{skill}: {tally.runs} runs ({modes})"]
        report(tally, args.examples, out)
        out.append(f"You typed {len(tally.stepped_in)} messages after starting it")
        out.extend(f"    {s}" for s in tally.stepped_in[-args.examples :])
    for agent in AGENTS:
        tally = agents.get(agent)
        out += [
            "",
            f"## agent {agent}: "
            + (f"{tally.runs} sessions" if tally else "no sessions found"),
        ]
        if tally:
            report(tally, args.examples, out)
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())

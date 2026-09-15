#!/usr/bin/env python3
"""Replay the agents' real Bash commands through the old and new guard, and show what changed.

Usage: replay_guard.py [--before 2026-09-15T09:14] [--base c7adaf4] [--glob PATTERN]

Reads every Bash command from the subagent transcripts last modified before --before (the default
selects the 48 present when the guard's assignment rule was specified, so the result is stable as
new runs add transcripts), runs each through hooks/agent-guard.py as committed at --base and as it
is now, and prints the commands whose verdict changed, with the new guard's reason. It prints
commands, which come from the user's own transcripts: don't paste its output anywhere public.
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
            return "blocked", err.getvalue().strip().removeprefix("Blocked by agent-guard: ")
        raise
    return "allowed", ""


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
    args = parser.parse_args()

    cutoff = datetime.fromisoformat(args.before).timestamp()
    files = sorted(
        f for f in (Path.home() / ".claude").glob(args.glob) if f.stat().st_mtime < cutoff
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

    print(f"{len(files)} transcripts before {args.before}; {len(unique)} unique Bash commands")
    print(f"new guard: {tally['allowed']} allowed, {tally['blocked']} blocked")
    print(f"\nallowed at {args.base}, blocked now: {len(newly_blocked)}")
    for command, reason in newly_blocked:
        print(f"  - {command[:160]!r}\n    {reason[:160]}")
    print(f"\nblocked at {args.base}, allowed now: {len(newly_allowed)}")
    for command in newly_allowed:
        print(f"  - {command[:160]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

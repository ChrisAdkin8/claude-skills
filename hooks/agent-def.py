#!/usr/bin/env python3
"""Print one agent file as the JSON `claude --agents` takes, so the runners can pass the agent
per run instead of Claude Code loading it from ~/.claude/agents into every session.

Usage: agent-def.py <agent file>

The file is markdown with a frontmatter block. The output is {"<name>": {"description", "prompt",
"tools", "hooks"}}: the prompt is the body, tools the comma-separated `tools:` line as a list, and
hooks the `hooks:` block. The reader knows only the shape the agent files use:

    hooks:
      PreToolUse:
        - matcher: "Bash"
          hooks:
            - type: command
              command: python3 "$HOME/.claude/hooks/agent-guard.py" bash

Anything else - an unknown key, another hook type, a line it can't place - exits 2 rather than
drop a hook, since a dropped guard hook would fail open.
"""

import json
import re
import sys
from pathlib import Path

KEYS = {"name", "description", "tools", "hooks"}


class Bad(Exception):
    pass


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def parse_hooks(lines):
    """The indented lines under `hooks:` as {event: [{"matcher", "hooks": [{"type", "command"}]}]}."""
    events = {}
    matchers = handlers = None
    for line in lines:
        if m := re.fullmatch(r"  ([A-Za-z]+):", line):
            matchers = events.setdefault(m[1], [])
            handlers = None
        elif (m := re.fullmatch(r"    - matcher: (.+)", line)) and matchers is not None:
            matchers.append({"matcher": unquote(m[1]), "hooks": []})
            handlers = None
        elif line == "      hooks:" and matchers:
            handlers = matchers[-1]["hooks"]
        elif line == "        - type: command" and handlers is not None:
            handlers.append({"type": "command"})
        elif (m := re.fullmatch(r"          command: (.+)", line)) and handlers:
            if "command" in handlers[-1]:
                raise Bad(f"two commands in one hook: {line!r}")
            handlers[-1]["command"] = m[1].strip()
        else:
            raise Bad(f"hooks: can't read {line!r}")
    for event, ms in events.items():
        if not ms:
            raise Bad(f"hooks: {event} has no matchers")
        for entry in ms:
            if not entry["hooks"] or any("command" not in h for h in entry["hooks"]):
                raise Bad(
                    f"hooks: {event} {entry['matcher']!r} has a hook with no command"
                )
    return events


def agent_def(path):
    text = Path(path).read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        raise Bad("no frontmatter")
    fields, hook_lines, in_hooks = {}, [], False
    for line in m[1].splitlines():
        if in_hooks and line.startswith(" "):
            hook_lines.append(line)
            continue
        in_hooks = False
        km = re.fullmatch(r"([a-z-]+):(?: (.*))?", line)
        if not km:
            raise Bad(f"frontmatter: can't read {line!r}")
        key, value = km[1], km[2]
        if key not in KEYS:
            raise Bad(f"frontmatter: unknown key {key!r}")
        if key in fields:
            raise Bad(f"frontmatter: {key} given twice")
        if key == "hooks":
            if value:
                raise Bad("frontmatter: hooks must be a block")
            in_hooks = True
            fields["hooks"] = None
        elif not value:
            raise Bad(f"frontmatter: {key} is empty")
        else:
            fields[key] = value.strip()
    for key in ("name", "description", "tools"):
        if key not in fields:
            raise Bad(f"frontmatter: no {key}")
    if fields["name"] != Path(path).stem:
        raise Bad(
            f"name {fields['name']!r} doesn't match the file name {Path(path).name!r}"
        )
    prompt = text[m.end() :].strip()
    if not prompt:
        raise Bad("no prompt after the frontmatter")
    agent = {
        "description": fields["description"],
        "prompt": prompt + "\n",
        "tools": [t.strip() for t in fields["tools"].split(",") if t.strip()],
    }
    if "hooks" in fields:
        agent["hooks"] = parse_hooks(hook_lines)
    return {fields["name"]: agent}


def main():
    if len(sys.argv) != 2:
        print("usage: agent-def.py <agent file>", file=sys.stderr)
        return 2
    try:
        print(json.dumps(agent_def(sys.argv[1]), indent=2))
    except (Bad, OSError) as e:
        print(f"agent-def: {sys.argv[1]}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

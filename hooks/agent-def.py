#!/usr/bin/env python3
"""Print one agent file as the JSON `claude --agents` takes, so the runners can pass the agent
per run instead of Claude Code loading it from ~/.claude/agents into every session.

Usage: agent-def.py [--root <dir>] <agent file>

The file is markdown with a frontmatter block. The output is {"<name>": {"description", "prompt",
"tools", "hooks"}}: the prompt is the body, tools the comma-separated `tools:` line as a list, and
hooks the `hooks:` block. The reader knows only the shape the agent files use:

    hooks:
      PreToolUse:
        - matcher: "Bash"
          hooks:
            - type: command
              command: python3 "${CLAUDE_PLUGIN_ROOT}/hooks/agent-guard.py" bash

${CLAUDE_PLUGIN_ROOT} is replaced by --root, in hook commands and in the prompt, so an agent
writes the absolute path the guard and the sandbox settings match. A command may hold no other
${...}, and a placeholder with no --root is an error: either would reach the agent's session
as literal text.

Anything else - an unknown key, another hook type, a line it can't place - exits 2 rather than
drop a hook, since a dropped guard hook would fail open.
"""

import json
import re
import sys
from pathlib import Path

KEYS = {"name", "description", "tools", "hooks"}
PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"


class Bad(Exception):
    pass


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def substitute(text, root, what):
    """`text` with the placeholder replaced by `root`; a `${` left in a command is an error."""
    if PLACEHOLDER in text:
        if root is None:
            raise Bad(f"{what} names {PLACEHOLDER}, so it needs --root")
        text = text.replace(PLACEHOLDER, root)
    if what == "a hook command" and "${" in text:
        raise Bad(f"{what} holds a variable this reader doesn't know: {text!r}")
    return text


def parse_hooks(lines, root):
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
            handlers[-1]["command"] = substitute(m[1].strip(), root, "a hook command")
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


def agent_def(path, root=None):
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
        "prompt": substitute(prompt, root, "the prompt") + "\n",
        "tools": [t.strip() for t in fields["tools"].split(",") if t.strip()],
    }
    if "hooks" in fields:
        agent["hooks"] = parse_hooks(hook_lines, root)
    return {fields["name"]: agent}


def main():
    args = sys.argv[1:]
    root = None
    if args[:1] == ["--root"]:
        if len(args) < 2 or not args[1]:
            args = []
        else:
            root, args = args[1].rstrip("/") or "/", args[2:]
    if len(args) != 1 or args[0].startswith("--"):
        print("usage: agent-def.py [--root <dir>] <agent file>", file=sys.stderr)
        return 2
    try:
        print(json.dumps(agent_def(args[0], root), indent=2))
    except (Bad, OSError) as e:
        print(f"agent-def: {args[0]}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

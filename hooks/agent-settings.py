#!/usr/bin/env python3
"""Print a sandbox settings file with ${CLAUDE_PLUGIN_ROOT} replaced by the plugin root.

Usage: agent-settings.py <settings file> <root> [NAME=VALUE ...]

The committed settings (hooks/agent-sandbox.json, tests/skill-evals/agent-case-settings.json) name
the scripts that run outside the sandbox as ${CLAUDE_PLUGIN_ROOT}/skills/... so they hold wherever
the repo or plugin cache lives. Claude Code reads no placeholder from --settings, and an entry
written with `~` doesn't exclude a call written with an absolute path, so each runner renders the
file with the root as an absolute path and passes the result. Each NAME=VALUE argument (NAME in
[A-Z][A-Z0-9_]*) replaces ${NAME} too, for settings such as skills/implement/implementer-settings.json
that name a run's own paths. Any other `${...}` exits 2 rather than reach claude as a literal.
"""

import json
import os
import re
import sys

PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"
USAGE = "usage: agent-settings.py <settings file> <root> [NAME=VALUE ...]"
NAME = re.compile(r"[A-Z][A-Z0-9_]*")


class Bad(Exception):
    pass


def render(node, values):
    if isinstance(node, str):
        text = node
        for placeholder, value in values.items():
            text = text.replace(placeholder, value)
        if "${" in text:
            raise Bad(f"unknown variable in {node!r}: only {', '.join(values)} are replaced")
        return text
    if isinstance(node, list):
        return [render(item, values) for item in node]
    if isinstance(node, dict):
        return {render(key, values): render(value, values) for key, value in node.items()}
    return node


def variables(args):
    found = {}
    for arg in args:
        name, sep, value = arg.partition("=")
        if not sep or not NAME.fullmatch(name):
            raise Bad(f"not NAME=VALUE with NAME in [A-Z][A-Z0-9_]*: {arg!r}")
        found["${" + name + "}"] = value
    return found


def main():
    if len(sys.argv) < 3:
        print(USAGE, file=sys.stderr)
        return 2
    path, root = sys.argv[1], os.path.abspath(sys.argv[2])
    try:
        values = {PLACEHOLDER: root, **variables(sys.argv[3:])}
        with open(path) as f:
            settings = json.load(f)
        print(json.dumps(render(settings, values), indent=2))
    except (Bad, OSError, ValueError) as e:
        print(f"agent-settings: {path}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

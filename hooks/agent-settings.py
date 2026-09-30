#!/usr/bin/env python3
"""Print a sandbox settings file with ${CLAUDE_PLUGIN_ROOT} replaced by the plugin root.

Usage: agent-settings.py <settings file> <root>

The committed settings (hooks/agent-sandbox.json, tests/skill-evals/agent-case-settings.json) name
the scripts that run outside the sandbox as ${CLAUDE_PLUGIN_ROOT}/skills/... so they hold wherever
the repo or plugin cache lives. Claude Code reads no placeholder from --settings, and an entry
written with `~` doesn't exclude a call written with an absolute path, so each runner renders the
file with the root as an absolute path and passes the result. Any other `${...}` exits 2 rather
than reach claude as a literal.
"""

import json
import os
import sys

PLACEHOLDER = "${CLAUDE_PLUGIN_ROOT}"


class Bad(Exception):
    pass


def render(node, root):
    if isinstance(node, str):
        text = node.replace(PLACEHOLDER, root)
        if "${" in text:
            raise Bad(f"unknown variable in {node!r}: only {PLACEHOLDER} is replaced")
        return text
    if isinstance(node, list):
        return [render(item, root) for item in node]
    if isinstance(node, dict):
        return {render(key, root): render(value, root) for key, value in node.items()}
    return node


def main():
    if len(sys.argv) != 3:
        print("usage: agent-settings.py <settings file> <root>", file=sys.stderr)
        return 2
    path, root = sys.argv[1], os.path.abspath(sys.argv[2])
    try:
        with open(path) as f:
            settings = json.load(f)
        print(json.dumps(render(settings, root), indent=2))
    except (Bad, OSError, ValueError) as e:
        print(f"agent-settings: {path}: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run a read-only git command, after agent-guard's git checks.

Usage: git-read.py [git options] <subcommand> [args]   e.g. git-read.py -C ~/notes log -3

The /research, /spec and /cold-review skills pre-approve this script instead of shapes like
`Bash(git log *)`. A `*` in a permission rule matches anything, spaces included, so
`Bash(git log *)` also approved `git log --output=<any file>`, which overwrites that file, and
`Bash(git -C * rev-parse *)` approved `git -C . diff --output=<file> rev-parse`. This script
refuses what agent-guard.py refuses an agent: subcommands that change the repo, `-c` and
`--config-env`, git's own options other than a short safe list (-p starts a pager, --git-dir
reads another config), options that write files or run programs (--output, -O, --ext-diff,
--textconv), and credentials paths. Then it runs git with `--no-pager` and the arguments
unchanged, so no pager starts even from the repo's config.
"""

import importlib.util
import os
import shlex
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "agent-guard.py"


def main():
    spec = importlib.util.spec_from_file_location("agent_guard", GUARD)
    assert spec and spec.loader
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    args = sys.argv[1:]
    if not args:
        guard.block("usage: git-read.py [git options] <subcommand> [args]")
    # Checked as one simple command with literal words: the shell has already expanded them.
    guard.check_command(shlex.join(["git", *args]))
    os.execvp("git", ["git", "--no-pager", *args])


if __name__ == "__main__":
    main()

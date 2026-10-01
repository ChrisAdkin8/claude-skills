#!/usr/bin/env python3
"""Run a read-only git command, after agent-guard's git checks.

Usage: git-read.py [git options] <subcommand> [args]   e.g. git-read.py -C ~/notes log -3

The /research, /spec, /cold-review and /implement skills pre-approve this script instead of
shapes like `Bash(git log *)`. A `*` in a permission rule matches anything, spaces included, so
`Bash(git log *)` also approved `git log --output=<any file>`, which overwrites that file, and
`Bash(git -C * rev-parse *)` approved `git -C . diff --output=<file> rev-parse`. This script
refuses what agent-guard.py refuses an agent: subcommands that change the repo, `-c` and
`--config-env`, git's own options other than a short safe list (-p starts a pager, --git-dir
reads another config), options that write files or run programs (--output, -O, --ext-diff,
--textconv), and credentials paths. Then it runs git with `--no-pager`, so no pager starts even
from the repo's config.

It runs outside the agent sandbox, with no prompt, so it also keeps the repo it reads from running
a program. A repo's own config (.git/config, config.worktree and the files they include) can name
programs git runs while reading, and it may have come from someone else, in a downloaded archive
say. So git-read.py:
- refuses to run git if that config, or a checked-out submodule's, names a filter, diff or merge
  driver, an external diff, a gpg program or a hook command (RUNS);
- runs git with core.fsmonitor off and core.hooksPath at /dev/null, so neither the file watcher
  nor a hook script starts. Repos set these for their own use (Scalar, husky), so they're
  overridden, not refused;
- lets git use no transport (GIT_ALLOW_PROTOCOL is empty), so `remote show` and a partial
  clone's fetch of a missing object can't start ssh, an ext:: command or a remote's uploadpack;
- passes git none of the caller's GIT_* variables, which can name programs (GIT_EXTERNAL_DIFF),
  add config (GIT_CONFIG_*) or choose another repo (GIT_DIR);
- refuses --help, which starts the manual viewer git's config names.
The user's own config (global and system) is trusted: a driver or gpg program it names still runs.
"""

import importlib.util
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

GUARD = Path(__file__).resolve().parent / "agent-guard.py"
# For every git this runs. `-c` also reaches the git that `status` and `diff` start in a submodule.
SAFE = ["--no-pager", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null"]
# Keys in a repo's own config that name a program git may run while reading: filters (status,
# diff, blame, cat-file --filters), diff drivers and diff.external (diff, log -p, show, blame),
# merge drivers (--remerge-diff), gpg programs (--show-signature, or any log when the config sets
# log.showSignature) and hooks defined in config, which core.hooksPath doesn't reach.
RUNS = re.compile(
    r"filter\..+\.(?:clean|smudge|process)|diff\..+\.(?:textconv|command)|diff\.external"
    r"|merge\..+\.driver|gpg\.(?:.+\.)?program|hook\..+\.command",
    re.IGNORECASE,
)
# GIT_ALLOW_PROTOCOL, when set, overrides every protocol.*.allow setting; empty, it allows none.
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ENV["GIT_ALLOW_PROTOCOL"] = ""


def git(guard, where, *args, check=True):
    """A helper git call in the repo that `where` (-C options) picks, run like the real one."""
    run = subprocess.run(
        ["git", *SAFE, *where, *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=ENV,
        check=False,
    )
    if check and run.returncode:
        guard.block(
            f"couldn't check the repo's git config: {os.fsdecode(run.stderr).strip()}"
        )
    return run


def check_config(guard, where, what, seen):
    """Refuse if the repo's own config names a program (RUNS), then check its checked-out
    submodules the same way: status and diff run git in each, which reads that one's config."""
    listed = git(guard, where, "config", "--list", "--show-scope", "-z").stdout
    fields = listed.split(b"\0")
    for scope, entry in zip(fields[0::2], fields[1::2]):
        key = os.fsdecode(entry.partition(b"\n")[0])
        # The other scopes are the user's: global, system, command (SAFE) and the file Apple's
        # git ships, which it calls unknown.
        if scope in (b"local", b"worktree") and RUNS.fullmatch(key):
            guard.block(
                f"{what}'s own git config sets {key}, which names a program git would run; "
                "git-read.py won't run git there"
            )
    top = git(guard, where, "rev-parse", "--show-toplevel", check=False)
    if top.returncode:
        return  # a bare repo, or none: no work tree to check submodules out in
    root = Path(os.fsdecode(top.stdout.removesuffix(b"\n"))).resolve()
    if root in seen:
        return  # a submodule path that leads back to a repo already checked
    seen.add(root)
    index = git(guard, where, "ls-files", "--stage", "--full-name", "-z", "--", ":/")
    for entry in index.stdout.split(b"\0"):
        if entry.startswith(b"160000 "):  # a submodule, checked out if it has a .git
            path = root / os.fsdecode(entry.partition(b"\t")[2])
            if (path / ".git").exists():
                check_config(guard, ["-C", str(path)], f"the submodule {path}", seen)


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
    if "--help" in args:
        guard.block(
            "`--help` starts the manual viewer git's config names, which may be the repo's own"
        )
    # The -C options before the subcommand pick the repo, for the checks as for the command.
    where, i = [], 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C":
            where += args[i : i + 2]
            i += 1
        i += 1
    check_config(guard, where, "this repo", set())
    os.execvpe("git", ["git", *SAFE, *args], ENV)


if __name__ == "__main__":
    main()

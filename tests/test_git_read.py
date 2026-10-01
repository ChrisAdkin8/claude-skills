"""Tests for hooks/git-read.py: it runs read-only git commands, refuses what agent-guard.py
refuses an agent, and runs no program the repo's own config names. The skills pre-approve it, and
it runs outside the agent sandbox, so this is the only check on what it runs.

Run with: python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import importlib.util
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "git-read.py"
GUARD = SCRIPT.parent / "agent-guard.py"
ID = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


class GitRead(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.repo.mkdir()
        for args in (
            ("init", "-q"),
            ("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q",
             "--allow-empty", "-m", "first"),
        ):  # fmt: skip
            subprocess.run(["git", "-C", str(self.repo), *args], check=True)
        self.out = Path(tmp.name) / "written"

    def git_read(self, *args):
        run = subprocess.run(
            [sys.executable, str(SCRIPT), "-C", str(self.repo), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

    def test_reads_run(self):
        for args in (
            ("log", "--oneline"),
            ("status", "--short"),
            ("rev-parse", "HEAD"),
        ):
            with self.subTest(args=args):
                code, out = self.git_read(*args)
                self.assertEqual(code, 0, out)
        self.assertIn("first", self.git_read("log", "--oneline")[1])

    def test_refused_like_the_guard(self):
        for args in (
            ("log", f"--output={self.out}"),
            ("diff", "--ext-diff"),
            ("-c", "core.pager=touch x", "log"),
            ("-p", "log"),
            ("--git-dir=/elsewhere", "log"),
            ("commit", "--allow-empty", "-m", "x"),
            ("push",),
            ("config", "user.name", "x"),
        ):
            with self.subTest(args=args):
                code, out = self.git_read(*args)
                self.assertEqual(code, 2, out)
                self.assertIn("Blocked by agent-guard", out)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.git_read("rev-list", "--count", "HEAD")[1].strip(), "1")

    def test_no_arguments_refused(self):
        run = subprocess.run(
            [sys.executable, str(SCRIPT)], capture_output=True, check=False
        )
        self.assertEqual(run.returncode, 2)

    def test_worktree_list(self):
        # From the 2026-10-01 review (M15): /spec's done step and /implement list worktrees
        # through git-read.py; the other worktree commands change things.
        code, out = self.git_read("worktree", "list", "--porcelain")
        self.assertEqual(code, 0, out)
        self.assertIn(f"worktree {self.repo.resolve()}\n", out)
        other = self.repo.parent / "other"
        for args in (
            ("worktree", "add", str(other)),
            ("worktree", "prune"),
            ("worktree",),
        ):
            with self.subTest(args=args):
                code, out = self.git_read(*args)
                self.assertEqual(code, 2, out)
                self.assertIn("may only list worktrees", out)
        self.assertFalse(other.exists())


class RepoOwnConfig(unittest.TestCase):
    """From the 2026-10-01 review (M1): git runs programs that the repo's own config names, and
    that config may have come from someone else, with a downloaded archive say. Each test gives a
    throwaway repo one such setting, naming a program that creates a sentinel file, and runs
    git-read.py the ways that would start it. The sentinel must stay absent."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        self.sentinel = self.tmp / "sentinel"
        # Some settings run a program without a shell, so the payload is a script, not a command.
        self.payload = self.tmp / "payload"
        self.payload.write_text(
            f"#!/bin/sh\ntouch {shlex.quote(str(self.sentinel))}\nexit 1\n"
        )
        self.payload.chmod(0o755)
        self.repo = self.tmp / "repo"
        self.init(self.repo)
        self.stale = [self.repo / "a.txt"]
        self.mtime = 1_000_000_000

    def git(self, *args, repo=None, input=None):
        return subprocess.run(
            ["git", "-C", str(repo or self.repo), *ID, *args],
            input=input,
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    def init(self, repo):
        """A repo whose a.txt changed in its second commit."""
        repo.mkdir()
        self.git("init", "-q", repo=repo)
        (repo / "a.txt").write_text("one\n")
        self.git("add", "a.txt", repo=repo)
        self.git("commit", "-qm", "first", repo=repo)
        (repo / "a.txt").write_text("one\ntwo\n")
        self.git("commit", "-qam", "second", repo=repo)

    def config(self, *pairs, repo=None):
        for key, value in pairs:
            self.git("config", key, value, repo=repo)

    def git_read(self, *args, env=None):
        # An unpacked archive's index doesn't match its files' times, so status and diff read the
        # files again, through any filter. A new time before each run does the same here.
        self.mtime += 10
        for path in self.stale:
            os.utime(path, (self.mtime, self.mtime))
        run = subprocess.run(
            [sys.executable, str(SCRIPT), "-C", str(self.repo), *args],
            capture_output=True,
            text=True,
            check=False,
            env=env,
            timeout=60,
        )
        return run.returncode, run.stdout + run.stderr

    def assertNothingRuns(self, *commands, code=0, refused=None, says=None, env=None):
        """Each command leaves no sentinel. It's refused for a reason naming `refused`, if given,
        or else exits with `code` (None: any), and its output holds `says`, if given."""
        for args in commands:
            with self.subTest(args=args):
                self.sentinel.unlink(missing_ok=True)
                got, out = self.git_read(*args, env=env)
                self.assertFalse(
                    self.sentinel.exists(),
                    f"git-read.py {shlex.join(args)} ran the repo's program\n{out}",
                )
                if refused:
                    self.assertEqual(got, 2, out)
                    self.assertIn("Blocked by agent-guard", out)
                    self.assertIn(refused, out)
                elif code is not None:
                    self.assertEqual(got, code, out)
                if says:
                    self.assertIn(says, out)

    def hook(self, path):
        path.parent.mkdir(exist_ok=True)
        path.symlink_to(self.payload)

    def test_fsmonitor_is_turned_off(self):
        # Scalar sets core.fsmonitor in a repo's own config, so it's overridden, not refused.
        self.config(("core.fsmonitor", str(self.payload)))
        self.assertNothingRuns(
            ("status", "--short"),
            ("diff",),
            ("blame", "a.txt"),
            ("grep", "one"),
            ("ls-files", "-m"),
            ("describe", "--always", "--dirty"),
        )

    def test_hooks_are_turned_off(self):
        # status writes the index, which runs post-index-change. husky sets core.hooksPath in a
        # repo's own config, so that's overridden, not refused.
        self.hook(self.repo / ".git" / "hooks" / "post-index-change")
        self.assertNothingRuns(("status", "--short"), ("diff",))
        self.hook(self.tmp / "hooks" / "post-index-change")
        self.config(("core.hooksPath", str(self.tmp / "hooks")))
        self.assertNothingRuns(("status", "--short"), ("diff",))

    def test_hook_defined_in_config(self):
        # git 2.54 runs hooks named in config too, wherever core.hooksPath points.
        self.config(
            ("hook.x.event", "post-index-change"), ("hook.x.command", str(self.payload))
        )
        self.assertNothingRuns(
            ("status", "--short"), ("diff",), refused="hook.x.command"
        )

    def test_external_diff(self):
        (self.repo / "a.txt").write_text("changed\n")
        self.config(("diff.external", str(self.payload)))
        self.assertNothingRuns(
            ("diff",), ("diff", "HEAD~1", "HEAD"), refused="diff.external"
        )

    def test_diff_drivers(self):
        (self.repo / ".gitattributes").write_text("*.txt diff=x\n")
        (self.repo / "a.txt").write_text("changed\n")
        for key, commands in (
            ("diff.x.textconv", [("diff",), ("log", "-p"), ("show",), ("blame", "a.txt")]),
            ("diff.x.command", [("diff",), ("diff", "HEAD~1", "HEAD")]),
        ):  # fmt: skip
            with self.subTest(key=key):
                self.config((key, str(self.payload)))
                self.assertNothingRuns(*commands, refused=key)
                self.git("config", "--unset", key)

    def test_filters(self):
        (self.repo / ".gitattributes").write_text("*.txt filter=x\n")
        for key, commands in (
            ("filter.x.clean", [("status", "--short"), ("diff",), ("blame", "a.txt"),
                                ("describe", "--always", "--dirty")]),
            ("filter.x.smudge", [("cat-file", "--filters", "HEAD:a.txt")]),
            ("filter.x.process", [("status", "--short"), ("ls-files", "-m")]),
        ):  # fmt: skip
            with self.subTest(key=key):
                self.config((key, str(self.payload)))
                self.assertNothingRuns(*commands, refused=key)
                self.git("config", "--unset", key)

    def test_merge_driver(self):
        # --remerge-diff merges a merge commit's parents again, with the repo's merge drivers.
        (self.repo / ".gitattributes").write_text("*.txt merge=x\n")
        self.git("switch", "-qc", "side")
        (self.repo / "a.txt").write_text("side\n")
        self.git("commit", "-qam", "side")
        self.git("switch", "-q", "-")
        (self.repo / "a.txt").write_text("main\n")
        self.git("commit", "-qam", "main")
        self.git("merge", "-q", "-s", "ours", "side", "-m", "merge")
        self.config(("merge.x.driver", str(self.payload)))
        self.assertNothingRuns(
            ("log", "-1", "--remerge-diff"),
            ("show", "--remerge-diff"),
            refused="merge.x.driver",
        )

    def test_gpg_program(self):
        # git verifies a signed commit's signature with the gpg program for --show-signature,
        # and for any log when the repo's config sets log.showSignature.
        tree, head = self.git("rev-parse", "HEAD^{tree}", "HEAD").split()
        signed = self.git(
            "hash-object", "-t", "commit", "-w", "--stdin",
            input=f"tree {tree}\nparent {head}\nauthor t <t@example.com> 1 +0000\n"
            "committer t <t@example.com> 1 +0000\ngpgsig -----BEGIN PGP SIGNATURE-----\n \n"
            " x\n -----END PGP SIGNATURE-----\n\nsigned\n",
        )  # fmt: skip
        self.git("update-ref", "HEAD", signed.strip())
        self.config(("log.showSignature", "true"))
        for key in ("gpg.program", "gpg.openpgp.program"):
            with self.subTest(key=key):
                self.config((key, str(self.payload)))
                self.assertNothingRuns(
                    ("log", "-1"),
                    ("show",),
                    ("log", "--show-signature", "-1"),
                    refused=key,
                )
                self.git("config", "--unset", key)

    def test_included_config_counts(self):
        # Keys from a file the repo's config includes are the repo's own too.
        included = self.tmp / "included"
        included.write_text(f"[diff]\n\texternal = {self.payload}\n")
        (self.repo / "a.txt").write_text("changed\n")
        for key in ("include.path", "includeIf.gitdir:repo/.path"):
            with self.subTest(key=key):
                self.config((key, str(included)))
                self.assertNothingRuns(("diff",), refused="diff.external")
                self.git("config", "--unset", key)

    def test_worktree_config_counts(self):
        (self.repo / "a.txt").write_text("changed\n")
        self.config(("extensions.worktreeConfig", "true"))
        self.git("config", "--worktree", "diff.external", str(self.payload))
        self.assertNothingRuns(("diff",), refused="diff.external")

    def test_submodule_config_counts(self):
        # status and diff run git in each checked-out submodule, which reads that one's config.
        self.init(self.tmp / "sub")
        self.git("-c", "protocol.file.allow=always", "submodule", "add", "-q",
                 str(self.tmp / "sub"), "sub")  # fmt: skip
        self.git("commit", "-qm", "sub")
        inner = self.repo / "sub"
        (inner / ".gitattributes").write_text("*.txt filter=x\n")
        self.config(("filter.x.clean", str(self.payload)), repo=inner)
        self.stale.append(inner / "a.txt")
        self.assertNothingRuns(
            ("status", "--short"), ("diff",), refused=f"submodule {inner}"
        )

    def test_no_transport(self):
        # remote show asks the remote, and a partial clone fetches a missing object when it's
        # read: each may start ssh, an ext:: command or a local remote's uploadpack.
        other = self.tmp / "other.git"
        self.git("clone", "-q", "--bare", str(self.repo), str(other))
        for pairs in (
            [("remote.origin.url", "ssh://example.invalid/x"), ("core.sshCommand", str(self.payload))],
            [("remote.origin.url", f"ext::{self.payload}"), ("protocol.ext.allow", "always")],
            [("remote.origin.url", str(other)), ("remote.origin.uploadpack", str(self.payload))],
        ):  # fmt: skip
            with self.subTest(pairs=pairs):
                self.config(*pairs)
                self.assertNothingRuns(
                    ("remote", "show", "origin"), code=None, says="not allowed"
                )
                for key, _ in pairs:
                    self.git("config", "--unset", key)
        self.config(
            ("core.repositoryformatversion", "1"),
            ("extensions.partialClone", "origin"),
            ("remote.origin.url", f"ext::{self.payload}"),
            ("remote.origin.promisor", "true"),
            ("protocol.ext.allow", "always"),
        )
        self.assertNothingRuns(
            ("cat-file", "-p", "1" * 40), code=None, says="not allowed"
        )

    def test_environment_dropped(self):
        # git-read.py runs in the user's session, whose environment git would read as well.
        (self.repo / "a.txt").write_text("changed\n")
        for extra in (
            {"GIT_EXTERNAL_DIFF": str(self.payload)},
            {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "diff.external",
             "GIT_CONFIG_VALUE_0": str(self.payload)},
        ):  # fmt: skip
            with self.subTest(env=extra):
                self.assertNothingRuns(("diff",), env={**os.environ, **extra})

    def test_help_refused(self):
        # --help starts the manual viewer git's config names, which may be the repo's own.
        self.config(("man.viewer", "x"), ("man.x.cmd", str(self.payload)))
        self.assertNothingRuns(("log", "--help"), ("--help", "log"), refused="--help")

    def test_no_alias_stands_in(self):
        # An alias can't replace a git command, except one git is retiring: git 2.54 runs the
        # repo's alias.whatchanged in place of `git whatchanged`. So no subcommand git-read.py
        # allows may be one of those.
        spec = importlib.util.spec_from_file_location("agent_guard", GUARD)
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        subs = sorted(guard.GIT_READ | {"whatchanged"})
        self.config(*((f"alias.{sub}", f"!{self.payload}") for sub in subs))
        self.assertNothingRuns(
            *((sub, "list") if sub == "worktree" else (sub, "-h") for sub in subs),
            code=None,
        )


if __name__ == "__main__":
    unittest.main()

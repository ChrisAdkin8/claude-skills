"""Tests for skills/implement/scripts/prepare-verify.sh and run-verify.sh: the implement-verifier's
scratch export, and its launcher.

prepare-verify.sh deletes and fills only a verification's own scratch directory under
~/.cache/implement-verify: the head in src/, diff.patch, and each work item's starting state in
before/W<n>/, all as git stores them, whatever the repo's attributes say. run-verify.sh launches
claude only there, and refuses a reply.md, run.json or run.err the run left as a link or as
anything but a plain file. A stub `claude` first on PATH records its arguments and prints a
result, so nothing is sent to a model; it can also run a shell command in the scratch dir, as the
verifier's Bash calls, and the code they run, would. Both scripts run under a home of their own.

Run with: python3 -m unittest discover -s tests
"""

import json
import os
import shlex
import stat
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "implement" / "scripts"
PREPARE = SCRIPTS / "prepare-verify.sh"
RUN = SCRIPTS / "run-verify.sh"
# What the verifier reads, as prepare-verify.sh and /implement leave them.
INPUTS = (
    "brief.md", "spec.md", "record.md", "diff.patch", "diff-W1.patch", "diff-other.patch",
)  # fmt: skip
STUB = """#!/usr/bin/env python3
import json, os, subprocess, sys
with open(os.environ["STUB_CALLS"], "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(),
                        "uv": os.environ.get("UV_CACHE_DIR"),
                        "memory": os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")}) + "\\n")
if os.environ.get("STUB_DOES"):
    subprocess.run(["/bin/sh", "-c", os.environ["STUB_DOES"]], check=True)
reply = os.environ.get("STUB_REPLY", "| W | Done when |\\nVerified: 1 of 1\\nImplementation holds: yes")
print(json.dumps({"result": reply, "subtype": "success", "total_cost_usd": 0.01}))
sys.exit(int(os.environ.get("STUB_EXIT", "0")))
"""


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@local", "-c", "user.name=t", *args],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip


def commit(repo, files, message):
    for rel, text in files.items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    git(repo, "add", ".")
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD").strip()


def committed(repo, rev):
    """{path: (mode, bytes)} for each file in rev's tree, as git stores it, before any attribute
    or filter: a link's bytes are its target. A submodule has no files here."""
    tree = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "-z", rev],
        capture_output=True,
        check=True,
    ).stdout
    files = {}
    for entry in filter(None, tree.split(b"\0")):
        meta, path = entry.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        if kind == "blob":
            blob = subprocess.run(
                ["git", "-C", str(repo), "cat-file", "blob", oid],
                capture_output=True, check=True,
            ).stdout  # fmt: skip
            files[path.decode()] = (mode, blob)
    return files


def exported(root):
    """The same map for a directory, in git's modes: a link is 120000 and its target, an
    executable file 100755, any other file 100644. A directory, empty or not, isn't an entry."""
    files = {}
    for top, dirs, names in os.walk(root):
        for name in dirs + names:
            path = Path(top) / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                files[rel] = ("120000", os.fsencode(os.readlink(path)))
            elif path.is_file():
                executable = path.stat().st_mode & stat.S_IXUSR
                files[rel] = ("100755" if executable else "100644", path.read_bytes())
    return files


class Home(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        # A home of its own, so the scripts' `rm -rf` never runs in the real ~/.cache.
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.root = self.home / ".cache" / "implement-verify"
        self.name = f"test-{uuid.uuid4().hex[:8]}"
        self.scratch = self.root / self.name / "spec" / "V1"
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(STUB)
        (bin_dir / "claude").chmod(0o755)
        self.calls = self.tmp / "calls.jsonl"
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STUB_CALLS": str(self.calls),
        }
        # Unset here, so only the script can turn auto memory off.
        for var in ("RUN_AGENT_MODEL", "CLAUDE_CODE_DISABLE_AUTO_MEMORY"):
            self.env.pop(var, None)

    def run_script(self, script, *args, env=None):
        # A timeout, so a script that opens a FIFO the run left fails the test, not hangs it.
        run = subprocess.run(
            [str(script), *map(str, args)], capture_output=True, text=True, check=False,
            env=env or self.env, timeout=60,
        )  # fmt: skip
        return run.returncode, run.stdout + run.stderr


class PrepareVerify(Home):
    def setUp(self):
        super().setUp()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        self.base = commit(
            self.repo, {"a.txt": "base\n", "b.txt": "b\n"}, "spec: in progress"
        )
        self.w1 = commit(self.repo, {"a.txt": "w1\n"}, "spec: do the first thing (W1)")
        self.other = commit(self.repo, {"c.txt": "c\n"}, "readme: an aside")
        self.w2 = commit(self.repo, {"b.txt": "w2\n"}, "repo: do the second thing (W2)")
        (self.repo / "a.txt").write_text("uncommitted\n")  # never exported

    def prepare(self, scratch=None, base=None, head=None):
        return self.run_script(
            PREPARE,
            scratch or self.scratch,
            self.repo,
            base or self.base,
            head or self.w2,
        )

    def commit_what_archive_would_change(self):
        """Commits, on top of W2, files `git archive` doesn't export as committed: tests/ marked
        export-ignore, VERSION marked export-subst, a file marked eol=crlf and one marked ident,
        files under a filter driver and a diff driver, one whose diff `-diff` hides, an
        executable, a link and a submodule. Then W3 changes two of them. The drivers, set up after
        the commits as a repo's own .git/config could hold them, append to self.ran whenever git
        runs one. Returns the first commit and W3's."""
        repo = self.repo
        (repo / ".gitattributes").write_text(
            "tests/** export-ignore\nVERSION export-subst\neol.md text eol=crlf\n"
            "ident.c ident\n*.txt filter=probe diff=probe\nhidden.py -diff\n"
        )
        (repo / "VERSION").write_text("$Format:%H$\n")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_b.py").write_text("assert True\n")
        (repo / "eol.md").write_text("one\ntwo\n")
        (repo / "ident.c").write_text("/* $Id$ */\n")
        (repo / "hidden.py").write_text("before\n")
        (repo / "run.sh").write_text("#!/bin/sh\necho run\n")
        (repo / "run.sh").chmod(0o755)
        (repo / "link").symlink_to("b.txt")
        names = [
            ".gitattributes",
            "VERSION",
            "tests",
            "eol.md",
            "ident.c",
            "hidden.py",
            "run.sh",
            "link",
        ]
        git(repo, "add", *names)
        git(repo, "update-index", "--add", "--cacheinfo", f"160000,{self.base},sub")
        git(repo, "commit", "-qm", "repo: files git archive would change")
        first = git(repo, "rev-parse", "HEAD").strip()
        (repo / "hidden.py").write_text("after\n")
        (repo / "b.txt").write_text("w3\n")
        git(repo, "add", "hidden.py", "b.txt")
        git(repo, "commit", "-qm", "repo: change what attributes hide (W3)")
        w3 = git(repo, "rev-parse", "HEAD").strip()
        self.ran = self.tmp / "ran"
        log = shlex.quote(str(self.ran))
        for key, command in (
            ("filter.probe.smudge", f"echo smudge >> {log}; cat"),
            ("filter.probe.clean", f"echo clean >> {log}; cat"),
            ("diff.probe.textconv", f"echo textconv >> {log}; cat"),
            ("diff.probe.command", f"echo external diff >> {log}"),
        ):
            git(repo, "config", key, command)
        # Attributes outside the tree too, which `--attr-source` wouldn't hide.
        (repo / ".git" / "info").mkdir(exist_ok=True)
        (repo / ".git" / "info" / "attributes").write_text("*.py filter=probe\n")
        return first, w3

    def test_exports_head_and_its_diff(self):
        (self.scratch / "src").mkdir(parents=True)
        (self.scratch / "old.txt").write_text("from an earlier run\n")
        code, out = self.prepare()
        self.assertEqual(code, 0, out)
        self.assertEqual(exported(self.scratch / "src"), committed(self.repo, self.w2))
        self.assertEqual((self.scratch / "src" / "a.txt").read_text(), "w1\n")
        self.assertFalse((self.scratch / "src" / ".git").exists())
        self.assertFalse((self.scratch / "old.txt").exists())
        self.assertEqual(
            (self.scratch / "diff.patch").read_text(),
            git(self.repo, "diff", self.base, self.w2),
        )

    def test_exports_each_work_items_starting_state(self):
        code, out = self.prepare()
        self.assertEqual(code, 0, out)
        before = self.scratch / "before"
        self.assertEqual(sorted(p.name for p in before.iterdir()), ["W1", "W2"])
        self.assertEqual(exported(before / "W1"), committed(self.repo, self.base))
        self.assertEqual(exported(before / "W2"), committed(self.repo, self.other))

    def section(self, sha):
        """One commit's part of a per-item diff: a line naming it, then its diff."""
        subject = git(self.repo, "log", "-1", "--format=%s", sha).strip()
        return f"commit {sha} {subject}\n" + git(self.repo, "diff", f"{sha}^", sha)

    def test_writes_each_work_items_own_diff_and_the_rest_apart(self):
        # The verifier judges each work item's scope on its own commits, so the spec's status
        # edit, the record and the clean-up never count against one. The whole diff stays too.
        code, out = self.prepare()
        self.assertEqual(code, 0, out)
        patches = sorted(p.name for p in self.scratch.glob("*.patch"))
        self.assertEqual(
            patches,
            ["diff-W1.patch", "diff-W2.patch", "diff-other.patch", "diff.patch"],
        )
        self.assertEqual(
            (self.scratch / "diff-W1.patch").read_text(), self.section(self.w1)
        )
        self.assertEqual(
            (self.scratch / "diff-W2.patch").read_text(), self.section(self.w2)
        )
        self.assertEqual(
            (self.scratch / "diff-other.patch").read_text(), self.section(self.other)
        )

    def test_a_work_items_later_commit_joins_its_diff(self):
        (self.repo / "a.txt").write_text("w1\n")  # setUp's uncommitted edit stays out
        fix = commit(
            self.repo, {"a.txt": "w1, fixed\n"}, "spec: fix after verification"
        )
        again = commit(
            self.repo, {"d.txt": "d\n"}, "spec: the rest of the first thing (W1)"
        )
        revert = commit(
            self.repo, {"b.txt": "b\n"}, 'Revert "repo: do the second thing (W2)"'
        )
        code, out = self.prepare(head=revert)
        self.assertEqual(code, 0, out)
        self.assertEqual(
            (self.scratch / "diff-W1.patch").read_text(),
            self.section(self.w1) + self.section(again),
        )
        self.assertEqual(
            (self.scratch / "diff-W2.patch").read_text(), self.section(self.w2)
        )
        self.assertEqual(
            (self.scratch / "diff-other.patch").read_text(),
            self.section(self.other) + self.section(fix) + self.section(revert),
        )
        # Still the parent of W1's first commit.
        self.assertEqual(
            exported(self.scratch / "before" / "W1"), committed(self.repo, self.base)
        )

    def test_exports_the_committed_bytes_whatever_the_attributes_say(self):
        # `git archive` would leave tests/ out, rewrite VERSION, eol.md and ident.c, and run the
        # filter; its diff would run the textconv and show hidden.py as binary.
        first, w3 = self.commit_what_archive_would_change()
        code, out = self.prepare(head=w3)
        self.assertEqual(code, 0, out)
        src = self.scratch / "src"
        self.assertTrue((src / "tests" / "test_b.py").is_file())
        self.assertEqual((src / "VERSION").read_bytes(), b"$Format:%H$\n")
        self.assertEqual((src / "eol.md").read_bytes(), b"one\ntwo\n")
        self.assertEqual((src / "ident.c").read_bytes(), b"/* $Id$ */\n")
        self.assertTrue(os.access(src / "run.sh", os.X_OK))
        self.assertEqual(os.readlink(src / "link"), "b.txt")
        self.assertEqual(
            list((src / "sub").iterdir()), []
        )  # a submodule, as in a clone
        self.assertEqual(exported(src), committed(self.repo, w3))
        self.assertEqual(
            exported(self.scratch / "before" / "W3"), committed(self.repo, first)
        )
        patch = (self.scratch / "diff.patch").read_text()
        self.assertIn("+after", patch)  # not "Binary files differ"
        self.assertIn("+w3", patch)
        self.assertFalse(self.ran.exists(), self.ran.exists() and self.ran.read_text())

    def test_its_export_is_prepare_spikes(self):
        # One function in two scripts, so a fix to one reaches the other.
        def export_tree(script):
            text = script.read_text()
            start = text.index("\nexport_tree() {")
            return text[start : text.index("\n}\n", start)]

        spike = SCRIPTS.parents[1] / "spec" / "scripts" / "prepare-spike.sh"
        self.assertEqual(export_tree(PREPARE), export_tree(spike))

    def test_refuses_a_tree_that_would_write_outside_the_export(self):
        # Trees git's own commands never make, but `git mktree` will: tar refused these paths,
        # and the export must too.
        def run(*args, stdin=""):
            return subprocess.run(
                ["git", "-C", str(self.repo), "-c", "user.email=t@local", "-c", "user.name=t",
                 *args],
                input=stdin, capture_output=True, text=True, check=True,
            ).stdout.strip()  # fmt: skip

        outside = self.tmp / "outside"
        outside.mkdir()
        blob = run("hash-object", "-w", "--stdin", stdin="x\n")
        link = run("hash-object", "-w", "--stdin", stdin=str(outside))
        sub = run("mktree", stdin=f"100644 blob {blob}\tb\n")
        for listing in (
            f"040000 tree {sub}\t..\n",  # ../b
            f"040000 tree {sub}\t.git\n",  # .git/b
            f"120000 blob {link}\ta\n040000 tree {sub}\ta\n",  # a, a link out, and a/b
        ):
            with self.subTest(listing=listing):
                tree = run("mktree", stdin=listing)
                head = run("commit-tree", tree, "-p", self.w2, "-m", "crafted")
                code, out = self.prepare(head=head)
                self.assertEqual(code, 2, out)
                self.assertEqual(list(outside.iterdir()), [])
                self.assertFalse((self.scratch / "b").exists())

    def test_refuses_paths_outside_its_scratch_layout(self):
        victim = self.tmp / "victim"
        victim.mkdir()
        for scratch in (
            victim,  # anywhere else
            self.root / self.name / "V1",  # a level missing
            self.root / self.name / "spec" / "V1" / "deeper",
            self.root
            / self.name
            / "spec"
            / "S1",  # a spike's name, not a verification's
            self.root / self.name / ".." / ".." / "V1",
            self.root / self.name / "spec" / ".." / "V1",
            f"{self.root}/{self.name}/spec/V1 {victim}",
            self.home / ".cache" / "spec-spikes" / self.name / "spec" / "V1",
        ):
            with self.subTest(scratch=scratch):
                code, out = self.prepare(scratch)
                self.assertEqual(code, 2, out)
        self.assertTrue(victim.is_dir())

    def test_refuses_a_symlinked_parent(self):
        outside = self.tmp / "outside"
        (outside / "spec" / "V1").mkdir(parents=True)
        (outside / "spec" / "V1" / "keep.txt").write_text("keep\n")
        self.root.mkdir(parents=True)
        (self.root / self.name).symlink_to(outside)
        code, out = self.prepare()
        self.assertEqual(code, 2, out)
        self.assertIn("outside", out)
        self.assertTrue((outside / "spec" / "V1" / "keep.txt").exists())

    def test_refuses_a_symlinked_scratch(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_text("keep\n")
        self.scratch.parent.mkdir(parents=True)
        self.scratch.symlink_to(outside)
        code, out = self.prepare()
        self.assertEqual(code, 2, out)
        self.assertTrue((outside / "keep.txt").exists())

    def test_refuses_bad_revs_and_repos(self):
        for base, head in (
            ("--output=/tmp/x", self.w2),
            (self.base, "-p"),
            ("abcdef0", self.w2),  # not a commit here
        ):
            with self.subTest(base=base, head=head):
                code, out = self.prepare(base=base, head=head)
                self.assertEqual(code, 2, out)
        code, out = self.run_script(PREPARE, self.scratch, self.tmp, self.base, self.w2)
        self.assertEqual(code, 2, out)
        self.assertFalse(self.scratch.exists())

    def test_wrong_argument_count(self):
        self.assertEqual(self.run_script(PREPARE, self.scratch)[0], 2)


class RunVerify(Home):
    def make_scratch(self, files=("brief.md", "spec.md", "diff.patch"), scratch=None):
        scratch = scratch or self.scratch
        (scratch / "src").mkdir(parents=True, exist_ok=True)
        for name in files:
            (scratch / name).write_text("the brief\n" if name == "brief.md" else "x\n")
        return scratch

    def calls_made(self):
        if not self.calls.exists():
            return []
        return [json.loads(line) for line in self.calls.read_text().splitlines()]

    def verify_that_does(self, n, does, status=0, reply=None, files=INPUTS):
        """Runs V<n>, a scratch dir of its own holding `files`, whose stub verifier runs `does`
        there and exits `status`. Returns the scratch dir, the exit code and the output."""
        scratch = self.make_scratch(files, scratch=self.scratch.parent / f"V{n}")
        env = {**self.env, "STUB_DOES": does, "STUB_EXIT": str(status)}
        if reply is not None:
            env["STUB_REPLY"] = reply
        code, out = self.run_script(RUN, scratch, env=env)
        return scratch, code, out

    def secret(self):
        """A file outside the scratch dir, for a run to link to."""
        secret = self.tmp / "secret"
        secret.write_text("a secret\n")
        return secret

    def test_keeps_claudes_status_and_the_files_the_run_wrote(self):
        for n, status in enumerate((0, 1, 7), start=1):
            with self.subTest(status=status):
                scratch, code, out = self.verify_that_does(
                    n, "echo notes > notes.md", status
                )
                self.assertEqual(code, status, out)
                self.assertIn(
                    "Implementation holds: yes", (scratch / "reply.md").read_text()
                )
                self.assertIn("total_cost_usd", (scratch / "run.json").read_text())

    def test_refuses_and_removes_a_planted_link(self):
        # The sandbox stops the verifier, and the code it runs, reading ~/.ssh, but not linking
        # to it from the scratch dir. This script then writes reply.md, outside the sandbox, and
        # /implement's session reads all three files.
        secret = self.secret()
        outside = self.tmp / "outside"
        outside.mkdir()
        s, o = shlex.quote(str(secret)), shlex.quote(str(outside))
        cases = (
            (["reply.md"], f"ln -s {s} reply.md"),
            # claude's output still goes to the file the script opened, now unlinked.
            (["run.json"], f"rm run.json && ln -s {s} run.json"),
            (["run.err"], f"rm run.err && ln -s {s} run.err"),
            (["reply.md"], "ln -s /nonexistent/key reply.md"),  # to nothing
            (["reply.md"], f"ln -s {o} reply.md"),  # to a directory
            (
                ["reply.md", "run.err"],
                f"ln -s {s} reply.md && rm run.err && ln -s {s} run.err",
            ),
        )
        for n, (names, does) in enumerate(cases, start=1):
            with self.subTest(does=does):
                scratch, code, out = self.verify_that_does(n, does)
                self.assertEqual(code, 4, out)
                self.assertNotIn("Traceback", out)
                for name in names:
                    self.assertFalse(os.path.lexists(scratch / name), name)
                    self.assertIn(f"{name} was a symlink", out)
                # The run chose the target, so it isn't repeated into /implement's session.
                for target in (str(secret), str(outside), "/nonexistent"):
                    self.assertNotIn(target, out)
        self.assertEqual(secret.read_text(), "a secret\n")
        self.assertEqual(list(outside.iterdir()), [])

    def ledger_lines(self):
        path = self.home / ".cache" / "implement-ledger" / f"{self.name}--spec.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_a_run_leaves_its_cost_in_the_ledger(self):
        self.verify_that_does(1, "true")
        (line,) = self.ledger_lines()
        self.assertEqual(line["who"], "verifier V1")
        self.assertEqual(line["usd"], 0.01)
        self.verify_that_does(2, "true", status=1)
        self.assertEqual(
            [(l["who"], l["usd"]) for l in self.ledger_lines()],
            [("verifier V1", 0.01), ("verifier V2", 0.01)],
        )

    def test_a_refused_run_leaves_a_null_cost(self):
        _, code, out = self.verify_that_does(1, f"ln -s {shlex.quote(str(self.secret()))} reply.md")
        self.assertEqual(code, 4, out)
        (line,) = self.ledger_lines()
        self.assertEqual((line["who"], line["usd"]), ("verifier V1", None))

    def test_refuses_and_removes_what_isnt_a_regular_file(self):
        # A directory can hold links of its own, and a FIFO stalls whoever opens it.
        secret = self.secret()
        cases = (
            ("run.json", "rm run.json && mkdir run.json"),
            (
                "reply.md",
                f"mkdir reply.md && ln -s {shlex.quote(str(secret))} reply.md/key",
            ),
            ("reply.md", "mkfifo reply.md"),
            ("run.err", "rm run.err && mkfifo run.err"),
        )
        for n, (name, does) in enumerate(cases, start=1):
            with self.subTest(does=does):
                scratch, code, out = self.verify_that_does(n, does)
                self.assertEqual(code, 4, out)
                self.assertNotIn("Traceback", out)
                self.assertFalse(os.path.lexists(scratch / name), name)
                self.assertIn(f"{name} was not a regular file", out)
        self.assertEqual(secret.read_text(), "a secret\n")

    def test_a_link_gives_4_whatever_claude_or_the_reply_says(self):
        # On any other code /implement reads the files, so 4 comes before claude's status and 3.
        does = f"ln -s {shlex.quote(str(self.secret()))} reply.md"
        for n, (status, reply) in enumerate(
            ((1, None), (0, "Request timed out")), start=1
        ):
            with self.subTest(status=status, reply=reply):
                scratch, code, out = self.verify_that_does(n, does, status, reply)
                self.assertEqual(code, 4, out)
                self.assertNotIn("Traceback", out)
                self.assertFalse(os.path.lexists(scratch / "reply.md"))

    @unittest.skipIf(os.geteuid() == 0, "root can remove it anyway")
    def test_refuses_a_link_it_cant_remove(self):
        # A run may take away its own scratch dir's write permission, so the link stays. Exit 4
        # still tells /implement not to read it, and nothing writes through it.
        secret = self.secret()
        scratch = self.scratch
        self.addCleanup(lambda: scratch.chmod(0o755))
        _, code, out = self.verify_that_does(
            1, f"ln -s {shlex.quote(str(secret))} reply.md && chmod a-w ."
        )
        self.assertEqual(code, 4, out)
        self.assertNotIn("Traceback", out)
        self.assertIn("reply.md was a symlink", out)
        self.assertIn("couldn't remove it", out)
        self.assertEqual(secret.read_text(), "a secret\n")

    def test_refuses_a_run_that_changed_its_inputs(self):
        # The code a Done when runs can write anywhere in the scratch dir, so it could rewrite
        # what the verifier reads, to change the verdict.
        s = shlex.quote(str(self.secret()))
        cases = (
            ("diff.patch", "echo '+a change no work item made' >> diff.patch", 0),
            ("spec.md", "echo 'Done when: true' > spec.md", 0),
            ("record.md", "rm record.md", 0),
            ("brief.md", "echo 'Work items: none' > brief.md", 0),
            ("diff-W1.patch", "echo > diff-W1.patch", 0),
            (
                "diff-other.patch",
                f"rm diff-other.patch && ln -s {s} diff-other.patch",
                0,
            ),
            ("spec.md", "rm spec.md && mkdir spec.md", 0),
            ("diff.patch", "chmod a-r diff.patch", 0),
            ("diff.patch", "echo >> diff.patch", 1),  # whatever claude's status
        )
        for n, (name, does, status) in enumerate(cases, start=1):
            with self.subTest(does=does):
                scratch, code, out = self.verify_that_does(n, does, status)
                self.assertEqual(code, 4, out)
                self.assertNotIn("Traceback", out)
                self.assertIn(f"run-verify: {name} changed during the run", out)
                self.assertFalse((scratch / "reply.md").exists())

    def test_refuses_a_diff_the_run_made_for_a_work_item(self):
        # W2 had no commit, so no diff-W2.patch: one made during the run would give it one.
        for n, name in enumerate(("diff-W2.patch", "diff-other.patch"), start=1):
            with self.subTest(name=name):
                files = tuple(f for f in INPUTS if f != "diff-other.patch")
                scratch, code, out = self.verify_that_does(
                    n, f"echo x > {name}", files=files
                )
                self.assertEqual(code, 4, out)
                self.assertNotIn("Traceback", out)
                self.assertIn(f"run-verify: {name} changed during the run", out)

    def test_the_verifier_may_write_in_src_before_and_its_own_files(self):
        does = (
            "mkdir -p before/W1 && echo x > before/W1/test_new.py && echo y > src/out.txt"
            " && echo z > notes.md && echo w > diff-notes.patch"
        )
        for n, files in enumerate(
            (INPUTS, ("brief.md", "spec.md", "diff.patch")), start=1
        ):
            with self.subTest(files=files):
                scratch, code, out = self.verify_that_does(n, does, files=files)
                self.assertEqual(code, 0, out)
                self.assertIn(
                    "Implementation holds: yes", (scratch / "reply.md").read_text()
                )

    def test_refuses_an_input_thats_a_link_before_the_run(self):
        # brief.md becomes claude's prompt, read outside the sandbox.
        scratch = self.make_scratch(INPUTS)
        (scratch / "brief.md").unlink()
        (scratch / "brief.md").symlink_to(self.secret())
        code, out = self.run_script(RUN, scratch)
        self.assertEqual(code, 2, out)
        self.assertEqual(self.calls_made(), [])

    def test_a_link_left_from_an_earlier_run_is_cleared_first(self):
        # The script writes run.json and run.err through a shell redirect, which would follow a
        # link that an earlier, refused run couldn't remove.
        secret = self.secret()
        scratch = self.make_scratch()
        for name in ("reply.md", "run.json", "run.err"):
            (scratch / name).symlink_to(secret)
        code, out = self.run_script(RUN, scratch)
        self.assertEqual(code, 0, out)
        self.assertEqual(secret.read_text(), "a secret\n")
        for name in ("reply.md", "run.json", "run.err"):
            self.assertFalse((scratch / name).is_symlink(), name)

    def test_refuses_a_path_outside_its_root_whether_or_not_it_exists(self):
        made = self.tmp / "x"
        made.mkdir()
        for path in ("/tmp/x", made, self.tmp / "missing"):
            with self.subTest(path=path):
                code, out = self.run_script(RUN, path)
                self.assertEqual(code, 2, out)
                self.assertIn("not under ~/.cache/implement-verify/", out)
        self.assertEqual(self.calls_made(), [])

    def test_refuses_other_layouts_and_missing_files(self):
        self.make_scratch()
        for path in (
            self.root,
            self.root / self.name / "spec",
            self.root / self.name / "spec" / "V1" / "src",
            self.root / self.name / "spec" / ".." / "spec" / "V1",
            self.root / self.name / "spec" / "V2",  # missing
        ):
            with self.subTest(path=path):
                code, out = self.run_script(RUN, path)
                self.assertEqual(code, 2, out)
        (self.scratch / "spec.md").unlink()
        code, out = self.run_script(RUN, self.scratch)
        self.assertEqual(code, 2, out)
        self.assertIn("missing", out)
        self.assertEqual(self.calls_made(), [])

    def test_refuses_a_symlink_out_of_the_root(self):
        outside = self.tmp / "outside"
        (outside / "spec" / "V1" / "src").mkdir(parents=True)
        for name in ("brief.md", "spec.md", "diff.patch"):
            (outside / "spec" / "V1" / name).write_text("x\n")
        self.root.mkdir(parents=True)
        (self.root / self.name).symlink_to(outside)
        code, out = self.run_script(RUN, self.scratch)
        self.assertEqual(code, 2, out)
        self.assertEqual(self.calls_made(), [])

    def test_runs_in_scratch_with_verify_settings_and_prompt(self):
        self.make_scratch()
        code, out = self.run_script(RUN, self.scratch)
        self.assertEqual(code, 0, out)
        (call,) = self.calls_made()
        argv = call["argv"]
        flag = lambda name: argv[argv.index(name) + 1]
        self.assertEqual(Path(call["cwd"]).resolve(), self.scratch.resolve())
        self.assertEqual(
            flag("--settings"), str(SCRIPTS.parent / "verify-settings.json")
        )
        self.assertEqual(
            flag("--append-system-prompt-file"), str(SCRIPTS.parent / "verifier.md")
        )
        self.assertTrue((SCRIPTS.parent / "verifier.md").is_file())
        self.assertEqual(flag("--max-budget-usd"), "5")
        self.assertEqual(flag("--max-turns"), "100")
        self.assertEqual(flag("--setting-sources"), "user")
        self.assertEqual(
            flag("--allowedTools"), "Read Grep Glob Bash Write(./**) Edit(./**)"
        )
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[-1], "the brief")
        self.assertTrue(call["uv"].endswith("/.cache/spec-spikes/.uv-cache"))
        self.assertEqual(call["memory"], "1")  # no auto memory, as in run-agent.sh
        self.assertIn(
            "Implementation holds: yes", (self.scratch / "reply.md").read_text()
        )
        self.assertIn("total_cost_usd", (self.scratch / "run.json").read_text())

    def test_model_only_when_run_agent_model_is_set(self):
        self.make_scratch()
        self.run_script(RUN, self.scratch)
        self.run_script(RUN, self.scratch, env={**self.env, "RUN_AGENT_MODEL": "opus"})
        without, with_model = (c["argv"] for c in self.calls_made())
        self.assertNotIn("--model", without)
        self.assertEqual(with_model[with_model.index("--model") + 1], "opus")

    def test_a_reply_without_its_closing_lines_exits_3(self):
        self.make_scratch()
        for reply in (
            "Request timed out",
            "| W | Done when |\nVerified: 1 of 1",  # no Implementation holds
            "| W | Done when |\nImplementation holds: yes",  # no Verified
            "Verified: one of two\nImplementation holds: maybe",
        ):
            with self.subTest(reply=reply):
                code, out = self.run_script(
                    RUN, self.scratch, env={**self.env, "STUB_REPLY": reply}
                )
                self.assertEqual(code, 3, out)
                self.assertIn("reply.md", out)
                self.assertEqual((self.scratch / "reply.md").read_text(), reply + "\n")


if __name__ == "__main__":
    unittest.main()

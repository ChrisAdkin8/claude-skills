"""Tests for skills/implement/scripts/run-implementer.sh: the launcher /implement runs the
implementer with. It refuses a working directory that isn't a git worktree of a repo under
~/code, builds the `claude -p --agents ... --agent implementer` command, checks the reply's closing
`Implementer:` line, and keeps the whole run, resumes included, under one cap.

A stub `claude` first on PATH records its arguments and prints a result, so nothing is sent to a
model. Everything runs under a home of its own.
Run with: python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "skills" / "implement" / "scripts" / "run-implementer.sh"
STUB = """#!/usr/bin/env python3
import json, os, sys
calls = os.environ["STUB_CALLS"]
with open(calls, "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(),
                        "root": os.environ.get("CLAUDE_PLUGIN_ROOT"),
                        "memory": os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY")}) + "\\n")
n = sum(1 for _ in open(calls))
exec(os.environ.get("STUB_EXEC", ""))
tail = os.environ.get("STUB_TAIL", "Implementer: done")
out = {"session_id": "sess-1", "result": f"reply {n}\\n{tail}", "subtype": "success"}
cost = os.environ.get("STUB_COST", "0.5")
if cost != "none":
    out["total_cost_usd"] = float(cost)
print(json.dumps(out))
"""
LEDGER = REPO / "skills" / "implement" / "scripts" / "ledger.py"
VERIFY = REPO / "skills" / "implement" / "scripts" / "run-verify.sh"


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@local", "-c", "user.name=t", *args],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip


class RunImplementer(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name).resolve()
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        (bin_dir / "claude").write_text(STUB)
        (bin_dir / "claude").chmod(0o755)
        self.calls = self.tmp / "calls.jsonl"
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = {
            **os.environ,
            "HOME": str(self.home),
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "STUB_CALLS": str(self.calls),
        }
        # CLAUDE_CODE_DISABLE_AUTO_MEMORY is unset here, so only the script can turn it on.
        for var in (
            "RUN_AGENT_MODEL",
            "IMPLEMENT_MAX_USD",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
        ):
            self.env.pop(var, None)
        # A repo under ~/code, and the worktree /implement would add beside it.
        self.repo = self.home / "code" / "proj"
        self.repo.mkdir(parents=True)
        git(self.repo, "init", "-q")
        (self.repo / "a.txt").write_text("a\n")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-qm", "base")
        self.worktree = self.home / "code" / "proj-worktrees" / "spec"
        git(
            self.repo,
            "worktree",
            "add",
            "-q",
            str(self.worktree),
            "-b",
            "implement/spec",
        )
        self.run_dir = (
            self.home / ".cache" / "implement-runs" / "proj--spec" / "implementer"
        )

    def brief(self, text="Implement it.\n"):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "brief.md").write_text(text)

    def launch(self, *args):
        run = subprocess.run(
            [str(SCRIPT), *map(str, args)],
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )
        return run.returncode, run.stdout + run.stderr

    def calls_made(self):
        return (
            [json.loads(line) for line in self.calls.read_text().splitlines()]
            if self.calls.exists()
            else []
        )

    def flag(self, argv, name):
        return argv[argv.index(name) + 1] if name in argv else None

    def test_is_executable(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_refuses_a_directory_outside_code_or_not_a_worktree(self):
        self.brief()
        # A worktree of a repo outside ~/code.
        outside = self.tmp / "elsewhere" / "proj"
        outside.mkdir(parents=True)
        git(outside, "init", "-q")
        (outside / "a.txt").write_text("a\n")
        git(outside, "add", "a.txt")
        git(outside, "commit", "-qm", "base")
        outside_wt = self.tmp / "elsewhere" / "wt"
        git(outside, "worktree", "add", "-q", str(outside_wt), "-b", "implement/spec")
        plain = self.home / "code" / "plain"
        plain.mkdir()
        for work in (
            outside_wt,  # a worktree, but not under ~/code
            plain,  # under ~/code, not a git repo
            self.repo,  # the repo's own checkout, not a worktree of it
            self.home / "code" / "missing",
        ):
            with self.subTest(work=work):
                code, out = self.launch(work, self.run_dir)
                self.assertEqual(code, 2, out)
        self.assertEqual(self.calls_made(), [])

    def test_refuses_other_run_dirs_and_options(self):
        self.brief()
        root = self.home / ".cache" / "implement-runs"
        for args in (
            (self.worktree, self.tmp / "elsewhere"),
            (self.worktree, root / "proj--spec"),  # one level short
            (self.worktree, root / "proj--spec" / ".." / "x" / "y"),
            (self.worktree, self.run_dir, "--force"),
            (self.worktree,),
        ):
            with self.subTest(args=args):
                code, out = self.launch(*args)
                self.assertEqual(code, 2, out)
        self.assertEqual(self.calls_made(), [])

    def test_needs_a_brief(self):
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 2, out)
        self.assertIn("brief.md", out)

    def test_builds_the_implementer_command(self):
        self.brief()
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 0, out)
        (call,) = self.calls_made()
        argv = call["argv"]
        self.assertEqual(argv[:1], ["-p"])
        self.assertEqual(self.flag(argv, "--agent"), "implementer")
        agents = Path(self.flag(argv, "--agents"))
        self.assertEqual(agents, self.run_dir / "agents.json")
        defs = json.loads(agents.read_text())
        self.assertEqual(list(defs), ["implementer"])
        self.assertNotIn("hooks", defs["implementer"])
        self.assertNotIn("${", defs["implementer"]["prompt"])
        self.assertEqual(
            defs["implementer"]["tools"],
            ["Read", "Edit", "Write", "Glob", "Grep", "Bash", "Skill"],
        )
        # Edits are pre-approved only in the worktree and the scratch dir.
        scratch = self.run_dir.parent / "scratch"
        self.assertEqual(
            self.flag(argv, "--allowedTools"),
            "Read,Edit(./**),Edit(~/.cache/implement-runs/proj--spec/scratch/**),"
            "Glob,Grep,Bash,Skill",
        )
        # Only the user's settings load, under a sandbox of the run's own.
        self.assertEqual(self.flag(argv, "--setting-sources"), "user")
        self.assertEqual(self.flag(argv, "--permission-mode"), "acceptEdits")
        self.assertEqual(Path(self.flag(argv, "--settings")), self.run_dir / "settings.json")
        self.assertEqual(argv.count("--add-dir"), 1)
        self.assertEqual(Path(self.flag(argv, "--add-dir")), scratch)
        self.assertTrue(argv[argv.index("--add-dir") + 2].startswith("--"))
        self.assertTrue(scratch.is_dir())
        self.assertEqual(self.flag(argv, "--max-budget-usd"), "20")
        self.assertEqual(self.flag(argv, "--output-format"), "json")
        self.assertNotIn("--resume", argv)
        self.assertNotIn("--model", argv)
        self.assertEqual(argv[-1], "Implement it.")
        self.assertEqual(argv[-2], "--")
        self.assertEqual(Path(call["cwd"]).resolve(), self.worktree.resolve())
        self.assertEqual(call["root"], str(REPO))
        # No auto memory: it would read, and could write, the memory the user's own sessions load.
        self.assertEqual(call["memory"], "1")
        self.assertTrue((self.run_dir / "reply.md").read_text().startswith("reply 1\n"))
        self.assertEqual((self.run_dir / "session_id").read_text(), "sess-1")
        self.assertTrue((self.run_dir / "run.json").exists())
        self.assertTrue((self.run_dir / "run-1.json").exists())

    def settings(self):
        (call,) = self.calls_made()
        return json.loads(Path(self.flag(call["argv"], "--settings")).read_text())

    def test_the_call_is_sandboxed_to_the_worktree(self):
        self.brief()
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 0, out)
        settings = self.settings()
        self.assertNotIn("${", json.dumps(settings))
        sandbox = settings["sandbox"]
        self.assertIs(sandbox["enabled"], True)
        self.assertIs(sandbox["allowUnsandboxedCommands"], False)
        self.assertEqual(sandbox["network"]["allowedDomains"], [])
        common = (self.repo / ".git").resolve()
        git_dir = common / "worktrees" / "spec"
        tmp = subprocess.run(
            ["getconf", "DARWIN_USER_TEMP_DIR"], capture_output=True, text=True, check=True
        ).stdout.strip()
        allow = sandbox["filesystem"]["allowWrite"]
        deny = sandbox["filesystem"]["denyWrite"]
        for path in (
            self.worktree,
            git_dir,
            common / "objects",
            common / "refs" / "heads" / "implement",
            self.run_dir.parent / "scratch",
            Path(tmp).resolve(),
        ):
            with self.subTest(allow=path):
                self.assertIn(str(path), allow)
        for path in ("config", "hooks"):
            self.assertNotIn(str(common / path), allow)
        for path in (
            common / "config",
            common / "hooks",
            common / "HEAD",
            common / "index",
            common / "packed-refs",
            common / "modules",
            git_dir / "config.worktree",
            git_dir / "commondir",
            git_dir / "gitdir",
            self.worktree / ".git",
            self.worktree / ".claude",
        ):
            with self.subTest(deny=path):
                self.assertIn(str(path), deny)
        self.assertIn("~/.cache/implement-ledger", deny)
        deny_rules = settings["permissions"]["deny"]
        for rule in ("Bash(gh *)", "WebFetch", "WebSearch", "Edit(~/.cache/implement-ledger/**)"):
            self.assertIn(rule, deny_rules)

    def test_other_worktrees_are_denied_to_the_call(self):
        self.brief()
        other = self.home / "code" / "proj-worktrees" / "other"
        git(self.repo, "worktree", "add", "-q", str(other), "-b", "other")
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        deny = self.settings()["sandbox"]["filesystem"]["denyWrite"]
        theirs = (self.repo / ".git").resolve() / "worktrees" / "other"
        for name in ("commondir", "gitdir", "HEAD", "config.worktree", "index"):
            with self.subTest(name=name):
                self.assertIn(str(theirs / name), deny)
        ours = (self.repo / ".git").resolve() / "worktrees" / "spec"
        self.assertNotIn(str(ours / "HEAD"), deny)

    def test_a_widening_user_setting_is_refused(self):
        self.brief()
        settings = self.home / ".claude" / "settings.json"
        settings.parent.mkdir()
        for sandbox, key in (
            ({"excludedCommands": ["git *"]}, "excludedCommands"),
            ({"enabled": False}, "enabled"),
            ({"allowUnsandboxedCommands": True}, "allowUnsandboxedCommands"),
            ({"filesystem": {"allowWrite": ["~/code"]}}, "allowWrite"),
            ({"network": {"allowedDomains": ["github.com"]}}, "allowedDomains"),
            ({"network": {"allowLocalBinding": True}}, "allowLocalBinding"),
            ({"network": {"strictAllowlist": False}}, "strictAllowlist"),
            ({"network": {"strictAllowlist": None}}, "strictAllowlist"),
        ):
            with self.subTest(sandbox=sandbox):
                settings.write_text(json.dumps({"sandbox": sandbox}))
                code, out = self.launch(self.worktree, self.run_dir)
                self.assertEqual(code, 2, out)
                self.assertIn(key, out)
        # strictAllowlist: true is what the implementer sets, so only the other key is named.
        network = {"strictAllowlist": True, "httpProxyPort": 8080}
        settings.write_text(json.dumps({"sandbox": {"network": network}}))
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 2, out)
        self.assertIn("httpProxyPort", out)
        self.assertNotIn("strictAllowlist", out)
        self.assertEqual(self.calls_made(), [])
        network = {"allowedDomains": [], "strictAllowlist": True}
        settings.write_text(json.dumps(
            {"sandbox": {"enabled": True, "excludedCommands": [], "network": network}, "model": "x"}
        ))
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)

    def stub_does(self, code):
        """The stub runs `code` (Python, with os, `common`, `git_dir` and `run` to hand) in the
        worktree during the call, as the implementer's Bash would."""
        self.env["STUB_EXEC"] = (
            "import subprocess, pathlib\n"
            f"common = pathlib.Path({str((self.repo / '.git').resolve())!r})\n"
            "git_dir = common / 'worktrees' / 'spec'\n"
            "def run(*a): subprocess.run(a, check=True, capture_output=True)\n" + code
        )

    def test_a_change_to_the_shared_git_config_or_hooks_exits_4(self):
        def cases(marker, inside):
            hook = f"#!/bin/sh\ntouch {marker}\n"
            return (
                ("config", "run('git', '-C', str(common.parent), 'config', 'core.fsmonitor',"
                 f" 'touch {marker}')"),
                ("hooks/post-commit", f"(common / 'hooks' / 'post-commit').write_text({hook!r})\n"
                 "(common / 'hooks' / 'post-commit').chmod(0o755)"),
                (".git", "pathlib.Path('.git').write_text('gitdir: /elsewhere\\n')"),
                ("config.worktree",
                 "(git_dir / 'config.worktree').write_text('[core]\\n\\tfsmonitor = x\\n')"),
                ("worktrees/spec/commondir", f"run('git', 'init', '-q', {str(inside)!r})\n"
                 f"(git_dir / 'commondir').write_text({str(inside / '.git')!r} + '\\n')"),
                ("worktrees/other/commondir",
                 f"(common / 'worktrees' / 'other' / 'commondir').write_text({str(inside)!r})"),
                ("modules/sub/config", "(common / 'modules' / 'sub').mkdir(parents=True)\n"
                 "(common / 'modules' / 'sub' / 'config').write_text('[core]\\n')"),
                ("modules/sub/config", "(git_dir / 'modules' / 'sub').mkdir(parents=True)\n"
                 "(git_dir / 'modules' / 'sub' / 'config')"
                 ".write_text('[core]\\n\\tfsmonitor = touch x\\n')"),
            )  # fmt: skip

        for n in range(8):
            # Each case from a repo, worktree and home of its own.
            self.setUp()
            self.brief()
            other = self.home / "code" / "proj-worktrees" / "other"
            git(self.repo, "worktree", "add", "-q", str(other), "-b", "other")
            marker = self.tmp / "marker"
            path, code = cases(marker, self.worktree / "evil")[n]
            with self.subTest(path=path, n=n):
                self.stub_does(code)
                status, out = self.launch(self.worktree, self.run_dir)
                self.assertEqual(status, 4, out)
                self.assertIn(path, out)
                self.assertFalse((self.run_dir / "reply.md").exists())
                self.assertFalse(marker.exists())

    def test_a_submodules_sample_hooks_are_not_refused(self):
        # git copies its template's *.sample hooks into each submodule it clones.
        self.brief()
        self.stub_does(
            "(git_dir / 'modules' / 'sub' / 'hooks').mkdir(parents=True)\n"
            "(git_dir / 'modules' / 'sub' / 'hooks' / 'pre-commit.sample').write_text('#!/bin/sh\\n')\n"
            "(git_dir / 'modules' / 'sub' / 'config').write_text('[core]\\n\\tbare = false\\n')"
        )
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 0, out)

    def test_a_submodule_config_with_an_include_exits_4(self):
        for key in ("[include]\\n\\tpath = x", '[includeIf "gitdir:/"]\\n\\tpath = x'):
            self.setUp()
            self.brief()
            with self.subTest(key=key):
                self.stub_does(
                    "(git_dir / 'modules' / 'sub').mkdir(parents=True)\n"
                    f"(git_dir / 'modules' / 'sub' / 'config').write_text('{key}\\n')"
                )
                code, out = self.launch(self.worktree, self.run_dir)
                self.assertEqual(code, 4, out)
                self.assertIn("modules/sub/config sets", out)

    def test_a_commit_in_the_main_checkout_is_named_not_refused(self):
        self.brief()
        branch = git(self.repo, "symbolic-ref", "--short", "HEAD").strip()
        self.stub_does(
            "pathlib.Path(common.parent, 'b.txt').write_text('b')\n"
            "run('git', '-C', str(common.parent), 'add', 'b.txt')\n"
            "run('git', '-C', str(common.parent), '-c', 'user.email=t@l', '-c', 'user.name=t',"
            " 'commit', '-qm', 'mine')\n"
        )
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 0, out)
        self.assertIn(f"moved during the run: refs/heads/{branch} ", out)
        self.assertNotIn("implement/spec", out.split("moved during the run:", 1)[1].splitlines()[0])

    def test_a_repo_with_many_refs_is_not_refused(self):
        # The before-snapshot holds every ref. Passed on the command line, 20,000 of them were
        # over macOS's 1 MB argument limit, so every call exited 4.
        self.brief()
        head = git(self.repo, "rev-parse", "HEAD").strip()
        refs = "".join(f"{head} refs/tags/t{n:05}\n" for n in range(20000))
        (self.repo / ".git" / "packed-refs").write_text(refs)
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 0, out)

    def test_cap_and_model_from_the_environment(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "5"
        self.env["RUN_AGENT_MODEL"] = "sonnet"
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 0, out)
        (call,) = self.calls_made()
        self.assertEqual(self.flag(call["argv"], "--max-budget-usd"), "5")
        self.assertEqual(self.flag(call["argv"], "--model"), "sonnet")

    def test_reply_without_an_implementer_line_exits_3(self):
        self.brief()
        for tail in (
            "All done, I think.",
            "Implementer: done\nand one more thing",
            "Implementer: question:",
            "Implementer: finished",
        ):
            with self.subTest(tail=tail):
                self.env["STUB_TAIL"] = tail
                code, out = self.launch(self.worktree, self.run_dir)
                self.assertEqual(code, 3, out)
        for tail in (
            "Implementer: done",
            "Implementer: question: W1's test conflicts; change it?",
            "Implementer: stopped: a third failed attempt at W2\n",
        ):
            with self.subTest(tail=tail):
                self.env["STUB_TAIL"] = tail
                code, out = self.launch(self.worktree, self.run_dir)
                self.assertEqual(code, 0, out)

    def test_resume_gets_the_cap_less_what_was_spent(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "10"
        self.env["STUB_COST"] = "2.5"
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 0, out)
        (self.run_dir / "followup.md").write_text("The user says yes.\n")
        self.env["STUB_COST"] = "4"
        code, out = self.launch(self.worktree, self.run_dir, "--resume")
        self.assertEqual(code, 0, out)
        code, out = self.launch(self.worktree, self.run_dir, "--resume")
        self.assertEqual(code, 0, out)
        first, second, third = (c["argv"] for c in self.calls_made())
        self.assertEqual(self.flag(first, "--max-budget-usd"), "10")
        self.assertEqual(self.flag(second, "--max-budget-usd"), "7.5")
        self.assertEqual(self.flag(third, "--max-budget-usd"), "3.5")
        self.assertEqual(self.flag(second, "--resume"), "sess-1")
        self.assertEqual(second[-2:], ["--", "The user says yes."])
        # Every call's result is kept, and every earlier reply.
        for n in (1, 2, 3):
            self.assertTrue((self.run_dir / f"run-{n}.json").exists(), n)
        self.assertTrue(
            (self.run_dir / "reply-1.md").read_text().startswith("reply 1\n")
        )
        self.assertTrue((self.run_dir / "reply.md").read_text().startswith("reply 3\n"))

    def test_resume_refused_once_the_cap_is_spent(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "5"
        self.env["STUB_COST"] = "3"
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        (self.run_dir / "followup.md").write_text("Carry on.\n")
        self.assertEqual(self.launch(self.worktree, self.run_dir, "--resume")[0], 0)
        code, out = self.launch(self.worktree, self.run_dir, "--resume")
        self.assertEqual(code, 2, out)
        self.assertIn("cap", out)
        self.assertEqual(len(self.calls_made()), 2)

    def test_resume_needs_a_session_and_a_followup(self):
        self.brief()
        code, out = self.launch(self.worktree, self.run_dir, "--resume")
        self.assertEqual(code, 2, out)
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        code, out = self.launch(self.worktree, self.run_dir, "--resume")
        self.assertEqual(code, 2, out)
        self.assertIn("followup.md", out)

    def ledger(self):
        return self.home / ".cache" / "implement-ledger" / "proj--spec.jsonl"

    def ledger_lines(self):
        return [json.loads(line) for line in self.ledger().read_text().splitlines()]

    def plant(self, *lines):
        self.ledger().parent.mkdir(parents=True, exist_ok=True)
        with self.ledger().open("a") as f:
            for line in lines:
                f.write(json.dumps({"at": "2026-10-02T00:00:00+00:00", **line}) + "\n")

    def spent(self):
        run = subprocess.run(
            [str(LEDGER), "spent", "proj--spec"],
            capture_output=True, text=True, env=self.env, check=True,
        )  # fmt: skip
        return run.stdout.strip()

    def test_a_fresh_run_keeps_the_count(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "5"
        self.env["STUB_COST"] = "3"
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        # Every call's result is kept, fresh runs' included.
        self.assertTrue((self.run_dir / "run-2.json").exists())
        second = self.calls_made()[1]["argv"]
        self.assertEqual(self.flag(second, "--max-budget-usd"), "2")
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 2, out)
        self.assertIn("implement-ledger", out)
        self.assertIn("IMPLEMENT_MAX_USD", out)
        self.assertEqual(len(self.calls_made()), 2)

    def test_a_bad_cap_is_refused(self):
        self.brief()
        for cap in ("inf", "nan", "abc", "-1", "0", "1e3", "0.0", " 5", "5."):
            with self.subTest(cap=cap):
                self.env["IMPLEMENT_MAX_USD"] = cap
                code, out = self.launch(self.worktree, self.run_dir)
                self.assertEqual(code, 2, out)
                self.assertIn("IMPLEMENT_MAX_USD", out)
                self.assertNotIn("Traceback", out)
        self.assertEqual(self.calls_made(), [])
        self.env["IMPLEMENT_MAX_USD"] = ""
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        (call,) = self.calls_made()
        self.assertEqual(self.flag(call["argv"], "--max-budget-usd"), "20")

    def test_a_run_with_no_cost_is_charged_its_budget(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "10"
        for cost in ("none", "-3", "nan", "inf"):
            with self.subTest(cost=cost):
                self.ledger().unlink(missing_ok=True)
                self.env["STUB_COST"] = cost
                self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
                self.assertEqual(self.ledger_lines()[-1]["usd"], 10)
                self.assertEqual(self.spent(), "10")

    def test_a_planted_run_file_changes_nothing(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "10"
        self.env["STUB_COST"] = "2.5"
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        (self.run_dir / "run-1.json").write_text('{"total_cost_usd": -100}')
        (self.run_dir / "run-7.json").write_text("")
        (self.run_dir / "followup.md").write_text("Carry on.\n")
        self.assertEqual(self.launch(self.worktree, self.run_dir, "--resume")[0], 0)
        second = self.calls_made()[1]["argv"]
        self.assertEqual(self.flag(second, "--max-budget-usd"), "7.5")

    def test_the_ledger_records_each_call(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "20"
        self.env["STUB_COST"] = "1"
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        lines = self.ledger_lines()
        self.assertEqual(
            [(l["event"], l["call"]) for l in lines],
            [("start", 1), ("end", 1), ("start", 2), ("end", 2)],
        )
        self.assertEqual([l.get("budget") for l in lines[::2]], [20, 19])
        self.assertEqual(oct(self.ledger().parent.stat().st_mode & 0o777), "0o700")
        # With the second's end line gone, it's charged its whole budget, the first its cost.
        self.ledger().write_text("".join(json.dumps(l) + "\n" for l in lines[:3]))
        self.assertEqual(self.spent(), "20")
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 2, out)
        self.assertEqual(len(self.calls_made()), 2)

    def test_a_start_with_no_end_counts_its_budget(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "10"
        self.plant({"who": "implementer", "call": 1, "event": "start", "budget": 4})
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        (call,) = self.calls_made()
        self.assertEqual(self.flag(call["argv"], "--max-budget-usd"), "6")
        self.assertEqual(self.ledger_lines()[1]["call"], 2)

    def test_a_bad_ledger_is_refused(self):
        self.brief()
        start = {"who": "implementer", "call": 1, "event": "start", "budget": 4}
        for lines in (
            [start, {"who": "implementer", "call": 1, "event": "end", "usd": -1}],
            [start, {"who": "implementer", "call": 7, "event": "end", "usd": 1}],
            [start, {"who": "implementer", "call": 1, "event": "end", "usd": 1}]
            + [{"who": "implementer", "call": 1, "event": "end", "usd": 1}],
            [{**start, "budget": -4}],
            [{"who": "someone", "usd": 1}],
            [{"who": "verifier V1", "usd": -1, "note": ""}],
        ):
            with self.subTest(lines=lines):
                self.ledger().unlink(missing_ok=True)
                self.plant(*lines)
                code, out = self.launch(self.worktree, self.run_dir)
                self.assertEqual(code, 2, out)
                self.assertIn("implement-ledger", out)
        self.ledger().write_text("not json\n")
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 2)
        self.assertEqual(self.calls_made(), [])

    def test_a_ledger_written_during_the_call_exits_4(self):
        self.brief()
        self.env["STUB_EXEC"] = (
            "import pathlib\n"
            "p = pathlib.Path(os.environ['HOME'], '.cache/implement-ledger/proj--spec.jsonl')\n"
            "p.write_text(p.read_text() + p.read_text().splitlines()[-1] + '\\n')\n"
        )
        code, out = self.launch(self.worktree, self.run_dir)
        self.assertEqual(code, 4, out)
        self.assertIn("implement-ledger", out)
        self.assertNotIn("end", [l.get("event") for l in self.ledger_lines()])
        self.assertFalse((self.run_dir / "reply.md").exists())

    def test_verifier_lines_dont_change_the_budget(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "10"
        self.env["STUB_COST"] = "2"
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        self.plant(
            {"who": "verifier V1", "usd": 1.5, "note": "finished"},
            {"who": "verifier V2", "usd": None, "note": "refused"},
        )
        (self.run_dir / "followup.md").write_text("Carry on.\n")
        self.assertEqual(self.launch(self.worktree, self.run_dir, "--resume")[0], 0)
        second = self.calls_made()[1]["argv"]
        self.assertEqual(self.flag(second, "--max-budget-usd"), "8")

    def test_a_verifiers_line_leaves_the_resume_budget_as_it_was(self):
        self.brief()
        self.env["IMPLEMENT_MAX_USD"] = "10"
        self.env["STUB_COST"] = "2"
        self.assertEqual(self.launch(self.worktree, self.run_dir)[0], 0)
        scratch = self.home / ".cache" / "implement-verify" / "proj" / "spec" / "V1"
        (scratch / "src").mkdir(parents=True)
        for name in ("brief.md", "spec.md", "diff.patch"):
            (scratch / name).write_text("x\n")
        verify = subprocess.run(
            [str(VERIFY), str(scratch)], capture_output=True, text=True, env=self.env, check=False
        )
        # The stub's reply has no verdict lines, so 3; its cost still reaches the ledger.
        self.assertEqual(verify.returncode, 3, verify.stdout + verify.stderr)
        self.assertEqual(self.ledger_lines()[-1]["who"], "verifier V1")
        (self.run_dir / "followup.md").write_text("Carry on.\n")
        self.assertEqual(self.launch(self.worktree, self.run_dir, "--resume")[0], 0)
        second = self.calls_made()[-1]["argv"]
        self.assertEqual(self.flag(second, "--max-budget-usd"), "8")

if __name__ == "__main__":
    unittest.main()

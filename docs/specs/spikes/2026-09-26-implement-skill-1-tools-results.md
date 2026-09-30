# Spike results: /implement, part 1: range-level drift, a diff scanner and a sandboxed implement-verifier

## S1

### Can the build-verifier run this repo's own Done when commands under the spike settings?

Expect: most tests pass, but those that `git init` a plain `.git` directory (tests/test_check_spec.py:471's helper, test_run_agent) and those writing under `~/.cache/spec-spikes` (test_prepare_spike) fail with sandbox refusals, and check-spec.py's template read from `~/.claude` fails.
Runs: 1

#### Commands

```
diff src/skills/spec/spike-settings.json settings.json   # confirms this session's settings.json IS spike-settings.json
(cd src && python3 -m unittest discover -s tests -v) > "$TMPDIR/test_output.log" 2>&1
grep -E "^(FAIL|ERROR): " "$TMPDIR/test_output.log"
```

```
### probing why specific tests fail/pass
python3 -c "import subprocess, tempfile; d = tempfile.mkdtemp(); print(subprocess.run(['git','init','-q',d]).returncode)"
python3 -c "from pathlib import Path; print(Path.home().joinpath('.claude','skills','spec','template.md').read_text()[:50])"
```

#### Output

```
Ran 175 tests in 12.517s
FAILED (failures=2, errors=8)

ERROR: test_exports_the_repo_at_read_at (test_prepare_spike.PrepareSpike.test_exports_the_repo_at_read_at)
ERROR: test_refuses_a_symlink_out_of_the_root (test_prepare_spike.PrepareSpike.test_refuses_a_symlink_out_of_the_root)
ERROR: test_budget_cap (test_run_agent.RunAgent.test_budget_cap)
ERROR: test_reply_without_its_shape_exits_3 (test_run_agent.RunAgent.test_reply_without_its_shape_exits_3)
ERROR: test_researcher_keeps_its_mcp_servers (test_run_agent.RunAgent.test_researcher_keeps_its_mcp_servers)
ERROR: test_resume_needs_a_session (test_run_agent.RunAgent.test_resume_needs_a_session)
ERROR: test_resume_sends_followup_to_same_session_and_keeps_old_reply (test_run_agent.RunAgent.test_resume_sends_followup_to_same_session_and_keeps_old_reply)
ERROR: test_run_passes_agent_sandbox_and_brief (test_run_agent.RunAgent.test_run_passes_agent_sandbox_and_brief)
FAIL: test_read_at_none_only_clears (test_prepare_spike.PrepareSpike.test_read_at_none_only_clears)
FAIL: test_needs_a_brief (test_run_agent.RunAgent.test_needs_a_brief)
```

```
### test_prepare_spike failures: writes under ~/.cache/spec-spikes refused
PermissionError: [Errno 1] Operation not permitted: '~/.cache/spec-spikes/test-prepare-spike-3b454d64'
FileNotFoundError: [Errno 2] No such file or directory: '~/.cache/spec-spikes/test-prepare-spike-7fb83a74/spec/S1/src'
PermissionError: [Errno 1] Operation not permitted: '/tmp/claude-501/.../outside' -> '~/.cache/spec-spikes/test-prepare-spike-17d61e86'  (symlink target)

### test_run_agent failures: writes under ~/.cache/agent-runs refused (a *different* path than
### ~/.cache/spec-spikes, not named in the brief), plus one read denial:
PermissionError: [Errno 1] Operation not permitted: '~/.cache/agent-runs/test-67ca9645'
AssertionError: 'brief.md' not found in 'run-agent: no agent file: ~/.claude/agents/cold-reviewer.md\n'

### tests/test_check_spec.py: ALL tests pass, including the git-based Citations class that
### git_repo() (test_check_spec.py:471's helper) builds in a tempfile.TemporaryDirectory():
test_cite_repo (test_check_spec.Citations.test_cite_repo) ... ok
test_uncommitted_lines_warn (test_check_spec.Citations.test_uncommitted_lines_warn) ... ok
[... 17 Citations tests, all ok]

### probe: git init inside a tempdir succeeds (tempfile defaults to $TMPDIR, which is writable)
0

### probe: reading the real ~/.claude template path is denied, confirming the mechanism Expect named
ERROR PermissionError [Errno 1] Operation not permitted: '~/.claude/skills/spec/template.md'
```

#### Verdict

DIFFERENT: 165/175 tests pass; 10 fail, all from writes under `~/.cache/spec-spikes` (test_prepare_spike, as expected) or `~/.cache/agent-runs` (test_run_agent, a path the brief didn't name) plus one `~/.claude` read denial reached via test_run_agent rather than check-spec.py. The tests that `git init` a plain `.git` directory (test_check_spec.py:471's `git_repo` helper, all 17 Citations tests) all **pass** — tempfile.TemporaryDirectory() defaults to `$TMPDIR`, which this sandbox leaves writable, so `.git` writes there succeed; the "sandbox refuses writes inside `.git`" restriction does not block them. check-spec.py's own `~/.claude` template read is confirmed broken by direct probe, but no unit test exercises that code path (it's only reached for a "templated" spec, which no fixture is), so it does not appear as a suite failure.

#### Notes

- `test_run_agent.py` writes under `~/.cache/agent-runs`, a sibling path to `~/.cache/spec-spikes` that the brief's Design/Done-when text doesn't mention; if W3's `verify-settings.json` widens write paths, it needs `~/.cache/agent-runs` too, or those 6 test_run_agent failures also need CANNOT-RUN treatment.
- The one `~/.claude` read failure in the suite (`test_needs_a_brief`) is incidental: `run-agent.sh` checks for the agent file at `~/.claude/agents/<agent>.md` before checking for `brief.md`, so the assertion fails on the wrong message, not on a bare crash — it still exits 2, just with different text than the test expects.

total_cost_usd: 0.55; num_turns: 22

## S2

### Does spike S1's answer still hold at `1c7ea6e`? Since it ran, both tests it named use a temporary home (`tests/test_prepare_spike.py:40-44`, `tests/test_run_agent.py:43-51`), `check-spec.py` reads its template from beside itself (`skills/spec/scripts/check-spec.py:45`), and the suite has grown. So W3's live run may see no sandbox refusals, or new ones. Experiment: S1's, at `1c7ea6e`: run `python3 -m unittest discover -s tests` in a spike export under `spike-settings.json` and list each test that fails and why.

Expect: nearly all tests pass; `test_prepare_spike` and `test_run_agent` now pass under their temporary home; a few tests still fail with `Operation not permitted`, most likely ones that write under a real `~/.cache` path or read `~/.claude`, and none fail for a reason other than the sandbox.
Runs: 1

#### Commands

The session itself ran under the sandbox settings (`settings.json` in the working dir, the spike settings).

```
(cd src && python3 -m unittest discover -s tests)
# diagnosis of the eval_runners failure: re-ran its script directly; and
/usr/bin/mktemp -d                      # with TMPDIR=/tmp/claude-501 set
env -u TMPDIR /usr/bin/mktemp -d
# no_stale_paths: make src a git repo (src-git beside it), rerun that file only
(cd src && GIT_DIR=../src-git GIT_WORK_TREE=$PWD git init --template= && git add . && git commit -qm spike \
   && python3 -m unittest discover -s tests -p test_no_stale_paths.py)
```

#### Output

```
Ran 374 tests in 36.753s
FAILED (failures=3, errors=3)
ERROR: test_eval_runners.Runners.test_fixtures_are_cleaned_up
ERROR: test_no_stale_paths.NoStalePaths.test_exempt_files_exist
ERROR: test_no_stale_paths.NoStalePaths.test_no_tracked_file_names_an_old_install_path
FAIL: test_research_scripts.RepoHealth.test_a_repo_that_answers
FAIL: test_research_scripts.RepoHealth.test_api_error_is_not_reported_as_not_found
FAIL: test_research_scripts.RepoHealth.test_missing_repo_is_not_found
```

Why, per test:

```
test_research_scripts (3 tests): repo-health.sh:181 `tmp=$(mktemp -d) || exit 1` ->
  "mktemp: mkdtemp failed on /var/folders/.../T/tmp.XXXX: Operation not permitted"; script exits, table has header only.
test_eval_runners.test_fixtures_are_cleaned_up: tests/skill-evals/run.sh:45 bare `mktemp -d` ->
  same "Operation not permitted" on /var/folders/...; setup.sh never ran, so the `works` file is empty -> ValueError on unpack.
mktemp probe: /usr/bin/mktemp -d fails the same way with TMPDIR=/tmp/claude-501 set and unset;
  macOS mktemp -d without a template ignores $TMPDIR and uses the per-user /var/folders dir, which the sandbox doesn't allow writing.
test_no_stale_paths (2 tests): `git -C src ls-files` exits 128 - the export has no .git. Not a sandbox refusal.
  With a git repo made per the instructions: "Ran 4 tests ... OK".
```

test_prepare_spike, test_run_agent and test_check_spec: all pass (no failures listed).

#### Verdict

DIFFERENT: The "few tests fail with `Operation not permitted`" part holds, but for a different cause than Expect: 4 tests (3 in `test_research_scripts.RepoHealth`, 1 in `test_eval_runners.Runners`) fail because bare `mktemp -d` in `repo-health.sh` and `skill-evals/run.sh` writes to `/var/folders/.../T`, not from writes under `~/.cache` or reads of `~/.claude`. 2 further tests (`test_no_stale_paths`) fail for a non-sandbox reason: the spike export has no `.git`, and pass once one is made.

#### Notes

- For W3: a live run in a real checkout would have `.git`, so `test_no_stale_paths` should pass there; only the export lacks it. The `verifier.md` example should name `mktemp` writes to the per-user temp dir (`/var/folders`), not `~/.cache` writes or `~/.claude` reads, as the refusals to expect.
- The mktemp refusals happen although `$TMPDIR` points at a writable dir, because the scripts call `mktemp -d` with no template or `-t`; `mktemp -d "${TMPDIR:-/tmp}/x.XXXXXX"` would avoid them (not chased).
- The run's cwd briefly moved into `src/` through `cd src && ...` in one compound command; all results were unaffected.

total_cost_usd: 0.23; num_turns: 11

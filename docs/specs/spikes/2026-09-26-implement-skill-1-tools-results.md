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
PermissionError: [Errno 1] Operation not permitted: '/Users/chrisadkin/.cache/spec-spikes/test-prepare-spike-3b454d64'
FileNotFoundError: [Errno 2] No such file or directory: '/Users/chrisadkin/.cache/spec-spikes/test-prepare-spike-7fb83a74/spec/S1/src'
PermissionError: [Errno 1] Operation not permitted: '/tmp/claude-501/.../outside' -> '/Users/chrisadkin/.cache/spec-spikes/test-prepare-spike-17d61e86'  (symlink target)

### test_run_agent failures: writes under ~/.cache/agent-runs refused (a *different* path than
### ~/.cache/spec-spikes, not named in the brief), plus one read denial:
PermissionError: [Errno 1] Operation not permitted: '/Users/chrisadkin/.cache/agent-runs/test-67ca9645'
AssertionError: 'brief.md' not found in 'run-agent: no agent file: /Users/chrisadkin/.claude/agents/cold-reviewer.md\n'

### tests/test_check_spec.py: ALL tests pass, including the git-based Citations class that
### git_repo() (test_check_spec.py:471's helper) builds in a tempfile.TemporaryDirectory():
test_cite_repo (test_check_spec.Citations.test_cite_repo) ... ok
test_uncommitted_lines_warn (test_check_spec.Citations.test_uncommitted_lines_warn) ... ok
[... 17 Citations tests, all ok]

### probe: git init inside a tempdir succeeds (tempfile defaults to $TMPDIR, which is writable)
0

### probe: reading the real ~/.claude template path is denied, confirming the mechanism Expect named
ERROR PermissionError [Errno 1] Operation not permitted: '/Users/chrisadkin/.claude/skills/spec/template.md'
```

#### Verdict

DIFFERENT: 165/175 tests pass; 10 fail, all from writes under `~/.cache/spec-spikes` (test_prepare_spike, as expected) or `~/.cache/agent-runs` (test_run_agent, a path the brief didn't name) plus one `~/.claude` read denial reached via test_run_agent rather than check-spec.py. The tests that `git init` a plain `.git` directory (test_check_spec.py:471's `git_repo` helper, all 17 Citations tests) all **pass** — tempfile.TemporaryDirectory() defaults to `$TMPDIR`, which this sandbox leaves writable, so `.git` writes there succeed; the "sandbox refuses writes inside `.git`" restriction does not block them. check-spec.py's own `~/.claude` template read is confirmed broken by direct probe, but no unit test exercises that code path (it's only reached for a "templated" spec, which no fixture is), so it does not appear as a suite failure.

#### Notes

- `test_run_agent.py` writes under `~/.cache/agent-runs`, a sibling path to `~/.cache/spec-spikes` that the brief's Design/Done-when text doesn't mention; if W3's `verify-settings.json` widens write paths, it needs `~/.cache/agent-runs` too, or those 6 test_run_agent failures also need CANNOT-RUN treatment.
- The one `~/.claude` read failure in the suite (`test_needs_a_brief`) is incidental: `run-agent.sh` checks for the agent file at `~/.claude/agents/<agent>.md` before checking for `brief.md`, so the assertion fails on the wrong message, not on a bare crash — it still exits 2, just with different text than the test expects.

total_cost_usd: 0.55; num_turns: 22

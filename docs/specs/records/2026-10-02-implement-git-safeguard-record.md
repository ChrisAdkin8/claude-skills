# Record: /implement runs its own git commands with the file watcher and hooks off

What happened to [2026-10-02-implement-git-safeguard](../2026-10-02-implement-git-safeguard.md) after it was written. The spec is the plan; this file is its history, and nothing here is part of the plan. Sections appear as they're needed, in this order; leave out any that have nothing in them yet.

## Verification

- Quick spec on 2026-10-02: no cold review or spikes.
- 2026-10-02: spec-verifier, 20 of 21 claims confirmed. Plan holds: yes. Fixed: `CLAUDE.md:10-17`; Background and W1 now say the flag rule covers `revert`, which the steps never give.
- Set to reviewed on 2026-10-02 at the user's request to close out.

## Evidence

- Started at 297394a
- Baseline: `python3 -m unittest discover -s tests` -> pass (552 tests)
- Baseline: `ruff check --isolated --select E9,F .` (ruff 0.16.7, as CI pins) -> pass
- Baseline: `git ls-files -z '*.sh' | xargs -0 shellcheck -S warning` -> pass
- Baseline: `claude plugin validate . --json` -> pass (only the expected plugin.json version warning)
- Baseline: `claude plugin validate .claude-plugin/plugin.json` -> pass (expected warnings only)
- Baseline: `python3 tests/replay_guard.py` -> pass
- W1 (505169e): Done when `python3 -m unittest tests.test_implement_skill` -> pass (5 tests); failed first against the unchanged `skills/implement/SKILL.md`, 11 failures: the commands at :50, :59 (worktree add, add, commit), :60 and :99 (add, commit, status) lacked both flags, and the tool rules didn't name them; `python3 -m unittest discover -s tests` -> pass (557); `EVAL_MODEL=sonnet|opus tests/skill-evals/run.sh implement-basic implement-trap` -> not run: paid evals, run by hand (a `not run` section is in `tests/agent-evals/BASELINE.md` for their results); suite pass; scan clean
- Clean-up: simplify 554602d (a single pass without the Agent tool: the test reuses `allowed_tools()` from `test_skill_frontmatter.py`); code-review no changes; suite pass; Done when all pass that ran here (`tests.test_implement_skill` and the full suite); the paid implement skill evals on Sonnet and Opus not run
- Verifier V1 (554602d):

  | W | Done when | Ran | Result (PASS, FAIL or CANNOT-RUN) | Matches spec |
  |---|---|---|---|---|
  | W1 | `python3 -m unittest tests.test_implement_skill` passes, and its first test fails against today's `skills/implement/SKILL.md` (:50, :59-60, :99 lack the flags) | In src/: all 5 tests pass. They check that every backquoted `git -C` command carries both `-c` flags, that each matches a `Bash(...)` rule in allowed-tools via `fnmatchcase`, and that the tool rules name the flags and `revert`. A planted `core.fsmonitor` and `post-commit` hook leave no marker when the flags are on, and leave both markers in the control run without them. In before/W1/, with the new test file copied in: FAILED (failures=11). The flag test fails for the Gate `status --porcelain`, both `worktree add`, the first `add`/`commit`, the evidence `add`/`commit`/`status --porcelain`, and the tool-rules line. `test_the_tool_rules_say_to_keep_both_flags` and one pre-approval subtest also fail. | PASS | yes |
  | W1 | `python3 -m unittest discover -s tests` passes | In src/: 557 tests ran, 532 pass. The other 25 fail only for sandbox reasons. I re-ran each failing test's script to show its stderr. CANNOT-RUN, `mktemp -d` refused (`Operation not permitted` on `/var/folders/...`): test_eval_runners.Runners.{test_agent_eval_cap_override, test_agent_evals_agents_name_the_checkout_as_their_root, test_agent_evals_pass_the_model, test_agent_evals_settings_deny_the_answer_keys, test_agent_evals_settings_override, test_agent_evals_turn_off_auto_memory, test_fixtures_are_cleaned_up, test_agent_evals_case_is_a_copy_of_the_fixture_alone, test_agent_evals_clone_hides_this_checkouts_answer_keys, test_agent_evals_error_is_a_failure, test_agent_evals_fail, test_agent_evals_pass, test_agent_evals_pass_caps_and_sandbox, test_agent_evals_repo_is_a_clone_without_the_answer_keys, test_agent_evals_skip_a_case_for_another_model}; test_research_scripts.RepoHealth.{test_a_repo_that_answers, test_api_error_is_not_reported_as_not_found, test_missing_repo_is_not_found}. CANNOT-RUN, no git repo (git exit 128): test_no_stale_paths.NoStalePaths.{test_exempt_files_exist, test_no_tracked_file_names_an_old_install_path}; test_replay_guard.Main.{test_a_difference_not_accepted_fails (2 subtests), test_a_run_under_another_checkout_is_judged_at_this_one, test_accepted_differences_pass, test_an_entry_that_no_longer_occurs_is_reported_but_passes}. | PASS | yes |
  | W1 | `EVAL_MODEL=sonnet tests/skill-evals/run.sh implement-basic implement-trap` prints `PASS` for both cases, results and costs in a dated `BASELINE.md` section | not run. `BASELINE.md` has a dated section, but its table says "not run: paid, run by hand". | CANNOT-RUN: needs a `claude -p` call and the network | yes |
  | W1 | the same with `EVAL_MODEL=opus` prints `PASS` for both cases, results and costs in `BASELINE.md` | not run. `BASELINE.md` table says "not run: paid, run by hand". | CANNOT-RUN: needs a `claude -p` call and the network | yes |

  Other commits: 22ec554 "spec: … is in progress" (changes the spec's `status:` line and adds the record's `## Evidence` section; weakens no test); 554602d "tests: simplify after implementing" (changes `tests/test_implement_skill.py` and the record; reuses `allowed_tools()` from `test_skill_frontmatter.py` and writes a fixed `a.txt`; every assertion is still there, so no test is weakened)
  Verified: 2 of 2
  Implementation holds: yes
- CANNOT-RUN rows not sent to the implementer: both are the paid implement skill evals, which its rule 6 forbids it to run; they're for the user to run by hand, as `CLAUDE.md:34-37` asks.

## Implementation

- 2026-10-02, W1 (505169e): the Done when's paid skill evals (`implement-basic` and `implement-trap` on Sonnet and Opus) weren't run: the user chose to close out without them. `tests/agent-evals/BASELINE.md` records them as skipped; the next run of those cases, for `docs/specs/2026-10-02-implementer-sandbox.md`'s W6, covers this change.
- 2026-10-02, W1 (554602d): the clean-up made the new test reuse `allowed_tools()` from `tests/test_skill_frontmatter.py` instead of its own copy, as `/simplify` found; the spec named no helper.

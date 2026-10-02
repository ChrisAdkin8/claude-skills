# Record: The implementer's launcher refuses a user setting that opens its sandbox to the network

What happened to [2026-10-02-implementer-refuses-network-setting](../2026-10-02-implementer-refuses-network-setting.md) after it was written. The spec is the plan; this file is its history, and nothing here is part of the plan. Sections appear as they're needed, in this order; leave out any that have nothing in them yet.

## Verification

- Quick spec on 2026-10-02: no cold review or spikes.
- 2026-10-02: spec-verifier, 27 of 32 claims confirmed. Plan holds: yes. The five MISCITED were line numbers in `tests/test_run_implementer.py`, each off by one, corrected as given.
- 2026-10-02 (`/spec finish`, no drift from 99e002e): spec-verifier, 30 of 32 claims confirmed. Plan holds: yes. MISCITED `run-implementer.sh:355-357` re-cited as :355-359, the flags at :357; the INHERITED "about six lines of Python" is labelled an estimate, so unchanged. The verifier couldn't read `~/.claude/settings.json` to see whether W1 would refuse the user's own eval runs; checked from the main session the same day: it sets no `sandbox.network` key.

## Cold review

Reviewed on 2026-10-02 by cold-reviewer. Saved unchanged; what was folded in is logged under Changes since the review.

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
| 1 | ASSUMPTION | W1 Done when: "`shellcheck skills/implement/scripts/run-implementer.sh` prints nothing" | CI runs shellcheck only at warning level and above (`-S warning`). The spec's command runs at the default level, which also prints info and style notes. The file has no `shellcheck disable` lines. If the file at `99e002e` already gets an info or style note, this check fails even though nothing W1 changes is to blame: W1's code sits inside a heredoc (a block of text the shell passes to Python as-is), which shellcheck doesn't check. | requirement: "`shellcheck skills/implement/scripts/run-implementer.sh` prints nothing" | `.github/workflows/tests.yml:28` `xargs -0 shellcheck -S warning`; `grep -n shellcheck run-implementer.sh` finds nothing | Run shellcheck at its default level on the file at `99e002e`. If it prints anything, change the Done when to `-S warning`, as CI uses. |
| 2 | COLD-READ | Goal: "sets any key under `sandbox.network`, other than `strictAllowlist: true`, to a value that isn't empty" vs Design: "A key set to an empty list, `false`, `0` or `None` passes" and "`strictAllowlist` is added when its value is anything but `True`" | The rules disagree with each other. Read as written, the Goal lets `strictAllowlist: false` through, because `false` counts as empty, but Design and W1's fourth subtest refuse it. Design's two rules also clash on `strictAllowlist: null`: one says `None` passes, the other says anything but `True` is refused. No test covers `null`. | neither: W1's subtest settles `false` (refused), and `null` is an edge case that only decides refusing vs passing a setting nobody writes | spec lines 15, 51, 59 | Add one sentence that settles `strictAllowlist: null`, and say in the Goal that `strictAllowlist` is refused when it is anything but `true`. |
| 3 | COLD-READ | W1: "the 'not `strictAllowlist`' case needs its own `assertNotIn`" | The loop's tuples are `(sandbox, key)`, with one key that must appear in the output. The case that names `httpProxyPort` and must not name `strictAllowlist` doesn't fit that shape. The builder has to choose between changing the tuple and adding a separate block, and the spec doesn't say which. Either works. | neither: either layout tests the same behaviour | `tests/test_run_implementer.py:282-292` | Say which layout to use. |

Counts: 3 findings - 0 correctness, 1 requirement, 2 neither
Neither: 2, 3
Cold read: yes
Needs a run: 1

### Delta review, 2026-10-02

Reviewed on 2026-10-02 by cold-reviewer: the changes logged as Not reviewed. Saved unchanged.

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
| 1 | COLD-READ | W1: "`{"network": {"strictAllowlist": null}}` naming `strictAllowlist`" | The new subtest is written in JSON. In Python, the language the test file uses, `null` is `None`. Pasted into the tuple as written, it raises a NameError (Python doesn't recognise the name). The earlier tuples' `true` and `false` have the same problem, and anyone writing the test will spot and convert all of them. | neither: an obvious fix; the behaviour it tests is unchanged | `tests/test_run_implementer.py:282-287` builds the tuples as Python dicts, which `json.dumps` turns into JSON at :290 | Write the tuple as `{"network": {"strictAllowlist": None}}` |
| 2 | COLD-READ | Goal: "sets `strictAllowlist` to anything but `true`"; Design: "anything but `True`" | It doesn't say whether the check is `is not True` or `!= True`. That only changes the result for `strictAllowlist: 1`, which Python counts as equal to `True` but which isn't the same object. Built with `!= True`, a `1` passes. | neither: nobody writes `1` for this key, and no Done when tests it | `skills/implement/implementer-settings.json:7` uses `true`; the existing check uses `is True` / `is False` (`run-implementer.sh:138-139`) | Say "`is not True`", to match :138-139 |
| 3 | ASSUMPTION | W1 Done when: "At the default level the file already gets an info note (…:119) and a style note (:389)" | Plausible. Line 119 has the `A && B \|\| C` pattern, which ShellCheck (a shell-script checker) flags as info SC2015. Line 389 is `sed 's/^/…/' <<< "$changed"`, which can draw style note SC2001. But reading can't confirm what ShellCheck prints. The Done when itself runs `-S warning`, the level CI uses, so this note doesn't gate anything. | neither: explanation only; the gating command matches CI | `.github/workflows/tests.yml:28`; `run-implementer.sh:119`, `:389` | Run `shellcheck` at the default level and at `-S warning` on the file at `99e002e` |

The other two changes check out against the code:
- **`null` rule:** the Goal, Design and the new `null` subtest now agree.
- **`httpProxyPort` block:**
  - Placed after the loop and before `assertEqual(self.calls_made(), [])` at :293, it still feeds the no-call check.
  - `launch` returns stdout plus stderr (`tests/test_run_implementer.py:105`). Before it exits, nothing the launcher prints contains `strictAllowlist`; grep finds no other output that could, so the `assertNotIn` holds.
  - At `99e002e` the block exits 0, which fails its exit-2 check, so the "fails at `99e002e`" Done when still holds.

Counts: 3 findings - 0 correctness, 0 requirement, 3 neither
Neither: 1, 2, 3
Cold read: yes
Needs a run: 3

## Changes since the review

- Delta-reviewed on 2026-10-02: W1's Done when runs `shellcheck -S warning`, as CI does (`.github/workflows/tests.yml:28`); at the default level the file already prints an info note (:119) and a style note (:389) at 99e002e, checked by hand the same day. From cold review row 1, on 2026-10-02.
- Delta-reviewed on 2026-10-02: the Goal says `strictAllowlist` is refused when anything but `true`, Design says `null` is refused too, and W1 adds a `strictAllowlist: null` subtest. From cold review row 2, on 2026-10-02.
- Delta-reviewed on 2026-10-02: W1 puts the `httpProxyPort` case in its own block after the loop and before the no-call assertion, asserting exit 2, `httpProxyPort` named and `strictAllowlist` not. From cold review row 3, on 2026-10-02.
- Verifier round 2 ran on 2026-10-02: after the cold review, re-checking W1. 15 of 15 claims confirmed. Plan holds: yes.

## Evidence

- Started at 87b2aed
- Baseline: `python3 -m unittest discover -s tests` -> pass (589 tests)
- Baseline: `ruff check --isolated --select E9,F .` (local ruff, not `pipx run`) -> pass
- Baseline: `git ls-files -z '*.sh' | xargs -0 shellcheck -S warning` -> pass
- Baseline: `python3 tests/replay_guard.py` -> 1 failing: one recorded headless command, a `jq` read of `~/.claude/settings.json`, now blocked and not in `tests/replay-accepted.txt`
- Baseline: `claude plugin validate . --json` -> pass
- Baseline: `claude plugin validate .claude-plugin/plugin.json` -> pass (with the expected root `CLAUDE.md` warning)
- Baseline: `tests/agent-evals/run.sh` and `tests/skill-evals/run.sh` -> not run: paid, by hand only (`CLAUDE.md`)
- W1 (46969a4): Done when `python3 -m unittest tests.test_run_implementer` -> pass; it failed first with 5 failures (the four new subtests and the `httpProxyPort` block each exited 0, not 2). `python3 -m unittest discover -s tests` -> pass (589); `shellcheck -S warning skills/implement/scripts/run-implementer.sh` -> prints nothing. `EVAL_MODEL=sonnet|opus tests/skill-evals/run.sh implement-basic implement-trap` -> not run: paid, by hand only, so no `tests/agent-evals/BASELINE.md` section was added; suite as baseline (replay guard's same 1 difference); scan clean
- Clean-up: simplify dcad77a (undid a formatter hook's re-wrapping of five unrelated places in `tests/test_run_implementer.py`; single pass, no Agent fan-out); code-review no changes; suite as baseline (replay guard's same 1 difference); Done when all pass but the paid skill evals, not run (by hand only)
- Verifier V1 (dcad77a):

| W | Done when | Ran | Result (PASS, FAIL or CANNOT-RUN) | Matches spec |
|---|---|---|---|---|
| W1 | `python3 -m unittest tests.test_run_implementer` fails before the change with the new subtests (each exits 0, not 2), and passes after | In src/: `python3 -m unittest tests.test_run_implementer` → Ran 27 tests, OK. In before/W1/, after copying in src/'s test file: FAILED (failures=5). The failures are the four new subtests (`allowedDomains`, `allowLocalBinding`, `strictAllowlist: False`, `strictAllowlist: None`), each `AssertionError: 0 != 2 … finished (exit 0)`, plus the `httpProxyPort` block, which also exited 0, not 2. The test has the four tuples, the separate block with `assertIn("httpProxyPort")` / `assertNotIn("strictAllowlist")` placed before the no-call assertion, and the passing file with `network: {allowedDomains: [], strictAllowlist: True}`, as the Change asks. | PASS | yes |
| W1 | `python3 -m unittest discover -s tests` passes | In src/: Ran 589 tests, FAILED (failures=16, errors=9). All 25 are sandbox or no-git causes; the rest pass. CANNOT-RUN: `test_eval_runners.Runners.{test_agent_evals_case_is_a_copy_of_the_fixture_alone, test_agent_evals_clone_hides_this_checkouts_answer_keys, test_agent_evals_error_is_a_failure, test_agent_evals_fail, test_agent_evals_pass, test_agent_evals_pass_caps_and_sandbox, test_agent_evals_repo_is_a_clone_without_the_answer_keys, test_agent_evals_skip_a_case_for_another_model, test_agent_eval_cap_override, test_agent_evals_agents_name_the_checkout_as_their_root, test_agent_evals_pass_the_model, test_agent_evals_settings_deny_the_answer_keys, test_agent_evals_settings_override, test_agent_evals_turn_off_auto_memory, test_fixtures_are_cleaned_up}` and `test_research_scripts.RepoHealth.{test_a_repo_that_answers, test_missing_repo_is_not_found, test_api_error_is_not_reported_as_not_found}` (mktemp -d refused: `mkdtemp failed on /var/folders/… Operation not permitted`; for the 9 whose assertion didn't show it, the script's own output captured by re-running them shows that refusal and nothing else); `test_no_stale_paths.NoStalePaths.{test_exempt_files_exist, test_no_tracked_file_names_an_old_install_path}` and `test_replay_guard.Main.{test_a_difference_not_accepted_fails (2 subtests), test_a_run_under_another_checkout_is_judged_at_this_one, test_accepted_differences_pass, test_an_entry_that_no_longer_occurs_is_reported_but_passes}` (no git repo: `git ls-files` / `git show` exit 128) | PASS | yes |
| W1 | `shellcheck -S warning skills/implement/scripts/run-implementer.sh` prints nothing | In src/: no output, exit 0 | PASS | yes |
| W1 | By hand: `EVAL_MODEL=sonnet\|opus tests/skill-evals/run.sh implement-basic implement-trap` print PASS for both cases, and the results go in a dated `tests/agent-evals/BASELINE.md` section | not run. The record says the implementer didn't run them either, so W1 changes no `BASELINE.md` | CANNOT-RUN: paid `claude -p` evals that need the network and a person | yes |

Other commits: `spec: … is in progress` (f04ba83) changes the spec's `status:` line and adds the record's `## Evidence` start line. `implement: simplify after implementing` (dcad77a) changes the record (W1 evidence line) and `tests/test_run_implementer.py`: it undoes a formatter's re-wrapping of five unrelated places and compacts the new test blocks, with the same assertions. No test is weakened.
Verified: 3 of 3
Implementation holds: yes

- implementer-run: W1: `python3 -m unittest tests.test_eval_runners.Runners tests.test_research_scripts.RepoHealth tests.test_no_stale_paths.NoStalePaths tests.test_replay_guard.Main` -> Ran 52 tests, OK (all 52 passed: the 24 the verifier couldn't run, plus the other tests in those four classes)
- implementer-run: W1: `EVAL_MODEL=sonnet tests/skill-evals/run.sh implement-basic implement-trap`, then `EVAL_MODEL=opus` -> not run: paid `claude -p` evals, run by hand only, and the user hasn't asked for them; no `tests/agent-evals/BASELINE.md` section added

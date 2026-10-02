# Record: The guard judges paths as macOS resolves them, and keeps ~/.claude private

What happened to [2026-10-02-guard-path-identity](../2026-10-02-guard-path-identity.md) after it was written. The spec is the plan; this file is its history, and nothing here is part of the plan. Sections appear as they're needed, in this order; leave out any that have nothing in them yet.

## Verification

- 2026-10-02: spec-verifier, 37 of 39 claims confirmed. Plan holds: no, because W5 missed `tests/test_eval_runners.py:329-331`, which asserts the agent evals add `~/.claude` first. W5 was revised to change that test, and W3, W4 and W5 gained the missed files.
- Verifier round 2 ran on 2026-10-02: after verification, re-checking W3, W4 and W5.
- 2026-10-02, round 2: spec-verifier, 26 of 26 claims confirmed. Plan holds: yes.

## Cold review

Reviewed on 2026-10-02 by cold-reviewer. Saved unchanged; what was folded in is logged under Changes since the review.

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
| 1 | COST | W3: "a path under `CLAUDE_HOME` is allowed only under `SESSION_RESULTS`… or `OWN_ROOT`" | `~/.claude` itself becomes a refused path. `check_secrets` runs `secret_word` on every word before its recursive-search check, so `grep -rn spec ~/.claude` is now refused with the new message. That message has no "narrower directory" in it. `test_recursive_search_over_history_blocked` checks for exactly that phrase, so it goes red. W3 doesn't mention this test, and its Done when says "Unit tests pass". | correctness | `tests/test_agent_guard.py:1146-1151` (`assertIn("narrower directory", err)`); `hooks/agent-guard.py:1257-1279` (the `secret_word` loop runs before the `recursive` check) | Reading settles it. W3 should change that test, or drop `~/.claude` from its command list. |
| 2 | GAP | W1: "`with_root` in the replay calls `guard.own_root`" | The replay also passes the old guard from `--base` through `with_root`: `verdict(old, command)` calls `with_root(old, None)`. That old guard file has no `own_root` function. If `with_root` calls `guard.own_root(root)` every time, the replay crashes with AttributeError. Then "`python3 tests/replay_guard.py` exits 0" fails. The spec gives no warning. | correctness | `tests/replay_guard.py:417`, `:426`, `:220`, `:232`, `:255` | Reading settles the call path. The spec should say `with_root` sets `None` when it has no root and calls `own_root` only otherwise. |
| 3 | ASSUMPTION | Design, Sandbox: "Under `--plugin-dir` the root is a checkout outside `~/.claude`, and the `allowRead` re-opens nothing denied." | This is false for the agent evals. They render the settings with the root set to `$repo`. `deny_answer_keys` then adds `denyRead` entries inside `$repo` (`tests/agent-evals`, `tests/skill-evals`, `.git`). The new `allowRead: [$repo]` sits above those denies. Hiding the answer keys now depends on "the narrower path wins", which the spec marks *(unverified)*. Experiment 1 tested only the reverse case: an allow inside a deny. If the allow wins, Bash can read the answer keys. | correctness | `tests/agent-evals/run.sh:59`, `:82-98`, `:119-123`, `:189-193`; spike note `:17-36` | Needs a run. One `claude -p` with the W4 settings plus `deny_answer_keys`, then `wc -c` of a `tests/agent-evals/*/expect.txt` from Bash. |
| 4 | GAP | W3 Files: "`tests/test_sandbox_settings.py` (the guard's lists now cover `.claude` whole…)" | `test_agent_denies_known_to_guard` builds its known list from `SECRET_HOME \| HISTORY_HOME` only. After W3, `HISTORY_HOME` no longer holds `.claude/history.jsonl`, `file-history` and the others, but `agent-sandbox.json` still denies them. After W4 it also denies `.claude`. `CLAUDE_HOME` is in neither list, so the test goes red at W3 and again at W4. The spec never says what "known" should become (for example, add `CLAUDE_HOME`, or use `PRIVATE_HOME`). | requirement: "Unit tests pass" | `tests/test_sandbox_settings.py:79`, `:117-125`; `hooks/agent-sandbox.json:13` | Reading settles it. Name the change in W3. |
| 5 | GAP | W3 Change: "Reword … `hooks/agents/cold-reviewer.md:19`"; Rollback: "each work item is one commit" | W3 edits an agent file, but its Done when runs no agent evals. The first eval run is in W4, so the W3 commit lands without one. | requirement: "After changing an agent or skill file, run `tests/agent-evals/run.sh` by hand" (CLAUDE.md) | `CLAUDE.md:22-25`; spec W3 Done when | Move the prompt rewording to W4, or add an eval run to W3. |
| 6 | ASSUMPTION | Decision: "Saved tool output stays readable to the Read tool only… (experiment 2(a))"; W5 | Run 2(a) had no `--settings` and no guard, and the note doesn't say whether it passed `--allowedTools`. Nothing has tested a Read of `tool-results` under the full run-agent setup minus `--add-dir ~/.claude`. W5's eval run proves it only if some case produces output big enough to be saved. | requirement: "Saved tool output stays readable to the Read tool only" | spike note `:44-57`; `hooks/run-agent.sh:115-118` | Needs a run. One `run-agent.sh`-style run after W5 that overflows its output and reads the saved copy back with Read. |
| 7 | COLD-READ | W4: "`AGENT_NOT_DENIED` applies to the Read denies only" | After W3, `HISTORY_HOME` no longer holds `.claude/projects` or `.claude/plugins`, so `AGENT_NOT_DENIED` takes nothing away. The instruction is moot, and a reader can't tell what change is meant. | neither: no test result depends on it | `tests/test_sandbox_settings.py:40`, `:98` | Say to delete the set, or what it should hold. |
| 8 | WRONG | Decision: "differs between macOS and CI's Linux" | CI runs on `macos-latest`, not Linux. | neither: the other reason given ("needs the path to exist") still supports the choice | `.github/workflows/tests.yml:17` | Reading settles it. |
| 9 | COST | Effort, W4: "plus the agents those cases launch (capped at $2 each…)" | `implement-basic` and `implement-trap` each also run the implementer ($5 cap) and up to two verifiers ($5 each). On two models that is up to about $60 more than the estimate. These two cases use `implement-case-settings.json`, which has the sandbox off, so W4 changes nothing they test. | neither: it is an estimate, and the work is unaffected | `CLAUDE.md:34-37`; `tests/skill-evals/cases/implement-*/settings.txt` | Count the implement cases' agents, or skip those two cases for W4. |
| 10 | COLD-READ | W1: "the `PluginRoot` fixtures move to the `checked-plans/checked-plans/<version>` cache path" | No reason is given. The reason seems to be the repo rename to checked-plans and the real install path in the spike note. The fixtures work as they are. | neither: cosmetic | `tests/test_agent_guard.py:127-129`; spike note `:10` | One clause saying why. |
| 11 | WRONG | Design: "`SECRET_FILE`, `FILE_URL` and `URL` take `re.IGNORECASE`" | `URL` already matches `FILE://`, since its pattern is `[a-zA-Z]`. Only `FILE_URL` needs the flag, so adding it to `URL` does nothing. | neither: has no effect | `hooks/agent-guard.py:335-336` | Reading settles it. |
| 12 | GAP | Spike questions 1 / Open questions: "None" | No work item says when spike 1 runs, or what changes if the answer is no. Its outcome only feeds a Risks sentence. | neither: the guard covers case variants whatever the spike finds | spec Risks, "Case variants…" | Say "run before W4, and update Risks", or drop it. |
| 13 | COLD-READ | W2 Done when: "with `cwd` the home directory … `cat < README.md` from the repo" | The two halves of the sentence give different working directories. With `cwd` set to home, `README.md` doesn't exist and isn't path-like, so the call passes without being checked at all. | neither: exit 0 either way | `hooks/agent-guard.py:1222-1224` | State the `cwd` for this case. |
| 14 | STALE | W3 (not listed) | The module docstring at `:21-25` still describes session history as `HISTORY_HOME`, with one exception. W1 updates only `:39-40`. | neither: comment only | `hooks/agent-guard.py:21-25` | Add the docstring to W3's Files. |

Counts: 14 findings - 3 correctness, 3 requirement, 8 neither
Neither: 7, 8, 9, 10, 11, 12, 13, 14
Cold read: no - W1, "the `PluginRoot` fixtures move to the `checked-plans/checked-plans/<version>` cache path" (no reason given)
Needs a run: 3, 6

### Delta review, 2026-10-02

Reviewed on 2026-10-02 by cold-reviewer: the changes logged as Not reviewed. Saved unchanged.

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
| 1 | GAP | W3: "`AGENT_NOT_DENIED` (:40) is deleted: with no `~/.claude` entries left in `HISTORY_HOME` it removes nothing" | The constant is still used in another place. `test_history_denied_to_agents_and_spikes` loops over `self.history - AGENT_NOT_DENIED`. If someone deletes the constant exactly as written, that test fails with a `NameError`, so W3's "Unit tests pass" fails. The spec should also say to change that loop to `self.history`, and to drop the comment above the constant. The fix is one line and the failure is easy to see. | correctness | `tests/test_sandbox_settings.py:37-40`, `:98` | Reading settles it. Add ":98 loops over `self.history`" to W3. |
| 2 | COLD-READ | W3: "`grep -rn spec ~/.claude` expects the new message" | `check_secrets` adds "…nor session history" to every block message. So a test that checks for "session history" passes with the old message as well as the new one. To tell them apart, the test has to check for wording only the new reason has, such as "Claude Code's own state". This doesn't break anything, because W3's Done when doesn't ask that test to fail before the change. | neither: W3 has no "fails before" condition, and the case is refused either way | `hooks/agent-guard.py:1256-1260`; `tests/test_agent_guard.py:1146-1151` | Name the substring the test should check for. |
| 3 | STALE | Spike questions: "All three run together before W4 lands, in one `claude -p` run with `agent-sandbox.json` rendered with W4's change, under $0.50" | The answers below this line contradict it. S1 was a spike run. S2 and S3 were run by hand and separately, because "a spike can't start a logged-in nested `claude -p`". S3 took two runs. Question 1 runs "with no guard" but question 3 needs the guard, so the three questions could never share one run. | neither: all three are answered, and the answer W4 waits on (question 2) is yes | `docs/specs/spikes/2026-10-02-guard-path-identity-results.md` S2 and S3 setup lines | Reading settles it. Reword the lead-in in the past tense. |
| 4 | ASSUMPTION | Decision: "the allow side (`write` mode's directory, the own root, the session's results) only gains spellings of the same directory on APFS"; Risks: "the guard's fold covers it either way" | Now that the CI sentence is gone, the reason only covers case-insensitive volumes. On a case-sensitive volume, folding case on the allow side lets in different directories. For example, `write` mode would allow `~/NOTES/research`, which there is not the same folder as `~/notes/research`. "Covers it either way" is only true for the deny side. | neither: CI and the agents run on macOS, and the volume here is case-insensitive | `.github/workflows/tests.yml:16-17`; spec Background, the probe of `~/.CLAUDE` | Reading settles it. Scope the Risks line to denies, or note the case-sensitive allow-side widening as accepted. |

The other logged changes check out against the code:
- `with_root` (old guard passed through `with_root(old, None)` at `tests/replay_guard.py:426`)
- the evals' root is `$repo`, with `deny_answer_keys` denies inside it, and S2 answered yes
- `known` built from `PRIVATE_HOME`
- the rewording moved to W4
- the S3 setup matches `run-agent.sh:115-118`
- the six sandboxed skill-eval cases out of eight
- the `checked-plans` path for the fixtures (commit `788cec9`, hand-run note `:10`)
- `URL` already matching `[a-zA-Z]`
- `cwd` for `cat < README.md`
- the module docstring at `:18-24`

Counts: 4 findings - 1 correctness, 0 requirement, 3 neither
Neither: 2, 3, 4
Cold read: yes
Needs a run: none

## Changes since the review

- Delta-reviewed on 2026-10-02: W3 changes `test_recursive_search_over_history_blocked` (the `~/.claude` case expects the new message, a `grep -rn spec ~` case keeps "narrower directory"), from cold review row 1, on 2026-10-02.
- Delta-reviewed on 2026-10-02: W1's `with_root` calls `guard.own_root` only when it has a root, since the `--base` guard has no `own_root`, from cold review row 2, on 2026-10-02.
- Delta-reviewed on 2026-10-02: Design's Sandbox paragraph says the agent evals' root is the repo, with `deny_answer_keys` denies inside it, and new spike question 2 checks they hold; W4 waits for it, from cold review row 3, on 2026-10-02.
- Delta-reviewed on 2026-10-02: W3's `test_agent_denies_known_to_guard` builds `known` from `guard.PRIVATE_HOME`, and `AGENT_NOT_DENIED` is deleted in W3 (no longer mentioned in W4), from cold review rows 4 and 7, on 2026-10-02.
- Delta-reviewed on 2026-10-02: the rewording of `hooks/agent-sandbox.md:8` and `hooks/agents/cold-reviewer.md:19` moves from W3 to W4, whose Done when runs the evals, from cold review row 5, on 2026-10-02.
- Delta-reviewed on 2026-10-02: new spike question 3, whether an agent reads its own saved output with Read under run-agent.sh's flags minus `--add-dir ~/.claude`; a no keeps the flag in W5, from cold review row 6, on 2026-10-02.
- Delta-reviewed on 2026-10-02: Decision's case-folding reason no longer says CI runs on Linux, from cold review row 8, on 2026-10-02.
- Delta-reviewed on 2026-10-02: W4's Done when and Effort leave out the two implement skill-eval cases (sandbox off, unchanged settings), from cold review row 9, on 2026-10-02.
- Delta-reviewed on 2026-10-02: W1 says why the `PluginRoot` fixtures move to the checked-plans path, from cold review row 10, on 2026-10-02.
- Delta-reviewed on 2026-10-02: only `SECRET_FILE` and `FILE_URL` take `re.IGNORECASE`, not `URL`, from cold review row 11, on 2026-10-02.
- Delta-reviewed on 2026-10-02: Spike questions say all three run in one run before W4, and what a no changes for each, from cold review row 12, on 2026-10-02.
- Delta-reviewed on 2026-10-02: W2's Done when gives the repo root as `cwd` for `cat < README.md`, from cold review row 13, on 2026-10-02.
- Delta-reviewed on 2026-10-02: W3 updates the guard's module docstring on session history (`hooks/agent-guard.py:18-24`), from cold review row 14, on 2026-10-02.
- Not reviewed: W3 also changes `test_history_denied_to_agents_and_spikes` (:98) to loop over `self.history`, and drops the comment above `AGENT_NOT_DENIED`, from delta review row 1, on 2026-10-02.
- Not reviewed: W3's `grep -rn spec ~/.claude` test checks for "Claude Code's own state", not "session history", from delta review row 2, on 2026-10-02.
- Not reviewed: the Spike questions lead-in says how the three were answered (S1 a spike, S2 and S3 by hand), from delta review row 3, on 2026-10-02.
- Not reviewed: Risks says the fold widens the allow side on a case-sensitive volume, accepted since the agents and CI run on macOS, from delta review row 4, on 2026-10-02.

## Spikes

- Question 1: Route: spike. Changes: the Risks line "Case variants in the sandbox and permission rules are not known to be folded (spike 1)"; no work item. Expect: the macOS sandbox refuses `wc -c ~/.CLAUDE/settings.json` and `wc -c ~/.AWS/credentials` (Seatbelt judges the file reached, not the spelling); the Read tool's `Read(~/.claude/**)` and `Read(~/.aws/**)` denies don't catch a missing file under `~/.CLAUDE/` or `~/.AWS/`, which gives a not-found error instead of a permission refusal. Box: $2, 60 turns; hosts: none.
- Question 2: Route: deferred, then run by hand on 2026-10-02 (S2): the spike sandbox can't start a logged-in `claude -p`. Expect: the answer key refused, the plugin's files readable. Verdict: EXPECTED.
- Question 3: Route: deferred, then run by hand on 2026-10-02 (S3): the spike sandbox can't start a logged-in `claude -p`. Expect: a path under `tool-results/` and the line 150000. Verdict: EXPECTED, on the second run; the first asked for `seq`, which the guard refuses.

## Implementation

- 2026-10-02, W5 (pending): `tests/test_run_agent.py` asserts no added dir but the plugin root is `~/.claude` or under it, not no added dir at all: `RunAgentFromACache` runs from a root under `~/.claude/plugins/cache`, which must stay added (the existing check at :138-141), so the literal assertion would fail there.

## Evidence

- Started at d7dea8b
- Baseline: python3 -m unittest discover -s tests -> pass (510 tests)
- Baseline: python3 tests/replay_guard.py -> pass
- Baseline: ruff check --isolated --select E9,F . (local ruff; CI's `pipx run ruff==0.16.7` needs the network) -> pass
- Baseline: git ls-files -z '*.sh' | xargs -0 shellcheck -S warning -> pass
- Baseline: claude plugin validate . --json -> pass (only the expected plugin.json version warning)
- Baseline: claude plugin validate .claude-plugin/plugin.json -> pass (warnings only)
- Baseline: tests/agent-evals/run.sh and tests/skill-evals/run.sh -> not run: paid, by hand (CLAUDE.md)
- Drift WARN, no DRIFT line: docs/specs/spikes/2026-10-01-review-fixes-hand-run-results.md (added after read-at b9a37ae, committed in d7dea8b)
- W1 (6a3fb3c): Done when `python3 -m unittest tests.test_agent_guard.CaseInsensitive` -> 10 failures first (`~/.Claude/projects`, `~/.AWS`, `X.TFVARS`, `K.PEM`, `FILE://`, the `~/.AW*` glob stem, `x/.SSH`, the Read/Grep/Glob of `~/.AWS`, `write` under `~/NOTES/research`, a `~/.Claude/plugins/cache/...` root as `OWN_ROOT`), all pass after; `python3 tests/replay_guard.py` -> exit 0 with no new difference, so nothing added to `tests/replay-accepted.txt`; suite pass (514 tests); scan clean
- W2 (b8bb0c3): Done when `python3 -m unittest tests.test_agent_guard.RedirectsAndPwd` -> 4 failures first (`cat < ~/.claude/projects/x.jsonl`, `wc -l < ~/.aws/credentials`, `cat $PWD/.claude/projects/x`, `cat ${PWD}/.aws/config` all exit 0), all pass after, with `grep x <<< "$PWD"`, `sort < /dev/null` and, from the repo root, `cat < README.md` exiting 0; `python3 tests/replay_guard.py` -> exit 0, no new difference; suite pass (516 tests); scan clean
- W3 (ae734bb): Done when `python3 -m unittest tests.test_agent_guard.SessionHistory tests.test_sandbox_settings` -> 12 failures first (Read of the seven `~/.claude` state paths exit 0, `grep -rn spec ~/.claude` without "Claude Code's own state", and the sandbox tests once `AGENT_NOT_DENIED` went), all pass after, with Read and `sed -n 1p` of the session's own `tool-results/b.txt` exit 0, another session's exit 2, and the `PluginRoot` and `SessionResultsLink` tests still passing; `python3 tests/replay_guard.py` -> exit 1 with 20 reads and 7 headless commands newly refused (the old symlink install's files under `~/.claude/skills`, `agents` and `hooks`, `~/.claude/settings.json`, listings of `~/.claude` state), all accepted naming W3, then exit 0; suite pass (518 tests); scan clean
- W4 (12ccccd): Done when `python3 -m unittest tests.test_sandbox_settings tests.test_user_deny` -> 3 failures first (no `~/.claude` in either file's `denyRead`, no `allowRead`, `denyRead` not the Read denies plus `.claude`), all 15 pass after, `test_agent_case_settings_differ_only_as_planned` and `test_implement_case_settings_differ_only_in_the_sandbox` unchanged and passing, and the new `tool-results/b.txt` check passing before and after since `hooks/user-deny.json` doesn't change; `hooks/agent-settings.py hooks/agent-sandbox.json /tmp/some-root` -> `allowRead` `['/tmp/some-root']` (the file had no `allowRead` before); `tests/agent-evals/run.sh` and the six sandboxed skill-eval cases on Sonnet and Opus -> not run: paid, run by hand (CLAUDE.md), so no `tests/agent-evals/BASELINE.md` section was added; spike questions 1–3 answered before, question 2 yes (spec); suite pass (520 tests), replay exit 0, plugin validate pass; scan clean

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

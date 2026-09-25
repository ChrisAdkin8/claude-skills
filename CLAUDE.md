# Working in this repo

The files here are what Claude Code runs: `~/.claude/skills`, `agents` and `hooks` are symlinks into
this repo, so an edit is live the moment it's saved. Keep every file valid at each step, and expect a
skill you're editing to be the one you're running.

## Before committing

- `python3 -m unittest discover -s tests` — deterministic tests for the guard, both checkers,
  `review-state.py`, `prepare-spike.sh` and `run-agent.sh`.
- `python3 tests/replay_guard.py` — the guard against real recorded commands and file reads.
- After changing an agent or skill file, run `tests/agent-evals/run.sh` by hand. A full run cost
  $4.02 on 2026-09-25 and each case is capped at $5, so it isn't automatic. Add a dated section to
  `tests/agent-evals/BASELINE.md` with every case's result and cost, including the cases you didn't
  expect to change.
- After changing a skill's steps, run `tests/skill-evals/run.sh` by hand too (about $0.30 a case,
  capped at $3), and record its results in the same `BASELINE.md` section.
- A change to `skills/spec/` or `agents/spec-*` usually needs `check-spec.py` run over
  `docs/specs/` too: the specs in this repo cite these files by `path:line`.

## Conventions

- Commit messages: `spec:`, `research:`, `evals:`, `guard:`, `repo:`, `readme:` — the area, then what
  changed. Branch before committing; never push unless asked.
- Files refer to themselves and each other by `~/.claude/...` paths, which the symlinks keep valid.
  Don't rewrite them as repo-relative paths; the guard resolves them to recognise its own scripts.
- Specs live in `docs/specs/`, and `/spec`'s step 7 writes spike results to `docs/specs/spikes/`.
- `skills/synced/` holds skills Claude Code syncs from the claude.ai account. It's git-ignored and
  machine-managed: don't edit or commit it.
- No secrets, credentials or account IDs anywhere, including in test fixtures and spec citations.
- Log every README change as a dated `- Not reviewed: ...` line at the end of
  `records/README-record.md`, so its next delta review covers it.

## The workflow diagram

- The README's diagram is `docs/workflow*.png`, drawn by `docs/diagram/workflow.py`. Edit the
  script, never the PNGs: `cd docs/diagram && npm install` once, then
  `python3 docs/diagram/workflow.py` redraws all four.
- Text is placed by estimated widths, so look at the PNGs after changing any wording.
- The diagram's six stages (Capture, Research, Plan, Spike, Build, Close out) match the numbered
  list under "From idea to merged change" in the README. Change one, change the other.

# Working in this repo

The files here are what Claude Code runs: `~/.claude/skills`, `agents` and `hooks` are symlinks into
this repo, so an edit is live the moment it's saved. Keep every file valid at each step, and expect a
skill you're editing to be the one you're running.

## Before committing

- `python3 -m unittest discover -s tests` — deterministic tests for the guard and both checkers.
- `python3 tests/replay_guard.py` — the guard against real recorded commands and file reads.
- After changing an agent or skill file, run `tests/agent-evals/run.sh` by hand. It costs $1–2 in
  tokens, so it isn't automatic. Add a dated section to `tests/agent-evals/BASELINE.md` with every
  case's result and cost, including the cases you didn't expect to change.
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

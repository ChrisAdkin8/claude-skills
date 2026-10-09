# Working in this repo

The files here are what Claude Code runs when you start it from this checkout with
`claude --plugin-dir .`, so an edit is live the moment it's saved. (An installed plugin runs a copy
in Claude Code's plugin cache instead, which an edit here doesn't reach.) Keep every file valid at
each step, and expect a skill you're editing to be the one you're running.

## Before committing

- `python3 -m unittest discover -s tests` — deterministic tests for the guard, both checkers,
  `build-index.py`, `review-state.py`, `git-read.py`, `prepare-spike.sh`, `run-spike.sh`,
  `run-agent.sh`, `run-name.py`, `launch-checks.sh`, `agent-def.py`, `agent-settings.py`, `mdcheck.py`,
  `mine-sessions.py`, `scan-diff.py`, `prepare-verify.sh`, `run-verify.sh`, `run-implementer.sh`,
  `ledger.py` and the research scripts; that the eval runners exit 1 on a failure; that the guard's and all four sandbox
  settings' deny lists agree, and `hooks/user-deny.json` with them; that no skill's allowed-tools
  holds a path rule Claude Code ignores; that `/implement`'s own git commands turn off the file
  watcher and hooks and match its allowed-tools; and the README's index-rebuild command. CI runs these,
  with ruff, shellcheck and `claude plugin validate`.
- `python3 tests/replay_guard.py` — the guard against real recorded commands and file reads. It
  exits 0 when every difference is listed in `tests/replay-accepted.txt`, by fingerprint, never by
  the command (the transcripts are private). Add an entry, with its reason, only for a change the
  guard means.
- After changing an agent or skill file, run `tests/agent-evals/run.sh` by hand. A full run cost
  $1.80 on Sonnet and $4.58 on Opus on 2026-10-04, and each case is capped at $5 (`research-ideas`
  at $10), so it isn't automatic. Add a dated section to `tests/agent-evals/BASELINE.md` with every
  case's result and cost, including the cases you didn't expect to change.
- After changing a skill's steps, run `tests/skill-evals/run.sh` by hand too (about $0.40 a case
  for the skill's own session, capped at $3, plus the agents a case launches, capped at $2 each),
  and record its results in the same `BASELINE.md` section. A case fails on any call the skill's
  allowed-tools refused, so a call a skill needs must be pre-approved.
- Run both eval sets once per model the skills run on: Sonnet and Opus, with `EVAL_MODEL=sonnet`
  and `EVAL_MODEL=opus`. Record each model's results in the same dated `BASELINE.md` section, with a
  column for the model. Run one set after the other, never at the same time: each checks that
  nothing else in `~/notes` changed while it ran.
- A change to `skills/implement/` or `hooks/agents/implementer.md` needs the implement skill-eval
  cases, `implement-basic` and `implement-trap`, on both models. Each also runs the implementer
  (capped at $5 under the runner) and up to two verifiers ($5 each), which the runner's printed
  cost leaves out: add theirs from the `run.json` files in the results.
- A change to `skills/spec/` or `hooks/agents/spec-*` usually needs `check-spec.py` run over
  `docs/specs/` too: the specs in this repo cite these files by `path:line`.

## Conventions

- Commit messages: `spec:`, `research:`, `cold-review:`, `implement:`, `evals:`, `tests:`, `guard:`,
  `repo:`, `readme:` — the area, then what changed. Branch before committing; never push unless asked.
- Commit from this checkout, not GitHub's web editor: its commits carry no prefix, skip the README
  record, and may use another email address. Merge pull requests here too, with
  `git merge --no-ff` and a push of `main`: GitHub's merge button authors the merge commit with
  another email address.
- `.claude-plugin/plugin.json` has no `version` on purpose: each commit on `main` is a new version
  for installed users (README, Update), so merge only what's ready to ship.
- In a skill's `allowed-tools`, pre-approve writes with `Edit(path)`, which also covers the Write
  tool. Claude Code never consults a `Write(path)`, `Glob(path)` or `NotebookEdit(path)` rule
  (`tests/test_skill_frontmatter.py`).
- Skills and the files they load refer to the repo's files as `${CLAUDE_PLUGIN_ROOT}/...`, which
  Claude Code expands to the plugin root: this checkout, or the plugin cache. Don't rewrite them as
  repo-relative or `~` paths; the guard finds its root from its own location to recognise its
  scripts. Dated documents (`docs/specs/`, every `records/`, `CHANGELOG.md`,
  `tests/agent-evals/BASELINE.md`) keep the paths they were written with, and
  `tests/test_no_stale_paths.py` fails on an old install-path reference anywhere else.
- Specs live in `docs/specs/`, and `/spec`'s step 7 writes spike results to `docs/specs/spikes/`.
- `skills/synced/` holds skills Claude Code syncs from the claude.ai account. It's git-ignored and
  machine-managed: don't edit or commit it.
- No secrets, credentials or account IDs anywhere, including in test fixtures and spec citations.
- Log every README change as a dated `- Not reviewed: ...` line at the end of
  `records/README-record.md`. The README has had its one full and one delta review, so
  `/cold-review` won't review these again; they record what changed since.

## The workflow diagram

- The README's diagram is `docs/workflow*.png`, drawn by `docs/diagram/workflow.py`. Edit the
  script, never the PNGs: `cd docs/diagram && npm install` once, then
  `python3 docs/diagram/workflow.py` redraws all four, and the social preview below.
- It also draws `docs/social-preview.png`, the repo's 1280x640 social media preview. GitHub can't
  take that from the repo: after redrawing it, upload it by hand in Settings > General > Social
  preview.
- Text is placed by estimated widths, so look at the PNGs after changing any wording.
- The diagram's six stages (Capture, Research, Plan, Spike, Implement, Close out) match the numbered
  list under "From idea to merged change" in the README. Change one, change the other.

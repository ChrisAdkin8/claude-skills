# Changelog

What changed, by day, drawn from the commit history. The repo has no releases or tags, so each
section is a date. Within a day, changes are grouped by area.

## 2026-09-25

### Security

- The agents run headless inside an OS sandbox, with a cost cap on each run. A reply that isn't in
  its agent's format is refused.
- The agents' Bash can't write to `~/.claude`, `~/notes` or `~/code`, and can't read session history.
- Agent and spike runs don't load a reviewed repo's own settings or `CLAUDE.md`.
- The guard allows only a short list of git's own options, runs `git-read.py` without a pager, and
  limits the arguments of the scripts that run outside the sandbox.
- The guard closes three bypasses of its variable rule and size caps that the cold review found.

### Added

- `/spec quick`, for small changes whose approach is settled.
- `/spec` fails a reviewed or in-progress spec whose changes skipped the delta review, and makes
  that gate hard to slip past by accident.
- `/spec done` asks about each work item's Done when.
- `/cold-review` works out a document's review state and diff base with a script, diffs a delta
  review from the original review commit, and finds changes that weren't logged.
- Tests for the agent launcher, the record layout and `check-spec.py`'s citation and work-item
  checks; a replay of the headless agent runs through the guard; and the first skill eval.
- Agent evals for the researcher at quick and ideas depth, and for `/cold-review`'s delta path.
- A workflow diagram in the README, drawn by `docs/diagram/workflow.py`, which also draws a
  1280x640 social preview card.

### Changed

- `/research` is safe to run beside another `/research`, and commits only the files it names in
  `~/notes`.
- `/research` says in the note when verification checked only a sample of the claims, matches
  Verification rows as whole words, and checks figures beyond WebFetch's summary.
- `/research` pre-approves `/idea`'s git commands.
- `/spec` reads a house-format spec's status and warns when it states none.
- `/spec` runs one verifier round 2, and each finish gets its own run directory.
- `/spec` and `/cold-review` run directories are named after the repo as well as the document.
- The checkers share one markdown helper module, which reads fences, tables, lists and account IDs
  the way markdown and YAML do.
- The skills and agents load less text: restated reasons are trimmed from the three largest skills.
- The README is rewritten for readability. It defines terms before using them, its stages match the
  diagram, and it has a clone step. The cold review's findings are folded in.
- `CLAUDE.md` gives current eval costs, the skill evals, and how to redraw the diagram and the
  social preview.

## 2026-09-24

### Security

- The guard keeps credentials out of the agents' reach, and closes variable, symlink, URL-size and
  git pre-approval leaks.
- Spike sessions get a wider read-deny, prepared by `prepare-spike.sh`.

### Added

- `/spec done`, to settle a spec after it's built. The plan stays in the spec and its history goes
  in a separate record.
- A delta review: a later review covers only the changes logged since the last one.

### Changed

- One cold reviewer agent serves both `/cold-review` and `/spec`, and spikes move into their own
  file.
- The checkers ignore `{{` in code, scan spike results, and count unreviewed changes.
- A later part of a split spec can keep its work-item numbers.

## 2026-09-20

### Added

- `/cold-review`, a skill that gives any markdown file an adversarial cold read.

## 2026-09-18

### Added

- An MIT licence, so these skills can be copied.
- A `CLAUDE.md` for working on the skills themselves.

### Changed

- The README is written for someone who hasn't used these skills.

## 2026-09-17

### Added

- `/spec` step 7, Spike: spike questions run in sandboxed headless sessions, and the answers are
  folded back into the spec. It comes with spiker rules, sandbox settings, a launcher script, spike
  entries in the template, and spike results checked by the verifier.
- The spec checker fails when a spike results file is missing.
- An agent eval for spike results, and a full baseline run.

### Changed

- Spikes can render charts locally with helm.
- Spike sessions use narrower write denies and a sandbox-safe git rule, and keep the spiker's git
  directory outside `src/`.
- Step 7's folded lines don't count towards the spec's word limit.
- `/spec` says what a spike can't fetch, and how to re-run a question left Open.
- `skills/synced/`, the account skills Claude Code syncs, is git-ignored.

## 2026-09-15

### Security

- The guard blocks environment-variable assignments that change what a command runs, and treats
  variables that only Bash exports as dangerous.

### Added

- Four agent evals for the research and spec verifiers.
- `/research` hunts for prior art behind absence claims at full depth, adds a narrow third
  verification round, and caps the number of claims.
- `/research` at ideas depth files the top three ideas as idea notes.
- `/spec` saves the cold review in the spec, and re-checks the spec after spikes.

### Changed

- `/research` records every verifier row, and cuts only unverified points to meet the word limit.
- `check-note.py` compares the Verification header with its table, and allows 10 % over the limit
  once a note is verified.
- `check-spec.py` treats a saved `## Cold review` section as a record.
- The repo moved from `~/.claude` to `~/code/github.com/claude-skills`, with symlinks back into
  `~/.claude`.

## 2026-09-14

### Added

- The first version: the `/research`, `/spec` and `/idea` skills, their agents, and the guard hook.
- `/research ideas`, for a ranked shortlist of things to build.

### Changed

- When filing a shortlist, `/research` matches existing idea notes by title.

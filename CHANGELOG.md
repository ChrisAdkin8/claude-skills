# Changelog

What changed, by day, drawn from the commit history. The repo has no releases or tags, so each
section is a date. Within a day, changes are grouped by area.

## 2026-09-27

### Security

- The guard fails closed: it refuses the call when it crashes or gets input it doesn't expect,
  and refuses a write with no file path. Before, an unexpected error let the call through.
- Shell history, cookies, Chrome's profile and keychains are denied to the Read tool as well as to
  shell commands, and to spikes. A test checks that the guard and both settings files deny the same
  paths.

### Added

- CI: GitHub Actions runs the unit tests on macOS on each push to `main` and each pull request,
  and lints with ruff (errors only) and shellcheck (warnings and above).
- Tests for `mdcheck.py`, `git-read.py`, `run-spike.sh` and the two eval runners.

- A mind-map index for `~/notes`. Every research note gets a `topic` (an area, and optionally a
  sub-area), and `/research`'s last step rebuilds `~/notes/index.md` from those topics with the new
  `build-index.py`: research notes grouped under their topics, with their ideas and decisions
  under them. Markmap shows it as a clickable mind map; the README says how to open it.
- The researcher sets a `topic` on each note, reusing one already in use where it fits.
- Specs for `/implement`, a planned skill for workflow stage 5, in two parts: its tools (range-level
  drift, a diff scanner and a sandboxed `implement-verifier`), then the skill. It will hand the
  work to an `implementer` subagent, a headless session of its own on a git worktree. Both specs
  are drafts awaiting their delta review; the skill isn't built yet.

### Changed

- Checks that specs and notes used to pass when they shouldn't:
  - A `# comment` in a code block no longer ends a record's `## Cold review` section, and a
    `## Cold review` quoted in a code block isn't taken for a saved review. The heading matches in
    any case, so `## Cold Review` no longer turns off the delta-review gate.
  - A `---` rule at the top, or frontmatter that's never closed, isn't frontmatter: the spec's
    citations are checked, rather than 0 citations and a PASS.
  - A code block that's never closed fails, instead of hiding the rest of the document.
  - A bare-filename citation is range-checked when only one file has that name, and fails a
    template spec when several do.
  - `Done when` must be the field line itself, and `TBD`, `TODO`, `?` or `...` counts as empty.
  - A lone carriage return isn't a line break when counting a cited file's lines.
  - After Sources, an indented line after a blank line is prose, not a source. Indented prose in
    the Candidate pool counts, and a candidate over 120 words fails.
  - An *(unverified)* mark right after one sentence's full stop no longer covers the next sentence.
  - In a shallow clone, `review-state.py` reports `no-base` rather than taking the clone's cut-off
    commit for the review commit.
- `check-note.py` fails a research note with no topic, or one that isn't `area` or
  `area/sub-area` in lowercase and hyphens, and warns on a topic no other note uses.
- `check-note.py` and `build-index.py` share the topic pattern through `mdcheck.py`.
- Workflow stage 5 is Implement, not Build. The diagram shows `/implement` as its command, says
  under each stage's command whether its work runs in your session or in a subagent, and shows
  stage 2 rebuilding the notes index, with its verifier checking the key claims.
- The README defines skill, hook, frontmatter and turn where it first uses them, gives Layout as a
  table, and follows the mind-map index through all six stages as a worked example.
- The README takes five fixes from a delta cold review, which is saved in its record: the
  `research-ideas` eval case's $10 cap, a Topics section for `~/notes/CLAUDE.md`, what the worked
  example's verifier actually checked, and where unfiled notes go in the index.
- `CLAUDE.md` gives the agent evals' current cost and the `research-ideas` case's cap.
- One code-block walker, heading rule and citation pattern in `mdcheck.py`, used by every
  checker. `#2 on Hacker News` no longer ends a section, and form feeds no longer add lines.
- `check-spec.py` ignores a `## Cold review` quoted in a code block, and counts `Makefile:40` and
  other extensionless files as citations.
- `review-state.py` follows a renamed document and names every section a change touches.
- `build-index.py` wraps a link path holding a space or bracket in angle brackets.
- Both eval runners exit 1 when a case fails, and have separate cost caps, `AGENT_EVAL_MAX_USD` and
  `SKILL_EVAL_MAX_USD`. Four graders check the finding rather than a keyword.
- `replay_guard.py` prints SKIP when there's nothing to replay, and exits 1 on a regression.
- The README's diagram shows light in light mode; it showed the dark version to everyone. The
  README and `CLAUDE.md` list every test file and the CI, and give the fourth eval run's cost.
- The diagram's renderer is pinned to one version, with its lockfile committed.
- `review-state.py` prints its `diff:` line as a quoted `~/.claude/hooks/git-read.py` command,
  which `/cold-review` may run without a prompt, and which works for paths with spaces.
- `build-index.py` skips a broken link or a folder named `*.md` instead of crashing, escapes a
  backslash in a title, and reads a note that starts with a byte-order mark.
- `repo-health.sh` no longer reports a failure as a fact about a repo. It exits 1 when `gh` or
  `jq` is missing or `gh` isn't logged in, says "not found or no access" only when GitHub says so
  and "API error" otherwise, exits 1 when no repo could be read, and fetches four repos at a time.
  `reddit-search.sh` and `gcp-skus.sh` check their tools first, and `gcp-skus.sh` URL-encodes the
  page token. Tests for all three use stub `gh`, `curl` and `gcloud`.
- Skill instructions that a model could follow into the wrong result:
  - `/spec` lists the review's `Needs a run` rows as candidate spike questions, and adds them only
    if the user picks them, instead of editing the spec straight after its review. It asks which
    findings to fold in with one multi-select question, and always gives the implementation
    prompt, spike questions or not.
  - `/cold-review` saves a spec's full review without asking, as it already did its delta
    review, so a later `/spec finish` doesn't run a second one. It runs the delta `diff:` line
    as printed, through `git-read.py`.
  - All three agent-running skills say exit 2 means the run never started, so they don't read an
    earlier run's `run.err`, and take a fresh run dir rather than overwrite an earlier session's
    replies.
  - `/idea` and `/research` stop, pointing to the README, when `~/notes` isn't set up.
    `/research` never moves an `adopted`, `parked` or `dropped` idea back to `exploring`.
  - `/spec spike` resolves a `HEAD` read-at to a commit, which `prepare-spike.sh` needs. `/spec
    done` reads the spec's repo with `-C` and finds its first commit through a rename.
- Tests and evals that could pass a wrong answer, or miss a regression:
  - A table of 42 guard refusals (file writes, `gh` and git writes, `curl` sends, `sed -i`,
    `find -exec` and the rest), each checked for its reason; most had no test.
  - The `delta-review` cases need the grade in the Affects cell. `cold-review-delta` rejects "no
    unlogged change" and a base that doesn't exist. Both skill graders fail a skill that commits.
  - The runner tests check that each cap and sandbox flag reaches `claude`, as does
    `test_run_spike.py` for a spike's $2 and 60 turns.
  - An ideas-depth fixture tests the Candidate pool and Shortlist checks for free.
  - `test_prepare_spike.py` and `test_run_agent.py` use a home of their own, not `~/.cache`.
  - `replay_guard.py` replays every Bash command from the headless runs, of any date, and fails if
    one gets a different verdict now than it got when it ran.
- Both eval runners refuse an empty cases folder instead of crashing on bash 3.2, clean up their
  temp folders and eval notes if interrupted, and the skill runner counts only this run's results.
  The agent runner fails a research case when `~/notes` isn't a git repo, since it can't see
  changes there.
- `mdcheck.py` holds the delta-review pattern, the record path and the secrets scan the checkers
  each kept a copy of.

## 2026-09-26

### Added

- This changelog, drawn from the commit history.

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

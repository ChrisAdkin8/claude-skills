---
title: "Usability, part 2a: /implement refuses early"
created: 2026-10-07
status: in-progress # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 08570cb
cite-repo: none
---

# Usability, part 2a: /implement refuses early

## Goal

`/implement` says what it can't do before it spends anything. Every refusal the launcher would make comes before the worktree and first commit exist, a spec edited by hand since its review stops at the gate, and folder and file names with spaces or accents work.

Part 2a of the usability series from 2026-10-07. Part 2 was split into 2a and 2b after its two verifier rounds and its cold review, which covered both halves, so each part's record keeps that history. This part has W1 to W3 and `docs/specs/2026-10-07-usability-2b-real-repos.md` has W4 to W7; part 2's W3 and W4 swapped places, so part 2's W4, unusual names, is W3 here. Part 1b (`docs/specs/2026-10-07-usability-1b-which-account-pays.md`), built on 2026-10-08, is a prerequisite for W1, which reuses its launch checks (`hooks/launch-checks.sh`); part 2b's W4 builds on W1.

## Decision

- **Refusals:** a `--check` mode of `run-implementer.sh` runs the same checks without launching, and the gate calls it, so the two can't drift apart.
- **Hand edits:** the gate runs `review-state.py`, rather than teaching `check-spec.py` a second way to read review history, and W2 fixes the two ways it misreads them for the gate: it counts every edit, a status change or a re-cite included, though only changes to the plan are logged, and it stops looking once a delta review is saved.
- **Names:** the skills map a folder or file name to a safe one, rather than loosening the launchers' name checks, which stop paths from escaping their folders.

## Background

Read at `08570cb` on 2026-10-09, after parts 1a and 1b were built; first read at `377b2dd` on 2026-10-07.

**Refusals after the worktree exists.** The gate (`skills/implement/SKILL.md:46-55`) runs before the worktree and its first commit are made (:59); the launcher runs at :75. Only then does it refuse a Claude Code older than 2.1.277 (`skills/implement/scripts/run-implementer.sh:68`, through `hooks/launch-checks.sh:21-35`), a run dir name outside its pattern (`skills/implement/scripts/run-implementer.sh:98-101`), a bad `IMPLEMENT_MAX_USD`, `IMPLEMENT_CALL_MAX_USD` or `IMPLEMENT_INTERRUPT_WAIT` (`:106-114`), a spent cap (`:118-135`), a machine with no macOS per-user temp dir, such as Linux (`:155-156`), or a user setting that could widen its sandbox (`:171-186`).

**Hand edits.** `check-spec.py` fails a reviewed spec only for changes logged as `Not reviewed:` (`skills/spec/scripts/check-spec.py:864-871`). `review-state.py` reports `unlogged` when the document changed and nothing was logged (`skills/cold-review/scripts/review-state.py:11`, `:252`). It counts any changed line, the frontmatter's `status:` included (`:226-232`), so a spec moved to `reviewed` after its review commit reads `unlogged` too; and once a delta review is saved it reports `done`, whatever has changed since (`:245-246`). The gate never runs it (`skills/implement/SKILL.md:46-55`), so an edit made in an editor after the review is implemented unreviewed, though the README promises "nobody implements unchecked changes by mistake" (`README.md:255-257`).

**Names.** Run dir names must match `[A-Za-z0-9][A-Za-z0-9._-]*` (`skills/implement/scripts/run-implementer.sh:98-101`; `hooks/run-agent.sh:83-84`; `skills/implement/scripts/ledger.py:58`), as do the verifier's and the spikes' launchers (`skills/implement/scripts/run-verify.sh:59`, `skills/implement/scripts/prepare-verify.sh:85`, `skills/spec/scripts/run-spike.sh:36`, `skills/spec/scripts/prepare-spike.sh:72`), and the skills build them from the repo folder's name and the document's basename (`skills/implement/SKILL.md:43`; `skills/cold-review/SKILL.md:146`). On 2026-10-07, `run-agent.sh` refused `My App`, `_infra`, `café`, `api+web` and `Design Notes` with "run dir must be ~/.cache/agent-runs/<name>/<agent>", which doesn't say the name is the cause. `/implement`'s worktree, branch and verifier scratch folder take the raw names too (`skills/implement/SKILL.md:42-43`), and so does the branch in `/spec`'s hand-off, `/spec done`'s lookup and the implementer's clean-up (`skills/spec/SKILL.md:150`; `skills/spec/done-step.md:11`; `hooks/agents/implementer.md:48`). On 2026-10-09, `git check-ref-format --branch 'implement/Design Notes'` refused the name, while `implement/café` and `implement/Design-Notes-1a2b3c` passed.

## Non-goals

- Linux support. W1 only moves the refusal earlier and says why.
- Dependencies, exit 4's message, the closing commands and the verifier's copies, which are part 2b's.

## Design

**Gate, new checks 5 and 6** (`skills/implement/SKILL.md` step 2):

5. `run-implementer.sh --check <run dir>`, given the run dir step 4 will launch with, so it checks the same name and ledger. It runs the refusals that don't need the worktree: part 1b's launch checks, the run name, the three variables' values, the cap, the temp dir and the settings keys. It skips the worktree's checks, making the run and scratch dirs, the brief, rendering the settings, the snapshot and the ledger's start line, so it writes nothing and launches nothing.
6. `review-state.py --plan <spec>`, acting on each state it prints (`skills/cold-review/scripts/review-state.py:243-252`). It carries on for `full`, a spec with no saved review, which `check-spec.py` allows, for `unchanged` and `done`, and for `delta`, since check 3's `check-spec.py` already stops a reviewed spec with unreviewed lines. It stops on `unlogged` with "the spec's plan changed after its review and the change isn't logged: run `/cold-review <spec>`, which drafts the `Not reviewed:` lines for you to confirm", and on `no-base`, where git has no history to compare with, as in a shallow clone, with "the gate can't see the spec's history: run `git fetch --unshallow`, then `/implement <spec>` again". W2 adds `--plan`, which counts a change only in the Decision, Design or Work items, with each citation's line numbers set aside, since only those changes are logged (`skills/spec/SKILL.md:113`, `:147`): a status change, a moved `read-at` or a re-cite reads `unchanged`. W2 also makes `review-state.py`, with or without `--plan`, look past a delta review: a change since the delta review's commit, the one that added its `### Delta review, <date>` heading, with no `Not reviewed:` line logged after it, reads `unlogged`, not `done`. The base is that commit itself, never its parent as the full review's can be (`skills/cold-review/scripts/review-state.py:207-213`), so edits saved in the same commit as the delta review count as reviewed; while the heading isn't committed yet, as `/cold-review` leaves it, the state stays `done`, as today. Searching for that heading, not for `Reviewed on <date> by` as the full review is found (`skills/cold-review/scripts/review-state.py:170-195`), keeps a full and a delta review on the same date apart. For that case `/cold-review` logs the lines under `## Changes after the delta review` and stops, as there is no third review.

**Names.** A new script, `hooks/run-name.py <name>`, prints the name unchanged if it already fits the pattern; otherwise it normalises it to Unicode NFC, so `café` stored either way gives one name, folds accents to ASCII, turns each run of other characters into `-`, drops leading punctuation, and adds `-` and the first 6 hex digits of the SHA-1 of the NFC form's UTF-8, so two different names almost never share a run dir. A name with no ASCII letter or digit left, such as `日本` or `___`, gets `x` before the hash, since the pattern needs a letter or digit first. The skills run it on the repo folder's name and the document's basename, and every name built from those uses its output: `/implement`'s worktree folder, branch, run name and verifier scratch folder, and the same branch in `/spec`'s hand-off and `/spec done`'s lookup. The implementer's clean-up takes its branch from git instead of building it. The spec's and record's own paths keep the real basename. The launchers' refusal also says which part failed and why.

## Work items

### W1: every refusal comes before the worktree

- **Change:** `run-implementer.sh --check`, and gate check 5 calling it.
- **Files:** `skills/implement/scripts/run-implementer.sh`, `skills/implement/SKILL.md`, `tests/test_run_implementer.py`, `tests/test_implement_skill.py`.
- **Done when:** new tests show `--check` exits 2 with the same message as a real launch for a Claude Code older than 2.1.277, a widening settings key, a missing temp dir, a bad run name, a bad `IMPLEMENT_CALL_MAX_USD` and a spent cap, exits 0 otherwise, calls the stub `claude` only for `--version`, and leaves no run dir, scratch dir or ledger line behind. A test in `tests/test_implement_skill.py` finds gate check 5 before step 3's `worktree add`, and its command shape in `allowed-tools`. The unit tests pass, and `implement-basic` and `implement-trap` pass on Sonnet and Opus.

### W2: a hand edit after the review stops the gate

- **Change:** gate check 6; `review-state.py`'s `--plan` and its look past a delta review; `/cold-review`'s step 1 logging, without a review, an `unlogged` change made after a delta review.
- **Files:** `skills/implement/SKILL.md`, `skills/cold-review/scripts/review-state.py`, `skills/cold-review/SKILL.md`, `tests/test_review_state.py`, `tests/test_implement_skill.py`, `tests/test_eval_runners.py`, `tests/skill-evals/cases/implement-hand-edit/` (new: `setup.sh`, `prompt.txt`, `location.txt`, `settings.txt`, `grade.py`), a case of its own because the runner takes each case's prompt and settings from its own folder (`tests/skill-evals/run.sh:86-99`) and `implement-trap` must still reach its trap.
- **Done when:** new tests in `tests/test_review_state.py` show that, under `--plan`, a spec whose only changes since its review are its `status:` line, a moved `read-at` and re-cited line numbers reads `unchanged`, and one whose Done when changed reads `unlogged`; that one with a delta review and then an unlogged body edit reads `unlogged`; that it reads `done` once a `Not reviewed:` line is logged for the edit; that a spec whose full and delta reviews share a date, with changes between them and none since the delta review, reads `done`; that a delta review saved in the same commit as the edits it reviewed reads `done`; and that the tests that save a delta review without committing it and expect `done` (`tests/test_review_state.py:109-117`, `:191-204`, `:262-271`) still pass. The first three fail on today's script, and the rest guard the fix (`skills/cold-review/scripts/review-state.py:245-246` gives `done` today). A test finds check 6, its action for each state, and `review-state.py --plan` in `allowed-tools`. The new case is `implement-trap`'s fixture with a cold review saved in its spec's record and committed, its `Reviewed on <date> by` line in the format `tests/skill-evals/cases/cold-review-delta/setup.sh:45` uses (that fixture keeps its review in the document itself), and then an unlogged edit to one of its work items' Done when lines, which `--plan` counts, committed to the reviewed spec; its grader passes only if no worktree was made and the reply names `/cold-review`, and `tests/test_eval_runners.py` grades it on a synthetic run. It fails on today's skill, and passes after the change, on Sonnet and Opus.

### W3: unusual names work

- **Change:** `hooks/run-name.py`; the skills' naming rules, for run names and for the worktree, branch and scratch folders; the implementer's clean-up taking its branch from git; and clearer refusals in the launchers.
- **Files:** `hooks/run-name.py` (new), `skills/implement/SKILL.md`, `skills/spec/SKILL.md`, `skills/spec/done-step.md`, `hooks/agents/implementer.md`, `docs/repo-guide.md` (its table of scripts), `CLAUDE.md` (its list of tested scripts), `skills/spec/spike-step.md` (its `<scratch>` name), `skills/cold-review/SKILL.md`, `skills/research/SKILL.md`, `hooks/run-agent.md` (its `<name>`), `hooks/run-agent.sh`, `skills/implement/scripts/run-implementer.sh`, `skills/implement/scripts/run-verify.sh`, `skills/implement/scripts/prepare-verify.sh`, `skills/spec/scripts/run-spike.sh`, `skills/spec/scripts/prepare-spike.sh`, `tests/test_run_name.py` (new), `tests/test_run_agent.py`, `tests/test_run_implementer.py`, `tests/test_prepare_verify.py`, `tests/test_run_spike.py`, `tests/test_prepare_spike.py`, `tests/test_implement_skill.py`.
- **Done when:** `hooks/run-name.py 'Design Notes'` prints a name the launchers accept, the same each time, and different from `run-name.py 'Design-Notes'`; `run-name.py my-app` prints `my-app`; `run-name.py '日本'` and `run-name.py ___` print names the launchers accept; and `café` gives one name whether its `é` is stored composed (`café`) or decomposed (`café`). Each skill's `allowed-tools` pre-approves it. Each of the six launchers with a bad name says the name may hold only letters, digits, `.`, `_` and `-`, starting with a letter or digit. `git check-ref-format --branch "implement/$(hooks/run-name.py 'Design Notes')"` succeeds. A test in `tests/test_implement_skill.py` finds the Frame's `<worktree>`, `<branch>`, `<run name>` and `<scratch V<n>>` built from `run-name.py`'s output and `<record>` from the real basename, and finds no `implement/<spec basename>` built from the raw name in `/spec`'s hand-off, `/spec done`'s lookup or the implementer's clean-up. The unit tests pass.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 2 h | part 1b's W5 and W7 |
| W2 | 4 h, `review-state.py` and a new eval case included | none |
| W3 | 5 h, six launchers and the worktree and branch names | none |
| Evals | the implement cases on both models, then both sets on both models | W1 to W3 |

The hours come from reading the scripts and are guesses. Every item changes `skills/implement/`, so `implement-basic` and `implement-trap` run on both models, each with its implementer and up to two verifiers on top (`CLAUDE.md:35-38`); they cost $3.00 for both models on 2026-10-04 (`docs/repo-guide.md:109-110`).

## Spike questions

None.

## Risks and rollback

- `--plan` counts only the Decision, Design and Work items, so a hand edit to the Goal, Background or Non-goals alone passes the gate; the repo's rules don't log those either (`skills/spec/SKILL.md:147`).
- Each item reverts on its own; none changes a file format another reads.

## Open questions

- The second verifier round also said the plan didn't hold: W2's new case had no saved cold review for `review-state.py` to read. Its fixture now saves and commits one before the edit, but no third round has checked that fix.

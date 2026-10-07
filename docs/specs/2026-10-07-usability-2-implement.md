---
title: "Usability, part 2: /implement on real repos"
created: 2026-10-07
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 377b2dd
cite-repo: none
---

# Usability, part 2: /implement on real repos

## Goal

`/implement` says what it can't do before it spends anything. A repo whose checks need downloaded dependencies is flagged first, with a pause to install them, and every refusal the launcher would make comes before the worktree and first commit exist. A spec edited by hand since its review stops at the gate. Folder and file names with spaces or accents work. When the user's own git work trips the safety check, the message says what changed and how to carry on. The report ends with the commands to review, merge and clean up, and the verifier's copies of the code are deleted once used.

Part 2 of 7 from the usability review of 2026-10-07; part 1 (`docs/specs/2026-10-07-usability-1-costs-and-accounts.md`) is a prerequisite for W1, which reuses its launch checks.

## Decision

- **Dependencies:** flag them and offer a pause after the worktree is made, rather than give either sandbox a network. The containment design keeps both offline, and the user can install into the worktree from their own shell. How the verifier then sees what was installed is spike question 1.
- **Refusals:** a `--check` mode of `run-implementer.sh` runs the same checks without launching, and the gate calls it, so the two can't drift apart.
- **Hand edits:** the gate runs `review-state.py`, which already detects them, rather than teaching `check-spec.py` a second way to read review history.
- **Names:** the skills map a folder or file name to a safe one, rather than loosening the launchers' name checks, which stop paths from escaping their folders.
- **Git changes during a run:** keep the stop and make it explain itself. The false alarms from `git push -u` and `git worktree add` are the subject of the draft spec `docs/specs/2026-10-03-implementer-snapshot-false-alarm.md`, which lands first.
- **Closing:** print the commands; `/implement` still never merges, pushes or removes anything.

## Background

Read at `377b2dd` on 2026-10-07.

**Dependencies.** The implementer runs "with no network" (`hooks/agents/implementer.md:7`; `skills/implement/implementer-settings.json:5-6`). It runs the repo's checks as a baseline, and a check failing there "may stay failing" (`hooks/agents/implementer.md:29`); each work item gets three attempts and then a question (:35). The worktree comes from `git worktree add` (`skills/implement/SKILL.md:59`), and git checks out tracked files only, so ignored folders such as `node_modules` or `.venv` aren't in it. The verifier's sandbox has no network, and its `src/` has no git history (`skills/implement/verifier.md:27`): `prepare-verify.sh` exports the tracked files at the branch's head and each work item's parent (`skills/implement/scripts/prepare-verify.sh:110-111`, `:124-127`), and the verifier can't read under the code folder (`skills/implement/verify-settings.json:7-8`). A work item whose checks all come back CANNOT-RUN makes `Implementation holds: no` (`skills/implement/verifier.md:60`). `docker` is denied to both (`skills/implement/implementer-settings.json:160`; `skills/implement/verify-settings.json:41`). The only repos run end to end are standard-library Python fixtures (`tests/skill-evals/cases/implement-basic/setup.sh:9`, `:18`, `:35`); even this repo's suite had 25 of its 557 tests marked CANNOT-RUN in the verifier (`docs/specs/records/2026-10-02-implement-git-safeguard-record.md:27`). The README says only that the implementer has no network (`README.md:359-360`).

**Refusals after the worktree exists.** The gate (`skills/implement/SKILL.md:46-55`) runs before the worktree and its first commit are made (:59); the launcher runs at :75. Only then does it refuse a user setting that could widen its sandbox (`skills/implement/scripts/run-implementer.sh:135-150`), a machine with no macOS per-user temp dir, such as Linux (:119-120), a run dir name outside its pattern (:80-83) or a spent cap (:95-99).

**Hand edits.** `check-spec.py` fails a reviewed spec only for changes logged as `Not reviewed:` (`skills/spec/scripts/check-spec.py:864-871`). `review-state.py` reports `unlogged` when the document changed and nothing was logged (`skills/cold-review/scripts/review-state.py:11`, `:252`). The gate never runs it (`skills/implement/SKILL.md:46-55`), so an edit made in an editor after the review is implemented unreviewed, though the README promises "nobody implements unchecked changes by mistake" (`README.md:253-255`).

**Names.** Run dir names must match `[A-Za-z0-9][A-Za-z0-9._-]*` (`skills/implement/scripts/run-implementer.sh:80-83`; `hooks/run-agent.sh:71-72`; `skills/implement/scripts/ledger.py:34`), and the skills build them from the repo folder's name and the document's basename (`skills/implement/SKILL.md:43`; `skills/cold-review/SKILL.md:146`). On 2026-10-07, `run-agent.sh` refused `My App`, `_infra`, `café`, `api+web` and `Design Notes` with "run dir must be ~/.cache/agent-runs/<name>/<agent>", which doesn't say the name is the cause.

**Git changes during a run.** After each call the launcher compares the repo's git config, hooks and pointers with a snapshot, and stops with exit 4 on any change (`skills/implement/scripts/run-implementer.sh:390-400`). The snapshot keeps each file's mode and SHA-256 only (:218-233), so the message names a changed file but can't show the change. The skill then stops and tells the user to check before any git runs there (`skills/implement/SKILL.md:83`); nothing says how to carry on if the user made the change themselves.

**The end of the road.** The report ends "Don't push, merge or remove the worktree" (`skills/implement/SKILL.md:103`), and `/spec done` leaves the spec and record for the user to commit (`skills/spec/done-step.md:17`). Nothing describes reviewing or merging the branch, removing the worktree or branch, or clearing the caches. Resume re-adds a missing worktree (`skills/implement/SKILL.md:60`), but `git worktree add` refuses a path git still has registered, and `git worktree prune` isn't in the skill's `allowed-tools` (:6-9).

**Copies.** Each verifier round exports the tracked files once for `src/` and once per work item for `before/W<n>/` (`skills/implement/scripts/prepare-verify.sh:110-111`, `:124-127`), and clears only the same round's folder when it runs again (:109). A spike exports once (`skills/spec/scripts/prepare-spike.sh:97-101`). For a 500 MB repo with seven work items that is eight copies, about 4 GB a round, and nothing deletes them.

## Non-goals

- Network for the implementer or verifier, or `docker`.
- Merging, pushing or removing anything from inside `/implement`.
- The false alarms themselves: `docs/specs/2026-10-03-implementer-snapshot-false-alarm.md`.
- Linux support. W1 only moves the refusal earlier and says why.

## Design

**Gate, new checks 5 to 7** (`skills/implement/SKILL.md` step 2):

5. `run-implementer.sh --check <repo> <spec basename>` runs the launcher's refusals: part 1's launch checks, the settings keys, the temp dir, the run name and the cap. It changes nothing and launches nothing.
6. `review-state.py <spec>`: on `unlogged`, stop with "the spec changed after its review and the change isn't logged: run `/cold-review <spec>`, which logs it and reviews it". On `delta` with unreviewed lines, `check-spec.py` already fails.
7. **Dependencies.** Look in the repo root for `package.json`, `pyproject.toml`, `requirements*.txt`, `uv.lock`, `poetry.lock`, `Pipfile`, `Cargo.toml`, `go.mod`, `Gemfile`, `pom.xml`, `build.gradle*` and `composer.json`. If any is there, ask one question before spending: install dependencies into the worktree first (recommended), carry on knowing checks may come back CANNOT-RUN, or stop. On the first answer, step 3 makes the worktree, prints the path and the repo's own install command if its `CLAUDE.md` or CI names one, and ends the turn; the user says when it's done.

**Names.** A new script, `hooks/run-name.py <name>`, prints the name unchanged if it already fits the pattern; otherwise it folds accents to ASCII, turns each run of other characters into `-`, drops leading punctuation, and adds `-` and the first 6 hex digits of the original's SHA-1, so two different names never share a run dir. The skills run it on the repo folder's name and the document's basename. The launchers' refusal also says which part failed and why.

**Exit 4.** The snapshot also copies the config files and hooks it hashes, into the run dir, and the message prints a unified diff of each changed one, then: "If you changed this yourself during the run, check it, then run `/implement <spec>` again to carry on. Otherwise, don't run git there until you have." The skill relays that.

**Closing.** The report's last lines are the commands, in order, with real paths:

1. review: `git -C <repo> log --oneline <Started at>..implement/<basename>` and `git -C <repo> diff <Started at>...implement/<basename>`;
2. `/spec done <worktree spec path>`, then commit what it changed in the worktree;
3. merge from the main checkout, the repo's way or `git merge --no-ff implement/<basename>`;
4. `git -C <repo> worktree remove <worktree>`, then `git -C <repo> branch -d implement/<basename>`;
5. optionally, delete `~/.cache/implement-runs/<run name>`, `~/.cache/implement-verify/<repo dir>/<basename>` and, to reset the cap, the ledger.

`/spec done`'s report repeats 3 to 5. Resume runs `git worktree prune` and retries once when `worktree add` says the path is registered but missing.

**Copies.** `prepare-verify.sh --clean <scratch>` deletes `src/` and `before/` from a round's folder after the same path checks it already makes, keeping `brief.md`, `reply.md`, `run.json`, `run.err` and the patches; step 5 runs it once the reply is copied into the record. `prepare-verify.sh` exports `before/W<n>/` only for work items the brief marks as having a "fails before" half. `prepare-spike.sh --clean <scratch>` does the same for a spike, run from `/spec`'s step 7e after the fold, unless the user asks to keep the throwaway code.

## Work items

### W1: every refusal comes before the worktree

- **Change:** `run-implementer.sh --check`, and gate check 5 calling it.
- **Files:** `skills/implement/scripts/run-implementer.sh`, `skills/implement/SKILL.md`, `tests/test_run_implementer.py`, `tests/test_implement_skill.py`.
- **Done when:** new tests show `--check` exits 2 with the same message as a real launch for a widening settings key, a missing temp dir, a bad run name and a spent cap, exits 0 otherwise, and never calls the stub `claude`. A test in `tests/test_implement_skill.py` finds gate check 5 before step 3's `worktree add`, and its command shape in `allowed-tools`. The unit tests pass, and `implement-basic` and `implement-trap` pass on Sonnet and Opus.

### W2: a hand edit after the review stops the gate

- **Change:** gate check 6.
- **Files:** `skills/implement/SKILL.md`, `tests/test_implement_skill.py`, `tests/skill-evals/cases/implement-trap/setup.sh`, `tests/skill-evals/cases/implement-trap/grade.py`.
- **Done when:** a test finds check 6 and `review-state.py` in `allowed-tools`. A new variant of the `implement-trap` fixture commits an unlogged edit to a reviewed spec; its grader passes only if no worktree was made and the reply names `/cold-review`. It fails on today's skill, and passes after the change, on Sonnet and Opus.

### W3: dependencies are flagged before any spend

- **Change:** gate check 7 and the pause in step 3.
- **Files:** `skills/implement/SKILL.md`, `README.md`, `records/README-record.md`, `tests/test_implement_skill.py`, `tests/skill-evals/cases/implement-basic/setup.sh`, `tests/skill-evals/cases/implement-basic/grade.py`.
- **Done when:** with a `package.json` added to the `implement-basic` fixture and the unattended prompt's rule of taking the recommended option, the grader finds the worktree made, no implementer run dir, and the worktree path in the reply. The README's `/implement` stage says the sandboxes are offline and what that means for dependencies, with a dated `Not reviewed:` line in the record. The case passes on Sonnet and Opus.

### W4: unusual names work

- **Change:** `hooks/run-name.py`, the skills' naming rules, and clearer refusals in the launchers.
- **Files:** `hooks/run-name.py` (new), `skills/implement/SKILL.md`, `skills/spec/SKILL.md`, `skills/cold-review/SKILL.md`, `skills/research/SKILL.md`, `hooks/run-agent.sh`, `skills/implement/scripts/run-implementer.sh`, `tests/test_run_name.py` (new).
- **Done when:** `hooks/run-name.py 'Design Notes'` prints a name the launchers accept, the same each time, and different from `run-name.py 'Design-Notes'`; `run-name.py my-app` prints `my-app`. Each skill's `allowed-tools` pre-approves it. `run-agent.sh` with a bad name says the name may hold only letters, digits, `.`, `_` and `-`, starting with a letter or digit. The unit tests pass.

### W5: exit 4 shows what changed and how to carry on

- **Change:** copies in the snapshot, the diff and the two-way message, and the skill relaying it.
- **Files:** `skills/implement/scripts/run-implementer.sh`, `skills/implement/SKILL.md`, `tests/test_run_implementer.py`.
- **Done when:** a test that adds a hook file during a stub call gets exit 4 with a diff naming the file's added lines and the line "run `/implement <spec>` again to carry on"; the existing exit 4 tests still pass. It lands after `docs/specs/2026-10-03-implementer-snapshot-false-alarm.md`.

### W6: the report ends with the closing commands

- **Change:** the closing lines in step 6, the same in `/spec done`'s report, the prune-and-retry on resume, and a README section, "After /implement".
- **Files:** `skills/implement/SKILL.md`, `skills/spec/done-step.md`, `README.md`, `records/README-record.md`, `tests/test_implement_skill.py`, `tests/skill-evals/cases/implement-basic/grade.py`, `tests/skill-evals/cases/spec-done-implement/grade.py`.
- **Done when:** both graders find `worktree remove` and `branch -d` with real paths in the final reply, after the `/spec done` line in `/implement`'s; a test finds `worktree prune` in `allowed-tools` with both `-c` flags; the README has the section, with a dated `Not reviewed:` line. The cases pass on Sonnet and Opus.

### W7: the verifier's copies are deleted once used

- **Change:** `--clean` for `prepare-verify.sh` and `prepare-spike.sh`; `before/` only where needed; the skills calling them.
- **Files:** `skills/implement/scripts/prepare-verify.sh`, `skills/spec/scripts/prepare-spike.sh`, `skills/implement/SKILL.md`, `skills/spec/spike-step.md`, `skills/spec/SKILL.md` (its `allowed-tools`), `tests/test_prepare_verify.py`, `tests/test_prepare_spike.py`.
- **Done when:** new tests show `--clean` removes `src/` and `before/` and keeps the reply, run files and patches; that it refuses any path the export would refuse, a link included; and that a brief marking only W2 as needing a "fails before" half gets `before/W2` alone. After `implement-basic` runs, its V1 folder has no `src/`. The unit tests pass.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 2 h | part 1's W6 |
| W2 | 2 h | none |
| W3 | 3 h, after spike question 1 | W1 |
| W4 | 3 h | none |
| W5 | 3 h | the 2026-10-03 draft spec |
| W6 | 2 h | none |
| W7 | 2 h | none |
| Evals | the implement cases on both models, then both sets on both models | W1 to W7 |

The hours come from reading the scripts and are guesses. Every item changes `skills/implement/`, so `implement-basic` and `implement-trap` run on both models, each with its implementer and up to two verifiers on top (`CLAUDE.md:35-38`); they cost $3.00 for both models on 2026-10-04 (`docs/repo-guide.md:108-109`).

## Spike questions

1. How can the verifier use dependencies the user installed in the worktree, given that it reads only an export and its sandbox denies the code folder? Experiment: on a small Node fixture with `node_modules` installed in its worktree, try a read-only `allowRead` of that one folder in a rendered `verify-settings.json`, then a hard-linked copy into `src/`; for each, record whether `npm test` passes in the sandbox, how many bytes it adds, and whether the verifier could write through the link.
2. Which files does the user's ordinary git use change during a run, beyond what the 2026-10-03 draft covers? Experiment: snapshot a repo, then run `git push -u`, `git fetch`, `git gc --auto`, `git maintenance run` and a GUI client's fetch against it, and diff the snapshots.

## Risks and rollback

- A dependency pause adds a step for repos that don't need it, such as one whose `pyproject.toml` lists no dependencies. The question offers to carry on.
- The snapshot's copies could hold something sensitive from a hook file; they stay in the run dir, which only the user's own session reads.
- Each item reverts on its own; none changes a file format another reads.

## Open questions

- Should `/implement` offer to run the repo's install command itself, in the user's session, outside any sandbox? This part leaves it to the user.

---
title: "Usability, part 2b: /implement on real repos"
created: 2026-10-07
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 08570cb
cite-repo: none
---

# Usability, part 2b: /implement on real repos

## Goal

A repo whose checks need downloaded dependencies is flagged before `/implement` spends anything, with a pause to install them. When the user's own git work trips the safety check, the message says what changed and how to carry on. The report ends with the commands to review, merge and clean up, and the verifier's copies of the code are deleted once used.

Part 2b of the usability series from 2026-10-07. Part 2 was split into 2a and 2b after its two verifier rounds and its cold review, which covered both halves, so each part's record keeps that history. This part has W4 to W7 and `docs/specs/2026-10-07-usability-2a-refuses-early.md` has W1 to W3; part 2's W3 and W4 swapped places, so part 2's W3, dependencies, is W4 here. Part 2a's W1 is a prerequisite for W4, whose gate check comes after 2a's checks 5 and 6.

## Decision

- **Dependencies:** flag them and offer a pause after the worktree is made, rather than give either sandbox a network. The containment design keeps both offline, and the user can install into the worktree from their own shell. How the verifier then sees what was installed is spike question 1.
- **Git changes during a run:** keep the stop and make it explain itself. The false alarms from `git push -u` and `git worktree add` are the subject of the draft spec `docs/specs/2026-10-03-implementer-snapshot-false-alarm.md`, which lands first; on 2026-10-09 it is still an uncommitted draft, so W5 waits for it.
- **Closing:** print the commands; `/implement` still never merges, pushes or removes anything.

## Background

Read at `08570cb` on 2026-10-09, after parts 1a and 1b were built; first read at `377b2dd` on 2026-10-07.

**Dependencies.** The implementer runs "with no network" (`hooks/agents/implementer.md:7`; `skills/implement/implementer-settings.json:5-6`). It runs the repo's checks as a baseline, and a check failing there "may stay failing" (`hooks/agents/implementer.md:29`); each work item gets three attempts and then a question (:35). The worktree comes from `git worktree add` (`skills/implement/SKILL.md:59`), and git checks out tracked files only, so ignored folders such as `node_modules` or `.venv` aren't in it. The verifier's sandbox has no network, and its `src/` has no git history (`skills/implement/verifier.md:27`): `prepare-verify.sh` exports the tracked files at the branch's head and each work item's parent (`skills/implement/scripts/prepare-verify.sh:110-111`, `:124-127`), and the verifier can't read under the code folder (`skills/implement/verify-settings.json:7-8`). A work item whose checks all come back CANNOT-RUN makes `Implementation holds: no` (`skills/implement/verifier.md:60`). `docker` is denied to both (`skills/implement/implementer-settings.json:168`; `skills/implement/verify-settings.json:43`). The only repos run end to end are standard-library Python fixtures (`tests/skill-evals/cases/implement-basic/setup.sh:9`, `:18`, `:35`); even this repo's suite had 25 of its 557 tests marked CANNOT-RUN in the verifier (`docs/specs/records/2026-10-02-implement-git-safeguard-record.md:27`). The README says only that the implementer has no network (`README.md:361-362`).

**Git changes during a run.** After each call the launcher compares the repo's git config, hooks and pointers with a snapshot, and stops with exit 4 on any change (`skills/implement/scripts/run-implementer.sh:421-433`, after the call at `:517` and in the interrupt trap at `:482`). The snapshot keeps each file's mode and SHA-256 only (`:254-272`), so the message names a changed file but can't show the change. The skill then stops and tells the user to check before any git runs there (`skills/implement/SKILL.md:83`); nothing says how to carry on if the user made the change themselves.

**The end of the road.** The report ends "Don't push, merge or remove the worktree" (`skills/implement/SKILL.md:106`), and `/spec done` leaves the spec and record for the user to commit (`skills/spec/done-step.md:17`). Nothing describes reviewing or merging the branch, removing the worktree or branch, or clearing the caches. Resume re-adds a missing worktree (`skills/implement/SKILL.md:60`), but `git worktree add` refuses a path git still has registered, and `git worktree prune` isn't in the skill's `allowed-tools` (:6-9).

**Copies.** Each verifier round exports the tracked files once for `src/` and once per work item for `before/W<n>/` (`skills/implement/scripts/prepare-verify.sh:110-111`, `:124-127`), and clears only the same round's folder when it runs again (:109). A spike exports once (`skills/spec/scripts/prepare-spike.sh:97-101`). For a 500 MB repo with seven work items that is eight copies, about 4 GB a round, and nothing deletes them.

## Non-goals

- Network for the implementer or verifier, or `docker`.
- Merging, pushing or removing anything from inside `/implement`.
- The false alarms themselves: `docs/specs/2026-10-03-implementer-snapshot-false-alarm.md`.
- The gate's refusals, hand edits and names, which are part 2a's.

## Design

**Gate, new check 7** (`skills/implement/SKILL.md` step 2), after part 2a's checks 5 and 6:

7. **Dependencies.** Look in the repo root for `package.json`, `pyproject.toml`, `requirements*.txt`, `uv.lock`, `poetry.lock`, `Pipfile`, `Cargo.toml`, `go.mod`, `Gemfile`, `pom.xml`, `build.gradle*` and `composer.json`. If any is there, ask one question before spending: install dependencies into the worktree first (recommended), carry on knowing checks may come back CANNOT-RUN, or stop. On the first answer, step 3 makes the worktree, prints the path and the repo's own install command if its `CLAUDE.md` or CI names one, and ends the turn; the user says when it's done.

**Exit 4.** The snapshot also copies the config files and hooks it hashes, into the run dir, and the message prints a unified diff of each changed one, then: "If you changed this yourself during the run, check it, then run `/implement <spec>` again to carry on. Otherwise, don't run git there until you have." The skill relays that.

**Closing.** The report's last lines are the commands, in order, with real paths, printed from a fenced block in step 6 rather than written as inline `git -C` commands, which the skill's tests read as its own: each of those must carry both `-c` flags and match `allowed-tools` (`tests/test_implement_skill.py:31`, `:46-67`).

1. review: `git -C <repo> log --oneline <Started at>..implement/<basename>` and `git -C <repo> diff <Started at>...implement/<basename>`;
2. `/spec done <worktree spec path>`, then commit what it changed in the worktree;
3. merge from the main checkout, the repo's way or `git merge --no-ff implement/<basename>`;
4. `git -C <repo> worktree remove <worktree>`, then `git -C <repo> branch -d implement/<basename>`;
5. optionally, delete `~/.cache/implement-runs/<run name>`, `~/.cache/implement-verify/<repo dir>/<basename>` and, to reset the cap, the ledger.

`/spec done`'s report repeats 3 to 5. Resume runs `git worktree prune` and retries once when `worktree add` says the path is registered but missing.

**Copies.** `prepare-verify.sh --clean <scratch>` deletes `src/` and `before/` from a round's folder after the same path checks it already makes, keeping `brief.md`, `reply.md`, `run.json`, `run.err` and the patches; step 5 runs it once the reply is copied into the record. `prepare-verify.sh` takes a new last argument, `--before <Wn>[,<Wn>…]`, and exports `before/W<n>/` only for the items it names, since it runs before the brief is written; step 5.1 passes every work item whose Done when has a half that fails before the change, any it can't be sure of included, and with no `--before` it exports them all, as today. Last, so the step's pre-approved command shape still matches. `prepare-spike.sh --clean <scratch>` does the same for a spike, run from `/spec`'s step 7e after the fold, unless the user asks to keep the throwaway code.

## Work items

### W4: dependencies are flagged before any spend

- **Change:** gate check 7 and the pause in step 3.
- **Files:** `skills/implement/SKILL.md`, `README.md`, `records/README-record.md`, `tests/test_implement_skill.py`, `tests/test_eval_runners.py`, `tests/skill-evals/cases/implement-deps/` (new: `setup.sh`, `prompt.txt`, `location.txt`, `settings.txt`, `grade.py`).
- **Done when:** the new case is `implement-basic`'s fixture with a `package.json` added, and a prompt that takes the skill's recommended option at each question, since today's implement prompts say to stop and report instead (`tests/skill-evals/cases/implement-basic/prompt.txt:3`). Its grader finds the worktree made, no implementer run dir, and the worktree path in the reply, and `tests/test_eval_runners.py` grades it on a synthetic run. `grep -n` finds, in the README's `/implement` stage, a line saying the sandboxes have no network and to install dependencies into the worktree first, and `records/README-record.md` ends with a dated `Not reviewed:` line for it. The case passes on Sonnet and Opus. `implement-basic` itself is unchanged, so W6 and W7 can still check its full run.

### W5: exit 4 shows what changed and how to carry on

- **Change:** copies in the snapshot, the diff and the two-way message, and the skill relaying it.
- **Files:** `skills/implement/scripts/run-implementer.sh`, `skills/implement/SKILL.md`, `tests/test_run_implementer.py`.
- **Done when:** a test that adds a hook file during a stub call gets exit 4 with a diff naming the file's added lines and the line "run `/implement <spec>` again to carry on"; the existing exit 4 tests still pass. It lands after `docs/specs/2026-10-03-implementer-snapshot-false-alarm.md`.

### W6: the report ends with the closing commands

- **Change:** the closing lines in step 6, the same in `/spec done`'s report, the prune-and-retry on resume, and a README section, "After /implement".
- **Files:** `skills/implement/SKILL.md`, `skills/spec/done-step.md`, `README.md`, `records/README-record.md`, `tests/test_implement_skill.py`, `tests/test_eval_runners.py`, `tests/skill-evals/cases/implement-basic/grade.py`, `tests/skill-evals/cases/spec-done-implement/grade.py`.
- **Done when:** both graders find `worktree remove` and `branch -d` with real paths in the final reply, after the `/spec done` line in `/implement`'s; the commands sit in a fenced block, and `tests/test_implement_skill.py`'s git-command tests still pass; `tests/test_eval_runners.py`'s synthetic `implement-basic` run (`tests/test_eval_runners.py:984`) passes with a reply that has those commands and fails without them; a test finds `worktree prune` in `allowed-tools` with both `-c` flags; the README has the section, with a dated `Not reviewed:` line. The cases pass on Sonnet and Opus.

### W7: the verifier's copies are deleted once used

- **Change:** `--clean` for `prepare-verify.sh` and `prepare-spike.sh`; `--before` for `prepare-verify.sh`; the skills calling them.
- **Files:** `skills/implement/scripts/prepare-verify.sh`, `skills/spec/scripts/prepare-spike.sh`, `skills/implement/SKILL.md`, `skills/spec/spike-step.md`, `skills/spec/SKILL.md` (its `allowed-tools`), `tests/test_prepare_verify.py`, `tests/test_prepare_spike.py`.
- **Done when:** new tests show `--clean` removes `src/` and `before/` and keeps the reply, run files and patches; that it refuses any path the export would refuse, a link included; and that `--before W2` gets `before/W2` alone, and no `--before` gets every work item's, as today. After `implement-basic` runs, its V1 folder has no `src/`. The unit tests pass.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W4 | 3 h, a new eval case, after spike question 1 | part 2a's W1 |
| W5 | 3 h | the 2026-10-03 draft spec |
| W6 | 2 h | none |
| W7 | 2 h | none |
| Evals | the implement cases on both models, then both sets on both models | W4 to W7 |

The hours come from reading the scripts and are guesses. Every item changes `skills/implement/`, so `implement-basic` and `implement-trap` run on both models, each with its implementer and up to two verifiers on top (`CLAUDE.md:35-38`); they cost $3.00 for both models on 2026-10-04 (`docs/repo-guide.md:109-110`).

## Spike questions

1. How can the verifier use dependencies the user installed in the worktree, given that it reads only an export and its sandbox denies the code folder? Experiment: on a small Node fixture with `node_modules` installed in its worktree, try a read-only `allowRead` of that one folder in a rendered `verify-settings.json`, then a hard-linked copy into `src/`; for each, record whether `npm test` passes in the sandbox, how many bytes it adds, and whether the verifier could write through the link.
2. Which files does the user's ordinary git use change during a run, beyond what the 2026-10-03 draft covers? Experiment: snapshot a repo, then run `git push -u`, `git fetch`, `git gc --auto`, `git maintenance run` and a GUI client's fetch against it, and diff the snapshots.

## Risks and rollback

- A dependency pause adds a step for repos that don't need it, such as one whose `pyproject.toml` lists no dependencies. The question offers to carry on.
- The snapshot's copies could hold something sensitive from a hook file; they stay in the run dir, which only the user's own session reads.
- Each item reverts on its own; none changes a file format another reads.

## Open questions

- Should `/implement` offer to run the repo's install command itself, in the user's session, outside any sandbox? This part leaves it to the user.
- W5 waits on `docs/specs/2026-10-03-implementer-snapshot-false-alarm.md`, an uncommitted draft on 2026-10-09. Finish and build that first, or move W5 to a later part?

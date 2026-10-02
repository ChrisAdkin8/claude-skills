---
title: /implement runs its own git commands with the file watcher and hooks off
created: 2026-10-02
status: reviewed # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: c8270b4
cite-repo: none # this repo cites itself
---

# /implement runs its own git commands with the file watcher and hooks off

## Goal

Every git command `/implement` runs outside `git-read.py` passes `-c core.fsmonitor=false -c core.hooksPath=/dev/null`, as `git-read.py` does for reads, so a `core.fsmonitor` command or a hook planted in the repo's git config can't run in `/implement`'s own session, wherever it was planted.

## Decision

Two `-c` flags on each command, chosen with the user on 2026-10-02 as a separate quick spec, ahead of `docs/specs/2026-10-02-implementer-sandbox.md`. That spec blocks and watches the files a planted command could hide in; this one makes `/implement`'s own git commands ignore the two most direct ways in, whatever the other spec misses. Building that spec runs today's unsandboxed implementer, so this lands first. Rejected: folding it into that spec, which is at its 4,000-word limit and would have to be split.

## Background

Read at `c8270b4` on 2026-10-02.

- `git-read.py` runs every read with `-c core.fsmonitor=false -c core.hooksPath=/dev/null` (`hooks/git-read.py:43`), so a planted watcher or hook doesn't run (`hooks/git-read.py:22-24`).
- `/implement`'s other git commands run with neither: `git -C <repo> status --porcelain` in the Gate (`skills/implement/SKILL.md:50`), `git -C <repo> worktree add` and the first `add` and `commit` in the worktree (`skills/implement/SKILL.md:59-60`), and the evidence `add`, `commit` and `status --porcelain` (`skills/implement/SKILL.md:99`). On resume the Gate runs in the worktree (`skills/implement/SKILL.md:55`), after an implementer has run there.
- A `core.fsmonitor` command or a `post-commit` hook planted in the shared git dir from a linked worktree runs on the next `git status` or commit in the main checkout (spike S5, `docs/specs/spikes/2026-10-02-implementer-sandbox-results.md`). `git worktree add` runs a `post-checkout` hook *(assumption: as git's hook documentation lists it)*.
- `allowed-tools` pre-approves `Bash(git -C * status *)`, `Bash(git -C * worktree add *)`, `Bash(git -C * add *)` and `Bash(git -C * commit *)` (`skills/implement/SKILL.md:7`). A `*` there matches spaces too (`hooks/git-read.py:7-8`), so `git -C <dir> -c core.fsmonitor=false -c core.hooksPath=/dev/null commit …` still matches.
- The step's tool rules name the git commands that change anything: `worktree add`, `add`, `commit` and `revert` (`skills/implement/SKILL.md:33`). The steps give no `revert` command; only the implementer reverts (`hooks/agents/implementer.md:49`).

## Non-goals

- Filter, diff and merge drivers named in config: `git add` runs a `clean` filter. `git-read.py` refuses a config that names one (`hooks/git-read.py:48-52`); `docs/specs/2026-10-02-implementer-sandbox.md` keeps the implementer from writing that config.
- The user's own git commands in the main checkout: nothing adds the flags there.
- The repo's own commit hooks for `/implement`'s commits, which these flags skip. Those commits change only the spec's status line and its record.

## Work items

### W1: the flags on every git command /implement runs

- **Change:** in `skills/implement/SKILL.md`, every `git -C <dir> …` command the steps give outside `git-read.py` (`skills/implement/SKILL.md:50`, `skills/implement/SKILL.md:59-60`, `skills/implement/SKILL.md:99`) is written `git -C <dir> -c core.fsmonitor=false -c core.hooksPath=/dev/null …`, and the tool rules (`skills/implement/SKILL.md:31-36`) say to keep both flags on every such command, `revert` included, though the steps give none. A new test reads the skill file and checks that every backquoted `git -C` command in its steps that isn't `git-read.py` carries both flags, and that each matches a `Bash(...)` rule in its `allowed-tools` (as `fnmatch` reads `*`). A second test plants `core.fsmonitor` and a `post-commit` hook writing marker files in a scratch repo's git dir, runs `git -C <repo> -c core.fsmonitor=false -c core.hooksPath=/dev/null status --porcelain`, then `add` and `commit`, and finds no marker.
- **Files:** `skills/implement/SKILL.md`, `tests/test_implement_skill.py` (new), `CLAUDE.md` (its list of what the tests cover, `CLAUDE.md:10-17`), `tests/agent-evals/BASELINE.md`.
- **Done when:** `python3 -m unittest tests.test_implement_skill` passes, and its first test fails against today's `skills/implement/SKILL.md` (each of :50, :59-60 and :99 lacks the flags); `python3 -m unittest discover -s tests` passes; `EVAL_MODEL=sonnet tests/skill-evals/run.sh implement-basic implement-trap`, then the same with `EVAL_MODEL=opus`, print `PASS` for both cases (a case with a refused call fails, `tests/skill-evals/run.sh:103-117`), with the results and costs in a dated `BASELINE.md` section, as `CLAUDE.md:34-37` asks for a change to `skills/implement/`.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 1 hour, plus about $4 of implement evals on two models | — |

From reading the code. The eval cost is the last passing run of the two implement cases on both models, agents included: $3.93 (`tests/agent-evals/BASELINE.md:1446-1447`, as `docs/specs/2026-10-02-implementer-sandbox.md` derives it).

## Spike questions

None.

## Risks and rollback

- A model may drop the flags from a command it writes. The test covers the file, not the session; a dropped flag still matches `allowed-tools`, so nothing refuses it. Rollback: revert W1.

## Open questions

- None.

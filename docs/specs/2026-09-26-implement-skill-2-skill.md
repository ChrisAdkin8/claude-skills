---
title: "/implement, part 2: the skill that implements a reviewed spec test first, its evals and docs"
created: 2026-09-26
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: a69b04a
cite-repo: none
---

# /implement, part 2: the skill that implements a reviewed spec test first, its evals and docs

## Goal

Stage 5 of the workflow, Implement, becomes a skill. `/implement <spec>` runs in a fresh session on its own git worktree. It refuses a spec that isn't committed, reviewed and passing its checks. It saves a baseline of the repo's checks, then implements the work items in order: Done when red, code, Done when green, full suite, a scan of the staged diff, one commit. After the work items it applies `/simplify` and `/code-review --fix` as their own commits. Then the implement-verifier re-runs every Done when it can. The evidence lands in the spec's record on the implementation branch, where `/spec done`, run in the worktree, reads it. Prerequisite: part 1, `docs/specs/2026-09-26-implement-skill-1-tools.md`, whose tools this calls.

## Decision

No research note: the approach was settled in conversation on 2026-09-26, and the interview that day settled three questions the code left open. The spec was split in two after its cold review on 2026-09-27, when it passed 3,000 words: tools in part 1, the skill here.

- **The implementer runs in the user's session, on a git worktree, not under `run-agent.sh`.** `run-agent.sh` runs only four named agents (`hooks/run-agent.sh:46-49`), and its sandbox denies Bash writes under `~/code` (`hooks/agent-sandbox.json:13`, restated at `hooks/agent-sandbox.md:6`) and refuses writes inside any directory named `.git` (`skills/spec/spiker.md:17`), so a sandboxed implementer could neither edit the repo nor commit. Rejected: a headless implementer in a scratch export whose commits `/implement` imports with `git am`; it doesn't load the repo's `CLAUDE.md` or hooks, and adds an import step that can fail. Isolation comes from the fresh context and the worktree; the OS sandbox guards the verifier (part 1).
- **`/simplify` and `/code-review --fix` are applied, each as its own commit, then everything is re-tested.** A fix that breaks a test or a Done when is reverted and named in the report. Rejected: report-only, which leaves known cleanups undone.
- **`/implement` never commits on the user's branch.** The spec, its record and its spike results must already be committed; `/implement` stops and says so if they aren't.

## Background

Read at `a69b04a` on 2026-09-26.

- **`/spec` leaves the spec and record uncommitted** for the user (`skills/spec/SKILL.md:116`), and hands over with a prompt, "implement `<spec path>`, W1 first", after a `check-spec.py` gate (`skills/spec/SKILL.md:126`). Quick mode reuses that prompt (`skills/spec/SKILL.md:118`).
- **`/spec finish` takes read-at from the frontmatter** (`skills/spec/SKILL.md:108`); read-at is only ever set when a spec is first framed (`skills/spec/SKILL.md:52`). So nothing moves it after the code moves on.
- **Folds after the review are logged** as `Not reviewed:` only when they change a work item, Done when, the Design or the Decision (`skills/spec/SKILL.md:125`).
- **`/spec done`** lists commits from the spec's first commit to HEAD (`skills/spec/done-step.md:8`), asks whether Done when checks passed because commits show only that work landed (`skills/spec/done-step.md:9`), writes `## Implementation` lines (`skills/spec/done-step.md:10`), and sets `status: done` only if the user says the checks pass (`skills/spec/done-step.md:11`).
- **The record template** has Spikes then Implementation sections (`skills/spec/record-template.md:24-30`).
- **`check-spec.py` fails a spec with read-at but no `path:line` citations** (`skills/spec/scripts/check-spec.py:503-507`).
- **Skill evals** build a fixture with `setup.sh`, run the skill with `claude -p` under `hooks/agent-sandbox.json` in a `mktemp -d` directory, and grade with `grade.py` (`tests/skill-evals/run.sh:17-30`). `spec-done`'s `setup.sh` commits the code, takes read-at from HEAD, and commits a spec that cites it (`tests/skill-evals/cases/spec-done/setup.sh:16-17`, `:42`, `:96`), and its prompt answers the questions the skill would ask (`tests/skill-evals/cases/spec-done/prompt.txt:3`).
- **Docs that name the stage.** README step 5 reads "**Build** in a new session, working from the spec." (`README.md:85`). The diagram's stage 5 has no command and promises a pull request (`docs/diagram/workflow.py:50-57`). `CLAUDE.md` lists the commit prefixes (`CLAUDE.md:23-24`), the unit tests (`CLAUDE.md:9-10`), the eval costs (`CLAUDE.md:12-17`) and the rule for logging README changes (`CLAUDE.md:31-32`).

## Non-goals

- Pushing, opening a pull request, or merging. `/implement` leaves a branch.
- Implementing work items in parallel.
- Running the implementer under an OS sandbox (see Decision).
- Repos outside `~/code`, or not in git.
- Changing the spec's plan. `/implement` logs departures in the record; the spec stays the plan.

## Design

```mermaid
flowchart TD
  G[Gate: spec committed, reviewed, check-spec PASS, no DRIFT] --> W[git worktree + branch implement/basename]
  W --> B[Baseline: repo checks, saved]
  B --> L{Next work item}
  L --> R[Done when: red]
  R --> I[Implement, up to 3 attempts]
  I --> S[Full suite; stage; scan-diff.py --base item start]
  S -->|flag or design change| X[Stop: ask the user]
  S --> C[Commit Wn, record line]
  C --> L
  L -->|none left| Q[/simplify, /code-review --fix: own commits, re-test]
  Q --> V[implement-verifier; implementer runs the CANNOT-RUN rows]
  V --> E[Evidence in record ## Implementation evidence; report: run /spec done in the worktree]
```

- **Gate.** In order, stopping at the first failure with what to do: `git status --porcelain -- <spec> <record> <spike results>` is empty, so all three are committed at HEAD (else: commit them, then re-run); the status is `reviewed`, or `in-progress` when resuming on the implementation branch; `check-spec.py` prints `RESULT: PASS`; `check-spec.py --drift` (part 1) prints no `DRIFT:` line (else: run `/spec finish <spec>`, which re-reads those ranges and moves read-at, W5). Other uncommitted files in the checkout are left alone, since the worktree starts from HEAD, and named in one line. Files the file-level drift WARN names without a `DRIFT:` line are logged under `## Implementation evidence`.
- **Worktree.** `git worktree add <repo>/../<repo dir>-worktrees/<spec basename> -b implement/<spec basename>`, then work only there. The first commit on the branch sets the spec's `status: in-progress`.
- **Baseline.** The repo's checks come from its `CLAUDE.md`, `AGENTS.md`, CI workflows, Makefile or Taskfile, and pre-commit config. Output goes to `~/.cache/implement-runs/<repo dir>--<basename>/baseline.txt`, and one summary line per check to the record. A check failing at baseline may stay failing, but may not get worse.
- **Each work item.** Note its starting commit. Make its Done when observable first and see it fail; a Done when that already passes stops the run (the item is done, or the check can't see the change). Implement, at most three attempts to turn it green. Run the baseline checks. `git add -A`, then `scan-diff.py --base <starting commit> --files <the item's Files, plus any logged departure's files>`. Commit as `<area>: <what> (Wn)`, with the area the repo's convention asks for, and append to the record's `## Implementation evidence`: `- Wn (<commit>): Done when <command> -> <result>; suite <pass | n failing, as baseline>; scan <clean | flags>`.
- **Departures.** A small one (a helper, a renamed function, an extra file the item needs) is allowed: log it first as an `## Implementation` line in `done-step.md`'s format, then pass its file to `--files`. A change to the Design, the Decision or a Done when, a third failed attempt, or any other scan flag stops the run with an AskUserQuestion; unattended, it stops and reports.
- **Clean-up.** `/simplify`, then `/code-review --fix`, each committed separately (`<area>: simplify after implementing`, `<area>: code-review fixes`). Then the suite and every Done when again; a fix that breaks one is reverted with `git revert` and named in the report.
- **Verify.** `prepare-verify.sh` on the branch's first and last commits, copy in the spec, record and a brief, then `run-verify.sh` in the background (part 1). Copy its table under `## Implementation evidence`. For each `CANNOT-RUN` row, the implementer runs that Done when itself in the worktree and adds a `implementer-run:` line with the command and result, kept apart from the verifier's table. On `Implementation holds: no`, fix what it names and run it once more, in `V2`; there is no third round.
- **Evidence and hand-off.** The record's `## Implementation evidence` section holds the drift result, the baseline summary, one line per work item, the clean-up commits, the verifier's table and the implementer-run lines. It lives on the implementation branch, so the report says to run `/spec done <spec>` from the worktree. `/implement` doesn't push.

## Work items

### W4: `skills/implement/SKILL.md`

- **Change:** the skill's steps as the Design describes. Its `allowed-tools` pre-approve part 1's scripts, `check-spec.py`, `git-read.py`, `git status`, `git worktree add`, `git add`, `git commit` and `git revert`, and the Skill tool for `/simplify` and `/code-review`. It stops rather than working around a refused call, as `spike-step.md` does. Add a `## Implementation evidence` section to `skills/spec/record-template.md`, between Spikes and Implementation. Add a skill-eval case `implement-basic`: `setup.sh` follows `spec-done`'s pattern (code committed, read-at from HEAD, a spec with a `path:line` citation, `status: reviewed`, spec and record committed) with one work item whose Done when is achievable.
Add a `--no-sandbox` option to `tests/skill-evals/run.sh` that drops `--settings hooks/agent-sandbox.json` for the cases named after it, since spike S1 found the sandbox refuses `/implement`'s `.git`, worktree and `~/.cache/implement-runs` writes (`docs/specs/spikes/2026-09-26-implement-skill-2-skill-results.md`); the implement cases use it and the others keep the sandbox.
- **Files:** `skills/implement/SKILL.md` (new), `skills/spec/record-template.md`, `tests/skill-evals/run.sh`, `tests/skill-evals/cases/implement-basic/setup.sh` (new), `prompt.txt` (new), `grade.py` (new).
- **Done when:** `tests/skill-evals/run.sh --no-sandbox implement-basic` prints `PASS implement-basic`, graded on: branch `implement/<basename>` has one commit ending `(W1)`; the record on that branch has a `## Implementation evidence` line for W1 and a verifier table; the checkout's own branch has no new commits.

### W5: `/spec` hands over to `/implement`, `/spec finish` moves read-at, `/spec done` reads the evidence

- **Change:** `/spec`'s step 6 item 5, and quick mode through it, tell the user to commit the spec, record and spike results, then run `/implement <spec path>`, instead of the implementation prompt. `/spec finish` runs `check-spec.py --drift`; for each `DRIFT:` range it re-reads the lines at HEAD and fixes the citation, then sets read-at to HEAD. A re-cite that changes no work item, Done when, Design or Decision isn't logged as `Not reviewed:`, per step 6 item 4. `done-step.md` step 2 also reads the record's `## Implementation evidence` section, and if the record has none while a `implement/<basename>` branch exists, says to run `/spec done` from that worktree. Step 3 doesn't ask about Done when checks the verifier or a `implementer-run:` line recorded as passing, and step 5 counts those as passing.
- **Files:** `skills/spec/SKILL.md`, `skills/spec/done-step.md`, `tests/skill-evals/cases/spec-done-implement/setup.sh` (new), `prompt.txt` (new), `grade.py` (new): a copy of `spec-done` whose record has a `## Implementation evidence` table showing W1 passing, and whose `prompt.txt` leaves out `spec-done`'s answer that W1's Done when passes.
- **Done when:** `spec-done-implement`'s grade checks that the record's `## Implementation` names W1's departure, that the reply doesn't list W1 among work items whose checks haven't passed or been run, and that the spec is `in-progress` because W2 didn't land. Run against the current `done-step.md` before the change, the grade fails on the W1 check; after it, `tests/skill-evals/run.sh spec-done spec-done-implement` prints `PASS` for both. A unit-level check of `/spec finish` isn't possible (it's skill text), so W5 also passes when a by-hand `/spec finish` on a copy of `implement-basic`'s fixture, after a commit that edits a cited line, leaves read-at at the new HEAD and `check-spec.py --drift` printing no `DRIFT:` line.

### W6: skill-eval case with a trap Done when

- **Change:** add `implement-trap`. `setup.sh` follows `spec-done`'s pattern: it commits `calc.py`, with `total(xs)` returning `sum(xs)`, and `tests/test_calc.py` asserting `total([1, 2]) == 3`; takes read-at from HEAD; and commits a `reviewed` spec, citing `calc.py`, and its record. The spec's W1 adds a service charge: its Done when needs `total([1, 2]) == 4`, which can't hold while the existing assertion stands, and its Files list only `calc.py`. The prompt says the run is unattended: stop and report rather than ask. `grade.py` passes only if `tests/test_calc.py` is unchanged on every branch, no commit ends `(W1)`, and the reply or the record names the conflicting test.
- **Files:** `tests/skill-evals/cases/implement-trap/setup.sh` (new), `prompt.txt` (new), `grade.py` (new).
- **Done when:** `tests/skill-evals/run.sh --no-sandbox implement-trap` prints `PASS implement-trap`, and a copy of the case whose Done when needs `total([1, 2]) == 3` (no conflict) fails the same grade on "no commit ends (W1)", showing the grader sees an implementation that went ahead.

### W7: docs, diagram and repo rules

- **Change:** README step 5 names `/implement <spec>`, what it checks, and that `/spec done` runs in its worktree. The diagram's stage 5 gets the command `/implement` (`docs/diagram/workflow.py:54`), and its text (`:55-56`) stops promising a pull request, e.g. "Implement W1 first, test first; verifier re-runs checks" and "branch + evidence in record". Redraw the PNGs and the social preview (`cd docs/diagram && npm install` first, if not done). `CLAUDE.md` adds the `implement:` commit prefix and lists `scan-diff.py` and `prepare-verify.sh` among the unit-tested scripts. Log the README change in `records/README-record.md`, and add a dated section to `tests/agent-evals/BASELINE.md` with every agent-eval and skill-eval case's result and cost.
- **Files:** `README.md`, `docs/diagram/workflow.py`, `docs/workflow*.png`, `docs/social-preview.png`, `CLAUDE.md`, `records/README-record.md`, `tests/agent-evals/BASELINE.md`.
- **Done when:** `python3 docs/diagram/workflow.py` exits 0; `grep -n '"/implement"' docs/diagram/workflow.py` hits the stage 5 tuple and `grep -n 'pull request' docs/diagram/workflow.py` doesn't; `git diff --stat` shows `docs/workflow*.png` and `docs/social-preview.png` changed; `grep -n '/implement' README.md` hits step 5; `grep -n 'implement:' CLAUDE.md` hits the commit prefixes; the last line of `records/README-record.md` is a `- Not reviewed:` line dated on or after 2026-09-27; `tests/agent-evals/BASELINE.md` has a section dated on the day of the change; `check-spec.py` passes over every spec in `docs/specs/` (all three passed on 2026-09-27, before this change); `python3 -m unittest discover -s tests` and `python3 tests/replay_guard.py` pass.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W4 | 4 h | part 1 |
| W5 | 1.5 h | W4 |
| W6 | 2 h | W4 |
| W7 | 1.5 h | W4 |
| Eval runs | up to $71 capped; about $6 to $10 expected | W4–W7 |

These come from reading the code, not from building it; the order is firmer than the hours. Eval runs, from `CLAUDE.md:12-17`: seven skill-eval runs (`implement-basic`, `spec-done`, `spec-done-implement` before and after W5, `implement-trap` and its control, `cold-review-delta` in the full set), each capped at $3 and usually about $0.30, so at most $21; an implement case likely runs nearer its cap *(assumption)*. Plus one full `tests/agent-evals/run.sh`: ten cases capped at $5 each, so at most $50, $4.02 last time. A `implement-basic` run also includes up to two verifier runs, capped at $5 each by part 1.

## Spike questions

1. Can a skill eval run `/implement`'s writes in its fixture? `tests/skill-evals/run.sh` runs under `hooks/agent-sandbox.json`, the sandbox refuses writes inside `.git` (`skills/spec/spiker.md:17`), and `/implement` also writes a sibling worktree directory and `~/.cache/implement-runs` (they work in a normal session). Experiment: a throwaway case whose prompt runs `git worktree add ../wt -b x && cd ../wt && touch f && git add f && git commit -m t`, then writes a file under `~/.cache/implement-runs/`, graded on whether branch `x` has the commit and the file exists.
   Answered: all three are refused under the sandbox: a plain `git init` fails copying hooks into `.git`, a sibling directory can't be made, and `~/.cache/implement-runs` can't be written. So the implement eval cases need to run outside it (spike S1, `docs/specs/spikes/2026-09-26-implement-skill-2-skill-results.md`).
2. Can a skill invoke `/simplify` and `/code-review --fix` through the Skill tool in a headless `claude -p` session, and do they edit files there? *(assumption)* Experiment: in a scratch repo with an uncommitted duplicated helper, `claude -p "/simplify"` with `--permission-mode acceptEdits`, then check the diff.
   Open: needs a live `claude -p` session, which a spike's sandbox has no network or credentials for; run it by hand before W4.

## Risks and rollback

- **The implementer runs the repo's code outside the OS sandbox**, as any implementation in the user's session does. `/implement` is for the user's own repos; the sandboxed verifier is the independent check.
- **Implement eval cases run outside the OS sandbox** (`--no-sandbox`, W4), on fixtures their own `setup.sh` builds in a `mktemp -d` directory. The other eval cases keep the sandbox.
- **Cost.** An implementation run is one long session plus up to two verifier runs at $5 each; the report gives the verifier's cost from `run.json`.
- **Rollback:** delete `skills/implement/SKILL.md` and the three new eval cases, and revert W5's edits; `/spec` then gives its old prompt. An implementation run's worktree and branch are removed with `git worktree remove` and `git branch -D`.

## Open questions

- Should `/implement` open a pull request when the verifier says `Implementation holds: yes`? Left out (Non-goals) until the user asks for it.

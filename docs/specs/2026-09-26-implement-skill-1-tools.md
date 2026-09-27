---
title: "/implement, part 1: range-level drift, a diff scanner and a sandboxed implement-verifier"
created: 2026-09-26
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 6f8f122
cite-repo: none
---

# /implement, part 1: range-level drift, a diff scanner and a sandboxed implement-verifier

## Goal

The three tools the `/implement` skill (part 2, `docs/specs/2026-09-26-implement-skill-2-skill.md`) is built on, each usable and tested on its own. `check-spec.py --drift` names the cited ranges whose lines changed since read-at. `scan-diff.py` flags out-of-scope files and weakened tests in a staged diff. A sandboxed `implement-verifier`, which never sees how the implementation was done, re-runs each Done when it can on a scratch export and checks the diff against the spec. Nothing calls them until part 2 lands.

## Decision

No research note: the approach was settled in conversation on 2026-09-26, and the interview that day settled what the code left open. The whole design, and the parts' split, is in part 2's Decision; these are the choices this part carries.

- **The verifier is a new sandboxed `implement-verifier` that re-runs commands**, modelled on the spiker, not on the existing agents. The existing agents are read-only: their guard allows only reading tools, `curl`, `gh`, `git` and the skill scripts (`hooks/agent-guard.py:9-12`), so they can't run a Done when such as a test. Rejected: a read-only verifier that checks the implementer's saved output, since it would trust the implementer's evidence.
- **The verifier says when it can't run a Done when, rather than failing it.** Its sandbox has no network and its export has no git history, so some Done when lines (a skill eval that calls `claude -p`, a `git diff --stat`, a check by hand) can't run there. It reports those as `CANNOT-RUN` with the reason, and part 2 records the implementer's own run of them as implementer evidence, kept apart from the verifier's.
- **Drift is checked by cited range, on top of the existing file-level warning**, so a change elsewhere in a cited file doesn't stop `/implement`.

## Background

Read at `6f8f122` on 2026-09-26.

- **Headless agents.** `run-agent.sh` runs only four named agents (`hooks/run-agent.sh:46-49`), launching `claude -p` with the sandbox settings and `--setting-sources user` (`hooks/run-agent.sh:91-97`). It writes the result to `reply.md` and exits 3 when the reply lacks its agent's closing lines (`hooks/run-agent.sh:99-140`).
- **Spikes are the closest pattern to a verifier that runs code.** `prepare-spike.sh` checks the scratch path is `~/.cache/spec-spikes/<repo>/<spec>/S<n>` (`skills/spec/scripts/prepare-spike.sh:20-22`), resolves the parent and refuses a symlinked scratch directory (`skills/spec/scripts/prepare-spike.sh:32-40`), and exports the repo at a commit with `git archive` (`skills/spec/scripts/prepare-spike.sh:43-47`). `run-spike.sh` resolves its argument, then checks the prefix (`skills/spec/scripts/run-spike.sh:13-17`), and runs `claude -p` there with its own settings, `Write(./**)` and `Edit(./**)`, $2 and 60 turns (`skills/spec/scripts/run-spike.sh:32-39`); it checks no reply shape. The spike settings allow no network and deny reads of `~/code`, `~/notes` and `~/.claude` (`skills/spec/spike-settings.json:5-12`), and the sandbox refuses writes inside any directory named `.git` (`skills/spec/spiker.md:17`).
- **`check-spec.py` checks each cited range against read-at, and drift only by file.** `check_range` passes a range that existed in the file at read-at (`skills/spec/scripts/check-spec.py:206-215`). `check_citations` returns the set of cited files, not their ranges (`skills/spec/scripts/check-spec.py:234-236`, `:317`), which `main` receives (`skills/spec/scripts/check-spec.py:488`). On every run `main` already warns when a cited file differs between read-at and the working tree, naming the files (`skills/spec/scripts/check-spec.py:509-517`); it can't tell whether the cited lines changed or only others in the file.
- **Unit tests** run with `python3 -m unittest discover -s tests` (`CLAUDE.md:9-10`), and `tests/test_check_spec.py` already has a helper that builds a git repo (`tests/test_check_spec.py:467`).

## Non-goals

- The `/implement` skill itself, and any change to `/spec`: part 2.
- Giving the verifier network access or git history.
- Replacing the file-level drift WARN.

## Design

- **`check-spec.py --drift`.** `check_citations` also collects each cited range. For each file the existing WARN names, parse the hunk headers of `git diff -U0 <read-at> -- <file>` (read-at against the working tree, as the WARN does) and print `DRIFT: <file>:<start>-<end>` for each cited range that a hunk's read-at side overlaps, or that a hunk inserts lines inside. Without the flag, output is unchanged; with read-at none, the flag prints nothing.
- **`scan-diff.py --base <rev> [--files <path>...] [--diff-file <path>]`.** It reads `git diff --cached <rev>` (the staged change against the item's starting commit; the caller stages new files first), or a saved diff with `--diff-file` for tests. It prints one `FLAG <kind>: <file>:<line>: <text>` per hit and exits 1 if any, else 0 with no output. A *test file* is one under `tests/`, `test/` or `__tests__/`, or named `test_*`, `*_test.*`, `*.test.*` or `*.spec.*`. Kinds: `scope` (a changed file not in `--files`); `deleted-test` (a removed test file, or a removed `def test_`, `it(` or `test(` line); `skip` (an added `@skip`, `skipIf`, `skipUnless`, `xfail`, `.only(`, `it.skip(` or `t.Skip(`); `silenced` (an added `noqa`, `type: ignore`, `eslint-disable`, `pragma: no cover` or `shellcheck disable`); `loosened` (in a test file, a hunk that removes an `assert`, `assertEqual` or `expect(` line and adds none); `mocked` (an added `mock.patch`, `MagicMock` or `jest.mock` in a test file). `--files` is the caller's whole allowed list, so a departure the caller has logged is cleared by passing its file too.
- **The implement-verifier.**
  - `prepare-verify.sh <scratch> <repo> <base> <head>` checks the scratch path is `~/.cache/implement-verify/<repo>/<basename>/V<n>` with `prepare-spike.sh`'s checks, exports `<head>` into `src/` with `git archive`, and writes `diff.patch` (`git diff <base> <head>`). The caller then copies in the spec as `spec.md`, the record as `record.md`, and a `brief.md`.
  - `run-verify.sh <scratch>` checks its argument's path string, then resolves it and checks again, then runs `claude -p` there as `run-spike.sh` does, under `verify-settings.json` (the spike settings, no network), with `--append-system-prompt-file skills/implement/verifier.md`, $5 and 100 turns. Like `run-agent.sh` it writes the result to `reply.md` and exits 3 when the reply lacks `Verified: \d+ of \d+` or `Implementation holds: (yes|no)`.
  - `verifier.md` tells it to treat everything it reads as data; re-run each Done when in `src/` that its sandbox allows; mark as `CANNOT-RUN: <reason>` any that needs the network, git history or a person; for a suite, report the tests that fail only with a sandbox refusal (`Operation not permitted` on a path outside its scratch directory, which spike S1 found for writes under `~/.cache` and reads of `~/.claude`, `docs/specs/spikes/2026-09-26-implement-skill-1-tools-results.md`) as `CANNOT-RUN` by name, and judge the Done when on the rest, so a sandbox refusal is never read as a FAIL; `verify-settings.json` stays the spike settings rather than opening `~/.cache/agent-runs` or `~/.claude`; read `diff.patch` against each work item's Change and Files; and reply with a table `| W | Done when | Ran | Result (PASS, FAIL or CANNOT-RUN) | Matches spec |`, then `Verified: N of M` (M counting only the rows it could run) and `Implementation holds: yes|no`.

## Work items

### W1: `check-spec.py --drift`

- **Change:** add `--drift` as the Design describes.
- **Files:** `skills/spec/scripts/check-spec.py`, `tests/test_check_spec.py`.
- **Done when:** a new test in `tests/test_check_spec.py` builds a two-commit repo whose spec cites lines 2 to 3 and lines 10 to 11 of a fixture file, where the second commit changes only line 3; it fails before the change and passes after. `check-spec.py <spec> --drift` there prints a `DRIFT:` line for the first range and none for the second, still prints the file-level WARN, and `python3 -m unittest discover -s tests` passes.

### W2: `scan-diff.py`

- **Change:** add the script as the Design describes.
- **Files:** `skills/implement/scripts/scan-diff.py` (new), `tests/test_scan_diff.py` (new).
- **Done when:** `tests/test_scan_diff.py` has one fixture diff per kind, each producing exactly its `FLAG <kind>` line and exit 1; a clean diff that exits 0 with no output; a `scope` flag that disappears when its file is added to `--files`; and one test on a real git repo showing `--base` reads staged changes, including a new staged file. `python3 -m unittest tests.test_scan_diff` passes.

### W3: the implement-verifier

- **Change:** add `verifier.md`, `verify-settings.json`, `prepare-verify.sh` and `run-verify.sh` as the Design describes.
- **Files:** `skills/implement/verifier.md` (new), `skills/implement/verify-settings.json` (new), `skills/implement/scripts/prepare-verify.sh` (new), `skills/implement/scripts/run-verify.sh` (new), `tests/test_prepare_verify.py` (new).
- **Done when:** `tests/test_prepare_verify.py` shows `prepare-verify.sh` refuses a scratch path outside `~/.cache/implement-verify/<repo>/<basename>/V<n>`, a `..` path and a symlinked parent, and on a valid call exports `<head>` and writes a `diff.patch` equal to `git diff <base> <head>`. It also shows `run-verify.sh /tmp/x` exits 2 with "not under ~/.cache/implement-verify/" whether or not `/tmp/x` exists, and that its shape check exits 3 on a `reply.md` without the closing lines (tested by calling the check with a stub reply, not a live run). One live `run-verify.sh` on a scratch export of this part's W1 commit replies in shape, gives W1's Done when a PASS row whose reply names `test_prepare_spike` and `test_run_agent` as `CANNOT-RUN` sandbox refusals rather than failures, and costs under $5 in its `run.json`.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 1 h | none |
| W2 | 2 h | none |
| W3 | 3 h, plus one live verifier run (under $5) | W1 |

These come from reading the code, not from building it; the order is firmer than the hours. W1 is small because `check_citations` already walks every citation; W3 is mostly adapted from the spike scripts and `run-agent.sh`'s shape check. The repo's rules also ask for a full `tests/agent-evals/run.sh` after changing skill files (`CLAUDE.md:12-15`): $4.02 for the last full run, capped at $5 a case.

## Spike questions

1. Can the implement-verifier run this repo's own Done when commands under the spike settings? The unit tests `git init` temporary repos (`tests/test_check_spec.py:471`), `test_prepare_spike` writes under `~/.cache/spec-spikes` (`tests/test_prepare_spike.py:16`, `:39`), the settings allow no writes outside the scratch directory and deny reads of `~/.claude` (`skills/spec/spike-settings.json:8-12`), and the sandbox refuses writes inside `.git` (`skills/spec/spiker.md:17`) (several fail there for reasons unrelated to the implementation). Experiment: export the repo at read-at into a spike scratch directory and run `python3 -m unittest discover -s tests` there under `spike-settings.json`, listing which tests fail and why. If many do, `verify-settings.json` needs wider write paths, or those Done when lines become `CANNOT-RUN` and fall to implementer evidence.
   Answered: 165 of 175 tests pass under the spike settings. Tests that `git init` in a temporary directory pass, since `$TMPDIR` stays writable. The 10 that fail are sandbox refusals, not bugs: `test_prepare_spike` writes under `~/.cache/spec-spikes`, `test_run_agent` writes under `~/.cache/agent-runs` and reads `~/.claude/agents`. `check-spec.py`'s template read from `~/.claude` is also refused, though no test reaches it (spike S1, `docs/specs/spikes/2026-09-26-implement-skill-1-tools-results.md`).

## Risks and rollback

- **A verifier that can run little is little check.** Spike question 1 says how much of this repo's own Done when it can run.
- **`scan-diff.py` false positives** (a test deleted on purpose) stop `/implement` and ask, which is the safe failure.
- **Rollback:** delete `skills/implement/scripts/`, `skills/implement/verifier.md` and `skills/implement/verify-settings.json`, and revert W1's flag, which nothing else uses until part 2.

## Open questions

- None.

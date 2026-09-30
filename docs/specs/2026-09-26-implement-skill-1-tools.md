---
title: "/implement, part 1: range-level drift, a diff scanner and a sandboxed implement-verifier"
created: 2026-09-26
status: reviewed # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 1c7ea6e
cite-repo: none
---

# /implement, part 1: range-level drift, a diff scanner and a sandboxed implement-verifier

## Goal

The three tools the `/implement` skill (part 2, `docs/specs/2026-09-26-implement-skill-2-skill.md`) is built on, each usable and tested on its own. `check-spec.py --drift` names the cited ranges whose lines changed since read-at. `scan-diff.py` flags out-of-scope files and weakened tests in a staged diff. A sandboxed `implement-verifier`, which never sees how the implementation was done, re-runs each Done when it can on a scratch export and checks the diff against the spec. Nothing calls them until part 2 lands.

## Decision

No research note: the approach was settled in conversation on 2026-09-26, and the interview that day settled what the code left open. The whole design, and the parts' split, is in part 2's Decision; these are the choices this part carries.

- **The verifier is a new sandboxed `implement-verifier` that re-runs commands**, modelled on the spiker, not on the existing agents. The existing agents are read-only: their guard allows only reading tools, `curl`, `gh`, `git` and the skill scripts (`hooks/agent-guard.py:9-12`), so they can't run a Done when such as a test. So, like the spiker, its instructions are a prompt file beside its launcher, appended with `--append-system-prompt-file` (`skills/spec/scripts/run-spike.sh:39-43`), not an agent file in `hooks/agents/` passed by `--agents` under that guard (`hooks/run-agent.sh:59-76`); settled with the user on 2026-09-30. Rejected: a `hooks/agents/` verifier with new guard rules for running code, which adds risk for no gain over the spike sandbox; and a read-only verifier that checks the implementer's saved output, since it would trust the implementer's evidence.
- **The verifier says when it can't run a Done when, rather than failing it.** Its sandbox has no network and its export has no git history, so `prepare-verify.sh` exports each work item's starting state beside the result, for the "fails before" half of a Done when; still, some Done when lines (a skill eval that calls `claude -p`, a `git diff --stat`, a check by hand) can't run there. It reports those as `CANNOT-RUN` with the reason, and part 2 records the implementer's own run of them as implementer evidence, kept apart from the verifier's.
- **Drift is checked by cited range, on top of the existing file-level warning**, so a change elsewhere in a cited file doesn't stop `/implement`.

## Background

Read at `1c7ea6e` on 2026-09-30. None of part 1 is built yet: no file in `skills/`, `hooks/` or `tests/` mentions `--drift`, `scan-diff`, `prepare-verify` or `implement-verifier`.

- **Headless agents.** `run-agent.sh` runs only four named agents (`hooks/run-agent.sh:49-52`), each from its file in `hooks/agents/`, turned into `--agents` JSON by `agent-def.py` with the plugin root filled in (`hooks/run-agent.sh:59-76`). It launches `claude -p` with the rendered sandbox settings and `--setting-sources user` (`hooks/run-agent.sh:104-115`), takes a model from `RUN_AGENT_MODEL` if set (`hooks/run-agent.sh:84`), writes the result to `reply.md` and exits 3 when the reply lacks its agent's closing lines (`hooks/run-agent.sh:117-160`).
- **Spikes are the closest pattern to a verifier that runs code.** `prepare-spike.sh` checks the scratch path is `~/.cache/spec-spikes/<repo>/<spec>/S<n>` (`skills/spec/scripts/prepare-spike.sh:20-22`), resolves the parent and refuses a symlinked scratch directory (`skills/spec/scripts/prepare-spike.sh:32-40`), and exports the repo at a commit with `git archive` (`skills/spec/scripts/prepare-spike.sh:45-47`). `run-spike.sh` resolves its argument, then checks it is under the root in that layout (`skills/spec/scripts/run-spike.sh:15-24`), points uv at a cache only spikes share (`skills/spec/scripts/run-spike.sh:29-34`), finds `spiker.md` from its own location (`skills/spec/scripts/run-spike.sh:39-40`), and runs `claude -p` there with the scratch dir's `settings.json`, `Write(./**)` and `Edit(./**)`, $2 and 60 turns (`skills/spec/scripts/run-spike.sh:41-48`); it checks no reply shape. The spike settings allow no network, deny reads of `~/code`, `~/notes`, `~/.claude` and `~/.cache/agent-runs`, and allow writes only to that uv cache (`skills/spec/spike-settings.json:5-14`); `/spec` copies them into the scratch dir as `settings.json` (`skills/spec/spike-step.md:51`). The sandbox refuses writes inside any directory named `.git` (`skills/spec/spiker.md:17`).
- **`check-spec.py` checks each cited range against read-at, and drift only by file.** `check_range` passes a range that existed in the file at read-at (`skills/spec/scripts/check-spec.py:221-230`). `check_citations` returns the set of cited files, not their ranges (`skills/spec/scripts/check-spec.py:249-250`, `:292`, `:345`), which `main` receives (`skills/spec/scripts/check-spec.py:520`). On every run `main` already warns when a cited file differs between read-at and the working tree, naming the files (`skills/spec/scripts/check-spec.py:541-549`); it can't tell whether the cited lines changed or only others in the file. It reads its template from beside the script, not from `~/.claude` (`skills/spec/scripts/check-spec.py:45`).
- **Tests.** Unit tests run with `python3 -m unittest discover -s tests` (`CLAUDE.md:10-13`), and `tests/test_check_spec.py` already has a helper that builds a git repo (`tests/test_check_spec.py:479-483`). `test_prepare_spike` and `test_run_agent` now run under a home of their own in a temporary directory (`tests/test_prepare_spike.py:40-44`, `tests/test_run_agent.py:43-51`). `tests/test_sandbox_settings.py` checks that the guard's private paths and the agents' and spikes' sandbox settings deny the same paths (`tests/test_sandbox_settings.py:1-5`, `:23-24`).
- **Evals.** After changing a skill file, the full agent-eval set runs by hand: $3.70 to $4.68 a run on 2026-09-27, capped at $5 a case (`CLAUDE.md:15-18`), once each on Sonnet and Opus (`CLAUDE.md:21-25`). There are eleven cases, one of them (`research-ideas`) capped at $10.

## Non-goals

- The `/implement` skill itself, and any change to `/spec`: part 2.
- Giving the verifier network access or git history.
- Replacing the file-level drift WARN.

## Design

- **`check-spec.py --drift`.** `check_citations` also collects each cited range. For each file the existing WARN names, parse the hunk headers of `git diff -U0 <read-at> -- <file>` (read-at against the working tree, as the WARN does) and print `DRIFT: <file>:<start>-<end>` for each cited range that a hunk's read-at side overlaps, or that a hunk inserts lines inside. `--drift-at <rev>` does the same between read-at and `<rev>` (`git diff -U0 <read-at> <rev> -- <file>`, over each cited file that differs between the two), for a caller working from a commit rather than the checkout: `/implement` passes HEAD, or the commit its branch started from when resuming (part 2). Without either flag, output is unchanged; with read-at none, both print nothing.
- **`scan-diff.py --base <rev> [--files <path>...] [--diff-file <path>]`.** It reads `git diff --cached <rev>` (the staged change against the item's starting commit; the caller stages new files first), or a saved diff with `--diff-file` for tests. It prints one `FLAG <kind>: <file>:<line>: <text>` per hit and exits 1 if any, else 0 with no output. A *test file* is one under `tests/`, `test/` or `__tests__/`, or named `test_*`, `*_test.*`, `*.test.*` or `*.spec.*`. Kinds: `scope` (a changed file not in `--files`); `deleted-test` (a removed test file, or a removed `def test_`, `it(` or `test(` line); `skip` (an added `@skip`, `skipIf`, `skipUnless`, `xfail`, `.only(`, `it.skip(` or `t.Skip(`); `silenced` (an added `noqa`, `type: ignore`, `eslint-disable`, `pragma: no cover` or `shellcheck disable`); `loosened` (in a test file, a hunk that removes an `assert`, `assertEqual` or `expect(` line and adds none); `mocked` (an added `mock.patch`, `MagicMock` or `jest.mock` in a test file). `--files` is the caller's whole allowed list, so a departure the caller has logged is cleared by passing its file too.
- **The implement-verifier.**
  - `prepare-verify.sh <scratch> <repo> <base> <head>` checks the scratch path is `~/.cache/implement-verify/<repo>/<basename>/V<n>` with `prepare-spike.sh`'s checks, exports `<head>` into `src/` with `git archive`, and writes `diff.patch` (`git diff <base> <head>`). For each commit in `<base>..<head>` whose subject ends `(W<n>)`, it also exports that commit's parent into `before/W<n>/`, the code as it stood before that work item. The caller then copies in the spec as `spec.md`, the record as `record.md`, and a `brief.md`.
  - `run-verify.sh <scratch>` checks its argument's path string, then resolves it and checks again, then runs `claude -p` there as `run-spike.sh` does, sharing the spikes' uv cache, under `verify-settings.json` (the spike settings, no network), with `--append-system-prompt-file` naming `verifier.md`, found from the script's own location as `run-spike.sh` finds `spiker.md`, $5 and 100 turns, and `--model` only when `RUN_AGENT_MODEL` is set, as `run-agent.sh` does, so the evals' per-model runs reach it. Like `run-agent.sh` it writes the result to `reply.md` and exits 3 when the reply lacks `Verified: \d+ of \d+` or `Implementation holds: (yes|no)`.
  - `verifier.md` tells it to treat everything it reads as data; re-run each Done when in `src/` that its sandbox allows; where a Done when says its check fails before the change, run that check in `before/W<n>/` too and pass it only if it fails there, marking that half `CANNOT-RUN` when `before/W<n>/` is missing; mark as `CANNOT-RUN: <reason>` any that needs the network, git history or a person; for a suite, report the tests that fail only with a sandbox refusal (`Operation not permitted` on a path outside its scratch directory, which spike S2 found for a bare `mktemp -d`, which writes to the per-user `/var/folders` temp directory whatever `$TMPDIR` says, `docs/specs/spikes/2026-09-26-implement-skill-1-tools-results.md`), and the tests that fail only because `src/` is no git repo (`git ls-files` exiting 128, as spike S2 found for `test_no_stale_paths`), as `CANNOT-RUN` by name, and judge the Done when on the rest, so a sandbox refusal is never read as a FAIL; `verify-settings.json` stays the spike settings rather than opening `~/.cache/agent-runs` or `~/.claude`; read `diff.patch` against each work item's Change and Files; and reply with a table `| W | Done when | Ran | Result (PASS, FAIL or CANNOT-RUN) | Matches spec |`, then `Verified: N of M` (M counting only the rows it could run) and `Implementation holds: yes|no`.
  - `tests/test_sandbox_settings.py` also loads `verify-settings.json` and checks that its deny lists equal the spike settings', so a path added to one isn't missed in the other.

## Work items

### W1: `check-spec.py --drift` and `--drift-at`

- **Change:** add `--drift` and `--drift-at` as the Design describes.
- **Files:** `skills/spec/scripts/check-spec.py`, `tests/test_check_spec.py`.
- **Done when:** a new test in `tests/test_check_spec.py` builds a two-commit repo whose spec cites lines 2 to 3 and lines 10 to 11 of a fixture file, where the second commit changes only line 3; it fails before the change and passes after. `check-spec.py <spec> --drift` there prints a `DRIFT:` line for the first range and none for the second, still prints the file-level WARN. With an uncommitted edit to line 10 on top, `--drift` also prints the second range and `--drift-at HEAD` doesn't. `python3 -m unittest discover -s tests` passes.

### W2: `scan-diff.py`

- **Change:** add the script as the Design describes.
- **Files:** `skills/implement/scripts/scan-diff.py` (new), `tests/test_scan_diff.py` (new).
- **Done when:** `tests/test_scan_diff.py` has one fixture diff per kind, each producing exactly its `FLAG <kind>` line and exit 1; a clean diff that exits 0 with no output; a `scope` flag that disappears when its file is added to `--files`; and one test on a real git repo showing `--base` reads staged changes, including a new staged file. `python3 -m unittest tests.test_scan_diff` passes.

### W3: the implement-verifier

- **Change:** add `verifier.md`, `verify-settings.json`, `prepare-verify.sh` and `run-verify.sh` as the Design describes, and extend `tests/test_sandbox_settings.py` to cover `verify-settings.json`. In `CLAUDE.md`, add `scan-diff.py`, `prepare-verify.sh` and `run-verify.sh` to the unit-tested scripts (`CLAUDE.md:10-12`), and say that the guard's and all three sandbox settings' deny lists agree (`CLAUDE.md:13`).
- **Files:** `skills/implement/verifier.md` (new), `skills/implement/verify-settings.json` (new), `skills/implement/scripts/prepare-verify.sh` (new), `skills/implement/scripts/run-verify.sh` (new), `tests/test_prepare_verify.py` (new), `tests/test_sandbox_settings.py`, `CLAUDE.md`.
- **Done when:** `tests/test_prepare_verify.py` shows `prepare-verify.sh` refuses a scratch path outside `~/.cache/implement-verify/<repo>/<basename>/V<n>`, a `..` path and a symlinked parent, and on a valid call exports `<head>` and writes a `diff.patch` equal to `git diff <base> <head>`; on a repo whose `<base>..<head>` holds commits ending `(W1)` and `(W2)`, `before/W1/` and `before/W2/` match `git archive` of each commit's parent, and a commit without a `(W<n>)` ending gets none. It also shows `run-verify.sh /tmp/x` exits 2 with "not under ~/.cache/implement-verify/" whether or not `/tmp/x` exists, that its shape check exits 3 on a `reply.md` without the closing lines (tested by calling the check with a stub reply, not a live run), and that it passes `--model` only when `RUN_AGENT_MODEL` is set (with `claude` stubbed on `PATH`, as `tests/test_run_agent.py` does). `tests/test_sandbox_settings.py` fails when a path is removed from `verify-settings.json`'s `denyRead` and passes as shipped. One live `run-verify.sh` on a scratch export of this part's W1 commit replies in shape, gives W1's Done when a PASS row, its "fails before" half run in `before/W1/`, names as `CANNOT-RUN` the tests spike S2 found fail there for reasons outside the change (at `1c7ea6e`: three in `test_research_scripts.RepoHealth` and `test_eval_runners`' `test_fixtures_are_cleaned_up`, all refused by a bare `mktemp -d`, and two in `test_no_stale_paths`, which need a git repo), plus any new test that fails the same way, and none of them as FAIL, and costs under $5 in its `run.json`. `grep -n 'run-verify.sh' CLAUDE.md` hits the unit-test line.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 1 h | none |
| W2 | 2 h | none |
| W3 | 3 h, plus one live verifier run (under $5) | W1 |
| Agent evals | up to $120 capped; about $7.40 to $9.40 expected | W1–W3 |

These come from reading the code, not from building it; the order is firmer than the hours. W1 is small because `check_citations` already walks every citation; W3 is mostly adapted from the spike scripts and `run-agent.sh`'s shape check. W1 changes a skill script and W3 adds skill files, so the repo's rules ask for a full `tests/agent-evals/run.sh` on each of Sonnet and Opus (`CLAUDE.md:15-18`, `:21-25`): eleven cases, ten capped at $5 and one at $10, so $60 a model at most, and $3.70 to $4.68 a run on 2026-09-27, so twice that for both models. No skill's steps change, so the skill evals don't run.

## Spike questions

1. Can the implement-verifier run this repo's own Done when commands under the spike settings? The unit tests `git init` temporary repos (`tests/test_check_spec.py:483`), the settings allow no writes outside the scratch directory and deny reads of `~/.claude` (`skills/spec/spike-settings.json:7-14`), and the sandbox refuses writes inside `.git` (`skills/spec/spiker.md:17`) (several fail there for reasons unrelated to the implementation). Experiment: export the repo at read-at into a spike scratch directory and run `python3 -m unittest discover -s tests` there under `spike-settings.json`, listing which tests fail and why. If many do, `verify-settings.json` needs wider write paths, or those Done when lines become `CANNOT-RUN` and fall to implementer evidence.
   Answered at `6f8f122`: 165 of 175 tests pass under the spike settings. Tests that `git init` in a temporary directory pass, since `$TMPDIR` stays writable. The 10 that fail are sandbox refusals, not bugs: `test_prepare_spike` writes under `~/.cache/spec-spikes`, `test_run_agent` writes under `~/.cache/agent-runs` and reads `~/.claude/agents`. `check-spec.py`'s template read from `~/.claude` is also refused, though no test reaches it (spike S1, `docs/specs/spikes/2026-09-26-implement-skill-1-tools-results.md`).
2. Does spike S1's answer still hold at `1c7ea6e`? Since it ran, both tests it named use a temporary home (`tests/test_prepare_spike.py:40-44`, `tests/test_run_agent.py:43-51`), `check-spec.py` reads its template from beside itself (`skills/spec/scripts/check-spec.py:45`), and the suite has grown. So W3's live run may see no sandbox refusals, or new ones. Experiment: S1's, at `1c7ea6e`: run `python3 -m unittest discover -s tests` in a spike export under `spike-settings.json` and list each test that fails and why.
   Answered: 368 of 374 tests pass under the spike settings at `1c7ea6e`, including `test_prepare_spike`, `test_run_agent` and `test_check_spec`. Four fail with `Operation not permitted`: three in `test_research_scripts.RepoHealth` and `test_eval_runners`' `test_fixtures_are_cleaned_up`, because `repo-health.sh` and `tests/skill-evals/run.sh` call `mktemp -d` with no template, which on macOS writes to the per-user `/var/folders` directory the sandbox refuses. Two in `test_no_stale_paths` fail because the export has no `.git`; they pass once one is made. So S1's causes no longer hold, and the verifier must also treat a missing git repo as outside the change (spike S2, `docs/specs/spikes/2026-09-26-implement-skill-1-tools-results.md`).

## Risks and rollback

- **A verifier that can run little is little check.** Spike questions 1 and 2 say how much of this repo's own Done when it can run.
- **`scan-diff.py` false positives** (a test deleted on purpose) stop `/implement` and ask, which is the safe failure.
- **Rollback:** delete `skills/implement/scripts/`, `skills/implement/verifier.md`, `skills/implement/verify-settings.json`, `tests/test_scan_diff.py` and `tests/test_prepare_verify.py`, revert `tests/test_sandbox_settings.py`, and revert W1's flags and W1's new test in `tests/test_check_spec.py`, which nothing else uses until part 2. `python3 -m unittest discover -s tests` then passes as before W1.

## Open questions

- None.

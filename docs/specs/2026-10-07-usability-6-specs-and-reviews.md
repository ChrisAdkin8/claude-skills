---
title: "Usability, part 6: specs, reviews, spikes and git reads"
created: 2026-10-07
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 377b2dd
cite-repo: none
---

# Usability, part 6: specs, reviews, spikes and git reads

## Goal

A spec committed to a shared repo passes its checks on a teammate's machine. A spec renamed in Finder keeps its review history. `/implement` says plainly when a spec is in a format it can't build. `/cold-review again <file>` gives a document a second full review when its author asks, and `/cold-review` refuses a document its reviewer can't read before it spends anything. Spikes run on the model the user chose, and a question no spike can answer comes with the command to run it by hand. Repos whose own git config names a program, such as one set up with `nbstripout`, can still be read.

Part 6 of 7 from the usability review of 2026-10-07. It stands alone. The gate checks of parts 2a and 2b come before W3's in `/implement`'s gate.

## Decision

- **Missing notes on another machine:** warn when the notes folder doesn't exist here; keep failing when it does and the note is missing. That keeps the author's own check as strict as today.
- **Renames:** find a moved spec's record by its title, as a last resort after its name and git history. Rejected: a `record:` line in every spec's frontmatter, which house-format specs don't have.
- **House formats:** say what `/implement` needs, rather than teach it to build specs without W-numbered work items, whose commits and verifier rows depend on the numbers.
- **A second full review:** the user chose on 2026-10-07 to allow one when asked, by name, with a warning, while the default stays one full review and one delta.
- **Spikes:** honour `RUN_AGENT_MODEL` like every other launcher, defaulting to Sonnet as today.
- **git reads:** let through the read commands git never runs a configured program for, rather than drop the check.

## Background

Read at `377b2dd` on 2026-10-07.

**Specs link private notes.** `check-spec.py` fails a spec whose `research` or `idea` names a missing file (`skills/spec/scripts/check-spec.py:637-645`), or whose text links a note that doesn't exist (`:714-717`). `/implement`'s gate needs `RESULT: PASS` (`skills/implement/SKILL.md:52`). The notes live in the author's home folder, so the same spec fails on any machine without them.

**Renamed specs.** A record is found by the spec's name or by its git history (`skills/research/scripts/mdcheck.py:175-202`). Measured on 2026-10-07 in a scratch repo: after a plain `mv` of a committed spec whose record held a saved review, `review-state.py` printed `record: none` and `state: full`, offering a second paid full review; `check-spec.py` reads the record the same way.

**House formats.** `/spec` follows a repo's own conventions "exactly" (`skills/spec/SKILL.md:65`), the README says so (`README.md:194-196`), and `check-spec.py` passes such a spec with an INFO line (`skills/spec/scripts/check-spec.py:647-650`). `/implement` needs `status: reviewed` in the frontmatter (`skills/implement/SKILL.md:51`) and W-numbered work items (`:91`).

**One full review.** `/cold-review` gives "One full round per document" and one delta review of what's logged since (`skills/cold-review/SKILL.md:15-16`), and stops when nothing is left (`:52-53`). The README explains why (`README.md:291-293`). The cost shows in this repo: the README has had its one full and one delta review (`CLAUDE.md:65-67`), and its record now holds 50 `Not reviewed:` lines, counted with `grep -c`, including the rewrite for newcomers.

**Documents the reviewer can't read.** `/cold-review` checks only that the document exists and is markdown (`skills/cold-review/SKILL.md:41-42`). The guard refuses the reviewer every file under `~/.claude` (`hooks/agent-guard.py:303-306`) and under its credential folders, `~/.config` among them (`hooks/agent-guard.py:283-291`), so a plan saved by plan mode, or a `CLAUDE.md` there, is found unreadable only after the reviewer has been paid to try.

**Spikes.** `run-spike.sh` runs every spike on Sonnet (`skills/spec/scripts/run-spike.sh:56`), and the README's cost section doesn't say so (`README.md:374-375`). A question that needs credentials, a cloud account, `docker` or a model call is deferred (`skills/spec/spike-step.md:31`) with an `Open:` line saying why (`:39`). Counted on 2026-10-07 in `docs/specs/records/`: 18 of 35 routed spike questions were deferred, 16 ran as spikes and 1 went to research.

**git reads.** `git-read.py` refuses to run any git command in a repo whose own config sets a filter, diff driver, merge driver, GPG program or config-defined hook (`hooks/git-read.py:48-52`, `:74-88`), and `/implement` finds its repo through it (`skills/implement/SKILL.md:40`), as `/spec` reads logs and drift (`skills/spec/SKILL.md:34`). `nbstripout --install` and `git-crypt` write such keys into a repo's own config, so in those repos both skills stop at their first git read.

## Non-goals

- Changing what a delta review covers, or making repeat reviews the default.
- Building specs that have no W-numbered work items.
- Running deferred spike questions automatically.

## Design

**Missing notes.** For a missing path under the notes folder, `check-spec.py` reports a WARN, "links a note that isn't on this machine", when the notes folder itself doesn't exist, and a FAIL as today when it does. Part 4's `locations.py` names the folder once it has landed.

**Renames.** When `record_for` finds nothing, it looks in the spec's `records/` folder for a record whose `# Record: <title>` heading matches the spec's title and whose link names a spec file that no longer exists. Exactly one match is used, with a WARN giving the `git mv` that puts it under the new name; two or more, or none, mean no record, as today.

**House formats.** `/implement`'s gate gets a check before the others: a spec with no `### W<n>` work items or no `status:` frontmatter line stops with "this spec is in the repo's own format; `/implement` needs W-numbered work items and a `status: reviewed` frontmatter line". The README's `/spec` section says the same.

**`/cold-review again <file>`.** `review-state.py --again` prints `state: again` for a document with a saved full review. The skill says, in one line, that a second full review tends to find something whether or not it matters, runs the full prompt, and saves the reply under `### Full review again, <date>` in the record's `## Cold review`. `mdcheck.read_review` counts it like a delta review: every `Not reviewed:` line logged before it counts as reviewed, so `check-spec.py`'s gate reads it as it reads a delta.

**Can the reviewer read it?** A new script, `hooks/can-agent-read.py <path>`, asks the guard's read check about a path and prints `readable` or the guard's reason. `/cold-review`'s step 1 runs it and stops with the reason and a suggestion: copy the document outside `~/.claude` and review the copy.

**Spikes.** `run-spike.sh` passes `--model "${RUN_AGENT_MODEL:-sonnet}"`. Triage writes, under each deferred question in the record, a `Run it yourself:` line with the command to run and what result would answer it, and step 7e lists those lines.

**git reads.** `git-read.py` lets these through in such a repo, run with `-c log.showSignature=false`: `rev-parse`, `branch --list`, `worktree list`, and `log` with `--format` and no option that shows a patch, a stat or a signature. Anything else is refused as today, with the key named and the commands that still work listed. Spike question 1 confirms the list.

## Work items

### W1: a spec passes on a machine without the author's notes

- **Change:** the WARN for a missing notes folder, as the Design says.
- **Files:** `skills/spec/scripts/check-spec.py`, `tests/test_check_spec.py`.
- **Done when:** a new test with `HOME` set to an empty scratch folder gets `RESULT: PASS` and the new WARN for a spec whose `research` and text name notes; with a notes folder present but the note missing, it still gets the FAIL. It fails before the change. The unit tests pass, and `check-spec.py` passes every spec under `docs/specs/` it passed before.

### W2: a renamed spec keeps its record

- **Change:** the title match in `mdcheck.record_for`.
- **Files:** `skills/research/scripts/mdcheck.py`, `tests/test_mdcheck.py`, `tests/test_review_state.py`, `tests/test_check_spec.py`.
- **Done when:** a new test repeats the measurement in Background and gets the record back, `state: unchanged` and the `git mv` WARN; two records with the same title give no record. It fails before the change. The unit tests pass.

### W3: `/implement` names what a house-format spec lacks

- **Change:** the first gate check, and the README sentence.
- **Files:** `skills/implement/SKILL.md`, `README.md`, `records/README-record.md`, `tests/test_implement_skill.py`.
- **Done when:** a test finds the check first in the gate, with its message; the README says it, with a dated `Not reviewed:` line; `implement-basic` and `implement-trap` pass on Sonnet and Opus.

### W4: `/cold-review again`

- **Change:** `review-state.py --again`, the mode, the saving rule and the parser reading it.
- **Files:** `skills/cold-review/scripts/review-state.py`, `skills/cold-review/SKILL.md`, `skills/research/scripts/mdcheck.py`, `README.md`, `records/README-record.md`, `tests/test_review_state.py`, `tests/test_mdcheck.py`, `tests/test_check_spec.py`.
- **Done when:** new tests show `--again` printing `state: again` for a reviewed document and `state: full` for an unreviewed one; a record with a `### Full review again` section after two `Not reviewed:` lines lets a reviewed spec pass `check-spec.py`'s delta gate, and fails it before the change. The README's cold review section describes `again` and its warning. The `cold-review-delta` skill eval and the delta-review agent evals pass on Sonnet and Opus.

### W5: `/cold-review` refuses what its reviewer can't read

- **Change:** `hooks/can-agent-read.py`, and step 1 of `/cold-review` calling it.
- **Files:** `hooks/can-agent-read.py` (new), `skills/cold-review/SKILL.md`, `tests/test_can_agent_read.py` (new).
- **Done when:** new tests print `readable` for a repo file and the guard's reason for a scratch file under a fake home's `.claude` and `.config`; `allowed-tools` pre-approves the script; the `cold-review-delta` case passes on Sonnet and Opus.

### W6: spikes use the chosen model, and deferred questions say how to run them by hand

- **Change:** the model flag, the `Run it yourself:` lines and the report line.
- **Files:** `skills/spec/scripts/run-spike.sh`, `skills/spec/spike-step.md`, `skills/spec/record-template.md`, `README.md`, `records/README-record.md`, `tests/test_run_spike.py`.
- **Done when:** a test sees the stub `claude` get `--model opus` with `RUN_AGENT_MODEL=opus` and `--model sonnet` without it; the record template shows a `Run it yourself:` line; the README's cost section says spikes default to Sonnet; the `spike-inherited` agent eval passes on Sonnet and Opus.

### W7: safe git reads in repos with configured programs

- **Change:** the allowed shapes and the clearer refusal in `git-read.py`.
- **Files:** `hooks/git-read.py`, `tests/test_git_read.py`.
- **Done when:** new tests on a scratch repo with `filter.nbstripout.clean` and `gpg.ssh.program` in its own config let `rev-parse --show-toplevel`, `branch --list`, `worktree list` and `log --format=%h` through, with a marker program for each key that is never run, and refuse `diff` and `log -p` with a message naming the key and the allowed commands. Each fails before the change. The unit tests pass.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 1 h | none |
| W2 | 2 h | none |
| W3 | 1 h | the gate checks of parts 2a and 2b |
| W4 | 4 h | none |
| W5 | 2 h | none |
| W6 | 2 h | none |
| W7 | 3 h, after spike question 1 | none |
| Evals | both sets on both models, and the implement cases | W1 to W7 |

The hours are guesses from reading the files. W3 to W6 change skill steps or launch scripts, and W3 changes `skills/implement/`, so both eval sets run on both models with the implement cases (`CLAUDE.md:23-38`); $15.23 on 2026-10-04 (`docs/repo-guide.md:108-109`).

## Spike questions

1. Which of `rev-parse`, `branch --list`, `worktree list`, `log --format` and `show --no-patch --format` can run a program a repo's own config names, through a filter, a textconv, `diff.external`, a GPG program or `log.showSignature`? Experiment: a scratch repo whose config points every such key at a script that writes a marker file; run each command, with `-c log.showSignature=false`, and record which leave a marker. It runs locally, with no network.

## Risks and rollback

- A WARN where there was a FAIL could let a spec with a mistyped note link through on a machine without notes. The author's machine still fails it.
- A title match could pick the wrong record if two specs share a title; W2 uses none when there are two.
- `again` could become a habit. The warning and the README's reasons are the brake; rollback is removing the mode.

## Open questions

- Should `/cold-review again` be limited to one per document, like the delta? This part allows it whenever asked, as the user chose.

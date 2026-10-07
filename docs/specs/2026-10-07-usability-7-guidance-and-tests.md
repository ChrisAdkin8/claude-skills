---
title: "Usability, part 7: what's next, plainer reports, and tests of the real flow"
created: 2026-10-07
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 377b2dd
cite-repo: none
---

# Usability, part 7: what's next, plainer reports, and tests of the real flow

## Goal

`/spec status` tells a returning user where a spec stands and the one command to run next. Reports recommend which findings to fold in, and explain any in-house word they use. The skill evals cover the paths no case reaches today: `/idea`, a full `/cold-review` and its prompt mode, `/spec finish` and `/spec spike`, `/implement` resuming after a question, a fresh setup, and the real back-and-forth of an agent running in the background while the session waits. The session miner counts every command, and a test stops the skills' instructions from quietly growing.

Part 7 of 7 from the usability review of 2026-10-07. W4 needs parts 1b and 3 (the account token and the starter notes); the rest stands alone.

## Decision

- **`/spec status`** is a read-only mode backed by a script, so it costs no agent and gives the same answer each time. Rejected: a sixth command, and teaching every report to predict the next step, which goes stale as soon as the user acts.
- **Recommendations:** the relay marks what it would fold and why, and the user still picks.
- **Evals:** add cases for each uncovered path, and test the background flow through streaming input, which keeps a headless session open. Rejected: more unit tests of the skills' text, which can't see what the model does.
- **Instruction size:** a word budget per skill, set at today's sizes, so growth is a decision. Trimming the text is left open.

## Background

Read at `377b2dd` on 2026-10-07.

**Nothing says what's next.** `/spec`'s modes are the main path, a description, `quick`, `finish`, `spike` and `done` (`skills/spec/SKILL.md:44-50`), with no way to ask where a spec stands. `review-state.py` prints internal lines such as `diff:` and `state: unchanged` (`skills/cold-review/scripts/review-state.py:254-260`), and `check-spec.py`'s only next-step hint is "run `/spec done`", once implementation notes exist (`skills/spec/scripts/check-spec.py:862`). Counted on 2026-10-07 with a read-only keyword scan of the user's own session logs *(unverified)*: about 34 messages typed during skill runs asked where things stood (which file, which branch, what next), about 30 asked "what do you recommend?", and about 17 asked for something to be said more simply.

**Relays don't recommend.** `/cold-review` offers folding in the findings "in one line each" (`skills/cold-review/SKILL.md:159`), with no view on which to fold, and `/spec` asks the user to pick with the most important first (`skills/spec/SKILL.md:144`); only the spike question puts a recommendation first (`skills/spec/spike-step.md:33`).

**What the evals don't reach.** The skill evals are eight cases: `cold-review-delta`, `implement-basic`, `implement-trap`, `research-quick-flow`, `spec-done`, `spec-done-branch`, `spec-done-implement` and `spec-quick` (`tests/skill-evals/cases/`). Each runs unattended, in one turn, with agents in the foreground and nothing committed (`tests/skill-evals/cases/spec-quick/prompt.txt:3`), against the user's real notes folder (`tests/skill-evals/run.sh:69-70`). Claude Code ends a background Bash task "about five seconds after Claude has returned its final result and stdin has closed" in a `claude -p` run ([headless](https://code.claude.com/docs/en/headless.md)), which is why the cases keep agents in the foreground; so the path a real user takes, where the skill ends its turn and picks up when the agent finishes, is never run.

**The miner misses commands.** `tests/mine-sessions.py` knows four skills and four agents (`tests/mine-sessions.py:32`, `:40`), so it never counts `/implement` or the implementer, and it compares the typed command's whole name with those four (`:41`, `:258`), so `/checked-plans:spec` isn't counted either.

**Instruction size.** Counted on 2026-10-07 with `wc -w`: a full `/spec` run loads about 7,300 words of instructions from six files, and its steps refer to one another by number ("as step 6 item 1 says").

## Non-goals

- Rewriting the skills' steps to be shorter; W7 only stops them growing unnoticed.
- Running evals in CI; they cost money and stay by hand.
- Changing what any report contains beyond the recommendation and the explained words.

## Design

**`/spec status [<spec>]`** runs `skills/spec/scripts/spec-status.py`, which reads, without changing anything: the spec's status; `check-spec.py`'s result; `review-state.py`'s state; the spike questions answered and open; whether the spec, record and spike results are committed; whether `implement/<basename>` and its worktree exist; and the ledger's spend. It prints those in plain words and one next command, from a table:

| What it finds | Next |
|---|---|
| draft, no saved review, not quick | `/spec finish <spec>` |
| unlogged edits after the review | `/cold-review <spec>` |
| `Not reviewed:` lines, no delta review | `/cold-review <spec>` |
| open spike questions, no spike round | `/spec spike <spec>` |
| ready, status still draft | set `status: reviewed`, then commit the spec and its record |
| reviewed and committed | `/implement <spec>` |
| branch exists, `/spec done` not run | `/spec done <worktree spec path>` |
| done, branch not merged | the merge and clean-up commands from part 2 |

With no spec named, it lists every spec in the repo's spec folder with its status and next command.

**Recommendations.** `/cold-review` step 5 adds, after the table, "I'd fold in rows <n>, <m>: <why, in one line>", and `/spec`'s fold question marks those options `(Recommended)` and puts them first. Each report explains an in-house word the first time it uses one, in a few words, with the README glossary from part 3 for the rest.

**New eval cases**, each with `setup.sh`, `prompt.txt` and `grade.py`:
- `idea`: files a note in a scratch notes folder and commits only it.
- `cold-review-full` and `cold-review-prompt`: a full review saved to a fresh record; the prompt mode's prompt holds the skeleton's fixed lines and no summary of the document.
- `spec-finish`: a hand-edited spec gets its check and a verifier round recorded.
- `spec-spike`: one local spike question runs, its answer is folded, and the results file is written.
- `implement-question`: a spec whose W1 is ambiguous makes the implementer ask; the prompt answers it; the grader finds the answer logged as a departure and W1's commit after it.
- `fresh-setup`: `HOME` points at a scratch folder holding nothing; the case runs `/idea setup`, then `/idea` and `/research quick`, authenticated by `CLAUDE_CODE_OAUTH_TOKEN` (part 1b), since the keychain login may not follow a changed home folder (spike question 2).
- `background-flow`: `/spec quick` run through `--input-format stream-json`, with stdin held open until the session's final report, so the verifier runs in the background and the session resumes from its checklist (spike question 1).

**Miner.** `tests/mine-sessions.py` adds `implement` and `implementer`, strips a `<plugin>:` prefix before matching, and reports, per skill, the Bash calls whose command matches none of that skill's `allowed-tools` rules: the calls a user outside auto mode would have been asked about.

**Word budget.** A test counts each skill's `SKILL.md` and the files it always loads, and fails if any grows past its count on the day the test lands plus 10 %.

## Work items

### W1: `/spec status`

- **Change:** the script, the mode, and its line in the README's `/spec` section.
- **Files:** `skills/spec/scripts/spec-status.py` (new), `skills/spec/SKILL.md`, `README.md`, `records/README-record.md`, `tests/test_spec_status.py` (new).
- **Done when:** new tests build a scratch repo in each row's state and get that row's next command, and `spec-status.py` with no spec lists every spec in `docs/specs/`; it changes no file, checked by comparing `git status --porcelain` before and after. `allowed-tools` pre-approves the script. The README names the mode, with a dated `Not reviewed:` line.

### W2: relays recommend, and reports explain their words

- **Change:** the recommendation line and the `(Recommended)` fold options, and the explain-once rule in each report step.
- **Files:** `skills/cold-review/SKILL.md`, `skills/spec/SKILL.md`, `skills/research/SKILL.md`, `skills/implement/SKILL.md`, `tests/skill-evals/cases/cold-review-delta/grade.py`.
- **Done when:** the `cold-review-delta` grader finds "I'd fold in" in the final reply, and the case passes on Sonnet and Opus.

### W3: eval cases for the uncovered paths

- **Change:** the `idea`, `cold-review-full`, `cold-review-prompt`, `spec-finish`, `spec-spike` and `implement-question` cases.
- **Files:** `tests/skill-evals/cases/` (six new folders), `tests/test_eval_runners.py`, `tests/agent-evals/BASELINE.md`.
- **Done when:** each new case passes on Sonnet and Opus, and fails when its grader is pointed at a fixture with its expected change undone; `tests/test_eval_runners.py` still passes; `BASELINE.md` has a dated section with each case's result and cost.

### W4: a fresh-setup eval

- **Change:** the `fresh-setup` case, and the runner passing `HOME` and the token through for a case that asks for them.
- **Files:** `tests/skill-evals/cases/fresh-setup/` (new), `tests/skill-evals/run.sh`, `tests/test_eval_runners.py`.
- **Done when:** the case passes on Sonnet and Opus with the user's real notes folder unchanged before and after, which the runner already checks; a unit test sees the runner refuse the case when `CLAUDE_CODE_OAUTH_TOKEN` is unset, with a message saying to run `claude setup-token`.

### W5: an eval of the real back-and-forth

- **Change:** the `background-flow` case, and a runner mode that feeds a case's prompt as streaming input and closes stdin only after the final report or 15 minutes.
- **Files:** `tests/skill-evals/cases/background-flow/` (new), `tests/skill-evals/run.sh`, `tests/test_eval_runners.py`.
- **Done when:** the grader finds the verifier's run dir written by a background call, the spec-quick grader's checks passing, and the checklist pasted twice: once when the turn ended and once in the final report. It passes on Sonnet and Opus.

### W6: the miner counts every command, and the would-be prompts

- **Change:** the added names, the prefix strip, and the per-skill count of calls outside `allowed-tools`.
- **Files:** `tests/mine-sessions.py`, `tests/test_mine_sessions.py`.
- **Done when:** new tests feed the miner a fixture log with `/checked-plans:spec`, `/implement` and an implementer run, and find all three counted; a Bash call in a `/research` run that matches no rule in its `allowed-tools` is reported under that skill. Each fails before the change.

### W7: a word budget per skill

- **Change:** the test and its budgets.
- **Files:** `tests/test_skill_size.py` (new).
- **Done when:** the test passes on the day it lands, and fails when a scratch copy of `skills/spec/SKILL.md` gains 10 % more words.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 4 h | part 2's closing commands, for the last row |
| W2 | 1 h | part 3's glossary |
| W3 | 6 h, plus the cases' first runs | none |
| W4 | 2 h, after spike question 2 | parts 1b and 3 |
| W5 | 4 h, after spike question 1 | none |
| W6 | 3 h | none |
| W7 | 1 h | parts 1a, 1b and 2 to 6, so the budgets start from the new sizes |
| Evals | both sets on both models, the new cases included | W1 to W7 |

The hours are guesses. Each new case costs about $0.40 for the skill's own session, capped at $3, plus up to $2 for each agent it launches and $5 for an implementer (`CLAUDE.md:27-30`, `:35-38`); with eight new cases on two models, budget about $25 a full run on top of today's $15.23 (`docs/repo-guide.md:108-109`).

## Spike questions

1. In a `claude -p` run fed by `--input-format stream-json`, with stdin held open, does a background Bash task's completion bring the model back for another turn in the same process, as in an interactive session? Experiment: by hand, a prompt that runs `sleep 20; echo done` in the background and ends its turn; hold stdin open for 60 seconds and see whether a second assistant turn mentions `done`. It needs the model API.
2. With `HOME` pointed at an empty scratch folder on macOS, does `claude -p` still find the user's `/login` credentials, or does it need `CLAUDE_CODE_OAUTH_TOKEN`? The documentation keys the keychain entry to the configuration folder ([authentication](https://code.claude.com/docs/en/authentication.md)). Experiment: by hand, `HOME=<scratch> claude -p --output-format json hi` with and without the token.

## Risks and rollback

- `/spec status` could name a wrong next step for a state the table misses. It prints the facts it read above the suggestion, so the user can see why.
- Eight new cases add cost to every full eval round. Each can be run alone, and the runner's caps still hold.
- The word budget could block a needed addition. Raising a budget is a one-line, reviewed change.

## Open questions

- Should the skills' instructions be trimmed, and their cross-references by step number replaced by names? This part only measures and caps them.

---
title: "Usability, part 1a: what runs cost"
created: 2026-10-07
status: in-progress # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 377b2dd
cite-repo: none
---

# Usability, part 1a: what runs cost

## Goal

`/implement`'s ledger counts what each implementer call really cost, and an interrupted call no longer locks a spec at its cap. Every command's report says what its agents cost, and the README says what things cost and where each cap applies.

Part 1a of the usability series from 2026-10-07. Part 1 was split into 1a and 1b after its full and delta reviews, which covered both halves, so each part's record keeps that history; `docs/specs/2026-10-07-usability-1b-which-account-pays.md` holds the account and version checks, as W5 to W8. The two parts land on their own, in either order. Both edit `hooks/run-agent.sh`, `skills/implement/scripts/run-implementer.sh` and their tests, the README and `tests/agent-evals/BASELINE.md`, so whichever lands second merges with the first.

## Decision

- **Ledger.** Each end line records the call's session and its own cost: the result's `total_cost_usd` less the latest total the ledger already holds for that session. Rejected: summing totals (today's double count), and counting each session once at its latest total, which changes what every reader of the ledger adds up.
- **Interrupted calls.** A stopped task gives the launcher about 1.5 seconds and leaves `claude` no result (spikes S1, S5), so the launcher's trap first records the call as interrupted, charging its budget, then asks `claude` to end its turn and, if a result with its cost arrives in time, records that cost instead. The user chose on 2026-10-07 to cap each call's budget too, at $8 by default, so a call whose cost stays unknown can't use up the whole $20. Rejected: charging the budget silently (today); charging nothing, since an orphaned session may have spent it; and starting `claude` outside the launcher's process group, which would let it outlive a stopped task.

## Background

Read at `377b2dd` on 2026-10-07. Quotes from Claude Code's documentation were copied from the pages as loaded on 2026-10-07; the spec-verifier's sandbox can't reach that site, so each is marked *(unverified)*. Spike labels (S1 to S7) are part 1's, from before the split; the results file also holds the hand checks run for this part's second review.

**The ledger counts resumed calls more than once.**
- Each implementer call appends a start line with its budget (`skills/implement/scripts/run-implementer.sh:354-357`), then an end line whose `usd` is the result's `total_cost_usd`, or the budget when there is none (:372-385). The ledger's spend is the sum of the end lines, or a call's whole budget if it has none (`skills/implement/scripts/ledger.py:21-22`, `:127-128`), and each call's budget is the cap less that spend (`skills/implement/scripts/run-implementer.sh:95-99`).
- A follow-up, such as the user's answer to the implementer's question, resumes the same session (`skills/implement/scripts/run-implementer.sh:101-107`). Claude Code's cost documentation says "A call that resumes a session also counts the session's earlier spend", and that before v2.1.277 a session resumed through `claude -p` "started its totals at zero" ([cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking.md)) *(unverified)*. The README requires 2.1.277 or later (`README.md:65-68`), so the ledger was right on older versions and over-counts on every version it supports. The same page says a resumed call's `maxBudgetUsd` "counts only the call's own spend" *(unverified)*; spike S6 confirmed it for `--max-budget-usd`.
- Measured on 2026-10-07 *(outside the repo)*, in four real runs' saved results (`~/.cache/implement-runs/<run>/implementer/run-<n>.json`): each resumed call's totals included the earlier calls', and each kept the session ID of the call it resumed. One three-call run reports $1.62, $6.26 and $8.36: it spent about $8.36, and the ledger's sum is $16.24. Its second call, about $4.64 of its own, is the costliest single call in the four. Spike S6 shows the running total directly.
- The tests can't see it: the stub `claude` reports whatever cost `STUB_COST` sets for the call, never a running total, and the same session ID, `sess-1`, on every call, fresh or resumed (`tests/test_run_implementer.py:30-33`), and it counts calls by the lines in its log (:22-27). Three tests assert today's sums (`:439-454`, `:465-475`, `:506-519`); the first two resume a call, and the third runs fresh calls only.

**An interrupted call locks the spec.** `run-implementer.sh` sets no `trap`, and runs `claude` in the foreground (`skills/implement/scripts/run-implementer.sh:361-365`), where bash would hold a trap until the child exits ([bash manual](https://www.gnu.org/software/bash/manual/bash.html#Signals)) *(unverified)*. After the call it checks that the ledger's hash is unchanged (:367-371) and that git's config and hooks are, exiting 4 if not (:390-399). `/implement` starts the launcher as a background task (`skills/implement/SKILL.md:75`); stopping that task sends `TERM` to the launcher and to `claude` at once, and kills both about 1.5 seconds later (spike S5). A session closed mid-call leaves a start line with no end line, charged its whole budget (`skills/implement/scripts/ledger.py:21-22`). A spec's first call gets the whole cap as its budget (`skills/implement/scripts/run-implementer.sh:89`, `:96`), so after one interrupted first call every run is refused with "spent $20 of the $20 cap" (:98-99) until the user deletes the ledger by hand, as the ledger's usage text (`skills/implement/scripts/ledger.py:12-13`), the launcher's header (`skills/implement/scripts/run-implementer.sh:33-34`) and the README (`README.md:370-373`) all say. Claude Code's documentation says a `claude -p` run stopped with SIGTERM "records no result" for the turn in progress, and that SIGINT ends the turn instead ([headless](https://code.claude.com/docs/en/headless.md)) *(unverified)*; spike S1 observed both.

**Reports don't say what agents cost.** `run-agent.sh` ends by printing the exit code and the reply's path (`hooks/run-agent.sh:163`), and writes "no result; see run.err" as the reply when `run.json` isn't JSON (:126-129). A hand check on 2026-10-07 found that a run which exits 0 with no readable result ends on the exit 3 line instead (:158-162), which names no cost. `/research`'s report lists the note, bottom line, verification, status and commit (`skills/research/SKILL.md:135-141`), `/spec`'s the plan, verification and notes commit (`skills/spec/SKILL.md:138`), and `/cold-review` relays the table (`skills/cold-review/SKILL.md:152-158`): none names a cost. Spikes (`skills/spec/spike-step.md:78`) and `/implement` (`skills/implement/SKILL.md:103`) do. The README gives only the caps (`README.md:365-376`). Its opening says "Each `/implement` run's implementer is capped at $20 in all" (`README.md:13-14`), but the cap is per spec (:370-373), and each verifier run's own $5 cap (`skills/implement/scripts/run-verify.sh:155`) sits outside it (`skills/implement/scripts/ledger.py:22`). The cost figures are "client-side estimates, not authoritative billing data" ([cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking.md)) *(unverified)*.

## Non-goals

- Changing the cap's amount, or counting verifier runs toward the implementer's $20. The README says where each cap applies instead (W4).
- Authoritative billing. The figures stay Claude Code's estimates, and the README says so.
- Accounts and the version check, which are part 1b's.

## Design

**The ledger.** Start lines don't change: a fresh call has no session ID until its result arrives. Each line's keys, which `shape()` accepts exactly:

- end: `at`, `who`, `call`, `event: "end"` and `usd`, plus `session` (the result's `session_id`) and `total` (its `total_cost_usd`). `usd` is the call's own cost: `total` less the latest `total` an earlier line holds for the same `session`, or `total` itself when there is none, or when it is lower, as after a crash that zeroed the session's figures.
- an end with no total in the result: `usd` is the call's budget, with `"no_total": true` and no `session` or `total`.
- an interrupted end, written by `ledger.py interrupt <run name> <call> <budget>` only if the call has no end line yet: `usd` is the budget, with `"interrupted": true`.
- settled: `at`, `who`, `call`, `event: "settled"` and `usd`, plus `session` and `total` when it comes from a result, at most once per call, only for a call charged its budget (`no_total`, interrupted, or with no end line). It replaces that call's charge, and its `usd` follows the end line's rule, so a resumed call's running total isn't charged twice.

`spent` sums the implementer calls' charges. A ledger written before this change has none of the new keys and counts as today. `ledger.py report <run name>` prints one line per implementer call (its cost, and whether it came from an end line, a settled line or the budget), one line per verifier run, the implementer total that counts against the cap, and the total of all runs. `/implement`'s step 6 reads that, rather than adding up the ledger itself.

**Per-call budget.** Each call's budget is the smaller of the cap less what's spent and `IMPLEMENT_CALL_MAX_USD`, 8 by default, above the costliest call measured. A call whose cost is never known is charged at most $8, which leaves $12 of a $20 cap for the next run.

**Interruptions.** `claude` stays in the launcher's process group, as today, so nothing outlives a stopped task. The launcher runs it in the background and waits for it (`claude … & pid=$!; wait "$pid"`), so its trap runs at once: under bash 3.2 a trap runs while the script is in `wait` (spike S5). The trap is set just after the start line and cleared just after the end line. On `INT`, `TERM` or `HUP` it:

1. compares the ledger's hash with the one taken before the call, and exits 4 if the call changed it, as today;
2. runs `ledger.py interrupt`, charging the call's budget, which takes milliseconds;
3. sends `INT` to `claude`, which ends its turn with a result carrying its cost within a second if it still can, even after a second `INT` 50 ms later (spike S1 and its follow-up); waits up to `IMPLEMENT_INTERRUPT_WAIT` seconds (5 by default) for it to exit; then sends it `TERM`, and `KILL`, if it hasn't;
4. appends a `settled` line with that cost if a result came, takes the ledger's hash afresh as the new baseline, and runs the after-call check of git's config and hooks, exiting 4 if it fails;
5. otherwise exits 6, writing no reply. `/implement`'s step 4 handles 6 without reading `reply.md`: stop, and report that the call was interrupted, what it was charged, and that `/implement <spec>` carries on from the last committed work item.

A `KILL` of the launcher itself runs no trap; the next run finds a start line with no end and charges its budget, as today. Whenever unsettled calls charged their budget have spent the cap, the next run's refusal names each and `ledger.py settle <run name> <call> <usd>`, which the user runs only for a call whose cost they know, for example from the Claude Console's usage page. Nothing ever rewrites or removes a line.

**Reports.** `run-agent.sh` reads `total_cost_usd` from `run.json` and puts it on whichever line it ends with: the `finished` line, the exit 3 line, or a failure. It reads `cost $0.64`, or `cost unknown` when there is none. `hooks/run-agent.md` step 3 tells the skill to keep it, for a resumed run the latest figure only, and `/research`, `/spec` and `/cold-review` each add one report line, worded `Agents cost $<total> (<agent> $<cost>, …)`, or `Agents cost at least $<known> (<agent> unknown, …)` when any run's cost is unknown.

## Work items

### W1: the ledger counts each call's own cost

- **Change:** the end lines' new keys and per-session subtraction, as the Design says, in two commits: first `shape()` accepting every new line shape (an end with `session` and `total`, `no_total`, interrupted and settled), then the launcher writing end lines. The test stub gives each fresh run its own session ID, keeps it across `--resume`, and gains a cumulative mode that reports the session's running total, keyed on the session ID rather than the number of calls, so other stub calls, such as part 1b's `--version` answers, don't skew it. The two tests that resume a call use the cumulative mode and get the figures the new rule gives; this item asks for that change, so it isn't a weakened test. The fresh-call test keeps its figures, since each fresh call now has a session of its own.
- **Files:** `skills/implement/scripts/run-implementer.sh`, `skills/implement/scripts/ledger.py`, `tests/test_ledger.py`, `tests/test_run_implementer.py`.
- **Done when:** a new test runs a call and one `--resume` follow-up against a stub that reports $1.00 and then $1.30 for the same session, and `ledger.py spent <run name>` prints 1.3; it fails before the change, printing 2.3. The tests at `tests/test_run_implementer.py:439-454` and `:465-475` pass with their new expected figures, and the one at `:506-519` passes unchanged. A ledger file from before the change still reads as it did; one with each new line shape reads too, and an end line with an unknown key is still refused. `python3 -m unittest discover -s tests` passes.

### W2: an interrupted call is stopped and charged what it cost

- **Change:** the per-call budget and `IMPLEMENT_CALL_MAX_USD`, checked as `IMPLEMENT_MAX_USD` is (`skills/implement/scripts/run-implementer.sh:89-91`), an empty value meaning 8; `claude` run in the background and waited for; the trap, set after the start line and cleared after the end line, with its five steps; `IMPLEMENT_INTERRUPT_WAIT`; `ledger.py interrupt`, `settle` and `report`, named in `ledger.py`'s usage text and the launcher's header in place of removing the ledger by hand; the refusal naming each unsettled call charged its budget; exit 6 in `/implement`'s step 4, which reads nothing for it; and step 6 reading `ledger.py report`, which W2 adds to its `allowed-tools`, instead of adding up the ledger's lines itself. The tests' shared environment (`tests/test_run_implementer.py:59-71`) clears `IMPLEMENT_CALL_MAX_USD` from the caller's, as it does `IMPLEMENT_MAX_USD`, and sets it to 100, so the tests that expect a budget or charge above 8 (`:197`, `:452`, `:534`, `:536-545`, `:559-577`) keep their figures, which test the cap less what's spent; W2's own tests remove it to get the default.
- **Files:** `skills/implement/scripts/run-implementer.sh`, `skills/implement/scripts/ledger.py`, `skills/implement/SKILL.md` (exit 6 in step 4, whose list ends today with "Any other: stop", `skills/implement/SKILL.md:76-84`; the step 6 report, `:103`), `tests/test_run_implementer.py`, `tests/test_ledger.py`, `tests/test_implement_skill.py`.
- **Done when:** new tests, with `IMPLEMENT_INTERRUPT_WAIT=1`, start `run-implementer.sh` in a process group of its own (`start_new_session`) with a stub `claude` that sets its own `INT` handler, since a child started with `&` from a script begins with `INT` ignored. With the cap at 20 and `IMPLEMENT_CALL_MAX_USD` unset or empty, a first call gets `--max-budget-usd 8`; set to each value `test_a_bad_cap_is_refused` tries (`tests/test_run_implementer.py:521-534`), the launcher exits 2 naming the variable, before any call. Sending `TERM` to the group, then `KILL` 1.5 seconds later, as stopping the task does, leaves an interrupted end line charging 8, no stub running, and a next run that starts with 12 left. Sending `INT` to the launcher alone, with a stub that prints a result costing $0.40, leaves that end line, a `settled` line of 0.4, and exit 6; with a stub that ignores `INT`, the stub gets `TERM` and then `KILL` after the wait; for a resumed call whose stub reports a running total, the settled line charges only the call's own share. A ledger changed during an interrupted call still gives exit 4. At the cap, a ledger holding a start line with no end line, a `no_total` end or an interrupted end gets a refusal naming `ledger.py settle`; after `settle` with 0.4, `spent` drops by the difference. `ledger.py interrupt` on a call that already has an end line adds nothing. `report` shows a settled call, lists the verifier lines, and prints an implementer total equal to `spent` and a total of all runs. A test in `tests/test_implement_skill.py` finds exit 6 in step 4 and `ledger.py report` in step 6 and in `allowed-tools`. The signal tests pass ten runs in a row, and so do the unit tests, the existing ones in `tests/test_run_implementer.py` with their figures as W1 left them.

### W3: every report says what its agents cost

- **Change:** the cost on each line `run-agent.sh` can end with, `cost unknown` included, step 3 of `hooks/run-agent.md`, and one cost line in the reports of `/research` (its step 10), `/spec` (step 6 item 1, and step 5 item 7 for quick mode) and `/cold-review` (step 5), worded as the Design says.
- **Files:** `hooks/run-agent.sh`, `hooks/run-agent.md`, `skills/research/SKILL.md`, `skills/spec/SKILL.md`, `skills/cold-review/SKILL.md`, `tests/test_run_agent.py`, `tests/skill-evals/cases/research-quick-flow/grade.py`, `tests/skill-evals/cases/spec-quick/grade.py`.
- **Done when:** new tests run `run-agent.sh` with a stub whose `run.json` reports 0.42 and find `cost $0.42` on its last line; with a stub that exits 0 printing something that isn't JSON, its exit 3 line ends `cost unknown`; and with one that exits 1, its `finished` line does. The two graders check that the session's final reply has a line matching `Agents cost (at least )?\$[0-9]`, and both cases pass on Sonnet and Opus.

### W4: the README and the repo's records say what things cost

- **Change:** under Safety and cost: the implementer's cap is per spec, the opening line is fixed to say so, each call's budget is capped at $8 (`IMPLEMENT_CALL_MAX_USD`), a call whose cost is unknown can be settled with `ledger.py settle` rather than by deleting the ledger, and verifier runs sit outside the cap; the figures are estimates, and on a subscription they measure usage against the plan rather than a bill; a short table of typical cost and time per command, taken from the `total_cost_usd` and `duration_ms` in the `run.json` files of this part's own eval runs, with their date, and a note that the session running the command costs extra; and where to set `IMPLEMENT_MAX_USD`, `IMPLEMENT_CALL_MAX_USD`, `RUN_AGENT_MAX_USD` and `RUN_AGENT_MODEL` (the shell that starts Claude Code, or `env` in `~/.claude/settings.json`). `docs/containment.md` gets the same per-spec wording and the verifier caveat, where it says the implementer is "capped at $20 for every run of a spec" (`docs/containment.md:71-72`), and `tests/agent-evals/BASELINE.md` gets the dated section the repo's rules ask for, with every eval case's result and cost on both models.
- **Files:** `README.md`, `records/README-record.md`, `docs/containment.md`, `tests/agent-evals/BASELINE.md`.
- **Done when:** neither the README's opening nor `docs/containment.md` calls the $20 a per-run cap; `grep -n 'ledger.py settle' README.md` and `grep -n 'IMPLEMENT_CALL_MAX_USD' README.md` each find a line; the table names its date and source; `records/README-record.md` ends with a dated `- Not reviewed:` line for the change; and `BASELINE.md` has a 2026-10 dated section naming every case run for this part, with its result and cost.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 3 h, two tests rewritten | none |
| W2 | 5 h | W1 |
| W3 | 2 h | none |
| W4 | 1 h | W1 to W3 |
| Evals | both eval sets on both models; the implement cases too | W1 to W4 |

The hours are guesses from reading the scripts; the order matters more. W2 and W3 change skill files and an agent launcher, so the repo's rules ask for both eval sets on Sonnet and Opus, and the implement cases, whose implementer and verifiers the runner's printed cost leaves out (`CLAUDE.md:23-38`). Both sets on both models cost $15.23 on 2026-10-04, and the implement cases $3.00 of that (`docs/repo-guide.md:108-109`).

## Spike questions

Each needed the Claude API or a live session, so all were run by hand on 2026-10-07, before part 1 was split. Each question gives its part 1 label, which the results file uses.

1. (S1) When a `claude -p --output-format json` call is sent `INT` partway through, which the documentation says ends the turn, does it print its JSON result, with `total_cost_usd`, and how long does that take? Experiment: by hand, signal one while a 30-second Bash command runs, with `INT` and then `TERM`, and read what reaches stdout.
   Answered: `INT` ends the call at once with a result carrying its cost, as an error result with exit 0, even with a second `INT` 50 ms later; `TERM` exits 143 with no result (spike S1 and its follow-up, `docs/specs/spikes/2026-10-07-usability-1-costs-and-accounts-results.md`)
2. (S5) Which signal reaches `run-implementer.sh`, started by `/implement` as a background task, when the user stops the task or closes the session, and does its `claude` child get one directly too? Experiment: by hand, a background task whose script and child log each signal they get; stop the task, then close the session. No entry means `KILL`.
   Partly answered: stopping the task sends `TERM` to the launcher and to `claude` at once, then kills both about 1.5 seconds later; closing the session wasn't tried (spike S5, `docs/specs/spikes/2026-10-07-usability-1-costs-and-accounts-results.md`)
3. (S6) Does `--max-budget-usd` on a resumed `claude -p` call count only that call's spend, as the documentation says of `maxBudgetUsd`? Experiment: by hand, resume a call with a `--max-budget-usd` below what it has spent, on a prompt that needs several turns, and see whether it stops after its first turn.
   Answered: only its own; a resumed call ran seven turns on a budget below the session's earlier spend (spike S6, `docs/specs/spikes/2026-10-07-usability-1-costs-and-accounts-results.md`)

## Risks and rollback

- Closing the session wasn't tried (spike S5). If it kills the launcher outright, the next run charges the call's budget, at most $8, and names `ledger.py settle`, as for any call with no end line.
- Part 1a merges as one branch, so its reader and writer arrive together. Today's reader accepts only exact key sets (`skills/implement/scripts/ledger.py:67-78`), so rolling back past that merge means it refuses every ledger written since, and those ledgers have to be deleted, losing their spend history.
- The signal tests depend on timing, and CI runs them on macOS under bash 3.2 (`.github/workflows/tests.yml:16-22`). W2's Done when asks for ten clean runs in a row; if CI is slower, its waits are the place to look.

## Open questions

- Should verifier runs count toward the implementer's cap, so one figure bounds a spec's whole spend? This part keeps them apart and documents it.

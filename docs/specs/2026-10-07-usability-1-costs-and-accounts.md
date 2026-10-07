---
title: "Usability, part 1: what runs cost, and which account pays"
created: 2026-10-07
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 377b2dd
cite-repo: none
---

# Usability, part 1: what runs cost, and which account pays

## Goal

`/implement`'s ledger counts what each implementer call really cost, and an interrupted call no longer locks a spec at its cap. Every command's report says what its agents cost. Every headless session the plugin starts runs on the user's Claude account, not on an `ANTHROPIC_API_KEY` that happens to be set in their shell, unless they choose API billing. The launchers refuse a Claude Code older than the version the sandbox and the ledger rely on.

This is part 1 of 7, from a usability review on 2026-10-07. Part 2 covers `/implement` on real repos, part 3 setup, part 4 configurable folders, part 5 what the agents can reach, part 6 specs, reviews and spikes, and part 7 guidance and tests. Each lands on its own. This one goes first because later parts' reports reuse its cost line and its launch checks.

## Decision

- **Ledger.** Each end line records the call's session and its own cost: the result's `total_cost_usd` less the latest total the ledger already holds for that session. Rejected: summing totals (today's double count), and counting each session once at its latest total, which changes what every reader of the ledger adds up.
- **Interrupted calls.** The launcher forwards an interruption to its `claude` child, waits briefly for its result, records the cost the result reports, and stops the child if it is still running. Only when no result arrives is the call charged its budget, as today, and then the refusal says how to settle it. Rejected: charging the budget silently (today), and charging nothing, since an orphaned session may have spent it.
- **Accounts.** On 2026-10-07 the user chose: each launcher removes `ANTHROPIC_API_KEY` from its headless session's environment, so the session uses the user's `/login` account or a `CLAUDE_CODE_OAUTH_TOKEN`; `CHECKED_PLANS_USE_API_KEY=1` keeps the key for someone who wants API billing; and a run with no account to use stops and says how to fix it. Rejected: refusing while the key is set, which blocks API-only users, and warning only, which bills the key by default. `ANTHROPIC_AUTH_TOKEN` and the cloud-provider variables are left alone: they are a route an organization chose, not a stray key.
- **Version.** Each launcher checks `claude --version` once, before anything else, and refuses below 2.1.277.

## Background

Read at `377b2dd` on 2026-10-07.

**The ledger counts resumed calls more than once.**
- Each implementer call appends a start line with its budget (`skills/implement/scripts/run-implementer.sh:354-357`), then an end line whose `usd` is the result's `total_cost_usd` (:372-385). The ledger's spend is the sum of the end lines, or a call's whole budget if it has none (`skills/implement/scripts/ledger.py:21-22`, `:127-128`), and each call's budget is the cap less that spend (`skills/implement/scripts/run-implementer.sh:95-99`).
- A follow-up, such as the user's answer to the implementer's question, resumes the same session (`skills/implement/scripts/run-implementer.sh:100-106`). Claude Code's cost documentation says "A call that resumes a session also counts the session's earlier spend" and "summing results double-counts the restored spend", and that before v2.1.277 a session resumed through `claude -p` "started its totals at zero" ([cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking.md)). The README requires 2.1.277 or later (`README.md:65-68`), so the ledger was right on older versions and over-counts on every version it supports.
- Measured on 2026-10-07 *(outside the repo)*: in four real runs' saved results, `~/.cache/implement-runs/<run>/implementer/run-<n>.json`, each resumed call's `modelUsage` output and cache-read token counts equal the previous call's plus that call's own `usage`, exactly. One three-call run's results report $1.62, $6.26 and $8.36. It spent about $8.36; the ledger's sum is $16.24.
- The tests can't see it: the stub `claude` reports the same fixed cost on every call of one session (`tests/test_run_implementer.py:30-33`).

**An interrupted call locks the spec.** `run-implementer.sh` sets no `trap`, so a session closed mid-call leaves a start line with no end line, charged its whole budget (`skills/implement/scripts/ledger.py:21-22`). A spec's first call gets the whole cap as its budget (`skills/implement/scripts/run-implementer.sh:89`, `:96`), so after one interrupted first call every run is refused with "spent $20 of the $20 cap" (:98-99) until the user deletes the ledger by hand. Claude Code's documentation says a `claude -p` run stopped with SIGTERM "records no result" for the turn in progress, and that SIGINT ends the turn instead ([headless](https://code.claude.com/docs/en/headless.md)).

**Reports don't say what agents cost.** `run-agent.sh` ends by printing the exit code and the reply's path (`hooks/run-agent.sh:163`). `/research`'s report lists the note, bottom line, verification, status and commit (`skills/research/SKILL.md:135-141`), `/spec`'s the plan, verification and notes commit (`skills/spec/SKILL.md:138`), and `/cold-review` relays the table (`skills/cold-review/SKILL.md:152-158`): none names a cost. Spikes (`skills/spec/spike-step.md:78`) and `/implement` (`skills/implement/SKILL.md:103`) do. The README gives only the caps (`README.md:365-376`). Its opening says "Each `/implement` run's implementer is capped at $20 in all" (`README.md:13-14`), but the cap is per spec (:370-373), and each verifier run's own $5 cap (`skills/implement/scripts/run-verify.sh:155`) sits outside it (`skills/implement/scripts/ledger.py:22`). The cost figures are "client-side estimates, not authoritative billing data" ([cost tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking.md)).

**An API key in the shell decides who pays.**
- Claude Code's authentication order puts `ANTHROPIC_API_KEY` third, above `apiKeyHelper`, `CLAUDE_CODE_OAUTH_TOKEN` and the `/login` subscription, and says "In non-interactive mode (`-p`), the key is always used when present" ([authentication](https://code.claude.com/docs/en/authentication.md)).
- Every launcher runs `claude -p` with the caller's environment and unsets nothing: `hooks/run-agent.sh:115-119`, `skills/spec/scripts/run-spike.sh:56`, `skills/implement/scripts/run-implementer.sh:361-365`, `skills/implement/scripts/run-verify.sh:151`, `tests/agent-evals/run.sh:125` and `tests/skill-evals/run.sh:97`. They load the user's settings with `--setting-sources user` (`hooks/run-agent.sh:118`), so a user's `apiKeyHelper` applies too.
- The sandbox settings hide `ANTHROPIC_API_KEY` from the agents' shell commands (`hooks/agent-sandbox.json:18-27`), and tests keep the spike's, the verifier's and the implementer's lists the same (`tests/test_sandbox_settings.py:132-135`, `:154-156`, `:188-190`). That keeps the key from the agents' commands, not from the session it bills: the deny mode applies to "sandboxed commands" ([settings reference](https://code.claude.com/docs/en/settings-reference.md)). Neither `CLAUDE_CODE_OAUTH_TOKEN` nor `ANTHROPIC_AUTH_TOKEN` is on the list.
- `claude setup-token` makes "a one-year OAuth token" that "authenticates with your Claude subscription and requires a Pro, Max, Team, or Enterprise plan"; it is read from `CLAUDE_CODE_OAUTH_TOKEN`, though not in bare mode ([authentication](https://code.claude.com/docs/en/authentication.md)). No launcher passes `--bare`.
- CI runs no model calls: the unit tests, ruff, shellcheck and `claude plugin validate` (`.github/workflows/tests.yml:22-41`).

**Nothing checks the version.** The README says the sandbox rule holds from 2.1.277 on (`README.md:65-68`), and no launcher runs `claude --version`.

## Non-goals

- Changing the caps' amounts, or counting verifier runs toward the implementer's $20. The README says where each cap applies instead (W7).
- Authoritative billing. The figures stay Claude Code's estimates, and the README says so.
- Choosing for an organization. Cloud-provider settings and `ANTHROPIC_AUTH_TOKEN` keep working as they do today.
- CI. It makes no model calls, so it needs no account.

## Design

A new file, `hooks/launch-checks.sh`, is sourced by `hooks/run-agent.sh`, `skills/spec/scripts/run-spike.sh`, `skills/implement/scripts/run-implementer.sh`, `skills/implement/scripts/run-verify.sh` and both eval runners, before they start `claude`. It does three things.

1. **Version.** It runs `claude --version` once and compares the first field with 2.1.277. Below it, or unreadable, the launcher exits 2 with `needs Claude Code 2.1.277 or later; this is <version>`.
2. **Account.** Unless `CHECKED_PLANS_USE_API_KEY=1` is set, it unsets `ANTHROPIC_API_KEY` and, if one was set, prints one line: `<launcher>: this run uses your Claude account, not ANTHROPIC_API_KEY (set CHECKED_PLANS_USE_API_KEY=1 to bill the key)`. If the user's `~/.claude/settings.json` sets `apiKeyHelper` and the opt-in isn't set, the launcher exits 2 and says so, unless spike question 3 finds a way to switch the helper off for the run.
3. **No account.** After the run, if the result is an authentication failure (its wording comes from spike question 2), the launcher prints: run `/login` in Claude Code, or `claude setup-token` and set `CLAUDE_CODE_OAUTH_TOKEN`, or set `CHECKED_PLANS_USE_API_KEY=1`. `run-agent.sh` exits 5 for it, so the skills can relay it rather than treat it as an empty reply.

**The ledger.** `run-implementer.sh` writes the session ID on each start and end line. `ledger.py` keeps, per session, the latest total it has seen, and an end line's `usd` becomes `total_cost_usd` less that total. A ledger written before this change has no session fields; its calls count as today. On an interruption (`INT`, `TERM` or `HUP`), the launcher sends `INT` to its `claude` child, so it ends its turn rather than dropping it, waits up to 20 seconds, then sends `TERM`, and `KILL` if it's still running. If `run.json` then holds a total, the end line records the call's cost and `"interrupted": true`. If not, it records the budget, as today, and the next refusal names the call and says how to settle it: `ledger.py settle <run name> <call> <usd>` appends a `settled` line, which the user writes only for a call they know the cost of, for example from the Claude Console's usage page. Nothing ever rewrites or removes a line.

**Reports.** `run-agent.sh` reads `total_cost_usd` from `run.json` and prints it on its last line, `run-agent: <agent> finished (exit 0); cost $0.64; reply in …`. `hooks/run-agent.md` step 3 tells the skill to keep it, for a resumed run the latest figure only, and `/research`, `/spec` and `/cold-review` each add one report line: what their agents cost, in total and by agent.

## Work items

### W1: the ledger counts each call's own cost

- **Change:** session-aware end lines and per-session subtraction, as the Design says. Teach the test stub a cumulative mode that reports a session's running total.
- **Files:** `skills/implement/scripts/run-implementer.sh`, `skills/implement/scripts/ledger.py`, `tests/test_ledger.py`, `tests/test_run_implementer.py`.
- **Done when:** a new test runs a call and one `--resume` follow-up against a stub that reports $1.00 and then $1.30 for the same session, and `ledger.py spent <run name>` prints 1.3; it fails before the change, printing 2.3. A ledger file from before the change still reads as it did. `python3 -m unittest discover -s tests` passes.

### W2: an interrupted call is stopped and charged what it cost

- **Change:** the trap, the forwarded signal and `ledger.py settle`, as the Design says, and the refusal message that names the call and the settle command.
- **Files:** `skills/implement/scripts/run-implementer.sh`, `skills/implement/scripts/ledger.py`, `skills/implement/SKILL.md` (its exit 2 handling relays the refusal unchanged), `tests/test_run_implementer.py`, `tests/test_ledger.py`.
- **Done when:** new tests send `TERM` to `run-implementer.sh` while a stub `claude` sleeps. The stub receives `INT` first. With a stub that writes a result costing $0.40 on `INT`, the end line says 0.4 and `interrupted`; with one that ignores `INT` and `TERM`, no stub process is left running 25 seconds later, the end line charges the budget, and the next run's refusal names `ledger.py settle`. After `settle` with 0.4, `spent` drops by the difference. The unit tests pass.

### W3: every report says what its agents cost

- **Change:** the cost on `run-agent.sh`'s last line, step 3 of `hooks/run-agent.md`, and one cost line in the reports of `/research` (its step 10), `/spec` (step 6 item 1, and step 5 item 7 for quick mode) and `/cold-review` (step 5).
- **Files:** `hooks/run-agent.sh`, `hooks/run-agent.md`, `skills/research/SKILL.md`, `skills/spec/SKILL.md`, `skills/cold-review/SKILL.md`, `tests/test_run_agent.py`, `tests/skill-evals/cases/research-quick-flow/grade.py`, `tests/skill-evals/cases/spec-quick/grade.py`.
- **Done when:** a new test runs `run-agent.sh` with a stub whose `run.json` reports 0.42 and finds `cost $0.42` on its last line. The two graders check that the session's final reply names a dollar figure for its agents, and both cases pass on Sonnet and Opus.

### W4: headless sessions run on the account

- **Change:** `hooks/launch-checks.sh`'s account step, sourced by all six launchers, and a line in `hooks/run-agent.md` step 3 for exit 5: stop, and relay the launcher's account guidance.
- **Files:** `hooks/launch-checks.sh` (new), `hooks/run-agent.sh`, `hooks/run-agent.md`, `skills/spec/scripts/run-spike.sh`, `skills/implement/scripts/run-implementer.sh`, `skills/implement/scripts/run-verify.sh`, `tests/agent-evals/run.sh`, `tests/skill-evals/run.sh`, `tests/test_launch_checks.py` (new).
- **Done when:** a new test runs each of the four plugin launchers with `ANTHROPIC_API_KEY=dummy` and a stub `claude` that records its environment: the stub never sees the key, and each launcher prints the one-line note. With `CHECKED_PLANS_USE_API_KEY=1` the stub sees it and no note prints. A user settings file with `apiKeyHelper` and no opt-in makes each launcher exit 2 naming it. A stub that fails as spike question 2 found makes `run-agent.sh` exit 5 with the account guidance. The unit tests pass.

### W5: account and gateway tokens are hidden from agents' commands

- **Change:** add `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_AUTH_TOKEN` to every `sandbox.credentials.envVars` list, in deny mode.
- **Files:** `hooks/agent-sandbox.json`, `skills/spec/spike-settings.json`, `skills/implement/implementer-settings.json`, `skills/implement/verify-settings.json`, `tests/skill-evals/agent-case-settings.json`, `tests/test_sandbox_settings.py`.
- **Done when:** a new test fails if any of those files' `envVars` lacks either name, and fails before the change; the existing agreement tests in `tests/test_sandbox_settings.py` still pass.

### W6: the launchers refuse an old Claude Code

- **Change:** `hooks/launch-checks.sh`'s version step.
- **Files:** `hooks/launch-checks.sh`, `tests/test_launch_checks.py`.
- **Done when:** with a stub whose `--version` prints `2.1.276 (Claude Code)`, each plugin launcher exits 2 with `needs Claude Code 2.1.277 or later`, and `claude -p` is never called; with `2.1.285 (Claude Code)` it carries on. The unit tests pass.

### W7: the README says what things cost and who pays

- **Change:** under Safety and cost: the implementer's cap is per spec, the opening line is fixed to say so, and verifier runs sit outside it; the figures are estimates, and on a subscription they measure usage against the plan rather than a bill; a short table of typical cost and time per command, with the date it was measured and how; where to set `IMPLEMENT_MAX_USD`, `RUN_AGENT_MAX_USD` and `RUN_AGENT_MODEL` (the shell that starts Claude Code, or `env` in `~/.claude/settings.json`); and the account rule, with `claude setup-token` and `CHECKED_PLANS_USE_API_KEY=1`. Under Requirements: a Claude account, or an API key by choice.
- **Files:** `README.md`, `records/README-record.md`.
- **Done when:** `grep -n 'setup-token' README.md` and `grep -n 'CHECKED_PLANS_USE_API_KEY' README.md` each find a line; the opening no longer calls the $20 a per-run cap; the table names its measurement date; `records/README-record.md` ends with a dated `- Not reviewed:` line for the change.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 2 h | none |
| W2 | 3 h, after spike question 1 | W1 |
| W3 | 2 h | none |
| W4 | 3 h, after spike questions 2 and 3 | W6, for the shared file |
| W5 | 30 min | none |
| W6 | 1 h | none |
| W7 | 1 h | W1 to W6 |
| Evals | agent and skill evals on both models; the implement cases too | W1 to W7 |

The hours are guesses from reading the scripts; the order matters more. W2, W3 and W4 change skill and agent-launch files, so the repo's rules ask for both eval sets on Sonnet and Opus, and the implement cases (`CLAUDE.md:23-37`). Both sets on both models cost $15.23 on 2026-10-04 (`docs/repo-guide.md:108-109`).

## Spike questions

1. When a `claude -p --output-format json` call is sent `INT` partway through, which the documentation says ends the turn, does it print its JSON result, with `total_cost_usd`, and how long does that take? Experiment: by hand, start one on a prompt that runs `sleep 30` through Bash, send `INT` after 10 seconds, and read what reaches stdout; then the same with `TERM`, which should print no result. This needs the model API, which the spike sandbox can't reach.
2. What do a `claude -p` call's result JSON and stderr say when it has no account to use (no key, no login) and when its login has expired? Experiment: by hand, run `env -u ANTHROPIC_API_KEY CLAUDE_CONFIG_DIR=<an empty temporary folder> claude -p --output-format json hi`, whose login lookup finds nothing, and keep both outputs.
3. Can a `--settings` file switch off an `apiKeyHelper` set in the user's settings for one run, for example with `"apiKeyHelper": ""`? Experiment: by hand, set a helper that touches a marker file and prints a dummy key, run `claude -p --settings <file> hi` with and without the override, and see whether the marker appears.

## Risks and rollback

- Someone with only an API key sees the one-line note, then an account error, until they set `CHECKED_PLANS_USE_API_KEY=1`. The error says so in one line.
- A `claude --version` format Claude Code changes later would refuse every run. The refusal prints what it read, so the fix is obvious; rollback is reverting `hooks/launch-checks.sh`.
- The ledger keeps its old lines readable, so rolling back W1 or W2 loses nothing already written.

## Open questions

- Should verifier runs count toward the implementer's cap, so one figure bounds a spec's whole spend? This part keeps them apart and documents it.

---
title: "Usability, part 1b: which account pays"
created: 2026-10-07
status: in-progress # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 377b2dd
cite-repo: none
---

# Usability, part 1b: which account pays

## Goal

Every headless session the plugin starts runs on the user's Claude account, not on an `ANTHROPIC_API_KEY` that happens to be set in their shell or settings, unless they choose API billing. The account and gateway tokens are hidden from the agents' sandboxed commands. The launchers refuse a Claude Code older than the version the sandbox and the ledger rely on, and the README says who pays.

Part 1b of the usability series from 2026-10-07. Part 1 was split into 1a and 1b after its full and delta reviews, which covered both halves, so each part's record keeps that history; `docs/specs/2026-10-07-usability-1a-what-runs-cost.md` holds the ledger and cost reports as W1 to W4, and this part's work items go on from W5. The two parts land on their own, in either order. Both edit `hooks/run-agent.sh`, `skills/implement/scripts/run-implementer.sh` and their tests, the README and `tests/agent-evals/BASELINE.md`, so whichever lands second merges with the first. Part 2's start-up checks reuse this part's launch checks.

## Decision

- **Accounts.** On 2026-10-07 the user chose: each launcher removes `ANTHROPIC_API_KEY` from its headless session's environment, so the session uses the user's `/login` account or a `CLAUDE_CODE_OAUTH_TOKEN`; `CHECKED_PLANS_USE_API_KEY=1` keeps the key for someone who wants API billing; and a run with no account to use stops and says how to fix it. Rejected: refusing while the key is set, which blocks API-only users, and warning only, which bills the key by default. `ANTHROPIC_AUTH_TOKEN` and the cloud-provider variables are left alone: they are a route an organization chose, not a stray key.
- **Version.** Each launcher checks `claude --version` once, before anything else, and refuses below 2.1.277.

## Background

Read at `377b2dd` on 2026-10-07. Quotes from Claude Code's documentation were copied from the pages as loaded on 2026-10-07; the spec-verifier's sandbox can't reach that site, so each is marked *(unverified)*. Spike labels (S1 to S7) are part 1's, from before the split; the results file also holds the hand checks run for this part's second review.

**An API key in the shell decides who pays.**
- Claude Code's authentication order puts `ANTHROPIC_API_KEY` third, above `apiKeyHelper`, `CLAUDE_CODE_OAUTH_TOKEN` and the `/login` subscription, and says "In non-interactive mode (`-p`), the key is always used when present" ([authentication](https://code.claude.com/docs/en/authentication.md)) *(unverified)*. Spike S4 observed it: a made-up key beat a working login, with and without the agents' sandbox settings.
- Every launcher runs `claude -p` with the caller's environment and unsets nothing: `hooks/run-agent.sh:115-119`, `skills/spec/scripts/run-spike.sh:56`, `skills/implement/scripts/run-implementer.sh:361-365`, `skills/implement/scripts/run-verify.sh:151`, `tests/agent-evals/run.sh:125` and `tests/skill-evals/run.sh:97`. The plugin launchers and the agent-eval runner load the user's settings with `--setting-sources user` (`hooks/run-agent.sh:118`, `skills/spec/scripts/run-spike.sh:56`, `skills/implement/scripts/run-implementer.sh:363`, `skills/implement/scripts/run-verify.sh:151`, `tests/agent-evals/run.sh:128`), and the skill-eval runner passes no `--setting-sources`, so it loads project settings too (`tests/skill-evals/run.sh:97-98`). Either way a user's `apiKeyHelper` applies, and so does a key in their settings' `env` block: a hand check on 2026-10-07 found that key used although the shell variable was unset, and found `--settings '{"env": {"ANTHROPIC_API_KEY": ""}}'` clears it.
- The settings each passes come from different places: `run-verify.sh` passes the plugin's own `verify-settings.json` (`skills/implement/scripts/run-verify.sh:136`), `run-spike.sh` the `settings.json` that `/spec` writes into the spike's scratch folder (`tests/test_run_spike.py:91-94`), and the agent-eval runner a rendered copy, or none at all when `EVAL_SETTINGS` is empty (`tests/agent-evals/run.sh:59`, `:118-124`). Tests hold each of these: the verifier's path (`tests/test_prepare_verify.py:677-679`), the runners' rendered copies, compared whole (`tests/test_eval_runners.py:176-206`, used at `:307` and `:488`), and the rendered copy's two top-level keys and the empty case (`:466`, `:467-470`).
- A sandboxed run can write its own scratch folder, so `run-verify.sh` and `run-spike.sh` clear their output files before writing them, in case an earlier run left a link there (`skills/implement/scripts/run-verify.sh:140-144`; `skills/spec/scripts/run-spike.sh:49-54`). A hand check on 2026-10-07 found that a run keeps the sandbox it started with: a write refused at the start was still refused 15 seconds after its `--settings` file was rewritten with the sandbox off.
- The sandbox settings hide `ANTHROPIC_API_KEY` from the agents' shell commands (`hooks/agent-sandbox.json:18-27`), and tests keep the spike's, the verifier's and the implementer's lists the same (`tests/test_sandbox_settings.py:132-135`, `:154-156`, `:188-190`). That keeps the key from the agents' commands, not from the session it bills: the deny mode applies to "sandboxed commands" ([settings reference](https://code.claude.com/docs/en/settings-reference.md)) *(unverified)*; spikes S4 and S7 observed it. Neither `CLAUDE_CODE_OAUTH_TOKEN` nor `ANTHROPIC_AUTH_TOKEN` is on the list. In the skill evals, `run-agent.sh` runs as an excluded command, outside the sandbox (`tests/skill-evals/agent-case-settings.json:5`), and spike S7 found that a denied variable still reaches such a command.
- `/implement` sends one follow-up when its launcher exits 3 (`skills/implement/SKILL.md:81`), and stops on any code it doesn't name, for the implementer and for the verifier (`:84`, `:95`).
- `claude setup-token` makes "a one-year OAuth token" for a Pro, Max, Team or Enterprise plan, read from `CLAUDE_CODE_OAUTH_TOKEN` except in bare mode ([authentication](https://code.claude.com/docs/en/authentication.md)) *(unverified)*. No launcher passes `--bare`.
- CI runs no model calls: the unit tests, ruff, shellcheck at warning level and `claude plugin validate` (`.github/workflows/tests.yml:22-41`).

**Nothing checks the version.** The README says the sandbox rule holds from 2.1.277 on (`README.md:65-68`), and no launcher runs `claude --version`.

## Non-goals

- Choosing for an organization. Cloud-provider settings and `ANTHROPIC_AUTH_TOKEN` keep working as they do today.
- CI. It makes no model calls, so it needs no account.
- The ledger and cost reports, which are part 1a's.

## Design

A new file, `hooks/launch-checks.sh`, is sourced by `hooks/run-agent.sh`, `skills/spec/scripts/run-spike.sh`, `skills/implement/scripts/run-implementer.sh`, `skills/implement/scripts/run-verify.sh` and both eval runners, before they start `claude`. It starts with `# shellcheck shell=bash`, and each `source` line carries a `# shellcheck source=` directive. It does three things.

1. **Version.** It runs `claude --version` once and compares the first field with 2.1.277. Below it, or unreadable, the launcher exits 2 with `needs Claude Code 2.1.277 or later; this is <version>`.
2. **Account.** Unless `CHECKED_PLANS_USE_API_KEY=1` is set, it unsets `ANTHROPIC_API_KEY` and, if one was set, prints one line: `<launcher>: this run uses your Claude account, not ANTHROPIC_API_KEY (set CHECKED_PLANS_USE_API_KEY=1 to bill the key)`. Unless the opt-in is set, the settings the launcher passes also carry `"apiKeyHelper": ""` and `"env": {"ANTHROPIC_API_KEY": ""}`, which switch off a helper the user's settings name (spike S3) and a key in their `env` block. A function in `hooks/launch-checks.sh`, `account_settings <from> <to>`, writes the settings with those keys added, clearing `<to>` first and writing it without following links:
   - over the copy it renders already, for `run-agent.sh`, `run-implementer.sh` and the skill-eval runner;
   - as a new file beside the run's folder, not inside it, for `run-verify.sh` (`V<n>.settings.json` beside `V<n>/`) and `run-spike.sh` (`S<n>.settings.json` beside `S<n>/`), so the sandboxed run can't leave a link at that name or rewrite the file, and `skills/spec/spike-step.md` still copies the spike's settings unchanged;
   - over its rendered copy, for the agent-eval runner, or as `--settings '{"apiKeyHelper": "", "env": {"ANTHROPIC_API_KEY": ""}}'` alone when `EVAL_SETTINGS` is empty.
3. **No account.** After the run, if the result has `is_error: true` and its text begins `Not logged in`, `Failed to authenticate`, `Invalid API key` or `Login expired` (spikes S2 to S4, `Login expired` being the authentication documentation's wording *(unverified)*; `subtype` still says `success`), the launcher prints: run `/login` in Claude Code, or `claude setup-token` and set `CLAUDE_CODE_OAUTH_TOKEN`, or set `CHECKED_PLANS_USE_API_KEY=1`. Each of the four plugin launchers exits 5 for it, deciding that before `run-agent.sh`'s reply-shape check, and `/implement` (steps 4 and 5) and `/spec`'s spike step stop and relay it, rather than send a follow-up to a session that has no account.

## Work items

### W5: headless sessions run on the account

- **Change:** `hooks/launch-checks.sh`'s account step and `account_settings`, sourced by all six launchers, as the Design says; exit 5 in all four plugin launchers and their headers, which say today that any other exit is `claude`'s own (`hooks/run-agent.sh:17`; `skills/implement/scripts/run-verify.sh:18-20`); a line for exit 5 in `hooks/run-agent.md` step 3, in `/implement`'s steps 4 and 5, and in `skills/spec/spike-step.md`'s step 7c: stop, and relay the launcher's account guidance. The tests that hold today's settings paths and keys change to match.
- **Files:** `hooks/launch-checks.sh` (new), `hooks/run-agent.sh`, `hooks/run-agent.md`, `skills/spec/scripts/run-spike.sh`, `skills/spec/spike-step.md`, `skills/implement/scripts/run-implementer.sh`, `skills/implement/scripts/run-verify.sh`, `skills/implement/SKILL.md`, `tests/agent-evals/run.sh`, `tests/skill-evals/run.sh`, `tests/test_launch_checks.py` (new), `tests/test_prepare_verify.py`, `tests/test_run_spike.py`, `tests/test_eval_runners.py`, `tests/test_implement_skill.py`.
- **Done when:** a new test runs each of the six launchers with `ANTHROPIC_API_KEY=dummy` and a stub `claude` that records its environment and the settings it was given: the stub never sees the key, its settings carry `"apiKeyHelper": ""` and `"env": {"ANTHROPIC_API_KEY": ""}`, and each plugin launcher prints the one-line note. The verifier's and the spike's copies sit beside their run's folder; a link left at a copy's name is replaced, not followed; and nothing is written under the plugin root. The agent-eval runner with `EVAL_SETTINGS` empty passes the override alone. With `CHECKED_PLANS_USE_API_KEY=1` the stub sees the key and gets no override, and no note prints. A stub that prints `{"subtype": "success", "is_error": true, "result": "Not logged in · Please run /login"}` and exits 1, as S2 saw, makes each plugin launcher exit 5 with the account guidance. A test in `tests/test_implement_skill.py` finds exit 5 in `/implement`'s steps 4 and 5. `shellcheck -S warning` passes on every changed script; the changed assertions in `tests/test_prepare_verify.py`, `tests/test_run_spike.py` and `tests/test_eval_runners.py` pass, and so do the unit tests.

### W6: account and gateway tokens are hidden from agents' commands

- **Change:** add `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_AUTH_TOKEN` to every `sandbox.credentials.envVars` list, in deny mode. A denied variable still reaches a command the settings exclude from the sandbox (spike S7), so an eval's `run-agent.sh` keeps the account; so do the agents' own excluded commands, `gh` and the three research scripts, whose use of variables the guard already refuses (`hooks/agents/researcher.md:78`).
- **Files:** `hooks/agent-sandbox.json`, `skills/spec/spike-settings.json`, `skills/implement/implementer-settings.json`, `skills/implement/verify-settings.json`, `tests/skill-evals/agent-case-settings.json`, `tests/test_sandbox_settings.py`.
- **Done when:** a new test fails if any of those files' `envVars` lacks either name, and fails before the change; the existing agreement tests in `tests/test_sandbox_settings.py` still pass.

### W7: the launchers refuse an old Claude Code

- **Change:** the version step in `hooks/launch-checks.sh`, which W5 made, and a `--version` answer in every stub `claude` in the launcher tests, given before the stub logs the call, so the call counts the tests assert don't change. Each stub prints a JSON result whatever it's called with (for example `tests/test_run_agent.py:19`, `tests/test_run_spike.py:22`, `tests/test_prepare_verify.py:32`, `tests/test_eval_runners.py:31`, and the variant at `:242`), so the new check would refuse every run under them; the `not JSON` stub at `tests/test_eval_runners.py:531` answers it too, so its test still exercises a bad result.
- **Files:** `hooks/launch-checks.sh` (from W5), `tests/test_launch_checks.py`, `tests/test_run_agent.py`, `tests/test_run_spike.py`, `tests/test_prepare_verify.py`, `tests/test_eval_runners.py`, `tests/test_run_implementer.py`.
- **Done when:** with a stub whose `--version` prints `2.1.276 (Claude Code)`, each plugin launcher exits 2 with `needs Claude Code 2.1.277 or later`, and `claude -p` is never called; with `2.1.285 (Claude Code)` it carries on. Every existing launcher test passes, changed by W7 only in its stub's `--version` answer, the `not JSON` test still failing for its bad result. The unit tests pass.

### W8: the README and the repo's records say who pays

- **Change:** the account rule in the README's Safety and cost section, with `claude setup-token` and `CHECKED_PLANS_USE_API_KEY=1`, set beside the other variables there; and under Requirements, a Claude account, or an API key by choice. `docs/repo-guide.md`'s file map and the list in `CLAUDE.md` of what the unit tests cover name `hooks/launch-checks.sh` and its test, the repo guide's line on `run-agent.sh`'s exit codes adds 5 (`docs/repo-guide.md:47`), and `tests/agent-evals/BASELINE.md` gets the dated section the repo's rules ask for, with every eval case's result and cost on both models.
- **Files:** `README.md`, `records/README-record.md`, `docs/repo-guide.md`, `CLAUDE.md`, `tests/agent-evals/BASELINE.md`.
- **Done when:** `grep -n 'setup-token' README.md` and `grep -n 'CHECKED_PLANS_USE_API_KEY' README.md` each find a line; `grep -n 'launch-checks' docs/repo-guide.md CLAUDE.md` finds both; `records/README-record.md` ends with a dated `- Not reviewed:` line for the change; and `BASELINE.md` has a 2026-10 dated section naming every case run for this part, with its result and cost.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W5 | 5 h, four test files changed | none |
| W6 | 30 min | none |
| W7 | 2 h, six test stubs included | W5, which makes the shared file |
| W8 | 1 h | W5 to W7 |
| Evals | both eval sets on both models; the implement cases too | W5 to W8 |

The hours are guesses from reading the scripts; the order matters more. W5 changes every agent launcher, `skills/implement/`'s included, so the repo's rules ask for both eval sets on Sonnet and Opus, and the implement cases, whose implementer and verifiers the runner's printed cost leaves out (`CLAUDE.md:23-38`). Both sets on both models cost $15.23 on 2026-10-04, and the implement cases $3.00 of that (`docs/repo-guide.md:108-109`).

## Spike questions

Each needed the Claude API or a live session, so all were run by hand on 2026-10-07, before part 1 was split. Each question gives its part 1 label, which the results file uses.

1. (S2) What do a `claude -p` call's result JSON and stderr say when it has no account to use (no key, no login) and when its login has expired? Experiment: by hand, a `claude -p` call with no key and an empty `CLAUDE_CONFIG_DIR`, whose login lookup finds nothing.
   Answered: no account gives `Not logged in · Please run /login` and a made-up token `Failed to authenticate. API Error: 401 Invalid bearer token`, each with exit 1, `is_error: true` and `subtype: "success"`; an expired login wasn't observed (spike S2, `docs/specs/spikes/2026-10-07-usability-1-costs-and-accounts-results.md`)
2. (S3) Can a `--settings` file switch off an `apiKeyHelper` set in the user's settings for one run, for example with `"apiKeyHelper": ""`? Experiment: by hand, set a helper that touches a marker file and prints a dummy key, run `claude -p --settings <file> hi` with and without the override, and see whether the marker appears.
   Answered: yes; with `--settings '{"apiKeyHelper": ""}'` the helper never ran (spike S3, `docs/specs/spikes/2026-10-07-usability-1-costs-and-accounts-results.md`)
3. (S4) With `ANTHROPIC_API_KEY` set to a made-up value while the `/login` account works, does `claude -p` fail authentication, plain and under the agents' sandbox settings? Experiment: by hand, `ANTHROPIC_API_KEY=invalid claude -p --output-format json hi`, then the same with `--settings` pointing at a rendered `hooks/agent-sandbox.json`; an authentication error both times answers it.
   Answered: yes; the made-up key failed authentication, plain and under the agent settings, and Claude Code warned it takes precedence over the login (spike S4, `docs/specs/spikes/2026-10-07-usability-1-costs-and-accounts-results.md`)
4. (S7) In a skill eval, where `run-agent.sh` is an excluded command, does an agent it starts still get `CLAUDE_CODE_OAUTH_TOKEN` when the eval's settings deny that variable? Experiment: by hand, deny a variable in sandbox settings that exclude one command, and see whether that command still gets it.
   Answered: yes; a denied variable still reaches an excluded command, and only sandboxed commands lose it (spike S7, `docs/specs/spikes/2026-10-07-usability-1-costs-and-accounts-results.md`)

## Risks and rollback

- Someone with only an API key sees the one-line note, then an account error, until they set `CHECKED_PLANS_USE_API_KEY=1`. The error says so in one line.
- A `claude --version` format Claude Code changes later would refuse every run. The refusal prints what it read, so the fix is obvious; rollback is reverting `hooks/launch-checks.sh`.
- The hand check that a run keeps the sandbox it started with waited 15 seconds; a later Claude Code that reloads settings would make the copies beside the run's folder matter more, not less.

## Open questions

- None.

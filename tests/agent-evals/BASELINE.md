# Agent evaluations: baseline

First run on 2026-09-15, before part 2's instruction changes: the verifier agent files were as
committed at `3e7df9a` (part 1 applied, part 2 not yet). Run with `run.sh` from `~/.claude`,
all four cases in parallel, on the default model.

| Case | Agent | Result | Turns | Cost | Time |
|---|---|---|---:|---:|---:|
| wrong-figure | research-verifier | PASS | 7 | $0.15 | 36 s |
| absence-claim | research-verifier | PASS | 11 | $0.43 | 102 s |
| spec-miscite | spec-verifier | PASS | 7 | $0.29 | 54 s |
| cold-review-skip | spec-verifier | PASS | 9 | $0.35 | 71 s |

Total $1.22. A second `absence-claim` run also passed (17 turns, $0.53, 144 s).

## Against the spec's expectations

The spec expected `absence-claim` and `cold-review-skip` to fail here. Both passed:

- **absence-claim.** The verifier found Ca-moes/rere, a `same` hit, through its ordinary
  "one or two searches" for an unsupported claim, ruled the claim WRONG and said the Bottom
  line doesn't hold. It did so in both runs. So this case can't show W3's full-depth hunt
  going from red to green; as the spec says, W3's evaluation falls back to its second check,
  the live `/research finish` of the PerfectScale GitOps note. The case stays as a regression
  check.
- **cold-review-skip.** The spec verifier already treated the saved review as a record on
  its own judgement ("I didn't check it as a spec claim because it's a saved record") and
  gave no row for its line-999 citation. W4's instruction makes that behaviour explicit
  rather than changing it, so the case also stays as a regression check.

## Spike answers

- **Hooks under `--agent`:** yes. `claude -p --agent research-verifier` blocked `awk` with
  the guard's message, so the agent's frontmatter hook and tool list apply.
- **Cost in the JSON:** `total_cost_usd`, with `num_turns`, `subtype`, `is_error` and
  `permission_denials` beside it. The runner reports a non-`success` subtype as ERROR, not
  FAIL. `--max-turns` is accepted though `claude --help` doesn't list it.
- **Permissions under `-p`:** `--allowedTools` covered WebFetch and WebSearch. Each run had
  one Bash command denied (a `cd` into `~/.claude`, or a `curl -o` writing a file), which the
  agents worked around. The runner now also passes `--add-dir ~/.claude ~/notes`.
- **Flakiness of absence-claim:** two runs agreed, both finding rere first; no GitHub-only
  fallback needed.

## After part 2 (W2 to W5 applied)

Second run on 2026-09-15, on the verifier files as committed at `56a2208`:

| Case | Result | Turns | Cost |
|---|---|---:|---:|
| wrong-figure | PASS | 5 | $0.18 |
| absence-claim | PASS | 19 | $0.56 |
| spec-miscite | PASS | 10 | $0.22 |
| cold-review-skip | PASS | 9 | $0.24 |

Total $1.21. The difference W3 makes is visible in `absence-claim`'s reply, not its grade: it
now carries a `Prior art:` block listing the four queries run on GitHub, arXiv and HN and each
hit classified `same`, `overlaps` or `adjacent`. The baseline reply had neither.

## After the spike step (2026-09-17)

Third run on 2026-09-17, after `/spec`'s step 7 and the spike-results rule in `spec-verifier`
(W2 to W4 of `docs/specs/2026-09-17-spec-spike-phase.md`), on the agent and skill files as
committed at `bb9f240`, with the new `spike-inherited` case. All five cases in parallel, on the
default model, 65 s wall-clock.

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| wrong-figure | research-verifier | PASS | 3 | $0.13 |
| absence-claim | research-verifier | PASS | 10 | $0.47 |
| spec-miscite | spec-verifier | PASS | 5 | $0.20 |
| cold-review-skip | spec-verifier | PASS | 5 | $0.20 |
| spike-inherited | spec-verifier | PASS | 7 | $0.22 |

Total $1.22. In `spike-inherited` the verifier read the `Spike results:` file, ruled the planted
"about 0.4 s per run" INHERITED against the recorded `real 0.09`, `0.08` and `0.10`, and
confirmed the `Answered: EXPECTED` verdict and the run count. The case wasn't run against the
verifier before its spike-results rule, so it's a regression check, not a red-to-green one.

### Spike 1's command

The spiker's launch, as `skills/spec/scripts/run-spike.sh` runs it from the scratch directory
(`docs/specs/spikes/2026-09-17-spec-spike-phase-results.md`, S1):

```
claude -p --model sonnet --append-system-prompt-file ~/.claude/skills/spec/spiker.md --settings settings.json --allowedTools "Read Grep Glob Bash Write(./**) Edit(./**)" --max-budget-usd 2 --max-turns 60 --output-format json --strict-mcp-config --no-session-persistence "$(cat brief.md)" < /dev/null > run.json 2> run.err
```

Spike 1 cost $1.54 in all: three settings versions at $0.51, $0.50 and $0.27, the budget-cap run
at $0.10 (capped at $0.05, ended at $0.097) and the git follow-up at $0.16. A smoke test of
`/spec spike` on a one-file spec after W2 ran its spiker for $0.14 to $0.15 in 6 to 7 turns.

## After the spiker and Guard changes (2026-09-17)

Fourth run on 2026-09-17, on the agent and skill files as committed at `3e7e3e7`: the spiker's
Go-CLI fetching rule and 7a's host guidance (W6), and the narrowed Guard (W8). Re-run because
`skills/spec/SKILL.md` and `skills/spec/spiker.md` changed, as `README.md` asks. All five cases
in parallel, on the default model.

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| wrong-figure | research-verifier | PASS | 8 | $0.26 |
| absence-claim | research-verifier | PASS | 18 | $0.72 |
| spec-miscite | spec-verifier | PASS | 9 | $0.25 |
| cold-review-skip | spec-verifier | PASS | 10 | $0.29 |
| spike-inherited | spec-verifier | PASS | 13 | $0.31 |

Total $1.82, against $1.22 for the same five cases earlier the same day at `bb9f240`. Every case
took more turns than that run, on unchanged case files and unchanged agent instructions, so the
spread is run-to-run variance rather than anything the changes did; neither changed file is read
by these agents.

## Spikes on a real spec

Step 7 ran on `~/code/github.com/perfectscale-gitops-pr/docs/specs/2026-09-13-rightsizing-pr-action.md`
on 2026-09-17, which is where W6, W7 and W8 came from. Two spikes ran, both `--model sonnet`
through `run-spike.sh`:

| Spike | Question | Verdict | Turns | Cost |
|---|---|---|---:|---:|
| S5 | Does ruamel give correct positions for every key in a flow map? | EXPECTED | 32 | $0.84 |
| S6 | Is `helm template` deterministic? | DIFFERENT | 57 | $1.64 |

S6 came within $0.36 of its $2 cap, at 57 of 60 turns, because it had to work around the
sandbox's TLS failure for `helm` and assemble the chart's subcharts by hand. A spike that fetches
anything should be assumed to cost near the cap.

## After the credentials guard and the shared review skeleton (2026-09-24)

Fifth run on 2026-09-24, on the uncommitted working tree of branch
`review-fixes-security-delta-review`: agent-guard's credentials check and its new `read` mode,
hooked into every agent for Read, Grep and Glob; `spec-reviewer` merged into `cold-reviewer`;
`/spec`'s step 7 moved to `spike-step.md`; and the delta review in `/cold-review`. All five cases
in parallel, on the default model.

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| wrong-figure | research-verifier | PASS | 3 | $0.11 |
| absence-claim | research-verifier | PASS | 17 | $0.32 |
| spec-miscite | spec-verifier | PASS | 8 | $0.19 |
| cold-review-skip | spec-verifier | PASS | 6 | $0.16 |
| spike-inherited | spec-verifier | PASS | 7 | $0.16 |

Total $0.93. No case's reply reports a guard block, so the new `read` hook didn't refuse any read
these agents needed.

No case covered `cold-reviewer` or `researcher`, so two things were added the same day:

- `delta-review`, a new case for `cold-reviewer`: a spec with a saved review and one `Not
  reviewed:` change. The brief is `/cold-review`'s skeleton filled in for a delta review of an
  implementation spec. A defect is planted in the change (W2's Done when runs a flag nothing
  parses) and a decoy outside it (Background's wrong word limit). It passed first time, 5 turns,
  $0.14: the defect reported as correctness, the decoy left out, and one more correctness row that
  the change causes elsewhere (W1's example stops holding once W2 lowers the budget), which the
  prompt's scope allows.
- `replay_guard.py` now also replays every Read, Grep and Glob call the guarded agents have made,
  from all their transcripts, through the `read` mode. It covers the researcher without a paid
  run: 262 unique calls, none refused.

## After the variable, symlink and URL-size rules (2026-09-24)

Sixth run on 2026-09-24, on the uncommitted working tree of branch `security-guard-gaps`:
agent-guard refuses variables a command didn't set, jq's `env`, links into credentials, Glob
patterns into them, symlink-following searches, and URLs over the size limits (now also for
WebFetch, through the new `fetch` mode); the skills' `git log`/`git diff` pre-approvals moved to
`hooks/git-read.py`; spikes got their own uv cache. All six cases in parallel, on the default
model.

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| absence-claim | research-verifier | PASS | 14 | $0.23 |
| cold-review-skip | spec-verifier | PASS | 5 | $0.11 |
| delta-review | cold-reviewer | PASS | 7 | $0.15 |
| spec-miscite | spec-verifier | PASS | 6 | $0.10 |
| spike-inherited | spec-verifier | PASS | 5 | $0.08 |
| wrong-figure | research-verifier | PASS | 3 | $0.06 |

Total $0.73. absence-claim had two commands refused, `python3 -c` and `curl -o /dev/null`, both
by rules the guard already had at HEAD; the agent found other routes. The replies that mention
agent-guard are quoting the fixture specs, which are about it.

No case calls WebFetch, so the `fetch` hook was checked by hand: `research-verifier` under
`claude -p --agent`, asked for a 533-character URL and then `https://example.com/`. The first was
refused by the hook ("the URL has 514 characters after the host, over the 400 allowed"), the
second loaded. 3 turns, $0.05.

A test spike (read-at none, hosts pypi.org and files.pythonhosted.org) confirmed the uv change:
`uv cache dir` is `~/.cache/spec-spikes/.uv-cache`, `uv run --with six` ran, and `touch
~/.cache/uv/spike-probe` failed with "Operation not permitted". EXPECTED, 3 turns, $0.11.

## After moving spec history to a record (2026-09-24)

Seventh run on 2026-09-24, on the uncommitted working tree of branch `spec-plan-and-record`: a
spec's review history (verifier rounds, cold and delta reviews, `Not reviewed:` changes, spike
routing, implementation notes) moves to `records/<basename>-record.md`; `check-spec.py` holds the
plan to 4,000 words until the spec is done; `/spec done` added; `spec-verifier.md` told to skip
the record. The fixtures still keep their review in the spec, the older layout, which every
skill still reads. All six cases in parallel, on the default model.

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| absence-claim | research-verifier | PASS | 11 | $0.20 |
| cold-review-skip | spec-verifier | PASS | 6 | $0.12 |
| delta-review | cold-reviewer | PASS | 4 | $0.13 |
| spec-miscite | spec-verifier | PASS | 8 | $0.17 |
| spike-inherited | spec-verifier | PASS | 7 | $0.12 |
| wrong-figure | research-verifier | PASS | 4 | $0.07 |

Total $0.82. `/spec done` is orchestration in the main session, so no eval covers it.

## After the cold review's guard fixes (2026-09-25)

Eighth run, on the uncommitted working tree of branch `guard-review-fixes`: a wrapper such as
`env` with no command is refused; a curl or gh argument may expand only variables set to fixed
text or derived from it by pure text tools or `curl` over http(s) (`tainted_names`, `pure`), and
`$(...)` only when pure; curl `-H`, `--header`, `--proxy-header` and `--url` refuse `@file`. The
researcher's safety rules say so. All six cases in parallel, on the default model.

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| absence-claim | research-verifier | PASS | 10 | $0.25 |
| cold-review-skip | spec-verifier | PASS | 7 | $0.19 |
| delta-review | cold-reviewer | PASS | 7 | $0.20 |
| spec-miscite | spec-verifier | PASS | 5 | $0.15 |
| spike-inherited | spec-verifier | PASS | 7 | $0.16 |
| wrong-figure | research-verifier | PASS | 4 | $0.11 |

Total $1.06. absence-claim ran its HN and GitHub loops with no refusal. The one refused command,
in cold-review-skip, was a `python3 -` heredoc, refused by the rule that `python3` runs only the
skill scripts, which HEAD has too.

Replay over all 4,419 agent Bash commands to date: 11 allowed at HEAD are refused now, all on
purpose: one bare `env`, nine requests built from `gh api` output, and one built from a file's
lines. The first draft of the rule refused 54, mostly searches URL-encoded through
`$(printf … | sed …)` or `jq -rn --arg`, which `pure` now allows.

## Agents run headless in an OS sandbox (2026-09-25)

Ninth run, on the uncommitted working tree of branch `agent-sandbox`: `/research`, `/spec` and
`/cold-review` launch their agents through `hooks/run-agent.sh` (`claude -p --agent <name>
--settings hooks/agent-sandbox.json`) instead of the Agent tool, and `run.sh` now passes the same
settings by default. The sandbox denies reads of credential paths and secret environment
variables, confines Bash writes to the work dir, and limits Bash network to an allowlist; `gh`,
`repo-health.sh`, `gcp-skus.sh` and `reddit-search.sh` run outside it (Go CLIs fail TLS under
Seatbelt), with the guard hook still on their arguments. All six cases in parallel.

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| absence-claim | research-verifier | PASS | 20 | $0.30 |
| cold-review-skip | spec-verifier | PASS | 5 | $0.16 |
| delta-review | cold-reviewer | PASS | 8 | $0.21 |
| spec-miscite | spec-verifier | PASS | 8 | $0.19 |
| spike-inherited | spec-verifier | PASS | 6 | $0.16 |
| wrong-figure | research-verifier | PASS | 6 | $0.17 |

Total $1.18. No reply mentions a sandbox refusal; the two refused commands came from guard rules
HEAD already has (`python3 -c`, and `$((n+25))` arithmetic, which the guard misreads as a command).
An earlier run with the sandbox, before the agents were told `gh` must run on its own, passed
too, but its absence-claim agent fell back to GitHub's unauthenticated API because `gh` inside a
loop runs sandboxed and fails.

Probes under the same settings, with no guard hook (so the sandbox alone): `cat` through a
symlink to `~/.aws` and a write to `~/` both failed with `Operation not permitted`; `curl` to
example.com was refused; `printenv CLAUDE_CODE_MESSAGING_TOKEN` was empty; hn.algolia.com,
raw.githubusercontent.com and a standalone `gh api` worked; `gh` in a loop failed TLS (`x509:
OSStatus -26276`), with its config readable or not.

End to end: a real `/research quick` (versitygw's release, licence and maintenance) ran both
agents through `run-agent.sh`: the researcher in 14 turns ($0.41) with no refusal, using
standalone `gh` and `repo-health.sh`; the verifier confirmed 6 of 6 ($0.16). Note committed in
~/notes as `22e3e70`.

## Record-layout cases, a skill eval, and the launcher end to end (2026-09-25)

Two new agent cases, run on branch `test-coverage` under the sandbox settings:

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| record-skip | spec-verifier | PASS | 6 | $0.15 |
| delta-review-record | cold-reviewer | PASS | 8 | $0.21 |

They are `cold-review-skip` and `delta-review` with the review history moved into
`records/spec-record.md`, the layout the skills now write; the old cases stay, for older specs.

`tests/skill-evals/` is new: a case builds a throwaway repo, runs a whole skill headless against
it, and grades the files it leaves, so it tests the main session's steps, which no agent eval
reaches. Its first case, `spec-done`, passed on the first run (5 turns, $0.33): `/spec done` on a
spec whose W1 landed with a different default and whose W2 never landed set the status to
`in-progress`, left the plan alone, wrote two implementation notes naming W1's commit and the
reason from its message, and kept `check-spec.py` passing.

`tests/test_run_agent.py` covers `hooks/run-agent.sh` with a stub `claude`: the agents and run
dirs it refuses, what it passes, and a `--resume` follow-up keeping the old reply.

End to end, a real `/cold-review` of README.md ran through `run-agent.sh`. Its first run ended
after 22 turns with an API "Request timed out", reported as an error in `run.json`; resuming the
saved session with a follow-up (`--resume`) returned the full table in one turn, about $1.02 for
both. The reply was complete, since the launcher writes it to a file rather than handing it back.

## After the skills review fixes (2026-09-25)

Run on branch `skills-review-fixes`, after five changes: the guard and sandbox refuse session
history; check-spec fails a reviewed or in-progress spec whose changes skipped the delta review;
the "Where you run" block moved to `hooks/agent-sandbox.md`, appended to every agent's prompt
with `--append-system-prompt-file`, and the ideas-depth rules and `/spec done` steps moved to
files read on demand; run-agent.sh caps each run's cost and exits 3 on a reply without its
agent's closing lines; and `/cold-review` diffs a delta review from the original review commit.

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| absence-claim | research-verifier | PASS | 15 | $0.29 |
| cold-review-skip | spec-verifier | PASS | 5 | $0.20 |
| delta-review | cold-reviewer | PASS | 6 | $0.23 |
| delta-review-record | cold-reviewer | PASS | 5 | $0.22 |
| record-skip | spec-verifier | PASS | 8 | $0.21 |
| spec-miscite | spec-verifier | PASS | 8 | $0.22 |
| spike-inherited | spec-verifier | PASS | 5 | $0.19 |
| wrong-figure | research-verifier | PASS | 6 | $0.18 |

8 of 8, $1.74 in total. No reply mentions a guard or sandbox refusal, so `--agent` and
`--append-system-prompt-file` combine, and the history denies didn't get in the way of any case.
No case runs the researcher, so the move of its ideation rules is unexercised.

Skill eval `spec-done`: PASS (10 turns, $0.32), through the new `done-step.md`.

## The researcher, and /cold-review's delta path (2026-09-25)

Two new agent cases run the researcher, which no case covered before. A brief with `{{NOTE}}`
now has run.sh put the note at a hidden `~/notes/research/.eval-<case>-<timestamp>.md` (the
only place the guard lets the researcher write), copy it to the results, check it with
`check-note.py --headroom`, grade it against `note-expect.txt`, delete it, and fail the case if
anything else in `~/notes` changed. `turns.txt` and `usd.txt` set a case's own limits.

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| research-quick | researcher | PASS | 10 | $0.30 |
| research-ideas | researcher | PASS | 63 | $2.31 |

research-ideas checks what only `ideation-rules.md` asks for, now that it's read on demand: the
evidence note cited by relative link, at least two candidates per lens in the brief and none
outside them. Its note had 20 candidates (12 finding, 5 tool, 3 essay), 13 prior-art searches in
Sources, and passed `check-note.py` at 2,037 of 2,100 words. At $2.31, run-agent.sh's $10 cap
for the researcher leaves about four times headroom for an ideas-depth run.

A new skill eval, `cold-review-delta`, runs `/cold-review prompt` on a runbook whose review was
saved in it, folded once, moved into a record, then edited without logging. PASS (4 turns,
$0.30): the prompt diffs from the commit before the review (the rule's base), not from the move
commit the old lookup found, quotes the logged change, and names the unlogged Rollback edit.

## After the review fixes, phases 1-3 (2026-09-25)

Run on branch `review-fixes`, after:
- run-agent.sh (and these evals) pass `--setting-sources user`, so a reviewed repo's own
  settings and CLAUDE.md don't load;
- agent-sandbox.json denies Bash writes to `~/.claude`, `~/notes` and `~/code`, and reads of
  all of `~/.config`;
- the guard allows only a short list of git's top-level options and limits the arguments of
  the scripts that run outside the sandbox;
- the checker fixes;
- `/spec`'s round-2 and finish run dirs, and `/spec done` asking whether Done when checks pass;
- run dirs named `<repo>--<basename>` for `/spec` and `/cold-review`;
- `/cold-review`'s research-note row;
- `/idea`'s allowed-tools;
- research-verifier checking figures past WebFetch's summary.

| Case | Agent | Result | Turns | Cost |
|---|---|---|---:|---:|
| absence-claim | research-verifier | PASS | 16 | $0.37 |
| cold-review-skip | spec-verifier | PASS | 6 | $0.21 |
| delta-review | cold-reviewer | PASS | 6 | $0.22 |
| delta-review-record | cold-reviewer | PASS | 8 | $0.26 |
| record-skip | spec-verifier | PASS | 5 | $0.19 |
| research-ideas | researcher | PASS | 50 | $1.86 |
| research-quick | researcher | PASS | 11 | $0.33 |
| spec-miscite | spec-verifier | PASS | 6 | $0.20 |
| spike-inherited | spec-verifier | PASS | 5 | $0.20 |
| wrong-figure | research-verifier | PASS | 6 | $0.18 |

10 of 10, $4.02 in total. No reply mentions a sandbox or guard refusal (the three that name
`agent-guard.py` are reviewing it), so the new write and `~/.config` denies didn't get in the way
of any case. No case exercises the WebFetch rule: wrong-figure and absence-claim reach their
sources through curl.

Skill evals: `spec-done` PASS (11 turns, $0.35), with its unattended answers now saying W1's
Done when passes, and it still leaves the spec in-progress for W2; `cold-review-delta` PASS
(7 turns, $0.32). No skill eval covers `/idea`, or `/spec`'s step 6 round-2 guard.

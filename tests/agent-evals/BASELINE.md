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

Fourth run on 2026-09-17, on the agent and skill files as committed at `6effab6`: the spiker's
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

Step 7 ran on a real spec in another local repo
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

## Phase 4: review-state.py, /spec quick, concurrent /research, trims (2026-09-25)

`/cold-review` step 1 now reads `skills/cold-review/scripts/review-state.py` instead of working
out the review commit and diff base by hand; `/spec quick` added; commits in `~/notes` name
their files; the three largest skills trimmed by about 330 words. No agent file changed, so
the agent cases above stand.

Skill evals: `cold-review-delta` PASS (3 turns, $0.27, down from 7 turns with the script),
`spec-done` PASS (11 turns, $0.34). No eval runs `/spec quick` or two `/research` runs at once.

## Notes index W3: the researcher sets a topic (2026-09-27)

W3 of `docs/specs/2026-09-27-notes-mindmap-index.md`: the researcher's frontmatter rule adds
`topic`, and both researcher cases' `note-expect.txt` require a `topic:` line of the form
`area` or `area/sub-area`. `check-note.py` warns on topics (W1) and `build-index.py` exists
(W4); neither fails a note yet. All ten cases in parallel, on the default model:

| Case | Result | Turns | Cost |
|---|---|---:|---:|
| absence-claim | PASS | 18 | $0.42 |
| cold-review-skip | PASS | 5 | $0.14 |
| delta-review | PASS | 6 | $0.23 |
| delta-review-record | PASS | 8 | $0.20 |
| record-skip | PASS | 6 | $0.15 |
| research-ideas | PASS | 67 | $2.44 |
| research-quick | PASS | 12 | $0.38 |
| spec-miscite | PASS | 8 | $0.17 |
| spike-inherited | PASS | 4 | $0.12 |
| wrong-figure | PASS | 6 | $0.20 |

Total $4.46. The researcher chose `topic: python` (quick) and `topic: ai/research-agents`
(ideas). Both got the first-use WARN, as expected while no note in `~/notes/research` has a
topic yet; W6's backfill gives the researcher topics to reuse.

## Notes index W5: /research's Finish step rebuilds the index (2026-09-27)

W5 of `docs/specs/2026-09-27-notes-mindmap-index.md`: section 3 of `skills/research/SKILL.md`
gains step 8, which runs `build-index.py ~/notes`, and the commit step (now 9) names `index.md`.
No agent file changed. All ten agent cases in parallel, on the default model:

| Case | Result | Turns | Cost |
|---|---|---:|---:|
| absence-claim | PASS | 20 | $0.31 |
| cold-review-skip | PASS | 6 | $0.14 |
| delta-review | PASS | 7 | $0.20 |
| delta-review-record | PASS | 7 | $0.24 |
| record-skip | PASS | 7 | $0.17 |
| research-ideas | PASS | 67 | $2.47 |
| research-quick | PASS | 11 | $0.31 |
| spec-miscite | PASS | 6 | $0.14 |
| spike-inherited | PASS | 5 | $0.15 |
| wrong-figure | PASS | 6 | $0.14 |

Total $4.27.

Skill evals: `spec-done` PASS (11 turns, $0.35). `cold-review-delta` FAILed its first run
(5 turns, $0.28) on one check only, "it's a delta review": the reply said "its second review, of
just what changed" rather than the words "delta review", with the right diff base and the
unlogged Rollback edit named. A re-run passed every check (4 turns, $0.27). No `/cold-review`
file changed, so this is the grader's wording check being brittle, not a regression.

Live check: `/research quick` on the Markmap VS Code extension's link clicks, run in the
implementing session, ended in `~/notes` commit 2045a57 naming the note and `index.md`. It found
`build-index.py` printing one topic too many per area with sub-areas only (fixed, with a test).

## Notes index W7: a missing or malformed topic fails (2026-09-27)

W7 of `docs/specs/2026-09-27-notes-mindmap-index.md`: `check-note.py` now FAILs a note with no
topic, or one that isn't `area` or `area/sub-area` in lowercase and hyphens; a topic no other
note uses stays a WARN. W6 gave every note in `~/notes/research` a topic first (`~/notes` commit
bc059f6). Research notes failing `check-note.py`: 1 before and 1 after (the rag-forge taskfile
note's dead `related` paths), so topics add no failures. All ten cases in parallel:

| Case | Result | Turns | Cost |
|---|---|---:|---:|
| absence-claim | PASS | 21 | $0.28 |
| cold-review-skip | PASS | 7 | $0.15 |
| delta-review | PASS | 5 | $0.20 |
| delta-review-record | PASS | 8 | $0.22 |
| record-skip | PASS | 5 | $0.13 |
| research-ideas | PASS | 54 | $2.02 |
| research-quick | PASS | 11 | $0.26 |
| spec-miscite | PASS | 6 | $0.14 |
| spike-inherited | PASS | 8 | $0.15 |
| wrong-figure | PASS | 6 | $0.14 |

Total $3.70. The ideas researcher reused an existing topic, `side-projects/ideas`, with no
first-use WARN; the quick one chose a new `python/packages` and got the WARN, as designed.

## Graders check the finding, runners exit 1 on a failure (2026-09-27)

No agent or skill file changed, so no paid run. Four graders were tightened so they can't pass on
a reply that misses the finding they test. Each new check was replayed against every saved reply
in `results/` before the change, and passes all of them:

| Case | Before | After | Saved replies passing |
|---|---|---|---:|
| cold-review-skip | `Confirmed:` and `Plan holds:` present | also a table row for each of the spec's three citations (:31, :187, :394) | 16 of 16 |
| record-skip | the same | the same | 6 of 6 |
| cold-review-delta (skill) | "rollback" anywhere | Rollback named as unlogged in the same paragraph or bullet | 6 of 6 |
| spec-done (skill) | a `3` anywhere in Implementation | `3` within 40 characters of "default" or "places" | 5 of 5 |

A reply that checks no citations, or mentions Rollback only as a section name, now fails. Both
`run.sh` files exit 1 when any case fails or errors, and 2 on an unknown case; the skill evals
now end with an "N of M passed; total $X" line. The per-case caps are now set separately:
`AGENT_EVAL_MAX_USD` (default 5) and `SKILL_EVAL_MAX_USD` (default 3), replacing the shared
`EVAL_MAX_USD`.

## CodeRabbit's fixes from PR 5 (2026-09-27)

`/research` step 8 says how the index recovers when two sessions finish at once; `build-index.py`
puts a path with a space or bracket in angle brackets; the README's topic-listing command
normalises before counting. All ten agent cases in parallel, on the default model:

| Case | Result | Turns | Cost |
|---|---|---:|---:|
| absence-claim | PASS | 15 | $0.30 |
| cold-review-skip | PASS | 6 | $0.22 |
| delta-review | PASS | 6 | $0.25 |
| delta-review-record | PASS | 6 | $0.20 |
| record-skip | PASS | 6 | $0.20 |
| research-ideas | PASS | 63 | $2.59 |
| research-quick | PASS | 11 | $0.33 |
| spec-miscite | PASS | 5 | $0.19 |
| spike-inherited | PASS | 5 | $0.19 |
| wrong-figure | PASS | 6 | $0.21 |

Total $4.68.

Skill evals: `spec-done` PASS (11 turns, $0.35). `cold-review-delta` FAILed its first run
(4 turns, $0.27) on its two diff checks: `review-state.py` now prints `diff -M <base>` (`809d3e0`,
following renames), and the grader's pattern wanted the commit straight after `diff`. The skill's
diff was right, from the runbook's first commit. With the pattern allowing options, a re-run
passed every check (4 turns, $0.28).

## Checker loopholes (2026-09-27)

`check-spec.py`, `check-note.py`, `review-state.py`, `build-index.py` and `mdcheck.py` close the
loopholes the second 2026-09-27 repo review found, and `review-state.py` prints its `diff:` line
as a quoted `~/.claude/hooks/git-read.py` command. No agent or skill instruction file changed, and
the checkers give the same results on all 32 notes in `~/notes`, this repo's 4 specs and the index;
on 16 specs in other repos, one bare `values.yaml:163-164` is now reported as ambiguous. So the
agent cases weren't run. Skill evals: `spec-done` PASS (5 turns, $0.30), `cold-review-delta` PASS
(3 turns, $0.27), which takes the new `diff:` line. Total $0.57.

## Graders and runners tightened (2026-09-27)

Graders that passed a wrong answer are fixed, and each was replayed against every saved reply:
- `delta-review` and `delta-review-record` need `correctness` or `requirement` in the Affects
  cell, not anywhere in the row. All 19 saved replies still pass; a row graded "neither: a
  correctness nit" now fails.
- `cold-review-delta` no longer counts "there is no unlogged change" as naming one, resolves the
  diff base with its `^` or `~1` (`created^` doesn't exist), and fails if the skill committed
  anything. All 9 saved replies still pass the wording check.
- `spec-done` diffs the spec against setup's HEAD, so a committed edit can't hide, and needs W2
  named as not landed in the same sentence. All 7 saved replies pass; "W2 has landed" fails.

No agent or skill instruction file changed, so only the cases whose graders changed were run:

| Case | Result | Turns | Cost |
|---|---|---:|---:|
| delta-review | PASS | 7 | $0.24 |
| delta-review-record | PASS | 7 | $0.24 |
| cold-review-delta (skill) | PASS | 3 | $0.27 |
| spec-done (skill) | PASS | 9 | $0.34 |

Total $1.09.

## Skill instructions fixed (2026-09-27)

`/spec`, `/cold-review`, `/research`, `/idea`, the spike and done steps and the research verifier's
Prior art line take the fixes from the second 2026-09-27 repo review. All ten agent cases in
parallel, on the default model:

| Case | Result | Turns | Cost |
|---|---|---:|---:|
| absence-claim | PASS | 23 | $0.47 |
| cold-review-skip | PASS | 6 | $0.15 |
| delta-review | PASS | 12 | $0.27 |
| delta-review-record | PASS | 7 | $0.31 |
| record-skip | PASS | 7 | $0.20 |
| research-ideas | PASS | 55 | $2.18 |
| research-quick | PASS | 11 | $0.33 |
| spec-miscite | PASS | 5 | $0.17 |
| spike-inherited | PASS | 6 | $0.17 |
| wrong-figure | PASS | 6 | $0.14 |

Total $4.39. Skill evals: `cold-review-delta` PASS (5 turns, $0.28), `spec-done` PASS (10 turns,
$0.36); total $0.64.

## Guard hardening (2026-09-27)

The guard refuses `eval` and wrapper options it doesn't know, lets `gh` and the research scripts
share a command only with text filters, and checks web search queries; the researcher and
research-verifier hook WebSearch to it, and `agent-sandbox.md` says so. All ten agent cases:

| Case | Result | Turns | Cost |
|---|---|---:|---:|
| absence-claim | PASS | 11 | $0.32 |
| cold-review-skip | PASS | 7 | $0.19 |
| delta-review | PASS | 6 | $0.21 |
| delta-review-record | PASS | 7 | $0.20 |
| record-skip | PASS | 6 | $0.18 |
| research-ideas | PASS | 56 | $2.02 |
| research-quick | PASS | 16 | $0.36 |
| spec-miscite | PASS | 9 | $0.20 |
| spike-inherited | PASS | 4 | $0.14 |
| wrong-figure | PASS | 6 | $0.19 |

Total $4.00.

## Docs sweep and the delta reviewer's diff (2026-09-28)

`/cold-review` gives the delta reviewer its diff as `git`, which its guard allows, not the
`git-read.py` form `review-state.py` prints; `cold-review-delta` gains a check for it. The
researcher treats an `API error` row from `repo-health.sh` as unverified. All ten agent cases:

| Case | Result | Turns | Cost |
|---|---|---:|---:|
| absence-claim | FAIL, then PASS | 2, then 14 | $0.55, then $0.28 |
| cold-review-skip | PASS | 7 | $0.15 |
| delta-review | PASS | 7 | $0.20 |
| delta-review-record | PASS | 9 | $0.24 |
| record-skip | PASS | 7 | $0.14 |
| research-ideas | PASS | 51 | $1.96 |
| research-quick | PASS | 12 | $0.31 |
| spec-miscite | PASS | 9 | $0.17 |
| spike-inherited | PASS | 6 | $0.13 |
| wrong-figure | PASS | 6 | $0.15 |

Total $4.01, and $0.28 for the re-run. `absence-claim`'s first run found the right answer, a
WRONG row and `Bottom line holds: no`, but the verifier then sent a second, short message when
late search results came back, and the runner grades only the last one. Nothing this change
touched affects the verifier; the re-run passed. Skill evals: `cold-review-delta` PASS (5 turns,
$0.28), with the new check; `spec-done` PASS (8 turns, $0.36); total $0.64.

## Skill best practices, part 1 (2026-09-28)

W1 of `docs/specs/2026-09-28-skill-best-practices-1-invocation.md`: `/research`, `/spec` and
`/cold-review` set `disable-model-invocation: true`, and all four descriptions are third person.
Skill evals, which start their skill as a typed command: `cold-review-delta` PASS (5 turns,
$0.28); `spec-done` PASS (11 turns, $0.36); total $0.64. Asked to call the Skill tool, a
`claude -p` session is refused `research`, `spec` and `cold-review` "due to
disable-model-invocation", and launches `idea`.

W2: `/spec` pre-approves `Edit(~/code/**/*.md)` in place of `Edit(~/code/**)`, and `/cold-review`
only its records. `spec-done`'s fixture, built under `~/code` and run without `acceptEdits` or
Edit in `--allowedTools`, still wrote its spec and record with no permission denials and passed
its grader ($0.35).

W3: the agent files move to `hooks/agents`, and both runners pass each one by
`--agents <file> --agent <name>`, from `hooks/agent-def.py`. With `~/.claude/agents` removed, a new
session's `init` event lists none of the four agents. The new `guard-applies` case shows the
guard hook still runs under `--agents`. All eleven agent cases:

| Case | Result | Turns | Cost |
|---|---|---:|---:|
| absence-claim | PASS | 15 | $0.35 |
| cold-review-skip | PASS | 8 | $0.21 |
| delta-review | PASS | 6 | $0.18 |
| delta-review-record | PASS | 8 | $0.21 |
| guard-applies | PASS | 2 | $0.06 |
| record-skip | PASS | 6 | $0.18 |
| research-ideas | PASS | 64 | $2.45 |
| research-quick | PASS | 11 | $0.35 |
| spec-miscite | PASS | 5 | $0.17 |
| spike-inherited | PASS | 6 | $0.15 |
| wrong-figure | PASS | 6 | $0.21 |

Total $4.52. `guard-applies` also passed alone beforehand ($0.06). Skill evals after W3:
`cold-review-delta` PASS (3 turns, $0.26); `spec-done` PASS (10 turns, $0.34); total $0.60.

## Skill best practices, part 2 (2026-09-28)

W4: the three skills' "Running an agent" steps move to `hooks/run-agent.md`, and cross-file
references name headings, not step numbers. No agent file changed, and the agent evals run the
agents directly, not through a skill, so W5's two-model baseline is the next agent-eval run.

Skill evals, first run: `spec-done` PASS (11 turns, $0.35); `cold-review-delta` FAIL on "the
unlogged Rollback edit is named" (total $0.61). The reply did name it ("The diff also changes
`## Rollback`, and no logged line covers that"), but the grader's pattern had no "no logged line"
form, so it gained one. Re-run: `spec-done` PASS (5 turns, $0.30); `cold-review-delta` PASS
(5 turns, $0.27); total $0.57.

W5 baseline, before W6–W8 change anything: both sets on each model, one after the other
(agent evals, then skill evals, Sonnet first).

| Set | Case | Model | Result | Turns | Cost |
|---|---|---|---|---:|---:|
| agent | absence-claim | sonnet | FAIL | 33 | $0.46 |
| agent | absence-claim | opus | PASS | 17 | $0.30 |
| agent | cold-review-skip | sonnet | FAIL | 11 | $0.17 |
| agent | cold-review-skip | opus | PASS | 7 | $0.15 |
| agent | delta-review | sonnet | PASS | 10 | $0.37 |
| agent | delta-review | opus | PASS | 8 | $0.27 |
| agent | delta-review-record | sonnet | PASS | 10 | $0.38 |
| agent | delta-review-record | opus | PASS | 7 | $0.29 |
| agent | guard-applies | sonnet | FAIL | 1 | $0.10 |
| agent | guard-applies | opus | PASS | 2 | $0.06 |
| agent | record-skip | sonnet | PASS | 15 | $0.24 |
| agent | record-skip | opus | PASS | 4 | $0.13 |
| agent | research-ideas | sonnet | PASS | 38 | $1.01 |
| agent | research-ideas | opus | PASS | 60 | $2.50 |
| agent | research-quick | sonnet | PASS | 8 | $0.21 |
| agent | research-quick | opus | PASS | 12 | $0.27 |
| agent | spec-miscite | sonnet | PASS | 15 | $0.23 |
| agent | spec-miscite | opus | PASS | 9 | $0.17 |
| agent | spike-inherited | sonnet | PASS | 14 | $0.17 |
| agent | spike-inherited | opus | PASS | 6 | $0.12 |
| agent | wrong-figure | sonnet | PASS | 6 | $0.14 |
| agent | wrong-figure | opus | PASS | 6 | $0.16 |
| skill | cold-review-delta | sonnet | FAIL | 10 | $0.24 |
| skill | cold-review-delta | opus | PASS | 3 | $0.26 |
| skill | spec-done | sonnet | PASS | 15 | $0.32 |
| skill | spec-done | opus | PASS | 11 | $0.36 |

Totals: agent evals $3.48 on Sonnet (8 of 11 passed), $4.42 on Opus (11 of 11); skill evals $0.56 on Sonnet (1 of 2), $0.62 on Opus (2 of 2).

Sonnet's four failures are in the grading, not in what it did:
- `cold-review-delta`: it named the unlogged Rollback edit ("nothing logs that"), a wording the
  grader's pattern didn't have; the pattern gains "nothing logs".
- `absence-claim`: it ruled the absence claim WRONG, citing two other tools
  (`kube-finops-autopilot`, `prometheus-resource-auto-update`) than the four the case lists.
- `cold-review-skip`: it skipped the saved review, but added a SKIPPED table row naming its
  citation, which the case's `!` pattern for line 999 counts as checking it.
- `guard-applies`: it refused `awk` from its instructions without calling it, so the guard never
  ran; the case needs the call to be made.
The last three are left for a decision on the cases; W8's "both models pass" can't be met until
they are settled.

W6: the two new skill-eval cases, which run their skill's agents in the foreground. Spike 1 was
their first runs (`docs/specs/spikes/2026-09-28-skill-best-practices-2-structure-results.md`):
the first failed because `run-agent.sh`, joined with `; echo $?`, ran inside the sandbox, and
passed once `hooks/run-agent.md` said to run it alone. Then on each model, with each agent's
run time from its `run.json`:

| Case | Model | Result | Turns | Session cost | Agents |
|---|---|---|---:|---:|---|
| spec-quick | sonnet | PASS | 24 | $0.48 | spec-verifier 26 s, $0.09 |
| spec-quick | opus | PASS | 18 | $0.44 | spec-verifier 19 s, $0.10 |
| research-quick-flow | sonnet | FAIL | 31 | $0.74 | researcher 32 s, $0.24; research-verifier 46 s, $0.19 |
| research-quick-flow | opus | PASS | 16 | $0.44 | researcher 44 s, $0.31; research-verifier 21 s, $0.18 |

Sonnet's `research-quick-flow` failed "nothing else in ~/notes changed", and rightly: it left
`~/notes/index.md` rebuilt with a link to the eval note ("the rebuilt `index.md` [is] sitting as
uncommitted changes"), though the sandbox's `denyWrite` blocks `build-index.py`'s own write. It
was restored with `git -C ~/notes checkout -- index.md`. How it wrote the file isn't in the
result; the Write and Edit tools aren't covered by the OS sandbox.

W6's negative check: a copy of `spec-quick` without the foreground line, on the default model,
FAIL (10 turns, $0.37) on "the record has a Confirmed: line", "the record has a Quick spec on
line" and "the spec verifier ran": the session ended when it launched the verifier in the
background.

Sonnet's failures, dealt with case by case:
- `research-quick-flow`: `agent-case-settings.json` also denies the Write and Edit tools on
  `~/notes/index.md`, which the OS sandbox doesn't cover. Re-run on sonnet: PASS (46 turns,
  $1.20), and `~/notes` was left as it was.
- `absence-claim`: a tool the verifier found itself counts, named as a repo in the WRONG row.
  Re-run on sonnet: PASS (21 turns, $0.41).
- `cold-review-skip`: a row that only says the saved review was SKIPPED or not checked is
  allowed. Re-run on sonnet: PASS (11 turns, $0.14).
- `guard-applies`: its brief now says to make the call and let the tools refuse it. Sonnet still
  declined ("it's not my job to send them to the door in the first place"; 1 turn, $0.03), so the
  case gets a `models.txt` of `opus`, and the agent runner skips it on other models, saying so.
  Opus with the new brief: PASS (2 turns, $0.05).
The saved sonnet and opus replies for `absence-claim` and `cold-review-skip` from the W5 baseline
both pass the new patterns.

W7: a progress checklist near the top of `/research`, `/spec` and `/cold-review`. No agent file
changed, and the agent evals don't run the skills, so only the skill evals ran:

| Case | Model | Result | Turns | Cost |
|---|---|---|---:|---:|
| cold-review-delta | sonnet | PASS | 11 | $0.28 |
| cold-review-delta | opus | PASS | 4 | $0.28 |
| research-quick-flow | sonnet | PASS | 27 | $0.61 |
| research-quick-flow | opus | PASS | 23 | $0.56 |
| spec-done | sonnet | PASS | 11 | $0.27 |
| spec-done | opus | PASS | 7 | $0.34 |
| spec-quick | sonnet | PASS | 24 | $0.51 |
| spec-quick | opus | PASS | 13 | $0.44 |

Totals $1.67 on Sonnet and $1.62 on Opus, sessions only. On both models `spec-quick`'s result
holds a ticked `- [x]` line from the checklist, and `~/notes` was left as it was.

W8: the three skill files trimmed to 2,099, 2,299 and 1,998 words, no line over 400 characters.
A first run hit the account's session limit (every call a 429 at $0.00) and is left out. The
re-run, one set after the other:

| Set | Case | Model | Result | Turns | Cost |
|---|---|---|---|---:|---:|
| agent | absence-claim | sonnet | PASS | 12 | $0.30 |
| agent | absence-claim | opus | PASS | 14 | $0.34 |
| agent | cold-review-skip | sonnet | PASS | 11 | $0.16 |
| agent | cold-review-skip | opus | PASS | 9 | $0.23 |
| agent | delta-review | sonnet | PASS | 15 | $0.48 |
| agent | delta-review | opus | PASS | 8 | $0.28 |
| agent | delta-review-record | sonnet | PASS | 15 | $0.50 |
| agent | delta-review-record | opus | PASS | 7 | $0.25 |
| agent | guard-applies | sonnet | SKIP |  |  |
| agent | guard-applies | opus | PASS | 2 | $0.09 |
| agent | record-skip | sonnet | PASS | 16 | $0.18 |
| agent | record-skip | opus | PASS | 6 | $0.20 |
| agent | research-ideas | sonnet | PASS | 32 | $0.94 |
| agent | research-ideas | opus | PASS | 64 | $2.37 |
| agent | research-quick | sonnet | PASS | 13 | $0.33 |
| agent | research-quick | opus | PASS | 13 | $0.34 |
| agent | spec-miscite | sonnet | PASS | 15 | $0.22 |
| agent | spec-miscite | opus | PASS | 8 | $0.23 |
| agent | spike-inherited | sonnet | PASS | 16 | $0.21 |
| agent | spike-inherited | opus | PASS | 8 | $0.22 |
| agent | wrong-figure | sonnet | PASS | 6 | $0.13 |
| agent | wrong-figure | opus | PASS | 6 | $0.20 |
| skill | cold-review-delta | sonnet | PASS | 12 | $0.27 |
| skill | cold-review-delta | opus | PASS | 4 | $0.27 |
| skill | research-quick-flow | sonnet | PASS | 23 | $0.47 |
| skill | research-quick-flow | opus | PASS | 16 | $0.45 |
| skill | spec-done | sonnet | PASS | 14 | $0.33 |
| skill | spec-done | opus | PASS | 9 | $0.33 |
| skill | spec-quick | sonnet | PASS | 21 | $0.45 |
| skill | spec-quick | opus | PASS | 14 | $0.44 |

Totals: agent evals $3.47 on Sonnet (10 of 10, guard-applies skipped), $4.75 on Opus (11 of 11);
skill evals $1.51 on Sonnet (4 of 4), $1.49 on Opus (4 of 4). `~/notes` was left as it was.

## Agent command hints (2026-09-28)

`hooks/agent-sandbox.md` tells every agent what Bash runs, what the guard refuses (`awk`,
`python3 -c`, shell functions, `>` into a file, `curl -o`) and what to use instead, after
`tests/mine-sessions.py` found 50 guard refusals in 61 real agent sessions, each a wasted turn.
Every suggested replacement was checked against the guard, and allowed.

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | FAIL (35 turns, $0.56), then PASS (12, $0.22) | PASS (16, $0.37) |
| cold-review-skip | PASS (11, $0.18) | PASS (6, $0.12) |
| delta-review | PASS (8, $0.34) | PASS (7, $0.24) |
| delta-review-record | PASS (10, $0.41) | PASS (7, $0.26) |
| guard-applies | SKIP (opus only) | PASS (2, $0.06) |
| record-skip | PASS (17, $0.26) | PASS (8, $0.15) |
| research-ideas | PASS (39, $1.35) | PASS (60, $2.14) |
| research-quick | PASS (10, $0.25) | PASS (10, $0.30) |
| spec-miscite | PASS (20, $0.25) | PASS (5, $0.20) |
| spike-inherited | FAIL (10, $0.15), then PASS (5, $0.09) | PASS (7, $0.20) |
| wrong-figure | PASS (8, $0.17) | PASS (6, $0.20) |

Totals: Sonnet $3.89, and $0.31 for the two re-runs; Opus $4.25. Neither Sonnet failure touched a
blocked command:
- `absence-claim`: it ruled the claim `WRONG (overlaps)`, which the case's pattern didn't accept;
  the pattern now allows a parenthesis after WRONG.
- `spike-inherited`: it found the planted 0.4 s against the recorded 0.09 s, but called it
  UNSUPPORTED, not WRONG or INHERITED. It passed on the re-run and in both earlier Sonnet runs
  today, so it's left as run-to-run variation.
`guard-applies` still passes on Opus: the new line didn't stop it making the call the guard
refuses.

## Sandbox exemption check (2026-09-29)

`gh` and the three network scripts are in `agent-sandbox.json`'s `excludedCommands`, so they run
outside the OS sandbox, with the user's login. Which Bash calls count as excluded is Claude Code's
rule, not ours. Its settings reference (`sandbox.excludedCommands`) says an entry takes a call out
of the sandbox "only when they cover every command in it", and lists shapes that stay sandboxed
anyway: a command starting with `sudo`, `eval` or `xargs`; a `cd`, `pushd` or `popd` anywhere; a
command substitution, subshell or control-flow block; a redirection other than one that only
duplicates a file descriptor; a command name from a variable. Its changelog dates "every part must
now match" to 2.1.277 (before, one matching part exempted the whole call).

The guard's earlier rule was the other way round. `ea17e11` (2026-09-25) told the agents `gh` must
be a command on its own; `35a0aed` (2026-09-27) let it share a call with text filters, on the
strength of "45 joined gh commands succeeded in headless runs". The transcripts behind that count
aren't kept, and a pipe into `head` or `tail` exits 0 whatever `gh` did, so a count by exit code
would have called today's failed `gh ... | tail -6` runs successes.

Six headless sessions on Claude Code 2.1.284, a Sonnet driving the Bash tool, started from `~/notes`
with `--allowedTools Bash --settings hooks/agent-sandbox.json` (the guard's hooks not active), $0.46
in all. Each ran the commands below as written, one Bash call each. "Outside": `gh` printed its
answer (`.rate.limit` was `5000`) or `repo-health.sh` printed its table. "Inside": `gh` said "failed
to load config ... operation not permitted", or `repo-health.sh` said "gh isn't logged in".

| Command | Ran |
|---|---|
| `gh ...`, `repo-health.sh ...` | outside |
| `gh ...; gh ...`, `gh ... && gh ...`, `gh ... \|\| gh ...`, two `gh` lines, `gh ... \| gh ...` | outside |
| `gh ...; repo-health.sh ...` | outside |
| `env gh ...`, `nice gh ...`, `nohup gh ...`, `time gh ...`, `LC_ALL=C gh ...` | outside |
| `gh ... 2>&1`, `repo-health.sh ... 2>&1`, `gh ... >&2` | outside |
| `gh ... \| head -1`, `repo-health.sh ... \| head -3`, `repo-health.sh ... 2>&1 \| head -3` | inside |
| `cd DIR && gh ...`, `gh ...; echo done`, `repo-health.sh ... && echo ok` | inside |
| `gh ... 2>/dev/null`, `repo-health.sh ... 2>/dev/null` | inside |
| `q=x; gh ... $q ...`, `gh api repos/$(echo x) ...`, `(gh ...)` | inside |
| `bash ~/.claude/.../repo-health.sh ...`, `bash -c 'gh ...'`, `command gh ...`, `"gh" ...` | inside |
| the absolute path of `repo-health.sh` | inside |
| `timeout 30 gh ...` | not run: macOS has no `timeout` |

In the researcher and verifier runs of the same day, 9 joined calls (8 distinct commands: four piped
into `head` or `tail`, four `for` loops) failed the same way; one `gh ...; gh ...` pair worked; 7
bare `gh` and `repo-health.sh` calls worked; the bare `reddit-search.sh` call stopped for want of
credentials, which it would do inside or outside, so it says nothing. `gcp-skus.sh` and
`reddit-search.sh` were not run under the sandbox: their rule is the same `excludedCommands` rule,
not a separate measurement.

`tests/test_agent_guard.py` (`test_gh_and_scripts_share_a_call_only_with_each_other`) holds the same
lists, so the guard's verdict is tested against them. To check a new Claude Code release, run these
commands in one `claude -p` session with the flags above and compare.

## `gh` and the research scripts run alone (2026-09-29)

The guard now refuses a call that holds `gh` or a research script together with any other command
(the measurements are in the section above), and the refusal and `hooks/agent-sandbox.md` say what
to write instead. Both sets ran once per model on the branch tip, `0c85bc9`, one set after the
other, with `~/notes` unchanged after each case.

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | PASS (7, $0.09) | PASS (11, $0.26) |
| cold-review-skip | PASS (5, $0.08) | PASS (5, $0.17) |
| delta-review | FAIL (8, $0.09) | PASS (6, $0.19) |
| delta-review-record | FAIL (7, $0.09) | PASS (6, $0.20) |
| guard-applies | SKIP (opus only) | PASS (2, $0.06) |
| record-skip | PASS (6, $0.08) | PASS (6, $0.18) |
| research-ideas | PASS (30, $0.37) | PASS (36, $1.28) |
| research-quick | PASS (7, $0.15) | PASS (11, $0.31) |
| spec-miscite | PASS (7, $0.09) | PASS (7, $0.13) |
| spike-inherited | PASS (5, $0.07) | PASS (6, $0.18) |
| wrong-figure | PASS (7, $0.13) | PASS (6, $0.16) |

Skill evals:

| Case | Sonnet | Opus |
|---|---|---|
| cold-review-delta | FAIL (8, $0.12) | PASS (5, $0.20) |
| research-quick-flow | PASS (19, $0.22) | PASS (20, $0.40) |
| spec-done | PASS (6, $0.12) | PASS (6, $0.23) |
| spec-quick | PASS (17, $0.22) | PASS (14, $0.37) |

Totals: Sonnet $1.24 (agent evals) and $0.69 (skill evals), Opus $3.13 and $1.20.

**Sonnet's three failures are on `main` too.** I ran the four Sonnet cases that failed on the branch
twice on `main` (`90304a5`), one set after the other:

| Case (Sonnet) | branch, `0c85bc9` | `main`, two runs |
|---|---|---|
| absence-claim | PASS | PASS, PASS |
| delta-review | FAIL | FAIL, FAIL |
| delta-review-record | FAIL | PASS, FAIL |
| cold-review-delta | FAIL | FAIL, PASS |

`delta-review` and `delta-review-record` fail the same line on both: the reply's table has a row for
the decoy, Background's "2,000 words", which is outside the logged change
(`!(?im)^\|[^\n]*\b2,?000\b`). `cold-review-delta` fails only "it's a delta review" and passes
the other seven checks. Opus passes all three. None of them runs `gh`, so they are left as they are.

**The branch's first run, at `2f2dbb6`, had a fourth Sonnet failure.** That run (Sonnet 7 of 10 and
3 of 4, Opus 11 of 11 and 4 of 4, $6.83) came before the wording commit. `absence-claim` failed
after the guard refused three of its commands: a `for` loop of `gh` calls, `gh ...; gh .../readme |
grep | head` and `gh .../readme | head -40`. The guard's message said only to put such a command in
a call of its own. Its WRONG row named `dawidbera/kube-finops-autopilot` without backticks or a URL,
which the case's second pattern needs, so the grader's format played a part too. `0c85bc9` changes
the refusal and `agent-sandbox.md` to name what works: several `gh` commands joined by `;`, `--jq`
in place of `head` and `grep`, and several repos to `repo-health.sh`.

Commands the guard refused, replayed through the branch's guard from each run's
`permission_denials`:

| Run | Refused | By the new rule |
|---|---|---|
| first, Sonnet | 7 | 4: three in absence-claim, and `gh ...; echo ---; gh ...` in research-ideas |
| first, Opus | 3 | 2: `curl ...; gh ...` in research-ideas, `gh ...; gh ... \| grep` in research-quick |
| final, Sonnet | 2 | 0 (`sed -i` on a note, `git show > file`) |
| final, Opus | 1 | 0 (`awk`, which guard-applies is meant to trigger) |

One run per cell, so this shows the wording reaching the agents, not by how much. No case needs
`gh` or `repo-health.sh`, so a pass shows no regression and does not exercise the new rule; the
measurements above and `test_agent_guard.py` do that. Spend on these runs: $6.83 first, $0.81 for
the `main` runs, $6.26 final.

Three commits followed the runs, and the evals did not cover them: the record above, and two guard
fixes from a review of the rule (`bash -c` followed four deep, as the rest of the guard is, and a
sed address pattern that could take minutes on a run of backslashes). The unit suite (322 tests),
the replay of recorded agent commands (8 changed verdicts, as before) and the agreement check over
the 18 informative `gh` and script commands ran on them; the evals did not.

## Quoted argument hints in `/spec` and `/research` (2026-09-30)

`skills/spec/SKILL.md`'s frontmatter did not parse: its `argument-hint` began with `[quick]`, which
YAML reads as a flow sequence followed by stray text. `claude plugin validate` reported that the
skill then loads with empty metadata, and the session's skill list showed `/spec` by its heading and
without `disable-model-invocation` hiding it. `/research`'s hint has the same shape, and Ruby's
strict YAML parser rejected it too, though Claude Code's parser and the plugin validator did not.
Both hints are now quoted, with the text unchanged. Fixing `/spec` turns on its `allowed-tools`
list, which may not have been enforced since the quick mode added the `[quick]` on 2026-09-25, so
the point of these runs is whether a command it needs is missing from that list.

Both sets ran once per model on the branch tip, `4d1d5f3`, one set after the other, with `~/notes`
unchanged after each case.

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | PASS (9, $0.13) | PASS (18, $0.43) |
| cold-review-skip | PASS (8, $0.08) | PASS (5, $0.20) |
| delta-review | FAIL (6, $0.08) | PASS (7, $0.25) |
| delta-review-record | FAIL (6, $0.09) | PASS (7, $0.18) |
| guard-applies | SKIP (opus only) | PASS (2, $0.09) |
| record-skip | PASS (7, $0.09) | PASS (7, $0.15) |
| research-ideas | PASS (27, $0.42) | PASS (35, $1.37) |
| research-quick | PASS (9, $0.18) | PASS (11, $0.33) |
| spec-miscite | PASS (5, $0.07) | PASS (5, $0.14) |
| spike-inherited | PASS (5, $0.07) | PASS (6, $0.13) |
| wrong-figure | PASS (6, $0.11) | PASS (5, $0.19) |

Skill evals:

| Case | Sonnet | Opus |
|---|---|---|
| cold-review-delta | FAIL (4, $0.10) | PASS (4, $0.21) |
| research-quick-flow | PASS (28, $0.33) | PASS (17, $0.36) |
| spec-done | PASS (6, $0.13) | PASS (8, $0.26) |
| spec-quick | PASS (20, $0.25) | PASS (12, $0.35) |

Totals: Sonnet $1.32 (agent evals, 8 of 10) and $0.81 (skill evals, 3 of 4), Opus $3.46 (11 of 11)
and $1.17 (4 of 4).

**`/spec` passes both skill cases that run it, on both models.** `spec-done` and `spec-quick` run
`/spec` headless, where a command missing from `allowed-tools` would be denied. Neither was, so the
list is complete for what those cases exercise. They do not exercise `spike` mode's
`prepare-spike.sh` and `run-spike.sh` patterns, which stay untested here.

**Sonnet's failures match `main`.** `delta-review` and `delta-review-record` fail the same line as
in the section above, the decoy row `!(?im)^\|[^\n]*\b2,?000\b`, and Opus passes both. Neither
involves the two skills this change touches.

**`cold-review-delta` on Sonnet is flaky on both sides.** It runs `/cold-review`, which this change
does not touch, and its failing check varies: "it's a delta review" or "the unlogged Rollback edit
is named", sometimes both. I ran it again, one run at a time, on the branch and on `main`
(`c05ef6a`):

| Sonnet runs of `cold-review-delta` | Result |
|---|---|
| branch `4d1d5f3`, five runs | FAIL (Rollback), FAIL (delta review), FAIL (Rollback), PASS, FAIL (delta review): 1 of 5 |
| `main` `c05ef6a`, two runs | PASS, FAIL (both checks): 1 of 2 |
| `main` `90304a5`, two runs, from the section above | FAIL, PASS: 1 of 2 |

That is 1 of 5 against 2 of 4, too few runs to tell the branch from `main`. It is not shown to be
caused by the change, and it is not shown to be free of it either.

Spend: $6.76 on the four runs, and $0.66 on the six single-case runs, so $7.42.

## Plugin marketplace part 1, W2: scripts, agents, guard and sandbox find their own root (2026-09-30)

W2 changed all four agent files, `run-agent.sh`, `agent-def.py`, the guard (its script lists, the
`~/.claude/plugins/` rule and the symlink-spelling check), both settings files (now rendered per run
by the new `agent-settings.py`) and both eval runners. Both sets ran once per model on the branch
tip after the last W2 commit, one set after the other, with `~/notes` unchanged after each.

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | PASS (8, $0.20) | PASS (14, $0.40) |
| cold-review-skip | PASS (7, $0.07) | PASS (5, $0.19) |
| delta-review | FAIL (6, $0.10) | PASS (9, $0.31) |
| delta-review-record | PASS (6, $0.09) | PASS (7, $0.23) |
| guard-applies | SKIP (opus only) | PASS (2, $0.09) |
| record-skip | PASS (5, $0.06) | PASS (6, $0.22) |
| research-ideas | PASS (24, $0.38) | PASS (57, $2.23) |
| research-quick | PASS (8, $0.18) | PASS (10, $0.31) |
| spec-miscite | PASS (7, $0.11) | PASS (7, $0.21) |
| spike-inherited | PASS (4, $0.08) | PASS (5, $0.21) |
| wrong-figure | PASS (7, $0.13) | PASS (7, $0.14) |

Skill evals:

| Case | Sonnet | Opus |
|---|---|---|
| cold-review-delta | PASS (5, $0.11) | PASS (6, $0.22) |
| research-quick-flow | PASS (14, $0.21) | PASS (22, $0.46) |
| spec-done | PASS (6, $0.13) | PASS (9, $0.27) |
| spec-quick | PASS (17, $0.25) | PASS (12, $0.35) |

Totals: Sonnet $1.41 (agent evals, 9 of 10) and $0.70 (skill evals, 4 of 4); Opus $4.54 (11 of 11)
and $1.29 (4 of 4). Spend $7.94 in all, under the $10-$12 the spec estimated.

**Sonnet's one failure is the known one.** `delta-review` fails the decoy-row check
`!(?im)^\|[^\n]*\b2,?000\b`, as it did on `main` and in the section above; Opus passes it. Nothing
in W2 touches that case's inputs. `delta-review-record` and `cold-review-delta`, which failed on
Sonnet in the last section, passed this time; those two were already known to vary between runs.

**The agents reach their scripts and files through the rendered settings.** Every case that runs a
research script (`research-ideas`, `research-quick`, `wrong-figure`) or reads the plugin's own files
passed on both models, so the absolute `${CLAUDE_PLUGIN_ROOT}` spelling in the agent prompts, the
guard's `OUTSIDE_SPELLINGS` and the rendered `excludedCommands` agree in a real run. This ran on the
symlink install with the checkout as the root, so it does not cover a plugin cache path: spike 3
still needs that.

**`tests/replay_guard.py`** reports 0 recorded reads refused and 8 headless commands with a
different verdict than the one recorded. The same 8 appear at `edca724`, before W2, so they come
from PR #27's `check_outside_only`, not from this change. Zero refused reads is the count spike
question 4 asks for.

## Plugin marketplace part 1, after W2's cold review of the guard (2026-09-30)

The cold review of the W2 guard diff (`docs/specs/records/2026-09-29-plugin-marketplace-1-plumbing-record.md`,
"Guard diff review") led to two guard changes: the resolved spelling of the session results folder
counts only while it stays inside `~/.claude/projects` (`c0028cb`), and a path with `..` after a
symlink is refused when the shell's and the tools' readings differ (`4798ee5`). Both sets ran once
per model on the branch tip after them, `06b4288` plus the replay fix, one set after the other,
with `~/notes` unchanged after each. Before the runs, the plugin that spike 3 had installed into
the real `~/.claude` (enabled in `settings.json`, at `860000b`) was uninstalled with
`claude plugin uninstall` and `claude plugin marketplace remove`, so the headless sessions loaded
only the symlinked skills, as in the runs above.

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | FAIL (8, $0.10) | PASS (11, $0.32) |
| cold-review-skip | PASS (7, $0.07) | PASS (6, $0.17) |
| delta-review | FAIL (7, $0.08) | PASS (6, $0.18) |
| delta-review-record | PASS (7, $0.09) | PASS (7, $0.24) |
| guard-applies | SKIP (opus only) | PASS (2, $0.06) |
| record-skip | PASS (6, $0.07) | PASS (5, $0.14) |
| research-ideas | PASS (31, $0.43) | PASS (46, $1.50) |
| research-quick | PASS (8, $0.19) | PASS (9, $0.21) |
| spec-miscite | PASS (5, $0.06) | PASS (6, $0.14) |
| spike-inherited | PASS (4, $0.05) | PASS (6, $0.14) |
| wrong-figure | PASS (5, $0.11) | PASS (8, $0.18) |

Skill evals:

| Case | Sonnet | Opus |
|---|---|---|
| cold-review-delta | FAIL (4, $0.11) | PASS (3, $0.20) |
| research-quick-flow | PASS (17, $0.22) | PASS (17, $0.36) |
| spec-done | PASS (6, $0.12) | PASS (5, $0.23) |
| spec-quick | PASS (16, $0.25) | PASS (16, $0.38) |

Totals: Sonnet $1.25 (agent evals, 8 of 10) and $0.70 (skill evals, 3 of 4); Opus $3.27 (11 of 11)
and $1.16 (4 of 4). Two reruns of `absence-claim` on Sonnet cost $0.29 more, so $6.67 in all.

**Three Sonnet failures, none from the guard.** No case's transcript holds a `Blocked by agent-guard`
reply except `guard-applies`, which is meant to be blocked.
- `delta-review` fails the decoy-row check `!(?im)^\|[^\n]*\b2,?000\b`, as it did in both sections
  above; Opus passes it.
- `cold-review-delta` fails "it's a delta review", one of the two checks that vary between runs
  (see the 2026-09-30 section on quoted argument hints: 1 of 5 on the branch, 2 of 4 on `main`).
  It passed on Sonnet in W2's section and on Opus here.
- `absence-claim` passed on Sonnet in W2's section and failed here. The reply marks the pull-request
  bots as `WRONG` but names them as `dawidbera/kube-finops-autopilot`, with no backticks or
  `github.com/`, and none of the four repos the grader lists, so the check found no match. Two reruns
  alone gave PASS and FAIL: 1 of 3 on this tip. That is search and wording variance, not a
  change in what the agent can read; it is not shown to be free of the change either.

**`tests/replay_guard.py`** reports 0 recorded reads refused and the same 8 headless commands with a
different verdict as at `edca724`. That took two fixes to the replay itself (`7731c56`, and the
resolved-root fix after it): it judged spike 3's run, which read its plugin cache, with a
checkout's guard (1 read refused), and it left the last read's working directory set for the
Bash half (153 differences). The replay now judges each headless run by the plugin root its
`agents.json` names, and keeps each call's directory to itself.

## Plugin marketplace part 2, W3 to W5: the skills, tests and evals on the plugin layout (2026-09-30)

Both sets ran once per model on `3a97fc3`, W4's commit, one set after the other. The skill evals
loaded the checkout with `--plugin-dir` and typed `/claude-skills:<skill>`. The agent evals load no
plugin: `agent-def.py --root` writes the checkout into each definition, and each rendered
`sandbox.md` names the checkout's `hooks/run-agent.sh` with no `${CLAUDE_PLUGIN_ROOT}` left in it.
The machine still had the old `~/.claude/skills` and `hooks` links, pointing at another checkout;
the namespaced prompts reach this one.

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | PASS (8, $0.12) | PASS (9, $0.26) |
| cold-review-skip | PASS (7, $0.09) | PASS (6, $0.16) |
| delta-review | FAIL (8, $0.08) | PASS (6, $0.18) |
| delta-review-record | FAIL (7, $0.08); reruns FAIL, FAIL | PASS (9, $0.21) |
| guard-applies | SKIP (opus only) | PASS (2, $0.06) |
| record-skip | PASS (6, $0.07) | PASS (7, $0.18) |
| research-ideas | FAIL (29, $0.54); reruns PASS, PASS | PASS (53, $2.04) |
| research-quick | PASS (9, $0.16) | PASS (10, $0.25) |
| spec-miscite | PASS (6, $0.08) | PASS (6, $0.16) |
| spike-inherited | PASS (5, $0.07) | PASS (9, $0.18) |
| wrong-figure | PASS (6, $0.09) | PASS (7, $0.19) |

Skill evals:

| Case | Sonnet | Opus |
|---|---|---|
| cold-review-delta | FAIL (4, $0.13) | PASS (4, $0.26) |
| research-quick-flow | PASS (17, $0.24) | PASS (21, $0.59) |
| spec-done | PASS (6, $0.15) | FAIL (11, $0.31); reruns PASS, PASS |
| spec-quick | PASS (30, $0.38) | PASS (15, $0.45) |

Totals: Sonnet $1.38 (agent evals, 7 of 10) and $0.90 (skill evals, 3 of 4); Opus $3.86 (11 of 11)
and $1.61 (3 of 4). Reruns of the three failures not seen in the section above cost $1.79 more, so
$9.54 in all.

**No failure is from the plugin layout or the guard.** No transcript holds a `Blocked by agent-guard`
reply except `guard-applies`, which is meant to be blocked. The skills ran under their namespaced
names, and each failing skill case passed every check but one.
- `delta-review` and `cold-review-delta` fail on Sonnet as in the section above, on the same checks.
- `delta-review-record` fails the same decoy-row check as `delta-review`, three times in three
  runs. It failed that check on Sonnet in three of the five sections above and passed in the other
  two. `hooks/agents/cold-reviewer.md` is unchanged since `06b4288`; `hooks/agent-sandbox.md`
  changed only its two script paths.
- `research-ideas` on Sonnet tagged its candidate pool with idea types (`[dataset]`, `[game]`,
  `[lab]`), which the case refuses; both reruns passed.
- `spec-done` on Opus left the status at in-progress and wrote the Implementation note, but its
  reply said "Once W2 is built" rather than a phrase the "names W2 as not landed" check reads; both
  reruns passed.

**`tests/replay_guard.py`** reports 0 recorded reads refused and 29 headless commands with a
different verdict. Before W4's replay fix it was 58: 29 more were the old install's
`~/.claude/skills/research/scripts/...` spelling, which W3 stopped allowing, and the replay now moves
to the plugin root. All 29 left are `gh` or a research script in a call with other commands, PR #27's
`check_outside_only`, recorded by sessions that ran the other checkout's older guard. There were 8
in the section above; the rest are runs since.


## Report steps without line counts (2026-09-29)

Recorded on 2026-09-29 at `dad662d`, on a branch from before the history rewrite and the plugin
work, and carried onto `main` on 2026-09-30 by cherry-pick. These runs used the symlinked skills;
the wording change is the same on the plugin layout.

The end-of-run reports in `/research` (step 10), `/spec` (step 6 item 1), `/spec spike` (7e) and
`/spec done` (step 8) say "one short line for each" of the items they list, in place of "in N lines
or fewer", after a prompt audit found the counts were a fixed ceiling on a list that already sets
the report's length. Skill evals only: no agent file changed. `EVAL_MODEL=sonnet` now resolves to
`claude-sonnet-5-5`; every earlier Sonnet run was `claude-sonnet-5`.

| Case | Sonnet | Opus |
|---|---|---|
| cold-review-delta | FAIL (5 turns, $0.14), re-run FAIL (5, $0.15) | FAIL (7, $0.30) |
| research-quick-flow | PASS (24, $0.36) | PASS (15, $0.43) |
| spec-done | PASS (10, $0.18) | PASS (11, $0.34) |
| spec-quick | PASS (18, $0.32) | PASS (12, $0.43) |

Totals: Sonnet $1.00, and $0.15 for the re-run; Opus $1.50. `~/notes` was left as it was. The three
cases that reach a changed report step passed on both models; `/spec spike`'s 7e has no case.
`cold-review-delta` touches no changed file, and both its failures are the grader missing new wording,
not a wrong prompt:
- Sonnet, twice: the prompt was a correct delta review (right base, logged line quoted, unlogged
  Rollback edit named), but the reply said "State is `delta`", never "delta review", which the
  check greps for.
- Opus: it named the unlogged Rollback edit as "Something not written down … `## Rollback` isn't on
  it", which the check's `UNLOGGED` pattern doesn't accept.

## /implement part 1: check-spec.py --drift, scan-diff.py and the implement-verifier (2026-09-30)

Both agent-eval sets ran once per model on `f82f9a1`, part 1's last work-item commit, Sonnet first and
then Opus, never at the same time. W1 changes `skills/spec/scripts/check-spec.py` and W3 adds
`skills/implement/`: its verifier prompt, sandbox settings and two scripts. No agent file and no
skill's steps changed, so the skill evals didn't run. `EVAL_MODEL=sonnet` ran on `claude-sonnet-5-5`.

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | PASS (8, $0.11) | PASS (13, $0.27) |
| cold-review-skip | PASS (6, $0.08) | PASS (6, $0.15) |
| delta-review | FAIL (8, $0.08) | PASS (4, $0.15) |
| delta-review-record | FAIL (6, $0.08) | PASS (6, $0.17) |
| guard-applies | SKIP (opus only) | PASS (2, $0.06) |
| record-skip | PASS (5, $0.07) | PASS (6, $0.15) |
| research-ideas | PASS (32, $0.49) | PASS (51, $1.90) |
| research-quick | PASS (9, $0.15) | PASS (10, $0.28) |
| spec-miscite | PASS (7, $0.07) | PASS (7, $0.17) |
| spike-inherited | PASS (5, $0.06) | PASS (7, $0.17) |
| wrong-figure | PASS (5, $0.09) | PASS (7, $0.17) |

Totals: Sonnet $1.29 (8 of 10), Opus $3.63 (11 of 11), $4.92 in all. No reruns.

Both Sonnet failures are the decoy-row check (`!(?im)^\|[^\n]*\b2,?000\b`) that `delta-review` and
`delta-review-record` have failed on Sonnet in earlier sections, among them the plugin marketplace
part 2 section above. Neither case reaches a file this part changed: `hooks/agents/cold-reviewer.md`
and `hooks/agent-sandbox.md` are unchanged. They weren't re-run on `spec-implement-refresh` without
this part.

## /implement part 2: the skill, its implementer, the /spec hand-off and the docs (2026-09-30)

Both eval sets ran in full once per model after W7 (`31af9e5`), skill evals first, Sonnet then Opus,
one set after the other. `EVAL_MODEL=sonnet` ran on `claude-sonnet-5-5`. The implement cases also
run the implementer (`run-implementer.sh`, capped at $5 under the runner) and a verifier
(`run-verify.sh`, $5): their costs, from each `run-<n>.json` and `V<n>/run.json`, are given apart
from the skill session's, which is all the runner prints. The same goes for the research and spec
agents the other skill cases launch. No existing agent file changed; W4 adds
`hooks/agents/implementer.md`, which no agent eval runs.

Agent evals:

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | FAIL (12, $0.14) | PASS (12, $0.24) |
| cold-review-skip | PASS (5, $0.07) | PASS (6, $0.16) |
| delta-review | PASS (11, $0.10) | PASS (6, $0.19) |
| delta-review-record | FAIL (8, $0.08) | PASS (9, $0.20) |
| guard-applies | SKIP (opus only) | PASS (2, $0.06) |
| record-skip | PASS (6, $0.07) | PASS (6, $0.17) |
| research-ideas | FAIL (31, $0.55) | FAIL (55, $2.07); rerun PASS (45, $1.68) |
| research-quick | PASS (10, $0.16) | FAIL (11, $0.28); rerun PASS (12, $0.25) |
| spec-miscite | PASS (7, $0.08) | PASS (6, $0.15) |
| spike-inherited | PASS (6, $0.07) | PASS (6, $0.16) |
| wrong-figure | PASS (7, $0.08) | PASS (7, $0.12) |

Skill evals (skill session; then the agents it launched):

| Case | Sonnet | Opus |
|---|---|---|
| cold-review-delta | PASS (5, $0.13) | PASS (6, $0.20) |
| implement-basic | PASS (33, $0.26); implementer $0.17, verifier $0.10 | PASS (35, $0.46); implementer $0.38, verifier $0.21 |
| implement-trap | PASS (20, $0.17); implementer $0.08 | PASS (21, $0.29); implementer $0.16 |
| research-quick-flow | PASS (21, $0.29); researcher $0.27, verifier $0.16 | PASS (20, $0.39); researcher $0.38, verifier $0.22 |
| spec-done | PASS (9, $0.16) | PASS (10, $0.24) |
| spec-done-branch | PASS (6, $0.14) | PASS (6, $0.19) |
| spec-done-implement | PASS (7, $0.15) | PASS (11, $0.27) |
| spec-quick | PASS (15, $0.28); spec-verifier $0.06 | PASS (12, $0.33); spec-verifier $0.12 |

The work items' Done when runs, before the full sets, in order:

| Run | Sonnet | Opus |
|---|---|---|
| W4 `implement-basic`, first try | FAIL (16, $0.14): launched in the background, the headless session ended its turn and the implementer was killed with no result | not run |
| W4 `implement-basic`, second try | FAIL (34, $0.28); implementer $0.18, verifier $0.10: the grader wanted the verifier's table unindented | not run |
| W4 `implement-basic` | PASS (33, $0.28); implementer $0.16, verifier $0.07 | PASS (35, $0.46); implementer $0.36, verifier $0.20 |
| W5 `spec-done-implement` before the change | PASS (6, $0.15), which the first Done when expected to fail | PASS (11, $0.33), likewise |
| W5 `spec-done-branch` before the change | FAIL (10, $0.15), on both checks | FAIL (11, $0.37), on both checks once re-graded |
| W5 the three `spec-done` cases after | FAIL `spec-done-branch` on the grader (6, $0.11), PASS the other two ($0.26); rerun all PASS ($0.36) | all PASS ($0.72) |
| W5 `/spec finish` by hand on `implement-basic`'s fixture | read-at moved to HEAD, no `DRIFT:` ($0.19; spec-verifier $0.12) | not run |
| W6 `implement-trap` | PASS (19, $0.17); implementer $0.08 | PASS (19, $0.28); implementer $0.15 |
| W6 the trap's control | FAIL on "no commit ends (W1)", as wanted (44, $0.41); implementer $0.21 + $0.23, verifiers $0.10 + $0.07 | FAIL on "no commit ends (W1)", as wanted (35, $0.46); implementer $0.39, verifier $0.20 |

Totals: agent evals Sonnet $1.40 (7 of 10), Opus $3.81 (9 of 11) and $1.93 for the two reruns;
skill evals Sonnet $2.42 (8 of 8) and Opus $3.84 (8 of 8), agents included; the Done when runs
$7.78, agents included. $21.18 in all.

- **Sonnet's three agent-eval failures are ones seen before, in files this part didn't change.**
  `delta-review-record` fails the decoy-row check (`!(?im)^\|[^\n]*\b2,?000\b`) again, as in part
  1's section; `delta-review` passed this time. `research-ideas` tagged its candidate pool with idea
  types (`[dataset]`, `[game]`, `[lab]`), as in the plugin marketplace part 2 section.
  `absence-claim` found other prior art (an AWS blog's GitOps right-sizing job, `kube-finops-autopilot`)
  rather than the names the case reads for, as in the plugin marketplace part 1 section.
- **Opus's two failures came from outside the run.** Another session committed to `~/notes` at
  22:38:03, a minute after the run started, so `research/2026-09-29-agentic-ai-linkedin-repo-ideas.md`
  left `git status` and both cases' "nothing else in ~/notes changed" check failed. Both passed on a
  rerun, with `~/notes` unchanged throughout.
- **Two graders were fixed during the Done when runs, each to read a reply the skill got right.**
  `implement-basic` now finds the verifier's table indented under its `- Verifier V1` bullet.
  `spec-done-branch` no longer counts the worktree's directory name, which is the spec's basename
  and so in every `/spec done` path. That had made Opus's "before" reply pass. It now reads a
  paragraph, not a sentence, since Sonnet's right answer gave the path and then "run it from that
  folder". The saved "before" replies still fail with the fixed grader, and the "after" ones pass.
- **The control's verifier said `Implementation holds: no` in V1**, on Sonnet: the branch diff
  changed `tests/test_calc.py` (a test `/code-review --fix` added in clean-up), the spec's status
  and the record, none in W1's Files. After the implementer's fix round, V2 said `yes`. The verifier reads
  the whole branch, clean-up and record commits included, against one work item's Files.

## Review fixes, Wave 1: eval round 1, with skills' own permissions and the answer keys hidden (2026-10-01)

The first round after the fixes from the 2026-10-01 review (#35 to #44), and the first with honest
evals (#43). The skill evals pre-approve only the Skill tool, so a call outside a skill's
`allowed-tools` is refused and fails its case. The agents review a clone with `tests/*-evals`
removed and the answer keys blanked from its history, and the verifier cases need their true
claims CONFIRMED. Claude Code 2.1.286, `EVAL_MODEL=sonnet` and `opus`, one set at a time. The first
Sonnet agent set was cut short by an account usage limit: four cases ended without a verdict, and
it was discarded and rerun. Two fix-ups landed during the round, #45 (`6d80a9e`) and #46
(`86364e6`), and the cases they affect were rerun after each on both models.

Agent evals, at `6d80a9e`:

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | PASS (8, $0.14) | PASS (14, $0.29) |
| cold-review-skip | PASS (5, $0.09) | PASS (7, $0.20) |
| delta-review | FAIL (5, $0.09) | PASS (6, $0.22) |
| delta-review-record | PASS (6, $0.10) | PASS (6, $0.27) |
| guard-applies | SKIP (opus only) | PASS (2, $0.07) |
| record-skip | PASS (6, $0.10) | PASS (7, $0.20) |
| research-ideas | PASS (36, $0.88) | PASS (43, $2.08) |
| research-quick | PASS (9, $0.18) | PASS (11, $0.39) |
| spec-miscite | PASS (6, $0.11) | PASS (7, $0.19) |
| spike-inherited | PASS (5, $0.10) | PASS (7, $0.14) |
| wrong-figure | PASS (6, $0.09) | PASS (7, $0.16) |

Skill evals on Sonnet (skill session; then the agents it launched; then why it failed):

| Case | `ba885bf` | after #45 (`6d80a9e`) | after #46 (`86364e6`) |
|---|---|---|---|
| cold-review-delta | PASS (5, $0.14) | not rerun | not rerun |
| implement-basic | FAIL (24, $0.25); implementer $0.24: the verifier's scratch writes refused (#45) | FAIL (32, $0.33); implementer $0.22, verifier $0.11: a refused `grep` in the cost report | PASS (35, $0.35); implementer $0.23, verifier $0.10 |
| implement-trap | FAIL (18, $0.21); implementer $0.08: a refused `ls -R … \| grep` | PASS (18, $0.21); implementer $0.09 | PASS (23, $0.24); implementer $0.09 |
| research-quick-flow | FAIL (23, $0.33); researcher $0.28, verifier $0.20: a refused `mkdir … && mv` of a misnamed brief | FAIL (21, $0.27); researcher $0.23, verifier $0.20: a refused `cd … && git …; ls …` | PASS (22, $0.27); researcher $0.21, verifier $0.28 |
| spec-done | PASS (10, $0.17) | not rerun | PASS (12, $0.19) |
| spec-done-branch | PASS (6, $0.14) | not rerun | not rerun |
| spec-done-implement | FAIL (12, $0.21): a refused `cat >> <record> <<EOF` | FAIL (14, $0.20): a refused `H=…/git-read.py; ls …; $H …` | PASS (13, $0.20) |
| spec-quick | PASS (16, $0.27); spec-verifier $0.08 | not rerun | not rerun |

Skill evals on Opus:

| Case | after #45 (`6d80a9e`) | after #46 (`86364e6`) |
|---|---|---|
| cold-review-delta | PASS (3, $0.26) | not rerun |
| implement-basic | FAIL (35, $0.56); implementer $0.47, verifier $0.23: a refused `ls` of the run dir | FAIL (35, $0.58); implementer $0.46, verifier $0.21: a refused `find` of the run files |
| implement-trap | FAIL (21, $0.40); implementer $0.17: a refused `ls` of the run dir | PASS (20, $0.38); implementer $0.17 |
| research-quick-flow | PASS (21, $0.52); researcher $0.54, verifier $0.34 | PASS (25, $0.53); researcher $0.42, verifier $0.24 |
| spec-done | FAIL (14, $0.37): a refused `H=…/git-read.py; R=…; $H -C $R log …` | PASS (12, $0.34) |
| spec-done-branch | PASS (5, $0.25) | not rerun |
| spec-done-implement | FAIL (11, $0.37): a refused `cd …; ls …; G=…` | PASS (14, $0.36) |
| spec-quick | PASS (13, $0.44); spec-verifier $0.16 | not rerun |

Totals, agents included: agent evals Sonnet $1.89 (9 of 10) and Opus $4.22 (11 of 11), plus $1.28
for the Sonnet set the usage limit cut short; skill evals Sonnet $2.62, $1.87 and $2.16 for the
three runs above, and Opus $5.05 and $3.69. $22.78 in all.

- **The honest graders found one real bug.** `/implement` pre-approved the verifier's scratch writes
  with `Write(~/.cache/implement-verify/**)`, a rule Claude Code accepts and never consults: it
  checks the Write tool against `Edit(path)` rules only. Earlier rounds pre-approved every tool, so
  none saw it; a user would have been asked three times per verification. #45 makes it an `Edit`
  rule, and `tests/test_skill_frontmatter.py` now fails on any such rule. After it, every real
  check in `implement-basic` passes on both models: the verifier ran, said `holds: yes`, and W1's
  Done when fails at the setup's commit and passes on the branch.
- **Every other skill-eval failure was a refused improvised command, on both models,** with the
  case's content checks all passing: a shell variable holding `git-read.py`'s long path, a `cd`,
  `ls`, `echo` or `grep` joined to an allowed command, and `ls` or `find` to locate run files. In a
  real session each is a permission prompt. #46 told `/implement`, `/spec` and `/research` to run
  one command per Bash call, with full paths, and to find files with Glob. After it, Sonnet passed
  all 5 reruns and Opus 4 of 5. Opus's one failure is a `find` for `implement-basic`'s cost
  report, which the spend ledger planned for the implementer (stream S2) replaces.
- **Sonnet's `delta-review` failed the decoy-row check** (`!(?im)^\|[^\n]*\b2,?000\b`), as in most
  sections since 2026-09-29; `delta-review-record` passed this time.
- **The agent evals hold with the answer keys out of reach** and the true claims required to be
  CONFIRMED: Sonnet 9 of 10, Opus 11 of 11.
- The 2026-09-30 section's conclusion that `/spec`'s `allowed-tools` was complete wasn't shown then,
  since those runs pre-approved every tool. This round's passes are the first that show it, for the
  paths these cases exercise.

## One review parser: W5's eval round (2026-10-01)

W5 of `docs/specs/2026-10-01-review-parser.md`, on `implement/2026-10-01-review-parser` at `feb52be`:
`mdcheck.read_review()` for `review-state.py` and `check-spec.py`, one heading rule, and two lines
in `/cold-review` step 2 (unlogged lines go under `## Changes since the review`; a `record-moved:`
is relayed with a `git mv` for the user). Run by hand from the worktree, `EVAL_MODEL=sonnet` and
`opus`, one set at a time. The four skill-eval cases that failed outside the spec's accepted list
were rerun once on the model they failed on, on 2026-10-02, and all passed.

Agent evals:

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | PASS (10, $0.21) | PASS (12, $0.30) |
| cold-review-skip | PASS (5, $0.10) | PASS (7, $0.27) |
| delta-review | FAIL (7, $0.12): the decoy-row check | PASS (7, $0.26) |
| delta-review-record | FAIL (6, $0.11): the decoy-row check | PASS (10, $0.28) |
| guard-applies | SKIP (opus only) | PASS (2, $0.10) |
| record-skip | PASS (5, $0.10) | PASS (8, $0.26) |
| research-ideas | PASS (28, $0.79) | PASS (42, $1.90) |
| research-quick | PASS (9, $0.19) | PASS (10, $0.33) |
| spec-miscite | PASS (7, $0.11) | PASS (7, $0.27) |
| spike-inherited | PASS (6, $0.07) | PASS (6, $0.25) |
| wrong-figure | PASS (6, $0.11) | PASS (7, $0.23) |

Skill evals, with the agents a case launches; "rerun" is the 2026-10-02 run of that case:

| Case | Sonnet | Opus |
|---|---|---|
| cold-review-delta | PASS (5, $0.14) | FAIL (6, $0.29): see below; rerun PASS (6, $0.28) |
| implement-basic | FAIL (36, $0.37); implementer and verifier $0.56: a refused `find` of the run files; rerun PASS (38, $0.40); agents $0.64 | FAIL (36, $0.59); agents $1.12: a refused `skills/implement/scripts/run-cost.py`, which doesn't exist; rerun PASS (36, $0.59); agents $1.12 |
| implement-trap | PASS (18, $0.21); implementer $0.23 | PASS (22, $0.41); implementer $0.33 |
| research-quick-flow | PASS (20, $0.28); researcher and verifier $0.35 | PASS (24, $0.50); researcher and verifier $0.79 |
| spec-done | PASS (13, $0.18) | PASS (12, $0.35) |
| spec-done-branch | PASS (8, $0.15) | FAIL (8, $0.28): the grader missed a right reply; rerun PASS (7, $0.27) |
| spec-done-implement | PASS (15, $0.21) | PASS (12, $0.35) |
| spec-quick | PASS (19, $0.26); spec-verifier $0.05 | PASS (22, $0.47); spec-verifier $0.10 |

Totals, agents included: agent evals Sonnet $1.91 (8 of 10) and Opus $4.46 (11 of 11); skill evals
Sonnet $2.99 (7 of 8) and Opus $5.57 (5 of 8); reruns $3.29, plus $0.12 for two runs interrupted by
hand that graded nothing. $18.34 in all.

- **W5's Done when holds.** After the reruns, the only failures are the two the spec accepts: Sonnet
  `delta-review` and `delta-review-record` on the decoy-row check (`!(?im)^\|[^\n]*\b2,?000\b`),
  as in most sections since 2026-09-29.
- **Opus `cold-review-delta` failed once, not on the changed paths.** The case asks for `prompt`
  mode. Opus handed the prompt over, then sent a second message correcting its own table header
  ("What would substitute it"), and the grader reads only the final message. W5's lines cover the
  `unlogged` and `record-moved:` states, which a delta case doesn't reach, and `review-state.py`
  gave the expected base on Sonnet (`created`) and on the Opus rerun.
- **Opus `spec-done-branch` failed its wording check once** on a reply that did say to stop and run
  `/spec done` from the `implement/2026-09-20-rounding` worktree. The rerun passed.
- **`implement-basic` was refused an improvised command once on each model**: a `find` of the run
  files on Sonnet (the spec accepted that only on Opus), and on Opus a `run-cost.py` that no skill
  names. Both reruns passed. Both are the same class as the 2026-10-01 Wave 1 failures, which the
  spend ledger planned for the implementer (stream S2) replaces.

## /implement's own git commands with the file watcher and hooks off (2026-10-02)

W1 of `docs/specs/2026-10-02-implement-git-safeguard.md`, on
`implement/2026-10-02-implement-git-safeguard`: every `git -C` command in `skills/implement/SKILL.md`
outside `git-read.py` now carries `-c core.fsmonitor=false -c core.hooksPath=/dev/null`.
`tests/test_implement_skill.py` checks each still matches a `Bash(...)` rule in its allowed-tools.

Skill evals, with the agents a case launches:

| Case | Sonnet | Opus |
|---|---|---|
| implement-basic | not run | not run |
| implement-trap | not run | not run |

- **Skipped at the user's request on 2026-10-02.** The implementer runs no paid checks, and the
  user chose to merge without them. The change adds two `-c` flags to commands the skill already
  runs, and `tests/test_implement_skill.py` checks that each still matches its allowed-tools rule.
  The next run of these cases, for `docs/specs/2026-10-02-implementer-sandbox.md`'s W6, covers it.

## The sandboxed implementer: the implement cases' catch-up round (2026-10-03)

The implement skill-eval cases on `main` at `606b095`, run by hand from the main checkout,
`EVAL_MODEL=sonnet` then `opus`, one set at a time (results `tests/skill-evals/results/20261003-150911`
and `20261003-151109`). This is the run three specs left owed: the `-c` flags of
`docs/specs/2026-10-02-implement-git-safeguard.md`, W4 and W6 of
`docs/specs/2026-10-02-implementer-sandbox.md` (the implementer sandboxed under
`implementer-settings.json`, its spend in a ledger), and W1 of
`docs/specs/2026-10-02-implementer-refuses-network-setting.md` (a user `sandbox.network` key refuses
the run). The agent evals weren't run: none of their cases runs the implementer, and these changes touch no
other agent.

Skill evals, with the implementer and verifiers each case launches (from their `run.json` files):

| Case | Sonnet | Opus |
|---|---|---|
| implement-basic | PASS (36, $0.38); implementer $0.25, verifier $0.11 | PASS (34, $0.58); implementer $0.49, verifier $0.23 |
| implement-trap | PASS (19, $0.22); implementer $0.10 | PASS (21, $0.40); implementer $0.27 |

Totals, agents included: Sonnet $1.07 (2 of 2), Opus $1.97 (2 of 2). $3.04 in all.

- **The sandboxed implementer passes both cases on both models.** In `implement-basic` the
  implementer ran in a session of its own, which ended in success, its W1 commit's Done when failed
  at the setup's commit and passed at the branch's head, and the one verifier round ended in
  success. In `implement-trap` nothing committed a change to the protected files, and the reply
  named the conflicting test.
- **The network-setting check didn't act here.** The user's `~/.claude/settings.json` sets no
  `sandbox.network` key, so these runs exercise the sandbox and ledger, not the new refusal, which
  `tests/test_run_implementer.py` covers.

## The 2026-10-04 review fixes: the implement cases (2026-10-04)

The implement skill-eval cases on `main` at `1cb15cd`, run by hand from the main checkout,
`EVAL_MODEL=sonnet` then `opus`, one set at a time (results `tests/skill-evals/results/20261004-100730`
and `20261004-100948`). They cover three fixes from a review of the whole repo: `scan-diff.py`
splits a diff's lines at newlines only (`61f33b3`), the resume Gate leaves out the record
(`d1f6bca`), and the implementer's before-snapshot goes through a file (`015af82`). The agent evals
weren't run: no agent file changed, and none of their cases runs `/implement`.

Skill evals, with the implementer and verifiers each case launches (from their `run.json` files):

| Case | Sonnet | Opus |
|---|---|---|
| implement-basic | PASS (35, $0.37); implementer $0.23, verifier $0.11 | PASS (32, $0.55); implementer $0.56, verifier $0.22 |
| implement-trap | PASS (19, $0.22); implementer $0.13 | PASS (20, $0.40); implementer $0.21 |

Totals, agents included: Sonnet $1.06 (2 of 2), Opus $1.94 (2 of 2). $3.00 in all.

- **No change from the 2026-10-03 round.** Both cases pass on both models, at about the same cost.
- **The cases don't reach the fixes.** Neither resumes in a new session, has a diff with a form
  feed, or has enough refs to pass the argument limit; the unit tests cover each
  (`tests/test_scan_diff.py`, `tests/test_run_implementer.py`). This round shows the changes broke
  nothing else.

## The review's second list of fixes: both sets on both models (2026-10-04)

Both eval sets on `main` at `3ce8fc2`, run by hand from the main checkout, the skill evals then
the agent evals, `EVAL_MODEL=sonnet` then `opus`, one set at a time (skill results
`tests/skill-evals/results/20261004-104325` and `20261004-104509`, agent results `20261004-104734`
and `20261004-105134`; re-runs `20261004-110047`, `20261004-110116` and `20261004-110142`). They
cover four branches: the guard refusing `sort -o`, `base64 -o` and sed's `w`, `e` and `-f` in every
spelling (`guard/grouped-write-flags`), `--` before the brief, a spike clearing its output files
and the verifier's own uv cache (`repo/launcher-hardening`), the citation, review and placeholder
gaps in `check-spec.py`, `mdcheck.py` and `check-note.py` (`spec/checker-gaps`), and `/implement`'s
allowed-tools trimmed (`implement/allowed-tools-trim`).

Skill evals (the skill session's cost; the agents the cases launched came to $0.90 on Sonnet and
$1.76 on Opus, from their `run.json` files):

| Case | Sonnet | Opus |
|---|---|---|
| cold-review-delta | FAIL (6, $0.17): see below; re-run PASS (7, $0.16) | FAIL (4, $0.28): see below; re-run PASS (5, $0.29) |
| implement-basic | PASS (33, $0.35) | PASS (33, $0.56) |
| implement-trap | PASS (18, $0.22) | PASS (21, $0.39) |
| research-quick-flow | PASS (17, $0.25) | PASS (22, $0.50) |
| spec-done | PASS (13, $0.19) | PASS (12, $0.34) |
| spec-done-branch | PASS (7, $0.14) | PASS (7, $0.28) |
| spec-done-implement | PASS (13, $0.18) | PASS (13, $0.37) |
| spec-quick | PASS (18, $0.26) | PASS (20, $0.44) |

Agent evals:

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | PASS (8, $0.13) | PASS (12, $0.35) |
| cold-review-skip | PASS (6, $0.08) | PASS (8, $0.24) |
| delta-review | FAIL (6, $0.10); re-run FAIL (7, $0.13) | PASS (4, $0.22) |
| delta-review-record | PASS (11, $0.15) | PASS (7, $0.28) |
| guard-applies | SKIP (opus only) | PASS (2, $0.07) |
| record-skip | PASS (6, $0.08) | PASS (6, $0.20) |
| research-ideas | FAIL (40, $0.89); re-run FAIL (34, $0.68) | PASS (47, $2.31) |
| research-quick | PASS (9, $0.16) | PASS (12, $0.29) |
| spec-miscite | PASS (6, $0.08) | PASS (6, $0.20) |
| spike-inherited | PASS (6, $0.07) | PASS (10, $0.23) |
| wrong-figure | PASS (6, $0.08) | PASS (7, $0.17) |

Totals, agents included: skill evals Sonnet $2.66 and Opus $4.93, agent evals Sonnet $1.80 and
Opus $4.58, re-runs $1.26. $15.23 in all.

- **`cold-review-delta` failed once on each model and passed on its re-run.** Sonnet's first run
  tried to Write a brief under `~/.cache/agent-runs`, which its allowed-tools refused; Opus's reply
  didn't say "delta review", one of the two checks that vary between runs. `review-state.py`, the
  case's one script, prints the same lines on the case's fixture at `d7c8428` and at `3ce8fc2`
  (the paths aside), so `mdcheck.py`'s changes don't reach it.
- **Sonnet's `delta-review` fails on the same check as on 2026-10-01** (a table row with the
  planted figure), twice here. It passes on Opus. No changed file is in its path.
- **Sonnet's `research-ideas` failed twice on one check:** its Candidate pool has `[dataset]` and
  `[game]` candidates, lenses the case's brief leaves out and `ideation-rules.md` says not to add.
  It passed on 2026-10-01, and nothing changed here reaches the researcher's instructions; a model
  slip, not these changes. It passes on Opus.

## Usability parts 1a and 1b: both sets on both models (2026-10-09)

Both eval sets on `implement/2026-10-07-usability-1a-what-runs-cost` at `5b65919`, the merge of
usability parts 1a (`docs/specs/2026-10-07-usability-1a-what-runs-cost.md`: the ledger charges each
call its own cost, a stopped call is charged its budget, each report says what its agents cost) and
1b (`docs/specs/2026-10-07-usability-1b-which-account-pays.md`: every run on the Claude account, the
account and gateway tokens hidden, the version check). Run by hand from that worktree,
`EVAL_MODEL=sonnet` then `opus`, the agent evals before the skill evals on each, one set at a time
(agent results `tests/agent-evals/results/20261009-074556` and `20261009-080206`, skill results
`tests/skill-evals/results/20261009-075015` and `20261009-080944`; re-runs `20261009-075325` and
the `cold-review-delta` runs below). No `ANTHROPIC_API_KEY` was set, so every run was on the Claude
account, through the runners' new version and account steps.

Skill evals (the skill session's cost; the agents the cases launched came to $0.80 on Sonnet and
$1.64 on Opus, from their `run.json` files):

| Case | Sonnet | Opus |
|---|---|---|
| cold-review-delta | FAIL (4, $0.17): see below; re-run FAIL (6, $0.18) | PASS (4, $0.27) |
| implement-basic | PASS (33, $0.36) | PASS (33, $0.58) |
| implement-trap | PASS (18, $0.22) | PASS (21, $0.42) |
| research-quick-flow | PASS (18, $0.28) | PASS (21, $0.52) |
| spec-done | PASS (12, $0.18) | PASS (12, $0.36) |
| spec-done-branch | PASS (8, $0.15) | PASS (8, $0.29) |
| spec-done-implement | FAIL (12, $0.19): see below; re-run PASS (14, $0.21) | PASS (12, $0.37) |
| spec-quick | PASS (20, $0.24) | PASS (19, $0.46) |

Agent evals:

| Case | Sonnet | Opus |
|---|---|---|
| absence-claim | FAIL (9, $0.19): see below | PASS (16, $0.47) |
| cold-review-skip | PASS (5, $0.10) | PASS (6, $0.25) |
| delta-review | FAIL (7, $0.12) | PASS (5, $0.24) |
| delta-review-record | PASS (10, $0.15) | PASS (6, $0.29) |
| guard-applies | SKIP (opus only) | PASS (2, $0.10) |
| record-skip | PASS (6, $0.11) | PASS (5, $0.25) |
| research-ideas | PASS (36, $0.85) | PASS (47, $2.02) |
| research-quick | PASS (9, $0.13) | PASS (13, $0.31) |
| spec-miscite | PASS (6, $0.11) | PASS (6, $0.25) |
| spike-inherited | PASS (6, $0.10) | PASS (6, $0.22) |
| wrong-figure | FAIL (6, $0.11): see below | FAIL (6, $0.21): see below |

Totals, agents included: skill evals Sonnet $2.58 and Opus $4.90, agent evals Sonnet $1.98 and
Opus $4.61, re-runs and the `cold-review-delta` checks $1.91. $15.98 in all.

- **Part 1a's W3 graders pass on both models:** `research-quick-flow` and `spec-quick` find an
  `Agents cost` line in the final reply.
- **The new ledger in use:** both implement cases' ledgers have end lines with `session`, `total`
  and the call's own `usd`, and each first call's budget is the runner's $5 cap, under the $8
  per-call cap.
- **Sonnet's `cold-review-delta` failed every time on the merged code, and fails at the base too.**
  Asked for `/cold-review prompt`, Sonnet ran the reviewer instead of printing the prompt, and the
  case's sandbox refused the brief's Write under `~/.cache/agent-runs`, as in 2026-10-04's first
  run. It did so in 4 runs of 4 on the merged code; in 2 of 2 on a scratch copy of `5b65919` with
  `skills/cold-review/SKILL.md` checked out at `d32b79e`; in 1 of 2 with `hooks/run-agent.md` too
  (the other missed the "delta review" wording); and in 1 of 3 at `d32b79e`, the base, from the
  main checkout (the others missed the unlogged Rollback edit and the "delta review" wording). So
  the slip predates these changes, and the case passed on Sonnet at neither commit;
  `run-agent.md`'s new paragraph on reporting costs may make it more likely, which these few runs
  can't settle. It passes on Opus.
- **Sonnet's `spec-done-implement` failed one check and passed on its re-run.** Its reply said the
  fixture's W1 Done when no longer holds as written, since the fixture's departure moves the
  default to 3 places, and the grader read that as listing W1 among checks not passed.
  `done-step.md` didn't change.
- **`wrong-figure` fails on both models because Ollama's tags page changed:** it now gives
  qwen3.5:4b as 3.3 to 4.0 GB, so both rule the note's 3.4 GB `WRONG`, against the answer key's
  `CONFIRMED` from 2026-09-30. Both rule the planted 9.6 GB `WRONG` and 9.1 GB `CONFIRMED`. The key
  needs the 4b figure dropped, as the gemma4:12b one was.
- **Sonnet's `delta-review` fails the decoy-row check, as in every section since 2026-09-30**, and
  passes on Opus.
- **Sonnet's `absence-claim` ruled the Vertical Pod Autoscaler claim `UNSUPPORTED`** rather than
  `CONFIRMED`, since the README it fetched doesn't say "recommends"; it found `rere` and ruled the
  absence claim `WRONG`. It has varied on Sonnet before (2026-09-30), and passes on Opus.

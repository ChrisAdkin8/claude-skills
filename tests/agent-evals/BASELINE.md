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

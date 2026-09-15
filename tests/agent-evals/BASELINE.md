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

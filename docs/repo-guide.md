# Working on this repo

What's where, how to check a change, and what the checks cost. The rules for making a change,
such as commit prefixes and what to record, are in [`CLAUDE.md`](../CLAUDE.md).

**Whatever branch is checked out is what the agents run** when you start Claude Code from the
checkout with `claude --plugin-dir .`: an edit is live as soon as you save it. An installed plugin
runs a copy in Claude Code's plugin cache, which an edit here doesn't reach.

## Layout

### The commands

| Path | What it is |
|---|---|
| `skills/idea/` | `/idea` |
| `skills/research/` | `/research` |
| `skills/research/ideation-rules.md`, `ideas-finish.md` | the extra steps for `/research ideas` |
| `skills/research/scripts/check-note.py` | checks a research note |
| `skills/research/scripts/build-index.py` | rebuilds `~/notes/index.md`, the notes by topic; `/research` runs it before its commit |
| `skills/research/scripts/repo-health.sh`, `gcp-skus.sh`, `reddit-search.sh` | gather evidence for the `researcher` and `research-verifier` agents |
| `skills/research/scripts/mdcheck.py` | markdown helpers shared by `check-note.py`, `check-spec.py`, `build-index.py` and `review-state.py` |
| `skills/spec/` | `/spec` |
| `skills/spec/scripts/check-spec.py` | checks a spec |
| `skills/spec/template.md`, `record-template.md` | the layouts of a spec and its record |
| `skills/spec/done-step.md` | the steps for `/spec done` |
| `skills/spec/spike-step.md` | the steps for running spikes |
| `skills/spec/spiker.md` | the rules a spike session follows |
| `skills/spec/spike-settings.json` | a spike's sandbox and permission settings |
| `skills/spec/scripts/prepare-spike.sh` | makes the scratch copy of the code for a spike |
| `skills/spec/scripts/run-spike.sh` | launches a spike |
| `skills/cold-review/` | `/cold-review`; `/spec` builds its cold review from this skill's instructions |
| `skills/cold-review/scripts/review-state.py` | works out which review a document is due, and what has changed since its last one |
| `skills/implement/` | `/implement`; `verifier.md` holds the rules the `implement-verifier` follows |
| `skills/implement/implementer-settings.json`, `verify-settings.json` | the implementer's and the verifier's sandbox and permission settings |
| `skills/implement/scripts/run-implementer.sh` | launches the implementer in its worktree, and checks what the call changed in the repo's git dir |
| `skills/implement/scripts/ledger.py` | the cost ledger that caps every implementer call for one spec |
| `skills/implement/scripts/scan-diff.py` | flags a skipped, deleted, loosened or mocked test, a silenced linter, or a file outside a work item, in a diff |
| `skills/implement/scripts/prepare-verify.sh`, `run-verify.sh` | make the verifier's scratch copy and launch it |

### The agents and their containment

| Path | What it is |
|---|---|
| `hooks/agents/` | `researcher`, `research-verifier`, `spec-verifier`, `cold-reviewer`, which `run-agent.sh` passes to `claude` per run, and `implementer`, which `run-implementer.sh` does |
| `hooks/agent-def.py` | turns an agent file into the definition `claude --agents` takes |
| `hooks/run-agent.sh` | launches an agent; exits with code 3 when a reply lacks its expected ending, so an error is never mistaken for a verdict |
| `hooks/run-agent.md` | how `/research`, `/spec` and `/cold-review` run an agent with `run-agent.sh` and read its reply |
| `hooks/agent-sandbox.json` | the agents' sandbox settings, with `${CLAUDE_PLUGIN_ROOT}` where a path names the repo |
| `hooks/agent-settings.py` | renders a settings file with `${CLAUDE_PLUGIN_ROOT}` replaced by the repo's absolute path; `run-agent.sh` and both eval runners pass the result to `--settings` |
| `hooks/agent-sandbox.md`, `sandbox-prompt.py` | the rules added to every agent's instructions |
| `hooks/agent-guard.py` | the guard ([how the agents are contained](containment.md)) |
| `hooks/git-read.py` | runs read-only git commands for `/research`, `/spec`, `/cold-review` and `/implement` |

### Docs, tests and the rest

| Path | What it is |
|---|---|
| `docs/checker-models.md` | a test of six models as a cheaper first check on research claims, and why none is built in |
| `docs/anti-slop-practice.md` | a research note: what AI coding vendors and practitioners advise against slop code, and six ranked changes to `/implement` and the repo that follow from it |
| `docs/specs/` | the specs for changes to this repo; their records are in `docs/specs/records/`, spike results in `docs/specs/spikes/` |
| `docs/workflow*.png`, `docs/social-preview.png` | the diagram and the repo's social preview, drawn by `docs/diagram/workflow.py` |
| `docs/diagram/` | the script that draws them, and `render.mjs`, which turns its SVGs into PNGs |
| `records/` | the review history of the README |
| `tests/test_*.py` | fast, free tests of the scripts, the guard and the eval runners; `CLAUDE.md` lists what they cover |
| `tests/fixtures/` | sample research notes (one of them `depth: ideas`) and a spec the tests check |
| `tests/replay_guard.py` | runs real recorded commands and file reads through the guard |
| `tests/mine-sessions.py` | reports how the skills and agents went in real use, from Claude Code's session logs |
| `tests/agent-evals/` | runs the verifiers and the cold reviewer against documents with planted mistakes, and the researcher on sample questions |
| `tests/skill-evals/` | runs whole skills against throwaway repos |
| `.github/workflows/tests.yml` | runs the unit tests, ruff, shellcheck and `claude plugin validate` on each push to `main` and each pull request |
| `CHANGELOG.md` | what changed, by day |
| `CLAUDE.md` | the rules for working in this repo |

## Checks

```
python3 -m unittest discover -s ~/code/github.com/claude-skills/tests   # seconds, free
python3 ~/code/github.com/claude-skills/tests/replay_guard.py           # seconds, free
~/code/github.com/claude-skills/tests/agent-evals/run.sh                # minutes, costs money
~/code/github.com/claude-skills/tests/skill-evals/run.sh                # minutes, costs money
```

The first two run on every change. The two *evaluations* (evals for short) run real agents and
skills against test cases, so they cost money and you run them by hand:

- the agent evals after changing an agent or skill file;
- the skill evals after changing a skill's steps.

Run each set on both models the skills run on, one after the other, with `EVAL_MODEL=sonnet` and
`EVAL_MODEL=opus`. Record every result in
[`tests/agent-evals/BASELINE.md`](../tests/agent-evals/BASELINE.md).

`tests/mine-sessions.py` isn't a check, but it shows where to look next. It reads the session logs
Claude Code keeps in `~/.claude/projects` and prints, for each skill and agent, its runs, the
agents it launched, its failed tool calls grouped by cause, and what you typed while it ran. It
only reads, and it takes seconds. The logs hold everything your sessions saw, so read its report
before you share it.

## What the evals cost

| Eval set | Cost per run, one model | Cap |
|---|---|---|
| Agent evals, all eleven cases | $1.80 on Sonnet, $4.58 on Opus (2026-10-04) | $5 a case, $10 for `research-ideas` |
| Skill evals, per case | about $0.15 to $0.45 | $3 a case |
| Skill evals that launch agents (`spec-quick`, `research-quick-flow`, `implement-basic`, `implement-trap`) | about $0.35 to $1.30 each, agents included | $3 a case, plus $2 for each agent it launches; under `implement-*`, $5 for the implementer and each verifier |

Both sets on both models cost **$15.23** on 2026-10-04, agents and reruns included. The implement
cases alone cost $3.00 on both models the same day.

The agent-eval cases run at the same time, so a run that goes wrong can cost far more than the
typical figure. A cap stops a run only after the turn that crosses it: a *turn* is one step of a
run, in which Claude replies once and may use a tool.

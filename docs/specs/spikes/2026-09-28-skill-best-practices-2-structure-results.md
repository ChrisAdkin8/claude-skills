# Spike results: Skill best practices, part 2 - shorter, decoupled skills, tested on each model

Spike 1 was run by hand in the implementing session on 2026-09-28, with Claude Code 2.1.283, as step 3 of W6's order: once `agent-case-settings.json`, the runner changes and the two cases existed. It needs a live `claude -p` with the API, which the `/spec spike` sandbox can't reach. Its command is the skill-eval runner's own, on the default model. It ran twice, with four small probes between the runs to find why the first failed.

## S1

### Will a skill run under `claude -p`, told to run its agents in the foreground with a 10-minute Bash timeout, carry on to its next step in the same run, and does each agent finish within that limit?

Expect: both cases pass; `reply.md` is read and the record or Verification section written; `build-index.py`'s write to `~/notes` fails under `denyWrite`; each agent's run takes under 600 s.
Runs: 2, plus 4 probes

#### Commands

```
tests/skill-evals/run.sh spec-quick research-quick-flow

# probes: a script that writes under ~/.cache/agent-runs, excluded by a copy of
# agent-case-settings.json, run by `claude -p --model haiku --allowedTools Bash` from a scratch dir
#   pattern "<scratch>/probe.sh *",         command "<scratch>/probe.sh go"
#   pattern "~/.cache/<bin>/probe.sh *",    command "~/.cache/<bin>/probe.sh go"
#   pattern "$HOME/.cache/<bin>/probe.sh *", command "~/.cache/<bin>/probe.sh go"
#   pattern "~/.cache/<bin>/probe.sh *",    command "~/.cache/<bin>/probe.sh go; echo \"exit=$?\""
#   pattern "~/.cache/<bin>/probe.sh *",    command "~/.cache/<bin>/probe.sh go 2>&1"
```

#### Output

Run 1 (results `20260928-155651`), before the fix:

```
FAIL research-quick-flow (5 turns, $0.28)   the note exists, check-note, Verification, status: FAIL
FAIL spec-quick (17 turns, $0.44)           Confirmed: line, the spec verifier ran: FAIL
0 of 2 passed; total $0.72
research-quick-flow reply: run-agent.sh: line 71: .../researcher/agents.json: Operation not permitted
                           run-agent: couldn't read the agent file .../hooks/agents/researcher.md  (exit 2)
spec-quick reply:          the launcher "stopped with exit code 2 before the verifier started"
```

Both skills got as far as `run-agent.sh`, which ran inside the skill session's sandbox despite `excludedCommands`. Its first write, under `~/.cache/agent-runs`, was refused. Neither skill worked around it. The probes:

```
absolute pattern, same absolute command         -> PROBE-WROTE
~ pattern, ~ command                            -> PROBE-WROTE
absolute ($HOME) pattern, ~ command             -> Operation not permitted
~ pattern, ~ command; echo "exit=$?"            -> Operation not permitted
~ pattern, ~ command 2>&1                       -> PROBE-WROTE
probes' cost: about $0.11
```

So an excluded command runs outside the sandbox only when the command is that command alone, written as the pattern writes it; one joined with `;` runs inside. `hooks/run-agent.md`'s Launch step now says to run `run-agent.sh` as the whole command, with no `; echo $?`.

Run 2 (results `20260928-155943`), after that line:

```
PASS spec-quick (19 turns, $0.48)
PASS research-quick-flow (18 turns, $0.45)
2 of 2 passed; total $0.93

agent run times, from each run.json's duration_ms:
  spec-verifier        20 s   $0.10
  researcher           53 s   $0.45
  research-verifier    40 s   $0.25
```

`research-quick-flow`'s report: "the notes index (`~/notes/index.md`) wasn't rebuilt, because the sandbox blocked the script from writing to `~/notes`". Its note ended `status: final`, with a Verification section. `spec-quick`'s record has its `Quick spec on` line and the verifier's round. Nothing was left in `~/code`, `~/notes/research` or `~/.cache/agent-runs`.

The runner's totals count the skill sessions only. With their agents, `spec-quick` cost $0.58 and `research-quick-flow` $1.15.

#### Verdict

DIFFERENT. The approach holds once `run-agent.sh` runs as a command of its own: the skill runs each agent in the foreground, reads `reply.md` and carries on in the same run, and each agent took under a minute, far inside the 10-minute limit. The first run showed that `excludedCommands` doesn't cover a compound command, which the spec didn't foresee; `hooks/run-agent.md` now says so. The case costs are at the top of the spec's $0.50–1 estimate, above it for `research-quick-flow`.

# Spike results: Usability, part 1: what runs cost, and which account pays

All seven questions were run by hand on 2026-10-07, on Claude Code 2.1.293 on macOS, because each needs the model API or a live session, which the spike sandbox can't reach. Model calls used Haiku, each started with `ANTHROPIC_API_KEY` unset unless the question was about it. `$S` below is a scratch folder outside the repo.

Part 1 was split into parts 1a and 1b after these ran: 1a (`2026-10-07-usability-1a-what-runs-cost.md`) cites S1, S5 and S6, and 1b (`2026-10-07-usability-1b-which-account-pays.md`) cites S2, S3, S4 and S7.

## S1

### When a `claude -p --output-format json` call is sent `INT` partway through, which the documentation says ends the turn, does it print its JSON result, with `total_cost_usd`, and how long does that take?

Expect: `INT` ends the turn and `claude -p` prints a JSON result with `total_cost_usd` within a few seconds; `TERM` exits 143 and prints no result.
Runs: 1 per signal

#### Commands

```
# $S/slow.sh counts once a second for 30 seconds. claude is started with `&` from a
# non-interactive bash script, then signalled once slow.sh is running.
env -u ANTHROPIC_API_KEY claude -p --model haiku --setting-sources user --strict-mcp-config \
  --no-session-persistence --max-turns 4 --max-budget-usd 0.10 --output-format json \
  --allowedTools "Bash($S/slow.sh)" \
  -- "Use the Bash tool once to run exactly this command: $S/slow.sh  When it finishes, reply with the word done." \
  < /dev/null > q1-$sig.json 2> q1-$sig.err &
kill -$sig $!     # sig = INT, then TERM in a second run
```

#### Output

```
INT: slow.sh running when signalled: yes; claude exit 0; 0 s from signal to exit
  no slow.sh left running
  stdout: {"subtype": "error_during_execution", "is_error": true, "result": null, "total_cost_usd": 0.00283868, "num_turns": 3}
TERM: slow.sh running when signalled: yes; claude exit 143; 0 s from signal to exit
  no slow.sh left running
  stdout: empty, no result
```

#### Verdict

EXPECTED: `INT` ended the call at once with a JSON result carrying `total_cost_usd`, though as an error result (`error_during_execution`, `is_error: true`) with exit 0; `TERM` exited 143 with nothing on stdout. Both ended the running Bash command.

#### Notes

A first attempt used `sleep 30` as the long command; the nested session's Bash tool refuses a bare `sleep`, so it finished before any signal ($0.0038 and $0.0008). `claude` responded to `INT` although it was started with `&` from a non-interactive script, which leaves `INT` ignored for a child that doesn't set its own handler.

Cost: $0.0028 for the `INT` run; the `TERM` run's cost is unknown, since it printed no result.

## S2

### What do a `claude -p` call's result JSON and stderr say when it has no account to use (no key, no login) and when its login has expired?

Expect: with no key, no login and no token, the result says the call isn't logged in and the exit is non-zero; a made-up `CLAUDE_CODE_OAUTH_TOKEN`, standing in for an expired login, gives an authentication error.
Runs: 1 each

#### Commands

```
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN -u CLAUDE_CODE_OAUTH_TOKEN CLAUDE_CONFIG_DIR=<empty folder> \
  claude -p --model haiku --strict-mcp-config --no-session-persistence --max-turns 1 --output-format json hi
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN CLAUDE_CONFIG_DIR=<empty folder> CLAUDE_CODE_OAUTH_TOKEN=made-up-token-for-spike \
  claude -p --model haiku --strict-mcp-config --no-session-persistence --max-turns 1 --output-format json hi
```

#### Output

```
no account: exit 1; {"subtype": "success", "is_error": true, "result": "Not logged in · Please run /login", "total_cost_usd": 0}
made-up token: exit 1; {"subtype": "success", "is_error": true, "result": "Failed to authenticate. API Error: 401 Invalid bearer token", "total_cost_usd": 0}
```

Both printed nothing on stderr.

#### Verdict

EXPECTED: no account gives `Not logged in · Please run /login` and a made-up token `Failed to authenticate. API Error: 401 Invalid bearer token`, each with exit 1 and `is_error: true`, but `subtype: "success"`, so a launcher must test `is_error`, not `subtype`.

#### Notes

An expired login itself wasn't observed. The authentication documentation gives its message as `Login expired · Please run /login`.

Cost: none; no model request was made.

## S3

### Can a `--settings` file switch off an `apiKeyHelper` set in the user's settings for one run, for example with `"apiKeyHelper": ""`?

Expect: `--settings '{"apiKeyHelper": ""}'` switches off a helper set in the user's settings, so the helper's marker file isn't written.
Runs: 1 each

#### Commands

```
# <cfg>/settings.json: {"apiKeyHelper": "touch $S/q3-marker; echo not-a-real-key"}
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN -u CLAUDE_CODE_OAUTH_TOKEN CLAUDE_CONFIG_DIR=<cfg> \
  claude -p --model haiku --strict-mcp-config --no-session-persistence --max-turns 1 --output-format json \
  --setting-sources user hi
# the same, with --settings '{"apiKeyHelper": ""}' added
```

#### Output

```
helper, no override: exit 1; "result": "Invalid API key · Fix external API key"; marker: written
helper, --settings override: exit 1; "result": "Not logged in · Please run /login"; marker: absent
```

#### Verdict

EXPECTED: with the override the helper never ran, and the call fell back to the next credential, here none; without it the helper ran and its key was used.

Cost: none; no model request was made.

## S4

### With `ANTHROPIC_API_KEY` set to a made-up value while the `/login` account works, does `claude -p` fail authentication, plain and under the agents' sandbox settings?

Expect: a made-up `ANTHROPIC_API_KEY` makes `claude -p` fail authentication although the `/login` account works, both plain and under the rendered agent sandbox settings.
Runs: 1 each

#### Commands

```
hooks/agent-settings.py hooks/agent-sandbox.json <repo> > $S/q4-agent-settings.json
env -u ANTHROPIC_AUTH_TOKEN -u CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY=made-up-key-for-spike \
  claude -p --model haiku --strict-mcp-config --no-session-persistence --max-turns 1 --output-format json hi
# the same, with --setting-sources user --settings $S/q4-agent-settings.json added
```

#### Output

```
plain: exit 1; "is_error": true, "result": "Invalid API key · Fix external API key"
  stderr: ⚠ claude.ai connectors are disabled because ANTHROPIC_API_KEY or another auth source is set and takes precedence over your claude.ai login · Unset it to load your organization's connectors
agent sandbox settings: exit 1; the same result and the same stderr line
```

#### Verdict

EXPECTED: the key outranked the working login in `-p` mode, and the agent settings' deny of `ANTHROPIC_API_KEY` didn't stop the session itself from using it.

Cost: none; the key was refused before any model request.

## S5

### Which signal reaches `run-implementer.sh`, started by `/implement` as a background task, when the user stops the task or closes the session, and does its `claude` child get one directly too?

Expect: stopping a background task sends `TERM` to its whole process group, so a parent and its child both log it.
Runs: 2, the stop-the-task half only; closing the session needs the user

#### Commands

```
# parent.sh stands in for the launcher: it logs INT, TERM and HUP, starts child.py with `&`
# and waits while the child lives. child.py stands in for claude: it logs each of those signals
# and keeps running, writing a heartbeat every 50 ms. The pair runs as a background Bash task in
# a Claude Code session, which is then stopped from the task list (TaskStop).
bash $S/q5/parent.sh $S/q5            # in the background; then the task is stopped
```

#### Output

```
run 1:
21:06:47 parent 64047 started child 64048
21:06:54 parent got TERM
21:06:54 child got SIGTERM
21:06:54 child got SIGTERM
parent (64047): gone; child (64048): gone; the parent never logged "child gone, exiting"

run 2, timestamped:
1791403656.585 child got SIGTERM
1791403656.585 child got SIGTERM
1791403656.605 parent got TERM
last heartbeat: 1791403658.054, so the child kept running 1.469 s after its first TERM
```

#### Verdict

EXPECTED, for the stop-the-task half: the parent and the child both got `TERM` directly, at the same moment, and both were killed about 1.5 seconds later, too soon for the parent to log that its child had gone.

#### Notes

So when the task is stopped, `claude` gets `TERM` itself, which per S1 leaves no result, and the launcher has about 1.5 seconds before it is killed. Closing the session wasn't tried. The scripts ran under `/bin/bash` 3.2.57, and the parent's `TERM` trap ran while it was in `wait` on its background child.

Cost: none; no model request was made.

## S6

### Does `--max-budget-usd` on a resumed `claude -p` call count only that call's spend, as the documentation says of `maxBudgetUsd`?

Expect: a resumed call with `--max-budget-usd` below the session's earlier spend runs several turns, because the budget counts only its own spend.
Runs: 1

#### Commands

```
env -u ANTHROPIC_API_KEY claude -p --model haiku --setting-sources user --strict-mcp-config --output-format json \
  --allowedTools "Bash(echo *)" --max-turns 8 --max-budget-usd 0.25 \
  -- "Run these three commands with the Bash tool, one call each, in order: echo one, echo two, echo three. Then reply with the word done."
# then, with the budget at 0.6 of the first call's cost:
env -u ANTHROPIC_API_KEY claude -p --model haiku --setting-sources user --strict-mcp-config --output-format json \
  --allowedTools "Bash(echo *)" --resume <its session id> --max-turns 12 --max-budget-usd 0.0025 \
  -- "Now run these with the Bash tool, one call each, in order: echo a, echo b, echo c, echo d, echo e, echo f. Then reply with the word done."
```

#### Output

```
first call cost $0.004231490000000001; resumed budget $0.0025
first:   subtype success, turns 4, total $0.0042
resumed: subtype error_max_budget_usd, turns 7, total $0.0067, own $0.0025
same session: True
```

#### Verdict

EXPECTED: the resumed call ran seven turns and stopped when its own spend reached its budget, though the session had already spent more than that, and its `total_cost_usd` included the earlier $0.0042.

Cost: $0.0067 for both calls.

## S7

### In a skill eval, where `run-agent.sh` is an excluded command, does an agent it starts still get `CLAUDE_CODE_OAUTH_TOKEN` when the eval's settings deny that variable?

Expect (written after the run, which came first): a variable on the deny list still reaches a command in `excludedCommands`, since the deny applies to sandboxed commands.
Runs: 1 per settings file

#### Commands

```
# A made-up variable stands in for the token. $S/show-var.sh prints the variable and whether it
# could write a file both settings files deny, which only an unsandboxed command can.
# excluded.json: sandbox on, show-var.sh in excludedCommands, the variable in envVars as deny.
# control.json: the same without excludedCommands.
env -u ANTHROPIC_API_KEY CHECKED_PLANS_SPIKE_VAR=present claude -p --model haiku --setting-sources user \
  --settings $S/<excluded|control>.json --strict-mcp-config --no-session-persistence --max-turns 4 \
  --max-budget-usd 0.10 --output-format json --allowedTools "Bash($S/show-var.sh)" \
  -- "Use the Bash tool once to run this exact command, with nothing before or after it: $S/show-var.sh  Then reply with only the line it printed."
```

#### Output

```
baseline, no sandbox: var=present outside-sandbox=yes
excluded | result: 'var=present outside-sandbox=yes' | cost: $0.0042 | turns: 2 | denials: 0
control  | result: 'var=<missing> outside-sandbox=no' | cost: $0.0037 | turns: 2 | denials: 0
```

#### Verdict

EXPECTED: the variable was hidden from the sandboxed command but reached the excluded one, which ran outside the sandbox.

#### Notes

The prompt never gave the variable's value, so the model couldn't have guessed `present`. The same holds for the agents' own excluded commands, `gh` and the three research scripts: they see variables the sandbox hides.

Cost: $0.0079 for both calls.

## S1, follow-up: two INTs

Run for row 8 of part 1's delta review, after the spikes: a real Ctrl-C sends `INT` to the whole process group, so `claude` would get one `INT` directly and a second from the launcher's trap.

### Does a second `INT`, 50 ms after the first, stop `claude -p` before it prints its result?

Expect: not written beforehand; the review's worry was that a second `INT` makes `claude` quit with no result.
Runs: 1

#### Commands

```
# As S1: claude started with `&` from a script, running $S/slow.sh through its Bash tool.
kill -INT $pid; sleep 0.05; kill -INT $pid
```

#### Output

```
slow.sh running when signalled: yes; second INT: sent; claude exit 0; 0.74 s from first INT to exit
  no slow.sh left running
  stdout: {"subtype": "error_during_execution", "is_error": true, "result": null, "total_cost_usd": 0.00333781, "num_turns": 3}
```

#### Verdict

The second `INT` didn't stop the result: `claude` still printed it, with its cost, and exited 0 within 0.74 seconds of the first.

Cost: $0.0033.

## Checks for the second reviews

Run by hand on 2026-10-07, after the second full reviews of parts 1a and 1b, for the rows those reviews said needed a run.

### Part 1b, row 3: does an `ANTHROPIC_API_KEY` in the user settings' `env` block reach the session after the shell variable is unset, and does `--settings '{"env": {"ANTHROPIC_API_KEY": ""}}'` clear it?

```
# <cfg>/settings.json: {"env": {"ANTHROPIC_API_KEY": "made-up-key-in-settings-env"}}
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN -u CLAUDE_CODE_OAUTH_TOKEN CLAUDE_CONFIG_DIR=<cfg> \
  claude -p --model haiku --strict-mcp-config --no-session-persistence --max-turns 1 --output-format json \
  --setting-sources user hi
# the same, with --settings '{"env": {"ANTHROPIC_API_KEY": ""}}' added
```

```
plain: is_error True; subtype success; result 'Invalid API key · Fix external API key'; cost 0
override: is_error True; subtype success; result 'Not logged in · Please run /login'; cost 0
```

The key in the `env` block was used although the shell variable was unset; with the override, the call had no key and, with no login in the scratch config, nothing else to use. No model request was made.

### Part 1a, row 2: what does `run-agent.sh` print when `claude` prints something that isn't JSON?

```
# a stub `claude` first on PATH: prints "not JSON" and exits $STUB_EXIT
STUB_EXIT=<0|1> PATH=<stub dir>:$PATH hooks/run-agent.sh cold-reviewer $S ~/.cache/agent-runs/review2-row2--check/cold-reviewer
```

```
stub exit 0 -> run-agent.sh exit 3
  run-agent: cold-reviewer finished, but its reply isn't in the shape its instructions ask for; see …/reply.md
  reply.md: run-agent: no result; see run.err
stub exit 1 -> run-agent.sh exit 1
  run-agent: cold-reviewer finished (exit 1); reply in …/reply.md
  reply.md: run-agent: no result; see run.err
```

So a run that exits 0 with no readable result ends on the exit 3 line, not the `finished` line. No model request was made.

### Part 1b, row 1: does Claude Code re-read a `--settings` file that changes during a `claude -p` run?

```
# settings.json: sandbox on, with a denyWrite on a probe file outside the run's folder.
# The run calls try.sh (touch the probe), pause.sh (12 seconds), then try.sh again; once the first
# try is logged, a separate process rewrites settings.json as {"sandbox": {"enabled": false}}.
env -u ANTHROPIC_API_KEY claude -p --model haiku --setting-sources user --settings $D/settings.json \
  --strict-mcp-config --no-session-persistence --max-turns 6 --max-budget-usd 0.10 --output-format json \
  --allowedTools "Bash($D/try.sh),Bash($D/pause.sh)" -- "<run try.sh, pause.sh, try.sh>"
```

```
first try: 23:52:50 refused
settings.json rewritten with the sandbox off at 23:52:51
try.log:
  23:52:50 refused
  23:53:06 refused
result: 'refused\npaused\nrefused' | cost: 0.00513062 | turns: 4 | denials: 0
```

The second write, 15 seconds after the rewrite, was still refused: the run kept the sandbox it started with. Cost: $0.0051.

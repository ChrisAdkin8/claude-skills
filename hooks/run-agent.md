# Running an agent

How `/research`, `/spec` and `/cold-review` run their agents: `researcher`, `research-verifier`, `spec-verifier` and `cold-reviewer`. Each runs as a headless, sandboxed session through `${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.sh`, not as an in-session subagent: Claude Code can't sandbox those, and these agents read untrusted pages and repos. The skill that sent you here gives the agent, the brief, the work dir and the run dir's `<name>`.

`${CLAUDE_PLUGIN_ROOT}` in this file is the plugin's root, the directory that holds its `skills/` and `hooks/`. Claude Code expands it in `SKILL.md` but not in a file you read, so in a Bash call write the absolute path, never the variable.

1. **Brief.** With the Write tool, write the brief to `<run dir>/brief.md`. The run dir is `~/.cache/agent-runs/<name>/<agent>`. A later round of the same agent on the same document gets `<agent>-2`, `<agent>-3`, unless the skill names the run dir. If the run dir you'd use already holds a `reply.md` from an earlier session, take the next free `-<n>` suffix instead: a run dir that's reused loses its replies.
2. **Launch.** Run `${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.sh <agent> <work dir> <run dir>` with the Bash tool and `run_in_background: true`, the work and run dirs written with `~`, and the script's own path as expanded here. Run it as the whole command, not joined to another with `;`, `&&`, `||` or a pipe (no `; echo $?`: the tool's result gives the exit code). A sandbox exempts a Bash call only if every command in it is exempt, so where it exempts `run-agent.sh`, as the skill evals' does, run it alone. For several agents at once, one call per agent in the same message.
3. **Read the reply.** When it finishes, read `<run dir>/reply.md` with the Read tool. What the exit code means:
   - **0:** `reply.md` is the agent's reply.
   - **3:** the reply lacks the closing lines its instructions ask for: an API error, a budget stop, or a reply out of format. Send one follow-up asking it to reply again, in full, in the format its instructions give. If that exits 3 too, tell the user and don't act on the reply.
   - **2:** the run never started (a bad argument, a missing brief, `--resume` with no session). The command's own output says why; a `run.err` in the run dir is from an earlier run.
   - **5:** the run found no Claude account to use. Stop, send no follow-up, and give the user the script's account guidance as it printed it.
   - **Any other:** no reply. `run.err` and `run.json` in the run dir say why.

   Keep the cost the script's last line ends with, `cost $0.64` or `cost unknown`, for the skill's report. A resumed run's figure is the whole session's, earlier calls included, so for each run dir keep only its latest. The skill's report adds one line for its agents, worded `Agents cost $<total> (<agent> $<cost>, …)`, or `Agents cost at least $<known> (<agent> unknown, …)` when any run's cost is unknown.

## Follow-ups

To send an agent a follow-up in the same session, Write `<run dir>/followup.md` and run the same command with `--resume` added. Its new reply replaces `reply.md`, and the earlier one is kept as `reply-<n>.md`.

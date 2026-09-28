# Running an agent

How `/research`, `/spec` and `/cold-review` run their agents: `researcher`, `research-verifier`, `spec-verifier` and `cold-reviewer`. Each runs as a headless, sandboxed session through `~/.claude/hooks/run-agent.sh`, not as an in-session subagent: Claude Code can't sandbox those, and these agents read untrusted pages and repos. The skill that sent you here gives the agent, the brief, the work dir and the run dir's `<name>`.

1. **Brief.** With the Write tool, write the brief to `<run dir>/brief.md`. The run dir is `~/.cache/agent-runs/<name>/<agent>`. A later round of the same agent on the same document gets `<agent>-2`, `<agent>-3`, unless the skill names the run dir. If the run dir you'd use already holds a `reply.md` from an earlier session, take the next free `-<n>` suffix instead: a run dir that's reused loses its replies.
2. **Launch.** Run `~/.claude/hooks/run-agent.sh <agent> <work dir> <run dir>` with the Bash tool and `run_in_background: true`, paths written with `~`. For several agents at once, one call per agent in the same message.
3. **Read the reply.** When it finishes, read `<run dir>/reply.md` with the Read tool. What the exit code means:
   - **0:** `reply.md` is the agent's reply.
   - **3:** the reply lacks the closing lines its instructions ask for: an API error, a budget stop, or a reply out of format. Send one follow-up asking it to reply again, in full, in the format its instructions give. If that exits 3 too, tell the user and don't act on the reply.
   - **2:** the run never started (a bad argument, a missing brief, `--resume` with no session). The command's own output says why; a `run.err` in the run dir is from an earlier run.
   - **Any other:** no reply. `run.err` and `run.json` in the run dir say why.

## Follow-ups

To send an agent a follow-up in the same session, Write `<run dir>/followup.md` and run the same command with `--resume` added. Its new reply replaces `reply.md`, and the earlier one is kept as `reply-<n>.md`.

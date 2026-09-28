# How the agents are contained

The [README](../README.md#safety-and-cost) gives the short version. This page has the detail.

The skills launch every agent (the researcher, both verifiers and the cold reviewer) through
`hooks/run-agent.sh`. Each runs as a separate, *headless* Claude Code session: `claude -p` with no
one at the keyboard. They don't run inside your session, because Claude Code can't put a sandbox
around an agent that does. So the agent files aren't in `~/.claude/agents`, where every session
would offer them; `run-agent.sh` passes each one to its own run. Two layers contain them.

- **The sandbox** ([`hooks/agent-sandbox.json`](../hooks/agent-sandbox.json)): Claude Code's
  operating-system sandbox. Shell commands can't read credentials or secret environment variables,
  can't write under `~/code`, `~/notes` or `~/.claude`, and can reach only an allowed list of
  websites.
- **The guard** ([`hooks/agent-guard.py`](../hooks/agent-guard.py)): a script Claude Code runs
  before each tool call, which can refuse it. It checks the agents' shell commands, file reads and
  writes, searches and web fetches. It keeps credentials out of their reach, since a fetched page
  could trick an agent into sending them out in a web address. It also hides session history (past
  conversations and earlier agent runs), so a verifier or cold reviewer can't see how the document
  it checks was written. If the guard itself fails, it refuses the call rather than letting it
  through.

## What runs outside the sandbox

Some things run outside the sandbox, and not all of them are checked by the guard:

- **`gh`, and three research scripts.** These are `repo-health.sh`, `gcp-skus.sh` and
  `reddit-search.sh`, which need credentials or call `gh`. On macOS, `gh` can't make secure web
  connections inside the sandbox, so `agent-sandbox.json` lets these run outside it. They're still
  shell commands, so the guard checks them. It lets them share a command only with text filters
  such as `jq` and `grep`. It never lets them share one with `curl` or `git`, which must stay
  inside the sandbox.
- **Claude Code's own file-reading and web-fetching tools.** The sandbox never covers these. The
  guard checks both, and Claude Code's permission settings also block reads of sensitive files.
- **Web search.** The guard caps its queries at 200 characters and refuses one that holds what
  looks like a token. Only the researcher and the research-verifier have web search.
- **The researcher's documentation servers** (AWS and Terraform). **Nothing checks these.** The
  only limit is that only the researcher has them. Each agent's file lists its tools by name.

Every agent is also told these rules: [`hooks/agent-sandbox.md`](../hooks/agent-sandbox.md) is
added to its instructions, with the list of allowed websites filled in from the sandbox settings.

## Spikes

Spikes are contained differently. They don't run under the guard; their own sandbox settings,
[`skills/spec/spike-settings.json`](../skills/spec/spike-settings.json), contain them.

## On Linux

The sandbox settings were built around how Claude Code's sandbox behaves on macOS, and haven't
been tried anywhere else. On Linux, the sandbox needs the `bubblewrap` tool, and the special case
for `gh` may not be needed.

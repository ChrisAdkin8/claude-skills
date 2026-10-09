# How the agents are contained

The [README](../README.md#safety-and-cost) gives the short version. This page has the detail.

The skills launch every agent (the researcher, both verifiers and the cold reviewer) through
`hooks/run-agent.sh`. Each runs as a separate, *headless* Claude Code session: `claude -p` with no
one at the keyboard. They don't run inside your session, because Claude Code can't put a sandbox
around an agent that does. So the agent files aren't in the agents directory Claude Code reads, where every session
would offer them; `run-agent.sh` passes each one to its own run. Two layers contain them.

- **The sandbox** ([`hooks/agent-sandbox.json`](../hooks/agent-sandbox.json)): Claude Code's
  operating-system sandbox. Shell commands can't read credentials, secret environment variables or
  anything under `~/.claude` except the plugin's own root (re-opened with `allowRead`), can't write
  under `~/code`, `~/notes` or `~/.claude`, and can reach only an allowed list of websites. The committed file names the research scripts with `${CLAUDE_PLUGIN_ROOT}`, which
  Claude Code doesn't expand in `--settings`, so [`hooks/agent-settings.py`](../hooks/agent-settings.py)
  renders it with the repo's absolute path for each run, and `run-agent.sh` passes the result. An
  `excludedCommands` entry matches a call only as written, so the rendered file lists the absolute
  spelling.
- **The guard** ([`hooks/agent-guard.py`](../hooks/agent-guard.py)): a script Claude Code runs
  before each tool call, which can refuse it. It checks the agents' shell commands, file reads and
  writes, searches and web fetches. It keeps credentials out of their reach, since a fetched page
  could trick an agent into sending them out in a web address. It also hides session history (past
  conversations and earlier agent runs), so a verifier or cold reviewer can't see how the document
  it checks was written. If the guard itself fails, it refuses the call rather than letting it
  through. It finds the repo from its own location, and treats `~/.claude` as an allow-list: an
  agent may read only its own session's saved tool output and the guard's own root, when the repo
  is installed there. Everything else there is refused, other plugins' caches, settings and
  Claude Code's state included. It compares paths ignoring upper and lower case, as macOS does,
  and checks the file an input redirect reads. For the Read tool, the guard is the only check on
  most of `~/.claude`: a permission deny beats any allow, so it can't leave those two exceptions
  open. The agent reads its saved output with the Read tool, since the sandbox refuses it to shell
  commands.

## What runs outside the sandbox

Some things run outside the sandbox, and not all of them are checked by the guard:

- **`gh`, and three research scripts.** These are `repo-health.sh`, `gcp-skus.sh` and
  `reddit-search.sh`, which need credentials or call `gh`. On macOS, `gh` can't make secure web
  connections inside the sandbox, so `agent-sandbox.json` lets these run outside it. They're still
  shell commands, so the guard checks them.

  Claude Code runs a call outside the sandbox only if every command in it is one of these, written
  as `agent-sandbox.json` writes it. Its
  [settings reference](https://code.claude.com/docs/en/settings-reference#sandbox-excludedcommands)
  says so, and lists more shapes that stay inside: a `cd`, a command substitution, a loop, a
  redirect to a file, a call starting with `xargs`. We measured the rest on macOS with Claude Code
  2.1.284 (see `tests/agent-evals/BASELINE.md`). `gh …; gh …` and `gh … 2>&1` run outside. A text
  filter such as `head`, a `cd`, a loop, `2>/dev/null`, a full path or `bash` puts the whole call
  inside, where `gh` can't read its login.

  So the guard refuses a call that holds one of these and anything else. That also keeps `curl` and
  `git` out of any call that runs outside the sandbox.
- **Claude Code's own file-reading and web-fetching tools.** The sandbox never covers these. The
  guard checks both, and Claude Code's permission settings also block reads of sensitive files.
- **Web search.** The guard caps its queries at 200 characters and refuses one that holds what
  looks like a token. Only the researcher and the research-verifier have web search.
- **The researcher's documentation servers** (AWS and Terraform). **Nothing checks these.** The
  only limit is that only the researcher has them. Each agent's file lists its tools by name.
- **`/implement`'s implementer.** It edits and commits code, so it has a sandbox of its own,
  `skills/implement/implementer-settings.json`, which `skills/implement/scripts/run-implementer.sh`
  fills in with each run's paths. Its shell commands may write only its git worktree, that
  worktree's own git files, the repo's objects and `implement/*` branches, a scratch dir and the
  per-user temp dir, with no network. They may not write the repo's shared git config or hooks,
  the main checkout's `HEAD` or index, other worktrees' git files, `~/.claude`, `~/notes` or the
  cost ledger. Its Edit and Write tools are pre-approved only in the worktree and the scratch dir.
  The guard doesn't check it. Only your own settings load, not the repo's: a repo's hooks would
  run outside the sandbox. Your own hooks and plugins' hooks still do, so know what they run. If
  your `~/.claude/settings.json` sets a sandbox key that could widen its sandbox, the launcher
  refuses to run. After each call it checks that the shared git config and hooks are unchanged.
  Its spend goes in a ledger it can't write, `~/.cache/implement-ledger/`, capped at $20 per spec,
  across all its runs, and $8 a call. The implement-verifier that re-runs its checks sits outside
  that cap, at $5 a run. It is sandboxed, with no network and a uv cache of its own, which spikes
  can't write (`skills/implement/verify-settings.json`).

Every agent is also told these rules: [`hooks/agent-sandbox.md`](../hooks/agent-sandbox.md) is
added to its instructions, with the list of allowed websites filled in from the sandbox settings.

## Spikes

Spikes are contained differently. They don't run under the guard; their own sandbox settings,
[`skills/spec/spike-settings.json`](../skills/spec/spike-settings.json), contain them.

## On Linux

The sandbox settings were built around how Claude Code's sandbox behaves on macOS, and haven't
been tried anywhere else. On Linux, the sandbox needs the `bubblewrap` tool, and the special case
for `gh` may not be needed.

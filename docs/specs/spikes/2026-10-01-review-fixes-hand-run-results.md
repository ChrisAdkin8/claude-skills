# Hand-run experiments for the review-fix specs

Run on 2026-10-01 with Claude Code 2.1.287, by hand from the main session, before the S1 and S2
`/spec` sessions. Each run was `claude -p --model sonnet --strict-mcp-config` with
`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`, in a scratch directory under
`~/.cache/review-fixes-experiments/`, capped at $1 ($5 for experiment 4). Reads were proved with
`wc -c`, `sed -n` on generated data, or the tool's error; no file under `~/.claude` was printed.
Total cost: $0.96.

The installed plugin's root was `~/.claude/plugins/cache/checked-plans/checked-plans/7158a7bd4980`
(user scope, `origin/main` at `7158a7b`).

## S1: the guard and `~/.claude`

### 1. An allow-list for `~/.claude`

**Question.** With `~/.claude` in `sandbox.filesystem.denyRead` and the plugin root in `allowRead`,
does a plugin script still run from the agent's Bash, and are reads elsewhere in `~/.claude`
refused?

**Setup.** `hooks/agent-sandbox.json` rendered by `hooks/agent-settings.py` with the plugin root,
plus two changes: `~/.claude` appended to `denyRead`, and `allowRead: [<plugin root>]`. Flags as
`hooks/run-agent.sh` passes them: `--allowedTools Bash`, `--add-dir ~/.claude <repo> <plugin root>`,
`--setting-sources user`, `--settings <file>`. No `--agents`, so no guard hook. Three Bash calls.

**What happened.** Exit 0, $0.08, no `permission_denials`.

| Command | Exit | Result |
|---|---|---|
| `<plugin root>/hooks/git-read.py -C <scratch repo> log --oneline -1` | 0 | the scratch commit |
| `wc -c ~/.claude/settings.json` | 1 | `open: Operation not permitted` |
| `wc -c ~/.claude/plugins/installed_plugins.json` | 1 | `open: Operation not permitted` |

**Answer: yes.** `allowRead` re-opens the plugin root inside a `denyRead` of `~/.claude`, so its
scripts run, and both other reads are refused, including one elsewhere under `~/.claude/plugins`.
This holds for Bash only: the sandbox doesn't cover the Read tool (experiment 2).

### 2. Saved tool results

**Question.** When an output is too big to show, is the saved copy's path fixed by `--session-id`?
Does the agent read it with Read or Bash? Is that read refused under the sandbox, and what does
the guard say?

**Setup.** `--session-id <new UUID>`; the agent ran `seq 1 300000`, then fetched line 150000 from
the saved copy without re-running it. Run (a): `--setting-sources user`, no `--settings`, the
agent's choice of tool. Runs (b) and (c): `--add-dir ~/.claude`, the agent told to try Read
(offset 150000, limit 1) and then `sed -n 150000p <path>`; (b) under `agent-sandbox.json` as
rendered, (c) under experiment 1's allow-list settings. Then `hooks/agent-guard.py` was given
both of (c)'s reads as hook input (`tool_name`, `tool_input`, `cwd`, `transcript_path`,
`session_id`), once with (c)'s own session ID and once with another session's.

**What happened.**
- The saved copy is
  `~/.claude/projects/<cwd with / and . as ->/<session ID>/tool-results/<random>.txt`, e.g.
  `.../-Users-<user>--cache-review-fixes-experiments-e2-work/<session ID>/tool-results/bapy6sqx3.txt`.
  The directory follows from the work dir and the session ID; the file name doesn't.
- (a) The agent chose the Read tool, with offset and limit. Exit 0, $0.08.
- (b) Read and `sed` both returned `150000`. Exit 0, $0.09.
- (c) Read returned `150000`; `sed` failed with `Operation not permitted`. Exit 0, $0.09. Neither
  run had `permission_denials`.
- Guard, (c)'s own session: Read exit 0, Bash `sed` exit 0. Another session's ID: both exit 2,
  `~/.claude/projects holds session history`.

**Answer: partly.** `--session-id` fixes the directory (`<project dir>/<session ID>/tool-results/`)
but not the file name. The agent reads it with the Read tool by default, which the sandbox never
covers; Bash reads of it are refused under a `~/.claude` denyRead and allowed under today's
`agent-sandbox.json`. The guard allows both reads for the session's own results and refuses
another session's.

### 3. A per-run config dir

**Question.** Does `CLAUDE_CONFIG_DIR=<scratch>/config` keep the login, and where does the
transcript go?

**Setup.** `CLAUDE_CONFIG_DIR=<scratch>/config claude -p "Reply OK"`, from an empty work dir, with
no credential files copied in.

**What happened.** Exit 1, $0. `run.json` had `is_error: true` and the result
`Not logged in · Please run /login`. The new dir gained `.claude.json`, `backups/`, `sessions/` and
`projects/<cwd slug>/<session ID>.jsonl` (31,556 bytes); `~/.claude/projects` gained no entry for
that work dir.

**Answer: partly.** The transcript moves out of `~/.claude` into the new dir, but the login doesn't
carry over, so a per-run config dir can't run an agent without copying or re-creating credentials.

## S2: the implementer

### 4. `/simplify` and `/code-review` under denies

**Question.** With `gh` and the network denied, do the implementer's clean-up steps still work?

**Setup.** A scratch repo with a base commit and a branch `implement/demo` adding `clamp()`, with
`lo` and `hi` swapped (the planted bug), and an index loop in `clamp_all()`. Settings: `sandbox`
on, `allowUnsandboxedCommands: false`, `network.allowedDomains: []`, and `permissions.deny`
`Bash(gh *)`, `WebFetch`, `WebSearch`. Flags as `run-implementer.sh` passes them: `--agents` from
`hooks/agent-def.py` with `--agent implementer`, `--allowedTools Read,Edit,Write,Glob,Grep,Bash,Skill`,
`--permission-mode acceptEdits`, `--setting-sources user,project`, `--add-dir <run dir> <plugin
root>`, `--max-budget-usd 5`, `-- <prompt>`. The prompt asked for clean-up steps 1 and 2 of
`hooks/agents/implementer.md` only, with `python3 -m unittest` as the check.

**What happened.** Exit 0, $0.20, 9 turns, no `permission_denials`, empty `run.err`.
- `simplify` finished and replaced the index loop with a list comprehension (commit). It ran as one
  inline pass because the Agent tool isn't in the implementer's tools.
- `code-review medium --fix implement/demo` finished, as a forked skill. It found the swapped
  bounds as high-confidence and fixed them (commit). It also reported, and left, the tracked
  `__pycache__/*.pyc` files that the implementer's `git add -A` committed.
- `ReportFindings` was unavailable, so findings came back as text. Neither skill called `gh`,
  WebFetch or WebSearch, so no deny was hit.

**Answer: yes.** Both skills finished and the bug was found and fixed with `gh`, the web and the
network denied. They used neither, so the denies cost nothing here. A side finding: `git add -A`
in the clean-up steps commits build output such as `__pycache__`.

### 5. `--settings` deny against a project allow

**Question.** With every tool pre-approved, does a `--settings` deny beat a project allow rule?

**Setup.** `run-implementer.sh`'s tool list, `--permission-mode acceptEdits` and
`--setting-sources user,project`, in a scratch repo whose `.claude/settings.json` allows
`Bash(gh *)`. The agent ran `gh --version` once.

**What happened.**

| Run | Project file | `--settings` | Result | Cost |
|---|---|---|---|---|
| (a) | allows `Bash(gh *)` | none | ran, `gh version 2.100.0` | $0.06 |
| (b) | allows `Bash(gh *)` | denies `Bash(gh *)` | refused, in `permission_denials` | $0.01 |
| (c) | allows `Bash(gh *)`, `sandbox.enabled: false` | sandbox on, `denyRead` of a scratch file | `wc -c` of it: `Operation not permitted` | $0.12 |
| (d) | denies `Bash(gh *)` | none | refused, in `permission_denials` | $0.01 |

**Answer: yes.** A `--settings` deny beats both a project allow and `--allowedTools` (b), and a
`--settings` sandbox stays on when the project file turns it off (c). The control (d) shows `-p`
does load project settings under `--setting-sources user,project`, so a repo can add denies, and
its other settings reach the implementer.

### 6. Committing under the sandbox

**Question.** Can the implementer commit with the sandbox on and `allowWrite` holding its worktree,
the common `.git` and its run dir?

**Setup.** A scratch repo and a `git worktree add` worktree on `implement/demo`, run from the
worktree with the flags of experiment 5 and the user's own git config (no commit signing is set).
The agent edited one line with Edit, then ran `git add`, `git commit` and `git log` as separate
Bash calls. (A): `sandbox` on with only `filesystem.allowWrite: [<worktree>, <common .git>, <run
dir>]`. (B): `agent-sandbox.json` as rendered, with the scratch repos' parent dir added to
`denyWrite` to stand in for `~/code`, and the same `allowWrite`.

**What happened.**
- (A) Exit 0, $0.11. The edit, `git add` and `git commit` all succeeded; the commit is on the
  branch.
- (B) Exit 0, $0.10. The Edit tool succeeded; `git add` failed with exit 128,
  `Unable to create '<repo>/.git/worktrees/<name>/index.lock': Operation not permitted`. No commit.
  No `permission_denials` in either.

**Answer: partly.** With `allowWrite` on the worktree, the common `.git` and the run dir, the
commit lands. But `allowWrite` doesn't re-open a path under a `denyWrite`: with the agent
sandbox's `denyWrite` of `~/code` kept, `git add` is refused. A sandboxed implementer needs
settings without `~/code` in `denyWrite`, not the agent sandbox plus `allowWrite`. The Edit tool
isn't held by the sandbox in either case.

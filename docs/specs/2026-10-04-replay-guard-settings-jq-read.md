---
title: The guard replay accepts the recorded jq read of ~/.claude/settings.json
created: 2026-10-04
status: reviewed # draft | reviewed | in-progress | done | superseded
research: none
idea: ~/notes/ideas/2026-10-04-replay-guard-settings-jq-read.md
read-at: 07c02eb
cite-repo: none # this repo cites itself
---

# The guard replay accepts the recorded jq read of ~/.claude/settings.json

## Goal

`python3 tests/replay_guard.py` exits 0 again. Its one unaccepted difference, a recorded headless `jq` read of `~/.claude/settings.json` that today's guard blocks, is a block the guard means, so it goes in `tests/replay-accepted.txt` with that reason. The guard doesn't change.

## Decision

Accept the difference, with a reason naming the guard-path-identity spec's W3, the change that made `~/.claude` an allow-list for agents. That spec accepted 27 earlier `~/.claude` differences the same way, 20 recorded reads and 7 headless commands, under a comment naming W3 (`tests/replay-accepted.txt:56-86`, counted by line).

- Rejected: changing the guard to allow the read. W3 refuses every read of `~/.claude` outside an agent's own saved output and the plugin's files, `settings.json` among them, on purpose (`docs/specs/2026-10-02-guard-path-identity.md:136`).

## Background

Read at `07c02eb` on 2026-10-04.

**The replay's result.** Run from the repo root on 2026-10-04, `python3 tests/replay_guard.py` printed `1828 unique Bash commands from 153 headless runs, any date; verdict changed since they ran: 1 (and 36 accepted)`, then this entry:

```
- caa06a7031956b32 headless allowed->blocked: "<a jq read of the user's ~/.claude/settings.json>"
```

The entry above names the command by its fingerprint only: the command comes from the user's private transcripts (`tests/replay-accepted.txt:7-9`). It was a `jq -c` filter over the `.sandbox` key of `~/.claude/settings.json`.

The guard's reason begins `~/.claude holds session history and Claude Code's own state; agents may read only their own saved tool output and the plugin's files`. The run ended `FAIL: 0 commands allowed that --base blocked, 0 recorded reads refused, 1 headless commands with a different verdict now, none of them accepted`. Its other two halves passed: `blocked at c7adaf4, allowed now: 0 (and 1 accepted)` and `refused now: 0 (and 20 accepted)`.

**Why it was allowed then.** The headless half replays each Bash command a headless agent ran through today's guard, and records a change of verdict (`tests/replay_guard.py:470-489`). Agents run the installed plugin's guard, not this checkout's. Claude Code's install record, `~/.claude/plugins/installed_plugins.json`, gives `checked-plans@checked-plans` at `gitCommitSha` `7158a7bd498005e8245cb1603838b166f805db03`, installed and last updated `2026-10-01T19:53:44.727Z`, for both its user and project entries. Commit `7158a7b` (2026-10-01) is before the guard-path-identity merge (`0546620`, 2026-10-02), and that copy's `hooks/agent-guard.py` has no `CLAUDE_HOME`. So an agent run since then could read `~/.claude/settings.json` through the guard, and today's guard blocks it. Which run recorded the command isn't known *(assumption: an agent checking a user `sandbox.network` key, as the 2026-10-02 network-setting spec's verifier tried to, `docs/specs/records/2026-10-02-implementer-refuses-network-setting-record.md:9`)*. Nothing depends on which.

**Today's guard.** `CLAUDE_HOME` is `~/.claude` (`hooks/agent-guard.py:302`), its block message is at :304, and the allow-list test is at :1205. W3 made it so, and its Done when asked for each newly refused recorded read to be accepted with a reason naming W3, and its seven headless entries (`tests/replay-accepted.txt:80-86`) show it applied to commands too (`docs/specs/2026-10-02-guard-path-identity.md:132-136`).

**The accepted file.** Each line is `<fingerprint> <half> <then>-><now>  # <why>`, the fingerprint being the first 16 hex characters of the command's SHA-256 (`tests/replay-accepted.txt:1-8`). `load_accepted` reads it, and exits on a line that doesn't match `ENTRY` (`tests/replay_guard.py:328-330`, :339-354). The replay leaves accepted differences out before deciding its exit code, and reports an accepted one that no longer occurs as stale without failing (:30-36). The last seven lines are W3's headless entries, each `headless allowed->blocked  # names ~/.claude or its state (settings.json, usage-data, ...): refused since W3 (2026-10-02)` (`tests/replay-accepted.txt:80-86`).

**The rule.** `CLAUDE.md:19-22` says to add an entry, with its reason, only for a change the guard means, by fingerprint, never by the command.

## Non-goals

- Updating the installed plugin. That's the user's step (`README.md:134-149`), not a change to the repo. Until it's done, agents keep running the 2026-10-01 guard, and the replay may find more differences like this one.
- Any change to `hooks/agent-guard.py` or `tests/replay_guard.py`.

## Design

One line at the end of `tests/replay-accepted.txt`:

```
caa06a7031956b32 headless allowed->blocked  # names ~/.claude or its state (settings.json, usage-data, ...): refused since W3 (2026-10-02); run under the plugin installed at 7158a7b, before W3
```

The fingerprint, half and change are copied from the replay's output. The reason is W3's, plus why it was allowed when it ran.

## Work items

### W1: Accept the difference

- **Change:** append the Design's line to `tests/replay-accepted.txt`.
- **Files:** `tests/replay-accepted.txt`.
- **Done when:**
  - `python3 tests/replay_guard.py` exits 1 at `07c02eb`, with `verdict changed since they ran: 1 (and 36 accepted)`, and exits 0 after, with `verdict changed since they ran: 0 (and 37 accepted)` and no `FAIL:` line.
  - `python3 -m unittest discover -s tests` passes.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 10 minutes: one line, and two replay runs (an estimate; no run was timed) | — |

Estimated from reading the replay and its accepted file. No agent or skill file changes, so no eval run is due (`CLAUDE.md:23-38`).

## Spike questions

None.

## Risks and rollback

- **The replay reads this machine's transcripts.** It prints SKIP and exits 0 where there are none (`tests/replay_guard.py:30-36`), so the Done when holds only on this machine, as the replay does today.
- **More differences while the install is stale.** Each new agent run under the 2026-10-01 guard may record another `~/.claude` read that today's guard blocks. Updating the plugin stops that.
- **Rollback:** remove the line.

## Open questions

- None.

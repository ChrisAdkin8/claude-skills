# Record: The guard replay accepts the recorded jq read of ~/.claude/settings.json

What happened to [2026-10-04-replay-guard-settings-jq-read](../2026-10-04-replay-guard-settings-jq-read.md) after it was written. The spec is the plan; this file is its history, and nothing here is part of the plan. Sections appear as they're needed, in this order; leave out any that have nothing in them yet.

## Verification

- Quick spec on 2026-10-04: no cold review or spikes.
- 2026-10-04: spec-verifier, 21 of 24 claims confirmed. Plan holds: yes. Two UNSUPPORTED it couldn't check from its sandbox, left as written: the replay's output (it may not run the replay; observed by the author's run from the repo root the same day, and W1's Done when re-runs it) and the install record's commit and timestamp (the guard refused its read; the author read `~/.claude/plugins/installed_plugins.json` the same day, and the verifier's own guard showed the pre-W3 block message). W3's Done when re-worded to "recorded read", and the INHERITED replay time labelled an estimate.
- 2026-10-04, after verification: the Background's copy of the replay's output names the command by its fingerprint only, and the guard's message starts at `~/.claude`, not the home path: the command comes from private transcripts and this repo is public (`tests/replay-accepted.txt:7-9`). The plan didn't change.

## Implementation

- 2026-10-04, W1 (`bbac000`): built as specified, by hand, without `/implement`. `python3 tests/replay_guard.py` exited 1 before, with `verdict changed since they ran: 1 (and 36 accepted)`, and 0 after, with `verdict changed since they ran: 0 (and 37 accepted)` and no `FAIL:` line; the other halves were unchanged (`1 accepted`, `20 accepted`). `python3 -m unittest discover -s tests` passes. Done when met.

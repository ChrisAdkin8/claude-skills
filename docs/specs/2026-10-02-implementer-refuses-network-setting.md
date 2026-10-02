---
title: The implementer's launcher refuses a user setting that opens its sandbox to the network
created: 2026-10-02
status: in-progress # draft | reviewed | in-progress | done | superseded
research: none
idea: ~/notes/ideas/2026-10-02-implementer-refuses-network-setting.md
read-at: 99e002e
cite-repo: none # this repo cites itself
---

# The implementer's launcher refuses a user setting that opens its sandbox to the network

## Goal

`skills/implement/scripts/run-implementer.sh` refuses to start the implementer (exit 2, naming the key) when `~/.claude/settings.json` sets any key under `sandbox.network` to a value that isn't empty, or sets `strictAllowlist` to anything but `true`. Once it's done, a user's own allowed domains, sockets or proxy can't reach the implementer's Bash, which the implementer-sandbox spec says has no network.

## Decision

Refuse every non-empty `sandbox.network` key, not only `allowedDomains`. Settled with the user on 2026-10-02. One check then covers network keys the launcher doesn't name, including any Claude Code adds later, and it fails closed: a key it doesn't know is refused, not let through. `strictAllowlist: true` is what the implementer's own settings set (`skills/implement/implementer-settings.json:5-8`), so a user who sets it too is still let through.

- Rejected: only `sandbox.network.allowedDomains`, as the idea note proposed. It leaves the other network keys unchecked.
- Rejected: also refusing in the implement-verifier's launcher. See Non-goals.

## Background

Read at `99e002e` on 2026-10-02, the merge of the implementer-sandbox branch.

**The no-network decision.** The implementer-sandbox spec decided that the implementer's Bash gets no network: no allowed domains, the same as the verifier (`docs/specs/2026-10-02-implementer-sandbox.md:21`). Its settings file has `allowedDomains: []` and `strictAllowlist: true` (`skills/implement/implementer-settings.json:5-8`), and `tests/test_sandbox_settings.py:185` pins `allowedDomains` as empty.

**User settings load.** The launcher passes `--setting-sources user` and `--settings "$run/settings.json"` (`skills/implement/scripts/run-implementer.sh:355-359`, the flags at :357), so `~/.claude/settings.json` loads alongside the implementer's sandbox. That spec left open whether the user's sandbox keys widen a `--settings` sandbox (`docs/specs/2026-10-02-implementer-sandbox.md:87`). For `allowRead`, the docs say entries merge from every settings scope a session loads *(unverified)* ([sandboxing](https://code.claude.com/docs/en/sandboxing), as cited by `docs/specs/2026-10-02-guard-path-identity.md`). Whether `allowedDomains` merges the same way, and whether `strictAllowlist: true` stops it, is untested here *(assumption: it may widen; the launcher refuses either way, so no work item depends on the answer)*.

**The check today.** Before each call, an inline Python block reads `~/.claude/settings.json` (`skills/implement/scripts/run-implementer.sh:122-146`). A missing file passes (:128-129); a file it can't read or parse exits 2 (:130-131). It takes `sandbox` and `sandbox.filesystem`, treating a value that isn't a dict as empty (:132-134). It builds a list of widening keys from four tests (:135-142): `sandbox.enabled` is `False`, `sandbox.allowUnsandboxedCommands` is `True`, and `sandbox.excludedCommands` or `sandbox.filesystem.allowWrite` is truthy. If the list isn't empty, it exits 2 with the keys joined by commas (:143-145). The header comment lists "a user setting that could widen the sandbox" among the exit-2 causes (:18-20), and :45-46 says a widening user setting refuses the run; neither names the keys.

**The gap.** Code review during the implementer-sandbox build found that a user's `sandbox.network.allowedDomains` isn't refused, and left it open (`docs/specs/records/2026-10-02-implementer-sandbox-record.md:117`).

**The test.** `test_a_widening_user_setting_is_refused` (`tests/test_run_implementer.py:278-297`) writes each of four `sandbox` values in turn to the test home's `~/.claude/settings.json`, and asserts exit 2 with the key named in the output (:282-292). It then asserts no call was made (:293), and that a file with `enabled: True`, an empty `excludedCommands` and an unrelated key exits 0 (:294-297).

**User docs.** `docs/containment.md:68-70` says the launcher refuses a sandbox key that could widen the sandbox, without naming keys, so it stays true. No other doc lists the refused keys: `README.md`, `skills/implement/SKILL.md`, `hooks/agents/implementer.md` and `CHANGELOG.md` don't name `excludedCommands` or `allowUnsandboxedCommands` (grep at `99e002e`).

**Checks.** `python3 -m unittest discover -s tests` runs the launcher's tests (`CLAUDE.md:10-18`). A change to `skills/implement/` also needs the implement skill-eval cases, `implement-basic` and `implement-trap`, run by hand on Sonnet and Opus (`CLAUDE.md:35-38`). Their results go in a dated section of `tests/agent-evals/BASELINE.md` (`CLAUDE.md:23-26`, :31-34).

## Non-goals

- The implement-verifier's launcher, `skills/implement/scripts/run-verify.sh`, also loads user settings (`skills/implement/scripts/run-verify.sh:148-151`) and refuses none. Left for a later idea, chosen by the user on 2026-10-02.
- `hooks/run-agent.sh`'s read-only agents, whose sandbox (`hooks/agent-sandbox.json`) allows some hosts on purpose.
- Testing whether user network keys really widen a `--settings` sandbox. The launcher refuses them either way.
- No change to `implementer-settings.json` or `docs/containment.md`.

## Design

After the `fs` line (`skills/implement/scripts/run-implementer.sh:134`), the block takes `net`, the `sandbox.network` dict, treating a value that isn't a dict as empty, as `fs` does. Each key in `net` is added to the widening list as `sandbox.network.<key>`, in sorted order, when its value is truthy, with one exception: `strictAllowlist` is added when its value is anything but `True`, `false` and `null` included, since turning it off could loosen the allowlist *(assumption)*. Any other key set to an empty list, `false`, `0` or `null` passes. The exit-2 message at :143-145 is unchanged: it already names every key in the list.

For example, `{"sandbox": {"network": {"allowedDomains": ["github.com"]}}}` exits 2 with `sets sandbox.network.allowedDomains, which could widen the implementer's sandbox`. `{"sandbox": {"network": {"allowedDomains": [], "strictAllowlist": true}}}` passes.

## Work items

### W1: The launcher refuses any non-empty user network key

- **Change:** in the inline block at `skills/implement/scripts/run-implementer.sh:132-142`, add the `sandbox.network` check as Design says. Update the comment at :122 to say network keys are refused too. In `test_a_widening_user_setting_is_refused` (`tests/test_run_implementer.py:278-297`), add four `(sandbox, key)` tuples to the loop at :282-292: `{"network": {"allowedDomains": ["github.com"]}}` naming `allowedDomains`; `{"network": {"allowLocalBinding": true}}` naming `allowLocalBinding`, a key the launcher doesn't name; `{"network": {"strictAllowlist": false}}` naming `strictAllowlist`; and `{"network": {"strictAllowlist": null}}` naming `strictAllowlist`. The loop checks only that one key is in the output (:292), so the case that must name one key and not another goes in its own block after the loop and before the no-call assertion at :293: it writes `{"sandbox": {"network": {"strictAllowlist": true, "httpProxyPort": 8080}}}`, and asserts exit 2, `httpProxyPort` in the output and `strictAllowlist` not in it. Add `"network": {"allowedDomains": [], "strictAllowlist": true}` to the passing file at :294-295. Write the tests first.
- **Files:** `skills/implement/scripts/run-implementer.sh`, `tests/test_run_implementer.py`, `tests/agent-evals/BASELINE.md`.
- **Done when:**
  - `python3 -m unittest tests.test_run_implementer` fails at `99e002e` with the new subtests (each exits 0, not 2, and a call is made), and passes after the change.
  - `python3 -m unittest discover -s tests` passes, and `shellcheck -S warning skills/implement/scripts/run-implementer.sh` prints nothing, at the level CI runs it (`.github/workflows/tests.yml:28`). At the default level the file already gets an info note (`skills/implement/scripts/run-implementer.sh:119`) and a style note (:389) at `99e002e`, neither from this change.
  - By hand: `EVAL_MODEL=sonnet tests/skill-evals/run.sh implement-basic implement-trap`, then the same with `EVAL_MODEL=opus`, print PASS for both cases (`CLAUDE.md:35-38`). Each case's result and cost, the implementer's and verifiers' from their `run.json` files included, goes in a dated `tests/agent-evals/BASELINE.md` section with a column per model.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 30 minutes for the code and tests: about six lines of Python, four subtests and one test block. Plus the paid evals: two cases × two models, each case up to $3 for the skill's session, $5 for the implementer and $5 for each of up to two verifiers (`CLAUDE.md:27-29`, :35-38) | — |

The code estimate comes from reading the launcher and its test, not from doing it; the eval costs are the repo's caps, so the real spend is likely lower.

## Spike questions

None.

## Risks and rollback

- **A user with network settings can't run `/implement`.** Someone who sets `sandbox.network.allowedDomains` for their own sessions must remove it first, as with the four keys refused today. The message names the key.
- **A future network key whose empty-looking value widens.** A key other than `strictAllowlist` set to `false` or `0` passes. If Claude Code adds a key where `false` opens something, this check misses it. Unlikely, since the sandbox's other network keys add access when set *(assumption)*.
- **Rollback:** W1 is one commit; reverting it restores today's four checks.

## Open questions

- None.

# Spike results: Install the skills from the Claude Code plugin marketplace, part 1: plumbing

## S2

### After `claude plugin install` from a marketplace (not `--plugin-dir`), does the cache copy keep the executable bit on `hooks/*.py`, `hooks/*.sh` and `skills/*/scripts/*`, and does `hooks/agents/` stay unloaded as agents?

Expect: after a local-marketplace install into a scratch `HOME`, the 14 files git tracks as 100755 under `hooks/` and `skills/` are still executable in the cache, and the plugin's component inventory lists the four skills and no agents.
Runs: 1

#### Commands

```
# src/ has no .claude-plugin yet (W1 not built): wrote minimal plugin.json + marketplace.json (source "./") into src/.claude-plugin
export HOME=$PWD/h        # scratch HOME, claude 2.1.285
claude plugin marketplace add $PWD/src
claude plugin install claude-skills@claude-skills
find hooks skills -type f -perm -u+x   # in src and in the cache dir; diff
ls -l <cache>/hooks <cache>/skills/*/scripts
claude plugin details claude-skills@claude-skills
claude agents --json
# positive control: separate marketplace "ctl" with top-level agents/probe.md
claude plugin marketplace add $PWD/ctl; claude plugin install ctl@ctl; claude plugin details ctl@ctl
```

#### Output

Run 1. Cache path h/.claude/plugins/cache/claude-skills/claude-skills/0.1.0
```
executable files in cache under hooks/ + skills/: 14; diff of src vs cache list: identical
hooks: agent-def.py agent-guard.py git-read.py run-agent.sh sandbox-prompt.py  -rwxr-xr-x
skills: review-state.py build-index.py check-note.py gcp-skus.sh reddit-search.sh repo-health.sh check-spec.py prepare-spike.sh run-spike.sh  -rwxr-xr-x
non-exec (-rw-r--r--, also non-exec in src): agent-sandbox.json/.md, run-agent.md, research/scripts/mdcheck.py
hooks/agents/ copied to cache (4 files)

claude-skills 0.1.0
  Skills (4)  cold-review, idea, research, spec
  Agents (0)
  Hooks (0)

claude agents --json  ->  []
```
Control (top-level agents/probe.md, plugin ctl):
```
  Agents (1)  probe
```

#### Verdict

EXPECTED: all 14 executable files keep mode 755 in the marketplace-install cache copy, and `plugin details` shows 4 skills and 0 agents for the plugin with agents in `hooks/agents/`; the control shows the inventory does see a top-level `agents/`.

#### Notes

- The manifests were minimal stand-ins I wrote; the real plugin.json may add fields, but agent discovery is by directory.
- `Hooks (0)` is because no hooks/hooks.json exists; `hooks/` is not auto-registered (relevant to any work item expecting hooks from that dir).
- `claude agents --json` returned `[]` even for the control plugin (no auth/network in sandbox), so it is not a usable instrument here; `plugin details` was used instead.
- Network denials to api.anthropic.com occurred but did not affect install.

total_cost_usd: 0.192733; num_turns: 11

## Q5 (run by hand, 2026-09-29)

### Does `claude plugin validate` run without credentials, so CI can call it?

Runs: 1, in `S2/src`, which holds the S2 spiker's stand-in manifests, with `HOME=$(mktemp -d)` and `ANTHROPIC_API_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` unset.

#### Commands

```
HOME=$(mktemp -d) env -u ANTHROPIC_API_KEY -u CLAUDE_CODE_OAUTH_TOKEN claude plugin validate . --strict; echo "exit $?"
```

#### Output

```
Validating marketplace manifest: .../S2/src/.claude-plugin/marketplace.json

⚠ Found 1 warning:

  ❯ description: No marketplace description provided. Adding a description helps users understand what this marketplace offers

✘ Validation failed (--strict treats warnings as errors)
exit 1
```

#### Verdict

INCONCLUSIVE on credentials, and DIFFERENT for W1: validation ran with no API key or login prompt, so it did not ask for credentials in a scratch `HOME`. It failed under `--strict` only because the stand-in `marketplace.json` has no top-level `description`, so the real one needs it.

#### Notes

- A macOS Keychain login survives a scratch `HOME`, so "no credentials" is proven only on a fresh CI runner; W1's first CI run is the real test.
- The output shows only the marketplace manifest check. Whether `plugin.json` is checked in the same run is not shown.

## Q6 (run by hand, 2026-09-29)

### Does a sandbox `excludedCommands` entry written with the absolute plugin root exclude a call written with that same absolute path?

Runs: 1, with a stand-in `probe.sh` (one `curl` to `api.github.com`, so no `gh` credentials) in `~/.cache/spike-q6`, and `claude -p --setting-sources user --settings <file> --allowedTools Bash` told to run `$S/probe.sh x` by its absolute path. Three settings files, each with the sandbox enabled and `network.allowedDomains: []`: `abs` (`excludedCommands` holds the absolute path), `tilde` (it holds `~/.cache/spike-q6/probe.sh *`), `none` (empty).

#### Output

```
== abs    http 200
== tilde  curl: (56) CONNECT tunnel failed, response 403 / http 000
          deny network-outbound api.github.com:443 (host is not on the allow list)
== none   curl: (56) CONNECT tunnel failed, response 403 / http 000
```

#### Verdict

EXPECTED: an entry written with the absolute path excludes a call written with it (`abs` reached the network), while an entry written with `~` does not exclude an absolute-path call (`tilde` was blocked, as `hooks/agent-guard.py:209-213` says). The `none` control was blocked, so the sandbox does block the host.

#### Notes

- The script was a stand-in for `repo-health.sh`; the test shows the exclusion pattern matching, not `gh` itself.
- The model was told the absolute path, as skills will be once `${CLAUDE_PLUGIN_ROOT}` expands (spike Q1).

## Q3 (run by the user, 2026-09-30)

### Does `run-agent.sh` run an agent end to end from the cache path, with the agent's Read and Bash guarded there?

Runs: 1, by the user, recorded in part 1's record (`## Implementation`); not re-run for this file. `run-agent.sh spec-verifier` from the plugin cache copy, `~/.claude/plugins/cache/claude-skills/claude-skills/0.1.0/hooks/run-agent.sh`, on a tiny spec whose cite repo was that cache copy.

#### Output

```
exit 0; run.json subtype success; 4 turns; $0.07
reply.md closing lines: the claim table, "Confirmed: 1 of 3", "Plan holds: no"
the verifier read hooks/run-agent.sh in the cache to check its citation (it quoted line 1 and lines 54 and 61)
run.json holds no denial; the rendered settings.json names the absolute cache path in excludedCommands
```

#### Verdict

EXPECTED: an agent ran end to end from the cache path, and the guard's own-root exemption let it read the plugin's files.

#### Notes

- The run used the user's real `HOME`, not a scratch one, so the marketplace install went into the real `~/.claude/plugins` and the credentials were the real login. The scratch-`HOME` half is covered by W1's and spike 2's installs and by `RunAgentFromACache`.
- Not tested: an agent that runs a `SCRIPTS` script from the cache (the tiny spec needed none), and a scratch `HOME` behind a link.

## Q4 (replay of recorded agent sessions, 2026-09-30)

### Which paths under the plugin root do the four agents actually read, so the guard's "own root only" rule for `~/.claude/plugins/` doesn't block one?

Runs: 1, `python3 tests/replay_guard.py`, recorded in part 1's record (`## Implementation`); not re-run for this file. It was run with the own-root rule in place, after a fix (`7731c56`) so each headless run is judged with the plugin root its `agents.json` names; before that it judged the spike 3 run by a checkout's guard and let one call's working directory leak into the next (153 headless differences).

#### Output

```
refused reads: 0
headless differences: 8, the same 8 as at edca724
```

#### Verdict

INCONCLUSIVE on the list of paths, EXPECTED on the concern: the rule refused none of the recorded reads, but the replay counts refusals and does not list which plugin paths the agents read, and it covers only the transcripts on this machine.

## Q5 (CI, 2026-09-30)

### Does `claude plugin validate` run without credentials, so CI can call it?

Runs: 1, on the GitHub `macos-latest` runner with no secret configured: run `36704261516`, at `04dd1b7`, on the branch behind draft PR #28. It closes the question the local run (above, `## Q5 (run by hand, 2026-09-29)`) left open, since a macOS Keychain login survives a scratch `HOME` and a fresh runner has none.

#### Output

```
Install the claude CLI, pinned:  npm install -g @anthropic-ai/claude-code@2.1.285  ->  added 2 packages in 3s
                                 npm warn install-scripts: @anthropic-ai/claude-code@2.1.285 (postinstall: node install.cjs) not yet covered by allowScripts
Validate the plugin and marketplace manifests:  claude plugin validate . --strict  ->  Validation passed
Validate the plugin's skills:  claude plugin validate .claude-plugin/plugin.json  ->  Validation passed with warnings
    (one warning: CLAUDE.md at the plugin root is not loaded as project context)
all seven steps of the job: success
```

#### Verdict

EXPECTED: `validate` ran on a fresh runner with no login and no secret, and both validate steps passed.

#### Notes

- The runner had npm, and the pinned package installed and ran.
- npm warns that the package's `postinstall` script is not yet covered by `allowScripts`. It ran here, or is not needed, since `validate` worked. A later npm that blocks such scripts by default could break the install step, so that warning is the thing to look at if this step ever fails.

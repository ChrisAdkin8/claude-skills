# Spike results: Install the skills from the Claude Code plugin marketplace

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

## Q1 (run by hand, 2026-09-29)

### Does `${CLAUDE_PLUGIN_ROOT}` expand in `allowed-tools` frontmatter, and does the expanded absolute path then match the Bash call the model writes, so the command runs without a prompt?

Runs: 1, with `claude -p --plugin-dir` on a scratch plugin `hello` holding three skills that each run `<root>/bin/hello world`: `var` (`allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/hello *)`), `abs` (the same with the literal absolute path) and `none` (no `allowed-tools`).

#### Output

```
== var    hello world        denials: []
== abs    hello world        denials: []
== none   blocked, needs approval
          denials: [{'tool_name': 'Bash', 'tool_input': {'command': '/var/folders/qp/.../T/tmp.yjHIJt7DT6/p/bin/hello world', ...}}]
```

#### Verdict

EXPECTED: the variable expands in `allowed-tools`, and the model's expanded absolute-path call matched it with no prompt; `abs` worked as the positive control and `none` was denied as the negative control, so the test can see a denial. The `none` denial shows the skill body's `${CLAUDE_PLUGIN_ROOT}` expanded to an absolute path, which is what the model then writes.

#### Notes

- Tested under `--plugin-dir`, where the root is the directory itself. A marketplace install's versioned cache path was not tested, though it goes through the same expansion.
- The MCP authorization text in the replies was unrelated noise.

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

## Q7 (run by hand, 2026-09-29)

### Does a plugin's skill answer to its bare name (`/var`) as well as to `/hello:var`?

Runs: 1, with `claude -p --plugin-dir $P --output-format json --max-turns 4 "/var"` on the Q1 scratch plugin `hello`, whose `var` skill runs `<root>/bin/hello world`.

#### Output

```
hello world
```

#### Verdict

EXPECTED (the bare name resolves): `/var` ran the plugin's skill and printed `hello world`, with no denial.

#### Notes

- Tested under `--plugin-dir`, with no other skill named `var`. Not tested: a marketplace install, or a bare name shared with another skill, such as the same skill still linked in `~/.claude/skills`.

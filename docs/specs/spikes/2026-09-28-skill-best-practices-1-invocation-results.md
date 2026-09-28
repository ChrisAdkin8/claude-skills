# Spike results: Skill best practices, part 1 - who can start the skills and agents

All three spikes were run by hand in the authoring session on 2026-09-28, with Claude Code 2.1.283. Each needs a live `claude -p`, which the `/spec spike` sandbox can't reach (no network). Each ran from a scratch directory, and removed what it created: two throwaway user skills in `~/.claude/skills`, and a scratch repo under `~/code`. Every `claude -p` call was capped at `--max-budget-usd 0.3`.

`--allowedTools` takes a list of values, so a prompt placed straight after it is read as one more tool name, and `claude` then fails with "Input must be provided either through stdin or as a prompt argument". Every command below puts a flag with no value (`--strict-mcp-config`) between the list and the prompt. Two early runs of S3 missed this and failed at start-up, at no cost; they're left out.

## S1

### Does an agent passed by `--agents <file> --agent <name>` keep its `tools` allowlist, its PreToolUse hooks and its MCP tools?

Expect: its Read is blocked by the hook; it has no Glob or Bash; its `init` event's `tools` list holds only its own tools.
Runs: 1

#### Commands

```
# agents.json: {"spk": {"description": "...", "prompt": "...",
#   "tools": ["Read", "mcp__plugin_aws-core_aws-mcp__aws___list_regions"],
#   "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": "<scratch>/hook.sh"}]}]}}}
# hook.sh: echo "SPIKE-HOOK blocked this Read" >&2; exit 2
claude -p --agents <scratch>/agents.json --agent spk --output-format stream-json --verbose --max-turns 6 \
  --max-budget-usd 0.3 --allowedTools "Read Glob Bash" --setting-sources user \
  "Step 1: use the Read tool on <scratch>/file.txt. Step 2: use the Glob tool with pattern '*'. Step 3: run 'ls' with the Bash tool. ..."
```

#### Output

```
init tools: ['Read', 'mcp__plugin_aws-core_aws-mcp__aws___list_regions']
   has Read: True | Glob: False | Bash: False | MCP tool: True
tool_use: Read {'file_path': '<scratch>/file.txt'}
tool_result: is_error=True PreToolUse:Read hook error: [<scratch>/hook.sh]: SPIKE-HOOK blocked this Read
permission_denials: ['Read']   cost: $0.051
```

The agent reported Glob and Bash as not available to it. Both were in the session's `--allowedTools`, so only the agent's `tools` list can have removed them.

#### Verdict

EXPECTED. An agent passed by `--agents` keeps its `tools` list (tools outside it aren't offered, even when the session allows them), its PreToolUse hooks (the hook blocked Read), and a listed MCP tool.

## S2

### Do `Edit(~/code/**/records/*-record.md)` and `Edit(~/code/**/*.md)` in a skill's `allowed-tools` allow a matching write and refuse a `.py` beside it?

Expect: the records pattern writes `records/a-record.md` and refuses `records/a.py`; the markdown pattern writes any `.md` and refuses a `.py`.
Runs: 1

#### Commands

```
# scratch repo: ~/code/spike-perm-<stamp>, with docs/records/ and docs/specs/
# ~/.claude/skills/zz-spike-records/SKILL.md: allowed-tools: Edit(~/code/**/records/*-record.md)
#   "With the Write tool, write "x" to <repo>/docs/records/a-record.md, then to <repo>/docs/records/a.py ..."
# ~/.claude/skills/zz-spike-md/SKILL.md: allowed-tools: Edit(~/code/**/*.md)
#   "... write "x" to <repo>/docs/specs/s.md, then to <repo>/x.py ..."
# run from the scratch directory, outside ~/code; no Write or Edit in --allowedTools; default permission mode
claude -p --output-format json --max-turns 6 --max-budget-usd 0.3 --allowedTools "Read" --strict-mcp-config "/zz-spike-records"
claude -p --output-format json --max-turns 6 --max-budget-usd 0.3 --allowedTools "Read" --strict-mcp-config "/zz-spike-md"
```

#### Output

```
zz-spike-records | denials: [('Write', 'docs/records/a.py')] | cost 0.14
   docs/records/a-record.md: WROTE
   docs/records/a.py: REFUSED. "Claude requested permissions to write to .../docs/records/a.py, but you haven't granted it yet."
zz-spike-md | denials: [('Write', 'x.py')] | cost 0.126
   docs/specs/s.md: WROTE
   x.py: REFUSED. "Claude requested permissions to write to .../x.py, but you haven't granted it yet."
files written: ./docs/records/a-record.md  ./docs/specs/s.md
```

#### Verdict

EXPECTED. Both patterns work in a skill's `allowed-tools`: each allowed the file it names, including through the Write tool, and refused a `.py` beside it.

## S3

### Does `disable-model-invocation: true` take a skill out of the `init` event's `skills` list, and does a typed `/name` still run it, with and without the Skill tool?

Expect: the disabled skill is missing from `skills` but present in `slash_commands`; a typed `/name` runs it with `Skill` in `--allowedTools` and without.
Runs: 1

#### Commands

```
# ~/.claude/skills/zz-spike-probe-disabled/SKILL.md (disable-model-invocation: true) and zz-spike-probe-enabled (without it),
#   each "Reply with exactly this and nothing else: PROBE-<kind>-<token>"
claude -p --output-format stream-json --verbose --max-turns 1 --max-budget-usd 0.3 'ok'          # the init event
claude -p --output-format stream-json --verbose --max-turns 4 --max-budget-usd 0.3 --allowedTools "Read Skill" --strict-mcp-config "/zz-spike-probe-disabled"
claude -p --output-format stream-json --verbose --max-turns 4 --max-budget-usd 0.3 --allowedTools "Read" --strict-mcp-config "/zz-spike-probe-disabled"
claude -p --output-format stream-json --verbose --max-turns 4 --max-budget-usd 0.3 --allowedTools "Read Skill" --strict-mcp-config "/zz-spike-probe-enabled"
# then, the model asked to use the Skill tool itself:
claude -p --output-format stream-json --verbose --max-turns 4 --max-budget-usd 0.3 --allowedTools "Skill" --strict-mcp-config \
  'Call the Skill tool with skill "zz-spike-probe-<kind>". Then reply with the tool'"'"'s result, quoted exactly, and nothing else.'
```

#### Output

```
init skills:         ['zz-spike-probe-disabled', 'zz-spike-probe-enabled']
init slash_commands: ['zz-spike-probe-disabled', 'zz-spike-probe-enabled']

typed /zz-spike-probe-disabled, Skill allowed:     ran=True  tool_uses=[]  turns=1 cost=0.125  reply: PROBE-disabled-<token>
typed /zz-spike-probe-disabled, Skill not allowed: ran=True  tool_uses=[]  turns=1 cost=0.005  reply: PROBE-disabled-<token>
typed /zz-spike-probe-enabled,  Skill allowed:     ran=True  tool_uses=[]  turns=1 cost=0.111  reply: PROBE-enabled-<token>

model asks the Skill tool for the disabled skill:
  tool_use: Skill {'skill': 'zz-spike-probe-disabled'}
  tool_result: is_error=True "<tool_use_error>Skill zz-spike-probe-disabled cannot be used with Skill tool due to
               disable-model-invocation. Ask the user to run /zz-spike-probe-disabled thems[elves]..."   cost 0.124
model asks the Skill tool for the enabled skill:
  tool_use: Skill {'skill': 'zz-spike-probe-enabled'}
  tool_result: "Launching skill: zz-spike-probe-enabled"   reply held the token   cost 0.119
```

When the two probe skills were created, the authoring session's own skill list gained `zz-spike-probe-enabled` only: the disabled one was never offered to the model.

#### Verdict

DIFFERENT, in part.
- **Typed commands: as expected.** A typed `/name` runs a disabled skill whether or not `Skill` is allowed, with no Skill tool call. So the prompt is expanded as a typed command, and W1 stands.
- **The start event: not as expected.** The `init` event's `skills` list still holds a disabled skill, so it can't show the field is set.
- **The observable check instead:** the Skill tool refuses a disabled skill with "cannot be used with Skill tool due to disable-model-invocation", while an enabled one launches.

Total for S1-S3: about $0.80 across nine calls.

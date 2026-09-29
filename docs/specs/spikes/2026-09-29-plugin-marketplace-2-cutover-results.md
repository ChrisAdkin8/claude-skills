# Spike results: Install the skills from the Claude Code plugin marketplace, part 2: cutover

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

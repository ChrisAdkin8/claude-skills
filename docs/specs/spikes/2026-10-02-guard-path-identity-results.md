# Spike results: The guard judges paths as macOS resolves them, and keeps ~/.claude private

## S1

### Does the macOS sandbox refuse `~/.AWS/credentials` and `~/.CLAUDE/settings.json` to Bash when `denyRead` lists `~/.aws` and `~/.claude`, and does a `Read(~/.aws/**)` permission deny refuse the Read tool `~/.AWS/credentials`?

Expect: the macOS sandbox refuses `wc -c ~/.CLAUDE/settings.json` and `wc -c ~/.AWS/credentials`; the Read tool's `Read(~/.claude/**)`/`Read(~/.aws/**)` denies don't catch a missing file under `~/.CLAUDE/` or `~/.AWS/` (not-found error, not a permission refusal).
Runs: 1

#### Commands

```
ls -ld ~/.aws ~/.AWS ~/.claude ~/.CLAUDE        # all four exist, same size/mtime: volume is case-insensitive
wc -c ~/.CLAUDE/settings.json; wc -c ~/.AWS/credentials
wc -c ~/.claude/settings.json; wc -c ~/.aws/credentials      # lowercase controls
wc -c ~/.AWS/nonexistent-spike; wc -c ~/.aws/nonexistent-spike
ls ~/.aws ~/.AWS ; ls ~/.Aws ~/.cLaUdE ; wc -c ~/.cLaUdE/settings.json
Read /Users/chrisadkin/.AWS/credentials
Read /Users/chrisadkin/.aws/credentials
Read /Users/chrisadkin/.CLAUDE/spike-missing.txt
Read /Users/chrisadkin/.cache/spec-spikes/nonexistent-spike.txt   # control outside denied dirs
```

#### Output

```
wc: ~/.CLAUDE/settings.json: open: Operation not permitted
wc: ~/.AWS/credentials: open: No such file or directory      (~/.aws/credentials also ENOENT: the file does not exist)
wc: ~/.claude/settings.json: open: Operation not permitted   (lowercase control)
wc: ~/.AWS/nonexistent-spike: No such file or directory      (same as lowercase)
ls: ~/.aws: Operation not permitted ; ls: ~/.AWS: Operation not permitted ; ls: ~/.Aws / ~/.cLaUdE: Operation not permitted
wc: ~/.cLaUdE/settings.json: Operation not permitted

Read .AWS/credentials         -> "File is in a directory that is denied by your permission settings."
Read .aws/credentials         -> same message
Read .CLAUDE/spike-missing.txt-> same message (file does not exist)
Read <non-denied missing file>-> "File does not exist."   (control: instrument can tell the two errors apart)
```

#### Verdict

DIFFERENT: Bash half: the sandbox does fold case. `~/.CLAUDE/settings.json` is refused exactly like `~/.claude/settings.json`, and `ls` on `.AWS`, `.Aws`, `.cLaUdE` is refused too. `~/.AWS/credentials` could not show a refusal because the file doesn't exist on this machine (ENOENT with lowercase too); `ls ~/.AWS` is refused, which covers the directory. Read half: contrary to Expect, the Read tool refused all case variants, including a missing file under `~/.CLAUDE/`, with a permission-denied message, not "does not exist". So the Risks line can say case variants are folded by both the sandbox and the Read permission check, on a case-insensitive APFS volume, in this session's settings.

#### Notes

- Not tested: which exact deny rules this session's Read permission uses (settings not inspected; could be `Read(~/.claude/**)` or a directory-level check), and I could not create a scratch file under the denied dirs (writes there are blocked), so a missing file was used instead.
- Case-sensitive volumes were not tested; the result only applies where the filesystem folds case.
- The Bash results only prove folding because the filesystem is case-insensitive (`.AWS` is the same directory as `.aws`).

- total_cost_usd: 0.1598
- num_turns: 10

## S2

#### With the root set to the repo and `deny_answer_keys` applied, is `wc -c` of a `tests/agent-evals/<case>/expect.txt` from Bash refused under `allowRead: [<repo>]`?

Run by hand on 2026-10-02 by the user, from the main session's scratch script, because a spike can't start a logged-in nested `claude -p`. Setup: `hooks/agent-sandbox.json` rendered by `hooks/agent-settings.py` with the repo as root; then `~/.claude` appended to `denyRead`, `allowRead: [<repo>]`, and the paths `deny_answer_keys` adds (the git common dir, `tests/agent-evals`, `tests/skill-evals` and `.git` in the repo, each as given and resolved) added to `denyRead` and as `Read(...)` denies. `claude -p --model sonnet --strict-mcp-config --setting-sources user --settings <file> --allowedTools Bash`, from an empty work dir, no guard. Three Bash calls.

##### Output

```
1. wc -c <repo>/tests/agent-evals/cases/absence-claim/expect.txt: exit 1: open: Operation not permitted
2. wc -c <repo>/hooks/agent-guard.py: exit 0: 66318
3. wc -c ~/.claude/settings.json: exit 1: open: Operation not permitted
```

No `permission_denials`.

##### Verdict

EXPECTED: the answer-key deny, narrower than `allowRead: [<repo>]`, holds; the plugin's own files stay readable, and the rest of `~/.claude` stays refused.

- total_cost_usd: 0.0831
- num_turns: not recorded

## S3

#### With `run-agent.sh`'s flags, `--settings` and the guard, but no `--add-dir ~/.claude`, does an agent read its own saved tool output with the Read tool?

Run by hand on 2026-10-02 by the user, from the main session's scratch script. Setup: `hooks/agent-def.py --root <repo> hooks/agents/cold-reviewer.md` for `--agents` (tools Read, Grep, Glob, Bash, and the guard's `bash` and `read` hooks); `hooks/agent-sandbox.json` rendered with the repo as root, plus `~/.claude` in `denyRead` and `allowRead: [<repo>]`; `hooks/sandbox-prompt.py` for `--append-system-prompt-file`. Flags as `hooks/run-agent.sh:115-118` passes them, on Sonnet, with `--add-dir ~/notes <work dir> <repo>` and no `~/.claude`. The script wrote `big.txt` (`seq 1 300000`) into the work dir first; the agent ran `cat big.txt`, then Read the saved copy at offset 150000, limit 1.

A first run asked the agent to run `seq 1 300000` itself. The guard refused it (`seq` isn't on its command list; one `permission_denials` entry), so nothing was saved and that run tested nothing. Cost $0.0446.

##### Output

```
~/.claude/projects/<cwd slug>/<session ID>/tool-results/b8l5gynga.txt
150000    150000
```

The second line is the Read tool's line number and the line. No `permission_denials`.

##### Verdict

EXPECTED: without `--add-dir ~/.claude`, under W4's sandbox and the guard, the agent read its own saved output with the Read tool.

- total_cost_usd: 0.0338 (the second run)
- num_turns: not recorded

# Spike results: A spike step for /spec, run in sandboxed headless sessions and folded back into the spec

Run by hand on 2026-09-17, from a Claude Code session, after W1 (`65c9f21`) and before W2. `claude --version`: `2.1.274 (Claude Code)`. Scratch output stays in `~/.cache/spec-spikes/claude-skills/2026-09-17-spec-spike-phase/` (`S1/run1`, `S1/run2`, `S1`, `S1-git`, `S1-budget`); the probe repo for spike 2 was deleted after the run.

## S1: Do the sandbox settings contain the spiker?

Expect: `uv` and a Write to `./ok.txt` and `git init` in `src/` succeed; Bash and Write-tool writes outside the scratch dir, Bash and Read-tool reads of `~/notes`, and `curl` to an unlisted host are refused.
Runs: 1 per settings version (three versions), plus a budget-cap run and a git follow-up.

### Command

Run from the scratch dir, which held `brief.md`, `spec.md`, `settings.json` (a copy of `skills/spec/spike-settings.json`) and `src/` (`git archive ac65fbd`):

```
claude -p --model sonnet --append-system-prompt-file ~/.claude/skills/spec/spiker.md --settings settings.json --allowedTools "Read Grep Glob Bash Write(./**) Edit(./**)" --max-budget-usd 2 --max-turns 60 --output-format json --strict-mcp-config --no-session-persistence "$(cat brief.md)" > run.json 2> run.err
```

### Run 1: settings as in the spec's Design ($0.51, 19 turns, `success`)

Nothing leaked, but the settings blocked the spiker's own work:

```
2 Bash cat ~/notes/CLAUDE.md          -> cat: /Users/…/notes/CLAUDE.md: Operation not permitted
3 Bash echo probe > ~/spike-test-bash.txt -> operation not permitted
4 Write ~/.cache/spike-test-write.txt  -> File is in a directory that is denied by your permission settings.
5 Write ~/spike-test-write.txt         -> File is in a directory that is denied by your permission settings.
6 Write ./ok.txt                       -> File is in a directory that is denied by your permission settings.
7 Read ~/notes/CLAUDE.md               -> File is in a directory that is denied by your permission settings.
8 curl -sI https://example.com         -> HTTP/1.1 403 Forbidden, X-Proxy-Error: blocked-by-allowlist
9 git init in src/                     -> src/.git: Operation not permitted
  echo instrument-check > ./instrument-check.txt -> operation not permitted
1 uv run --no-project python -c 'print(1)' -> error: Failed to initialize cache at ~/.cache/uv … Operation not permitted
```

`Write(~/**)` and `Edit(~/**)` match the scratch dir, which is under `~`. Bash writes to the scratch dir and to `~/.cache/uv` failed too, although `sandbox.filesystem.allowWrite` names the latter, so the `Edit` deny evidently reaches the sandbox's write rules as well *(inferred: removing it fixed both)*. The spiker couldn't write `results.md`; `permission_denials` in `run.json` recorded every refused call.

### Run 2: `Write(~/**)` and `Edit(~/**)` removed ($0.50, 20 turns, `success`)

```
1 uv run …                    -> 1
2 Bash cat ~/notes/CLAUDE.md  -> Operation not permitted
3 Bash write to ~/            -> operation not permitted
4 Write ~/.cache/…            -> Claude requested permissions to write to /Users/…/.cache/spike-test-write.txt, but you haven't granted it yet.
5 Write ~/…                   -> Claude requested permissions to write to /Users/…/spike-test-write.txt, but you haven't granted it yet.
6 Write ./ok.txt              -> File created successfully
7 Read ~/notes/CLAUDE.md      -> File is in a directory that is denied by your permission settings.
8 curl                        -> 403 blocked-by-allowlist
9 cd src && git init && …     -> fatal: cannot copy '…/templates/hooks/commit-msg.sample' to '…/src/.git/hooks/commit-msg.sample': Operation not permitted (exit 128)
```

`modelUsage` in `run.json` lists `claude-sonnet-5` and `claude-haiku-4-5-20251001`: `--model sonnet` resolved to Sonnet 5. The reply followed `spiker.md`'s two-line format (`Verdict: DIFFERENT` / `Results: results.md`), so `--append-system-prompt-file` applies in `-p` mode. The spiker also noted that after a bare `cd src`, a Write to the scratch root was refused until it changed back: `Write(./**)` follows the Bash working directory.

### Run 3: narrow Write and Edit denies added (`1810bd8`) ($0.27, 16 turns, `success`)

Denies on `~/notes`, `~/code`, `~/.claude`, `~/.ssh`, `~/.aws`, `~/.zshrc`, `~/.zprofile`, `~/.bashrc` and `~/.profile`, and a new probe 10:

```
1 uv run …                         -> 1
2, 3                               -> Operation not permitted
4, 5                               -> … but you haven't granted it yet.
6 Write ./ok.txt                   -> File created successfully
7 Read ~/notes/CLAUDE.md           -> File is in a directory that is denied by your permission settings.
8 curl                             -> 403 blocked-by-allowlist
9 (cd src && git init --template= && …) -> error: could not write config file …/src/.git/config: Operation not permitted (exit 128)
  echo test > src/probe-write-check.txt  -> test
10 Write ~/code/spike-test-write.txt -> File is in a directory that is denied by your permission settings.
```

No probe wrote outside the scratch dir in any run: `ls ~/spike-test-bash.txt ~/spike-test-write.txt ~/.cache/spike-test-write.txt ~/code/spike-test-write.txt` found none after each run.

### Git follow-up (`S1-git`, $0.16, 6 turns, `success`)

```
A (cd a && git init --template= && …)                                 -> could not write config file …/a/.git/config: Operation not permitted
B (cd b && git --git-dir=gitdir --work-tree=. init --template= && … commit) -> 23ecfb3e78d80b78e5801bcd81aba8ee70558a71
C (cd c && export GIT_DIR=$PWD/gitdir GIT_WORK_TREE=$PWD && git init --template= && … commit && git ls-tree --name-only HEAD) -> d62dcbaaf96bec008b6311ed55d64f30a2bddf0c, a.txt
```

The sandbox refuses writes inside any directory named `.git`. Outside the sandbox, `git add .` with `GIT_DIR` inside the work tree committed `gitdir/HEAD` and `gitdir/config`; with `GIT_DIR` beside it (`src-git`), `git ls-tree -r --name-only HEAD` printed only `a.txt`. That layout is `spiker.md`'s rule (`eb2d97e`); it wasn't re-run inside the sandbox.

### Budget cap (`S1-budget`)

The same command with `--max-budget-usd 0.05`:

```
exit=1
{'type': 'result', 'subtype': 'error_max_budget_usd', 'is_error': True, 'total_cost_usd': 0.096646, 'num_turns': 1}
```

The cap ends the run with a non-`success` subtype and records `total_cost_usd`, but only after the turn that crosses it: $0.097 against $0.05.

### Verdict

DIFFERENT: with the Design's settings the spiker couldn't write in its own scratch dir. With `Write(~/**)` and `Edit(~/**)` replaced by narrow denies, every out-of-directory read, write and network call was refused and scratch-dir writes and `uv` worked, so option B isn't needed. Plain `git init` can't work in the sandbox; a git directory named other than `.git` can. The budget cap holds but overshoots by up to a turn.

## S2: Do W2's allowed-tools entries pre-approve 7b and 7c?

Expect: each side of `&&` and `|` is matched separately, so the entries approve every call as written.
Runs: 1 per probe (three probes).

### Method

A throwaway repo `~/code/spike-probe-tmp` held a project skill whose `allowed-tools` were the entries under test. Each probe ran `claude -p --model sonnet --setting-sources project --output-format json --strict-mcp-config --no-session-persistence --max-budget-usd 3 --max-turns 40 "/<probe skill>"` from that repo, so user settings approved nothing, and the skill made 7b's and 7c's calls with `~` unexpanded. Refused calls show in `permission_denials`.

### Probe 1: `/spec`'s current `allowed-tools` plus W2's entries ($0.16, 12 turns)

```
rm -rf X && mkdir -p X/src && git -C R archive <sha> | tar -x -C X/src  -> This Bash command contains multiple operations. The following part requires approval: rm -rf … && mkdir -p … && git -C … archive <sha>
Write X/spec.md, X/brief.md, X/settings.json  -> Claude requested permissions to write to /Users/…/.cache/spec-spikes/…, but you haven't granted it yet.
cd X && claude -p … "$(cat brief.md)" > run.json 2> run.err  -> Contains shell syntax (string) that cannot be statically analyzed
mkdir -p ~/code/spike-probe-tmp/docs/specs/spikes  -> allowed
Write and Edit ~/code/spike-probe-tmp/docs/specs/spikes/2026-09-17-probe-results.md  -> allowed
```

`Write(~/.cache/spec-spikes/**)` didn't approve Write calls there.

### Probe 2: split calls, `Edit(~/.cache/spec-spikes/**)`, `cp` for the settings ($0.16, 15 turns)

Its `allowed-tools`: `Read Grep Glob Edit(~/code/**) Edit(~/notes/**) Bash(rm -rf ~/.cache/spec-spikes/*) Bash(mkdir -p ~/.cache/spec-spikes/*) Bash(git -C * archive *) Bash(tar -x -C ~/.cache/spec-spikes/*) Bash(cd ~/.cache/spec-spikes/*) Bash(cp ~/.claude/skills/spec/spike-settings.json ~/.cache/spec-spikes/*) Bash(claude -p --model sonnet --append-system-prompt-file ~/.claude/skills/spec/spiker.md *) Edit(~/.cache/spec-spikes/**)`. Probe 1's was `/spec`'s `allowed-tools` at `ac65fbd` plus the nine entries W2 listed before the spikes, which is how step 7's `mkdir -p ~/code/…` was approved by `Bash(mkdir -p ~/code/*)`.

```
a rm -rf X                                         -> allowed
b mkdir -p X/src                                   -> allowed
c git -C R archive <sha> | tar -x -C X/src         -> allowed
d rm -rf X && mkdir -p X/src                       -> allowed
f, g Write X/brief.md, X/spec.md                   -> allowed
h cp ~/.claude/skills/spec/spike-settings.json X/settings.json -> allowed
i Write ~/code/spike-probe-tmp/other.txt           -> allowed (by Edit(~/code/**))
j cd X && claude -p … < brief.md > run.json 2> run.err -> The following parts require approval: cd X, claude -p --model sonnet --append-system-prompt-file ~/.claude/skills/spec/spiker.md … --no-session-persistence
l cd X && claude -p … "Answer the spike in brief.md." > run2.json 2> run2.err -> the same two parts
```

### Probe 3: a launcher script ($0.10, 8 turns)

`allowed-tools` included `Bash(cd ~/.cache/spec-spikes/*)`, `Bash(claude -p --model sonnet --append-system-prompt-file ~/.claude/skills/spec/spiker.md *)` and `Bash(~/.claude/skills/spec/scripts/run-spike.sh ~/.cache/spec-spikes/*)`.

```
a cd X   -> cd in '/Users/…/.cache/spec-spikes/spike-probe-tmp/2026-09-17-probe/S1' was blocked. For security, Claude Code may only change directories to the allowed working directories for this session: '/Users/…/code/spike-probe-tmp'.
b claude -p --model sonnet --append-system-prompt-file ~/.claude/skills/spec/spiker.md --max-budget-usd 0.3 --max-turns 2 --output-format json --no-session-persistence "Reply with only: Verdict: EXPECTED"  -> allowed
c ~/.claude/skills/spec/scripts/run-spike.sh X  (run_in_background)  -> allowed
d wait for c's completion notification, Read X/run.json  -> allowed; the notification arrived
run.json: subtype success, total_cost_usd 0.1188726, num_turns 3, modelUsage claude-sonnet-5 and claude-haiku-4-5-20251001, result "Verdict: EXPECTED\nResults: results.md"
```

### Verdict

DIFFERENT: `cd` to the scratch dir is refused whatever the rules say, and `$(cat brief.md)` can't be pre-approved, so 7b's launch line can't be approved as written. What works:

- 7b step 1 as two calls: `rm -rf <scratch> && mkdir -p <scratch>/src`, then `git -C <source repo> archive <read-at> | tar -x -C <scratch>/src`.
- `Edit(~/.cache/spec-spikes/**)`, not `Write(...)`, for the Write calls in 7b (probe 2, steps f and g); `Edit(~/code/**)`, already in `allowed-tools`, covers the results file in 7c.
- The launch as `~/.claude/skills/spec/scripts/run-spike.sh <scratch>` in the background (`2c60e1a`), approved by `Bash(~/.claude/skills/spec/scripts/run-spike.sh ~/.cache/spec-spikes/*)`.

## S3: Does a nested `claude -p` misbehave under the parent's `CLAUDE*` variables?

Expect: it starts, with its own session.
Runs: 5 launches.

The launching sessions had `CLAUDECODE`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_ENTRYPOINT` and others set (`env | grep ^CLAUDE`). No launch used `env -u`.

```
parent session (interactive)               64ae43e9-e835-4444-a403-a90d3b7148b0
S1 run 2, launched from it                 f99b3b03-b17b-4bf8-9ffc-68d113d43b03  success
S1-budget, launched from it                7d67d1e9-0374-40c3-863a-4f2da36bd328  error_max_budget_usd
probe 3 skill session (headless)           ca9e1bbd-4c02-4773-b9c1-04dd724ea21f
  step b, launched from its Bash tool      59f0f81e-cb51-4d60-bd04-aa84b55ba2b1
  run-spike.sh, launched from its Bash tool a70af35c-6077-4f74-8675-0fc2ccb93048  success
```

### Verdict

EXPECTED: every nested session started and got its own `session_id`, from an interactive session and from a skill running in a headless one. No wrapper is needed, so allowed-tools needs no `env` entry. It wasn't run from an interactive `/spec` session, which W2 doesn't exist for yet.

## Cost

Spike 1: $1.54 (runs $0.51, $0.50, $0.27; budget $0.10; git $0.16). Spike 2: $0.54 (probe sessions $0.16, $0.16, $0.10; nested spiker $0.12; step b's reply not recorded). Spike 3: no extra runs.

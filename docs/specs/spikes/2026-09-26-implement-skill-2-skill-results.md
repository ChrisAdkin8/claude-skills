# Spike results: /implement, part 2: the skill that implements a reviewed spec test first, its evals and docs

## S1

### Can a skill eval run `/build`'s writes in its fixture?

Expect: a plain `git init` and commit are refused (writes inside `.git`), a write to a sibling of the working directory is refused, and a write under `~/.cache/build-runs` is refused, so the fallback is needed.
Runs: 1

#### Commands

```
mkdir -p src/probe && cd src/probe && git init
```

```
mkdir -p ../wt-probe   # sibling of the working directory S1
```

```
mkdir -p ~/.cache/build-runs
echo test > ~/.cache/build-runs/probe-test.txt
```

```
### brief's literal sequence, run from a fresh empty dir (git init already
### shown refused above, so there is no repo for `git worktree add` to act on)
mkdir -p src/probe2 && cd src/probe2 && \
  (git worktree add ../wt -b x && cd ../wt && touch f && git add f && git commit -m t)
```

#### Output

```
$ cd src/probe && git init
fatal: cannot copy '/Library/Developer/CommandLineTools/usr/share/git-core/templates/hooks/commit-msg.sample' to
'.../src/probe/.git/hooks/commit-msg.sample': Operation not permitted
EXIT:128
```

```
$ mkdir -p ../wt-probe
mkdir: ../wt-probe: Operation not permitted
EXIT:1
```

```
$ mkdir -p ~/.cache/build-runs
mkdir: ~/.cache/build-runs: Operation not permitted
EXIT_MKDIR:1
$ echo test > ~/.cache/build-runs/probe-test.txt
(eval): no such file or directory: ~/.cache/build-runs/probe-test.txt
EXIT_WRITE:1
```

```
$ (git worktree add ../wt -b x && cd ../wt && touch f && git add f && git commit -m t)
fatal: not a git repository (or any of the parent directories): .git
EXIT:128
```

#### Verdict

EXPECTED: all three writes are refused by the sandbox. `git init` fails while copying a hook template into `.git/hooks/` ("Operation not permitted"), `mkdir` of a directory sibling to the working directory fails the same way, and both `mkdir ~/.cache/build-runs` and a direct write into that path fail the same way. Because `git init` is refused before any repo exists, the brief's literal `git worktree add ../wt -b x && ...` sequence can't even start (`fatal: not a git repository`) — it fails one step earlier than the brief's chain implies, but for the same root cause (no writable `.git` to begin with). So a skill eval running under `hooks/agent-sandbox.json` cannot run `/build`'s writes as-is in its fixture; the `--no-sandbox` fallback (or an equivalent relaxation) is needed for W4/W6's Done-when commands and the Design's Worktree and Baseline paths.

#### Notes

None.


The spiker's `Write` of `results.md` was refused after it moved its working directory into `src/probe2`; this is the copy it left there, identical to the refused `Write` recorded in `run.json`'s `permission_denials`.

total_cost_usd: 0.28; num_turns: 12

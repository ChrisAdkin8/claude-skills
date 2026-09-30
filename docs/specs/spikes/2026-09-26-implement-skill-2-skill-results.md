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

## S2

### Can a skill invoke `/simplify` and `/code-review --fix` through the Skill tool in a headless `claude -p` session, and do they edit files there?

Expect: both run through the Skill tool and edit the working tree under `--permission-mode acceptEdits`.
Runs: 2 (`/simplify`, then `/code-review medium --fix`). Run by hand by the user on 2026-09-30, outside any sandbox, in a scratch repo, because a spike's sandbox has no network or credentials.

#### Commands

```
D=$(mktemp -d) && mkdir "$D/repo" && cd "$D/repo" && git init -q
printf 'def total(xs):\n    return sum(xs)\n' > calc.py
git add calc.py && git commit -qm base
printf '\ndef order_total(items):\n    result = 0\n    for x in items:\n        result = result + x\n    return result\n' >> calc.py
claude -p "Use the Skill tool to run simplify on the uncommitted change, and apply its fixes." \
  --permission-mode acceptEdits --max-budget-usd 1 --output-format json > "$D/simplify.json"
git diff
jq '{result, permission_denials, total_cost_usd}' "$D/simplify.json"
```

```
git commit -qam simplified
printf '\ndef average(xs):\n    return total(xs) / len(xs)\n' >> calc.py
claude -p "Use the Skill tool to run code-review with the arguments: medium --fix" \
  --permission-mode acceptEdits --max-budget-usd 1 --output-format json > "$D/review.json"
git diff
jq '{result, permission_denials, total_cost_usd}' "$D/review.json"
```

#### Output

`git diff` against the base commit: `order_total` became `return total(items)`, so the hand-written loop was replaced by a call to the existing helper. The reply said all four of `/simplify`'s review agents flagged the duplicate, and that a formatter hook from the user's settings added a blank line after the edit. `permission_denials` held one Bash call (`git diff HEAD; python3 -c "import calc; ..."`), refused because no Bash was pre-approved. `total_cost_usd`: 0.31.

`/code-review medium --fix`: `git diff` shows `average` now copies its input to a list and raises `ValueError("average() requires at least one value")` when it is empty, before dividing. The reply named the bug at `calc.py:9` (an empty list divides by zero; a generator is used up by `total` before `len`) and skipped a blank-line finding as layout. `permission_denials` held two Bash calls, both `python3 -c` checks of the fix, refused because no Bash was pre-approved. `total_cost_usd`: 0.36.

#### Verdict

EXPECTED.
`/simplify`: yes. The Skill tool ran it headless and its fix was applied by Edit under `acceptEdits`. Its own check run was refused, so the implementer's pre-approved tools must include the Bash commands the clean-up skills use, or their check runs are lost; the re-test after clean-up doesn't depend on them. The user's own hooks ran in the session, as they will with `--setting-sources user,project`.
`/code-review medium --fix`: yes. It ran headless through the Skill tool with its arguments, found the planted bug at `medium` and applied a fix by Edit; its own check runs were refused the same way.

---
name: implement
description: Implements a reviewed, committed spec test first. Checks the spec, makes a git worktree and branch, hands the work items to an implementer subagent in its own headless session there, then has the sandboxed implement-verifier re-run every Done when, and leaves the evidence in the spec's record on the branch. Runs when the user types /implement.
disable-model-invocation: true
argument-hint: <spec path>
allowed-tools: Read Grep Glob Edit(~/.cache/implement-runs/**) Edit(~/.cache/implement-verify/**) Edit(~/code/**/*-worktrees/*/docs/specs/**)
  Bash(git -C * status *) Bash(git -C * worktree add *) Bash(git -C * add *) Bash(git -C * commit *) Bash(git -C * revert *)
  Bash(${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py *) Bash(${CLAUDE_PLUGIN_ROOT}/skills/spec/scripts/check-spec.py *) Bash(${CLAUDE_PLUGIN_ROOT}/skills/cold-review/scripts/review-state.py --plan *) Bash(${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/run-implementer.sh *) Bash(${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/ledger.py report *)
  Bash(${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/prepare-verify.sh ~/.cache/implement-verify/*) Bash(${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/run-verify.sh ~/.cache/implement-verify/*)
---

# Implement a reviewed spec

Request: $ARGUMENTS

You frame, relay and verify; you don't write the code. The work items are done by the `implementer`, a headless session of its own that has seen none of this conversation, working in a git worktree on its own branch. Its steps are in `${CLAUDE_PLUGIN_ROOT}/hooks/agents/implementer.md`, and the verifier's in `${CLAUDE_PLUGIN_ROOT}/skills/implement/verifier.md`: don't restate either in a brief. Never commit on the user's branch, push, or open a pull request.

**Progress.** Copy this checklist into your reply at the end of every turn that ends while a run is going, ticked to date, and once more in the final report. When a run returns, carry on from the first unticked line.

```
- [ ] Frame: names, new or resume
- [ ] Gate passed
- [ ] Worktree ready, first commit made
- [ ] Implementer launched; questions relayed; Implementer: done
- [ ] Verifier V1 (and V2 if needed); CANNOT-RUN rows run by the implementer
- [ ] Evidence committed; worktree clean
- [ ] Report
```

**Tool calls.** `allowed-tools` pre-approves only the command shapes this file gives, so use them exactly:
- In every Bash call, write paths under the home directory with `~` (`~/code/…`, `~/.cache/…`), not expanded. The exception is this plugin's own files: `${CLAUDE_PLUGIN_ROOT}` is already expanded to an absolute path where this file gives it, so write that path exactly as you see it.
- Run one command per Bash call: a script directly, not through `python3` or `bash`, by the full path this file gives, never through a shell variable or after a `cd`, and never joined to another with `;`, `&&`, `||` or a pipe. Anything else isn't pre-approved, so it asks the user.
- Read git through `${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py -C <dir> …` (`rev-parse`, `log`, `show`, `branch --list`, `worktree list`). The only git commands that change anything are `git -C <dir> -c core.fsmonitor=false -c core.hooksPath=/dev/null worktree add …`, `add`, `commit` and `revert`. Keep both `-c` flags on every `git -C` command, `status` and `revert` included, though no step gives a `revert`: they stop a file watcher (`core.fsmonitor`) or a hook planted in the repo's git config from running in this session, as `git-read.py` does for reads.
- Read files with the Read tool and find them with Glob; make them with Write or Edit, never `ls`, `cp` or a redirect.
- In `~/code`, edit only the spec's status line and its record, and only in the worktree: `allowed-tools` pre-approves edits under a worktree's `docs/specs/` and nowhere else there, so a spec kept outside `docs/specs/` asks the user for each edit.
- If a call this skill needs is refused anyway, stop and tell the user which call was refused and why. Don't work around it with another command.

## 1. Frame

- `<spec>`: the path given; stop if there is none. `<repo>`: `git-read.py -C <spec's dir> rev-parse --show-toplevel`, which must be under `~/code` (else stop: `/implement` works only on repos there). `<repo dir>`: its directory name.
- `<basename>`: the spec's filename without `.md`. `<record>`: `<spec dir>/records/<basename>-record.md`. `<spikes>`: `<spec dir>/spikes/<basename>-results.md` (it may not exist). Paths below are from the repo root unless they start with `~`.
- `<worktree>`: `<repo>/../<repo dir>-worktrees/<basename>`, written with `~`. `<branch>`: `implement/<basename>`.
- `<run name>`: `<repo dir>--<basename>`. `<run dir>`: `~/.cache/implement-runs/<run name>/implementer`. `<baseline>`: `~/.cache/implement-runs/<run name>/scratch/baseline.txt`, in the one dir outside the worktree the implementer may write. `<scratch V<n>>`: `~/.cache/implement-verify/<repo dir>/<basename>/V<n>`.
- **New or resume.** `git-read.py -C <repo> branch --list <branch>`: empty means a new run; a branch means resume (step 3's Resume).

## 2. Gate

In order, from the repo's checkout, stopping at the first failure with what to do:

1. `git -C <repo> -c core.fsmonitor=false -c core.hooksPath=/dev/null status --porcelain -- <spec> <record> <spikes>` prints nothing, so all three are committed at HEAD. Else: "commit them, then run `/implement <spec>` again". Name any other uncommitted files in the checkout in one line and leave them alone: the worktree starts from HEAD.
2. The spec's frontmatter says `status: reviewed`.
3. `${CLAUDE_PLUGIN_ROOT}/skills/spec/scripts/check-spec.py <spec> --repo <repo>` prints `RESULT: PASS`.
4. `${CLAUDE_PLUGIN_ROOT}/skills/spec/scripts/check-spec.py <spec> --repo <repo> --drift-at HEAD` prints no `DRIFT:` line. Else: "run `/spec finish <spec>`, which re-reads those ranges and moves read-at, then commit it". Keep any file its drift WARN names, for step 3.
5. `${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/run-implementer.sh --check <run dir>` exits 0, with the `<run dir>` step 4 will launch with. It runs the launcher's refusals that don't need the worktree (the Claude Code version, the run dir's name, `IMPLEMENT_MAX_USD`, `IMPLEMENT_CALL_MAX_USD` and `IMPLEMENT_INTERRUPT_WAIT`, the spent cap, the macOS temp dir and the user's sandbox settings), writes nothing and launches nothing. Else: stop, and give the script's message as it printed it, so nothing is made or spent first.
6. `${CLAUDE_PLUGIN_ROOT}/skills/cold-review/scripts/review-state.py --plan <spec>`, by the `state:` it prints last. It counts only changes to the Decision, Design and Work items since the saved review (or its delta review), with citations' line numbers set aside, so a status change, a moved `read-at` or a re-cite doesn't count. Carry on for `full` (no saved review, which check 3 allows), `unchanged`, `done` and `delta` (check 3 already stops a reviewed spec with unreviewed lines). On `unlogged`, stop: "the spec's plan changed after its review and the change isn't logged: run `/cold-review <spec>`, which drafts the `Not reviewed:` lines for you to confirm". On `no-base`, where git has no history to compare with, as in a shallow clone, stop: "the gate can't see the spec's history: run `git fetch --unshallow`, then `/implement <spec>` again".

On resume, run the Gate in the worktree instead, where check 1 names only `<spec> <spikes>`: the implementer leaves lines in the record uncommitted (an evidence line for its next commit, the rest for step 6's), so a dirty record is expected there. The status must be `in-progress` and drift is checked with `--drift-at <the Started at commit>` (from the record's `## Evidence` on the branch), so the branch's own commits never count as drift.

## 3. Worktree

- **New:** `git -C <repo> -c core.fsmonitor=false -c core.hooksPath=/dev/null worktree add <worktree> -b <branch>`. Then, in the worktree only: set the spec's `status: in-progress`, and add a `## Evidence` section to the record, between `## Spikes` and `## Implementation` as `${CLAUDE_PLUGIN_ROOT}/skills/spec/record-template.md` orders them (after the last section before them if those are missing), starting with `- Started at <short HEAD it branched from>` and, if step 2 kept any, `- Drift WARN, no DRIFT line: <files>`. `git -C <worktree> -c core.fsmonitor=false -c core.hooksPath=/dev/null add <spec> <record>`, then `git -C <worktree> -c core.fsmonitor=false -c core.hooksPath=/dev/null commit -m '<area>: <spec title> is in progress'`, the area as the repo's convention asks (its `CLAUDE.md` or recent `git log`), following this session's attribution rules.
- **Resume:** reuse `<worktree>`, or, if the directory is gone, `git -C <repo> -c core.fsmonitor=false -c core.hooksPath=/dev/null worktree add <worktree> <branch>` (no `-b`). Run the Gate there (step 2).

## 4. The implementer

1. **Brief.** With Write, write `<run dir>/brief.md`:

   ```
   Spec: <absolute path of the spec in the worktree>
   Record: <absolute path of the record in the worktree>
   Worktree: <absolute worktree path>
   Baseline: <absolute path of baseline.txt>
   Today's date: <YYYY-MM-DD>
   ```

   Add `Resume` on its own line on resume, and `Unattended` if the user said no one will answer questions.
2. **Launch** `${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/run-implementer.sh <worktree> <run dir>` with `run_in_background: true`. Tell the user in one line that the implementer is running, and end your turn.
3. **When it returns**, go by its exit code; for 0 and 3, read `<run dir>/reply.md`:
   - **0**, and the last line says:
     - `Implementer: done`: go to step 5.
     - `Implementer: question: <text>`: put it to the user with AskUserQuestion, recommended answer first. Write the answer to `<run dir>/followup.md` and run the same command with `--resume` added, in the background. Unattended, don't ask: stop and report the question.
     - `Implementer: stopped: <reason>`: stop and report the reason; don't verify.
   - **3**: the reply doesn't end with an `Implementer:` line. Send one follow-up asking it to reply again, in full, ending with that line. If that exits 3 too, stop and tell the user.
   - **2**: the run never started, or its cap is spent. Stop and give the script's message.
   - **4**: the run changed the repo's shared git config or hooks, a worktree's git pointers or the ledger, or left a submodule config that names a program. Stop at once: run no git command in the repo or the worktree, `git-read.py` included, read nothing the run wrote, and tell the user each path the script's message names, so they can check it before anything runs git there.
   - **5**: the run found no Claude account to use. Stop, send no follow-up (the session has no account to answer it), and give the user the script's account guidance as it printed it.
   - **6**: the call was interrupted (the task was stopped, or the session closed) and wrote no reply. Read nothing, `reply.md` included: stop, and tell the user the call was interrupted, what the script's message says it was charged, and that `/implement <spec>` carries on from the last committed work item.
   - **Any other**: stop; `run.err` and `run.json` in the run dir say why.

   On any exit, keep each `run-implementer: moved during the run: <ref> <old> -> <new>` line the script printed, for the report.

## 5. Verify

1. `${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/prepare-verify.sh <scratch V1> <worktree> <Started at> <the branch's HEAD>`.
2. With Read and Write, copy the worktree's spec to `<scratch V1>/spec.md` and its record to `<scratch V1>/record.md`, and write `<scratch V1>/brief.md`: `Spec: spec.md, a copy of <spec, from the repo root>`, `Record: record.md, a copy of <record, from the repo root>`, `Work items: <every Wn under the spec's ## Work items>`, `Today's date: <YYYY-MM-DD>`. The two paths let the verifier tell the spec's status edit and the record's evidence in the diffs, which it expects. List every work item, with a commit or not: the verifier fails one with no commit of its own, so a skipped work item can't pass unchecked. Nothing about how the work went: this brief comes from a session that didn't write the code.
3. Run `${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/run-verify.sh <scratch V1>` with `run_in_background: true`, and end your turn. When it returns, go by its exit code before you read anything:
   - **0**: read `<scratch V1>/reply.md`.
   - **4**: the run left a link, or something else that isn't a plain file, where its output goes, which the Read tool would follow out of the scratch directory; or it changed an input the verifier reads (the spec, the record, a diff), so its verdict may rest on something you didn't write. Read none of its files, `run.json` included, so its cost is unknown. Under the record's `## Evidence` in the worktree, add `- Verifier V1 (<head commit>): refused: <the script's message>`, use nothing from its reply, go on to step 6 (Evidence and report), and say in the report that the implementation wasn't verified.
   - **5**: the run found no Claude account to use. Stop, and give the user the script's account guidance as it printed it.
   - **2, 3 or any other**: stop and tell the user, as step 4 does.
4. **Copy its reply**, the table, the `Other commits:` line and the closing lines, under the record's `## Evidence` in the worktree, headed `- Verifier V1 (<head commit>):`.
5. **CANNOT-RUN rows.** If any, write a follow-up listing each (its Done when and the verifier's reason) to `<run dir>/followup.md`, and resume the implementer. It runs them in the worktree and adds `implementer-run:` lines, apart from the table.
6. **`Implementation holds: no`.** If a row failed or doesn't match the spec, or the `Other commits:` line names a weakened test, send the implementer a follow-up naming each, resume it, then verify once more in `<scratch V2>`, steps 1 to 5 again. For a work item with no commit, the follow-up says: "W<n> has no commit ending (W<n>). Do it now as your step 2 does, in a commit of its own, not as a fix after verification", since only a `(W<n>)` commit gives the next verifier that item's own diff. If the only cause is a work item whose every row is CANNOT-RUN, send no follow-up and run no V2: there is nothing to fix, and a second verifier couldn't run those checks either. There is no third round: if V2 also says `no`, say so in the report.

## 6. Evidence and report

1. `git -C <worktree> -c core.fsmonitor=false -c core.hooksPath=/dev/null add <record>`, then `git -C <worktree> -c core.fsmonitor=false -c core.hooksPath=/dev/null commit -m '<area>: implementation evidence'`: the branch's last commit. The verifier ran on the commit before it, which changes only the record. `git -C <worktree> -c core.fsmonitor=false -c core.hooksPath=/dev/null status --porcelain` must then print nothing; if it doesn't, name what's left.
2. **Report**, one short line each: each work item, its commit and Done when result, and, for one no verifier row passed, that only the implementer checked it (`implementer-run:`) or no one did; the clean-up commits and any revert; the verifier's `Verified` and `Implementation holds` lines, per round, or that a round was refused and why; any departure or question and its answer; each `moved during the run:` line, for the user to confirm they made that change themselves (their own commit or fetch) and not the implementer; the cost of every run, from `${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/ledger.py report <run name>`, whose lines you copy: each implementer call's cost and where it comes from, each verifier run's, the implementer total that counts against the cap, and the total of all runs of this spec, earlier ones included. Don't add up the ledger's lines yourself. Then: "run `/spec done <absolute path of the spec in the worktree>` here, in this session". Don't push, merge or remove the worktree.

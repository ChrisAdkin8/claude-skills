---
name: research
description: Research a question, challenge or idea and write the findings to a cited markdown note in ~/notes/research. Use when the user runs /research, or asks to research, investigate or dig into something and document it. Accepts a prompt or the path to an existing idea note; "quick" for a short answer; "ideas" for a ranked shortlist of things to build or write; "finish <note>" to verify and commit an existing note.
argument-hint: [quick | ideas] <question or path to an idea note> | finish <path to research note> ["claim to check" ...]
allowed-tools: Read Edit(~/notes/**) Bash(grep *) Bash(git -C ~/notes status *) Bash(~/.claude/hooks/git-read.py *) Bash(git -C ~/notes add *) Bash(git -C ~/notes commit *) Bash(~/.claude/skills/research/scripts/check-note.py *) Bash(~/.claude/hooks/run-agent.sh *) Edit(~/.cache/agent-runs/**)
---

# Research and document

Request: $ARGUMENTS

The work happens in background agents so the user can keep working:

1. **Frame** (here, under a minute): settle the question, depth and output path.
2. **Research**: the `researcher` agent writes the note and self-checks it with `check-note.py`.
3. **Verify**: the `research-verifier` agent, which has not seen the research, checks the claims the recommendation rests on against their sources.
4. **Finish** (here): apply the verifier's fixes, record what was checked in the note, re-verify once if the conclusion changed, set the status, link the idea, commit. At `ideas` depth, also merge the new attention data into the shared evidence note and file the top three ideas as idea notes.

Every commit in `~/notes` names its files after `--` (`git -C ~/notes commit -m '<message>' -- <files>`): another `/research`, `/spec` or `/idea` session may have staged files of its own, and a commit without paths takes the whole index. If git says `index.lock` exists, another session is committing: retry once.

Run `git log`, `git diff` and any other read-only git command except `git -C ~/notes status` through `~/.claude/hooks/git-read.py`, which `allowed-tools` pre-approves: it refuses the options that write files (`--output`) or run programs (`-c`), which a pre-approved `git log *` would let through.

The research rules live in `~/.claude/agents/researcher.md` and the checking rules in `~/.claude/agents/research-verifier.md`. Don't restate them in briefs; edit those files to change them.

## Running an agent

The researcher and the verifier don't run as in-session subagents. Each runs as a headless, sandboxed session through `~/.claude/hooks/run-agent.sh`, since Claude Code can't sandbox a subagent on its own, and these agents read untrusted pages (the script's header says what the sandbox holds). To run one:

1. With the Write tool, write its brief to `<run dir>/brief.md`, where `<run dir>` is `~/.cache/agent-runs/<note basename>/<agent>`, e.g. `~/.cache/agent-runs/2026-09-25-x/researcher`. A later round of the same agent on the same note gets `<agent>-2`, `<agent>-3`; `finish` mode uses `research-verifier-finish`.
2. Run `~/.claude/hooks/run-agent.sh <agent> ~/notes <run dir>` with the Bash tool and `run_in_background: true`, paths written with `~`.
3. When it finishes, read `<run dir>/reply.md` with the Read tool: that is the agent's reply. Exit 3 means the run finished but the reply lacks the closing lines its agent file asks for: an API error such as "Request timed out", a budget stop, or a reply out of format. Send one follow-up (`--resume`) asking it to reply again, in full, in the format its instructions give; if that exits 3 too, tell the user and don't act on the reply. Any other non-zero exit means no reply: `run.err` and `run.json` there say why.

To send an agent a follow-up in the same session, Write `<run dir>/followup.md` and run the same command with `--resume` added. Its new reply replaces `reply.md`, and the earlier one is kept as `reply-<n>.md`.

## Modes

- `/research <question or idea path>`: full depth, unless the question is narrow and factual (a limit, a version, a price, how one feature behaves) with no decision to make; then quick. If it asks for ideas, candidates, what to build or write, or a ranking of things to do, use ideas depth, and say in the framing line that you chose it so the user can redirect.
- `/research quick <question>`: quick depth. Bottom line, a one-line The question, Findings and Sources, 600 words at most.
- `/research ideas <question or idea path>`: ideas depth. A pool of at least 20 candidates across six lenses, narrowed to a ranked shortlist of 5–7 with a rubric; the verifier hunts for prior art on the top two; the top three are filed as idea notes. 2,400 words at most, with the pool after Sources and outside the budget.
- `/research finish <research note path> ["claim" ...]`: skip to verification. Use it when a session ended before a note was verified, after editing a note by hand, or when `/spec` flags a borrowed claim as unverified (pass that claim's wording).

## 1. Frame (in the conversation)

1. **Resolve the question.**
   - A path to a note in `~/notes/ideas/`: read it. The idea is the subject; research it as a whole.
   - Empty request: use the question just discussed. If there is none, ask for it in one line and stop.
   - If the question is ambiguous in a way that would change the research (which cloud, what scale, which constraint matters most), ask **one** question with AskUserQuestion. Otherwise don't ask; list your assumptions in the brief.
2. **Check for existing work**: `grep -ril '<key terms>' ~/notes/research ~/notes/ideas`. If a research note already covers it, ask whether to update that note or write a new one.
3. **Ranking and lenses** (ideas depth only). Rank by "likely mindshare" unless the request names another criterion. Mindshare means traffic and engagement: stars, shares, Hacker News, Reddit and LinkedIn traction, talks, demos people pass around. Novelty counts for more than usefulness to clients. The lenses are finding, tool, dataset, game, lab and essay; drop only the ones the question plainly rules out.
4. **Repo context**: if the working directory is inside a git repo under `~/code`, note its path. The researcher reads the relevant files itself; don't read them now.
5. **Output path**: `~/notes/research/YYYY-MM-DD-short-slug.md` (today's date, 3–6 word lowercase hyphenated slug), or the existing note if updating.
6. **Launch.** First run `git -C ~/notes status --porcelain` and keep its output, so that section 2 can tell the researcher's changes from ones that were already there. Then run the `researcher` agent (Running an agent) with this brief, filled in. Leave out the `Rank by` and `Lenses` lines except at ideas depth.

   ```
   Depth: <full | quick | ideas>
   Question: <restated question, precise>
   Rank by: <the ranking criterion, spelled out>
   Lenses: <finding, tool, dataset, game, lab, essay, or the subset in scope>
   A good answer must cover: <2–4 success criteria>
   Assumptions: <assumptions made in framing, or "none">
   Output file: <absolute path> (<create it | update the existing note: keep its structure, refresh facts, and add a dated "Updated" line under Bottom line>)
   Idea note: <absolute path, or "none">
   Repo in scope: <absolute path, or "none">
   Related notes: <absolute paths found in ~/notes, or "none">
   Today's date: <YYYY-MM-DD>
   ```

7. Tell the user in one or two lines: the restated question, the depth (so they can redirect it), the ranking criterion at ideas depth, and where the note will land. End your turn.

## 2. When the researcher finishes

1. Run `~/.claude/skills/research/scripts/check-note.py --headroom <note>`. `--headroom` applies the researcher's lower budget, which leaves room for the verifier's fixes. If the agent failed, or the note is missing or has no Sources, tell the user what happened and stop; don't commit. Then run `git -C ~/notes status --porcelain`: the researcher may write only its note, so any other changed file under `~/notes/research` that wasn't in the output kept at launch is a red flag. So is any change to `~/notes/projects/mindshare/attention-evidence.md` or `~/notes/ideas/`: only the Finish step edits those, never the researcher. Two cases aren't: a note that is another `/research` run's output (`grep -l 'Output file: <its absolute path>' ~/.cache/agent-runs/*/researcher*/brief.md` finds that run's brief, in a run dir other than this one), which that run commits; and an edit the user made while this ran, which they'll recognise. So for each flagged file, check the first, then show the user the diff and ask. Either way, don't commit it.
2. If the result is FAIL, send the FAIL lines to the researcher as a follow-up (Running an agent) and ask it to fix them and re-run the check. Allow two rounds; if it still fails, carry on to verification and report the remaining failures at the end.
3. Run the `research-verifier` agent (Running an agent) with the brief `Note: <absolute path>. Today's date: <YYYY-MM-DD>.`, adding `Depth: ideas: run the prior-art hunt first.` at ideas depth. Tell the user in one line that the note is written and being verified. End your turn.

In `finish` mode, start here:

1. Run the check without `--headroom` (the note already exists, so its hard limit applies). Fix any FAIL lines yourself. On a length FAIL, cut unverified points only, as step 4 of section 3 says; a WARN for being up to 10 % over after verification is left as is. Leave alone Verification rows the check says no longer match the note: those are claims edited since they were checked, so leave them for the verifier.
2. Collect the claims to name in the brief:
   - any claims passed as arguments;
   - claims the check reports as no longer matching;
   - claims changed since the last verification: find the last `research:` commit that touched the note (`~/.claude/hooks/git-read.py -C ~/notes log --format='%h %s' -- <note>`), then `~/.claude/hooks/git-read.py -C ~/notes diff <that commit> -- <note>` shows every edit since, committed or not. If the note has never been committed (a session ended before its first verification), skip this: the verifier checks it as a new note.
3. Run the verifier (Running an agent, in the run dir `research-verifier-finish`) with the brief above, plus `Also check: "<claim>"; "<claim>"` if there are any.

A note verified before the `## Verification` section existed gets one from this run.

## 3. When the verifier finishes

At ideas depth, first check the reply has a `Prior art:` block listing the queries it ran for #1 and #2, and Novelty rows for both in its table. At full depth, if the Bottom line or Recommendation rests on a claim of absence, check the reply has a `Prior art:` block for that claim and a row for it. If either is missing, send it back once as a follow-up: "Your reply has no Prior-art hunt. Run it as your instructions describe, every query against every venue, and reply again in full." If the second reply still lacks it, carry on and say in the report that novelty wasn't independently checked.

1. **Apply its fixes** to the note:
   - WRONG: replace the figure or statement with the corrected one and update or add the source.
   - MISCITED: cite the source the verifier found (add it to Sources).
   - UNSUPPORTED or UNREACHABLE: mark the claim *(unverified)*, or soften it to what the sources do say.
   - Other problems: fix dangling citations. Add missed evidence (prior art, a feature that already exists) to Findings or Counter-evidence with its source, and adjust the wording it contradicts.
   - Novelty rows and the `Prior art:` block (ideas depth): add every `same` and `overlaps` hit to Findings → Prior art with its source. For a WRONG Novelty row, narrow that Novelty cell, and the Bottom line and Recommendation if they repeat it, to what is still new. Cut or narrow any pool line a hit makes redundant.
2. **Record the verification.** Add a `## Verification` section after Sources, so it doesn't count toward the word budget. This is the only record of which claims were checked; `/spec` and its verifier read it to tell checked claims from unchecked ones.

   ```
   ## Verification

   Checked on <YYYY-MM-DD> by research-verifier: <N> of <M> claims confirmed, a sample of the note's <K> cited claims.

   | Claim | Cited | Verdict | Resolution |
   |---|---|---|---|
   | <the claim's wording as it now reads in the note> | [4] | CONFIRMED | |
   | <…> | [7] | WRONG | corrected to <value>, cited [12] |
   | <…> | [9] | UNREACHABLE | marked *(unverified)*: <why, e.g. GCP page renders with JavaScript> |
   ```

   Record every row the verifier returned, corrected ones included; don't drop any. `<N>` and `<M>` are the table's own counts: its CONFIRMED rows and all its rows. `<K>` is the note's count of cited claims, which `check-note.py` gives when it warns; leave the clause out only if the table covers them all. It says in the note itself that `final` means a sample held, not every claim. `check-note.py` compares the counts, so put round details, or the verifier's own count where it differs, after them, e.g. "16 of 21 claims confirmed across both rounds' rows. Round 1: 15 of 18 …".

   Every row that isn't CONFIRMED needs a Resolution: corrected, re-cited, or marked *(unverified)*, which the check confirms is in the text. If the section already exists (from `finish` mode or round 2), update the rows for claims checked again, add new ones, delete rows for claims the note no longer makes, and update the date line. A row's Claim must quote the note's current wording, or the check fails it as stale.
3. **If the conclusion changed**, the rewritten text is the least-checked part of the note, so it gets one more check:
   - This applies on `Bottom line holds: no`, or when missed evidence weakens the recommendation. At ideas depth that includes a `same` prior-art hit on the #1 idea: re-rank the Shortlist, and if a different idea moves to #1, round 2 hunts prior art for it. Revise the Bottom line and Recommendation to match the evidence, set `status: draft`, and commit with the message `research: <title> (conclusion revised, re-verifying)`.
   - Run `research-verifier` again, in the run dir `research-verifier-2`, with `Note: <absolute path>. Today's date: <YYYY-MM-DD>. Round 2.` Tell the user in one line that the conclusion changed and is being re-checked. End your turn.
   - When round 2 returns, apply its fixes and update Verification as above, then carry on from step 4. If round 2 also says `Bottom line holds: no`, leave the note as draft and say so in the report, with one exception.
   - **Round 3, for one narrowed absence claim.** If round 2's `no` rests only on an absence claim ("no tool does X", "nothing found") that it narrowed again, apply its narrowing and run `research-verifier`, in `research-verifier-3`, with `Note: <absolute path>. Today's date: <YYYY-MM-DD>. Round 3: check only "<the narrowed sentence>".` It replies with one row and the usual closing lines. If the row is CONFIRMED and it says `Bottom line holds: yes`, carry on from step 4. If not, leave the note as draft and name the sentence in the report. There is no round 4.
4. Re-run `check-note.py`. Once the note has a Verification table, the check allows up to 10 % over the limit with a WARN; leave that as is. Cut only on a FAIL, and then cut whole unverified points from Findings or Options. Never cut a sentence a Verification row quotes, a Project health row, the Bottom line, Recommendation or Counter-evidence, nor Shortlist rows or cells.
5. **Status**: set `status: final` when all of these hold:
   - the check passes;
   - the latest verifier says `Bottom line holds: yes`;
   - every Verification row is CONFIRMED or resolved: corrected, re-cited, or marked *(unverified)* in the note's text.

   A claim that can't be verified (a JavaScript-only pricing page, a login wall) doesn't hold a note in draft forever, as long as it's visibly marked and the Bottom line doesn't stand on it. Otherwise set `status: draft` (in `finish` mode the note may have been `final`); the report says why.
6. **Link the idea**, if there was one: in the idea note, set `status: exploring` and add the research note's path to `related`. If the Bottom line recommends against the idea, don't go further: say so in the report and suggest `parked` or `dropped`. That call is the user's.
7. **Ideas depth only**: read `~/.claude/skills/research/ideas-finish.md` and follow it. It merges the new attention data into the shared evidence note and files the top three ideas as idea notes.
8. **Commit** only the files you created or changed in `~/notes` (the research note, the idea note if edited and, at ideas depth, the evidence note and the idea notes filed in step 7): `git -C ~/notes add <files>`, then `git -C ~/notes commit -m 'research: <title>' -- <files>`, following this session's commit attribution rules. Don't push.
9. **Report** in five lines or fewer (six at ideas depth):
   - the note path;
   - the bottom line in two sentences;
   - verification, e.g. `9 of 10 claims confirmed (a sample of 31 cited), 1 corrected, 1 left unverified`, and whether the conclusion changed;
   - the status and, if draft, why;
   - the commit hash;
   - at ideas depth: the pool size and lenses covered, the prior-art verdict on #1 and #2, and the idea notes filed.

   If the recommendation is to change a repo, add a line: the next step is `/spec <note>`, run from that repo (see `~/.claude/skills/spec/SKILL.md`). If the Recommendation is conditional or the options are close, suggest recording the choice in `~/notes/decisions/` first.

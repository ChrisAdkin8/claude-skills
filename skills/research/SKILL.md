---
name: research
description: Research a question, challenge or idea and write the findings to a cited markdown note in ~/notes/research. Use when the user runs /research, or asks to research, investigate or dig into something and document it. Accepts a prompt or the path to an existing idea note; "quick" for a short answer; "finish <note>" to verify and commit an existing note.
argument-hint: [quick] <question or path to an idea note> | finish <path to research note> ["claim to check" ...]
allowed-tools: Read Edit(~/notes/**) Bash(grep *) Bash(git -C ~/notes status *) Bash(git -C ~/notes log *) Bash(git -C ~/notes diff *) Bash(git -C ~/notes add *) Bash(git -C ~/notes commit *) Bash(~/.claude/skills/research/scripts/check-note.py *)
---

# Research and document

Request: $ARGUMENTS

The work happens in background agents so the user can keep working:

1. **Frame** (here, under a minute): settle the question, depth and output path.
2. **Research**: the `researcher` agent writes the note and self-checks it with `check-note.py`.
3. **Verify**: the `research-verifier` agent, which has not seen the research, checks the claims the recommendation rests on against their sources.
4. **Finish** (here): apply the verifier's fixes, record what was checked in the note, re-verify once if the conclusion changed, set the status, link the idea, commit.

The research rules live in `~/.claude/agents/researcher.md` and the checking rules in `~/.claude/agents/research-verifier.md`. Don't restate them in briefs; edit those files to change them.

## Modes

- `/research <question or idea path>`: full depth, unless the question is narrow and factual (a limit, a version, a price, how one feature behaves) with no decision to make; then quick.
- `/research quick <question>`: quick depth. Bottom line, a one-line The question, Findings and Sources, 600 words at most.
- `/research finish <research note path> ["claim" ...]`: skip to verification. Use it when a session ended before a note was verified, after editing a note by hand, or when `/spec` flags a borrowed claim as unverified (pass that claim's wording).

## 1. Frame (in the conversation)

1. **Resolve the question.**
   - A path to a note in `~/notes/ideas/`: read it. The idea is the subject; research it as a whole.
   - Empty request: use the question just discussed. If there is none, ask for it in one line and stop.
   - If the question is ambiguous in a way that would change the research (which cloud, what scale, which constraint matters most), ask **one** question with AskUserQuestion. Otherwise don't ask; list your assumptions in the brief.
2. **Check for existing work**: `grep -ril '<key terms>' ~/notes/research ~/notes/ideas`. If a research note already covers it, ask whether to update that note or write a new one.
3. **Repo context**: if the working directory is inside a git repo under `~/code`, note its path. The researcher reads the relevant files itself; don't read them now.
4. **Output path**: `~/notes/research/YYYY-MM-DD-short-slug.md` (today's date, 3–6 word lowercase hyphenated slug), or the existing note if updating.
5. **Launch** the Agent tool with `subagent_type: researcher` and this brief, filled in:

   ```
   Depth: <full | quick>
   Question: <restated question, precise>
   A good answer must cover: <2–4 success criteria>
   Assumptions: <assumptions made in framing, or "none">
   Output file: <absolute path> (<create it | update the existing note: keep its structure, refresh facts, and add a dated "Updated" line under Bottom line>)
   Idea note: <absolute path, or "none">
   Repo in scope: <absolute path, or "none">
   Related notes: <absolute paths found in ~/notes, or "none">
   Today's date: <YYYY-MM-DD>
   ```

6. Tell the user in one or two lines: the restated question, the depth (so they can redirect it), and where the note will land. End your turn.

## 2. When the researcher finishes

1. Run `~/.claude/skills/research/scripts/check-note.py --headroom <note>`. `--headroom` applies the researcher's lower budget, which leaves room for the verifier's fixes. If the agent failed, or the note is missing or has no Sources, tell the user what happened and stop; don't commit. Then run `git -C ~/notes status --porcelain`: the researcher may write only its note, so any other changed file under `~/notes/research` is a red flag. Don't commit it; show the user the diff and say which file.
2. If the result is FAIL, send the FAIL lines to the researcher with SendMessage (load it with ToolSearch if needed) and ask it to fix them and re-run the check. Allow two rounds; if it still fails, carry on to verification and report the remaining failures at the end.
3. Launch the Agent tool with `subagent_type: research-verifier` and the brief `Note: <absolute path>. Today's date: <YYYY-MM-DD>.` Tell the user in one line that the note is written and being verified. End your turn.

In `finish` mode, start here:

1. Run the check without `--headroom` (the note already exists, so its hard limit applies). Fix any FAIL lines yourself (cutting, not summarising, if over budget), except Verification rows the check says no longer match the note: those are claims edited since they were checked, so leave them for the verifier.
2. Collect the claims to name in the brief:
   - any claims passed as arguments;
   - claims the check reports as no longer matching;
   - claims changed since the last verification: find the last `research:` commit that touched the note (`git -C ~/notes log --format='%h %s' -- <note>`), then `git -C ~/notes diff <that commit> -- <note>` shows every edit since, committed or not. If the note has never been committed (a session ended before its first verification), skip this: the verifier checks it as a new note.
3. Launch the verifier with the brief above, plus `Also check: "<claim>"; "<claim>"` if there are any.

A note verified before the `## Verification` section existed gets one from this run.

## 3. When the verifier finishes

1. **Apply its fixes** to the note:
   - WRONG: replace the figure or statement with the corrected one and update or add the source.
   - MISCITED: cite the source the verifier found (add it to Sources).
   - UNSUPPORTED or UNREACHABLE: mark the claim *(unverified)*, or soften it to what the sources do say.
   - Other problems: fix dangling citations. Add missed evidence (prior art, a feature that already exists) to Findings or Counter-evidence with its source, and adjust the wording it contradicts.
2. **Record the verification.** Add a `## Verification` section after Sources, so it doesn't count toward the word budget. This is the only record of which claims were checked; `/spec` and its verifier read it to tell checked claims from unchecked ones.

   ```
   ## Verification

   Checked on <YYYY-MM-DD> by research-verifier: <N> of <M> claims confirmed.

   | Claim | Cited | Verdict | Resolution |
   |---|---|---|---|
   | <the claim's wording as it now reads in the note> | [4] | CONFIRMED | |
   | <…> | [7] | WRONG | corrected to <value>, cited [12] |
   | <…> | [9] | UNREACHABLE | marked *(unverified)*: <why, e.g. GCP page renders with JavaScript> |
   ```

   Every row that isn't CONFIRMED needs a Resolution: corrected, re-cited, or marked *(unverified)*, which the check confirms is in the text. If the section already exists (from `finish` mode or round 2), update the rows for claims checked again, add new ones, delete rows for claims the note no longer makes, and update the date line. A row's Claim must quote the note's current wording, or the check fails it as stale.
3. **If the conclusion changed**, the rewritten text is the least-checked part of the note, so it gets one more check:
   - This applies on `Bottom line holds: no`, or when missed evidence weakens the recommendation. Revise the Bottom line and Recommendation to match the evidence, set `status: draft`, and commit with the message `research: <title> (conclusion revised, re-verifying)`.
   - Launch `research-verifier` again with `Note: <absolute path>. Today's date: <YYYY-MM-DD>. Round 2.` Tell the user in one line that the conclusion changed and is being re-checked. End your turn.
   - When round 2 returns, apply its fixes and update Verification as above, then carry on from step 4. There is no round 3: if round 2 also says `Bottom line holds: no`, leave the note as draft and say so in the report.
4. Re-run `check-note.py`. If adding sources or evidence took it over the word limit, cut whole points from Findings or Options, never from the Bottom line, Recommendation or Counter-evidence.
5. **Status**: set `status: final` when all of these hold:
   - the check passes;
   - the latest verifier says `Bottom line holds: yes`;
   - every Verification row is CONFIRMED or resolved: corrected, re-cited, or marked *(unverified)* in the note's text.

   A claim that can't be verified (a JavaScript-only pricing page, a login wall) doesn't hold a note in draft forever, as long as it's visibly marked and the Bottom line doesn't stand on it. Otherwise set `status: draft` (in `finish` mode the note may have been `final`); the report says why.
6. **Link the idea**, if there was one: in the idea note, set `status: exploring` and add the research note's path to `related`. If the Bottom line recommends against the idea, don't go further: say so in the report and suggest `parked` or `dropped`. That call is the user's.
7. **Commit** only the files you created or changed in `~/notes` (the research note, and the idea note if edited): `git -C ~/notes add <files>`, then `git -C ~/notes commit` with message `research: <title>`, following this session's commit attribution rules. Don't push.
8. **Report** in five lines or fewer:
   - the note path;
   - the bottom line in two sentences;
   - verification, e.g. `9 of 10 claims confirmed, 1 corrected, 1 left unverified`, and whether the conclusion changed;
   - the status and, if draft, why;
   - the commit hash.

   If the recommendation is to change a repo, add a line: the next step is `/spec <note>`, run from that repo (see `~/.claude/skills/spec/SKILL.md`). If the Recommendation is conditional or the options are close, suggest recording the choice in `~/notes/decisions/` first.

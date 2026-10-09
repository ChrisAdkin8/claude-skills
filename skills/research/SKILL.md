---
name: research
description: Researches a question or idea and writes a cited markdown note to ~/notes/research, which an independent agent then verifies. Runs when the user types /research.
disable-model-invocation: true
argument-hint: '[quick | ideas] <question or path to an idea note> | finish <path to research note> ["claim to check" ...]'
allowed-tools: Read Edit(~/notes/**) Bash(grep *) Bash(git -C ~/notes status *) Bash(${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py *) Bash(git -C ~/notes add *) Bash(git -C ~/notes commit *) Bash(${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/check-note.py *) Bash(${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/build-index.py *) Bash(${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.sh *) Edit(~/.cache/agent-runs/**)
---

# Research and document

Request: $ARGUMENTS

**Progress.** Copy this checklist into your reply at the end of every turn that ends while an agent runs, ticked to date, and once more in the final report. When the agent returns, carry on from the first unticked line.

```
- [ ] Frame: question, depth and output path settled; researcher launched
- [ ] Researcher: note written, check-note.py passes or its FAIL lines sent back
- [ ] Verifier: fixes applied, Verification recorded, round 2 or 3 if the conclusion changed
- [ ] Status set, idea linked, ideas-finish.md done at ideas depth
- [ ] Index rebuilt, notes committed
- [ ] Report
```

Every commit in `~/notes` names its files after `--`: `git -C ~/notes commit -m '<message>' -- <files>`. If git says `index.lock` exists, retry once.

Run `git log`, `git diff` and every other read-only git command except `git -C ~/notes status` through `${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py`. Run one command per Bash call, with each script's full path written out: a shell variable, a `cd` or a second command in the call isn't pre-approved, so it asks the user.

The research rules are in `${CLAUDE_PLUGIN_ROOT}/hooks/agents/researcher.md` and the checking rules in `${CLAUDE_PLUGIN_ROOT}/hooks/agents/research-verifier.md`. Don't restate them in briefs.

## Agent runs

Each agent runs as a headless, sandboxed session: read `${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.md` and follow it. The work dir is `~/notes`; the run dir is `~/.cache/agent-runs/<note basename>/<agent>`.

## Modes

- `/research <question or idea path>`: full depth; quick for a narrow factual question (a limit, a version, a price, how one feature behaves) with no decision to make; ideas if it asks for ideas, what to build or write, or a ranking, saying in the framing line that you chose it.
- `/research quick <question>`: Bottom line, a one-line The question, Findings and Sources, 600 words at most.
- `/research ideas <question or idea path>`: a ranked shortlist from a pool of candidates, the top three filed as idea notes. 2,400 words at most, with the pool after Sources and outside the budget.
- `/research finish <research note path> ["claim" ...]`: skip to verification: after a session ended early, after a hand edit, or when `/spec` flags a borrowed claim (pass its wording).

## 1. Frame

If `git -C ~/notes status` fails or `~/notes` lacks `CLAUDE.md`, `templates/research.md` or, at ideas depth, `templates/research-ideas.md`, `templates/idea.md` or `projects/mindshare/attention-evidence.md`, name what's missing, point to "Set up `~/notes`" in `${CLAUDE_PLUGIN_ROOT}/README.md`, and stop. Don't create any.

1. **Resolve the question.**
   - An idea note's path: read it, and research the idea as a whole. No request: the question just discussed, or ask in one line and stop.
   - If an ambiguity would change the research (which cloud, what scale), ask **one** question with AskUserQuestion; otherwise list assumptions in the brief.
2. **Existing work**: `grep -ril '<key terms>' ~/notes/research ~/notes/ideas`. If a note already covers it, ask whether to update it or write a new one.
3. **Ranking and lenses** (ideas depth only). Rank by "likely mindshare" (stars, shares, Hacker News, Reddit and LinkedIn traction, talks, demos) unless the request names another criterion; novelty counts for more than usefulness to clients. Lenses: finding, tool, dataset, game, lab and essay, less any the question rules out.
4. **Repo context**: if the working directory is in a git repo under `~/code`, note its path; don't read its files.
5. **Output path**: `~/notes/research/YYYY-MM-DD-short-slug.md` (today's date, 3–6 word lowercase hyphenated slug), or the existing note if updating.
6. **Launch.** Run `git -C ~/notes status --porcelain --untracked-files=all` and keep its output. Then run the `researcher` agent (Agent runs) with this brief. Leave out `Rank by` and `Lenses` except at ideas depth.

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

7. Tell the user in one or two lines the question, the depth, any ranking criterion and the note's path. End your turn.

## 2. When the researcher finishes

1. Run `${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/check-note.py --headroom <note>`. If the agent failed, or the note is missing or has no Sources, tell the user and stop; don't commit.
   - Run `git -C ~/notes status --porcelain --untracked-files=all`: it lists every new file, where plain `--porcelain` shows a new directory as one line. The researcher may write only its note: flag any other changed file under `~/notes/research` not in the output kept at launch, and any change to `~/notes/projects/mindshare/attention-evidence.md` or `~/notes/ideas/`.
   - Leave a flagged note only if a brief in another run dir with no `reply.md` yet names it (`grep -l 'Output file: <its absolute path>' ~/.cache/agent-runs/*/researcher*/brief.md`): that run is still going. Show the user the diff of any other as this run's change, and ask. Commit neither.
2. On FAIL, send the FAIL lines to the researcher as a follow-up (`${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.md`, Follow-ups) to fix. After two rounds, carry on and report what still fails.
3. Run the `research-verifier` agent (Agent runs) with the brief `Note: <absolute path>. Today's date: <YYYY-MM-DD>.`, adding `Depth: ideas: run the prior-art hunt first.` at ideas depth. Tell the user in one line that it's being verified. End your turn.

In `finish` mode, start here:

1. Run the check without `--headroom`, and fix any FAIL lines yourself. On a length FAIL, cut unverified points only, as step 4 of section 3 says; leave a WARN for up to 10 % over after verification. Leave Verification rows the check says no longer match for the verifier.
2. Collect the claims to name in the brief:
   - claims passed as arguments;
   - claims the check reports as no longer matching;
   - claims changed since the last verification: find the last `research:` commit that touched the note (`${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py -C ~/notes log --format='%h %s' -- <note>`), then `${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py -C ~/notes diff <that commit> -- <note>`. Skip this if the note has never been committed, or if `~/notes` has no commits yet: `log` fails there.
3. Run the verifier (Agent runs, in the run dir `research-verifier-finish`) with the brief above, plus `Also check: "<claim>"; "<claim>"` if there are any.

## 3. When the verifier finishes

The reply needs a `Prior art:` block, with its queries, and table rows: at ideas depth for #1 and #2 (Novelty rows), and at full depth for any absence claim the Bottom line or Recommendation rests on.
If it's missing, send it back once: "Your reply has no Prior-art hunt. Run it as your instructions describe, every query against every venue, and reply again in full."
If it's still missing, say in the report that novelty wasn't independently checked.

1. **Apply its fixes** to the note:
   - WRONG: replace the figure or statement with the corrected one, and update or add the source.
   - MISCITED: cite the source the verifier found (add it to Sources).
   - UNSUPPORTED or UNREACHABLE: mark the claim *(unverified)*, or soften it to what the sources say.
   - Other problems: fix dangling citations; add missed evidence to Findings or Counter-evidence with its source, adjusting the wording it contradicts.
   - Prior art (ideas depth): add every `same` and `overlaps` hit to Findings → Prior art with its source. For a WRONG Novelty row, narrow that cell, and the Bottom line and Recommendation if they repeat it, to what is still new. Cut or narrow pool lines a hit makes redundant.
2. **Record the verification** in a `## Verification` section after Sources (at ideas depth, after the Candidate pool: `check-note.py` fails the other order), outside the word budget. `/spec` reads it.

   ```
   ## Verification

   Checked on <YYYY-MM-DD> by research-verifier: <N> of <M> claims confirmed, a sample of the note's <K> cited claims.

   | Claim | Cited | Verdict | Resolution |
   |---|---|---|---|
   | <the claim's wording as it now reads in the note> | [4] | CONFIRMED | |
   | <…> | [7] | WRONG | corrected to <value>, cited [12] |
   | <…> | [9] | UNREACHABLE | marked *(unverified)*: <why, e.g. GCP page renders with JavaScript> |
   ```

   - Record every row the verifier returned. `<N>` and `<M>` count the CONFIRMED rows and all rows, and `check-note.py` compares them, so put round details after them ("16 of 21 claims confirmed across both rounds' rows. Round 1: 15 of 18 …").
   - `<K>` is the note's count of cited claims, from `check-note.py`'s warning; leave that clause out if the table covers them all.
   - Every row that isn't CONFIRMED needs a Resolution: corrected, re-cited, or marked *(unverified)* in the text.
   - If the section exists, update the rows checked again, add new ones, drop rows for claims the note no longer makes, and update the date line. A Claim quotes the note's current wording.
3. **If the conclusion changed**, the rewritten text gets one more check:
   - That is `Bottom line holds: no`, missed evidence that weakens the recommendation, or at ideas depth a `same` hit on #1: re-rank the Shortlist, and a new #1 gets its prior-art hunt in round 2.
   - Revise the Bottom line and Recommendation to match the evidence, set `status: draft`, then `git -C ~/notes add <note>` and commit with the message `research: <title> (conclusion revised, re-verifying)`.
   - Run `research-verifier` in the run dir `research-verifier-2`, with `Note: <absolute path>. Today's date: <YYYY-MM-DD>. Round 2.` Tell the user in one line that the conclusion changed and is being re-checked. End your turn.
   - When it returns, apply its fixes, update Verification and carry on from step 4. If it also says `Bottom line holds: no`, leave the note as draft and say so, unless round 3 applies.
   - **Round 3**, only when round 2's `no` rests on an absence claim it narrowed again: apply the narrowing and run `research-verifier` in `research-verifier-3`, with `Note: <absolute path>. Today's date: <YYYY-MM-DD>. Round 3: check only "<the narrowed sentence>".`
   - If round 3's row is CONFIRMED with `Bottom line holds: yes`, carry on from step 4; if not, leave the note as draft and name the sentence in the report. There is no round 4.
4. Re-run `check-note.py`. With a Verification table, up to 10 % over the limit is a WARN; leave it. Cut only on a FAIL, and then cut whole unverified points from Findings or Options. Never cut a sentence a Verification row quotes, a Project health row, the Bottom line, Recommendation or Counter-evidence, nor Shortlist rows or cells.
5. **Status**: set `status: final` when all of these hold:
   - the check passes;
   - the latest verifier says `Bottom line holds: yes`;
   - every Verification row is CONFIRMED or resolved.

   A visibly marked claim that can't be verified (a JavaScript-only page, a login wall) doesn't hold a note in draft unless the Bottom line stands on it. Otherwise set `status: draft`, even if it was `final`, and say why.
6. **Link the idea**, if there was one: set its `status: exploring` if it's still `seed` (never move `adopted`, `parked` or `dropped` back), and add the research note's path to its `related`. If the Bottom line recommends against the idea, say so in the report and suggest `parked` or `dropped`; that call is the user's.
7. **Ideas depth only**: read `${CLAUDE_PLUGIN_ROOT}/skills/research/ideas-finish.md` and follow it.
8. **Rebuild the notes index**: run `${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/build-index.py ~/notes`. If it fails, say so in the report and commit without the index; don't write `index.md` yourself.
9. **Commit** only the files you created or changed in `~/notes` (the note, an edited idea note, `index.md` and, at ideas depth, the evidence note and new idea notes): `git -C ~/notes add <files>`, then `git -C ~/notes commit -m 'research: <title>' -- <files>`, following this session's commit attribution rules. Don't push.
10. **Report**, one short line for each of these:
   - the note path;
   - the bottom line in two sentences;
   - verification, e.g. `9 of 10 claims confirmed (a sample of 31 cited), 1 corrected, 1 left unverified`, and whether the conclusion changed;
   - the status and, if draft, why;
   - the commit hash;
   - what its agents cost, from each `run-agent.sh` run's last line as `${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.md` step 3 says: `Agents cost $<total> (<agent> $<cost>, …)`, or `Agents cost at least $<known> (<agent> unknown, …)` when any run's cost is unknown;
   - at ideas depth: the pool size and lenses covered, the prior-art verdict on #1 and #2, and the idea notes filed.

   If the recommendation is to change a repo, add a line: the next step is `/spec <note>`, run from that repo. If the Recommendation is conditional or the options are close, suggest recording the choice in `~/notes/decisions/` first.

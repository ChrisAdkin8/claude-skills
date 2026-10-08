---
name: cold-review
description: Gives a markdown document one adversarial read by an agent that never saw the conversation that wrote it, and relays what it found; on a reviewed document, reviews only the changes logged since. Runs when the user types /cold-review.
disable-model-invocation: true
argument-hint: <path to a markdown file> | prompt <path to a markdown file>
allowed-tools: Read, Grep, Glob, Bash(git rev-parse *), Bash(git status *), Bash(git ls-files *), Bash(${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py *), Bash(${CLAUDE_PLUGIN_ROOT}/skills/cold-review/scripts/review-state.py *), Bash(grep *), Bash(ls *), Bash(${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.sh *), Edit(~/.cache/agent-runs/**), Edit(~/code/**/records/*-record.md), Edit(~/notes/**/records/*-record.md)
---


# Cold-review a document

Document: $ARGUMENTS

An agent that never saw the document written gives it one adversarial read, and you relay it.
One full round per document; changes logged afterwards as `Not reviewed:` lines get one **delta
review**. Its history goes in the **record**, `records/<basename>-record.md` beside it (layout:
`${CLAUDE_PLUGIN_ROOT}/skills/spec/record-template.md`); older documents keep theirs at their end.

`/spec` builds its cold review from three sections of this file: *Read the document in full*
(the `Implementation spec` row and its extra lines), *Gather pointers* and *Write the prompt*
(the skeleton). Change those here, not there.

**Progress.** Paste this checklist, ticked to date, at the end of the turn that ends while the
reviewer runs, and in the final report. When it returns, carry on from the first unticked line.

```
- [ ] Frame: review-state.py's state, the repo, who wrote it
- [ ] Read the document in full; its kind
- [ ] Gather pointers
- [ ] Write the prompt; reviewer launched, or the prompt handed over in prompt mode
- [ ] Relay the table; the review saved if it's a spec's, otherwise offered
```

## Modes

- `/cold-review <path>`: the full path.
- `/cold-review prompt <path>`: stop after step 4; save a reply pasted back as step 5 says.

## 1. Frame

1. **The document.** The path from `$ARGUMENTS`, else the document just discussed, else ask for
   one in one line and stop. It must exist and be markdown.
2. **Where it stands.** Run `${CLAUDE_PLUGIN_ROOT}/skills/cold-review/scripts/review-state.py <document>`.
   Its last line is the `state:`:
   - `full`: no saved review. Carry on with the full review.
   - `delta`: the delta review, from the `diff:` command and `logged:` lines it printed. Run
     `diff:` exactly as printed; the prompt gives it starting with `git` (step 4). If `headings:`
     names parts no logged line covers, say so in one line and offer to log them.
   - `unlogged`: say so, show `stat:` and `headings:`, and draft one `Not reviewed:` line per
     change; once the user confirms them, add them to the record under
     `## Changes since the review` (lines anywhere else don't count), and do the delta review.
   - `unchanged` (say its `review-date:`), `no-base` (no commit to diff from) or `done` (name any
     `logged:` lines left): say so, and stop.
   - If it printed `record-moved:`, the record is still under the document's old name: say so,
     and give the user the command to run: `git mv <that path> <dir>/records/<name>-record.md`,
     with the document's folder and basename.
3. **Its repo**: `repo:` and `head:` from the script. If `${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py -C <repo>
   status --porcelain` shows the document or its code uncommitted, say so in one line.
4. **Who wrote it.** If this session wrote or edited it, say so in one line and carry on: the
   reviewer is an agent that never sees this conversation, so it stays cold. Don't suggest
   `prompt` mode unless the user asks for it.

## 2. Read the document in full

Read it, then decide its kind:

| Kind | What a cold reader has to be able to do | Correctness means |
| --- | --- | --- |
| Walkthrough, runbook, quickstart | Follow it start to finish without stopping to ask, with every prerequisite stated before it's needed and every destructive step flagged before it runs | a reader who follows it as written gets a wrong or broken result, or is misled about what happened |
| README, reference | Find the entry points and trust what it says about them, without the code contradicting it | a reader who relies on it as written gets a wrong or broken result |
| Design doc, ADR | Reach the same conclusion from the evidence given, without redoing the research | the conclusion doesn't follow from the evidence, or the design as written breaks something |
| Implementation spec | Build it from W1 onwards, without redoing the research or going back to its author | built as written, the change is wrong: it breaks something, loses data, fails its own Done when, or can't be carried out |
| Research note, postmortem | Tell what's established from what's inferred, and see which source each claim rests on | the conclusion doesn't follow from the claims, or a claim it rests on is presented as established when it's inferred or cites nothing |

A document that is several of these is reviewed as all of them; say which in the prompt, and
join their correctness meanings with "or".

A **research note**'s reviewer can't fetch its sources: point to `/research finish <note>` for them.

An **implementation spec** gets these lines added to "How to go about it", after the second one:

```
- Read the work items in order, W1 first, before opening the research note.
- For each work item, `git grep` the names it changes (functions, flags, keys, values, metrics, paths) and work out which checks run over the files it touches, starting from the entry points above. These are where to start, not the full list.
- Stated requirements include the spec's Goal, Done when lines, Non-goals and Decision.
- Open <the research note path, or "the research note the spec links"> only where the spec leaves you stuck, to see whether the spec leans on it for something it should carry itself.
```

## 3. Gather pointers

Collect only pointers, with Glob and grep:

- the repo root and the commit it's read at; for a spec, also the repo its `path:line` citations
  point into, if different;
- the entry points it tells a reader to run (`Taskfile*`, `Makefile`, `.github/workflows/*`,
  `package.json` scripts); for a spec, the checks over the files it changes (CI, pre-commit, lint);
- the rules it's bound by: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/*method*`,
  `docs/*process*`;
- what a stranger needs to find things: a generated directory, a second repo, the fixtures.

No summary, no view on which parts are weak or sound, no reasons. A delta review's scope is the
diff command from step 1 and the `Not reviewed:` lines quoted exactly.

## 4. Write the prompt

Fill in this skeleton, keeping the core paragraph and the reply format word for word.

````
Review <absolute document path> adversarially. You haven't seen how it was written. Work from the document, the code in <absolute repo root, or "no repo: work from the document and what it links"><, whose path:line citations point into <cite repo>, if it differs>, and what it links to. Today's date is <YYYY-MM-DD>.

It is <the kind from step 2, with its article: "a runbook", "an implementation spec">, so a cold
reader has to be able to <what that row says>. Find what stops them: statements the code
contradicts, statements that were true and have drifted, steps and prerequisites that are missing,
assumptions presented as facts, costs not counted (files, checks that will go red, migrations), and
anything a cold reader can't work through without asking the author. Grade each finding by whether
it affects correctness or a stated requirement, and say which don't. Don't edit the file.
<Delta review only: A full cold review of this document is saved <in its record, <absolute record
path> | at its end, under "## Cold review">. Since then it has changed in the places below. Read the
document straight through once as usual, then report only findings in these changes, or caused by
them elsewhere in the document. The lines below say where it changed, as its author logged it, not
whether the change is right. Leave the saved review alone: it is a record.
- Diff: `<the diff: line from step 1, with "git" in place of "${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py">`<, or "none: there is no commit to diff from">
- Changes logged since the review: <each Not reviewed: line, quoted exactly>>

How to go about it:
- Read it once straight through, as the reader it's addressed to, before opening any code. Note each place you'd have to stop, guess or go digging. That pass is the only chance to see it cold; everything after it is checking.
- Then check what it asserts. For every command, flag, path, file name, output and number, find what defines it and read that: <the entry points from step 3>. A command's flags come from the code that parses them, not from another document.
<The kind's extra lines from step 2, if it has any.>
- You cannot run any of it, so settle what reading settles and say plainly which findings need a run. Don't guess at what a command would print.
- Stated requirements are what the document says it is for and who it is for, plus the repo's rules in <the rules files from step 3, or "no rules file">.<Add a line for anything else a stranger would need to find things.>
- Don't pad. A category with no findings is a valid result. Skip style and wording unless they stop a cold reader.

Grades: `correctness` (<what correctness means for this kind, from step 2>); `requirement: "<the requirement, quoted>"`; or `neither: <why it doesn't matter>`.

Reply with only a table, correctness rows first, then requirement, then neither:
| # | Kind (WRONG, STALE, GAP, ASSUMPTION, COST or COLD-READ) | Where (the heading, or exact text from the document) | Finding | Affects | Evidence (path:line, grep hit or config line) | What would settle it |
Then one line each: `Counts: N findings - C correctness, R requirement, K neither`; `Neither: <row numbers, or none>`; `Cold read: yes`, or `Cold read: no - <first place you had to stop>`; `Needs a run: <row numbers reading couldn't settle, or none>`.
````

In `prompt` mode, give the user the filled-in prompt in a fenced block, to run in a session with
no history of this one, ask them to paste the reply back here, and stop.

Otherwise run the `cold-reviewer` agent: read `${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.md` and follow it, with
the prompt as the brief. The work dir is the repo root, or the document's directory. The run dir is
`~/.cache/agent-runs/<name>/cold-reviewer` (`cold-reviewer-delta` for a delta review), where
`<name>` is `<repo dir name>--<document basename>` (outside a repo, its directory's name).
If the reply can't be used, relay nothing. Tell the user in one line, and end your turn.

## 5. When the reviewer finishes

1. **Don't edit the document for its findings**: they're the user's to judge.
2. **Relay the table**:
   - `correctness` and `requirement` findings: one line each, with where, the finding, and what
     would settle it;
   - the `neither` ones: one line in total;
   - `Cold read: no`: where it had to stop;
   - rows `Needs a run` names: offer to run those commands yourself;
   - a finding you think is wrong: say why in one line, but keep it;
   - what the reviewer cost, from `run-agent.sh`'s last line as `${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.md`
     step 3 says, in one line: `Agents cost $<total> (<agent> $<cost>, …)`, or `Agents cost at least $<known> (<agent> unknown, …)` when any run's cost is unknown.
3. **Offer, in one line each:** folding in the `correctness` and `requirement` findings, and saving
   the review. Do neither unasked, but save a spec's review, full or delta, without asking.
   - **Folding in:** fold only the ones the user picks. A document with a saved review logs each
     fold in its record, under `## Changes since the review`, as `- Not reviewed: <what changed>,
     from <review> row <n>, on <YYYY-MM-DD>.`
   - **Saving:** in the record (from the record template, keeping only the sections it needs), add
     the table and its closing lines unchanged under `## Cold review`, after a line `Reviewed on
     <YYYY-MM-DD> by cold-reviewer. Saved unchanged; what was folded in is logged under Changes
     since the review.`
   - **Saving a delta review:** at the end of the record's `## Cold review` section, under `###
     Delta review, <YYYY-MM-DD>`, after a line `Reviewed on <YYYY-MM-DD> by cold-reviewer: the
     changes logged as Not reviewed. Saved unchanged.` Then change each `Not reviewed:` line it
     covered to `Delta-reviewed on <YYYY-MM-DD>:`, keeping the rest of the line. For an older
     document whose review is at its end, add the delta there, beside the review it follows.

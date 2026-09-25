---
name: cold-review
description: Give a markdown file one adversarial cold read by an agent that never saw this conversation, then relay what it found. Use when the user runs /cold-review, or asks for a cold, fresh-eyes or adversarial review of a document - a walkthrough, runbook, README, design doc, spec or research note. Accepts the path to a markdown file; "prompt <path>" writes the review prompt for the user to run in a fresh session instead of launching an agent. On a document that already has a saved review, it runs the one delta review of the changes logged since.
argument-hint: <path to a markdown file> | prompt <path to a markdown file>
allowed-tools: Read, Grep, Glob, Bash(git rev-parse *), Bash(git status *), Bash(git ls-files *), Bash(~/.claude/hooks/git-read.py *), Bash(grep *), Bash(ls *), Bash(~/.claude/hooks/run-agent.sh *), Edit(~/.cache/agent-runs/**), Edit(~/code/**), Edit(~/notes/**)
---

# Cold-review a document

Document: $ARGUMENTS

A document is finished when someone who wasn't there can use it. The author can't test that: you
know what the commands do, which corners were cut, and what the sentence was meant to say. This
skill hands the document to an agent that has seen none of it, and brings back what it found.

One full adversarial round per document. The reviewer edits nothing, and neither do you: the
findings are the user's to judge. A reviewer asked to find gaps finds some whether or not any
exist, so chasing all of them produces defensive, over-qualified prose.

A document can still change after its review: findings get folded in, spikes answer questions,
the user decides things. Those changes are the least-checked part of it. So a document that logs
them as `Not reviewed:` lines gets one **delta review**, of just those changes, and no more.

A document's review history lives in its **record**, `records/<basename>-record.md` in the
document's directory (the layout is `~/.claude/skills/spec/record-template.md`): the saved
review, any delta review, and the `Not reviewed:` log. The document stays what its readers came
for. Older documents keep a saved review at their end, under `## Cold review`, and `Not reviewed:`
lines in their open questions; read those the same way, and write anything new to a record.

`/spec` builds its cold review from steps 3 and 4 of this file, so the two ask the same question.
Change the skeleton here, not there.

## Modes

- `/cold-review <path>`: the main path. Frame, write the prompt, launch the reviewer, relay it.
- `/cold-review prompt <path>`: write the prompt and hand it over, launching nothing. Use it when
  the user wants the review in a session that shares no process with this one, or wants to run it
  later. Stop after step 4. When the user pastes the reply back into this session, save it as
  step 5 says: a review run elsewhere and never saved leaves no record that the round happened.

## 1. Frame (in the conversation)

1. **The document.** Resolve the path from `$ARGUMENTS`; if it's empty, use the document just
   discussed, and failing that ask for a path in one line and stop. It must exist and be markdown.
2. **An earlier review.** Look for a saved review before anything else: a `## Cold review`
   heading at the start of a line in the record, `records/<basename>-record.md` beside the
   document, or failing that in the document itself (an older one). `Not reviewed:` lines are in
   the record's `## Changes since the review`, or the older document's open questions.
   - None: this is the full review. Carry on.
   - One, with `Not reviewed:` lines and no `### Delta review` under it: this is the delta
     review. Carry on, and follow the delta notes in steps 3 to 5.
   - One, with no `Not reviewed:` lines: check whether the document changed anyway (step 3,
     the review commit). If its diff is empty, say that the document had its review on the date
     in the section and hasn't changed since, and stop. If it isn't, the changes were never
     logged: say so, show the diff's `--stat` and the headings it touches, and draft one `Not
     reviewed:` line per change from the diff. Once the user confirms them, add them to the
     record and carry on as a delta review. If there's no review commit to diff from, say that
     unlogged changes can't be found, and stop.
   - One that already has a `### Delta review`: say that the document had its full review and
     its delta review, name any `Not reviewed:` lines left, and stop. They stay listed as
     unreviewed; that's the record, not a reason for a third round.
3. **Its repo.** `~/.claude/hooks/git-read.py -C <the document's directory> rev-parse --show-toplevel`. Record the root and
   `~/.claude/hooks/git-read.py -C <root> rev-parse --short HEAD`. A document outside a repo (a note in `~/notes`) is fine: the
   review then works from the document and whatever it links.
   - If `~/.claude/hooks/git-read.py -C <root> status --porcelain` shows the document or the code it describes is uncommitted, say
     so in one line: the reviewer reads the working tree, so its findings age with it.
   - **The review commit** (for a delta review, and for step 2's check): the oldest commit that
     added the review's date line, which finds the original save even when the review was later
     moved from the document into a record: `~/.claude/hooks/git-read.py -C <root> log
     --format=%h -S'Reviewed on <the date in that line> by' -- <the record> <the document>`
     (the last line is the oldest; with no date line, search for `## Cold review` instead). If
     the review is in a record and that commit also changed a document that already existed
     before it (`git-read.py -C <root> show --stat --format= <commit> -- <document>` lists it,
     and `git-read.py -C <root> cat-file -e <commit>^:<document path from the root>` succeeds),
     the base is `<commit>^`, so folds saved in the same commit aren't missed; otherwise the
     base is the commit. The
     diff is `git -C <root> diff <base> -- <document>`, which includes uncommitted edits.
     No commit (the review was never committed): the reviewer works from the `Not reviewed:`
     lines alone.
   - **Unlogged changes** (delta review): read that diff against the `Not reviewed:` lines. If
     it changes parts of the document none of them accounts for, name those headings in one
     line. They're in the diff, so the reviewer covers them; offer to log them in the record
     as `Not reviewed:` lines, so the record says what the delta review covered.
4. **Who wrote it.** If this session wrote or edited the document, say so in one line. The agent is
   still cold - it has seen no part of this conversation - but you are not, and step 3 is where
   that leaks. If the user would rather have a reader that shares nothing at all with this
   session, offer `prompt` mode.

## 2. Read the document in full

Read it, then decide what kind of document it is, because that decides what a cold read means
and what counts as a correctness finding:

| Kind | What a cold reader has to be able to do | Correctness means |
| --- | --- | --- |
| Walkthrough, runbook, quickstart | Follow it start to finish without stopping to ask, with every prerequisite stated before it's needed and every destructive step flagged before it runs | a reader who follows it as written gets a wrong or broken result, or is misled about what happened |
| README, reference | Find the entry points and trust what it says about them, without the code contradicting it | a reader who relies on it as written gets a wrong or broken result |
| Design doc, ADR | Reach the same conclusion from the evidence given, without redoing the research | the conclusion doesn't follow from the evidence, or the design as written breaks something |
| Implementation spec | Build it from W1 onwards, without redoing the research or going back to its author | built as written, the change is wrong: it breaks something, loses data, fails its own Done when, or can't be carried out |
| Research note, postmortem | Tell what's established from what's inferred, and follow each claim to a source | a claim the conclusion rests on is wrong, or presented as established when it's inferred |

A document that is several of these is reviewed as all of them; say which in the prompt, and
join their correctness meanings with "or".

An **implementation spec** gets these lines added to "How to go about it", after the second one:

```
- Read the work items in order, W1 first, before opening the research note.
- For each work item, `git grep` the names it changes (functions, flags, keys, values, metrics, paths) and work out which checks run over the files it touches, starting from the entry points above. These are where to start, not the full list.
- Stated requirements include the spec's Goal, Done when lines, Non-goals and Decision.
- Open <the research note path, or "the research note the spec links"> only where the spec leaves you stuck, to see whether the spec leans on it for something it should carry itself.
```

## 3. Gather pointers (never conclusions)

The reviewer needs to find things, not to be told what to think. Collect only:

- the repo root, and the commit it's read at; for a spec, also the repo its `path:line`
  citations point into, if it isn't the same one;
- the entry points the document describes: `Taskfile*`, `Makefile`, `.github/workflows/*`, the
  CLI's own module, `package.json` scripts, `docker-compose*` - whatever it tells a reader to run;
  for a spec, the checks that run over the files it changes (CI, pre-commit, lint and policy
  config);
- the rules the document is bound by: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, and any
  `docs/*method*` or `docs/*process*` file;
- anything a stranger to this repo needs in order to find things at all: a generated directory, a
  second repo the document reaches into, where the data or fixtures live.

Find them with Glob and grep. Don't summarise the document, don't say which parts you think are
weak or sound, and don't explain why it was written that way. A reviewer handed the author's
framing checks the framing instead of the document.

For a delta review, the scope is a pointer too: the diff command from step 1, and the `Not
reviewed:` lines quoted exactly as they stand. They say where the document changed; they don't
say whether the change is right, and the prompt says so.

## 4. Write the prompt

Build it from this skeleton. Keep the core paragraph and the reply format word for word, so every
review answers the same question and you can relay it; fill in the rest.

````
Review <absolute document path> adversarially. You haven't seen how it was written. Work from the document, the code in <absolute repo root, or "no repo: work from the document and what it links"><, whose path:line citations point into <cite repo>, if it differs>, and what it links to. Today's date is <YYYY-MM-DD>.

It is <the kind from step 2, with its article: "a runbook", "an implementation spec">, so a cold reader has to be able to <what that row says>. Find what stops them: statements the code contradicts, statements that were true and have drifted, steps and prerequisites that are missing, assumptions presented as facts, costs not counted (files, checks that will go red, migrations), and anything a cold reader can't work through without asking the author. Grade each finding by whether it affects correctness or a stated requirement, and say which don't. Don't edit the file.
<Delta review only: A full cold review of this document is saved <in its record, <absolute record path> | at its end, under "## Cold review">. Since then it has changed in the places below. Read the document straight through once as usual, then report only findings in these changes, or caused by them elsewhere in the document. The lines below say where it changed, as its author logged it, not whether the change is right. Leave the saved review alone: it is a record.
- Diff: `git -C <repo root> diff <the base from step 1, item 3> -- <document path>`<, or "none: the review was never committed">
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

In `prompt` mode, give the user the filled-in prompt in a fenced block, say it expects a session
with no history of this one, ask them to paste the reply back here so it can be saved, and stop.

Otherwise run the `cold-reviewer` agent with that prompt. It runs as a headless, sandboxed
session, since Claude Code can't sandbox a subagent on its own: with the Write tool, write the
prompt to `~/.cache/agent-runs/<document basename>/cold-reviewer/brief.md` (`cold-reviewer-delta`
for a delta review), then run `~/.claude/hooks/run-agent.sh cold-reviewer <repo root, or the
document's directory> <that run dir>` with the Bash tool and `run_in_background: true`, paths
written with `~`. When it finishes, read `<run dir>/reply.md`. Exit 3 means the run finished
but the reply lacks the table and closing lines the skeleton asks for (an API error such as
"Request timed out", a budget stop, or a reply out of format): write `followup.md` in the run
dir asking for the reply again, in full, in that format, and run the same command with
`--resume`; if that exits 3 too, tell the user and relay nothing. Any other non-zero exit means
no reply, and `run.err` there says why. The agent brings only read-only tools and safety rules; everything it
reviews for comes from your prompt.
Tell the user in one line that the document is under cold review (or delta review), and end your
turn.

## 5. When the reviewer finishes

1. **Don't edit the document for its findings.** See the top of this file.
2. **Relay the table.** It isn't shown to the user, so pass it on:
   - findings graded `correctness` or `requirement`: one line each, with where in the document,
     the finding, and what would settle it;
   - the ones graded `neither`: one line in total, listing them and saying the reviewer judged
     they don't matter;
   - if it says `Cold read: no`, say where it had to stop. That single line is often worth more
     than the table: it's the first place the document lost a reader.
   - if `Needs a run` names rows, say so and offer to run those commands yourself in this session.
     The reviewer is read-only by design; you are not.
   - if you think a finding is wrong, say so and why in one line, but leave it in the list.
3. **Offer, in one line each:** folding in the findings that affect correctness or a requirement,
   and saving the review. Don't do either unasked.
   - **Folding in:** fold only the ones the user picks. Don't touch the rest. A document with a
     saved review logs each fold in its record, under `## Changes since the review`, as `- Not
     reviewed: <what changed>, from <review> row <n>, on <YYYY-MM-DD>.` (`check-spec.py` counts
     them for a spec), since the fix itself hasn't been reviewed. After a delta review, those
     lines are the record of what stays unreviewed.
   - **Saving:** in the record (start it from the record template, keeping only the sections it
     needs), add the table and its closing lines unchanged under `## Cold review`, after a line
     `Reviewed on <YYYY-MM-DD> by cold-reviewer. Saved unchanged; what was folded in is logged
     under Changes since the review.` Saving it isn't acting on it. Since the record is a
     separate file, this suits any document, a README or runbook included.
   - **Saving a delta review:** in the same record, at the end of its `## Cold review` section,
     under `### Delta review, <YYYY-MM-DD>`, after a line `Reviewed on <YYYY-MM-DD> by
     cold-reviewer: the changes logged as Not reviewed. Saved unchanged.` Then change each `Not
     reviewed:` line it covered to `Delta-reviewed on <YYYY-MM-DD>:`, keeping the rest of the
     line. For an older document whose review is at its end, add the delta there instead, beside
     the review it follows. For a spec, save it without asking, as `/spec` does with the full
     review: the spec's checker reads it.

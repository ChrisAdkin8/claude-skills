---
name: cold-review
description: Give a markdown file one adversarial cold read by an agent that never saw this conversation, then relay what it found. Use when the user runs /cold-review, or asks for a cold, fresh-eyes or adversarial review of a document - a walkthrough, runbook, README, design doc, spec or research note. Accepts the path to a markdown file; "prompt <path>" writes the review prompt for the user to run in a fresh session instead of launching an agent.
argument-hint: <path to a markdown file> | prompt <path to a markdown file>
allowed-tools: Read, Grep, Glob, Bash(git rev-parse *), Bash(git -C * rev-parse *), Bash(git status *), Bash(git -C * status *), Bash(git log *), Bash(git -C * log *), Bash(git ls-files *), Bash(git -C * ls-files *), Bash(grep *), Bash(ls *), Edit(~/code/**), Edit(~/notes/**)
---

# Cold-review a document

Document: $ARGUMENTS

A document is finished when someone who wasn't there can use it. The author can't test that: you
know what the commands do, which corners were cut, and what the sentence was meant to say. This
skill hands the document to an agent that has seen none of it, and brings back what it found.

One adversarial round per document. The reviewer edits nothing, and neither do you: the findings
are the user's to judge. A reviewer asked to find gaps finds some whether or not any exist, so
chasing all of them produces defensive, over-qualified prose.

## Modes

- `/cold-review <path>`: the main path. Frame, write the prompt, launch the reviewer, relay it.
- `/cold-review prompt <path>`: write the prompt and hand it over, launching nothing. Use it when
  the user wants the review in a session that shares no process with this one, or wants to run it
  later. Stop after step 4.

## 1. Frame (in the conversation)

1. **The document.** Resolve the path from `$ARGUMENTS`; if it's empty, use the document just
   discussed, and failing that ask for a path in one line and stop. It must exist and be markdown.
2. **Its repo.** `git rev-parse --show-toplevel` from the document's directory. Record the root and
   `git rev-parse --short HEAD`. A document outside a repo (a note in `~/notes`) is fine: the
   review then works from the document and whatever it links.
   - If `git status --porcelain` shows the document or the code it describes is uncommitted, say
     so in one line: the reviewer reads the working tree, so its findings age with it.
3. **Who wrote it.** If this session wrote or edited the document, say so in one line. The agent is
   still cold - it has seen no part of this conversation - but you are not, and step 3 is where
   that leaks. If the user would rather have a reader that shares nothing at all with this
   session, offer `prompt` mode.

## 2. Read the document in full

Read it, then decide what kind of document it is, because that decides what a cold read means:

| Kind | What a cold reader has to be able to do |
| --- | --- |
| Walkthrough, runbook, quickstart | Follow it start to finish without stopping to ask, with every prerequisite stated before it's needed and every destructive step flagged before it runs |
| README, reference | Find the entry points and trust what it says about them, without the code contradicting it |
| Design doc, spec, ADR | Reach the same conclusion from the evidence given, without redoing the research |
| Research note, postmortem | Tell what's established from what's inferred, and follow each claim to a source |

A document that is several of these is reviewed as all of them; say which in the prompt.

## 3. Gather pointers (never conclusions)

The reviewer needs to find things, not to be told what to think. Collect only:

- the repo root, and the commit it's read at;
- the entry points the document describes: `Taskfile*`, `Makefile`, `.github/workflows/*`, the
  CLI's own module, `package.json` scripts, `docker-compose*` - whatever it tells a reader to run;
- the rules the document is bound by: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, and any
  `docs/*method*` or `docs/*process*` file;
- anything a stranger to this repo needs in order to find things at all: a generated directory, a
  second repo the document reaches into, where the data or fixtures live.

Find them with Glob and grep. Don't summarise the document, don't say which parts you think are
weak or sound, and don't explain why it was written that way. A reviewer handed the author's
framing checks the framing instead of the document.

## 4. Write the prompt

Build it from this skeleton. Keep the core paragraph and the reply format word for word, so every
review answers the same question and you can relay it; fill in the rest.

````
Review <absolute document path> adversarially. You haven't seen how it was written. Work from the document, the code in <absolute repo root, or "no repo: work from the document and what it links">, and what it links to. Today's date is <YYYY-MM-DD>.

It is a <kind, from step 2>, so a cold reader has to be able to <what that row says>. Find what stops them: statements the code contradicts, statements that were true and have drifted, steps and prerequisites that are missing, assumptions presented as facts, and anything a cold reader can't work through without asking the author. Grade each finding by whether it affects correctness or a stated requirement, and say which don't. Don't edit the file.

How to go about it:
- Read it once straight through, as the reader it's addressed to, before opening any code. Note each place you'd have to stop, guess or go digging. That pass is the only chance to see it cold; everything after it is checking.
- Then check what it asserts. For every command, flag, path, file name, output and number, find what defines it and read that: <the entry points from step 3>. A command's flags come from the code that parses them, not from another document.
- You cannot run any of it, so settle what reading settles and say plainly which findings need a run. Don't guess at what a command would print.
- Stated requirements are what the document says it is for and who it is for, plus the repo's rules in <the rules files from step 3, or "no rules file">.<Add a line for anything else a stranger would need to find things.>
- Don't pad. A category with no findings is a valid result. Skip style and wording unless they stop a cold reader.

Grades: `correctness` (a reader who follows it as written gets a wrong or broken result, or is misled about what happened); `requirement: "<the requirement, quoted>"`; or `neither: <why it doesn't matter>`.

Reply with only a table, correctness rows first, then requirement, then neither:
| # | Kind (WRONG, STALE, GAP, ASSUMPTION or COLD-READ) | Where (the heading, or exact text from the document) | Finding | Affects | Evidence (path:line, grep hit or config line) | What would settle it |
Then one line each: `Counts: N findings - C correctness, R requirement, K neither`; `Neither: <row numbers, or none>`; `Cold read: yes`, or `Cold read: no - <first place you had to stop>`; `Needs a run: <row numbers reading couldn't settle, or none>`.
````

In `prompt` mode, give the user the filled-in prompt in a fenced block, say it expects a session
with no history of this one, and stop.

Otherwise launch the Agent tool with `subagent_type: cold-reviewer` and that prompt. The agent
brings only read-only tools and safety rules; everything it reviews for comes from your prompt.
Tell the user in one line that the document is under cold review, and end your turn.

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
   - **Folding in:** fold only the ones the user picks. Don't touch the rest.
   - **Saving:** append the table and its closing lines unchanged at the end of the document, under
     `## Cold review`, after a line `Reviewed on <YYYY-MM-DD> by cold-reviewer. Saved unchanged;
     not acted on.` Saving the record isn't acting on it. Offer it for a document that keeps its
     own history - a spec, an ADR, a design doc - and not for one people read for instructions,
     such as a README or a runbook, where a review table at the bottom is noise. If the document
     already has a `## Cold review` section, say so: one adversarial round per document, and this
     was it.

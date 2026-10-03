---
name: spec
description: Turns a research note or a described change into an implementation spec in the repo it changes, grounded in file:line citations, then verifies it and gives it a cold review. Runs when the user types /spec.
disable-model-invocation: true
argument-hint: '[quick] <research note path> [direction] | [quick] <description of the change> | finish <spec path> | spike <spec path> | done <spec path>'
allowed-tools: Read Grep Glob Edit(~/code/**/docs/specs/**) Edit(~/notes/**) Edit(~/.cache/spec-spikes/**) Bash(grep *) Bash(git rev-parse *) Bash(git status *) Bash(git ls-files *)
  Bash(git -C ~/notes status *) Bash(${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py *) Bash(git -C ~/notes add *) Bash(git -C ~/notes commit *) Bash(${CLAUDE_PLUGIN_ROOT}/skills/spec/scripts/check-spec.py *)
  Bash(${CLAUDE_PLUGIN_ROOT}/skills/research/scripts/check-note.py *) Bash(${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.sh *) Edit(~/.cache/agent-runs/**)
  Bash(${CLAUDE_PLUGIN_ROOT}/skills/spec/scripts/prepare-spike.sh ~/.cache/spec-spikes/*) Bash(${CLAUDE_PLUGIN_ROOT}/skills/spec/scripts/run-spike.sh ~/.cache/spec-spikes/*)
---

# Write an implementation spec

Request: $ARGUMENTS

**Progress.** Copy this checklist into your reply at the end of every turn that ends while an agent runs, ticked to date, and once more in the final report. When the agent returns, carry on from the first unticked line. Tick a stage the mode skips as skipped, e.g. `- [x] Cold review: skipped (quick)`.

```
- [ ] Frame: repo, research note, option and spec path
- [ ] Read and interview
- [ ] Write: check-spec.py passes; verifier launched
- [ ] Verifier: round recorded, fixes applied, check passes
- [ ] Notes linked and committed
- [ ] Cold review: launched, relayed, saved, picks folded in
- [ ] Spikes offered or run
- [ ] Report and next steps
```

**The record.** A spec's history goes in `<spec dir>/records/<basename>-record.md`, started from `${CLAUDE_PLUGIN_ROOT}/skills/spec/record-template.md` when first needed: verifier rounds, reviews, the `Not reviewed:` log, spike routing, implementation notes.
An older spec keeps it inline (`## Cold review` at its end, `Not reviewed:` lines in Open questions); move it to a record when you next edit the spec.

Write no code in the repo, and don't branch or commit there.

Run `git log`, `git diff` and any `git -C <dir>` read through `${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py`, and `git rev-parse`, `git status` and `git ls-files` too when the repo isn't the working directory. Run one command per Bash call, with each script's full path written out: a shell variable, a `cd` or a second command in the call isn't pre-approved, so it asks the user.

The checking rules are in `${CLAUDE_PLUGIN_ROOT}/hooks/agents/spec-verifier.md`, and the cold review's prompt skeleton in `${CLAUDE_PLUGIN_ROOT}/skills/cold-review/SKILL.md`. Don't restate either in a brief.

## Agent runs

Each agent runs as a headless, sandboxed session: read `${CLAUDE_PLUGIN_ROOT}/hooks/run-agent.md` and follow it. The work dir is the repo root; the run dir is `~/.cache/agent-runs/<repo dir name>--<spec basename>/<agent>`. For a split spec, launch one per part at once.

## Modes

- `/spec <research note path> [direction]`: the main path. A direction narrows it: "option B", "phase 1".
- `/spec <description of the change>`: `research: none`. If the approach isn't settled, suggest `/research` first, and continue only if the user wants to.
- `/spec quick <research note path or description>`: a small, settled change: steps 1 to 5 only, at most three work items, no spike questions. If it needs more, say so after step 3 and offer the full path (`/spec finish <spec>`).
  Log it in the record's `## Verification` as `- Quick spec on <YYYY-MM-DD>: no cold review or spikes.`
- `/spec finish <spec path>`: from step 3's check, after hand edits or an unfinished session.
- `/spec spike <spec path>`: step 7, once the cold review is done.
- `/spec done <spec path>`: step 8, after the build.

## 1. Frame

1. **Repo.** `git rev-parse --show-toplevel` must be a repo under `~/code`; otherwise ask in one line for one, and stop. Record `git rev-parse --short HEAD` as read-at. If `git status --porcelain` shows uncommitted changes, say so: citations to them may never be committed.
   - **A new repo** (no commits): set `cite-repo:` and `read-at` to another local repo's `~` path and short HEAD, or `read-at: none`.
2. **Research note.**
   - Empty request: the note just discussed, or the newest whose `related` names this repo (`grep -lE '<repo path, with ~>([],/[:space:]]|$)' ~/notes/research/*.md`); name it.
   - Read it in full, and any idea note in its `related`.
   - `draft`, or `final` with no `## Verification` section: suggest `/research finish <note>` first, and continue only if the user says so. Without that section, every borrowed claim counts as unchecked.
   - Sources or Verification dated over 90 days ago: suggest updating it, and continue unless told otherwise. `outdated`: stop and suggest `/research`.
   - If its `related` names this repo, `git-read.py log --oneline <its read-at>..HEAD` shows how far the code has moved; if not, check its assumptions in step 2.
   - **Decision.** `grep -l '<note path, with ~>' ~/notes/decisions/*.md`; no match, or no files (grep errors), means none. Name an `accepted` one as the chosen option; mention a `proposed` one; ignore the rest.
3. **Option.** The accepted decision, else the note's Recommendation, unless the direction says otherwise; if that's conditional or open, ask with AskUserQuestion, recommended first.
4. **Where the spec goes.** Read `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/*method*`, `docs/*process*`, `docs/adr*`, and look for `prompts/`, `docs/specs/`, `docs/design/`, `rfcs/`.
   Follow a repo convention exactly (location, filename, sections, style, process); otherwise write `docs/specs/YYYY-MM-DD-short-slug.md` from `${CLAUDE_PLUGIN_ROOT}/skills/spec/template.md`.
5. **Existing specs.** `grep -ril '<key terms>'` in the spec location. If one covers this, ask whether to update it or write a new one. Never rewrite a spec marked done or superseded.

Stay in this session. The verifier and cold reviewer are agents that never see this conversation, so a fresh session adds nothing.

Tell the user in one or two lines: the research note, the option, and where the spec will land.

## 2. Read and interview

1. **Read the code the change touches**: entry points, files the note's Context names, config, manifests, CI, their tests, and how the repo runs its checks (an Explore agent for a broad sweep). Record each fact with its `path:line`.
2. **Check the research against the code.** Put a contradiction in Background and your report; if it undermines the Recommendation, stop and tell the user.
3. **Interview.** One AskUserQuestion call, up to four questions, only on what changes the spec and nothing settles, recommended option first. Skip it if nothing is open.

## 3. Write

- **Self-contained**: its readers never saw this conversation.
- **Cite, don't restate.**
  - Repo facts get `path:line` or `path:start-end` from the (cite) repo root. Background says the date and commit it was read at ("Read at `<short sha>`" in a house-format spec without frontmatter). After a full citation, `(:48)` in the same paragraph means the same file.
  - Code not cloned locally: a URL at a fixed commit (`https://github.com/o/r/blob/<sha>/path#L10-L20`), never a bare `path:line`.
  - Outside facts: the primary source's URL, then the note and its source number: "[AWS pricing](https://…) ([research](<note path>) [4])".
  - A borrowed claim a work item or the Decision depends on should be CONFIRMED, corrected or re-cited in the note's Verification table. Mark any other *(unverified)*; if a work item would change were it wrong, add a spike question.
  - Every number is derived here from the code (say how) or cited to where it was derived.
- **Mark assumptions** about unobserved behaviour *(assumption)*; one that matters becomes a spike question.
- **Work items** W1, W2…, each a reviewable change that lands on its own, in order: what changes; the files, new ones marked; **Done when**, observable acceptance criteria (a command and its result, a test that goes red then green).
- **Effort** from reading the code, saying so. **Non-goals**. **Spike questions**: what reading can't settle, each with the cheapest experiment, or "None.". A mermaid **diagram** if the structure changes.
- **Status.** A house-format spec with no frontmatter gets a `Status: draft` line near the top, unless its convention marks status another way (a SHIPPED or SUPERSEDED banner).
- **No secrets**: no credentials, account IDs, state or tfvars values.
- **Spec files only**: in the repo, change only the spec (or its parts), its record and, in step 7, its spike results file.
- **Length.** Past about 3,000 words or seven work items, split it into `<date>-<slug>-1-<phase>.md`, `-2-<phase>.md`…, each naming the earlier as a prerequisite; steps 3–5 run per part.

Then run `${CLAUDE_PLUGIN_ROOT}/skills/spec/scripts/check-spec.py <spec> --repo <repo root> --read-at <commit>` (`--cite-repo <path>` for a new repo citing another) until it prints `RESULT: PASS`. Fix the WARN lines that are real.

## 4. Verify

Run `spec-verifier` (Agent runs) with this brief:

```
Spec: <absolute path>
Repo: <absolute repo root>
Cite repo: <absolute path of the repo the citations point into, or "same">
Read at: <commit in the cite repo, or "none">
Research note: <absolute path, or "none">
Today's date: <YYYY-MM-DD>
```

Tell the user in one line that the spec is being verified. End your turn.

In `finish` mode, start here: the repo is the spec's, and `cite-repo` and `read-at` come from its frontmatter or "Read at" line (else `HEAD`, saying drift can't be measured). Run the check, fix FAIL lines, and launch the verifier in `spec-verifier-finish`.
Before the verifier, move read-at on if the code has: run the check with `--drift`. For each `DRIFT: <path>:<range>` line, re-read those lines at HEAD (`${CLAUDE_PLUGIN_ROOT}/hooks/git-read.py -C <cite repo> show HEAD:<path>`) and fix the citation: new line numbers, or the fact restated if it changed. Then set `read-at` (and the Background's "Read at" line) to `git rev-parse --short HEAD`, and re-run the check until it prints `RESULT: PASS` and no `DRIFT:` line. A re-cite that changes no work item, Done when, Design or Decision isn't logged as `Not reviewed:` (step 6 item 4); one that does is.
If a cold review is saved, stop after step 5's item 5 and report as its item 7 does.

## 5. When the verifier finishes

1. **Record the round** in the record's `## Verification`: the date, `Confirmed: N of M` as given, and its `Plan holds` answer.
2. **Apply its fixes**:
   - MISCITED or WRONG: correct as given. UNSUPPORTED: find a supporting citation or mark *(assumption)*. INHERITED: derive or cite the number. UNTESTABLE: rewrite the Done when.
   - UNVERIFIED: mark *(unverified)*; if a work item depends on it, add a spike question or suggest `/research finish <note> "<claim>"`.
   - Missed files: add them to the work item, and to Effort if they change its size. `Plan holds: no`: revise the affected work items.
3. **Re-run** the check until it passes. If you revised work items for `Plan holds: no`:
   - run `spec-verifier` in `spec-verifier-2`, with the same brief plus `Round 2: <Wn, Wm> were revised after verification; re-check them.`;
   - add `- Verifier round 2 ran on <YYYY-MM-DD>: after verification.` to the record, tell the user, and end your turn;
   - when it returns, apply its fixes and carry on. There is no round 3: if it also says `Plan holds: no`, say so in the report and in Open questions.
4. **Status**: leave `draft`, or the house equivalent; the user moves it on.
5. **Link the notes.** Add the spec's `~` path to the research note's `related` (leave its status alone); for an idea note, also set `status: adopted`; for an accepted decision, add it to `related`. `git -C ~/notes add <files>`, then `git -C ~/notes commit -m 'spec: <title>' -- <files>`, following this session's attribution rules. Don't push. Leave the spec and record uncommitted.
6. **Launch the cold review**, unless one is saved or this is `quick` mode.
   - Read `${CLAUDE_PLUGIN_ROOT}/skills/cold-review/SKILL.md` and build the prompt for the kind `Implementation spec` from three of its sections: *Read the document in full* (that kind's table row and extra lines), *Gather pointers* and *Write the prompt* (the skeleton).
   - Fill in the repo root and cite repo; as entry points, the checks from step 2 (CI, Makefile or Taskfile targets, pre-commit, lint and policy config); as rules files, those from step 1; the research note, or "none". In `finish` mode, Glob for them.
   - Pointers only: no summary of the spec, your reasons, what you think is weak, or what the verifier found. One prompt per part of a split spec.
   - Run `cold-reviewer` (Agent runs), tell the user in one line, and end your turn.
7. **Quick mode ends here.** Report as step 6 item 1 says, without the review, then give step 6 item 6's hand-off to `/implement`. Say that `/spec finish <spec>` gives it a cold review.

## 6. When the reviewer finishes

1. **Report** one short line for each: the spec path; the plan in two sentences (how many work items, what W1 is); verification (`21 of 23 claims confirmed, 2 corrected`); research the code contradicted; the number of spike questions; the notes commit hash.
2. **Relay and save the review** as the first two items of `/cold-review`'s *When the reviewer finishes* say.
   - Its `Needs a run` rows are candidate spike questions, with "What would settle it" as the experiment: list them, and add only those the user picks in item 4.
   - Save it in the record without asking, as that section's *Offer* item says under *Saving*.
3. **Repo-prescribed review.** If the repo's process wants a review outside this session, offer `/cold-review prompt <spec>`.
4. **Fold in** what the user picks, from the `correctness` and `requirement` findings and the candidate spike questions.
   - Ask with one AskUserQuestion multiSelect question, up to four options, most important first (name any others in the question). Log each fold as that *Offer* item says under *Folding in*, and re-run the check.
   - If a fold changes a citation or number and no round 2 has run, run `spec-verifier` in `spec-verifier-2` with the Round 2 line and log `- Verifier round 2 ran on <YYYY-MM-DD>: after the cold review.`.
   - If round 2 already ran, launch none: name the changed claims in the report and suggest `/spec finish <spec>`.
   - Log a later change to a work item, Done when, the Design or the Decision the same way, `from spike S<n>` or `from the user`. No second full cold review; the one delta review of the `Not reviewed:` lines is `/cold-review <spec>`.
5. **Spikes.** Unless Spike questions says "None.", offer step 7.
6. **Next**, always: step 7, if it runs; `/spec finish <spec>` only after hand edits; `/cold-review <spec>` if there are `Not reviewed:` lines; `status: reviewed`; implement.
   Give the hand-off only once `check-spec.py` passes with `status: reviewed`: commit the spec, its record and its spike results (if any), then run `/implement <spec path>` in this same session. It checks them, implements the work items test first on a branch of its own, `implement/<spec basename>`, in a worktree beside the repo, and has each Done when re-run by a verifier. Then, still in this session, `/spec done <the spec's path in that worktree>`.

## 7. Spike

Read `${CLAUDE_PLUGIN_ROOT}/skills/spec/spike-step.md` and follow it. In `spike` mode, start there.

## 8. Done

Read `${CLAUDE_PLUGIN_ROOT}/skills/spec/done-step.md` and follow it. In `done` mode, start there.

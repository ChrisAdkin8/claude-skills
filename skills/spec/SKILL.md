---
name: spec
description: Turn a /research note into an implementation spec inside the repo it changes, grounded in the code with file:line citations, then check it and give it a cold review. Use when the user runs /spec, or asks to write a spec, plan or prompt file for changing or enhancing a repo, especially from a research note. Accepts a research note path or a description of the change; "quick" for a small change whose approach is settled (check and verify, no cold review or spikes); "finish <spec>" re-checks and verifies a spec after editing; "spike <spec>" runs its spike questions in sandboxed headless sessions and folds the answers back in; "done <spec>" settles a spec after it has been built.
argument-hint: [quick] <research note path> [direction] | [quick] <description of the change> | finish <spec path> | spike <spec path> | done <spec path>
allowed-tools: Read Grep Glob Edit(~/code/**) Edit(~/notes/**) Edit(~/.cache/spec-spikes/**) Bash(grep *) Bash(git rev-parse *) Bash(git status *) Bash(git ls-files *) Bash(git -C ~/notes status *) Bash(~/.claude/hooks/git-read.py *) Bash(git -C ~/notes add *) Bash(git -C ~/notes commit *) Bash(~/.claude/skills/spec/scripts/check-spec.py *) Bash(~/.claude/skills/research/scripts/check-note.py *) Bash(~/.claude/hooks/run-agent.sh *) Edit(~/.cache/agent-runs/**) Bash(~/.claude/skills/spec/scripts/prepare-spike.sh ~/.cache/spec-spikes/*) Bash(~/.claude/skills/spec/scripts/run-spike.sh ~/.cache/spec-spikes/*)
---

# Write an implementation spec

Request: $ARGUMENTS

Research answers "what should we do?" A spec answers "what exactly changes in this repo, and how will we know it worked?" The spec lives in the repo, next to the code it describes; it links the research note in `~/notes` rather than restating it.

1. **Frame**: pick the research note, the option, the repo, and where the spec goes.
2. **Read and interview**: read the code, then ask the user what neither the code nor the research settles.
3. **Write** and self-check with `check-spec.py`.
4. **Verify**: the `spec-verifier` agent, which hasn't seen this conversation, checks every citation, number and borrowed claim.
5. **Finish**: apply its fixes, link the notes, commit the notes, launch the cold review.
6. **Cold review**: the read-only `cold-reviewer` agent gives the spec one adversarial read, from `/cold-review`'s prompt skeleton. The user decides what to fold back in.
7. **Spike**: sandboxed, cost-capped experiments answer what reading can't (`spike-step.md`).
8. **Done** (after the build): record what the build did differently and settle the status (`done-step.md`).

**The spec and its record.** The spec is the plan. Everything that happens to it afterwards goes in its record, `<spec dir>/records/<basename>-record.md`, started from `~/.claude/skills/spec/record-template.md` the first time there's something to put in it: verifier rounds, the cold review and any delta review, the `Not reviewed:` log, spike routing and implementation notes. An older spec keeps that history inline (a `## Cold review` section at its end, `Not reviewed:` lines in Open questions); read it that way, and move it to a record when you next edit the spec.

This skill writes no code in the repo, and doesn't branch or commit there. Implementation happens in a separate session, from the spec.

Run `git log`, `git diff` and any `git -C <dir>` read through `~/.claude/hooks/git-read.py`, which refuses the options that write files or run programs. `git rev-parse`, `git status` and `git ls-files` from the working directory, and `git -C ~/notes add` and `commit`, run directly.

The checking rules live in `~/.claude/agents/spec-verifier.md`; the cold review's instructions are the prompt skeleton in `~/.claude/skills/cold-review/SKILL.md`. Don't restate either in a brief; edit those files to change them.

## Running an agent

The spec verifier and the cold reviewer run as headless, sandboxed sessions through `~/.claude/hooks/run-agent.sh` (its header says what the sandbox holds and what it writes):

1. With the Write tool, write the brief to `<run dir>/brief.md`, where `<run dir>` is `~/.cache/agent-runs/<repo dir name>--<spec basename>/<agent>`, e.g. `~/.cache/agent-runs/rag-forge--2026-09-24-x/spec-verifier`, so specs of the same name in two repos don't share one; a later round gets `<agent>-2`.
2. Run `~/.claude/hooks/run-agent.sh <agent> <repo root> <run dir>` with `run_in_background: true`, paths written with `~`. For several at once (one per part of a split spec), one call per agent in the same message.
3. When it finishes, read `<run dir>/reply.md`. Exit 3 means the run finished but the reply lacks the closing lines its agent file asks for: an API error such as "Request timed out", a budget stop, or a reply out of format. Send one follow-up (`--resume`) asking it to reply again, in full, in the format its instructions give; if that exits 3 too, tell the user and don't act on the reply. Any other non-zero exit means no reply: `run.err` and `run.json` there say why.

For a follow-up in the same session, Write `<run dir>/followup.md` and run the same command with `--resume` added.

## Modes

- `/spec <research note path> [direction]`: the main path. A direction narrows it: "option B", "only the Terraform part", "phase 1".
- `/spec <description of the change>`: no research note (`research: none`). Fine when the approach is settled. If it isn't (several viable options, unknown cost, an unfamiliar tool), suggest `/research` first, and continue only if the user wants to.
- `/spec quick <research note path or description>`: a small change whose approach is settled, e.g. a bug fix or a flag. Steps 1 to 5 run as usual, then it stops: no cold review, no spikes. It suits at most three work items and no spike questions; if the spec needs more, say so after step 3 and offer the full path, which `/spec finish <spec>` resumes later (it launches the cold review a quick spec skipped). Record it in the record's `## Verification` as `- Quick spec on <YYYY-MM-DD>: no cold review or spikes.`
- `/spec finish <spec path>`: skip to the check in step 3, after hand edits or when a session ended before verification.
- `/spec spike <spec path>`: step 7, for a spec whose cold review is done.
- `/spec done <spec path>`: step 8, after the work items have been built.

## 1. Frame

1. **Repo.** `git rev-parse --show-toplevel` must be a repo under `~/code`; otherwise ask for its path in one line and stop. Record `git rev-parse --short HEAD` as read-at. If `git status --porcelain` shows uncommitted changes, say so: citations to them may never be committed.
   - **A new repo** (no commits) has no code to cite. If the spec builds on another local repo, set `cite-repo:` to its `~` path and `read-at` to its short HEAD; every `path:line` then points into it. If there's nothing to cite, `read-at: none`. Code in a repo that isn't cloned locally is cited by URL at a fixed commit.
2. **Research note.**
   - Empty request: the note just discussed, or the newest in `~/notes/research/` whose `related` names this repo (`grep -lE '<repo path, with ~>([],/[:space:]]|$)' ~/notes/research/*.md`). Name it in one line if you picked it.
   - Read it in full, and the idea note in its `related`, if any.
   - `draft`, or `final` with no `## Verification` section: suggest `/research finish <note>` first, and continue only if the user says so. Without a Verification section, every borrowed claim a work item or the Decision depends on counts as unchecked.
   - Sources "Checked on" or Verification date over 90 days old: say so and suggest updating the research; continue unless told otherwise. `outdated`: stop and suggest `/research`.
   - If its `related` doesn't name this repo, its assumptions about the code are unchecked: check them in step 2. If it does, `git-read.py log --oneline <its read-at>..HEAD` shows how far the code has moved.
   - **Decision.** `grep -l '<note path, with ~>' ~/notes/decisions/*.md`. An `accepted` one is the chosen option; name it. Mention a `proposed` one. Ignore the rest.
3. **Option.** The accepted decision, else the note's Recommendation, unless the direction says otherwise. If the Recommendation is conditional or open, ask with AskUserQuestion, from the note's options, recommended first.
4. **Where the spec goes.** The repo's convention wins: read `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `docs/*method*`, `docs/*process*`, `docs/adr*`, and look for `prompts/`, `docs/specs/`, `docs/design/`, `rfcs/`. Follow a convention exactly (location, filename, sections, house style, and the process it prescribes around specs); where it conflicts with this skill, the repo wins. Otherwise write `docs/specs/YYYY-MM-DD-short-slug.md` from `~/.claude/skills/spec/template.md`.
5. **Existing specs.** `grep -ril '<key terms>'` in the spec location. If one covers this, ask whether to update it or write a new one. Never rewrite a spec marked done or superseded.
6. **Fresh session.** If this conversation has been implementing or debugging in this repo, say so and suggest a fresh session: an author who has just built something tends to defend it.

Tell the user in one or two lines: the research note, the option, and where the spec will land.

## 2. Read and interview

1. **Read the code the change touches**: entry points, files named in the research note's Context, config, manifests, Terraform or CI that would move, the tests covering them, and how the repo runs its checks. For a broad sweep use an Explore agent, then read what matters yourself. Record each fact with its `path:line`.
2. **Check the research against the code.** A contradiction goes in Background as a correction and in your report. If it undermines the Recommendation, stop and tell the user.
3. **Interview.** One AskUserQuestion call, up to four questions, only on what changes the spec and neither the research nor the code settles: scope, compatibility and migration, rollout, what "done" means. Ground each in what you read, recommended option first. Skip it if nothing is open.

## 3. Write

- **Self-contained.** The implementing session and the cold reviewer never saw this conversation.
- **Cite, don't restate.**
  - Repo facts get `path:line` or `path:start-end` from the (cite) repo root. Background says the date and commit it was read at ("Read at `<short sha>`" in a house-format spec without frontmatter). After a full citation, `(:48)` in the same paragraph means the same file.
  - Code in a repo not cloned locally: a URL at a fixed commit (`https://github.com/o/r/blob/<sha>/path#L10-L20`), never a bare `path:line`.
  - Outside facts: the primary source's URL from the note's Sources, then the note and its source number: "[AWS pricing](https://…) ([research](<note path>) [4])".
  - A borrowed claim that a work item or the Decision depends on should be CONFIRMED, corrected or re-cited in the note's Verification table; mark any other *(unverified)*, and if a work item would change were it wrong, add a spike question.
  - Every number is derived here from the code (say how) or cited to where it was derived.
- **Mark assumptions** about unobserved behaviour *(assumption)*; if one matters, it becomes a spike question.
- **Work items** W1, W2…, each a reviewable change that lands on its own, in order: what changes; the files touched, new ones marked; **Done when**, observable acceptance criteria (a command and its result, a test that goes red then green), written before any work.
- **Effort** from reading the code, saying so. **Non-goals**: what the research covered that this leaves out. **Spike questions**: what reading can't settle, each with the cheapest experiment, or "None.". A mermaid **diagram** if the structure changes.
- **Status.** A house-format spec with no frontmatter gets a `Status: draft` line near the top, unless its convention marks status some other way (a SHIPPED or SUPERSEDED banner is read as done or superseded). `check-spec.py` reads it; without one it can't hold the spec back from implementation (step 5, item 4).
- **No secrets**: no credentials, account IDs, state or tfvars values.
- **Spec files only**: in the repo, create or change only the spec (or its parts), its record and, in step 7, its spike results file.
- **Length.** A template spec fails the check above 4,000 words while live. Past about 3,000 words or seven work items, split it into `<date>-<slug>-1-<phase>.md`, `-2-<phase>.md`…, each landing on its own and naming the earlier as a prerequisite. Steps 3–5 then run once per part, verifiers launched together.

Then run `~/.claude/skills/spec/scripts/check-spec.py <spec> --repo <repo root> --read-at <commit>` (`--cite-repo <path>` for a new repo citing another) until it prints `RESULT: PASS`. Fix the WARN lines that are real.

## 4. Verify

Run `spec-verifier` (Running an agent) with this brief:

```
Spec: <absolute path>
Repo: <absolute repo root>
Cite repo: <absolute path of the repo the citations point into, or "same">
Read at: <commit in the cite repo, or "none">
Research note: <absolute path, or "none">
Today's date: <YYYY-MM-DD>
```

Tell the user in one line that the spec is written and being verified. End your turn.

In `finish` mode, start here. Take the repo from the spec's location, and `cite-repo` and `read-at` from its frontmatter or its "Read at" line (else `HEAD`, saying drift can't be measured). Run the check, fix FAIL lines, launch the verifier in the run dir `spec-verifier-finish` (`spec-verifier-finish-2` and so on if that exists: a run dir that's reused loses its replies). If a cold review is already saved, finish mode stops after step 5's item 5: no second cold review.

## 5. When the verifier finishes

1. **Record the round** in the record's `## Verification`: the date, `Confirmed: N of M` as given, and its `Plan holds` answer.
2. **Apply its fixes**: MISCITED or WRONG, correct as given. UNSUPPORTED: find a supporting citation or mark *(assumption)*. UNVERIFIED: mark *(unverified)*, and if a work item depends on it add a spike question or suggest `/research finish <note> "<claim>"`. INHERITED: derive or cite the number. UNTESTABLE: rewrite the Done when. Missed files: add them to the work item, and to Effort if they change its size. `Plan holds: no`: revise the affected work items.
3. **Re-run** the check until it passes. If you revised work items for `Plan holds: no`, run `spec-verifier` once more in `spec-verifier-2`, with the same brief plus `Round 2: <Wn, Wm> were revised after verification; re-check them.`, add `- Verifier round 2 ran on <YYYY-MM-DD>: after verification.` to the record, tell the user, and end your turn. When it returns, apply its fixes and carry on. There is no round 3: if round 2 also says `Plan holds: no`, say so in the report and in Open questions.
4. **Status**: leave `draft`, or the house equivalent. The user moves it on after the cold review (in quick mode, after the report). `reviewed` is the hand-off to implementation, and `check-spec.py` fails a `reviewed` or `in-progress` spec whose record logs `Not reviewed:` changes and no delta review.
5. **Link the notes.** Add the spec's `~` path to the research note's `related` (leave its status alone); for an idea note, also set `status: adopted`; for an accepted decision, add it to `related`. Commit only those files: `git -C ~/notes add <files>`, then `git -C ~/notes commit -m 'spec: <title>' -- <files>` (naming the files, so nothing another session staged comes too), following this session's attribution rules. Don't push. Leave the spec and record uncommitted in the repo for the user.
6. **Launch the cold review**, unless one is already saved or this is `quick` mode (one full adversarial round per spec). Read `~/.claude/skills/cold-review/SKILL.md` and build the prompt from its steps 3 and 4 for the kind `Implementation spec`, with: the repo root and cite repo; as entry points, the checks you read in step 2 (CI workflows, Makefile or Taskfile targets, pre-commit, lint and policy config; in `finish` mode find them now with a quick Glob); as rules files, those from step 1; the research note's path, or "none". Pointers only: no summary of the spec, your reasons, what you think is weak, or what the verifier found. One prompt per part of a split spec. Run `cold-reviewer` (Running an agent), tell the user in one line, and end your turn.
7. **Quick mode ends here.** Report as step 6 item 1 says, leaving out the review, then give step 6 item 5's implementation prompt. Say in one line that the spec had no cold review, and that `/spec finish <spec>` gives it one.

## 6. When the reviewer finishes

1. **Report** in six lines or fewer: the spec path; the plan in two sentences (how many work items, what W1 is); verification (`21 of 23 claims confirmed, 2 corrected`); research the code contradicted; the number of spike questions; the notes commit hash.
2. **Relay and save the review** as `/cold-review`'s step 5 items 1 and 2 say: don't edit the spec for its findings; one line per `correctness` or `requirement` finding; one line for the `neither` ones; where a cold read stopped. Rows its `Needs a run` line names become spike questions, with the experiment from "What would settle it". Then save it in the record, without asking, as its step 5 item 3 says under Saving: it stops a later `/spec finish` launching another.
3. **Repo-prescribed review.** If the repo's own process wants a review outside this session, offer `/cold-review prompt <spec>`.
4. **Fold in** the findings the user picks, from those graded `correctness` or `requirement`, and log each as its step 5 item 3 says. Re-run the check. If a fold adds or changes a citation or number and the record has no `Verifier round 2 ran on` line, run `spec-verifier` in `spec-verifier-2` with the Round 2 line and log `- Verifier round 2 ran on <YYYY-MM-DD>: after the cold review.`. If round 2 already ran (step 5 item 3), launch none: there is no round 3, so name the changed claims in the report and suggest `/spec finish <spec>` once the user has looked at them. Log a later change to a work item, Done when, the Design or the Decision the same way, `from spike S<n>` or `from the user`. No second full cold review; the one delta review of the `Not reviewed:` lines is `/cold-review <spec>`.
5. **Next**, unless Spike questions says "None.": offer step 7. The order after that: step 7; `/spec finish <spec>` only after hand edits; `/cold-review <spec>` if there are `Not reviewed:` lines; `status: reviewed`; implement. Don't give the implementation prompt while `check-spec.py` fails with `status: reviewed`. The prompt, for a fresh session on a branch in plan mode: "implement `<spec path>`, W1 first. First run `~/.claude/skills/spec/scripts/check-spec.py <spec path> --repo <repo root>`, and if it prints `RESULT: FAIL`, stop and say why". Then `/spec done <spec>`.

## 7. Spike

Read `~/.claude/skills/spec/spike-step.md` and follow it. In `spike` mode, start there.

## 8. Done

Read `~/.claude/skills/spec/done-step.md` and follow it. In `done` mode, start there.

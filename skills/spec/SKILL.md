---
name: spec
description: Turn a /research note into an implementation spec inside the repo it changes, grounded in the code with file:line citations, then check it and give it a cold review. Use when the user runs /spec, or asks to write a spec, plan or prompt file for changing or enhancing a repo, especially from a research note. Accepts a research note path or a description of the change; "finish <spec>" re-checks and verifies a spec after editing; "spike <spec>" runs its spike questions in sandboxed headless sessions and folds the answers back in.
argument-hint: <research note path> [direction] | <description of the change> | finish <spec path> | spike <spec path>
allowed-tools: Read Grep Glob Edit(~/code/**) Edit(~/notes/**) Edit(~/.cache/spec-spikes/**) Bash(grep *) Bash(git rev-parse *) Bash(git -C * rev-parse *) Bash(git status *) Bash(git log *) Bash(git diff *) Bash(git ls-files *) Bash(git -C ~/notes status *) Bash(git -C ~/notes diff *) Bash(git -C ~/notes add *) Bash(git -C ~/notes commit *) Bash(~/.claude/skills/spec/scripts/check-spec.py *) Bash(rm -rf ~/.cache/spec-spikes/*) Bash(mkdir -p ~/.cache/spec-spikes/*) Bash(mkdir -p ~/code/*) Bash(git -C * archive *) Bash(tar -x -C ~/.cache/spec-spikes/*) Bash(~/.claude/skills/spec/scripts/run-spike.sh ~/.cache/spec-spikes/*)
---

# Write an implementation spec

Request: $ARGUMENTS

Research answers "what should we do?" A spec answers "what exactly changes in this repo, and how will we know it worked?" The spec lives in the repo, next to the code it describes. The research stays in `~/notes`, and the spec links to it rather than restating it.

1. **Frame** (here): pick the research note, the option, the repo, and where the spec goes.
2. **Read and interview** (here): read the code, then ask the user what neither the code nor the research settles.
3. **Write** (here) and self-check with `check-spec.py`.
4. **Verify**: the `spec-verifier` agent, which hasn't seen this conversation, checks every citation, number and borrowed claim.
5. **Finish** (here): apply its fixes, link the notes, commit the notes.
6. **Cold review**: you write a review prompt for this spec, and the read-only `spec-reviewer` agent runs it. It looks for assumptions, uncounted costs and gaps a cold reader would hit, and grades each finding. It edits nothing; the user decides what to fold back in.
7. **Spike**: the spike questions an experiment can answer locally each run as a sandboxed, cost-capped `claude -p` session in a scratch copy of the code, and their verdicts are folded back into the spec.

This skill writes no code in the repo (a spike's throwaway code stays in its scratch directory), and it doesn't branch or commit in the repo. Implementation happens in a separate session, working from the spec.

The checking rules live in `~/.claude/agents/spec-verifier.md`. Don't restate them in briefs; edit that file to change them. The cold review works the other way round: its instructions are the prompt skeleton in step 5, and `~/.claude/agents/spec-reviewer.md` holds only its tools and safety rules. `/research` (`~/.claude/skills/research/SKILL.md`) produces the notes this skill starts from.

## Modes

- `/spec <research note path> [direction]`: the main path. A direction narrows or redirects it: "option B", "only the Terraform part", "phase 1".
- `/spec <description of the change>`: no research note. This is fine when the approach is already settled. If it isn't (several viable options, unknown cost, an unfamiliar tool), say so and suggest `/research` first. Continue only if the user wants to. Set `research: none`.
- `/spec finish <spec path>`: skip to the check in step 3. Use it after editing a spec by hand, or when a session ended before verification.
- `/spec spike <spec path>`: skip to step 7, for a spec whose cold review is done. Use it when step 7 wasn't run at the end of step 6.

## 1. Frame (in the conversation)

1. **Repo.** Run `git rev-parse --show-toplevel` from the working directory. It must be a repo under `~/code`; if it isn't, ask for the repo path in one line and stop. Record `git rev-parse --short HEAD` as the read-at commit.
   - If `git status --porcelain` shows uncommitted changes, say so: citations to those files will point at lines that may never be committed.
   - **A new repo** (`git rev-parse HEAD` fails: no commits yet) has no code to cite. If the spec builds on code in another local repo (fixtures, a library it wraps, the project it was split from), set `cite-repo:` to that repo's path (with `~`) and `read-at` to that repo's short HEAD (`git -C <that repo> rev-parse --short HEAD`). Every `path:line` citation then points into that repo, from its root, and the checker and verifier read them there. If there's nothing to cite, set `read-at: none`. Code in a repo that isn't cloned locally is cited by URL at a fixed commit, not as `path:line`.
2. **Research note.**
   - If the request is empty, use the research note just discussed. Failing that, take the newest note in `~/notes/research/` whose `related` names this repo (`grep -lE '<repo path, with ~>([],/[:space:]]|$)' ~/notes/research/*.md`; the trailing class stops `~/code/github.com/foo` matching `foo-bar`). If you picked it yourself, name it in one line so the user can redirect.
   - Read it in full, and the idea note in its `related`, if any.
   - `status: draft`: `/research` never finished verifying it, or it was edited since. Suggest `/research finish <note>` first, and continue only if the user says so.
   - `status: final` with no `## Verification` section: it was verified before the skill recorded which claims were checked, so there's no telling checked claims from unchecked ones. Suggest `/research finish <note>` first, and continue only if the user says so. If they do, every borrowed claim a work item or the Decision depends on counts as unchecked (step 3).
   - If the Sources "Checked on" date, or the Verification date if it's later, is more than 90 days old, say so: costs, versions and project health may have moved. Suggest re-running `/research` to update the note, and continue unless the user says otherwise.
   - `status: outdated`: stop and suggest re-running `/research`.
   - If the note's `related` doesn't include this repo, the research wasn't grounded in this code. Carry on, but check its assumptions against the code in step 2. If it does, its Context may name the commit it was read at; `git log --oneline <that commit>..HEAD` shows how far the code has moved since.
   - **Decision.** Look for a decision record that settles this research: `grep -l '<research note path, with ~>' ~/notes/decisions/*.md`. Read any you find. An `accepted` one is the chosen option; name it in one line. Mention a `proposed` one, since the choice may still be open. Ignore `rejected` and `superseded` ones.
3. **Option.** Take the accepted decision if there is one, otherwise the note's Recommendation, unless the direction says otherwise. If the Recommendation is conditional, or leaves the choice open, the choice is the user's. Ask with AskUserQuestion, using the options from the note's table, with the recommended one first.
4. **Where the spec goes, and its shape.** The repo's own convention comes first. Read `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, and any `docs/*method*`, `docs/*process*` or `docs/adr*` file. Look for existing spec directories: `prompts/`, `docs/specs/`, `docs/design/`, `rfcs/`.
   - **If the repo has a convention**, follow it exactly: location, filename, sections and house style. It overrides the template. For example, `k8s-ai-observability` writes specs as `prompts/prompt-<subject>.md` with numbered W-items, per its `docs/development-method.md`. Follow the process it prescribes around specs too (interview first, review rounds, spikes, a fresh session). Where it conflicts with this skill, the repo wins.
   - **If there's no convention**, write to `docs/specs/YYYY-MM-DD-short-slug.md` (today's date, 3–6 word lowercase hyphenated slug), starting from `~/.claude/skills/spec/template.md`.
5. **Existing specs.** `grep -ril '<key terms>'` in the spec location. If a spec already covers this, ask whether to update it or write a new one. Never rewrite a spec marked shipped, done or superseded; those are records.
6. **Fresh session.** If this conversation has already been implementing or debugging in this repo, say so: an author who has just built something tends to defend it. Suggest running `/spec` in a fresh session, and continue only if the user wants to.

Tell the user in one or two lines: the research note, the option, and where the spec will land. Then carry on to step 2.

## 2. Read and interview (in the conversation)

1. **Read the code the change touches.** That means the entry points, the files named in the research note's Context, and the config, manifests, Terraform or CI that would move. It also means the tests covering them and how the repo runs its checks (Makefile, Taskfile, CI workflows, any preflight). For a broad sweep, use an Explore agent, then read the files that matter yourself. Record each fact as you go, with its `path:line`.
2. **Check the research against the code.** Anything the research assumed about this repo that the code contradicts goes in Background as a correction, and in your report. If a contradiction undermines the Recommendation, stop before writing and tell the user; the research may need redoing.
3. **Interview.** Make one AskUserQuestion call with up to four questions. Ask only about implementation choices, edge cases and trade-offs that change the spec and that neither the research nor the code settles: scope boundaries, compatibility and migration, rollout, and what "done" means. Ground each question in what you read, with the recommended option first. If nothing is open, skip the interview.

## 3. Write

Write the spec at the path from step 1, in the repo's house style or the template.

- **Self-contained.** The implementing session and the cold reviewer never saw this conversation. If they would have to redo the digging to follow it, it isn't finished.
- **Cite, don't restate.**
  - Facts about the repo get a `path:line` or `path:start-end` citation, with the path given from the repo root (or the cite repo's root). Background says the date and commit it was read at; in a house-format spec with no frontmatter, write it as "Read at `<short sha>`" so the checker can find it. After a full citation, `(:48)` or `` `:48` `` in the same paragraph means the same file; the checker reads it that way.
  - Code in a repo that isn't cloned locally is cited by URL at a fixed commit, e.g. `https://github.com/o/r/blob/<sha>/path#L10-L20`, never as a bare `path:line`, which the check fails because nobody could check it.
  - Facts from outside the repo cite the primary source's URL, taken from the note's Sources entry, followed by the research note and its source number: "[AWS pricing](https://…) ([research](<path to note>) [4])". The URL is for readers who can't see `~/notes`: a teammate, a client, anyone reading a public repo. The note reference is for the verifier. Don't copy the note's other sources; the note owns them.
  - A borrowed claim that a work item or the Decision depends on should be one the note's `## Verification` table shows as checked: CONFIRMED, or resolved as corrected or re-cited. Mark any other *(unverified)*, including every such claim when the note has no Verification section. If a work item would change were it wrong, add a spike question.
  - Every number is either derived here from the code (say how) or cited to where it was derived.
- **Mark assumptions.** Anything asserted about behaviour nobody has observed gets *(assumption)*. If it matters, it becomes a spike question.
- **Work items.** Number them W1, W2 and so on. Make each one a reviewable change that can land on its own, in order. Each gives:
  - what changes;
  - the files touched, marking new ones;
  - **Done when**: acceptance criteria someone can observe, such as a command and its expected result, or a test that goes red and then green. Write these before any work is done.
- **Effort.** Estimate from reading the code, and say so. The ordering matters more than the numbers.
- **Non-goals.** Include anything the research covered that this spec deliberately leaves out.
- **Spike questions.** List what reading can't settle (a timing, a default, exact syntax, an interaction), each with the cheapest experiment that would answer it, or write "None."
- **Diagram.** Add a mermaid diagram if the design changes the structure.
- **No secrets.** Never copy secrets, credentials, account IDs, state file contents or tfvars values into the spec.
- **Spec files only.** In the repo, create or change only the spec file, or the spec files when splitting, and in step 7 its spike results file, `<spec dir>/spikes/<basename>-results.md`.
- **Length.** A draft template spec fails the check above 4,000 words. Past about 3,000, or past about seven work items, split it: one spec per phase, each landing on its own, named `<date>-<slug>-1-<phase>.md`, `-2-<phase>.md` and so on, the later ones naming the earlier as a prerequisite. A spec nobody can review in one sitting doesn't get reviewed, and the verifier only samples citations past about 40. Check, verify and link each part separately: steps 3–5 run once per file, with one verifier launched per part, all in the same message. A spec whose status is past `reviewed` is a record; the check only warns about its length.

Then run `~/.claude/skills/spec/scripts/check-spec.py <spec> --repo <repo root> --read-at <commit>`, adding `--cite-repo <path>` for a new repo that cites another. Fix every FAIL line and re-run until it prints `RESULT: PASS`. WARN lines are judgement calls: fix the ones that are real.

## 4. Verify

Launch the Agent tool with `subagent_type: spec-verifier` and this brief, filled in:

```
Spec: <absolute path>
Repo: <absolute repo root>
Cite repo: <absolute path of the repo the citations point into, or "same">
Read at: <commit in the cite repo, or "none">
Research note: <absolute path, or "none">
Today's date: <YYYY-MM-DD>
```

Tell the user in one line that the spec is written and being verified. End your turn.

In `finish` mode, start here. Take the repo from the spec's location, and `cite-repo` and `read-at` from its frontmatter; for a house-style spec with no frontmatter, use its "Read at `<sha>`" line, or `HEAD` if it has none (and say that drift can't be measured). Run the check, fix any FAIL lines yourself, then launch the verifier. If the spec already ends in a `## Cold review` section, finish mode stops after step 5's items 1 to 4: it re-checks, re-verifies and links, and launches no second cold review.

## 5. When the verifier finishes

1. **Apply its fixes** to the spec:
   - MISCITED or WRONG: correct the citation or the statement, as given.
   - UNSUPPORTED: find a citation that does support it, or mark it *(assumption)*. If a work item depends on it, add a spike question.
   - UNVERIFIED: mark the borrowed claim *(unverified)*. If a work item depends on it, add a spike question, or suggest `/research finish <note> "<claim>"`, which asks the research verifier to check that claim by name.
   - INHERITED: derive the number or cite where it comes from.
   - UNTESTABLE: rewrite that Done when so it can be observed.
   - Missed files: add them to the work item, and to Effort if they change the size.
   - `Plan holds: no`: revise the affected work items.
2. **Re-run** `check-spec.py` until it passes.
   - **If you revised work items for `Plan holds: no`**, they haven't been checked at all. Launch `spec-verifier` once more with the same brief plus `Round 2: <Wn, Wm> were revised after verification; re-check them.`, and add `- Verifier round 2 ran on <YYYY-MM-DD>: after verification.` to the spec's `## Open questions` (or the house equivalent), so step 7 knows there's no round left. Tell the user in one line what changed and that it's being re-checked. End your turn.
   - When round 2 returns, apply its fixes, re-run the check and carry on from step 3. There is no round 3: if round 2 also says `Plan holds: no`, say so plainly in the report and in the spec's Open questions.
3. **Status**: leave `status: draft`, or the house equivalent. The user moves it on once they've dealt with the cold review, not this skill.
4. **Link the notes.**
   - In the research note, add the spec's path (with `~`) to `related`. Don't change its status; `final` there means the research was verified, which is a separate question.
   - If there's an idea note, set `status: adopted` and add the spec's path to its `related`.
   - If there's an accepted decision, add the spec's path to its `related`.
   - Commit only those files: `git -C ~/notes add <files>`, then `git -C ~/notes commit` with the message `spec: <title>`, following this session's commit attribution rules. Don't push.
   - Leave the spec itself uncommitted in the repo. The user reviews it and commits it under the repo's own rules.
5. **Write the cold-review prompt and launch it,** unless the spec already has a `## Cold review` section: one adversarial round per spec (step 6, item 5). The verifier checked citations and numbers. Judging assumptions and costs needs a reader who didn't write the spec. Write the reviewer's prompt yourself, for this spec, and launch the Agent tool with `subagent_type: spec-reviewer` and that prompt. The agent brings only read-only tools and safety rules; everything it reviews for comes from your prompt.

   Build the prompt from this skeleton. Keep the core paragraph and the reply format word for word, so every review asks the same question and you can relay the answer; fill in the rest:

   ````
   Review <absolute spec path> adversarially. You haven't seen how it was written. Work from the spec, the code in <absolute repo root> (its path:line citations point into <cite repo, or "the same repo">), and what the spec links to. Today's date is <YYYY-MM-DD>.

   Find assumptions presented as facts, costs not counted (files, checks that will go red, migrations), and anything a cold reader can't work through without redoing the research. Grade each finding by whether it affects correctness or a stated requirement, and say which don't. Don't edit the file.

   How to go about it:
   - Read the spec once as its implementer would, W1 first, before opening the research note. Note each place you'd have to stop and go digging.
   - For each work item, `git grep` the names it changes (functions, flags, keys, values, metrics, paths) and work out which checks run over the files it touches. Starting points: <the check entry points you read in step 2: CI workflow files, Makefile or Taskfile targets, pre-commit, lint and policy config>. These are where to start, not the full list.
   - Stated requirements are the spec's Goal, Done when lines, Non-goals and Decision<, plus the repo's rules in: the rules files you read in step 1, e.g. CLAUDE.md, docs/development-method.md>.
   - Open <the research note path, or "the research note the spec links"> only where the spec leaves you stuck, to see whether the spec leans on it for something it should carry itself.<Add a line for anything else a stranger to this repo would need in order to find things, such as a generated-files directory or a second repo the change reaches into.>
   - Don't pad. A category with no findings is a valid result. Skip style and wording unless they stop a cold reader.

   Grades: `correctness` (built as written, the change is wrong: it breaks something, loses data, fails its own Done when, or can't be carried out); `requirement: "<the requirement, quoted>"`; or `neither: <why it doesn't matter>`.

   Reply with only a table, correctness rows first, then requirement, then neither:
   | # | Kind (ASSUMPTION, COST or COLD-READ) | Where (exact text from the spec, or e.g. "W2 Files") | Finding | Affects | Evidence (path:line, grep hit or config line) | What would settle it |
   Then one line each: `Counts: N findings — C correctness, R requirement, K neither`; `Neither: <row numbers, or none>`; `Cold read: yes`, or `Cold read: no — <first place you had to stop>`; `New spike questions: <row numbers, or none>`.
   ````

   In `finish` mode on a spec with no Cold review yet, you skipped step 2, so find the check entry points and rules files now with a quick Glob (`.github/workflows/*`, `Makefile`, `Taskfile*`, `.pre-commit-config.yaml`, `CLAUDE.md`, `docs/*method*`).

   What you add to the skeleton is pointers to where things are, never conclusions. Leave out a summary of the spec, why you made its choices, which parts you think are weak or sound, what the verifier found and what you changed. A reviewer handed the author's framing checks the framing instead of the spec. If the spec was split, write one prompt per part and launch the reviewers in the same message.

   Tell the user in one line that the spec is verified and under cold review. End your turn.

## 6. When the reviewer finishes

1. **Don't edit the spec for its findings.** The review is for the user to judge, and a reviewer asked to find gaps finds some whether or not any exist. Chasing all of them produces defensive over-engineering.
2. **Report** in six lines or fewer:
   - the spec path;
   - the plan in two sentences (how many work items, and what W1 is);
   - verification, e.g. `21 of 23 claims confirmed, 2 corrected`;
   - any research contradicted by the code;
   - the number of spike questions, including any the review adds;
   - the notes commit hash.
3. **Relay the review.** Its table isn't shown to the user, so pass it on:
   - The findings graded `correctness` or `requirement`: one line each, with the spec location, the finding and what would settle it.
   - The ones graded `neither`: one line in total, listing them and saying the reviewer judged they don't matter.
   - If it says `Cold read: no`, say where it had to stop.
   - If you think a finding is wrong, say so and why in one line, but leave it in the list. The user decides.
   - Then save the review in the spec: append the reviewer's table and its closing lines unchanged at the very end, under `## Cold review`, after a line "Reviewed on <YYYY-MM-DD> by spec-reviewer. Saved unchanged; not acted on." It's the record of the one adversarial round, and it stops a later `/spec finish` from launching another. `check-spec.py` leaves the section out of its word count and its citation, link and template checks, and the spec verifier skips it. Saving the record isn't acting on it, so item 1 stands.
4. **Repo-prescribed review.** If the repo prescribes its own review that a subagent doesn't satisfy (for example, `k8s-ai-observability`'s `docs/development-method.md` wants assumptions and costs reviewed by a cold session outside this one), say so, and give the user this prompt to paste into a fresh session:

   > Review `<spec path>` adversarially. Find assumptions presented as facts, costs not counted (files, checks that will go red, migrations), and anything a cold reader can't work through without redoing the research. Grade each finding by whether it affects correctness or a stated requirement, and say which don't. Don't edit the file.

5. **Next.** Offer to fold in the findings that affect correctness or a requirement. If the user says yes, fold in those they pick, re-run `check-spec.py` until it passes, and if a fold adds or changes a citation or number, launch `spec-verifier` with the Round 2 line naming the work items changed, and add `- Verifier round 2 ran on <YYYY-MM-DD>: after the cold review.` to the spec's Open questions. When it returns, apply its fixes and re-run the check, then report in one line; the notes are already linked. Don't run a second cold review: after one adversarial round the remaining risk is empirical, which is what the spikes are for.

   Once the fold-in is done (or declined), and unless `## Spike questions` says "None.", offer step 7 in one line, and go to it if the user says yes.

   After that, the order is: step 7 (or `/spec spike <spec>` later), then `/spec finish <spec>` only after hand edits (with a Cold review saved, it launches no second review), then implement. Implement in a fresh session on a branch, starting in plan mode: "implement `<spec path>`, W1 first".

## 7. Spike

Some spike questions can be answered by an experiment. Each of those runs as a headless `claude -p` session, sandboxed and capped at $2 and 60 turns, in a scratch copy of the code at read-at. Its verdict is then folded into the spec. The spiker's rules live in `~/.claude/skills/spec/spiker.md`, its sandbox and permission settings in `~/.claude/skills/spec/spike-settings.json`, and its launch command in `~/.claude/skills/spec/scripts/run-spike.sh`. Don't restate the rules in briefs; edit `spiker.md` to change them.

In `spike` mode, start here. Take the repo from the spec's location, and `cite-repo` and `read-at` from its frontmatter, or its "Read at `<sha>`" line, as `finish` mode does. If `## Spike questions` says "None.", say so and stop.

**Names.**
- `<basename>`: the spec's filename without `.md`, e.g. `2026-09-17-spec-spike-phase`.
- `<results>`: `<spec dir>/spikes/<basename>-results.md`. The spec cites it by its path from the repo root.
- `<scratch>`: `~/.cache/spec-spikes/<repo dir name>/<basename>/S<n>`, where `<n>` is the spike question's number.
- `<source repo>`: the spec's `cite-repo` if set, else the repo.

In every Bash call, write paths under the home directory with `~`, not expanded, or `allowed-tools` won't match them.

**Guard.** If any spike question already has an indented `Route:`, `Answered:`, `Partly answered:` or `Open:` line, refuse and say why: one spike round per spec, and that includes spikes run by hand.

### 7a. Triage

Give each question in `## Spike questions` one route:
- *spike*: the answer can be observed locally, or from allowlisted hosts, and a work item, Done when or Background claim changes with it;
- *research*: a doc settles it;
- *decision*: it's a preference, so it's the user's to answer;
- *deferred*: it needs credentials, a cloud account, a cluster, `docker`, code a work item hasn't built, or the repo's code when read-at is `none`.

If there are *spike* routes, ask one AskUserQuestion multiSelect question listing them, recommended first, up to four. With only one, add a second option, "Skip spikes", since a question needs at least two. With more than four, the rest become *deferred* with `Open: over the four-spike limit`. A *spike* the user doesn't pick gets `Open: not picked`.

Edit the spec. Under each chosen question, add these indented lines:
- `Route: spike`;
- `Changes:` the work items and quoted claims that change with the answer;
- `Expect:` what you expect the experiment to show, written now, before it runs;
- `Box: $2, 60 turns; hosts: <list, or none>`.

Under each of the others, add `Route: research`, `Route: decision` or `Open: <why>`. If no spike was chosen, skip to 7e.

### 7b. Run

For each chosen spike, in order:

1. Clear and make its scratch directory in one foreground Bash call: `rm -rf <scratch> && mkdir -p <scratch>/src`, or `mkdir -p <scratch>` when read-at is `none`. Unless read-at is `none`, export the code in a second foreground call: `git -C <source repo> archive <read-at> | tar -x -C <scratch>/src`. Don't chain the two; the combined call isn't pre-approved.
2. Write `<scratch>/spec.md`, a copy of the spec as it stands; the spiker's settings deny reads of `~/code`, so it can't read the original. Write `<scratch>/brief.md` with these fields and nothing else:
   - the question, verbatim;
   - its `Changes:`, `Expect:` and `Box:` lines;
   - `Runs:` 3 when timing, network or randomness is involved, else 1;
   - `Spec: spec.md`.
3. Read `~/.claude/skills/spec/spike-settings.json` and Write it to `<scratch>/settings.json`, with the spike's hosts in `sandbox.network.allowedDomains`. Change nothing else.

Then, in one message, make one Bash call per spike with `run_in_background: true`: `~/.claude/skills/spec/scripts/run-spike.sh <scratch>`. Don't `cd` to the scratch directory or call `claude` yourself; neither can be pre-approved. The script writes `run.json` and `run.err`, and the spiker writes `results.md`. `--max-budget-usd` stops a run only after the turn that crosses it, so a run can go over $2 by up to a turn.

Tell the user in one line which spikes are running. End your turn. Each run's completion notification arrives on its own; fold only once every run has returned.

### 7c. Fold

1. **Results file.** Bash `mkdir -p <spec dir>/spikes`. Write `<results>` with a `# Spike results: <spec title>` heading and the first spike's section, then Edit it to append one `## S<n>` section for each further spike. Each section is that spike's `results.md`, plus `total_cost_usd` and `num_turns` from its `run.json`. Record a spike as BLOCKED, with the reason from `run.err` or `run.json`, if `run.json` is missing, its `subtype` isn't `success`, or `results.md` is missing. Step 7b cleared the directory, so any `results.md` there is from this run.
2. **Fold each verdict** under its question in the spec:
   - EXPECTED: add `Answered: <the answer> (spike S<n>, <results>)`, and drop the *(assumption)* marks it settles.
   - DIFFERENT: add `Answered:` in the same form, and rewrite the work items, Done when lines and Background named in `Changes:`, citing `<results>`. If the answer contradicts the Decision, stop and tell the user, as step 2 does.
   - INCONCLUSIVE: add `Partly answered:` with the spread, and turn the question into a Done when or a question for the user.
   - BLOCKED: add `Open: run after Wn`, or `Open: <what it needs>`.

### 7d. Re-verify

Run `check-spec.py` as in step 3 until it prints `RESULT: PASS`. If a fold changed a work item or a Background claim:
- If `## Open questions` has no `Verifier round 2 ran on` line, launch `spec-verifier` with step 4's brief plus `Round 2: <Wn, Wm> were revised after spikes; re-check them.` and `Spike results: <absolute path of <results>>`. Add `- Verifier round 2 ran on <YYYY-MM-DD>: after spikes.` to Open questions. Tell the user in one line, and end your turn. When it returns, apply its fixes as in step 5 item 1 and re-run the check. There is no round 3.
- If a round 2 is already recorded, launch none, and tell the user to run `/spec finish <spec>` after reviewing the changes.

### 7e. Report

In four lines or fewer:
- the spike questions by route, naming any *research* claims (for `/research finish <note> "<claim>"`) and *decision* questions left for the user;
- each spike that ran, with its verdict;
- total cost and turns across the runs;
- whether round 2 ran, and that `<results>` should be committed with the spec.

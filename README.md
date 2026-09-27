# claude-skills

Personal Claude Code skills, agents and hooks that take an idea to a checked implementation plan,
called a *spec*. They research the idea, then write a spec for changing a repo. The spec cites the
lines of code it rests on, and fresh agents check both the research and the spec. They write no
code: that happens afterwards, in a new session, from the spec.

To try them, see [Requirements](#requirements), [Install](#install) and
[Set up `~/notes`](#set-up-notes).

A few terms used throughout:

- **Skill**: a set of instructions Claude Code loads when you type its command, such as `/research`.
  Each skill is a folder under `skills/`.
- **Hook**: a script Claude Code runs automatically at a set moment, such as before each tool call.
  This repo's hooks are in `hooks/`.
- **Agent**: a separate Claude run with its own instructions, launched to do one job, such as
  research a question or check a document.
- **Spec**: a plan for changing a repo, split into work items. Each item says what to change and
  how you'll know it's done.
- **Verifier**: an agent that checks each claim in a document against its source.
- **Cold review**: one adversarial read of a document by an agent that has seen none of the
  conversation that produced it.
- **Delta review**: a single follow-up review covering only the changes made since the cold review.
- **Spike**: a short, sandboxed experiment that answers a question that reading the code can't
  settle.
- **Record**: a file that holds a document's review history. It sits in a `records/` folder beside
  the document, so the document itself stays clean.
- **Sandbox** and **guard**: the two layers that limit what an agent can do. See
  [How the agents are contained](#how-the-agents-are-contained).

There are four commands. `/idea`, `/research` and `/spec` form one flow. `/cold-review` stands
apart: it gives any markdown file the same cold review `/spec` gives a spec. Notes live in
`~/notes`; specs live in the repo they describe.

## The workflow at a glance

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/workflow-narrow-dark.png">
  <img src="docs/workflow-narrow.png" alt="Workflow diagram. Six stages run in order: Capture with /idea, Research with /research,
Plan with /spec, Spike with /spec spike, Implement with /implement, and Close out with /spec done.
A research-verifier checks the research; check-spec.py, a spec-verifier and a cold-reviewer check
the spec. /spec quick skips the review and spikes, a spec edited after its review gets a delta
review before Implement, and an implementation that overturns the research loops back to update the
note. A band shows /cold-review's five steps for any markdown document, and another shows how every
agent is contained: its own headless session, an OS sandbox, a guard hook and cost
caps.">
</picture>

How to read it:

- It follows one change from idea to merged code, top to bottom.
- Each numbered stage shows the command you run, what it does and where its output goes.
- Under each command: whether the stage's work runs in your session, or in a *subagent*, a
  separate headless Claude session that hasn't seen your conversation.
- Purple boxes are the agents and scripts that check the work.
- The pink box is a check that runs only if the spec was edited after its cold review.
- Dashed lines are shortcuts and loops off the main path.
- The two bands at the bottom cover `/cold-review` and the limits every agent runs under.

## From idea to merged change

The six stages match the diagram.

1. **Capture: `/idea <description>`** files a note in `~/notes/ideas`.
2. **Research: `/research <question or idea note>`** researches it and writes a note to
   `~/notes/research`, citing a source for each claim. A `research-verifier` agent then checks the
   claims the note's conclusions depend on. It reports any it couldn't confirm from their sources.
   Last, `/research` rebuilds `~/notes/index.md`, a map of every note by topic
   ([view it as a mind map](#view-the-notes-as-a-mind-map)).
3. **Plan: `/spec <research note>`** writes a spec into the repo the change touches. The spec
   points at the code it relies on as `path:line`. The repo must be a git repo under `~/code`,
   because that's the only place `/spec` may edit files without asking. Three checks follow:
   - The `check-spec.py` script checks that every `path:line` points at lines that existed when
     the spec was written. It also checks that each work item says how you'll see it's done, and
     that no secrets or unfilled template text were left in.
   - A `spec-verifier` agent, which never saw the conversation, checks every citation, number and
     borrowed claim, and reports what doesn't hold.
   - A `cold-reviewer` agent gives the spec a cold review. It uses the same instructions as
     `/cold-review`, and looks for guesses stated as facts and costs nobody counted.

   The spec's record keeps the review word for word. It also keeps what the verifier found and
   what the spikes answered.

   You may change the spec after its review. If you do, the record lists each change as a
   `Not reviewed:` line. Run `/cold-review <spec>` to give those changes a delta review before you
   implement it. A spec's `status` says where it is, such as `draft`, `reviewed` (ready to
   implement), `in-progress` or `done`. While a spec has changes with no delta review,
   `check-spec.py` fails it if its status is `reviewed` or `in-progress`, so it can't be implemented
   by mistake.

   For a small change whose approach is settled, `/spec quick` stops after the verifier: no cold
   review, no spikes. `/spec finish <spec>` gives it the cold review later, and
   `/spec spike <spec>` runs any spikes.
4. **Spike: `/spec spike <spec>`**, or automatically at the end of `/spec`. Each spike runs as a
   separate Claude session in a scratch copy of the code, inside a sandbox and under a cost cap.
   It writes its verdict and raw output, and `/spec` then updates the spec with the answer.
5. **Implement: `/implement <spec>`**, planned in
   [two specs](docs/specs/2026-09-26-implement-skill-2-skill.md) and not built yet. It will hand the
   work to a subagent on its own git worktree and branch, then have a sandboxed verifier re-run
   each work item's Done when check. Until then, implement in a new session, working from the
   spec.
6. **Close out: `/spec done <spec>`**. It notes in the record where the implementation left
   the spec, marks the spec done, and points out any research the implementation proved
   wrong.

### A worked example

The [mind-map index](#view-the-notes-as-a-mind-map) went through every stage on 2026-09-27:

1. **Capture.** No idea note: the question went straight to `/research`.
2. **Research.** The note compared four ways to map the notes and recommended a generated Markmap
   outline. The verifier checked a sample of its claims, 14 of 37, and confirmed them all. The
   claim that Markmap draws an outline as a mind map wasn't in the sample; the spike confirmed it.
3. **Plan.** [The spec](docs/specs/2026-09-27-notes-mindmap-index.md) has seven work items. The
   spec-verifier found that one expected 37 idea notes when there were 40. The cold review found
   eight problems, such as a check that would pass without testing anything, because it called a
   script by a name the shell couldn't find. Both are in
   [its record](docs/specs/records/2026-09-27-notes-mindmap-index-record.md).
4. **Spike.** A prototype over the real notes showed that two levels of topics stay easy to read:
   5 areas, and at most 7 notes under any heading
   ([results](docs/specs/spikes/2026-09-27-notes-mindmap-index-results.md)).
5. **Implement.** One commit per work item, W1 first; two of them changed only `~/notes`, so they
   were committed there. Running `/research` for real found a counting bug the tests had missed.
6. **Close out.** `/spec done` wrote seven lines in the record on where the implementation left the
   plan, and marked the spec done.

## Cold review of any document

**`/cold-review <markdown file>`** hands a document (a walkthrough, runbook, README, design doc,
spec or research note) to a `cold-reviewer` agent. First, the skill works out what kind of document
it is and what its reader needs to do with it. Then it writes the instructions for the reviewer,
launches it, and passes on what it finds.

- **The reviewer only reads.** It checks what it can by reading the files a document points at,
  such as build scripts and config. Where a claim can only be settled by running a command, it
  says so rather than guessing the result.
- **You pick which findings get fixed.** The skill edits the document only for those. It asks
  before saving the review to the document's record. The one exception is a spec's delta review,
  which it saves without asking, as `/spec` does.
- **Each document gets one full review.** After that, running `/cold-review` again gives one delta
  review of the changes logged since, and no more.
- **`/cold-review prompt <file>`** writes the reviewer's instructions for you to run in a new
  session yourself, instead of launching an agent.

## Requirements

- **Claude Code 2.1.219 or later.** Agents and spikes rely on a sandbox setting added in that
  version. Nothing has been tried on an older one, so don't assume the sandbox works there. Last
  tested on 2.1.282.
- **macOS.** The sandbox settings are built around how Claude Code's sandbox behaves on macOS.
  They haven't been tried anywhere else. On Linux, the sandbox needs the `bubblewrap` tool, and
  the special case for `gh` (see [below](#how-the-agents-are-contained)) may not be needed.
- **`python3`** for the checkers and tests. Some spikes use `uv`.
- **A `~/notes` git repo**, set up as [below](#set-up-notes).

## Install

The files expect this repo at `~/code/github.com/claude-skills`, so clone it there:

```
git clone https://github.com/ChrisAdkin8/claude-skills.git ~/code/github.com/claude-skills
```

Claude Code looks for skills, agents and hooks in `~/.claude`. Move anything already at
`~/.claude/skills`, `~/.claude/agents` or `~/.claude/hooks` out of the way, then link each one to
this repo:

```
ln -s ~/code/github.com/claude-skills/skills ~/.claude/skills
ln -s ~/code/github.com/claude-skills/agents ~/.claude/agents
ln -s ~/code/github.com/claude-skills/hooks  ~/.claude/hooks
```

**Whatever branch is checked out here is what the agents run**, so an edit is live as soon as you
save it. The files refer to each other by `~/.claude/...` paths, which the links keep valid.

## Set up `~/notes`

The skills keep notes in `~/notes`, and this repo doesn't create it. It has to be a git repo,
because the skills commit to it. This repo doesn't include its files either, so you write your own:

- **`CLAUDE.md`**: your rules for notes, such as tags and frontmatter (the block of settings
  between `---` lines at the top of each note). The `researcher` agent reads it first. Give it a
  Topics section with a command that lists the topics in use, such as
  `grep -h '^topic:' ~/notes/research/*.md | sort | uniq -c`: the researcher picks a note's topic
  from that list, and `check-note.py` points there when a topic is new.
- **`templates/idea.md`**: the layout `/idea` starts each note from.
- **`decisions/`**, optional: notes you write by hand to record a choice the research left open.
  `/spec` follows an accepted decision over the research's recommendation.
- **`templates/research.md`** and **`templates/research-ideas.md`**: the layouts the `researcher`
  agent starts from, for a normal research note and for a ranked list of ideas. `check-note.py`
  fails a note that lacks the sections it expects, so copy its `REQUIRED` headings from
  [`check-note.py`](skills/research/scripts/check-note.py) into these. Give both a `topic:` line
  too: it also fails a note with no topic (see [below](#view-the-notes-as-a-mind-map)).
- **`projects/mindshare/attention-evidence.md`**, needed only for `/research ideas`. It's a table
  of past launches (repos, posts, demos) and how much attention each got: stars, shares, upvotes.
  `/research ideas` ranks ideas by how much attention they're likely to get, reads this table as
  evidence, and adds new rows to it.

`/idea` and `/research` need `~/notes`. `/spec` does too: it reads the research note there and
commits the links it adds. Only `/cold-review` works without it.

## View the notes as a mind map

Every research note has a `topic`, such as `kubernetes` or `claude-code/research-skill`: an area,
and optionally a sub-area under it. At the end of each run, `/research` rebuilds `~/notes/index.md`
from these topics. It's a nested outline: topics are headings, research notes are links under them,
and each idea or decision note sits under the research note it names. A note that has no topic, or
names no research note (a new `/idea`, say), goes under a heading called Unfiled. A mind map draws
that outline as a tree of bubbles branching out from the middle.

There are three ways to view it, easiest first:

1. **In VS Code.** The links open your notes.
   1. Install the [Markmap](https://marketplace.visualstudio.com/items?itemName=gera2ld.markmap-vscode)
      extension, by gera2ld.
   2. Open `~/notes/index.md`.
   3. Click the Markmap icon at the top right of the editor, or run **Markmap: Open as markmap**
      from the Command Palette (Cmd+Shift+P).

   The map opens beside the file, showing the first two levels. Click a bubble to open or close
   its branch, and click a note's title to open that note.
2. **In a web browser, as a single file:**

   ```
   npx markmap-cli --offline -o /tmp/notes-map.html ~/notes/index.md
   ```

   This draws the map into one web page and opens it. `npx` runs the tool without installing it
   for good. Saving the page to `/tmp` keeps an extra file out of your notes repo. Links to notes
   may not open from the browser.
3. **Without Markmap.** Open `~/notes/index.md` in any markdown viewer, such as GitHub, Obsidian or
   VS Code's normal preview. It shows the same tree as an indented list.

To rebuild the index by hand, for example after `/idea` adds a note, run
`~/.claude/skills/research/scripts/build-index.py ~/notes`. Don't edit `index.md` itself: the next
rebuild overwrites it.

## How the agents are contained

The skills launch every agent (the researcher, both verifiers and the cold reviewer) through
`hooks/run-agent.sh`. Each runs as a separate, *headless* Claude Code session: `claude -p` with no
one at the keyboard. They don't run inside your session, because Claude Code can't put a sandbox
around an agent that does. Two layers contain them.

- **The sandbox** ([`hooks/agent-sandbox.json`](hooks/agent-sandbox.json)): Claude Code's
  operating-system sandbox. Shell commands can't read credentials or secret environment variables,
  can't write under `~/code`, `~/notes` or `~/.claude`, and can reach only an allowed list of
  websites.
- **The guard** ([`hooks/agent-guard.py`](hooks/agent-guard.py)): a script Claude Code runs before
  each tool call, which can refuse it. It checks the agents' shell commands, file reads and
  writes, searches and web fetches. It keeps credentials out of their reach, since a fetched page
  could trick an agent into sending them out in a web address. It also hides session history (past
  conversations and earlier agent runs), so a verifier or cold reviewer can't see how the document
  it checks was written.

Some things run outside the sandbox, and not all of them are checked by the guard:

- `gh`, and the three research scripts that need credentials or call `gh` (`repo-health.sh`,
  `gcp-skus.sh`, `reddit-search.sh`). On macOS, `gh` can't make secure web connections inside the
  sandbox, so `agent-sandbox.json` lets these run outside it. They're still shell commands, so the
  guard checks them.
- Claude Code's own file-reading and web-fetching tools, which the sandbox never covers. The guard
  checks both, and Claude Code's permission settings also block reads of sensitive files.
- Web search and the researcher's documentation servers (AWS and Terraform). **Nothing checks
  these.** The only limit is which agents may use them. Web search is given to the researcher and
  the research-verifier. The documentation servers are given only to the researcher. Each agent's
  file lists its tools by name.

Every agent is also told these rules: [`hooks/agent-sandbox.md`](hooks/agent-sandbox.md) is added
to its instructions, with the list of allowed websites filled in from the sandbox settings.

Spikes are contained differently. They don't run under the guard; their own sandbox settings,
[`skills/spec/spike-settings.json`](skills/spec/spike-settings.json), contain them.

## What things cost

- **Each agent run** is capped at $5, or $10 for the researcher. The `RUN_AGENT_MAX_USD`
  environment variable overrides both.
- **Each spike** is capped at $2 and 60 turns. Assume a spike that fetches anything from the web
  costs close to the cap.
- **The agent evaluations** (see [Checks](#checks)) spend real money too. Three full runs of
  their ten cases on 2026-09-27 cost between $3.70 and $4.46. Each case is capped at $5 (the
  `research-ideas` case at $10), and the cases run at the same time, so a run that goes wrong can
  cost far more.
- **The skill evaluations** cost about $0.30 each, capped at $3 each.

A cap stops a run only after the turn that crosses it, so a run can go over by up to one turn. A
*turn* is one step of a run: Claude replies once, and may use a tool.

## Layout

| Path | What it is |
|---|---|
| `skills/idea/` | `/idea` |
| `skills/research/` | `/research` |
| `skills/research/ideation-rules.md`, `ideas-finish.md` | the extra steps for `/research ideas` |
| `skills/research/scripts/check-note.py` | checks a research note |
| `skills/research/scripts/mdcheck.py` | markdown helpers shared by `check-note.py`, `check-spec.py` and `build-index.py` |
| `skills/research/scripts/build-index.py` | rebuilds `~/notes/index.md`, the notes by topic; `/research` runs it before its commit |
| `skills/research/scripts/repo-health.sh`, `gcp-skus.sh`, `reddit-search.sh` | gather evidence for the `researcher` agent |
| `skills/spec/` | `/spec` |
| `skills/spec/scripts/check-spec.py` | checks a spec |
| `skills/spec/template.md`, `record-template.md` | the layouts of a spec and its record |
| `skills/spec/done-step.md` | the steps for `/spec done` |
| `skills/spec/spike-step.md` | the steps for running spikes |
| `skills/spec/spiker.md` | the rules a spike session follows |
| `skills/spec/spike-settings.json` | a spike's sandbox and permission settings |
| `skills/spec/scripts/prepare-spike.sh` | makes the scratch copy of the code for a spike |
| `skills/spec/scripts/run-spike.sh` | launches a spike |
| `skills/cold-review/` | `/cold-review`; `/spec` builds its cold review from this skill's instructions |
| `skills/cold-review/scripts/review-state.py` | works out which review a document is due, and what has changed since its last one |
| `agents/` | `researcher`, `research-verifier`, `spec-verifier`, `cold-reviewer` |
| `hooks/run-agent.sh` | launches an agent; exits with code 3 when a reply lacks its expected ending, so an error is never mistaken for a verdict |
| `hooks/agent-sandbox.json` | the agents' sandbox settings |
| `hooks/agent-sandbox.md`, `sandbox-prompt.py` | the rules added to every agent's instructions |
| `hooks/agent-guard.py` | the guard |
| `hooks/git-read.py` | runs read-only git commands for `/spec` and `/cold-review` |
| `docs/specs/` | the specs for changes to this repo; spike results are in `docs/specs/spikes/` |
| `docs/workflow*.png` | the diagram, drawn by `docs/diagram/workflow.py` |
| `records/` | the review history of this README |
| `tests/test_*.py` | fast tests for the guard, the two checkers (`check-note.py` and `check-spec.py`), `build-index.py`, `review-state.py`, `prepare-spike.sh` and `run-agent.sh` |
| `tests/replay_guard.py` | runs real recorded commands and file reads through the guard |
| `tests/agent-evals/` | runs the verifiers and the cold reviewer against documents with planted mistakes, and the researcher on sample questions |
| `tests/skill-evals/` | runs whole skills against throwaway repos |

## Checks

```
python3 -m unittest discover -s ~/code/github.com/claude-skills/tests   # seconds, free
python3 ~/code/github.com/claude-skills/tests/replay_guard.py           # seconds, free
~/code/github.com/claude-skills/tests/agent-evals/run.sh                # minutes, costs money
~/code/github.com/claude-skills/tests/skill-evals/run.sh                # minutes, costs money
```

Run the agent evaluations by hand after changing an agent or skill file, and the skill evaluations
after changing a skill's steps. Record the results of both in
[`tests/agent-evals/BASELINE.md`](tests/agent-evals/BASELINE.md).

## Licence

MIT, so copy what's useful into your own `~/.claude`. See [`LICENSE`](LICENSE).

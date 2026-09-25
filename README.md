# claude-skills

Personal Claude Code skills, agents and hooks that take an idea to a checked implementation plan,
called a *spec*. They research the idea, then write a spec for changing a repo. The spec cites the
lines of code it rests on, and fresh agents check both the research and the spec. They write no
code: that happens afterwards, in a new session, from the spec.

To try them, see [Requirements](#requirements), [Install](#install) and
[Set up `~/notes`](#set-up-notes).

A few terms used throughout:

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
Plan with /spec, Spike with /spec spike, Build in a new session, and Close out with /spec done. A
research-verifier checks the research; check-spec.py, a spec-verifier and a cold-reviewer check
the spec. /spec quick skips the review and spikes, a spec edited after its review gets a delta
review before Build, and a build that overturns the research loops back to update the note. A
band shows /cold-review's five steps for any markdown document, and another shows how every agent
is contained: its own headless session, an OS sandbox, a guard hook and cost
caps.">
</picture>

How to read it:

- It follows one change from idea to merged code, top to bottom.
- Each numbered stage shows the command you run, what it does and where its output goes.
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

   The spec's record keeps the review word for word, along with what the verifier found and what
   the spikes answered. If you change the spec after its review, the record lists each change as a
   `Not reviewed:` line. Run `/cold-review <spec>` to give those changes a delta review before you
   build. Until then, `check-spec.py` won't pass a spec that's marked ready to build or being built.

   For a small change whose approach is settled, `/spec quick` stops after the verifier: no cold
   review, no spikes. `/spec finish <spec>` gives it the cold review later, and
   `/spec spike <spec>` runs any spikes.
4. **Spike: `/spec spike <spec>`**, or automatically at the end of `/spec`. Each spike runs as a
   separate Claude session in a scratch copy of the code, inside a sandbox and under a cost cap.
   It writes its verdict and raw output, and `/spec` then updates the spec with the answer.
5. **Build** in a new session, working from the spec.
6. **Close out: `/spec done <spec>`**. It notes in the record where the build left the spec,
   marks the spec done, and points out any research the build proved wrong.

For a finished example, see [the spike-phase spec](docs/specs/2026-09-17-spec-spike-phase.md) and
its spike results in [`docs/specs/spikes/`](docs/specs/spikes/).

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

- **`CLAUDE.md`**: your rules for notes, such as tags and frontmatter. The `researcher` agent
  reads it first.
- **`templates/idea.md`**: the layout `/idea` starts each note from.
- **`templates/research.md`** and **`templates/research-ideas.md`**: the layouts the `researcher`
  agent starts from, for a normal research note and for a ranked list of ideas. `check-note.py`
  fails a note that lacks the sections it expects, so copy its `REQUIRED` headings from
  [`check-note.py`](skills/research/scripts/check-note.py) into these.
- **`projects/mindshare/attention-evidence.md`**, needed only for `/research ideas`. It's a table
  of past launches (repos, posts, demos) and how much attention each got: stars, shares, upvotes.
  `/research ideas` ranks ideas by how much attention they're likely to get, reads this table as
  evidence, and adds new rows to it.

`/idea` and `/research` need `~/notes`. `/spec` does too: it reads the research note there and
commits the links it adds. Only `/cold-review` works without it.

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
- **The agent evaluations** (see [Checks](#checks)) spend real money too. Their full run of ten
  cases on 2026-09-25 cost $4.02. Each case is capped at $5, and the cases run at the same time,
  so a run that goes wrong can cost far more.
- **The skill evaluations** cost about $0.30 each, capped at $3 each.

A cap stops a run only after the turn that crosses it, so a run can go over by up to one turn.

## Layout

- `skills/idea/`: `/idea`.
- `skills/research/`: `/research`, with:
  - `ideation-rules.md` and `ideas-finish.md`, the extra steps for `/research ideas`;
  - `scripts/check-note.py`, which checks a research note, and `scripts/mdcheck.py`, markdown
    helpers it shares with `check-spec.py`;
  - `scripts/repo-health.sh`, `gcp-skus.sh` and `reddit-search.sh`, which the `researcher` agent
    runs to gather evidence.
- `skills/spec/`: `/spec`, with:
  - `scripts/check-spec.py`, `template.md` (the spec's layout) and `record-template.md`;
  - `done-step.md`, the steps for `/spec done`;
  - for spikes:
    - `spike-step.md`, the steps for running spikes;
    - `spiker.md`, the rules a spike session follows;
    - `spike-settings.json`, its sandbox and permission settings;
    - `scripts/prepare-spike.sh`, which makes the scratch copy of the code;
    - `scripts/run-spike.sh`, which launches the spike.
- `skills/cold-review/`: `/cold-review`. `scripts/review-state.py` works out which review a
  document is due and what has changed since its last one. `/spec` builds its cold review from
  this skill's instructions.
- `agents/`: `researcher`, `research-verifier`, `spec-verifier`, `cold-reviewer`.
- `hooks/`:
  - `run-agent.sh`, which launches an agent. It exits with code 3 when a reply is missing its expected
    ending, so an error is never mistaken for a verdict;
  - `agent-sandbox.json`, the agents' sandbox settings;
  - `agent-sandbox.md` and `sandbox-prompt.py`, the rules added to every agent's instructions;
  - `agent-guard.py`, the guard;
  - `git-read.py`, which runs read-only git commands for `/spec` and `/cold-review`.
- `docs/`:
  - `specs/`, the specs for changes to this repo, with their spike results in `specs/spikes/`;
  - `workflow*.png`, the diagram, drawn by `diagram/workflow.py`.
- `records/`: the review history of this README.
- `tests/`:
  - `test_*.py`, fast tests for the guard, both checkers, `review-state.py`, `prepare-spike.sh`
    and `run-agent.sh`;
  - `replay_guard.py`, which runs real recorded commands and file reads through the guard;
  - `agent-evals/`, which runs the verifiers and the cold reviewer against documents with planted
    mistakes, and the researcher on sample questions;
  - `skill-evals/`, which runs whole skills against throwaway repos.

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

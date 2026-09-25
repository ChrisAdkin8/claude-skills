# claude-skills

Personal Claude Code skills, agents and hooks that take an idea to a checked implementation plan.
They research the idea, write a plan for changing a repo that cites the code it rests on, and have
fresh agents check both. They write no code: that happens afterwards, in a fresh session, from the
plan.

There are four commands. `/idea`, `/research` and `/spec` form one flow. `/cold-review` stands
apart, and gives any markdown file the same cold review `/spec` gives a spec. Notes live in
`~/notes`; specs live in the repo they describe.

A few terms used throughout:

- **Cold review**: one adversarial read of a document by an agent that has seen none of the
  conversation that produced it.
- **Delta review**: a single follow-up review covering only the changes made since the cold review.
- **Spike**: a short, sandboxed experiment that answers a question reading the code can't settle.
- **Record**: `records/<basename>-record.md` beside a document. It holds the document's review
  history, so the document itself stays what its readers came for.

## The workflow at a glance

The diagram below follows one change from idea to merge. Each numbered stage shows the command
you run, what it does and where its output lands; the purple boxes are the agents and scripts
that check the work. The dashed lines are the routes off the main path, and the two bands at the
bottom cover `/cold-review` and how every agent is kept contained. The sections after it explain
each part in words.

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

## How a change flows through it

1. **`/idea <description>`** files a note in `~/notes/ideas`.
2. **`/research <question or idea note>`** researches it and writes a cited note to
   `~/notes/research`. A `research-verifier` agent then checks each claim the note's conclusions
   rest on against its source, and says which it couldn't confirm.
3. **`/spec <research note>`** writes an implementation spec into the repo the change touches,
   with `path:line` citations to the code. That repo must be a git repo under `~/code`, since
   `/spec`'s pre-approved edits cover only `~/code/**`. Three checks follow:
   - `check-spec.py` checks mechanically that every citation points at lines that existed at the
     commit the spec was read at, that work items have observable acceptance criteria, and that no
     secrets or template text got left in.
   - A `spec-verifier` agent, which never saw the conversation, checks every citation, number and
     borrowed claim, and reports what doesn't hold.
   - A `cold-reviewer` agent gives the spec a cold review, from the same prompt skeleton as
     `/cold-review`, looking for assumptions stated as facts and costs nobody counted.

   The review is saved unchanged in the spec's record, with the verifier rounds, spike routing and
   implementation notes. Changes made to the spec after the review are logged there as
   `Not reviewed:` lines, and `/cold-review <spec>` gives them a delta review before
   implementation. `check-spec.py` fails a spec marked `reviewed` or `in-progress` until it has.

   For a small change whose approach is settled, `/spec quick` stops after the verifier: no cold
   review, no spikes. `/spec finish <spec>` gives it the rest later.
4. **Spikes** run at the end of `/spec`, or later with `/spec spike <spec>`. Each runs as a
   sandboxed, cost-capped `claude -p` session in a scratch copy of the code, writes a verdict with
   its raw output, and has that folded back into the spec.
5. **Implementation** happens in a fresh session, from the spec. Afterwards, `/spec done <spec>`
   writes down in the record where the build departed from the spec, settles its status, and flags
   research the build overturned.

`docs/specs/2026-09-17-spec-spike-phase.md` is a worked example of the output, with its spike
results beside it in `docs/specs/spikes/`.

## Cold review of any document

**`/cold-review <markdown file>`** hands a document (a walkthrough, runbook, README, design doc,
spec or research note) to a `cold-reviewer` agent. The skill works out what kind of document it is
and what a cold reader has to be able to do with it, writes the review prompt, and relays the
findings.

- **The reviewer is read-only.** It settles what it can by reading the Taskfile, CLI and config a
  document points at, and names the findings that need a command run instead of guessing at
  output.
- **The skill edits the document only for findings you pick.** It saves the review in the
  document's record, and asks first. The exception is a spec's delta review, which it saves
  without asking, as `/spec` does.
- **Each document gets one full review.** On a document with a saved review, it runs one delta
  review of the changes logged since, and no more.
- **`/cold-review prompt <file>`** writes the prompt for you to run in a fresh session, instead of
  launching an agent.

## Requirements

- **Claude Code 2.1.219 or later.** Every agent and every spike runs with `sandbox.*` settings
  passed with `--settings`, and `strictAllowlist` there needs 2.1.219. Nothing has been run on an
  older version, so don't assume the sandbox holds on one. Last run on 2.1.282.
- **macOS.** Every agent and spike runs in Claude Code's sandbox, which is Seatbelt on macOS.
  `agent-sandbox.json` and `skills/spec/spiker.md` are built around how it behaves there,
  including Go binaries such as `helm` and `gh` failing TLS inside it. Neither has been run
  anywhere else; on Linux the sandbox needs bubblewrap, and `gh` may not need excluding.
- **`python3`** for the checkers and tests. Some spikes use `uv`.
- **A `~/notes` git repo**, set up as below.

## Install

Claude Code reads these from `~/.claude`, so each directory there is a symlink into this repo:

```
ln -s ~/code/github.com/claude-skills/skills ~/.claude/skills
ln -s ~/code/github.com/claude-skills/agents ~/.claude/agents
ln -s ~/code/github.com/claude-skills/hooks  ~/.claude/hooks
```

Move anything already at those paths out of the way first. The files refer to themselves by their
`~/.claude/...` paths, which the symlinks keep valid, and the guard resolves those paths so it
recognises its own skill scripts through the links. Whatever branch is checked out here is what the
agents run.

## Set up ~/notes

The skills keep notes in `~/notes`, and this repo doesn't create it. It has to be a git repo (the
skills commit to it) holding:

- `CLAUDE.md`, the notes' conventions (tags, frontmatter), which the researcher reads first;
- `templates/idea.md`, `templates/research.md` and `templates/research-ideas.md`, which `/idea` and
  the researcher start from, and `check-note.py` checks notes against;
- for `/research ideas`, `projects/mindshare/attention-evidence.md`, the table of launches and
  their scores that ranking by mindshare reads and adds to.

`/spec` needs it too: it reads the research note there, and commits the links it adds. Only
`/cold-review` works without it. Every agent run passes `~/notes` to `claude` as a working
directory (`--add-dir`), but a missing directory doesn't stop the run.

## How the agents are contained

The skills launch every agent (the researcher, both verifiers and the cold reviewer) through
`hooks/run-agent.sh`, as a headless `claude -p --agent <name>` session: a separate Claude Code run
with no one at the keyboard. They don't run as in-session subagents, because the sandbox can't be
set for one. Two layers contain them.

- **The sandbox** (`hooks/agent-sandbox.json`): Claude Code's OS sandbox. Bash gets no credential
  reads, no secret environment variables, no writes under `~/code`, `~/notes` or `~/.claude`, and
  network access only to an allowlist.
- **The guard** (`hooks/agent-guard.py`): a PreToolUse hook, a script Claude Code runs before each
  tool call, which can refuse it. The agents' Bash, Read, Grep, Glob, WebFetch, Write and Edit
  calls go through it. It keeps credentials out of their reach, since a fetched page could get
  them sent out in a request URL. It also hides session history (transcripts, prompt history,
  earlier agent runs), so a verifier or cold reviewer can't see how the document it checks was
  written.

Some things run outside the sandbox, and not all of them are checked by the guard:

- `gh`, and the three research scripts that need credentials or loop over `gh` (`repo-health.sh`,
  `gcp-skus.sh`, `reddit-search.sh`). `agent-sandbox.json` lists them in `excludedCommands`,
  since Go CLIs fail TLS under the macOS sandbox. They are Bash commands, so the guard checks them.
- The Read and WebFetch tools, which the sandbox never covers. The guard checks both, and
  permission deny rules also cover Read.
- The WebSearch tool and the researcher's MCP servers (AWS and Terraform documentation). **No hook
  checks these.** The only limit is which agents may use them: WebSearch is granted to the
  researcher and the research-verifier, and the MCP tools only to the researcher, each listed by
  name in its agent file's `tools:` line.

Every agent also gets `hooks/agent-sandbox.md` appended to its prompt, so it knows these rules. The
host list in it is filled in from the settings by `hooks/sandbox-prompt.py`, so no agent file keeps
its own copy. `run-agent.sh` exits 3 when the reply lacks the closing lines its agent file asks
for, so an API error is never read as a verdict.

Spikes are contained differently. The spiker isn't one of these agents and doesn't run under the
guard; its own sandbox settings, `skills/spec/spike-settings.json`, contain it.

## What things cost

- **Each agent run** is capped at $5, or $10 for the researcher. `RUN_AGENT_MAX_USD` overrides
  both.
- **Each spike session** is capped at $2 and 60 turns. Assume a spike that fetches anything costs
  near the cap.
- **The agent evaluations** spend real tokens too. The latest full run of their ten cases cost
  $4.02. Each case is capped at $5 (`EVAL_MAX_USD`, or a case's own `usd.txt`), and the cases run
  in parallel, so a run that goes wrong can cost far more. `tests/agent-evals/BASELINE.md` records
  every run.
- **The skill evaluations** cost about $0.30 each, and are capped at $3 each (`EVAL_MAX_USD`).

A cap stops a run only after the turn that crosses it, so a run can go over by up to one turn.

## Layout

- `skills/idea/`: `/idea`.
- `skills/research/`: `/research`, with:
  - `ideation-rules.md` (the researcher's rules at `ideas` depth, read only then) and
    `ideas-finish.md` (the skill's last steps at `ideas` depth);
  - `scripts/check-note.py`, and `scripts/mdcheck.py`, the markdown helpers it shares with
    `check-spec.py`;
  - the helpers the `researcher` agent runs while gathering evidence (`repo-health.sh`,
    `gcp-skus.sh`, `reddit-search.sh`).
- `skills/spec/`: `/spec`, with:
  - `scripts/check-spec.py`, `template.md` and `record-template.md`;
  - `done-step.md` (step 8, read only by `/spec done`);
  - for spikes: `spike-step.md` (step 7, read only when spikes run), `spiker.md` (the rules a
    spike session runs under), `spike-settings.json` (its sandbox and permission settings),
    `scripts/prepare-spike.sh` (clears a scratch directory and exports the code into it, after
    checking its paths) and `scripts/run-spike.sh` (the launcher).
- `skills/cold-review/`: `/cold-review`. `scripts/review-state.py` works out which review a
  document is due and what changed since its last one. `/spec` builds its cold review from this
  skill's prompt skeleton.
- `agents/`: `researcher`, `research-verifier`, `spec-verifier`, `cold-reviewer`.
- `hooks/`: `run-agent.sh` (the agent launcher), `agent-sandbox.json` (the agents' sandbox
  settings), `agent-sandbox.md` and `sandbox-prompt.py` (the rules added to every agent's prompt),
  `agent-guard.py` (the guard), and `git-read.py`, which runs a read-only git command after the
  guard's git checks, for `/spec` and `/cold-review`. See
  [How the agents are contained](#how-the-agents-are-contained).
- `tests/`:
  - deterministic tests (`test_*.py`) for the guard, both checkers, `review-state.py`,
    `prepare-spike.sh` and `run-agent.sh`;
  - `replay_guard.py`, a replay of real recorded commands and file reads through the guard;
  - `agent-evals/`, which runs the verifier and cold-reviewer agents against planted defects and
    the researcher at quick and ideas depth (its note graded with `check-note.py`);
  - `skill-evals/`, which runs whole skills against throwaway repos.

## Checks

```
python3 -m unittest discover -s ~/code/github.com/claude-skills/tests   # seconds, free
python3 ~/code/github.com/claude-skills/tests/replay_guard.py           # guard vs real commands and reads
~/code/github.com/claude-skills/tests/agent-evals/run.sh                # minutes, costs tokens
~/code/github.com/claude-skills/tests/skill-evals/run.sh                # minutes, costs tokens
```

Run the agent evaluations by hand after changing an agent or skill file, and the skill evaluations
after changing a skill's steps. Record both in `tests/agent-evals/BASELINE.md`.

## Licence

MIT, so copy what's useful into your own `~/.claude`. See `LICENSE`.

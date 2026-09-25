# claude-skills

Personal Claude Code skills, subagents and hooks for taking an idea to an implementation plan:
`/idea`, `/research` and `/spec`, the agents they launch, the guard hook those agents run under,
and the sandboxed headless sessions `/spec` runs spikes in. `/cold-review` stands apart from that
flow, and gives any markdown file the same adversarial cold read `/spec` gives a spec. Notes live
in `~/notes`; specs live in the repo they describe.

## How a change flows through it

1. **`/idea <description>`** files a note in `~/notes/ideas`.
2. **`/research <question or idea note>`** researches it and writes a cited note to
   `~/notes/research`. A `research-verifier` agent then checks each load-bearing claim against its
   source, and says which it couldn't confirm.
3. **`/spec <research note>`** writes an implementation spec into the repo the change touches,
   which must be a git repo under `~/code` (its pre-approved edits cover only `~/code/**`),
   grounded in the code with `path:line` citations. Then three things happen to it:
   - `check-spec.py` checks mechanically that every citation points at lines that existed at the
     commit the spec was read at, that work items have observable acceptance criteria, and that no
     secrets or template text got left in;
   - a `spec-verifier` agent, which never saw the conversation, checks every citation, number and
     borrowed claim, and reports what doesn't hold;
   - a `cold-reviewer` agent gives it one adversarial cold read, from the same prompt skeleton as
     `/cold-review`, looking for assumptions stated as facts and costs nobody counted. Its table is
     saved unchanged in the spec's record, `records/<spec>-record.md` beside it, which holds the
     spec's history (verifier rounds, the review, spike routing, implementation notes) so the
     spec itself stays the plan. Changes made after the review are logged there as `Not
     reviewed:` lines, and `/cold-review <spec>` gives them one delta review before
     implementation: `check-spec.py` fails a spec marked `reviewed` or `in-progress` until it has.
4. **Spikes** answer what reading can't settle. Each runs as a sandboxed, cost-capped `claude -p`
   session in a scratch copy of the code, writes a verdict with its raw output, and has that folded
   back into the spec. Spikes run at the end of `/spec`, or later with `/spec spike <spec>`.
5. **Implementation** happens in a fresh session, from the spec. This repo's skills write no code.
   Afterwards, `/spec done <spec>` writes down in the record where the build departed from the
   spec, settles its status, and flags research the build overturned.

`docs/specs/2026-09-17-spec-spike-phase.md` is a worked example of the output, with its spike
results beside it in `docs/specs/spikes/`.

Outside that flow, **`/cold-review <markdown file>`** hands a document - a walkthrough, runbook,
README, design doc, spec or research note - to a `cold-reviewer` agent that has seen none of the
conversation that produced it. The skill works out what kind of document it is and what a cold
reader has to be able to do with it, writes the prompt, and relays the findings. The reviewer edits nothing. The skill edits the
document only for findings you pick, and saves the review in a record, `records/<basename>-record.md`
beside the document; it asks first, except for a spec's delta review, which it saves as `/spec` does. On a document with a saved review, it runs one delta review
of the changes logged since as `Not reviewed:` lines, and no more. `/cold-review prompt <file>` writes the prompt for a fresh
session instead of launching an agent. The reviewer is read-only, so it settles what it can by
reading the Taskfile, CLI and config a document points at, and names the findings that need a
command run instead of guessing at output.

## Layout

- `skills/idea/`: `/idea`.
- `skills/research/`: `/research`, with `ideation-rules.md` (the researcher's rules at `ideas`
  depth, read only then), `ideas-finish.md` (the skill's last steps at `ideas` depth),
  `scripts/check-note.py` and the helpers the `researcher`
  agent runs while gathering evidence (`repo-health.sh`, `gcp-skus.sh`, `reddit-search.sh`).
- `hooks/run-agent.sh` and `hooks/agent-sandbox.json`: how the skills run their agents. Every agent
  also gets `hooks/agent-sandbox.md` appended to its prompt, with the host list filled in from the
  settings by `hooks/sandbox-prompt.py`, so no agent file keeps its own copy. Each run is capped
  at $5 ($10 for the researcher, or `RUN_AGENT_MAX_USD`), and exits 3 when the reply lacks the
  closing lines its agent file asks for, so an API error is never read as a verdict. Each runs as
  a headless `claude -p --agent <name>` session inside Claude Code's OS sandbox (no credential
  reads, no secret environment variables, Bash writes only in its work dir, Bash network only to an
  allowlist), since the sandbox can't be set for an in-session subagent. Some things run outside it:
  `gh` and the three research scripts that need credentials or loop over `gh` (`repo-health.sh`,
  `gcp-skus.sh`, `reddit-search.sh`), which `agent-sandbox.json` lists in `excludedCommands`, since
  Go CLIs fail TLS under the macOS sandbox; the Read, WebFetch and WebSearch tools, which the sandbox
  never covers (permission deny rules cover Read); and the researcher's MCP servers (AWS and
  Terraform documentation). For those, `agent-guard.py`'s checks are what holds.
- `skills/spec/`: `/spec`, with `scripts/check-spec.py`, `template.md`, `record-template.md` and
  `done-step.md` (step 8, read only by `/spec done`). Spikes add five files:
  `spike-step.md` (step 7, read only when spikes run), `spiker.md` (the rules a spike session runs
  under), `spike-settings.json` (its sandbox and permission settings), `scripts/prepare-spike.sh`
  (clears a scratch directory and exports the code into it, after checking its paths) and
  `scripts/run-spike.sh` (the launcher).
- `skills/cold-review/`: `/cold-review`. One file, and no script: the review is a prompt and an
  agent. `/spec` builds its cold review from this file's prompt skeleton.
- `agents/`: `researcher`, `research-verifier`, `spec-verifier`, `cold-reviewer`.
- `hooks/agent-guard.py`: the PreToolUse guard those subagents' Bash, Read, Grep, Glob and Write
  calls go through. It keeps credentials out of their reach, since a fetched page could get them
  sent out in a request URL, and session history (transcripts, prompt history, earlier agent
  runs), so a verifier or cold reviewer can't see how the document it checks was written. The spiker isn't a subagent and doesn't run under it; its sandbox
  settings contain it instead.
- `tests/`: deterministic tests for the guard and both checkers, a transcript replay for the guard,
  `agent-evals/`, which runs the verifier and cold-reviewer agents against planted defects and the
  researcher at quick and ideas depth (its note graded with `check-note.py`), and `skill-evals/`,
  which runs whole skills against throwaway repos.

## Requirements

- Claude Code, 2.1.219 or later: every agent and every spike runs with `sandbox.*` settings passed
  with `--settings`, and `strictAllowlist` there needs 2.1.219 (`sandbox.credentials`, 2.1.187).
  Last run on 2.1.282.
- `python3` for the checkers and tests. Some spikes use `uv`.
- **macOS.** Every agent and spike runs in Claude Code's sandbox, which is Seatbelt on macOS.
  `agent-sandbox.json` and `skills/spec/spiker.md` are built around how it behaves there, including
  Go binaries such as `helm` and `gh` failing TLS inside it. Neither has been run anywhere else; on
  Linux the sandbox needs bubblewrap, and `gh` may not need excluding.

## Set up ~/notes

The skills keep notes in `~/notes`, and this repo doesn't create it. It has to be a git repo (the
skills commit to it) holding:

- `CLAUDE.md`, the notes' conventions (tags, frontmatter), which the researcher reads first;
- `templates/idea.md`, `templates/research.md` and `templates/research-ideas.md`, which `/idea` and
  the researcher start from, and `check-note.py` checks notes against;
- for `/research ideas`, `projects/mindshare/attention-evidence.md`, the table of launches and
  their scores that ranking by mindshare reads and adds to.

Every agent run also passes `~/notes` to `claude` as a working directory (`--add-dir`), so it must
exist even for `/spec` and `/cold-review`.

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

## Checks

```
python3 -m unittest discover -s ~/code/github.com/claude-skills/tests   # seconds, free
python3 ~/code/github.com/claude-skills/tests/replay_guard.py           # guard vs real commands and reads
~/code/github.com/claude-skills/tests/agent-evals/run.sh                # minutes, costs tokens
```

Run the agent evaluations by hand after changing an agent or skill file; `tests/agent-evals/BASELINE.md`
records what each run cost and found. Recent full runs of its five cases cost $1.22 and $1.82.

**What things cost.** The evaluations spend real tokens, and so do spikes: each spike session is
capped at $2 and 60 turns, and a spike that fetches anything should be assumed to cost near the cap.
The cap stops a run only after the turn that crosses it, so a session can overshoot by up to a turn.

## Licence

MIT, so copy what's useful into your own `~/.claude`. See `LICENSE`.

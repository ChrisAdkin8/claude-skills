# claude-skills

Personal Claude Code skills, subagents and hooks for taking an idea to an implementation plan:
`/idea`, `/research` and `/spec`, the agents they launch, the guard hook those agents run under,
and the sandboxed headless sessions `/spec` runs spikes in. Notes live in `~/notes`; specs live in
the repo they describe.

## How a change flows through it

1. **`/idea <description>`** files a note in `~/notes/ideas`.
2. **`/research <question or idea note>`** researches it and writes a cited note to
   `~/notes/research`. A `research-verifier` agent then checks each load-bearing claim against its
   source, and says which it couldn't confirm.
3. **`/spec <research note>`** writes an implementation spec into the repo the change touches,
   grounded in the code with `path:line` citations. Then three things happen to it:
   - `check-spec.py` checks mechanically that every citation points at lines that existed at the
     commit the spec was read at, that work items have observable acceptance criteria, and that no
     secrets or template text got left in;
   - a `spec-verifier` agent, which never saw the conversation, checks every citation, number and
     borrowed claim, and reports what doesn't hold;
   - a `spec-reviewer` agent gives it one adversarial cold read, looking for assumptions stated as
     facts and costs nobody counted. Its table is saved in the spec, unchanged, as a record.
4. **Spikes** answer what reading can't settle. Each runs as a sandboxed, cost-capped `claude -p`
   session in a scratch copy of the code, writes a verdict with its raw output, and has that folded
   back into the spec. Spikes run at the end of `/spec`, or later with `/spec spike <spec>`.
5. **Implementation** happens in a fresh session, from the spec. This repo's skills write no code.

`docs/specs/2026-09-17-spec-spike-phase.md` is a worked example of the output, with its spike
results beside it in `docs/specs/spikes/`.

## Layout

- `skills/idea/`: `/idea`.
- `skills/research/`: `/research`, with `scripts/check-note.py` and the helpers the `researcher`
  agent runs while gathering evidence (`repo-health.sh`, `gcp-skus.sh`, `reddit-search.sh`).
- `skills/spec/`: `/spec`, with `scripts/check-spec.py` and `template.md`. Spikes add three files:
  `spiker.md` (the rules a spike session runs under), `spike-settings.json` (its sandbox and
  permission settings) and `scripts/run-spike.sh` (the launcher).
- `agents/`: `researcher`, `research-verifier`, `spec-verifier`, `spec-reviewer`.
- `hooks/agent-guard.py`: the PreToolUse guard those subagents' Bash and Write calls go through. The
  spiker isn't a subagent and doesn't run under it; its sandbox settings contain it instead.
- `tests/`: deterministic tests for the guard and both checkers, a transcript replay for the guard,
  and `agent-evals/`, which runs the verifier agents against planted defects.

## Requirements

- Claude Code. Tested on 2.1.274; spike sandboxing needs a version that honours `sandbox.*` settings
  passed with `--settings`.
- `python3` for the checkers and tests. Some spikes use `uv`.
- **macOS.** The spike sandbox is Seatbelt, and `skills/spec/spiker.md` carries rules about how it
  behaves there, including Go binaries such as `helm` and `gh` failing TLS inside it. Spikes haven't
  been run anywhere else.

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
python3 ~/code/github.com/claude-skills/tests/replay_guard.py           # guard vs real commands
~/code/github.com/claude-skills/tests/agent-evals/run.sh                # minutes, costs tokens
```

Run the agent evaluations by hand after changing an agent or skill file; `tests/agent-evals/BASELINE.md`
records what each run cost and found. Recent full runs of its five cases cost $1.22 and $1.82.

**What things cost.** The evaluations spend real tokens, and so do spikes: each spike session is
capped at $2 and 60 turns, and a spike that fetches anything should be assumed to cost near the cap.
The cap stops a run only after the turn that crosses it, so a session can overshoot by up to a turn.

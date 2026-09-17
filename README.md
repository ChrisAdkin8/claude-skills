# claude-skills

Personal Claude Code skills, subagents and hooks: `/idea`, `/research` and `/spec`, the agents they
launch, the guard hook the subagents run under, and the sandboxed headless sessions `/spec` runs
spikes in. Notes they write live in `~/notes`.

## Layout

- `skills/`: `idea`, `research` (with `scripts/check-note.py`, `repo-health.sh`, `gcp-skus.sh`,
  `reddit-search.sh`) and `spec` (with `scripts/check-spec.py`, `template.md`, and `spiker.md` and
  `spike-settings.json`, the rules and sandbox settings for its spike sessions).
- `agents/`: `researcher`, `research-verifier`, `spec-verifier`, `spec-reviewer`.
- `hooks/agent-guard.py`: the PreToolUse guard the subagents' Bash and Write calls go through. The
  spiker isn't a subagent and doesn't run under it; its sandbox settings contain it.
- `tests/`: deterministic tests for the guard and both checkers, a transcript replay for the guard,
  and `agent-evals/`, which runs the verifier agents on planted defects.

## Install

Claude Code reads these from `~/.claude`, so each directory there is a symlink into this repo:

```
ln -s ~/code/github.com/claude-skills/skills ~/.claude/skills
ln -s ~/code/github.com/claude-skills/agents ~/.claude/agents
ln -s ~/code/github.com/claude-skills/hooks  ~/.claude/hooks
```

The files refer to themselves by their `~/.claude/...` paths, which the symlinks keep valid. The
guard resolves those paths, so it recognises its skill scripts through the links. Whatever branch
is checked out here is what the agents run.

## Checks

```
python3 -m unittest discover -s ~/code/github.com/claude-skills/tests   # seconds, free
python3 ~/code/github.com/claude-skills/tests/replay_guard.py             # guard vs real commands
~/code/github.com/claude-skills/tests/agent-evals/run.sh                  # minutes, costs tokens
```

Run the agent evaluations by hand after changing an agent or skill file; see
`tests/agent-evals/BASELINE.md` for what to expect.

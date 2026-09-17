---
title: Fixture spec with one spike figure the results don't show
created: 2026-09-17
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: bb9f240
cite-repo: ~/code/github.com/claude-skills
---

# Fixture spec with one spike figure the results don't show

## Goal

Run `check-spec.py` from a pre-commit hook on every staged spec, if it's fast enough not to be noticed.

## Decision

Add the hook only if one check of a spec takes well under a second.

## Background

Read at `bb9f240` in `~/code/github.com/claude-skills`; citations point into that repo.

- A spike session is capped at $2 and 60 turns (`skills/spec/scripts/run-spike.sh:27`).
- Spike sessions get no network unless the spike's hosts are listed (`skills/spec/spike-settings.json:5`).

## Non-goals

- Checking specs in CI.

## Work items

### W1: A pre-commit hook for specs

- **Change:** add a pre-commit hook that runs `skills/spec/scripts/check-spec.py` on each staged file under `docs/specs/`.
- **Files:** `.pre-commit-config.yaml` (new).
- **Done when:** `git commit` of a spec with a bad citation fails with a `FAIL:` line from the checker.

## Spike questions

1. How long does one `check-spec.py` run take on this repo's spec? Experiment: time three runs.
   Route: spike
   Changes: the Decision's "well under a second".
   Expect: under a second.
   Box: $2, 60 turns; hosts: none
   Answered: EXPECTED, about 0.4 s per run over 3 runs (spike S1, `tests/agent-evals/cases/spike-inherited/results.md`)

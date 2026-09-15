---
title: Fixture spec with a saved cold review
created: 2026-09-15
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: c7adaf4
cite-repo: ~/.claude
---

# Fixture spec with a saved cold review

## Goal

Document how the agent guard treats environment-variable assignments today, as the basis for a later fix.

## Decision

Describe the current behaviour only.

## Background

Read at `c7adaf4` in `~/.claude`; citations point into that repo.

- The guard allows five skill scripts by path (`hooks/agent-guard.py:31-37`).
- `unwrap` drops assignment words before the command without reading them (`hooks/agent-guard.py:187-193`).
- `check_command` passes each simple command through `unwrap` (`hooks/agent-guard.py:394-395`).

## Non-goals

- Changing the guard.

## Work items

### W1: Write the behaviour down

- **Change:** add a paragraph to the guard's docstring describing how assignments are handled.
- **Files:** `hooks/agent-guard.py`.
- **Done when:** `python3 -c "import ast; print(ast.get_docstring(ast.parse(open('hooks/agent-guard.py').read())))"` prints a paragraph that mentions assignments.

## Spike questions

None.

## Cold review

Reviewed on 2026-09-15 by spec-reviewer. Saved unchanged; not acted on.

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
| 1 | COST | W1 Files | The docstring paragraph may drift from the code | neither: documentation only | hooks/agent-guard.py:999 | Re-read the docstring after any guard change |

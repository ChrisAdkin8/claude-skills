---
title: Fixture spec with one planted miscitation
created: 2026-09-15
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: c7adaf4
cite-repo: ~/.claude
---

# Fixture spec with one planted miscitation

## Goal

Document how the agent guard treats environment-variable assignments today, as the basis for a later fix.

## Decision

Describe the current behaviour only.

## Background

Read at `c7adaf4` in `~/.claude`; citations point into that repo.

- The guard allows five skill scripts by path (`hooks/agent-guard.py:31-37`).
- `unwrap` drops assignment words before the command without reading them (`hooks/agent-guard.py:40-46`).
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

---
title: Fixture spec for a delta review
created: 2026-09-20
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 23b0ace
cite-repo: none
---

# Fixture spec for a delta review

## Goal

Make `check-note.py` stricter for quick notes, so a quick answer stays short enough to read in a minute.

## Decision

Tighten the researcher's own budget for quick notes, and leave the hard limits alone.

## Background

Read at `23b0ace`.

- The hard limit for a full-depth note is 2,000 words (`skills/research/scripts/check-note.py:27`).
- `--headroom` applies the researcher's lower budgets, from `HEADROOM_BUDGET` (`skills/research/scripts/check-note.py:28`).

## Non-goals

- Changing the hard limits.

## Work items

### W1: Warn near the budget

- **Change:** print a WARN line when a note is within 5 % of its budget.
- **Files:** `skills/research/scripts/check-note.py`.
- **Done when:** a quick note of 480 words, checked with `--headroom`, prints a WARN line naming the budget.

### W2: Lower the quick headroom

- **Change:** lower the quick entry in `HEADROOM_BUDGET` from 500 words to 400.
- **Files:** `skills/research/scripts/check-note.py`, `agents/researcher.md` (its Depth section states the budget).
- **Done when:** `check-note.py --quick-budget 400 note.md` on a quick note of 420 words prints `RESULT: FAIL`.

## Spike questions

None.

## Open questions

- Not reviewed: W2 now lowers the quick headroom budget instead of adding a `--budget` flag, from cold review row 1, on 2026-09-20.

## Cold review

Reviewed on 2026-09-20 by cold-reviewer. Saved unchanged; not acted on.

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
| 1 | COST | W2: "add a `--budget N` flag" | A new flag duplicates `--headroom` and every caller would have to pass it. | neither: a design preference | `skills/research/scripts/check-note.py:537` | Lower the existing budget instead. |

Counts: 1 findings - 0 correctness, 0 requirement, 1 neither
Neither: 1
Cold read: yes
Needs a run: none

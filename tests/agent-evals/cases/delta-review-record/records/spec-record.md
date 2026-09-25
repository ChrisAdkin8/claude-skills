# Record: the fixture spec

What happened to [spec](../spec.md) after it was written.

## Cold review

Reviewed on 2026-09-20 by cold-reviewer. Saved unchanged; not acted on.

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
| 1 | COST | W2: "add a `--budget N` flag" | A new flag duplicates `--headroom` and every caller would have to pass it. | neither: a design preference | `skills/research/scripts/check-note.py:537` | Lower the existing budget instead. |

Counts: 1 findings - 0 correctness, 0 requirement, 1 neither
Neither: 1
Cold read: yes
Needs a run: none

## Changes since the review

- Not reviewed: W2 now lowers the quick headroom budget instead of adding a `--budget` flag, from cold review row 1, on 2026-09-20.

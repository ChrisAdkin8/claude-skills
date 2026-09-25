#!/usr/bin/env bash
# Builds the fixture repo for the spec-done case in $1: a spec with two work items, a record,
# and one commit that builds W1 with a different default than the spec says. W2 never lands.
set -euo pipefail
cd "$1"
g() { git -c user.email=eval@local -c user.name=eval "$@"; }
git init -q
cat > calc.py <<'PY'
"""Arithmetic helpers."""


def add(a: float, b: float) -> float:
    """Return a + b."""
    return a + b
PY
g add calc.py && g commit -qm "feat: calc.add"
readat=$(git rev-parse --short HEAD)
mkdir -p docs/specs/records
cat > docs/specs/2026-09-20-rounding.md <<SPEC
---
title: Rounding helpers
created: 2026-09-20
status: reviewed # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: $readat
cite-repo: none
---

# Rounding helpers

## Goal

Add a rounding helper to \`calc.py\`, and a \`--places\` option to a small CLI that uses it.

## Decision

Round half away from zero, with \`decimal\`, because invoices must not round 2.5 down.

## Background

Read at \`$readat\` on 2026-09-20. \`calc.py\` has one function, \`add\` (\`calc.py:4-6\`).

## Non-goals

- Currency formatting.

## Design

\`round_to(x, places=2)\` in \`calc.py\`; \`cli.py\` parses \`--places\` and prints \`round_to\` of its argument.

## Work items

### W1: round_to

- **Change:** add \`round_to(x: float, places: int = 2) -> float\` to \`calc.py\`, rounding half away from zero.
- **Files:** \`calc.py\`
- **Done when:** \`python3 -c "from calc import round_to; assert round_to(2.345) == 2.35"\` exits 0.

### W2: a --places option

- **Change:** add \`cli.py\` (new) with \`--places\`, printing \`round_to\` of its argument.
- **Files:** \`cli.py\` (new)
- **Done when:** \`python3 cli.py 2.345 --places 1\` prints \`2.3\`.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 30 min | none |
| W2 | 30 min | W1 |

From reading the code; the order is firmer than the times.

## Spike questions

None.

## Risks and rollback

- Reverting W1 leaves nothing behind.

## Open questions

- None.
SPEC
cat > docs/specs/records/2026-09-20-rounding-record.md <<'REC'
# Record: Rounding helpers

What happened to [2026-09-20-rounding](../2026-09-20-rounding.md) after it was written.

## Verification

- 2026-09-20: spec-verifier, 3 of 3 claims confirmed. Plan holds: yes.
REC
g add docs && g commit -qm "docs: spec for rounding helpers"
cat >> calc.py <<'PY'


def round_to(x: float, places: int = 3) -> float:
    """Round x to `places` decimals, half away from zero."""
    from decimal import ROUND_HALF_UP, Decimal

    return float(Decimal(str(x)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))
PY
g add calc.py && g commit -qm "feat: round_to (W1)

Default places is 3, not the spec's 2: invoice lines are priced in mills,
so two places lost the third digit. The Done when check therefore uses
round_to(2.345, 2)."

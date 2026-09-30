#!/usr/bin/env bash
# Builds the fixture repo for the implement-basic case in $1 (under ~/code): code with a test
# suite and a CLAUDE.md naming it, committed; read-at from HEAD; then a reviewed spec with one
# achievable work item, citing the code, and its record, committed too.
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
mkdir -p tests
cat > tests/test_calc.py <<'PY'
import unittest

from calc import add


class Add(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(1, 2), 3)


if __name__ == "__main__":
    unittest.main()
PY
cat > CLAUDE.md <<'MD'
# calc

- Tests: `python3 -m unittest discover -s tests`, run from the repo root. They must pass before
  every commit.
- Commit messages start with the area: `calc:`, `tests:` or `spec:`.
MD
g add . && g commit -qm "calc: add, with its test"
readat=$(git rev-parse --short HEAD)
mkdir -p docs/specs/records
cat > docs/specs/2026-09-28-double.md <<SPEC
---
title: A doubling helper
created: 2026-09-28
status: reviewed # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: $readat
cite-repo: none
---

# A doubling helper

## Goal

Add \`double(x)\` to \`calc.py\`, beside \`add\`.

## Decision

A plain function, as \`add\` is, since nothing else needs to change.

## Background

Read at \`$readat\` on 2026-09-28. \`calc.py\` has one function, \`add\` (\`calc.py:4-6\`), and \`tests/test_calc.py\` tests it (\`tests/test_calc.py:6-8\`).

## Non-goals

- Any other helper.

## Design

\`double(x: float) -> float\` returns \`2 * x\`, with a test beside \`add\`'s.

## Work items

### W1: double

- **Change:** add \`double(x: float) -> float\` to \`calc.py\`, returning \`2 * x\`, and a test of it to \`tests/test_calc.py\`.
- **Files:** \`calc.py\`, \`tests/test_calc.py\`
- **Done when:** \`python3 -c "from calc import double; assert double(3) == 6"\` exits 0 (it fails before the change), and \`python3 -m unittest discover -s tests\` passes.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 15 min | none |

From reading the code.

## Spike questions

None.

## Risks and rollback

- Reverting W1 leaves nothing behind.

## Open questions

- None.
SPEC
cat > docs/specs/records/2026-09-28-double-record.md <<'REC'
# Record: A doubling helper

What happened to [2026-09-28-double](../2026-09-28-double.md) after it was written. The spec is the plan; this file is its history, and nothing here is part of the plan.

## Verification

- 2026-09-28: spec-verifier, 2 of 2 claims confirmed. Plan holds: yes.
REC
g add docs && g commit -qm "spec: a doubling helper"
printf 'head=%s\nbranch=%s\n' "$(git rev-parse HEAD)" "$(git symbolic-ref --short HEAD)" > .git/eval-hashes

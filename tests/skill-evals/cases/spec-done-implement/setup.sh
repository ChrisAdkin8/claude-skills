#!/usr/bin/env bash
# Builds the fixture repo for the spec-done-implement case in $1: spec-done's fixture (a spec with
# two work items, W1 built with a different default than the spec says, W2 never landed), whose
# record then gains the ## Evidence section /implement leaves: W1's evidence line and a verifier
# table showing W1's Done when passing, committed as /implement's last commit is.
set -euo pipefail
"$(cd "$(dirname "$0")" && pwd)/../spec-done/setup.sh" "$1"
cd "$1"
g() { git -c user.email=eval@local -c user.name=eval "$@"; }
started=$(git rev-parse --short HEAD~1)
w1=$(git rev-parse --short HEAD)
cat >> docs/specs/records/2026-09-20-rounding-record.md <<REC

## Evidence

- Started at $started
- Baseline: no checks found in the repo's rules or CI.
- W1 ($w1): Done when \`python3 -c "from calc import round_to; assert round_to(2.345, 2) == 2.35"\` -> exit 0, and failed first (ImportError); suite: no checks; scan clean
- Verifier V1 ($w1):

| W | Done when | Ran | Result (PASS, FAIL or CANNOT-RUN) | Matches spec |
|---|---|---|---|---|
| W1 | \`round_to(2.345) == 2.35\`, run with \`places=2\` as the W1 commit gives it | \`python3 -c "from calc import round_to; assert round_to(2.345, 2) == 2.35"\` in src/: exit 0; in before/W1/: ImportError, so it failed before | PASS | yes |

Verified: 1 of 1
Implementation holds: yes
REC
g add docs && g commit -qm "docs: implementation evidence"
printf 'head=%s\n' "$(git rev-parse --short HEAD)" > .git/eval-hashes

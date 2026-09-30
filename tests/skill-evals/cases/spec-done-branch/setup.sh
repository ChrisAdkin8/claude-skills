#!/usr/bin/env bash
# Builds the fixture repo for the spec-done-branch case in $1: spec-done's spec and record,
# committed on the main checkout with no ## Evidence, while /implement's branch
# implement/2026-09-20-rounding, checked out in a worktree beside the repo, holds W1's commit and
# the record's evidence. /spec done is run from the main checkout, where the build isn't.
set -euo pipefail
"$(cd "$(dirname "$0")" && pwd)/../spec-done/setup.sh" "$1"
cd "$1"
g() { git -c user.email=eval@local -c user.name=eval "$@"; }
base=2026-09-20-rounding
record=docs/specs/records/$base-record.md
w1=$(git rev-parse HEAD)
g reset -q --hard HEAD~1
started=$(git rev-parse --short HEAD)
wt="$(dirname "$1")/$(basename "$1")-worktrees/$base"
g worktree add -q "$wt" -b "implement/$base"
cd "$wt"
sed -i.bak 's/^status: reviewed #/status: in-progress #/' "docs/specs/$base.md" && rm "docs/specs/$base.md.bak"
printf '\n## Evidence\n\n- Started at %s\n' "$started" >> "$record"
g add docs && g commit -qm "spec: rounding helpers is in progress"
g cherry-pick "$w1" > /dev/null
short=$(git rev-parse --short HEAD)
cat >> "$record" <<REC
- W1 ($short): Done when \`python3 -c "from calc import round_to; assert round_to(2.345, 2) == 2.35"\` -> exit 0, and failed first (ImportError); suite: no checks; scan clean
- Verifier V1 ($short):

| W | Done when | Ran | Result (PASS, FAIL or CANNOT-RUN) | Matches spec |
|---|---|---|---|---|
| W1 | \`round_to(2.345) == 2.35\`, run with \`places=2\` as the W1 commit gives it | in src/: exit 0; in before/W1/: ImportError | PASS | yes |

Verified: 1 of 1
Implementation holds: yes
REC
g add docs && g commit -qm "spec: implementation evidence"
cd "$1"
printf 'head=%s\nworktree=%s\n' "$(git rev-parse --short HEAD)" "$wt" > .git/eval-hashes

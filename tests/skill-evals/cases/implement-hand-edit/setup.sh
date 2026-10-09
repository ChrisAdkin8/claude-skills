#!/usr/bin/env bash
# Builds the fixture repo for the implement-hand-edit case in $1 (under ~/code): implement-trap's
# fixture, then a cold review saved in its spec's record and committed, then a hand edit to W1's
# Done when, committed to the reviewed spec with no `Not reviewed:` line logged for it.
# review-state.py --plan reads it `unlogged`, so /implement's gate check 6 should stop before any
# worktree is made, and send the user to /cold-review.
set -euo pipefail
"$(cd "$(dirname "$0")" && pwd)/../implement-trap/setup.sh" "$1"
cd "$1"
g() { git -c user.email=eval@local -c user.name=eval "$@"; }
spec=docs/specs/2026-09-28-service-charge.md
record=docs/specs/records/2026-09-28-service-charge-record.md
# The review line's format is cold-review-delta's (its setup.sh), saved here in the record.
cat >> "$record" <<'REC'

## Cold review

Reviewed on 2026-09-28 by cold-reviewer. Saved unchanged; what was folded in is logged under Changes since the review.

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
| 1 | COLD-READ | W1, Done when | The charge's size is given only as a number | neither: the Design says it | calc.py:4-6 | Name the charge in the Done when |

Counts: 1 findings - 0 correctness, 0 requirement, 1 neither
Neither: 1
Cold read: yes
Needs a run: none
REC
g add "$record" && g commit -qm "spec: save the service charge's cold review"
# The hand edit: W1's Done when now checks an empty order too, logged nowhere.
python3 - "$spec" <<'PY'
import sys
from pathlib import Path

p = Path(sys.argv[1])
s = p.read_text()
old = 'assert total([1, 2]) == 4"'
assert s.count(old) == 1
p.write_text(s.replace(old, 'assert total([1, 2]) == 4 and total([]) == 1"'))
PY
g add "$spec" && g commit -qm "spec: W1 checks an empty order too"
printf 'head=%s\n' "$(git rev-parse HEAD)" > .git/eval-hashes

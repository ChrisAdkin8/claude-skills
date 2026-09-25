#!/usr/bin/env bash
# Builds the fixture repo for the cold-review-delta case in $1: a runbook whose cold review was
# saved at its end (the older layout), one finding folded in and logged, then the review moved
# into a record, then an edit to another section that nobody logged. The commit hashes go in
# .git/eval-hashes for grade.py, where the skill has no reason to look.
set -euo pipefail
cd "$1"
g() { git -c user.email=eval@local -c user.name=eval "$@"; }
git init -q
mkdir -p docs
cat > Makefile <<'MK'
backup:
	tar czf backup.tgz data/

restore:
	tar xzf backup.tgz
MK
cat > docs/runbook.md <<'MD'
# Restore the data directory

## Before you start

You need the latest `backup.tgz` in the repo root.

## Restore

1. Stop the service.
2. Run `make restore`.
3. Start the service.

## Rollback

If the restore fails, run `make backup` first next time.

## Open questions

- None.
MD
g add . && g commit -qm "docs: a restore runbook"
created=$(git rev-parse --short HEAD)
cat >> docs/runbook.md <<'MD'

## Cold review

Reviewed on 2026-09-20 by cold-reviewer. Saved unchanged; not acted on.

| # | Kind | Where | Finding | Affects | Evidence | What would settle it |
|---|---|---|---|---|---|---|
| 1 | GAP | Restore, step 2 | `make restore` overwrites `data/` with no warning | correctness | Makefile:5 | Say so before step 2 |

Counts: 1 findings - 1 correctness, 0 requirement, 0 neither
MD
g commit -qam "docs: save the runbook's cold review"
saved=$(git rev-parse --short HEAD)
python3 - <<'PY'
from pathlib import Path
p = Path("docs/runbook.md"); s = p.read_text()
s = s.replace("2. Run `make restore`.", "2. Run `make restore`. It overwrites `data/` without asking.")
s = s.replace("- None.", "- Not reviewed: step 2 now warns that `make restore` overwrites `data/`, from cold review row 1, on 2026-09-21.")
p.write_text(s)
PY
g commit -qam "docs: fold the cold review's row 1 into the runbook"
python3 - <<'PY'
from pathlib import Path
p = Path("docs/runbook.md"); s = p.read_text()
body, review = s.split("\n## Cold review\n", 1)
line = "- Not reviewed: step 2 now warns that `make restore` overwrites `data/`, from cold review row 1, on 2026-09-21."
body = body.replace(line, "- None.")
p.write_text(body.rstrip() + "\n")
Path("docs/records").mkdir()
Path("docs/records/runbook-record.md").write_text(
    "# Record: Restore the data directory\n\n## Cold review\n" + review.rstrip()
    + "\n\n## Changes since the review\n\n" + line + "\n")
PY
g add . && g commit -qm "docs: move the runbook's review history into a record"
moved=$(git rev-parse --short HEAD)
python3 - <<'PY'
from pathlib import Path
p = Path("docs/runbook.md"); s = p.read_text()
s = s.replace("If the restore fails, run `make backup` first next time.",
              "If the restore fails, delete `data/` and restore again from yesterday's `backup.tgz`.")
p.write_text(s)
PY
g commit -qam "docs: a real rollback step"
printf 'created=%s\nsaved=%s\nmoved=%s\n' "$created" "$saved" "$moved" > .git/eval-hashes

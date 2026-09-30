"""Grades the spec-done-branch case: python3 grade.py <fixture dir> <result.json>. Prints one line per check.

The main checkout's record has no ## Evidence, and the work is on implement/2026-09-20-rounding,
in a worktree beside the repo. /spec done run from the checkout should say to run it from that
worktree, and leave the spec's status alone.
"""

import json
import re
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
reply = json.loads(Path(sys.argv[2]).read_text()).get("result", "")
spec = repo / "docs/specs/2026-09-20-rounding.md"
hashes = dict(l.split("=", 1) for l in (repo / ".git/eval-hashes").read_text().split())
worktree = hashes["worktree"]
# A paragraph or bullet that names /spec done and the worktree: the word, its path, or the
# branch ("Run /spec done from that folder" follows the path in the same paragraph). Not its
# directory name alone: that is the spec's basename, which every /spec done path holds.
blocks = re.split(r"\n\s*\n|\n(?=\s*[-*] )", reply)
names_worktree = re.compile(
    rf"(?i)worktree|implement/2026-09-20-rounding|{re.escape(worktree)}"
)
checks = {
    "the reply says to run /spec done from the implement/<basename> worktree": any(
        re.search(r"(?i)/?(?:claude-skills:)?spec done", b) and names_worktree.search(b)
        for b in blocks
    ),
    "the spec's status is unchanged (reviewed)": re.search(
        r"(?m)^status: reviewed\b", spec.read_text()
    )
    is not None,
}
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)

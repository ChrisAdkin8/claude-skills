"""Grades the implement-hand-edit case: python3 grade.py <fixture dir> <result.json>. Prints one
line per check.

The spec's W1 Done when was edited by hand after its saved cold review, and nothing was logged.
/implement's gate (check 6, review-state.py --plan) should stop before step 3 makes a worktree,
and send the user to /cold-review. A run that went past the gate leaves a worktree folder, a
second worktree in git's list, or an implement/ branch.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
reply = json.loads(Path(sys.argv[2]).read_text()).get("result", "")


def git(*args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


worktrees = [
    line for line in git("worktree", "list", "--porcelain").splitlines()
    if line.startswith("worktree ")
]
branches = git("for-each-ref", "--format=%(refname:short)", "refs/heads/implement").split()
folder = repo.parent / f"{repo.name}-worktrees"
checks = {
    "no worktree was made"
    + (f" (found: {', '.join(w[9:] for w in worktrees[1:]) or folder})"
       if len(worktrees) > 1 or folder.exists() else ""):
    len(worktrees) == 1 and not folder.exists(),
    "no implement/ branch was made" + (f" (found: {', '.join(branches)})" if branches else ""):
    not branches,
    "the reply names /cold-review": bool(re.search(r"/(?:checked-plans:)?cold-review\b", reply)),
}
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)

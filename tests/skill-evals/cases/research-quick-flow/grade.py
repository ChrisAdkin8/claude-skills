"""Grades the research-quick-flow case: python3 grade.py <fixture dir> <result.json>. Prints one line per check.

The runner gives the note's path as EVAL_NOTE, and `git -C ~/notes status --porcelain` from before
and after the case, eval notes left out, as NOTES_BEFORE and NOTES_AFTER. The index rebuild is
expected to fail: the sandbox denies Bash writes to ~/notes, so the eval can't rewrite the real
index.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# The repo this case lives in: tests/skill-evals/cases/<case>/grade.py.
ROOT = Path(__file__).resolve().parents[4]

note = Path(os.environ["EVAL_NOTE"])
text = note.read_text() if note.exists() else ""
check = (
    subprocess.run(
        [str(ROOT / "skills/research/scripts/check-note.py"), str(note)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    if text
    else ""
)
before, after = os.environ.get("NOTES_BEFORE", ""), os.environ.get("NOTES_AFTER", "")
checks = {
    "the note exists": bool(text),
    "check-note passes": "RESULT: PASS" in check,
    "the note has a Verification section": bool(
        re.search(r"(?m)^## Verification\b", text)
    ),
    "the note has a status": bool(re.search(r"(?m)^status: \w", text)),
    "~/notes is a git repo": "NOT A GIT REPO" not in before + after,
    "nothing else in ~/notes changed": before == after,
}
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)

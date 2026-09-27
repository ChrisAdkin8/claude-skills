"""Grades the cold-review-delta case: python3 grade.py <fixture dir> <result.json>.

/cold-review in prompt mode, on a runbook whose review was moved into a record after a fold,
and then edited once more without logging it. Prints one line per check."""

import json
import re
import subprocess
import sys
from pathlib import Path

# How past replies said it: "Unlogged changes", "A change nobody logged", "never logged", "isn't
# logged anywhere", "no `Not reviewed:` line covers it", "has no line".
UNLOGGED = re.compile(
    r"(?i)un-?logged|\b(?:not|nobody|never|isn't|wasn't)\s+(?:been\s+)?logged|no\s+`?not reviewed|has no\b[^.\n]*\bline"
)

repo, result = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
reply = result.get("result", "")
hashes = dict(l.split("=", 1) for l in (repo / ".git/eval-hashes").read_text().split())
# The diff base the prompt gives: `diff <sha> -- ...docs/runbook.md`.
bases = re.findall(r"diff\s+(?:-\S+\s+)*([0-9a-f]{7,40})(?:\^|~1)?\s+--\s+\S*runbook\.md", reply)
changed = subprocess.run(["git", "-C", str(repo), "status", "--porcelain"],
                         capture_output=True, text=True).stdout
checks = {
    "the prompt gives a diff of the runbook": bool(bases),
    # The review was saved in `saved`, which also changed the runbook, so the rule's base is its
    # parent, `created`; `saved` itself would still see every change since.
    "the diff starts at the review, not the move": bool(bases)
    and all(b[:7] in (hashes["created"], hashes["saved"]) for b in bases),
    "the logged change is quoted": "overwrites `data/`" in reply,
    # Named as unlogged, in one paragraph or bullet: Rollback alone is also a section name.
    "the unlogged Rollback edit is named": any(
        re.search(r"(?i)rollback", part) and UNLOGGED.search(part)
        for part in re.split(r"\n\s*\n|\n\s*[-*] ", reply)
    ),
    "it's a delta review": bool(re.search(r"(?i)delta review", reply)),
    "no file changed": changed.strip() == "",
}
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
print(f"     bases found: {bases}; hashes: {hashes}")
sys.exit(0 if all(checks.values()) else 1)

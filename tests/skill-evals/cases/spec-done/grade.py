"""Grades the spec-done case: python3 grade.py <fixture dir> <result.json>. Prints one line per check."""

import json
import re
import subprocess
import sys
from pathlib import Path

repo, result = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
spec = repo / "docs/specs/2026-09-20-rounding.md"
record = repo / "docs/specs/records/2026-09-20-rounding-record.md"
w1 = subprocess.run(["git", "-C", str(repo), "log", "--format=%h", "-1", "--grep", "(W1)"],
                    capture_output=True, text=True).stdout.strip()
diff = subprocess.run(["git", "-C", str(repo), "diff", "--", str(spec)], capture_output=True, text=True).stdout
changed = [l for l in diff.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))]
rec = record.read_text() if record.exists() else ""
impl = rec.split("## Implementation", 1)[1] if "## Implementation" in rec else ""
check = subprocess.run([str(Path.home() / ".claude/skills/spec/scripts/check-spec.py"), str(spec)],
                       capture_output=True, text=True).stdout
checks = {
    "status is in-progress (W2 hasn't landed)": re.search(r"(?m)^status: in-progress\b", spec.read_text()) is not None,
    "the plan is unchanged apart from the status line": all("status:" in l for l in changed),
    "the record has an Implementation section": bool(impl.strip()),
    "an implementation note names W1 and its commit": bool(re.search(rf"W1[^\n]*{w1[:7]}|{w1[:7]}[^\n]*W1", impl)),
    "the note says the default is 3 places": bool(re.search(r"\b3\b", impl)),
    "check-spec passes": "RESULT: PASS" in check,
    "the reply names W2 as not landed": bool(re.search(r"W2", result.get("result", ""))),
}
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)

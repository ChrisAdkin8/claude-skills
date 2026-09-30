"""Grades the spec-done-implement case: python3 grade.py <fixture dir> <result.json>. Prints one line per check.

spec-done's checks, with the record's `## Implementation` matched as the whole heading (the record
also has `## Evidence`), and one more: the record's evidence shows W1's Done when passing, so the
reply mustn't list W1 among the work items whose checks haven't passed or been run.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# The repo this case lives in: tests/skill-evals/cases/<case>/grade.py.
ROOT = Path(__file__).resolve().parents[4]

repo, result = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text())
reply = result.get("result", "")
spec = repo / "docs/specs/2026-09-20-rounding.md"
record = repo / "docs/specs/records/2026-09-20-rounding-record.md"
w1 = subprocess.run(
    ["git", "-C", str(repo), "log", "--format=%h", "-1", "--grep", "(W1)"],
    capture_output=True,
    text=True,
).stdout.strip()
head = dict(l.split("=", 1) for l in (repo / ".git/eval-hashes").read_text().split())[
    "head"
]
# Against setup's HEAD, not the index: a skill that commits its edit mustn't hide it.
diff = subprocess.run(
    ["git", "-C", str(repo), "diff", head, "--", str(spec)],
    capture_output=True,
    text=True,
).stdout
changed = [
    l for l in diff.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))
]
rec = record.read_text() if record.exists() else ""
m = re.search(r"(?ms)^## Implementation[ \t]*\n(.*?)(?=^## |\Z)", rec)
impl = m.group(1) if m else ""
check = subprocess.run(
    [str(ROOT / "skills/spec/scripts/check-spec.py"), str(spec)],
    capture_output=True,
    text=True,
).stdout
sentences = re.split(r"(?<=[.;\n])\s+", reply)
# A sentence about both W1 and W2 is split into its clauses, so W2's "hasn't landed" isn't read
# as W1's.
clauses = [
    c
    for s in sentences
    for c in (
        re.split(r",|\band\b|\bbut\b|\bwhile\b", s)
        if re.search(r"\bW1\b", s) and re.search(r"\bW2\b", s)
        else [s]
    )
]
# A sentence, clause or table row about W1 alone (not W2) that says its check hasn't passed or
# been run.
UNCHECKED = re.compile(
    r"(?i)(?:\bnot\b|\bnever\b|n't\b)[^.;\n]{0,30}\b(?:run|passed|pass|confirmed|verified|checked)\b"
    r"|unconfirmed|unverified|unknown|unchecked|no confirmation|not yet (?:run|confirmed|checked)"
)
CHECK = re.compile(r"(?i)done when|check|test|verif|confirm")
checks = {
    "status is in-progress (W2 hasn't landed)": re.search(
        r"(?m)^status: in-progress\b", spec.read_text()
    )
    is not None,
    "the plan is unchanged apart from the status line": all(
        "status:" in l for l in changed
    ),
    "the record has an ## Implementation section, matched as the whole heading": bool(
        impl.strip()
    ),
    "an implementation note names W1 and its commit": bool(
        re.search(rf"W1[^\n]*{w1[:7]}|{w1[:7]}[^\n]*W1", impl)
    ),
    # 3 beside "default" or "places", not any 3: "3 of 3 claims" is in the record already.
    "the note says the default is 3 places": bool(
        re.search(
            r"(?i)(?:default|places)[^\n]{0,40}\b3\b|\b3\b[^\n]{0,40}(?:default|places)",
            impl,
        )
    ),
    "check-spec passes": "RESULT: PASS" in check,
    "the reply doesn't list W1 among checks not passed or not run": not any(
        re.search(r"\bW1\b", c)
        and not re.search(r"\bW2\b", c)
        and CHECK.search(c)
        and UNCHECKED.search(c)
        for c in clauses
    ),
    # W2 with a word saying it's still open, in the same sentence: "W2 has landed" isn't it.
    "the reply names W2 as not landed": any(
        re.search(r"(?i)\bW2\b", s)
        and re.search(
            r"(?i)not (?:yet )?(?:landed|done|built|implemented|in)|\b(?:hasn't|has not|wasn't|was not|was never|never)\b|\bopen\b|pending|outstanding|remain|still to|unlanded|missing|no commit",
            s,
        )
        for s in sentences
    ),
}
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)

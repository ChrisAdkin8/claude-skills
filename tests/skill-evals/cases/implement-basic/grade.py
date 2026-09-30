"""Grades the implement-basic case: python3 grade.py <fixture dir> <result.json>. Prints one line per check."""

import re
import subprocess
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
base = "2026-09-28-double"
branch = f"implement/{base}"
record = f"docs/specs/records/{base}-record.md"
worktree = repo.parent / f"{repo.name}-worktrees" / base
run_json = (
    Path.home()
    / ".cache/implement-runs"
    / f"{repo.name}--{base}"
    / "implementer/run.json"
)
setup = dict(l.split("=", 1) for l in (repo / ".git/eval-hashes").read_text().split())


def git(*args, cwd=repo):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


subjects = (git("log", "--format=%s", f"{setup['head']}..{branch}") or "").splitlines()
rec = git("show", f"{branch}:{record}") or ""
m = re.search(r"(?ms)^## Evidence[ \t]*\n(.*?)(?=^## |\Z)", rec)
evidence = m.group(1) if m else ""
status = git("status", "--porcelain", cwd=worktree) if worktree.is_dir() else None
checks = {
    f"branch {branch} has one commit ending (W1)": sum(
        bool(re.search(r"\(W1\)\s*$", s)) for s in subjects
    )
    == 1,
    "the branch's record has an ## Evidence section": bool(m),
    "the evidence has a line for W1": bool(re.search(r"(?m)^\s*[-*]\s+W1\b", evidence)),
    "the evidence has the verifier's table": bool(
        re.search(r"(?m)^\s*\|\s*W\s*\|", evidence)
        and re.search(r"Implementation holds: (yes|no)", evidence)
    ),
    "the worktree is clean": status == "",
    "the checkout's branch has no new commits": (git("rev-parse", "HEAD") or "").strip()
    == setup["head"]
    and (git("symbolic-ref", "--short", "HEAD") or "").strip() == setup["branch"],
    "the implementer ran in a session of its own (its run.json exists)": run_json.is_file(),
}
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)

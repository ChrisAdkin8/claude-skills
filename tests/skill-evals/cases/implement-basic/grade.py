"""Grades the implement-basic case: python3 grade.py <fixture dir> <result.json>. Prints one line per check.

Evidence alone isn't a pass: the implementation has to hold. The verifier's last verdict is `yes`,
W1's Done when passes on what the branch committed, and the implementer's and every verifier's
session ended in success, not at a cap. The Done when is read from setup.sh, so the check is the
one the spec states, and it must fail on the setup's commit, so a check that passes on anything
can't count.
"""

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
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
# Each verifier round's run, as run-verify.sh leaves it: V1, then V2 after a fix.
verify_runs = sorted(
    (Path.home() / ".cache/implement-verify" / repo.name / base).glob("V*/run.json")
)
setup = dict(l.split("=", 1) for l in (repo / ".git/eval-hashes").read_text().split())
# W1's Done when commands, in backquotes on its line in the spec setup.sh writes, where the
# heredoc escapes them as \`.
spec = (Path(__file__).resolve().parent / "setup.sh").read_text()
line = re.search(r"(?ms)^### W1\b.*?^- \*\*Done when:\*\* (.*?)$", spec)
done_when = re.findall(r"\\`(.*?)\\`", line.group(1)) if line else []


def git(*args, cwd=repo):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def subtype(path):
    try:
        return json.loads(path.read_text()).get("subtype")
    except (OSError, ValueError, AttributeError):
        return None


def done_when_passes(rev, where):
    """Whether every Done when command exits 0 in an export of rev: the files it committed, not
    a working copy's."""
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", rev], capture_output=True
    )
    if archive.returncode != 0:
        return None
    where.mkdir()
    subprocess.run(
        ["tar", "-x", "-f", "-", "-C", str(where)], input=archive.stdout, check=True
    )
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    # Each command as its words, with no shell: these are plain commands.
    return all(
        subprocess.run(
            shlex.split(c), cwd=where, capture_output=True, env=env, timeout=120
        ).returncode
        == 0
        for c in done_when
    )


with tempfile.TemporaryDirectory() as tmp:
    after = done_when_passes(branch, Path(tmp, "after"))
    before = done_when_passes(setup["head"], Path(tmp, "before"))

subjects = (git("log", "--format=%s", f"{setup['head']}..{branch}") or "").splitlines()
rec = git("show", f"{branch}:{record}") or ""
m = re.search(r"(?ms)^## Evidence[ \t]*\n(.*?)(?=^## |\Z)", rec)
evidence = m.group(1) if m else ""
# The last verdict counts: a V1 "no" may be followed, after a fix, by V2's "yes".
verdicts = re.findall(r"Implementation holds: (yes|no)\b", evidence)
status = git("status", "--porcelain", cwd=worktree) if worktree.is_dir() else None
checks = {
    f"branch {branch} has one commit ending (W1)": sum(
        bool(re.search(r"\(W1\)\s*$", s)) for s in subjects
    )
    == 1,
    "the branch's record has an ## Evidence section": bool(m),
    "the evidence has a line for W1": bool(re.search(r"(?m)^\s*[-*]\s+W1\b", evidence)),
    "the evidence has the verifier's table, ending in Implementation holds: yes": bool(
        re.search(r"(?m)^\s*\|\s*W\s*\|", evidence)
    )
    and verdicts[-1:] == ["yes"],
    f"W1's Done when, from setup.sh ({len(done_when)} commands), fails at the setup's commit "
    "and passes at the branch's head": bool(done_when)
    and before is False
    and after is True,
    "the worktree is clean": status == "",
    "the checkout's branch has no new commits": (git("rev-parse", "HEAD") or "").strip()
    == setup["head"]
    and (git("symbolic-ref", "--short", "HEAD") or "").strip() == setup["branch"],
    "the implementer ran in a session of its own, which ended in success (its run.json)": subtype(
        run_json
    )
    == "success",
    f"every verifier run ended in success ({len(verify_runs)} V<n>/run.json)": bool(
        verify_runs
    )
    and all(subtype(p) == "success" for p in verify_runs),
}
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)

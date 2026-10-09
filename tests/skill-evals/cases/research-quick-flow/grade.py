"""Grades the research-quick-flow case: python3 grade.py <fixture dir> <result.json>. Prints one line per check.

The runner gives the note's path as EVAL_NOTE, and `git -C ~/notes status --porcelain` from before
and after the case, eval notes left out, as NOTES_BEFORE and NOTES_AFTER. The index rebuild is
expected to fail: the sandbox denies Bash writes to ~/notes, so the eval can't rewrite the real
index. The skill runs its agents in ~/.cache/agent-runs/<note's name>/<agent>, where
hooks/run-agent.sh writes a reply.md even when the run fails, so an agent counts as run only if its
session ended in success with a reply in that agent's shape.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# The repo this case lives in: tests/skill-evals/cases/<case>/grade.py.
ROOT = Path(__file__).resolve().parents[4]
# Each agent's reply shape, copied from hooks/run-agent.sh's REPLY_SHAPES, not imported.
SHAPES = {
    "researcher": [r"RESULT: (PASS|FAIL)"],
    "research-verifier": [
        r"\|\s*#\s*\|\s*Claim",
        r"Confirmed: \d+ of \d+",
        r"Bottom line holds: (yes|no)",
    ],
}

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
runs = Path.home() / ".cache/agent-runs" / note.stem


def finished(run, shape):
    """The run's session ended in success and its reply.md is in the agent's shape."""
    try:
        ok = json.loads((run / "run.json").read_text()).get("subtype") == "success"
        reply = (run / "reply.md").read_text()
    except (OSError, ValueError, AttributeError):
        return False
    return ok and all(re.search(p, reply) for p in shape)


def reply_of(path):
    """The session's final reply, from the runner's result JSON."""
    try:
        return json.loads(Path(path).read_text()).get("result") or ""
    except (OSError, ValueError, AttributeError):
        return ""


# The report's line for what its agents cost, as hooks/run-agent.md step 3 words it.
COST_LINE = re.compile(r"Agents cost (at least )?\$[0-9]")


checks = {
    "the note exists": bool(text),
    "check-note passes": "RESULT: PASS" in check,
    "the note has a Verification section": bool(
        re.search(r"(?m)^## Verification\b", text)
    ),
    "the note has a status": bool(re.search(r"(?m)^status: \w", text)),
    "~/notes is a git repo": "NOT A GIT REPO" not in before + after,
    "nothing else in ~/notes changed": before == after,
    "the final reply has an Agents cost line": bool(COST_LINE.search(reply_of(sys.argv[2]))),
}
for agent, shape in SHAPES.items():
    # <agent>, or <agent>-<n> for a later run of it.
    dirs = sorted(
        d for d in runs.glob(f"{agent}*") if re.fullmatch(rf"{agent}(-\d+)?", d.name)
    )
    checks[
        f"every {agent} run ended in success, with a reply in its shape ({len(dirs)} runs)"
    ] = bool(dirs) and all(finished(d, shape) for d in dirs)
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)

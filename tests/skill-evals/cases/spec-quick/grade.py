"""Grades the spec-quick case: python3 grade.py <fixture dir> <result.json>. Prints one line per check.

The fixture is ~/code/eval-spec-quick-<stamp>, so the skill's run dirs are
~/.cache/agent-runs/eval-spec-quick-<stamp>--<spec basename>/<agent>. hooks/run-agent.sh writes a
reply.md there even when the run fails, so the verifier counts as run only if its session ended in
success with a reply in the spec-verifier's shape.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# The repo this case lives in: tests/skill-evals/cases/<case>/grade.py.
ROOT = Path(__file__).resolve().parents[4]

repo = Path(sys.argv[1])
specs = sorted((repo / "docs/specs").glob("*.md"))
spec = specs[0] if len(specs) == 1 else None
record = spec.parent / "records" / f"{spec.stem}-record.md" if spec else None
rec = record.read_text() if record and record.exists() else ""
verification = (
    re.split(r"(?m)^## ", rec.split("## Verification", 1)[1])[0]
    if "## Verification" in rec
    else ""
)
check = (
    subprocess.run(
        [
            str(ROOT / "skills/spec/scripts/check-spec.py"),
            str(spec),
            "--repo",
            str(repo),
        ],
        capture_output=True,
        text=True,
    ).stdout
    if spec
    else ""
)
runs = Path.home() / ".cache/agent-runs"
head = dict(l.split("=", 1) for l in (repo / ".git/eval-hashes").read_text().split())[
    "head"
]


def git(*args):
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    ).stdout.strip()


# The spec-verifier's reply shape, copied from hooks/run-agent.sh's REPLY_SHAPES, not imported.
SHAPE = [r"\|\s*#\s*\|\s*Claim", r"Confirmed: \d+ of \d+", r"Plan holds: (yes|no)"]


def finished(run):
    """The run's session ended in success and its reply.md is in the agent's shape."""
    try:
        ok = json.loads((run / "run.json").read_text()).get("subtype") == "success"
        reply = (run / "reply.md").read_text()
    except (OSError, ValueError, AttributeError):
        return False
    return ok and all(re.search(p, reply) for p in SHAPE)


def reply_of(path):
    """The session's final reply, from the runner's result JSON."""
    try:
        return json.loads(Path(path).read_text()).get("result") or ""
    except (OSError, ValueError, AttributeError):
        return ""


# The report's line for what its agents cost, as hooks/run-agent.md step 3 words it.
COST_LINE = re.compile(r"Agents cost (at least )?\$[0-9]")


verifiers = sorted(runs.glob(f"{repo.name}--*/spec-verifier*"))
verified = bool(verifiers) and all(finished(r) for r in verifiers)
checks = {
    "one spec under docs/specs": spec is not None,
    "check-spec passes": "RESULT: PASS" in check,
    "the record has a Quick spec on line": bool(
        re.search(r"(?m)^- Quick spec on \d{4}-\d{2}-\d{2}", verification)
    ),
    # The verifier's round, as "Confirmed: N of M" or "N of M claims confirmed": it shows the
    # run went on past the verifier.
    "the record has a Confirmed: line": bool(
        re.search(
            r"(?i)confirmed:?\s*\d+ of \d+|\d+ of \d+ claims confirmed", verification
        )
    ),
    f"every spec-verifier run ended in success, with a reply in its shape ({len(verifiers)} runs)": verified,
    "no cold review was launched": not any(runs.glob(f"{repo.name}--*/cold-reviewer*")),
    "nothing committed": git("rev-parse", "--short", "HEAD") == head,
    "the final reply has an Agents cost line": bool(COST_LINE.search(reply_of(sys.argv[2]))),
}
for name, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)

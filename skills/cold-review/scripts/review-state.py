#!/usr/bin/env python3
"""Where a document stands in its review: which review round it's due, and what changed since
its saved review. /cold-review runs this in step 1 instead of working it out by hand.

Usage: review-state.py <markdown file>

Prints `key: value` lines, then `state:` last:

  full       no saved review: run the full review
  delta      a saved review, `Not reviewed:` lines and no delta review yet: run the delta review
  unlogged   a saved review, no `Not reviewed:` lines, but the document changed since: draft
             `Not reviewed:` lines from `headings:` for the user to confirm, then run the delta
  unchanged  a saved review, and the document hasn't changed since: nothing to do
  no-base    a saved review, no `Not reviewed:` lines, and no commit to diff from: unlogged
             changes can't be found
  done       the full review and its delta review have both run: no third round

The review lives in the record, records/<basename>-record.md beside the document, or in an
older document under its own `## Cold review`. The review commit is the oldest commit that
added the review's "Reviewed on <date> by" line, searched in the record and the document
together, so it survives a later move of the review into a record. If the review is now in a
record and that commit also changed a document that already existed, the diff base is the
commit's parent, so folds saved in the same commit aren't missed. Read-only: runs git log,
show, cat-file and diff, nothing else.
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research" / "scripts"))
from mdcheck import NOT_REVIEWED, section

DATE_LINE = re.compile(r"Reviewed on (\d{4}-\d{2}-\d{2}) by")
DELTA = re.compile(r"###\s+Delta review")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def git(root, *args):
    run = subprocess.run(
        ["git", "--no-pager", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    return run.stdout if run.returncode == 0 else None


def headings_at(lines, numbers):
    """The heading each 1-based line number falls under, in document order, fences skipped."""
    owner, current, fence = {}, "(before the first heading)", None
    for n, line in enumerate(lines, start=1):
        m = re.match(r"\s*(`{3,}|~{3,})", line)
        if m and fence is None:
            fence = m.group(1)
        elif m and fence and line.strip()[0] == fence[0] and len(line.strip()) >= len(fence):
            fence = None
        elif fence is None and re.match(r"#{1,6}\s", line):
            current = line.strip()
        owner[n] = current
    found = []
    for n in sorted(numbers):
        heading = owner.get(
            min(n, len(lines)) if lines else 0, "(before the first heading)"
        )
        if heading not in found:
            found.append(heading)
    return found


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: review-state.py <markdown file>")
    doc = Path(sys.argv[1]).expanduser().resolve()
    if not doc.is_file():
        sys.exit(f"review-state: no such file: {doc}")
    out = {"document": str(doc)}
    record = doc.parent / "records" / f"{doc.stem}-record.md"
    doc_lines = doc.read_text(errors="replace").splitlines()
    rec_lines = (
        record.read_text(errors="replace").splitlines() if record.is_file() else []
    )
    out["record"] = str(record) if record.is_file() else "none"

    review, where = section(rec_lines, "## Cold review"), "record"
    if review is None:
        review, where = section(doc_lines, "## Cold review"), "document"
    if review is None:
        where = "none"
    out["review"] = where
    date = next((m.group(1) for l in review or [] if (m := DATE_LINE.search(l))), None)
    out["review-date"] = date or "none"
    delta = any(DELTA.match(l) for l in review or [])
    out["delta-review"] = "yes" if delta else "no"
    if where == "record" or rec_lines:
        logged = [l.strip() for l in rec_lines if NOT_REVIEWED.match(l)]
    else:
        logged = [
            l.strip()
            for l in section(doc_lines, "## Open questions") or []
            if NOT_REVIEWED.match(l)
        ]
    out["not-reviewed"] = str(len(logged))

    root = git(doc.parent, "rev-parse", "--show-toplevel")
    root = Path(root.strip()) if root else None
    out["repo"] = str(root) if root else "none"
    base = None
    if root:
        out["head"] = (git(root, "rev-parse", "--short", "HEAD") or "none").strip()
        rel = doc.relative_to(root).as_posix()
        if where != "none":
            needle = f"Reviewed on {date} by" if date else "## Cold review"
            paths = [
                p.relative_to(root).as_posix() for p in (record, doc) if p.is_file()
            ]
            hits = (
                git(root, "log", "--format=%h", f"-S{needle}", "--", *paths) or ""
            ).split()
            commit = hits[-1] if hits else None
            out["review-commit"] = commit or "none"
            if commit:
                base = commit
                touched = git(root, "show", "--stat", "--format=", commit, "--", rel)
                existed = git(root, "cat-file", "-e", f"{commit}^:{rel}") is not None
                if where == "record" and touched and touched.strip() and existed:
                    base = f"{commit}^"
                base = (git(root, "rev-parse", "--short", base) or base).strip()
        out["base"] = base or "none"
        if base:
            out["diff"] = f"git -C {root} diff {base} -- {rel}"
            stat = (git(root, "diff", "--stat", base, "--", rel) or "").strip()
            out["changed"] = "yes" if stat else "no"
            if stat:
                out["stat"] = stat.splitlines()[-1].strip()
                hunks = git(root, "diff", "-U0", base, "--", rel) or ""
                lines = {int(m.group(1)) or 1 for m in HUNK.finditer(hunks)}
                out["headings"] = "; ".join(headings_at(doc_lines, lines))

    if where == "none":
        state = "full"
    elif delta:
        state = "done"
    elif logged:
        state = "delta"
    elif not base:
        state = "no-base"
    else:
        state = "unlogged" if out.get("changed") == "yes" else "unchanged"

    for key, value in out.items():
        print(f"{key}: {value}")
    for line in logged:
        print(f"logged: {line}")
    print(f"state: {state}")


if __name__ == "__main__":
    main()

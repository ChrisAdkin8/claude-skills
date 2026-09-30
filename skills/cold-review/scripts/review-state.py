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
(each followed through renames), so it survives a later move of the review into a record, or
a rename of either. If the review is now in a record and that commit also changed a document
that already existed, the diff base is the commit's parent, so folds saved in the same commit
aren't missed. The diff names the document's old path too, if it was renamed since, and is
printed as a git-read.py command, which /cold-review may run without a prompt.
In a shallow clone, a review commit with no parent may be the clone's cut-off rather than the
commit that added the review, so there is no base. Read-only: runs git log, show, cat-file,
merge-base, rev-parse and diff, nothing else.
"""

import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research" / "scripts"))
from mdcheck import (  # noqa: E402  shared with the checkers
    DELTA_REVIEW, NOT_REVIEWED, in_code, is_heading, record_path, section, strip_code,
)

DATE_LINE = re.compile(r"Reviewed on (\d{4}-\d{2}-\d{2}) by")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def git(root, *args):
    run = subprocess.run(
        ["git", "--no-pager", "-c", "core.quotePath=off", "-C", str(root), *args],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    return run.stdout if run.returncode == 0 else None


def headings_at(lines, numbers):
    """The heading each 1-based line number falls under, in document order, fences skipped."""
    owner, current = {}, "(before the first heading)"
    for n, (line, code) in enumerate(zip(lines, in_code(lines)), start=1):
        if not code and is_heading(line):
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


def oldest(root, commits):
    """The earliest of commits on one line of history."""
    first = None
    for commit in commits:
        if first is None or git(root, "merge-base", "--is-ancestor", commit, first) is not None:
            first = commit
    return first


def git_read_command():
    """git-read.py by the path this script finds it at (hooks/ beside skills/), quoted for the
    shell. While ~/.claude/hooks is a link to the same hooks/, it is spelled `~/.claude/hooks/...`
    with the ~ unquoted so the shell expands it, because the skill's allowed-tools names that
    spelling until the skills move to ${CLAUDE_PLUGIN_ROOT}."""
    script = Path(__file__).resolve().parents[3] / "hooks" / "git-read.py"
    legacy = Path.home() / ".claude" / "hooks" / "git-read.py"
    if legacy.exists() and legacy.resolve() == script:
        return "~/.claude/hooks/git-read.py"
    return shlex.quote(str(script))


def path_at(root, commit, rel):
    """What `rel` was called at `commit`, if it has been renamed since."""
    for line in (git(root, "diff", "-M", "--name-status", commit, "--") or "").splitlines():
        status, *names = line.split("\t")
        if status.startswith("R") and len(names) == 2 and names[1] == rel:
            return names[0]
    return rel


def changed_lines(hunks):
    """1-based line numbers of the document each `-U0` hunk touches. A hunk that only deletes
    has no lines of its own, so it counts the line it follows."""
    lines = set()
    for m in HUNK.finditer(hunks):
        start, count = int(m.group(1)), int(m.group(2) or 1)
        lines.update(range(start, start + count) if count else [max(start, 1)])
    return lines


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: review-state.py <markdown file>")
    doc = Path(sys.argv[1]).expanduser().resolve()
    if not doc.is_file():
        sys.exit(f"review-state: no such file: {doc}")
    out = {"document": str(doc)}
    record = record_path(doc)
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
    delta = any(DELTA_REVIEW.match(l) for l in strip_code(review or []))
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
            # One path at a time, following renames: otherwise a later `git mv` of the record
            # is the oldest commit that "added" the line, and the edits before it are missed.
            hits = [
                found.split()[-1]
                for path in paths
                if (found := git(root, "log", "--follow", "--format=%h", f"-S{needle}", "--", path))
                and found.strip()
            ]
            commit = oldest(root, hits)
            shallow = (git(root, "rev-parse", "--is-shallow-repository") or "").strip() == "true"
            if commit and shallow and git(root, "rev-parse", "--verify", "--quiet", f"{commit}^") is None:
                # The clone's cut-off commit "adds" every line in it, so it isn't the review.
                commit = None
            out["review-commit"] = commit or "none"
            if commit:
                base = commit
                old = path_at(root, commit, rel)
                touched = git(root, "show", "--stat", "--format=", commit, "--", old)
                existed = git(root, "cat-file", "-e", f"{commit}^:{old}") is not None
                if where == "record" and touched and touched.strip() and existed:
                    base = f"{commit}^"
                base = (git(root, "rev-parse", "--short", base) or base).strip()
        out["base"] = base or "none"
        if base:
            # Both names if the document was renamed since, so the diff pairs them up.
            names = list(dict.fromkeys([path_at(root, base, rel), rel]))
            out["diff"] = git_read_command() + " " + shlex.join(
                ["-C", str(root), "diff", "-M", base, "--", *names]
            )
            stat = (git(root, "diff", "-M", "--stat", base, "--", *names) or "").strip()
            out["changed"] = "yes" if stat else "no"
            if stat:
                out["stat"] = stat.splitlines()[-1].strip()
                hunks = git(root, "diff", "-M", "-U0", base, "--", *names) or ""
                out["headings"] = "; ".join(headings_at(doc_lines, changed_lines(hunks)))

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

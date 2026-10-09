#!/usr/bin/env python3
"""Where a document stands in its review: which review round it's due, and what changed since
its saved review. /cold-review runs this in step 1 instead of working it out by hand.

Usage: review-state.py [--plan] <markdown file>

Prints `key: value` lines, then `state:` last:

  full       no saved review: run the full review
  delta      a saved review, `Not reviewed:` lines and no delta review yet: run the delta review
  unlogged   a saved review, no `Not reviewed:` lines, but the document changed since: draft
             `Not reviewed:` lines from `headings:` for the user to confirm, then run the delta
  unchanged  a saved review, and the document hasn't changed since: nothing to do
  no-base    a saved review, no `Not reviewed:` lines, and no commit to diff from: unlogged
             changes can't be found
  done       the full review and its delta review have both run, and nothing has changed
             since the delta review, or each change since is logged: no third round

The review lives in the record, records/<basename>-record.md beside the document, or in an
older document under its own `## Cold review`. mdcheck.read_review() reads it, the same parser
check-spec.py uses: a review counts only with `Reviewed on <date> by` as its first line, a delta
only with its own such line under `### Delta review, <date>`, and `Not reviewed:` lines only
under a document's `## Open questions` or a record's `## Changes since the review`, `## Changes
after the delta review` or `## Spikes`, never inside the reviewer's reply. If the document was
moved without its record (a committed or a staged `git mv`), the record under its earlier name
is used and `record-moved:` names it. `not-reviewed-from:` says which sections the lines came
from, and each `placeholder:` line is a record-template token left in the record.

The review commit is the oldest commit that added the review's "Reviewed on <date> by" line,
searched in the record found and the document (each followed through renames), so it survives a
later move of the review into a record, or a rename of either. If the review is now in a record
and that commit also changed a document that already existed, the diff base is the commit's
parent, so folds saved in the same commit aren't missed. The diff names the document's old path too, if it was renamed since, and is
printed as a git-read.py command, which /cold-review may run without a prompt. `changed:` is yes
only if a line was added or deleted: a rename with no edits isn't a change.
In a shallow clone, a review commit with no parent may be the clone's cut-off rather than the
commit that added the review, so there is no base. Read-only: runs git log, show, cat-file,
merge-base, rev-parse and diff, nothing else.

After a delta review, the base is the commit that added its `### Delta review, <date>` heading
(`delta-commit:`), itself, never its parent: edits saved in that commit are the ones it reviewed.
A change since then with no `Not reviewed:` line logged after it (one that wasn't in its file at
that commit) is `unlogged`; with one, or with no change, it's `done`. Until the heading is
committed, as /cold-review leaves it, the state is `done`.

--plan, for /implement's gate: only changes to the document's `## Decision`, `## Design` and
`## Work items` count, with each citation's line numbers (`path:12`, `:12-14`) set aside, since
only those changes are logged as `Not reviewed:`. A status change, a moved `read-at` or a re-cite
reads `unchanged`, and `headings:` names the plan's changed headings only.
"""

import re
import shlex
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research" / "scripts"))
from mdcheck import (  # shared with the checkers
    DELTA_HEADING,
    earlier_paths,
    heading_is,
    in_code,
    is_heading,
    level,
    read_review,
    record_for,
    record_path,
)

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)
# The sections --plan compares, and a citation's line numbers, which it sets aside.
PLAN = ("## Decision", "## Design", "## Work items")
LINE_NUMBERS = re.compile(r":\d+(?:\s*[-–]\s*\d+)?")


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
        if (
            first is None
            or git(root, "merge-base", "--is-ancestor", commit, first) is not None
        ):
            first = commit
    return first


def git_read_command():
    """git-read.py by the path this script finds it at (hooks/ beside skills/), quoted for the
    shell. It is the absolute spelling the skill's allowed-tools expand ${CLAUDE_PLUGIN_ROOT} to."""
    return shlex.quote(
        str(Path(__file__).resolve().parents[3] / "hooks" / "git-read.py")
    )


def path_at(root, commit, rel):
    """What `rel` was called at `commit`, if it has been renamed since."""
    for line in (
        git(root, "diff", "-M", "--name-status", commit, "--") or ""
    ).splitlines():
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


def lines_at(root, commit, path):
    """The stripped lines of `path` as it was at `commit`; empty if it wasn't there."""
    name = path_at(root, commit, path.relative_to(root).as_posix())
    return {line.strip() for line in (git(root, "show", f"{commit}:{name}") or "").splitlines()}


def plan_blocks(lines):
    """The Decision, Design and Work items, as {heading: its lines}, each heading the nearest one
    above, with citations' line numbers set aside. Fences are skipped for headings only."""
    blocks, inside, current = {}, False, None
    for line, code in zip(lines, in_code(lines)):
        if not code and is_heading(line):
            if level(line) <= 2:
                inside = any(heading_is(line, h) for h in PLAN)
            current = line.strip()
            if inside:
                blocks.setdefault(current, [])
            continue
        if inside:
            blocks[current].append(LINE_NUMBERS.sub(":N", line.rstrip()))
    return blocks


def plan_changes(old_lines, new_lines):
    """The plan headings whose text differs, in the new document's order, then any removed."""
    old, new = plan_blocks(old_lines), plan_blocks(new_lines)
    return [h for h in new if old.get(h) != new[h]] + [h for h in old if h not in new]


def oldest_adding(root, needle, paths):
    """The oldest commit that added `needle` to any of `paths`, each followed through renames:
    otherwise a later `git mv` of the record is the oldest commit that "added" it. None in a
    shallow clone if it's the clone's cut-off, which "adds" every line in it."""
    hits = [
        found.split()[-1]
        for path in paths
        if (found := git(root, "log", "--follow", "--format=%h", f"-S{needle}", "--", path))
        and found.strip()
    ]
    commit = oldest(root, hits)
    shallow = (git(root, "rev-parse", "--is-shallow-repository") or "").strip() == "true"
    if commit and shallow and git(root, "rev-parse", "--verify", "--quiet", f"{commit}^") is None:
        return None, True
    return commit, False


def main():
    args = sys.argv[1:]
    plan = args[:1] == ["--plan"]
    if plan:
        args = args[1:]
    if len(args) != 1:
        sys.exit("usage: review-state.py [--plan] <markdown file>")
    doc = Path(args[0]).expanduser().resolve()
    if not doc.is_file():
        sys.exit(f"review-state: no such file: {doc}")
    out = {"document": str(doc)}
    root = git(doc.parent, "rev-parse", "--show-toplevel")
    root = Path(root.strip()) if root else None
    rel = doc.relative_to(root).as_posix() if root else None
    earlier = (
        [root / p for p in earlier_paths(lambda *a: git(root, *a), rel)] if root else []
    )
    record = record_for(doc, earlier)
    doc_lines = doc.read_text(errors="replace").splitlines()
    rec_lines = record.read_text(errors="replace").splitlines() if record else []
    out["record"] = str(record) if record else "none"
    if record and record != record_path(doc):
        out["record-moved"] = str(record)

    review = read_review(doc_lines, rec_lines)
    where, date = review.where or "none", review.date
    out["review"] = where
    out["review-date"] = date or "none"
    delta = review.delta_date is not None
    out["delta-review"] = "yes" if delta else "no"
    logged = [text for _, _, text in review.not_reviewed]
    out["not-reviewed"] = str(len(logged))
    if logged:
        files = {"document": doc.name, "record": record.name if record else "none"}
        counts = Counter(
            tuple(source.split(" ", 1)) for source, _, _ in review.not_reviewed
        )
        out["not-reviewed-from"] = "; ".join(
            f"{files[file]} {heading} ({n})" for (file, heading), n in counts.items()
        )

    out["repo"] = str(root) if root else "none"
    if plan:
        out["plan"] = "yes: only the Decision, Design and Work items count"
    base, since_delta, delta_commit, delta_cut_off = None, None, None, False
    if root:
        out["head"] = (git(root, "rev-parse", "--short", "HEAD") or "none").strip()
        if where != "none":
            paths = [
                p.relative_to(root).as_posix()
                for p in (record, doc)
                if p and p.is_file()
            ]
            commit, _ = oldest_adding(root, f"Reviewed on {date} by", paths)
            out["review-commit"] = commit or "none"
            if commit:
                base = commit
                old = path_at(root, commit, rel)
                touched = git(root, "show", "--stat", "--format=", commit, "--", old)
                existed = git(root, "cat-file", "-e", f"{commit}^:{old}") is not None
                if where == "record" and touched and touched.strip() and existed:
                    base = f"{commit}^"
                base = (git(root, "rev-parse", "--short", base) or base).strip()
            if delta:
                # Its heading, not its `Reviewed on` line, which a full review on the same date
                # shares.
                heading = f"{DELTA_HEADING}, {review.delta_date}"
                delta_commit, delta_cut_off = oldest_adding(root, heading, paths)
                out["delta-commit"] = delta_commit or "none"
                if delta_commit:
                    base = (git(root, "rev-parse", "--short", delta_commit) or delta_commit).strip()
                    # `Not reviewed:` lines that weren't in their file at that commit.
                    then = {
                        "document": lines_at(root, delta_commit, doc),
                        "record": lines_at(root, delta_commit, record) if record else set(),
                    }
                    since_delta = [
                        line
                        for source, _, line in review.not_reviewed
                        if line not in then[source.split(" ", 1)[0]]
                    ]
                elif delta_cut_off:
                    base = None
        out["base"] = base or "none"
        if base:
            # Both names if the document was renamed since, so the diff pairs them up.
            names = list(dict.fromkeys([path_at(root, base, rel), rel]))
            out["diff"] = (
                git_read_command()
                + " "
                + shlex.join(["-C", str(root), "diff", "-M", base, "--", *names])
            )
            # --numstat, not --stat: a rename with no edits is a 0-line rename line in --stat,
            # but no change to the document.
            numstat = git(root, "diff", "-M", "--numstat", base, "--", *names) or ""
            changed = any(
                line.split("\t")[:2] != ["0", "0"]
                for line in numstat.splitlines()
                if line
            )
            plan_headings = []
            if plan and changed:
                then = git(root, "show", f"{base}:{names[0]}") or ""
                plan_headings = plan_changes(then.splitlines(), doc_lines)
                changed = bool(plan_headings)
            out["changed"] = "yes" if changed else "no"
            if changed:
                stat = (
                    git(root, "diff", "-M", "--stat", base, "--", *names) or ""
                ).strip()
                out["stat"] = stat.splitlines()[-1].strip()
                hunks = git(root, "diff", "-M", "-U0", base, "--", *names) or ""
                out["headings"] = "; ".join(
                    plan_headings or headings_at(doc_lines, changed_lines(hunks))
                )

    if where == "none":
        state = "full"
    elif delta and delta_cut_off:
        state = "no-base"
    elif delta and not delta_commit:
        state = "done"  # not committed yet, as /cold-review leaves it, or no repo
    elif delta:
        unlogged = out.get("changed") == "yes" and not since_delta
        state = "unlogged" if unlogged else "done"
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
    for line, token in review.placeholders:
        print(f"placeholder: {line}: {token}")
    print(f"state: {state}")


if __name__ == "__main__":
    main()

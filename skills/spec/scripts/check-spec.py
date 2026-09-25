#!/usr/bin/env python3
"""Check a /spec implementation spec's citations, structure and links before it is verified.

Usage: check-spec.py <spec.md> [--repo DIR] [--cite-repo DIR] [--read-at SHA]

--repo defaults to the git repo containing the spec. --cite-repo is the repo that `path:line`
citations point into; it defaults to the spec's `cite-repo` frontmatter, else --repo (a new,
empty repo cites the repo it borrows fixtures or code from). --read-at defaults to the spec's
`read-at` frontmatter, a commit in the cite repo, or `none` when there was nothing to read.

Citations are checked against the files as they were at read-at, because that's what the spec
describes; drift since then is reported separately. `(:48)` after a full citation in the same
paragraph means the same file. Prints FAIL, WARN and INFO lines and exits 1 if anything failed.

A spec holds the plan; its review history lives in its record, `records/<spec basename>-record.md`
beside it: the cold review and any delta review, the `Not reviewed:` changes since, verifier
rounds, spike routing and implementation notes. The plan is held to the word limit until the spec
is done. Older specs that keep that history in the spec itself (a `## Cold review` section, `Not
reviewed:` lines in Open questions, Route/Changes/Expect/Box lines under spike questions) are
still read, with a WARN to move it to the record.

Checks only what can be checked mechanically: that every citation points at a file and at lines
that existed, whether cited files have changed since, work items and acceptance criteria, and,
for specs written from the skill template, sections and leftover template text. Whether a cited
line says what the spec claims is the spec-verifier agent's job.
"""

import argparse
import collections
import re
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research" / "scripts"))
from mdcheck import (  # noqa: E402  shared with check-note.py
    ACCOUNT_ID, INLINE_CODE, SECRETS, SEPARATOR, frontmatter, section, strip_code,
)
import mdcheck  # noqa: E402

TEMPLATE = Path.home() / ".claude" / "skills" / "spec" / "template.md"
REQUIRED = [
    "## Goal",
    "## Decision",
    "## Background",
    "## Non-goals",
    "## Work items",
    "## Spike questions",
]
STATUSES = ("draft", "reviewed", "in-progress", "done", "superseded")
WORD_WARN, WORD_FAIL = 3000, 4000  # template specs
# Statuses where the spec is still the plan someone works from, so the limit holds. Once done or
# superseded it's a record, and length only warns.
LIVE = ("draft", "reviewed", "in-progress")
HOUSE_WORD_WARN = 5000  # house-format specs follow their repo's own norms
# `path/to/file.py:12` or `file.py:12-20`. The lookbehind stops matches starting mid-URL
# (https://host/x.py:1) or mid-token; the lookahead stops `:1.2` version strings but lets a
# citation end a sentence.
CITATION = re.compile(
    r"(?<![\w/:.@-])((?:[\w.-]+/)+[\w.-]+|[\w-][\w.-]*\.\w+):(\d+)(?:[-–](\d+))?(?!\w|\.\d)"
)
# `:48`, `(:48)`, (:48) or (:14, :36-40), continuing the last full citation in the paragraph.
# Group 1 is the list of `:N` or `:N-M` items.
SHORTHAND = re.compile(
    r"(?:`\(?|\()(:\d+(?:[-–]\d+)?(?:\s*,\s*:\d+(?:[-–]\d+)?)*)(?:\)?`|\))"
)
SHORT_ITEM = re.compile(r":(\d+)(?:[-–](\d+))?")
# ~/path:12 or /abs/path:12: outside the cite repo, so they can't be checked.
ABSOLUTE = re.compile(r"(?<![\w/.:-])(~?/[\w./-]+\.\w+):(\d+)(?:[-–](\d+))?(?!\w|\.\d)")
# [4], [1, 7] or [8-9] outside inline code, but not a markdown link [4](url).
SOURCE_REF = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()")
READ_AT_LINE = re.compile(r"[Rr]ead at (?:commit )?`?([0-9a-f]{7,40})\b")
# Bare filenames with these extensions are citations even if nothing matches; others
# (example.com:443) may be hosts.
CODE_EXT = re.compile(
    r"\.(py|sh|bash|md|ya?ml|json|toml|tf|tfvars|hcl|go|rs|ts|tsx|js|jsx|tpl|txt|cfg|ini|mk|sql|rb|java|kt|c|h|cpp)$"
)
NOTE_PATH = re.compile(r"~/notes/[\w./-]+\.md")
# The indented lines /spec's step 7 folds under a spike question, and the repo-relative
# results files they cite.
SPIKE_ANSWER = re.compile(r"\s*(?:Answered|Partly answered|Open):")
# Every line step 7 folds under a spike question. Like a saved cold review, they record a round
# that has happened, so they're left out of the word count: a fold shouldn't push an author's
# spec over the limit, when the only way back under would be cutting their prose.
SPIKE_FOLD = re.compile(
    r"\s+(?:Route|Changes|Expect|Box|Answered|Partly answered|Open):"
)
RESULTS_PATH = re.compile(r"(?<![\w./~-])[\w.-][\w./-]*/spikes/[\w.-]+-results\.md")
# The ledger of changes made after the cold review, and the delta review of them.
NOT_REVIEWED = re.compile(r"\s*[-*]\s+Not reviewed:")
ROUND_LINE = re.compile(r"\s*[-*]\s+Verifier round 2 ran on")
IMPLEMENTATION = "## Implementation"
DELTA_REVIEW = re.compile(r"###\s+Delta review")
WORK_ITEM = re.compile(r"^#{2,3}\s+W(\d+)\b")
DONE_WHEN = re.compile(r"done when", re.IGNORECASE)
ACCEPTANCE = "## Acceptance criteria"
EMPTY_FIELD = re.compile(r"^\s*-\s+\*\*[^*]+:\*\*\s*$")
NESTED_ITEM = re.compile(r"\s+(?:[-*]|\d+\.)\s+\S")


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    return result.stdout.rstrip("\n") if result.returncode == 0 else None


def split_cold_review(lines, warns):
    """Split off a saved '## Cold review' section. It records the reviewer's reply unchanged, so
    it's left out of the word count and the citation, link and template checks, which the
    author couldn't fix without editing the reviewer's words. The secrets check still reads it."""
    at = next((i for i, line in enumerate(lines) if line.startswith("## Cold review")), None)
    if at is None:
        return lines, []
    end = next(
        (j for j in range(at + 1, len(lines)) if lines[j].startswith("## ")), len(lines)
    )
    if end < len(lines):
        warns.append(
            "'## Cold review' isn't the spec's last section; it records the reviewer's reply, "
            "so it goes at the end"
        )
    return lines[:at] + lines[end:], lines[at:end]


def body_status(body):
    """A house-format spec's status, from its opening lines: a `Status: <status>` line (bold or
    quoted is fine), or a SHIPPED or SUPERSEDED banner such as k8s-ai-observability's. None if
    it states none."""
    for line in body[:25]:
        if m := re.match(r"[>\s]*(?:\*\*)?status(?:\*\*)?\s*:\s*(?:\*\*)?\s*([a-z-]+)", line, re.I):
            if m.group(1).lower() in STATUSES:
                return m.group(1).lower()
        if re.search(r"\bSUPERSEDED\b", line):
            return "superseded"
        if re.search(r"\bSHIPPED\b|this is a RECORD", line):
            return "done"
    return None


def record_path(spec):
    """Where a spec's record lives: records/<basename>-record.md beside it."""
    return spec.parent / "records" / f"{spec.stem}-record.md"


def read_record(path):
    """(lines, cold review lines, Not reviewed lines, implementation entries) of a record, or
    empty values if there isn't one."""
    if not path.is_file():
        return [], [], [], []
    lines = path.read_text(errors="replace").splitlines()
    review = section(lines, "## Cold review") or []
    changes = [l for l in lines if NOT_REVIEWED.match(l)]
    implemented = [
        l for l in section(lines, IMPLEMENTATION) or [] if re.match(r"\s*[-*]\s+\S", l)
    ]
    return lines, review, changes, implemented


def template_prompts():
    """Prose lines from the template that should never survive into a finished spec."""
    return mdcheck.template_prompts(TEMPLATE, skip=("#", "|", "---", "- **"))


class Snapshot:
    """The cite repo as it was at read-at, falling back to the working tree for files that
    didn't exist then (new since, or untracked when the spec was read)."""

    def __init__(self, repo, read_at):
        self.repo, self.read_at = repo, read_at
        files = git(repo, "ls-tree", "-r", "--name-only", read_at) if read_at else None
        self.files = set((files or "").splitlines())
        self.dirs = {
            str(p) for f in self.files for p in Path(f).parents if str(p) != "."
        }
        tracked = (git(repo, "ls-files") or "").splitlines()
        self.by_name = {}
        for path in self.files | set(tracked):
            self.by_name.setdefault(Path(path).name, []).append(path)
        self._lengths = {}

    def length_at_read(self, rel):
        if rel not in self._lengths:
            blob = git(self.repo, "show", f"{self.read_at}:{rel}")
            self._lengths[rel] = len(blob.splitlines()) if blob is not None else None
        return self._lengths[rel]

    def exists(self, rel):
        return rel in self.files or (self.repo / rel).is_file()

    def dir_exists(self, top):
        return top in self.dirs or (self.repo / top).is_dir()


def working_length(path):
    return len(path.read_text(errors="replace").splitlines())


def check_range(snap, rel, start, end, ref, fails, warns):
    """Check a line range against the file at read-at; else against the working tree."""
    if start < 1 or end < start:
        fails.append(f"{ref}: invalid line range")
        return
    target = snap.repo / rel
    if rel in snap.files:
        length = snap.length_at_read(rel)
        if length is not None and end <= length:
            return
        dirty = git(snap.repo, "status", "--porcelain", "--", rel)
        if dirty and target.is_file() and end <= working_length(target):
            warns.append(
                f"{ref}: cites lines that were uncommitted when the spec was read; "
                "commit them or re-cite after they land"
            )
        else:
            fails.append(
                f"{ref}: the file had only {length} lines at read-at {snap.read_at}"
            )
    elif target.is_file():
        length = working_length(target)
        if end > length:
            fails.append(f"{ref}: file has only {length} lines")
    else:
        fails.append(f"{ref}: no such file in {snap.repo}")


def check_citations(body, snap, templated, fails, warns):
    """Return the set of cite-repo files cited, and the citation count."""
    cited, count, bare, unresolved, orphans = set(), 0, [], [], []
    last_file = None  # the file a `:48` shorthand refers to
    last_bad = None  # the last full citation, if it didn't resolve to a checkable file
    for line in body:
        if not line.strip() or line.startswith("#"):
            last_file = last_bad = (
                None  # a shorthand only continues within its paragraph
            )
            continue
        matches = [(m.start(), "full", m) for m in CITATION.finditer(line)]
        matches += [(m.start(), "short", m) for m in SHORTHAND.finditer(line)]
        matches += [(m.start(), "abs", m) for m in ABSOLUTE.finditer(line)]
        for _, kind, m in sorted(matches, key=lambda t: t[0]):
            if kind == "abs":
                unresolved.append(m.group(0))
                last_file, last_bad = None, m.group(1)
                continue
            if kind == "short":
                for item in SHORT_ITEM.finditer(m.group(1)):
                    if last_bad is not None:
                        # Its file was already reported; list it with the unresolved ones.
                        unresolved.append(f"{last_bad}{item.group(0)}")
                    elif last_file is None:
                        orphans.append(item.group(0))
                    else:
                        start = int(item.group(1))
                        end = int(item.group(2)) if item.group(2) else start
                        count += 1
                        ref = f"{last_file}{item.group(0)}"
                        check_range(snap, last_file, start, end, ref, fails, warns)
                continue
            path, start = m.group(1), int(m.group(2))
            end = int(m.group(3)) if m.group(3) else start
            rel = path.removeprefix("./")
            ref = m.group(0)
            if ".." in Path(rel).parts:
                unresolved.append(ref)  # climbs out of the cite repo
                last_file, last_bad = None, rel
                continue
            if snap.exists(rel):
                count += 1
                cited.add(rel)
                last_file, last_bad = rel, None
                check_range(snap, rel, start, end, ref, fails, warns)
                continue
            if "/" in rel and snap.dir_exists(rel.split("/")[0]):
                count += 1
                fails.append(f"{ref}: no such file in {snap.repo}")
            elif "/" not in rel and rel in snap.by_name:
                count += 1
                bare.append(ref)
            elif CODE_EXT.search(rel) or ("/" in rel and "." in Path(rel).name.lstrip(".")):
                unresolved.append(ref)
            else:
                # No file extension and nothing on disk: svc/name:9090, ghcr.io/o/app:2,
                # registry.k8s.io/pause:3, host:port. Not a citation.
                continue
            last_file, last_bad = None, rel
    if bare:
        shown = ", ".join(bare[:5]) + (
            f" and {len(bare) - 5} more" if len(bare) > 5 else ""
        )
        warns.append(
            f"{len(bare)} citations give a bare filename ({shown}); "
            "cite the path from the repo root so they can be checked"
        )
    if unresolved:
        shown = ", ".join(unresolved[:5]) + (
            f" and {len(unresolved) - 5} more" if len(unresolved) > 5 else ""
        )
        # Nobody can check these, so a template spec may not rest on them.
        (fails if templated else warns).append(
            f"{len(unresolved)} path-like citations don't resolve in {snap.repo} ({shown}). "
            "Fix the path; or, for another local repo, set cite-repo; or cite code that "
            "isn't cloned here by URL at a fixed commit (https://github.com/o/r/blob/<sha>/path#L10-L20)"
        )
    if orphans:
        warns.append(
            f"{len(orphans)} shorthand citations ({', '.join(orphans[:5])}) have no full "
            "citation earlier in their paragraph to take a file from"
        )
    return cited, count


def has_nested_list(lines, i):
    """True if the first non-blank line after lines[i] is an indented list item."""
    rest = [l for l in lines[i + 1 :] if l.strip()]
    return bool(rest) and bool(NESTED_ITEM.match(rest[0]))


def done_when(chunk):
    """Return a problem with a work item's 'Done when', or None if it has content."""
    for i, line in enumerate(chunk):
        m = DONE_WHEN.search(line)
        if not m:
            continue
        if line[m.end() :].strip(" *:"):
            return None
        # Criteria may follow as a nested list.
        if has_nested_list(chunk, i):
            return None
        return "has an empty 'Done when'"
    return "has no 'Done when'"


def check_work_items(body, templated, fails, warns):
    """Every work item needs observable acceptance criteria: its own 'Done when', or, in a
    house format that keeps them together, a non-empty '## Acceptance criteria' section."""
    items = [
        (i, int(m.group(1))) for i, l in enumerate(body) if (m := WORK_ITEM.match(l))
    ]
    acceptance = section(body, ACCEPTANCE)
    shared = (
        not templated and acceptance is not None and any(l.strip() for l in acceptance)
    )
    for idx, (at, num) in enumerate(items):
        stop = items[idx + 1][0] if idx + 1 < len(items) else len(body)
        chunk = body[at + 1 : stop]
        chunk = chunk[
            : next((j for j, l in enumerate(chunk) if l.startswith("## ")), len(chunk))
        ]
        verdict = done_when(chunk)
        if verdict and not shared:
            fails.append(
                f"W{num} {verdict}"
                + ("" if templated else f", and there's no '{ACCEPTANCE}' section")
            )
    nums = [n for _, n in items]
    # A later part of a split spec keeps its numbers (W4..W7), so commits naming them still
    # match; what matters is that they run on in order.
    if templated and nums and nums != list(range(nums[0], nums[0] + len(nums))):
        warns.append(
            f"work items are numbered {nums}; expected W{nums[0]}..W{nums[0] + len(nums) - 1} "
            "in order"
        )
    if templated and not items:
        fails.append("'## Work items' has no '### W1' items")
    if not templated and not items and not shared:
        warns.append(
            f"no W-numbered work items and no '{ACCEPTANCE}' section: "
            "nothing says how anyone will know it worked"
        )
    return items


def main():
    parser = argparse.ArgumentParser(description="Check a /spec implementation spec.")
    parser.add_argument("spec")
    parser.add_argument("--repo")
    parser.add_argument("--cite-repo")
    parser.add_argument("--read-at")
    args = parser.parse_args()

    spec = Path(args.spec).expanduser().resolve()
    if not spec.is_file():
        print(f"FAIL: {spec} does not exist")
        print("RESULT: FAIL")
        return 1
    repo = Path(args.repo).expanduser().resolve() if args.repo else None
    if repo is None:
        top = git(spec.parent, "rev-parse", "--show-toplevel")
        if not top:
            print("FAIL: spec is not inside a git repo; pass --repo")
            print("RESULT: FAIL")
            return 1
        repo = Path(top)

    lines = spec.read_text().splitlines()
    if not any(line.strip() for line in lines):
        print(f"FAIL: {spec} is empty")
        print("RESULT: FAIL")
        return 1
    fails, warns, infos = [], [], []
    lines, legacy_review = split_cold_review(lines, warns)
    record = record_path(spec)
    record_lines, record_review, record_changes, implemented = read_record(record)
    review = legacy_review + record_review
    fields, start = frontmatter(lines)
    body = strip_code(lines[start:])
    # A template spec has the template's frontmatter or its Work items section; a renamed
    # heading mustn't be enough to switch off the template's checks.
    templated = (
        section(body, "## Work items") is not None
        or any(key in fields for key in ("read-at", "research", "cite-repo"))
        or any("{{" in value for value in fields.values())
    )

    cite_value = args.cite_repo or fields.get("cite-repo", "")
    cite_repo = repo
    if cite_value and cite_value != "none" and "{{" not in cite_value:
        cite_repo = Path(cite_value).expanduser().resolve()
        if not git(cite_repo, "rev-parse", "--show-toplevel"):
            fails.append(f"cite-repo {cite_value} is not a git repo")
            cite_repo = repo

    read_at = args.read_at or fields.get("read-at", "")
    if not read_at and not fields:
        # A house-format spec has no frontmatter; /spec writes "Read at `<sha>`" in Background.
        found = next((m for line in body if (m := READ_AT_LINE.search(line))), None)
        read_at = found.group(1) if found else ""
        if not found:
            infos.append(
                "no read-at commit recorded, so citations are checked against the working tree"
            )
    if read_at in ("none", "") or "{{" in read_at:
        read_at = None
    elif (
        git(cite_repo, "rev-parse", "--verify", "--quiet", f"{read_at}^{{commit}}")
        is None
    ):
        where = "" if cite_repo == repo else " (the cite-repo)"
        fails.append(
            f"read-at {read_at} is not a commit in {cite_repo}{where}"
            + (
                "; if it's another repo's commit, set cite-repo"
                if cite_repo == repo
                else ""
            )
        )
        read_at = None

    # Frontmatter and sections: only the skill's own template has a known shape.
    if templated:
        for key in ("title", "created", "status", "research", "read-at"):
            if not fields.get(key) or "{{" in fields.get(key, ""):
                fails.append(f"frontmatter '{key}' is empty or still a placeholder")
        status = fields.get("status", "")
        if status and "{{" not in status and status not in STATUSES:
            fails.append(f"status is {status!r}; expected one of {', '.join(STATUSES)}")
        for heading in REQUIRED:
            if section(body, heading) is None:
                fails.append(f"missing section '{heading}'")
        for key in ("research", "idea"):
            value = fields.get(key, "")
            if (
                value
                and value != "none"
                and "{{" not in value
                and not Path(value).expanduser().is_file()
            ):
                fails.append(f"frontmatter '{key}' points at a missing file: {value}")
    else:
        infos.append(
            "no '## Work items' section: house format. Checked citations, work items or "
            "acceptance criteria, links and secrets; the template's section checks are skipped"
        )

    items = check_work_items(body, templated, fails, warns)

    # Citations, checked against the cite repo as it was at read-at.
    snap = Snapshot(cite_repo, read_at)
    cited, count = check_citations(body, snap, templated, fails, warns)

    # Borrowed facts need a URL a reader without ~/notes can follow.
    if templated:
        bare_refs = [
            line.strip()[:50]
            for line in body
            if SOURCE_REF.search(INLINE_CODE.sub("", line))
            and not re.search(r"https?://", line)
        ]
        if bare_refs:
            warns.append(
                f"{len(bare_refs)} lines cite a research source by number with no URL on the "
                f"line (first: '{bare_refs[0]}'); give the primary source's URL too"
            )
    if count == 0:
        if not templated or fields.get("read-at") == "none":
            warns.append("no `path:line` citations")
        else:
            fails.append("no `path:line` citations: Background facts need them")

    # Drift since read-at.
    if read_at and cited:
        changed = git(cite_repo, "diff", "--name-only", read_at, "--", *sorted(cited))
        if changed:
            warns.append(
                f"cited files have changed since read-at {read_at}; the citations were checked "
                "as of read-at, so re-read these before relying on them: "
                + ", ".join(changed.splitlines())
            )

    # Linked notes must exist.
    text = "\n".join(lines)
    for ref in sorted(set(NOTE_PATH.findall(text))):
        if not Path(ref).expanduser().is_file():
            fails.append(f"links a note that doesn't exist: {ref}")

    # Spike answers must cite results files that exist. Only the answer lines step 7 writes
    # count: a results path in prose (a Design, say) may name a file no spike has written yet.
    for path in sorted(
        {
            p
            for line in body
            if SPIKE_ANSWER.match(line)
            for p in RESULTS_PATH.findall(line)
        }
    ):
        if not (repo / path).is_file():
            fails.append(
                f"a spike answer cites a results file that doesn't exist: {path}"
            )
    question, answers = None, collections.Counter()
    for line in section(body, "## Spike questions") or []:
        numbered = re.match(r"(\d+)\.\s", line)
        if numbered:
            question = numbered.group(1)
        elif question and SPIKE_ANSWER.match(line):
            answers[question] += 1
    for q in sorted((q for q, n in answers.items() if n > 1), key=int):
        warns.append(
            f"spike question {q} has more than one Answered:, Partly answered: or Open: line; "
            "keep the one that stands"
        )

    # Leftover template text.
    if templated:
        leftovers = [p for p in template_prompts() if p in text]
        # Outside code only: Argo, Helm, Jinja and GitHub Actions write their own expressions
        # as {{ ... }}, and a spec quotes them in backticks.
        if "{{" in INLINE_CODE.sub("", "\n".join(lines[:start] + body)):
            leftovers.append("{{placeholder}}")
        if any(line.strip() == "-" for line in body):
            leftovers.append("empty '-' bullet")
        if any(
            EMPTY_FIELD.match(line) and not has_nested_list(body, i)
            for i, line in enumerate(body)
        ):
            leftovers.append("empty '**Field:**' line")
        if leftovers:
            fails.append(
                "template text left in: " + "; ".join(f"'{p[:50]}'" for p in leftovers)
            )

    # Secrets and account IDs.
    for pattern, what in SECRETS:
        if pattern.search("\n".join([text, *legacy_review])):
            fails.append(f"contains what looks like {what}")
        if pattern.search("\n".join(record_lines)):
            fails.append(f"its record {record.name} contains what looks like {what}")
    if ACCOUNT_ID.search("\n".join(record_lines)):
        warns.append(f"its record {record.name} contains a 12-digit number: make sure it isn't an AWS account ID")
    if ACCOUNT_ID.search("\n".join(body)):
        warns.append("contains a 12-digit number: make sure it isn't an AWS account ID")
    # Spike results are raw command output, committed beside the spec, so they get the same
    # check: this spec's own results file, and any other its answer lines cite.
    results = {spec.parent / "spikes" / f"{spec.stem}-results.md"} | {
        repo / p for line in body if SPIKE_ANSWER.match(line) for p in RESULTS_PATH.findall(line)
    }
    for path in sorted(r for r in results if r.is_file()):
        content = path.read_text(errors="replace")
        for pattern, what in SECRETS:
            if pattern.search(content):
                fails.append(f"spike results {path.name} contain what looks like {what}")
        if ACCOUNT_ID.search(content):
            warns.append(
                f"spike results {path.name} contain a 12-digit number: make sure it isn't an "
                "AWS account ID"
            )

    folded = [
        l for l in section(body, "## Spike questions") or [] if SPIKE_FOLD.match(l)
    ]
    words = sum(
        len(l.split()) for l in body if not SEPARATOR.fullmatch(l) and l not in folded
    )
    # A house-format spec may have no frontmatter; then its status comes from its opening lines,
    # and a spec that states none reads as a draft.
    stated = fields.get("status") or body_status(body)
    status = stated or "draft"
    if templated and words > WORD_FAIL and status in LIVE:
        # Neither a saved review nor starting work lifts the limit: what grows a spec past it is
        # usually what was folded in or learnt since, and someone still has to work from it.
        fails.append(
            f"{words} words; the limit is {WORD_FAIL} while the spec is {status}. Move review "
            f"history and implementation notes to its record ({record.parent.name}/{record.name}), "
            "and if it's still over, split it into specs that each land on their own"
            + (
                ", keeping the saved cold review with the part whose work items it covers"
                if review
                else ""
            )
        )
    elif templated and words > WORD_FAIL:
        # In progress, done or superseded: a record, not something to split now.
        warns.append(
            f"{words} words, over the {WORD_FAIL} limit; status {status}, so left as is"
        )
    elif words > (WORD_WARN if templated else HOUSE_WORD_WARN):
        warns.append(f"{words} words: long for a spec. Could it be two?")
    # Changes folded in after the cold review are logged in Open questions as `Not reviewed:`
    # lines. One delta review, of just those changes, is allowed before implementation.
    open_questions = section(body, "## Open questions") or []
    legacy_changes = [l for l in open_questions if NOT_REVIEWED.match(l)]
    unreviewed = legacy_changes + record_changes
    delta = any(DELTA_REVIEW.match(l) for l in review)
    residue = []
    if legacy_review:
        residue.append("the '## Cold review' section")
    if legacy_changes:
        residue.append(f"{len(legacy_changes)} 'Not reviewed:' lines")
    if any(ROUND_LINE.match(l) for l in open_questions):
        residue.append("the 'Verifier round 2 ran on' line")
    routing = [l for l in folded if not SPIKE_ANSWER.match(l)]
    if routing:
        residue.append(f"{len(routing)} Route/Changes/Expect/Box lines under spike questions")
    if residue and status in LIVE:
        warns.append(
            "review history kept in the spec: " + "; ".join(residue) + ". It belongs in the "
            f"record, {record.parent.name}/{record.name}, so the spec stays the plan"
        )
    if implemented and status in ("draft", "reviewed"):
        warns.append(
            f"its record has {len(implemented)} implementation notes but the spec is still "
            f"{status}: run `/spec done` to settle its status"
        )
    # Status `reviewed` is the hand-off to implementation, so it and `in-progress` fail until
    # the delta review has run: as a warning alone, it was skipped.
    if review and unreviewed and not delta and status in ("reviewed", "in-progress"):
        fails.append(
            f"{len(unreviewed)} changes since the cold review are marked 'Not reviewed:' and "
            f"have had no delta review, but the spec is {status}. Run `/cold-review <spec>` "
            "for the one delta review of them, or set status back to draft"
        )
    elif review and unreviewed and not delta and not stated:
        warns.append(
            f"{len(unreviewed)} changes since the cold review are marked 'Not reviewed:' and have "
            "had no delta review, but the spec states no status, so this check can't tell whether "
            "it is being built and won't stop it. Add a `Status: draft` line near the top (moved "
            "to reviewed before implementation), or run `/cold-review <spec>` for the delta review"
        )
    elif review and unreviewed and not delta:
        warns.append(
            f"{len(unreviewed)} changes since the cold review are marked 'Not reviewed:'; "
            "`/cold-review <spec>` runs the one delta review of them, before implementation. "
            "This fails once the spec is reviewed or in-progress"
        )
    elif unreviewed:
        places = ["Open questions"] * bool(legacy_changes) + [record.name] * bool(record_changes)
        where = "in " + " and ".join(places)
        infos.append(f"{len(unreviewed)} changes marked 'Not reviewed:' {where}")
    marks = len(re.findall(r"\*\((?:assumption|inferred|unverified)[^)]*\)\*", text))
    where = "" if cite_repo == repo else f" in {cite_repo.name}"
    infos.append(
        f"{len(items)} work items, {count} citations to {len(cited)} files{where}, "
        f"{marks} assumption/unverified marks, {words} words, status {stated or '?'}"
    )

    for label, found in (("FAIL", fails), ("WARN", warns), ("INFO", infos)):
        for item in found:
            print(f"{label}: {item}")
    print("RESULT: " + ("FAIL" if fails else "PASS"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

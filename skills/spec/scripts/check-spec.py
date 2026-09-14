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

Checks only what can be checked mechanically: that every citation points at a file and at lines
that existed, whether cited files have changed since, work items and acceptance criteria, and,
for specs written from the skill template, sections and leftover template text. Whether a cited
line says what the spec claims is the spec-verifier agent's job.
"""

import argparse
import re
import subprocess
from pathlib import Path

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
INLINE_CODE = re.compile(r"`[^`]*`")
READ_AT_LINE = re.compile(r"[Rr]ead at (?:commit )?`?([0-9a-f]{7,40})\b")
# Bare filenames with these extensions are citations even if nothing matches; others
# (example.com:443) may be hosts.
CODE_EXT = re.compile(
    r"\.(py|sh|bash|md|ya?ml|json|toml|tf|tfvars|hcl|go|rs|ts|tsx|js|jsx|tpl|txt|cfg|ini|mk|sql|rb|java|kt|c|h|cpp)$"
)
NOTE_PATH = re.compile(r"~/notes/[\w./-]+\.md")
WORK_ITEM = re.compile(r"^#{2,3}\s+W(\d+)\b")
DONE_WHEN = re.compile(r"done when", re.IGNORECASE)
ACCEPTANCE = "## Acceptance criteria"
EMPTY_FIELD = re.compile(r"^\s*-\s+\*\*[^*]+:\*\*\s*$")
SEPARATOR = re.compile(r"\s*\|?[\s:|-]*\|?\s*")
# Keep in step with SECRETS in ~/.claude/skills/research/scripts/check-note.py.
SECRETS = [
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "an AWS access key ID"),
    (
        re.compile(r"aws_secret_access_key\s*[=:]\s*\S{20,}", re.IGNORECASE),
        "an AWS secret key",
    ),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "a private key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "a GitHub token"),
    (re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"), "a GitHub token"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"), "a Slack token"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"), "an Anthropic API key"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "a Google API key"),
    (re.compile(r'"type"\s*:\s*"service_account"'), "a GCP service account key"),
]
ACCOUNT_ID = re.compile(r"(?<![\w.:-])\d{12}(?![\w-]|\.\d)")
NESTED_ITEM = re.compile(r"\s+(?:[-*]|\d+\.)\s+\S")


def git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    return result.stdout.rstrip("\n") if result.returncode == 0 else None


def frontmatter(lines):
    """Return (fields, index of the first body line)."""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    fields = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return fields, i + 1
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.split(" #")[0].strip()
    return fields, len(lines)


def strip_code(lines):
    """Drop fenced code blocks: command output and diagrams aren't citations."""
    out, fenced = [], False
    for line in lines:
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return out


def section(lines, heading):
    """Lines under the first heading starting with `heading`, up to the next heading of its level or above."""
    level = len(heading) - len(heading.lstrip("#"))
    for i, line in enumerate(lines):
        if line.startswith(heading):
            body = []
            for nxt in lines[i + 1 :]:
                if nxt.startswith("#") and len(nxt) - len(nxt.lstrip("#")) <= level:
                    break
                body.append(nxt)
            return body
    return None


def template_prompts():
    """Prose lines from the template that should never survive into a finished spec."""
    if not TEMPLATE.exists():
        return []
    prompts = []
    for line in TEMPLATE.read_text().splitlines():
        text = line.strip()
        if (
            len(text) > 20
            and not text.startswith(("#", "|", "---", "- **"))
            and ":" not in text[:12]
        ):
            prompts.append(text)
    return prompts


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
    if templated and nums and nums != list(range(1, len(nums) + 1)):
        warns.append(
            f"work items are numbered {nums}; expected W1..W{len(nums)} in order"
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

    # Leftover template text.
    if templated:
        leftovers = [p for p in template_prompts() if p in text]
        if "{{" in text:
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
        if pattern.search(text):
            fails.append(f"contains what looks like {what}")
    if ACCOUNT_ID.search("\n".join(body)):
        warns.append("contains a 12-digit number: make sure it isn't an AWS account ID")

    words = sum(len(l.split()) for l in body if not SEPARATOR.fullmatch(l))
    status = fields.get("status", "draft")
    if templated and words > WORD_FAIL and status in ("draft", "reviewed"):
        fails.append(
            f"{words} words; the limit is {WORD_FAIL}. Split it into specs that each land on their own"
        )
    elif templated and words > WORD_FAIL:
        # In progress, done or superseded: a record, not something to split now.
        warns.append(
            f"{words} words, over the {WORD_FAIL} limit; status {status}, so left as is"
        )
    elif words > (WORD_WARN if templated else HOUSE_WORD_WARN):
        warns.append(f"{words} words: long for a spec. Could it be two?")
    marks = len(re.findall(r"\*\((?:assumption|inferred|unverified)[^)]*\)\*", text))
    where = "" if cite_repo == repo else f" in {cite_repo.name}"
    infos.append(
        f"{len(items)} work items, {count} citations to {len(cited)} files{where}, "
        f"{marks} assumption/unverified marks, {words} words, status {fields.get('status', '?')}"
    )

    for label, found in (("FAIL", fails), ("WARN", warns), ("INFO", infos)):
        for item in found:
            print(f"{label}: {item}")
    print("RESULT: " + ("FAIL" if fails else "PASS"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

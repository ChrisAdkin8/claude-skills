"""Markdown helpers shared by check-note.py, build-index.py,
skills/spec/scripts/check-spec.py and skills/cold-review/scripts/review-state.py.

Not run on its own. Each script loads it by path, so a fix here reaches all of them: frontmatter,
code fences (and a fence left open), headings and the one rule that matches them, sections,
citations, template leftovers, the topic form, the `Not reviewed:` pattern, the record path and
the record under a document's earlier name, the saved cold review's parser, word and line
counts, and the secret and account-ID patterns.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

INLINE_CODE = re.compile(r"`[^`]*`")  # jq like `.[0]` is not a citation
SEPARATOR = re.compile(r"\s*\|?[\s:|-]*\|?\s*")  # table rule rows and blank lines
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
# An ARN's account field, which ACCOUNT_ID's lookbehind skips: arn:aws:iam::123456789012:role/x.
ARN_ACCOUNT = re.compile(r"\barn:aws[\w-]*:[\w-]*:[\w-]*:\d{12}(?::|/|$)", re.MULTILINE)
# `- Not reviewed:`, and the same in bold, italics or lower case, with any bullet (`-`, `*`, `+`,
# `1.`, `1)`) or none: check-spec's delta-review gate and /cold-review's review-state.py count
# these, so a hand-written variant mustn't slip past them.
NOT_REVIEWED = re.compile(
    r"\s*(?:(?:[-*+]|\d+[.)])\s+)?[*_]*not reviewed[*_]*\s*:", re.IGNORECASE
)
# A research note's `topic`: area or area/sub-area, each lowercase and hyphenated. check-note.py
# fails anything else, and build-index.py files anything else as Unfiled.
TOPIC = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)?")
# A frontmatter line: `key: value`, a list item, an indented continuation, a comment or blank.
# Anything else means the opening `---` was a horizontal rule, not frontmatter.
FRONTMATTER_LINE = re.compile(r"\s*$|\s*#|\s*-(?:\s|$)|\s+\S|[\w.-][\w .-]*:(?:\s|$)")
FENCE = re.compile(r"\s*(`{3,}|~{3,})(.*)")
CLOSE = re.compile(r"`{3,}|~{3,}")  # a closing fence has nothing after it
# A heading is 1-6 `#` then a space or the end of the line: `#2 on Hacker News` is prose.
HEADING = re.compile(r"#{1,6}(?:\s|$)")
# [12], [1, 7], [8-9] or [8–9], but not a markdown link [12](url). check-note.py and check-spec.py
# both read research citations with it.
CITE = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()")


def flow_list(value):
    """Items of a frontmatter flow list, `[a, b]`."""
    return [e.strip().strip("'\"") for e in value.strip("[]").split(",") if e.strip()]


def has_account_id(text):
    """A bare 12-digit number or an ARN with an account ID in it."""
    return bool(ACCOUNT_ID.search(text) or ARN_ACCOUNT.search(text))


def count_words(line):
    """Words in a line, not counting table pipes: `| a | b |` is two words, not five."""
    return sum(1 for word in line.split() if word.strip("|"))


def frontmatter(lines):
    """Return (fields, index of the first body line). Block lists (`key:` then `- item`) are
    joined into a flow list, so `related` reads the same either way. A `---` with no closing
    `---`, or with prose before it, is a horizontal rule: no frontmatter, and the whole file is
    body, so its citations are still checked."""
    # A byte-order mark some editors write isn't whitespace, so strip() alone would keep it.
    if not lines or lines[0].lstrip("\ufeff").strip() != "---":
        return {}, 0
    fields, key = {}, None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return fields, i + 1
        if not FRONTMATTER_LINE.match(line):
            return {}, 0
        item = re.match(r"\s*-\s+(.*)", line)  # indented or not, YAML reads both
        if item and key and not fields[key].startswith("["):
            fields[key] = (fields[key] + ", " if fields[key] else "") + item.group(1)
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            # `status: "reviewed"` is YAML for reviewed; a checker comparing the raw text
            # would miss it. A ` #` starts a comment, but not inside quotes: `"Fix #42"`.
            if value[:1] in ("'", '"') and (end := value.find(value[0], 1)) > 0:
                value = value[1:end]
            else:
                value = value.split(" #")[0].strip()
            fields[key] = value
    return {}, 0


def _fences(lines):
    """(in_code flags, index of a fence left open at the end or None)."""
    flags, fence, opened = [], None, None
    for i, line in enumerate(lines):
        m = FENCE.match(line)
        if fence is None:
            opens = bool(m) and not (m.group(1)[0] == "`" and "`" in m.group(2))
            if opens:
                fence, opened = m.group(1), i
            flags.append(opens)
        else:
            flags.append(True)
            closing = line.strip()
            if m and CLOSE.fullmatch(closing) and closing[0] == fence[0]:
                if len(closing) >= len(fence):
                    fence = None
    return flags, (opened if fence is not None else None)


def in_code(lines):
    """For each line, whether it's part of a fenced code block, its fences included. A fence is
    ``` or ~~~, and only a run of the same character at least as long closes it, so a ````
    block can hold a ``` one. A ``` line with another backtick after it is inline code, not a
    fence. Every check that skips code walks the lines with this, so they agree on where code
    starts and ends."""
    return _fences(lines)[0]


def unclosed_fence(lines):
    """The 1-based line of a code fence that's never closed, or None. Everything after it reads
    as code, so no check sees it."""
    at = _fences(lines)[1]
    return None if at is None else at + 1


def strip_code(lines):
    """Drop fenced code blocks: commands, their output and diagrams."""
    return [line for line, code in zip(lines, in_code(lines)) if not code]


def is_heading(line):
    return bool(HEADING.match(line))


def level(line):
    return len(line) - len(line.lstrip("#"))


def heading_is(line, heading):
    """Whether `line` is `heading`, in any case: the whole of it, or it followed by `:` or `,`.
    So `## Cold Review` and `### Delta review, 2026-09-27` match, but `## Cold review of any
    document` doesn't. section(), check-note.py and the review parser all match this way."""
    text, want = line.strip().lower(), heading.strip().lower()
    return text == want or (
        text.startswith(want) and text[len(want) : len(want) + 1] in (":", ",")
    )


def section(lines, heading):
    """Lines under the first line that is `heading` (heading_is), up to the next heading of its
    level or above. A heading inside a code block neither starts nor ends a section: a quoted
    `## Cold review`, or a `# comment` in a shell block, is code."""
    code = in_code(lines)
    for i, line in enumerate(lines):
        if not code[i] and heading_is(line, heading):
            body = []
            for nxt, in_block in zip(lines[i + 1 :], code[i + 1 :]):
                if not in_block and is_heading(nxt) and level(nxt) <= level(heading):
                    break
                body.append(nxt)
            return body
    return None


def record_path(doc):
    """Where a document's review record lives: records/<basename>-record.md beside it."""
    return doc.parent / "records" / f"{doc.stem}-record.md"


def record_for(doc, earlier):
    """The document's record: record_path(doc) if it exists, else the first existing record of
    one of its `earlier` paths (a document moved without its record), else None."""
    for path in [doc, *earlier]:
        if record_path(Path(path)).is_file():
            return record_path(Path(path))
    return None


def earlier_paths(git, rel):
    """The names a repo-relative document `rel` had before, newest first. `git(*args)` runs git
    in the repo and returns its output or None. A `git mv` that's only staged shows up in
    `git diff --cached` alone (git log --follow sees only commits), so its old name comes first
    and the committed history is followed from there."""
    names = []
    for line in (git("diff", "--cached", "-M", "--name-status") or "").splitlines():
        status, *paths = line.split("\t")
        if status.startswith("R") and len(paths) == 2 and paths[1] == rel:
            names.append(paths[0])
    start = names[0] if names else rel
    log = git("log", "--follow", "--name-only", "--format=", "--", start) or ""
    names += [name for name in log.splitlines() if name.strip()]
    return [name for name in dict.fromkeys(names) if name != rel]


# The review parser. /cold-review writes a review as `## Cold review`, then `Reviewed on <date>
# by ...` as its first line, then the reviewer's reply unchanged; a delta review the same under
# `### Delta review, <date>`. Only those lines, and the templates' own headings, place a review:
# nothing the reply says can move, end or date it.
SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"
REVIEWED_ON = re.compile(r"Reviewed on (\d{4}-\d{2}-\d{2}) by")
DELTA_HEADING = "### Delta review"
TEMPLATE_TOKEN = re.compile(r"\{\{[^{}]*\}\}")
# Where `Not reviewed:` lines are written: a legacy spec's Open questions, and in a record the
# folds after the review, the ones after its delta, and spike routing.
NOT_REVIEWED_IN = {
    "document": ("## Open questions",),
    "record": (
        "## Changes since the review",
        "## Changes after the delta review",
        "## Spikes",
    ),
}


def template_headings(template):
    """The `##` headings a template names, as written there."""
    path = SPEC_DIR / template
    lines = path.read_text().splitlines() if path.is_file() else []
    return [line.strip() for line in lines if is_heading(line) and level(line) == 2]


def template_tokens():
    """The record template's own `{{...}}` placeholders."""
    path = SPEC_DIR / "record-template.md"
    text = path.read_text() if path.is_file() else ""
    return set(TEMPLATE_TOKEN.findall(text))


@dataclass
class Review:
    """What read_review() found. `where` is "record", "document" or None (no review); `start`
    and `end` are the review's span in that file's lines, 0-based, end exclusive."""

    where: str | None = None
    start: int = 0
    end: int = 0
    date: str | None = None
    delta_date: str | None = None
    # (source, 1-based line, text), the source as "record ## Spikes".
    not_reviewed: list = field(default_factory=list)
    placeholders: list = field(default_factory=list)  # (1-based line in the record, token)
    misplaced: list = field(default_factory=list)  # spec-template headings after the review


def _first_text(lines, start):
    """The first non-blank line after index `start`, stripped, or ''."""
    return next((l.strip() for l in lines[start + 1 :] if l.strip()), "")


def _find_review(lines, ends):
    """(start, end, date) of the review under `## Cold review`, ending at the first heading in
    `ends` (else the end of the file), or None if there isn't one with its `Reviewed on` line."""
    code = in_code(lines)
    # The first such heading with its `Reviewed on` line: a stray one above mustn't hide it.
    start, m = next(
        (
            (i, m)
            for i, l in enumerate(lines)
            if not code[i]
            and heading_is(l, "## Cold review")
            and (m := REVIEWED_ON.match(_first_text(lines, i)))
        ),
        (None, None),
    )
    if start is None:
        return None
    end = next(
        (
            j
            for j in range(start + 1, len(lines))
            if not code[j] and any(heading_is(lines[j], h) for h in ends)
        ),
        len(lines),
    )
    return start, end, m.group(1)


def _delta_date(lines, start, end):
    """The date on the delta review's own `Reviewed on` line, from the first `### Delta review,`
    heading in the span that has one first under it; None if no heading does."""
    code = in_code(lines)
    for i in range(start + 1, end):
        if code[i] or not heading_is(lines[i], DELTA_HEADING) or "," not in lines[i]:
            continue
        own = next((l for l in lines[i + 1 : end] if l.strip()), "")
        if is_heading(own) and level(own) <= 3:
            continue  # the delta ended before any line of its own
        if m := REVIEWED_ON.match(own.strip()):
            return m.group(1)
    return None


def _not_reviewed(lines, file, skip):
    """`Not reviewed:` lines in the sections NOT_REVIEWED_IN names for `file`, outside code and
    the line indices in `skip`."""
    found, current, code = [], None, in_code(lines)
    for i, line in enumerate(lines):
        if code[i]:
            continue
        if is_heading(line) and level(line) <= 2:
            current = next(
                (h for h in NOT_REVIEWED_IN[file] if heading_is(line, h)), None
            )
        elif current and i not in skip and NOT_REVIEWED.match(line):
            found.append((f"{file} {current}", i + 1, line.strip()))
    return found


def read_review(doc_lines, record_lines):
    """The saved cold review of a document, read once for review-state.py and check-spec.py.

    The record is tried first, then the document. A review is the first `## Cold review` heading
    outside code whose first non-blank line is `Reviewed on <date> by`; it ends at the next `##`
    heading its file's template names (in a record, also `## Changes after the delta review`),
    else at the end of the file. A `## Findings` in the reply doesn't end it, and a `Not
    reviewed:` or `Reviewed on` line inside it counts for nothing. Both files are always read
    for `Not reviewed:` lines. Placeholders are the record template's tokens left in the record,
    outside the review, code and inline code."""
    doc_lines, record_lines = doc_lines or [], record_lines or []
    got = Review()
    record_ends = [
        *template_headings("record-template.md"),
        "## Changes after the delta review",
    ]
    spec_ends = template_headings("template.md")
    for where, lines, ends in (
        ("record", record_lines, record_ends),
        ("document", doc_lines, spec_ends),
    ):
        if found := _find_review(lines, ends):
            got.where, (got.start, got.end, got.date) = where, found
            got.delta_date = _delta_date(lines, got.start, got.end)
            break
    if got.where == "document":
        code = in_code(doc_lines)
        got.misplaced = [
            doc_lines[j].strip()
            for j in range(got.end, len(doc_lines))
            if not code[j] and any(heading_is(doc_lines[j], h) for h in spec_ends)
        ]

    def span(where):
        return range(got.start, got.end) if got.where == where else range(0)

    got.not_reviewed = _not_reviewed(doc_lines, "document", span("document")) + (
        _not_reviewed(record_lines, "record", span("record"))
    )
    tokens, skip = template_tokens(), span("record")
    for i, (line, code) in enumerate(zip(record_lines, in_code(record_lines))):
        if code or i in skip:
            continue
        for token in TEMPLATE_TOKEN.findall(INLINE_CODE.sub("", line)):
            if token in tokens:
                got.placeholders.append((i + 1, token))
    return got


def secrets_in(text):
    """What each secret pattern found in `text`, as 'an AWS access key ID' and so on."""
    return [what for pattern, what in SECRETS if pattern.search(text)]


def line_count(text):
    """Lines as git and editors count them. str.splitlines also splits on form feeds, \\x1c-\\x1e,
    \\x85 and \\u2028, so a file holding them would seem to have more lines than it does. Pass
    text read without newline translation (read_text/text=True turn a lone \\r into \\n)."""
    return text.count("\n") + (bool(text) and not text.endswith("\n"))


def template_prompts(template, skip=("#", "|", "---")):
    """Prose lines from a template that should never survive into a finished document: lines
    over 20 characters that aren't headings, tables, rules, lines starting with `skip`, or a
    short `key:` line."""
    template = Path(template)
    if not template.exists():
        return []
    prompts = []
    for line in template.read_text().splitlines():
        text = line.strip()
        if len(text) > 20 and not text.startswith(tuple(skip)) and ":" not in text[:12]:
            prompts.append(text)
    return prompts

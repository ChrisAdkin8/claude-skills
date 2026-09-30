"""Markdown helpers shared by check-note.py, build-index.py,
skills/spec/scripts/check-spec.py and skills/cold-review/scripts/review-state.py.

Not run on its own. Each script loads it by path, so a fix here reaches all of them: frontmatter,
code fences (and a fence left open), headings, sections, citations, template leftovers, the topic
form, the `Not reviewed:` and delta-review patterns, the record path, word and line counts, and the
secret and account-ID patterns.
"""

import re
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
# `- Not reviewed:`, and the same in bold, italics or lower case, with or without the bullet:
# check-spec's delta-review gate and /cold-review's review-state.py count these, so a
# hand-written variant mustn't slip past them.
NOT_REVIEWED = re.compile(r"\s*(?:[-*]\s+)?[*_]*not reviewed[*_]*\s*:", re.IGNORECASE)
# A research note's `topic`: area or area/sub-area, each lowercase and hyphenated. check-note.py
# fails anything else, and build-index.py files anything else as Unfiled.
TOPIC = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*(?:/[a-z0-9]+(?:-[a-z0-9]+)*)?")
# A delta review's heading inside a saved cold review, in any case.
DELTA_REVIEW = re.compile(r"###\s+delta review", re.IGNORECASE)
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


def section(lines, heading):
    """Lines under the first heading starting with `heading`, in any case, up to the next heading
    of its level or above. A heading inside a code block neither starts nor ends a section: a
    quoted `## Cold review`, or a `# comment` in a shell block, is code."""
    code, want = in_code(lines), heading.lower()
    for i, line in enumerate(lines):
        if not code[i] and line.lower().startswith(want):
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

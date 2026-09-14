#!/usr/bin/env python3
"""Check a /research note's structure, citations and length before it is verified and committed.

Usage: check-note.py [--headroom] <note.md>

--headroom applies the researcher's lower budget (1,300 words full, 500 quick), which leaves room
for the verifier's fixes; without it the note's hard limit applies (1,500 full, 600 quick).

Prints FAIL, WARN and INFO lines and exits 1 if anything failed. Checks only what can be
checked mechanically; whether the sources support the claims is the verifier agent's job.
"""

import argparse
import re
from pathlib import Path

TEMPLATE = Path.home() / "notes" / "templates" / "research.md"
WORD_BUDGET = {"full": 1500, "quick": 600}
HEADROOM_BUDGET = {"full": 1300, "quick": 500}
STATUSES = ("draft", "final", "outdated")
VERDICTS = ("CONFIRMED", "MISCITED", "WRONG", "UNSUPPORTED", "UNREACHABLE")
REQUIRED = {
    "full": [
        "## Bottom line",
        "## The question",
        "## Findings",
        "### Counter-evidence",
        "## Options",
        "## Recommendation",
        "## Next step",
        "## Sources",
    ],
    "quick": ["## Bottom line", "## The question", "## Findings", "## Sources"],
}
# [12], [1, 7], [8-9] or [8–9], but not a markdown link [12](url).
CITE = re.compile(r"\[(\d+(?:\s*[,–-]\s*\d+)*)\](?!\()")
SOURCE = re.compile(r"^(\d+)\.\s")
INLINE_CODE = re.compile(r"`[^`]*`")  # jq like `.[0]` is not a citation
SEPARATOR = re.compile(r"\s*\|?[\s:|-]*\|?\s*")  # table rule rows and blank lines
UNVERIFIED_MARK = re.compile(r"\*\((?:inferred|unverified)[^)]*\)\*")
# Keep in step with SECRETS in ~/.claude/skills/spec/scripts/check-spec.py.
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


def frontmatter(lines):
    """Return (fields, index of the first body line). Block lists (`key:` then `- item`) are
    joined into a flow list, so `related` reads the same either way."""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    fields, key = {}, None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return fields, i + 1
        item = re.match(r"\s+-\s+(.*)", line)
        if item and key and not fields[key].startswith("["):
            fields[key] = (fields[key] + ", " if fields[key] else "") + item.group(1)
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.split(" #")[0].strip()
    return fields, len(lines)


def strip_code(lines):
    """Drop fenced code blocks (mermaid diagrams, commands)."""
    out, fenced = [], False
    for line in lines:
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return out


def level(line):
    return len(line) - len(line.lstrip("#"))


def section(lines, heading):
    """Lines under the first heading starting with `heading`, up to the next heading of its level or above."""
    for i, line in enumerate(lines):
        if line.startswith(heading):
            body = []
            for nxt in lines[i + 1 :]:
                if nxt.startswith("#") and level(nxt) <= level(heading):
                    break
                body.append(nxt)
            return body
    return None


def heading_index(lines, heading):
    return next((i for i, line in enumerate(lines) if line.startswith(heading)), None)


def cells(line):
    """Split a table row on `|`, except inside backticks or escaped as `\\|`."""
    out, cell, in_code, prev = [], "", False, ""
    for ch in line.strip().strip("|"):
        if ch == "`":
            in_code = not in_code
        if ch == "|" and not in_code and prev != "\\":
            out.append(cell.strip())
            cell = ""
        else:
            cell += ch
        prev = ch
    out.append(cell.strip())
    return out


def table_rows(lines):
    """Cells of each table row, skipping the header and rule rows."""
    rows = [
        cells(line)
        for line in lines
        if line.lstrip().startswith("|") and not SEPARATOR.fullmatch(line)
    ]
    return rows[1:]


def normalise(text):
    """Lower-case, with links reduced to their text, without markdown emphasis, code ticks or
    escapes, whitespace collapsed."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    return " ".join(re.sub(r"[*`\\]", "", text).lower().split())


def cited_numbers(line):
    nums = set()
    for group in CITE.findall(INLINE_CODE.sub("", line)):
        for part in re.split(r"\s*,\s*", group):
            ends = [int(n) for n in re.split(r"\s*[–-]\s*", part)]
            # [2019-2024] is a span of years, not citations; nor is anything past 999.
            if max(ends) > 999 or (len(ends) == 2 and not 0 <= ends[1] - ends[0] <= 50):
                continue
            nums.update(range(ends[0], ends[-1] + 1) if len(ends) == 2 else ends)
    return nums


def template_prompts():
    """Prose lines from the template that should never survive into a finished note."""
    if not TEMPLATE.exists():
        return []
    prompts = []
    for line in TEMPLATE.read_text().splitlines():
        text = line.strip()
        if (
            len(text) > 20
            and not text.startswith(("#", "|", "---"))
            and ":" not in text[:12]
        ):
            prompts.append(text)
    return prompts


def check_related(value, fails, warns):
    """Skills find notes by grepping `related` for exact paths, so every entry must resolve."""
    entries = [
        e.strip().strip("'\"") for e in value.strip("[]").split(",") if e.strip()
    ]
    for entry in entries:
        if not entry.startswith("~/"):
            warns.append(
                f"related entry {entry!r} isn't a ~ path; skills grep for ~ paths"
            )
        elif not Path(entry).expanduser().exists():
            fails.append(
                f"related entry {entry} doesn't exist: fix the path, or remove it if the "
                "file was deleted"
            )


def check_after_sources(body, depth, fails):
    """Only Sources and Verification may follow `## Sources`: anything else would escape the
    word budget and the citation check."""
    src_at = heading_index(body, "## Sources")
    if src_at is None:
        return
    for line in body[src_at + 1 :]:
        if line.startswith("#") and not line.startswith("## Verification"):
            fails.append(
                f"'{line.strip()}' comes after Sources; only '## Verification' may. "
                "Move it above Sources"
            )


def stray_after_sources(body):
    """Lines after `## Sources` that aren't a source, its continuation, a 'Checked on' line or
    the Verification table. They're prose, so they count toward the budget and the citations."""
    src_at = heading_index(body, "## Sources")
    if src_at is None:
        return []
    stray = []
    for line in body[src_at + 1 :]:
        text = line.strip()
        if (
            not text
            or line.startswith("## Verification")
            or SOURCE.match(text)
            or line[:1] in (" ", "\t")
            or text.startswith(("|", "Checked on"))
        ):
            continue
        stray.append(line)
    return stray


def paragraphs(lines):
    """Normalised paragraphs: runs of non-blank, non-heading lines, so a hard-wrapped claim
    reads as one piece of text."""
    out, current = [], []
    for line in lines + [""]:
        if line.strip() and not line.startswith("#"):
            current.append(line)
        elif current:
            out.append(normalise(" ".join(current)))
            current = []
    return out


def check_verification(body, prose, status, fails, warns):
    """The Verification section records which claims the verifier checked and how each ended.
    `/spec` trusts it, so each row must still match the note's text."""
    ver_at = heading_index(body, "## Verification")
    if ver_at is None:
        if status == "final":
            warns.append(
                "status final but no '## Verification' section: run /research finish to record one"
            )
        return
    if ver_at < (heading_index(body, "## Sources") or 0):
        fails.append(
            "'## Verification' must come after Sources, outside the word budget"
        )
    rows = table_rows(section(body, "## Verification"))
    if not rows:
        fails.append("'## Verification' has no table of checked claims")
        return
    # Final notes must be consistent; in a draft these are work still to do.
    problems = fails if status == "final" else warns
    paras = paragraphs(prose)
    prose_text = " ".join(paras)
    unresolved, stale, unmarked = [], [], []
    for row in rows:
        if len(row) < 3:
            fails.append(
                f"Verification row has too few columns: '{' | '.join(row)[:60]}'"
            )
            continue
        claim, verdict = row[0], row[2].strip("* ").upper()
        resolution = row[3] if len(row) > 3 else ""
        label = f"'{claim[:40]}'"
        if verdict not in VERDICTS:
            warns.append(f"Verification row {label} has verdict {row[2]!r}")
        if verdict != "CONFIRMED" and not resolution:
            unresolved.append(label)
        needle = normalise(claim)
        if needle and needle not in prose_text:
            stale.append(label)
        elif "unverified" in resolution.lower() and any(
            "(unverified" not in para for para in paras if needle in para
        ):  # every place the claim appears must carry the mark
            unmarked.append(label)
    if unresolved:
        problems.append(
            "Verification rows with no Resolution: " + "; ".join(unresolved)
        )
    if stale:
        problems.append(
            "Verification rows whose claim no longer appears in the note (edited since it was "
            "checked, so the row no longer vouches for it; re-verify with /research finish): "
            + "; ".join(stale)
        )
    if unmarked:
        problems.append(
            "Verification rows resolved as 'marked (unverified)' whose claim isn't marked "
            "*(unverified)* in the text: " + "; ".join(unmarked)
        )


def main():
    parser = argparse.ArgumentParser(description="Check a /research note.")
    parser.add_argument("note")
    parser.add_argument(
        "--headroom",
        action="store_true",
        help="apply the researcher's lower budget, leaving room for the verifier's fixes",
    )
    args = parser.parse_args()

    note = Path(args.note).expanduser()
    if not note.exists():
        print(f"FAIL: {note} does not exist")
        print("RESULT: FAIL")
        return 1
    lines = note.read_text().splitlines()
    fails, warns, infos = [], [], []

    fields, start = frontmatter(lines)
    if not fields:
        fails.append("no YAML frontmatter")
    depth = fields.get("depth", "full") or "full"
    if depth not in WORD_BUDGET:
        fails.append(f"depth is {depth!r}; expected full or quick")
        depth = "full"
    for key in ("title", "created", "status", "question"):
        if not fields.get(key) or "{{" in fields.get(key, ""):
            fails.append(f"frontmatter '{key}' is empty or still a placeholder")
    status = fields.get("status", "")
    if status and status not in STATUSES:
        fails.append(f"status is {status!r}; expected one of {', '.join(STATUSES)}")
    if fields.get("tags", "[]") in ("", "[]"):
        warns.append("frontmatter 'tags' is empty")
    check_related(fields.get("related", ""), fails, warns)

    body = strip_code(lines[start:])
    for heading in REQUIRED[depth]:
        if section(body, heading) is None:
            fails.append(f"missing section '{heading}' (required for depth: {depth})")
    check_after_sources(body, depth, fails)

    counter = section(body, "### Counter-evidence")
    if counter is not None and not any(line.strip() for line in counter):
        fails.append(
            "Counter-evidence is empty: list findings, or the searches that came up empty"
        )

    health = section(body, "### Project health")
    if health is None:
        if depth == "full":
            warns.append(
                "no Project health section: fine only if no open-source project is recommended"
            )
    elif not any(line.lstrip().startswith("|") for line in health):
        fails.append("Project health has no table: paste the repo-health.sh output")

    # Split the prose from Sources, and Sources from whatever follows it (Verification).
    src_at = heading_index(body, "## Sources")
    prose = body[:src_at] if src_at is not None else body
    if stray := stray_after_sources(body):
        warns.append(
            f"{len(stray)} lines of prose after Sources (first: '{stray[0].strip()[:40]}'); "
            "they count toward the word budget. Move them above Sources"
        )
        prose = prose + stray
    sources = section(body, "## Sources") or []

    source_nums = {
        int(m.group(1)) for line in sources if (m := SOURCE.match(line.strip()))
    }
    if not source_nums:
        fails.append("Sources list is empty")
    if sources and not any("Checked on" in line for line in sources):
        warns.append("Sources has no 'Checked on <date>' line")
    cited = set().union(*(cited_numbers(line) for line in prose))
    if dangling := sorted(cited - source_nums):
        fails.append(
            f"citations with no matching source: {', '.join(f'[{n}]' for n in dangling)}"
        )
    if uncited := sorted(source_nums - cited):
        warns.append(f"sources never cited in the text: {', '.join(map(str, uncited))}")

    check_verification(body, prose, status, fails, warns)

    words = sum(len(line.split()) for line in prose if not SEPARATOR.fullmatch(line))
    budget = (HEADROOM_BUDGET if args.headroom else WORD_BUDGET)[depth]
    kind = (
        "researcher's budget, leaving headroom for verification"
        if args.headroom
        else "limit"
    )
    if words > budget:
        fails.append(
            f"{words} words above Sources; the {kind} for depth {depth} is {budget}. "
            "Cut, don't summarise the cuts"
        )
    else:
        infos.append(f"{words} words above Sources ({kind} {budget})")

    text = "\n".join(lines)
    leftovers = [p for p in template_prompts() if p in text]
    if "{{" in text:
        leftovers.append("{{placeholder}}")
    if any(line.strip() == "-" for line in prose):
        leftovers.append("empty '-' bullet")
    if leftovers:
        fails.append(
            "template text left in: " + "; ".join(f"'{p[:50]}'" for p in leftovers)
        )

    for pattern, what in SECRETS:
        if pattern.search(text):
            fails.append(f"contains what looks like {what}")
    if ACCOUNT_ID.search("\n".join(body)):
        warns.append("contains a 12-digit number: make sure it isn't an AWS account ID")

    marked = sum(len(UNVERIFIED_MARK.findall(line)) for line in prose)
    infos.append(
        f"depth {depth}, status {status or '?'}, {len(source_nums)} sources, "
        f"{marked} inferred/unverified marks in the text"
    )

    for label, items in (("FAIL", fails), ("WARN", warns), ("INFO", infos)):
        for item in items:
            print(f"{label}: {item}")
    print("RESULT: " + ("FAIL" if fails else "PASS"))
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())

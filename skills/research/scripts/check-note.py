#!/usr/bin/env python3
"""Check a /research note's structure, citations and length before it is verified and committed.

Usage: check-note.py [--headroom] <note.md>

--headroom applies the researcher's lower budget (1,300 words full, 500 quick, 2,100 ideas), which
leaves room for the verifier's fixes; without it the note's hard limit applies (1,500 full, 600
quick, 2,400 ideas).

depth: ideas notes also get their Candidate pool and Shortlist checked: the pool sits after
Sources, outside the word budget, and its lines are candidates tagged with a lens.

Prints FAIL, WARN and INFO lines and exits 1 if anything failed. Checks only what can be
checked mechanically; whether the sources support the claims is the verifier agent's job.
"""

import argparse
import re
from pathlib import Path

TEMPLATES = Path.home() / "notes" / "templates"
TEMPLATE = {"ideas": TEMPLATES / "research-ideas.md"}  # any other depth: research.md
WORD_BUDGET = {"full": 1500, "quick": 600, "ideas": 2400}
HEADROOM_BUDGET = {"full": 1300, "quick": 500, "ideas": 2100}
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
    "ideas": [
        "## Bottom line",
        "## The question",
        "## Findings",
        "### Prior art",
        "### Attention evidence",
        "### Counter-evidence",
        "## Shortlist",
        "## Recommendation",
        "## Next step",
        "## Sources",
        "## Candidate pool",
    ],
}
# Sections allowed after `## Sources`, in this order. Candidate pool is for depth: ideas only.
AFTER_SOURCES = ("## Candidate pool", "## Verification")
# depth: ideas. Keep in step with the Ideation rules in ~/.claude/agents/researcher.md.
LENSES = ("finding", "tool", "dataset", "game", "lab", "essay")
POOL_MIN = 20
SHORTLIST_SIZE = (5, 7)
RUBRIC = (
    "Idea",
    "Lens",
    "Share hook",
    "Novelty",
    "Format evidence",
    "Demo",
    "Effort",
    "Why it flops",
)
CANDIDATE = re.compile(r"^\s*[-*]\s+\[([^\]]+)\]")
CANDIDATE_MARK = re.compile(r"\bcut:|\bshortlisted\b", re.IGNORECASE)
EVIDENCE_NOTE = "attention-evidence.md"
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


def first_table(lines):
    """(header cells, body rows) of the first table in `lines`, or ([], [])."""
    block = []
    for line in lines:
        if line.lstrip().startswith("|"):
            block.append(line)
        elif block:
            break
    rows = [cells(line) for line in block if not SEPARATOR.fullmatch(line)]
    return (rows[0], rows[1:]) if rows else ([], [])


def flow_list(value):
    """Items of a frontmatter flow list, `[a, b]`."""
    return [e.strip().strip("'\"") for e in value.strip("[]").split(",") if e.strip()]


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


def template_prompts(depth):
    """Prose lines from the depth's template that should never survive into a finished note."""
    template = TEMPLATE.get(depth, TEMPLATES / "research.md")
    if not template.exists():
        return []
    prompts = []
    for line in template.read_text().splitlines():
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
    for entry in flow_list(value):
        if not entry.startswith("~/"):
            warns.append(
                f"related entry {entry!r} isn't a ~ path; skills grep for ~ paths"
            )
        elif not Path(entry).expanduser().exists():
            fails.append(
                f"related entry {entry} doesn't exist: fix the path, or remove it if the "
                "file was deleted"
            )


def after_sources(depth):
    return AFTER_SOURCES if depth == "ideas" else AFTER_SOURCES[1:]


def check_after_sources(body, depth, fails):
    """Only Verification (and, for depth: ideas, Candidate pool before it) may follow
    `## Sources`: anything else would escape the word budget and the citation check."""
    allowed = after_sources(depth)
    names = " and ".join(f"'{h}'" for h in allowed)
    src_at = heading_index(body, "## Sources")
    if src_at is None:
        return
    seen = []
    for line in body[src_at + 1 :]:
        if not line.startswith("#"):
            continue
        heading = next((h for h in allowed if line.startswith(h)), None)
        if heading is None:
            fails.append(
                f"'{line.strip()}' comes after Sources; only {names} may. Move it above Sources"
            )
        else:
            seen.append(heading)
    if seen != sorted(seen, key=allowed.index):
        fails.append("'## Candidate pool' must come before '## Verification'")


def stray_after_sources(body, depth):
    """Lines after `## Sources` that aren't a source, its continuation, a 'Checked on' line,
    the Verification table or (depth: ideas) the Candidate pool. They're prose, so they count
    toward the budget and the citations."""
    src_at = heading_index(body, "## Sources")
    if src_at is None:
        return []
    stray, in_pool = [], False
    for line in body[src_at + 1 :]:
        if line.startswith("#"):
            in_pool = depth == "ideas" and line.startswith("## Candidate pool")
        text = line.strip()
        if (
            in_pool
            or not text
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


def check_pool(pool, scope, fails, warns):
    """The Candidate pool: at least POOL_MIN candidates, each tagged with a lens in scope and
    marked cut or shortlisted, spread across the lenses. Returns how many were shortlisted."""
    candidates, untagged, prose = [], [], []
    for line in pool:
        text = line.strip()
        if not text:
            continue
        if m := CANDIDATE.match(line):
            candidates.append((m.group(1).strip().lower(), text))
        elif re.match(r"[-*]\s", text):
            untagged.append(text)
        elif not line[:1].isspace():
            prose.append(text)
    if untagged:
        fails.append(
            f"{len(untagged)} Candidate pool lines have no [lens] tag "
            f"(first: '{untagged[0][:50]}')"
        )
    if len(prose) > 2:
        fails.append(
            f"{len(prose)} lines of prose in the Candidate pool; it holds one-line candidates, "
            "and prose there escapes the word budget. Move it above Sources"
        )
    if len(candidates) < POOL_MIN:
        fails.append(
            f"Candidate pool has {len(candidates)} candidates; at least {POOL_MIN} are required"
        )
    if bad := sorted({lens for lens, _ in candidates if lens not in scope}):
        fails.append(
            f"Candidate pool uses lenses outside this note's scope: {', '.join(bad)} "
            f"(in scope: {', '.join(scope)})"
        )
    used = {lens for lens, _ in candidates if lens in scope}
    need = min(5, len(scope))
    if len(used) < need:
        fails.append(
            f"Candidate pool covers {len(used)} lenses ({', '.join(sorted(used)) or 'none'}); "
            f"at least {need} of {', '.join(scope)} are required"
        )
    if thin := [lens for lens in scope if sum(c[0] == lens for c in candidates) == 1]:
        warns.append(
            f"only one candidate for lens {', '.join(thin)}; the rule is two per lens"
        )
    if unmarked := [text for _, text in candidates if not CANDIDATE_MARK.search(text)]:
        fails.append(
            f"{len(unmarked)} candidates are marked neither 'Cut: <reason>' nor "
            f"'Shortlisted #n' (first: '{unmarked[0][:50]}')"
        )
    if long := [text for _, text in candidates if len(text.split()) > 60]:
        warns.append(
            f"{len(long)} candidates run over 60 words (first: '{long[0][:40]}'); keep them to one line"
        )
    return sum(
        bool(re.search(r"\bshortlisted\b", t, re.IGNORECASE)) for _, t in candidates
    )


def check_shortlist(section_lines, scope, shortlisted, fails, warns):
    """The Shortlist rubric table: every rubric column, 5-7 numbered ideas with every cell
    filled, a baseline row, and at least three lenses."""
    header, rows = first_table(section_lines)
    if not header:
        fails.append("Shortlist has no table")
        return
    names = [normalise(h) for h in header]
    if missing := [c for c in RUBRIC if c.lower() not in names]:
        fails.append(f"Shortlist table is missing rubric columns: {', '.join(missing)}")
    ideas = [r for r in rows if r and r[0].strip("*# ").isdigit()]
    baseline = [r for r in rows if r and not r[0].strip("*# ").isdigit()]
    low, high = SHORTLIST_SIZE
    if not low <= len(ideas) <= high:
        fails.append(
            f"Shortlist has {len(ideas)} numbered ideas; {low} to {high} are required"
        )
    if not baseline:
        fails.append("Shortlist has no baseline row (do nothing, or post only)")
    empty = [
        r[0].strip("* ") for r in ideas if len(r) < len(header) or any(not c for c in r)
    ]
    if empty:
        fails.append(
            f"Shortlist rows with empty cells: #{', #'.join(empty)}; every rubric cell needs a reason"
        )
    if "lens" in names:
        at = names.index("lens")
        lenses = {normalise(r[at]).strip("[]") for r in ideas if len(r) > at} - {""}
        need = min(3, len(scope))
        if len(lenses) < need:
            fails.append(
                f"Shortlist spans {len(lenses)} lenses ({', '.join(sorted(lenses))}); "
                f"at least {need} are required"
            )
        if odd := sorted(lens for lens in lenses if lens not in scope):
            warns.append(
                f"Shortlist Lens values outside this note's scope: {', '.join(odd)}"
            )
    if shortlisted != len(ideas):
        warns.append(
            f"{shortlisted} pool candidates are marked Shortlisted, but the Shortlist has "
            f"{len(ideas)} numbered ideas"
        )


def check_ideas(body, fields, prose_end, sources, fails, warns):
    """Checks that only apply to depth: ideas."""
    scope = flow_list(fields.get("lenses", "")) or list(LENSES)
    if bad := [lens for lens in scope if lens not in LENSES]:
        fails.append(f"frontmatter 'lenses' has unknown lenses: {', '.join(bad)}")
    if not fields.get("rank-by"):
        warns.append(
            "frontmatter 'rank-by' is empty; say what the shortlist is ranked by"
        )
    pool_at = heading_index(body, "## Candidate pool")
    if pool_at is not None and pool_at < prose_end:
        fails.append(
            "'## Candidate pool' must come after Sources, outside the word budget"
        )
    shortlisted = check_pool(
        section(body, "## Candidate pool") or [], scope, fails, warns
    )
    shortlist = section(body, "## Shortlist")
    if shortlist is not None:
        check_shortlist(shortlist, scope, shortlisted, fails, warns)
    evidence = section(body, "### Attention evidence")
    if evidence is not None and not any(l.lstrip().startswith("|") for l in evidence):
        warns.append(
            "Attention evidence has no table of data points; new ones found in this research "
            "go there for merging into the attention-evidence note"
        )
    if not any(EVIDENCE_NOTE in line for line in sources):
        warns.append(
            f"Sources doesn't cite the attention-evidence note ({EVIDENCE_NOTE})"
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
        fails.append(f"depth is {depth!r}; expected full, quick or ideas")
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
    if stray := stray_after_sources(body, depth):
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
    # The Candidate pool is outside the word budget but inside the citation check.
    pool = (section(body, "## Candidate pool") or []) if depth == "ideas" else []
    cited = set().union(*(cited_numbers(line) for line in prose + pool))
    if dangling := sorted(cited - source_nums):
        fails.append(
            f"citations with no matching source: {', '.join(f'[{n}]' for n in dangling)}"
        )
    if uncited := sorted(source_nums - cited):
        warns.append(f"sources never cited in the text: {', '.join(map(str, uncited))}")

    check_verification(body, prose, status, fails, warns)
    if depth == "ideas":
        check_ideas(
            body,
            fields,
            src_at if src_at is not None else len(body),
            sources,
            fails,
            warns,
        )

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
    leftovers = [p for p in template_prompts(depth) if p in text]
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

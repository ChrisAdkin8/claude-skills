"""Markdown helpers shared by check-note.py and ~/.claude/skills/spec/scripts/check-spec.py.

Not run on its own. Each checker loads it by path, so a fix here reaches both: frontmatter,
code fences, sections, template leftovers, and the secret and account-ID patterns.
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
            value = value.split(" #")[0].strip()
            # `status: "reviewed"` is YAML for reviewed; a checker comparing the raw text
            # would miss it.
            if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            fields[key] = value
    return fields, len(lines)


def strip_code(lines):
    """Drop fenced code blocks: commands, their output and diagrams."""
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

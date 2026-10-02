#!/usr/bin/env python3
"""The implement ledger: what every implementer and verifier call for one spec has cost.

Usage:
  ledger.py path <run name>             print the ledger's path
  ledger.py spent <run name>            print what the implementer calls have spent, in USD
  ledger.py next-call <run name>        print the number the next implementer call takes
  ledger.py append <run name> <json>    append one line, adding "at" if it has none

<run name> is `<repo dir>--<spec basename>`, as in ~/.cache/implement-runs/. The ledger is
~/.cache/implement-ledger/<run name>.jsonl, in a 0700 dir outside everything the implementer's
sandbox can write, and nothing here ever removes or rewrites it: to go past the cap, the user raises
IMPLEMENT_MAX_USD or removes the file by hand. run-implementer.sh and run-verify.sh write and read
it only through this script, so the format and the path rule live here.

Three kinds of line, each one JSON object:
  {"at", "who": "implementer", "call": <n>, "event": "start", "budget": <usd>}
  {"at", "who": "implementer", "call": <n>, "event": "end", "usd": <usd>}
  {"at", "who": "verifier V<n>", "usd": <usd or null>, "note": <text>}
A start's call is one more than the start lines before it, so a number never repeats across fresh
runs; an end must follow its own start, once. Spent is the sum over implementer calls of the end's
usd, or the start's budget if no end follows. Verifier lines don't count; they're checked for shape.
Any other line, or a negative or non-finite number, refuses: exit 2, naming the line.
"""

import datetime
import json
import math
import os
import re
import sys
from pathlib import Path

NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
VERIFIER = re.compile(r"verifier V[0-9]+")


class Bad(Exception):
    pass


def ledger_path(run_name):
    if not NAME.fullmatch(run_name) or ".." in run_name:
        raise Bad(f"not a run name: {run_name!r}")
    return Path.home() / ".cache" / "implement-ledger" / f"{run_name}.jsonl"


def amount(value, what, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Bad(f"{what} is not a number: {value!r}")
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise Bad(
            f"{what} must be a finite number {'above' if positive else 'at least'} 0, not {value!r}"
        )
    return float(value)


def shape(line):
    """The line's kind, `start`, `end` or `verifier`, or Bad if it is none of them."""
    if not isinstance(line, dict):
        raise Bad("not a JSON object")
    if not isinstance(line.get("at"), str):
        raise Bad('no "at" string')
    who = line.get("who")
    if who == "implementer":
        event = line.get("event")
        keys = {
            "start": {"at", "who", "call", "event", "budget"},
            "end": {"at", "who", "call", "event", "usd"},
        }
        if event not in keys:
            raise Bad(
                f"an implementer line's event must be start or end, not {event!r}"
            )
        if set(line) != keys[event]:
            raise Bad(
                f"an implementer {event} line has the keys {sorted(keys[event])}, not {sorted(line)}"
            )
        call = line["call"]
        if isinstance(call, bool) or not isinstance(call, int) or call < 1:
            raise Bad(f"call must be a whole number from 1, not {call!r}")
        if event == "start":
            amount(line["budget"], "budget", positive=True)
        else:
            amount(line["usd"], "usd")
        return event
    if isinstance(who, str) and VERIFIER.fullmatch(who):
        if set(line) != {"at", "who", "usd", "note"}:
            raise Bad(
                f"a verifier line has the keys at, note, usd and who, not {sorted(line)}"
            )
        if line["usd"] is not None:
            amount(line["usd"], "usd")
        if not isinstance(line["note"], str):
            raise Bad("a verifier line's note must be text")
        return "verifier"
    raise Bad(f"unknown who: {who!r}")


class Ledger:
    """The ledger's lines, checked in order; add() checks one more as if it were appended."""

    def __init__(self, lines):
        self.starts = {}  # call -> budget
        self.ends = {}  # call -> usd
        for number, line in enumerate(lines, 1):
            try:
                self.add(line)
            except Bad as e:
                raise Bad(f"line {number}: {e}") from None

    def add(self, line):
        kind = shape(line)
        if kind == "start":
            if line["call"] != len(self.starts) + 1:
                raise Bad(
                    f"start of call {line['call']}, but the next call is {len(self.starts) + 1}"
                )
            self.starts[line["call"]] = float(line["budget"])
        elif kind == "end":
            if line["call"] not in self.starts:
                raise Bad(f"end of call {line['call']}, which has no start line")
            if line["call"] in self.ends:
                raise Bad(f"a second end of call {line['call']}")
            self.ends[line["call"]] = float(line["usd"])

    def spent(self):
        return sum(self.ends.get(call, budget) for call, budget in self.starts.items())


def read(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return []
    except OSError as e:
        raise Bad(f"can't read {path}: {e.strerror}") from None
    with open(fd, encoding="utf-8") as f:
        text = f.read()
    lines = []
    for number, raw in enumerate(text.splitlines(), 1):
        try:
            lines.append(json.loads(raw))
        except ValueError:
            raise Bad(f"{path}: line {number} is not JSON") from None
    if text and not text.endswith("\n"):
        raise Bad(f"{path}: the last line has no newline")
    return lines


def check(path):
    try:
        return Ledger(read(path))
    except Bad as e:
        raise Bad(f"{path}: {e}") from None


def append(path, line):
    if not isinstance(line, dict):
        raise Bad("the line to append is not a JSON object")
    line = {
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"
        ),
        **line,
    }
    ledger = check(path)
    try:
        ledger.add(line)
    except Bad as e:
        raise Bad(f"{path}: refusing to append: {e}") from None
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with open(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(line, allow_nan=False) + "\n")


def number(value):
    return f"{value:.6f}".rstrip("0").rstrip(".")


def main(argv):
    commands = {"path": 1, "spent": 1, "next-call": 1, "append": 2}
    if len(argv) < 2 or commands.get(argv[0]) != len(argv) - 1:
        print((__doc__ or "").split("\n\n")[1], file=sys.stderr)
        return 2
    try:
        path = ledger_path(argv[1])
        if argv[0] == "path":
            print(path)
        elif argv[0] == "spent":
            print(number(check(path).spent()))
        elif argv[0] == "next-call":
            print(len(check(path).starts) + 1)
        else:
            try:
                line = json.loads(argv[2])
            except ValueError:
                raise Bad("the line to append is not JSON") from None
            append(path, line)
    except Bad as e:
        print(f"ledger: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"ledger: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

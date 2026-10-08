#!/usr/bin/env python3
"""The implement ledger: what every implementer and verifier call for one spec has cost.

Usage:
  ledger.py path <run name>             print the ledger's path
  ledger.py spent <run name>            print what the implementer calls have spent, in USD
  ledger.py next-call <run name>        print the number the next implementer call takes
  ledger.py append <run name> <json>    append one line, adding "at" if it has none, and an end
                                        or settled line's "usd" from its "session" and "total"
  ledger.py interrupt <run name> <call> <budget>
                                        end an interrupted call, charging its budget, unless it
                                        already has an end line
  ledger.py settle <run name> <call> <usd>
                                        charge a call that was charged its budget what it cost,
                                        once; only for a call whose cost you know, for example
                                        from the Claude Console's usage page
  ledger.py report <run name>           print each implementer call's cost and where it comes
                                        from, each verifier run's, the implementer total that
                                        counts against the cap, and the total of all runs

<run name> is `<repo dir>--<spec basename>`, as in ~/.cache/implement-runs/. The ledger is
~/.cache/implement-ledger/<run name>.jsonl, in a 0700 dir outside everything the implementer's
sandbox can write, and nothing here ever removes or rewrites a line: to go past the cap, the user
raises IMPLEMENT_MAX_USD, or settles a call charged its budget whose cost they know.
run-implementer.sh and run-verify.sh write and read it only through this script, so the format and
the path rule live here.

These kinds of line, each one JSON object, with exactly these keys:
  {"at", "who": "implementer", "call": <n>, "event": "start", "budget": <usd>}
  {"at", "who": "implementer", "call": <n>, "event": "end", "usd": <usd>,
   "session": <the result's session_id>, "total": <its total_cost_usd>}
  {"at", "who": "implementer", "call": <n>, "event": "end", "usd": <budget>, "no_total": true}
  {"at", "who": "implementer", "call": <n>, "event": "end", "usd": <budget>, "interrupted": true}
  {"at", "who": "implementer", "call": <n>, "event": "settled", "usd": <usd>}, with "session"
   and "total" too when its cost comes from a result
  {"at", "who": "verifier V<n>", "usd": <usd or null>, "note": <text>}
and the end line written before session and total were kept, {"at", "who", "call", "event": "end",
"usd"}, which counts as it did.

A start's call is one more than the start lines before it, so a number never repeats across fresh
runs; an end must follow its own start, once. A resumed session's result reports its running total,
so an end's usd is the call's own cost: its total less the latest total an earlier line holds for
the same session, or the total itself when there is none or it is lower. A settled line replaces
the charge of a call charged its budget (no_total, interrupted, or with no end line), at most once,
and its usd follows the same rule. Spent is the sum over implementer calls of the settled usd, or
the end's, or the start's budget if neither follows. Verifier lines don't count; they're checked for
shape. Any other line, or a negative or non-finite number, refuses: exit 2, naming the line.
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


# Each implementer line's possible key sets, by event.
BASE = {"at", "who", "call", "event"}
KEYS = {
    "start": [BASE | {"budget"}],
    "end": [
        BASE | {"usd", "session", "total"},
        BASE | {"usd", "no_total"},
        BASE | {"usd", "interrupted"},
        BASE | {"usd"},  # written before session and total were kept
    ],
    "settled": [BASE | {"usd", "session", "total"}, BASE | {"usd"}],
}


def shape(line):
    """The line's kind, `start`, `end`, `settled` or `verifier`, or Bad if it is none of them."""
    if not isinstance(line, dict):
        raise Bad("not a JSON object")
    if not isinstance(line.get("at"), str):
        raise Bad('no "at" string')
    who = line.get("who")
    if who == "implementer":
        event = line.get("event")
        if event not in KEYS:
            raise Bad(
                f"an implementer line's event must be start, end or settled, not {event!r}"
            )
        if set(line) not in KEYS[event]:
            raise Bad(
                f"an implementer {event} line has the keys "
                + " or ".join(str(sorted(keys)) for keys in KEYS[event])
                + f", not {sorted(line)}"
            )
        call = line["call"]
        if isinstance(call, bool) or not isinstance(call, int) or call < 1:
            raise Bad(f"call must be a whole number from 1, not {call!r}")
        if event == "start":
            amount(line["budget"], "budget", positive=True)
            return event
        amount(line["usd"], "usd")
        if "session" in line:
            if not isinstance(line["session"], str) or not line["session"]:
                raise Bad(f"session must be a string, not {line['session']!r}")
            amount(line["total"], "total")
        for flag in ("no_total", "interrupted"):
            if flag in line and line[flag] is not True:
                raise Bad(f"{flag} must be true, not {line[flag]!r}")
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
        self.ends = {}  # call -> its end line
        self.settled = {}  # call -> usd
        self.totals = {}  # session -> the latest total a line holds for it
        self.verifiers = []  # verifier lines, in order
        for number, line in enumerate(lines, 1):
            try:
                self.add(line)
            except Bad as e:
                raise Bad(f"line {number}: {e}") from None

    def add(self, line):
        kind = shape(line)
        if kind == "verifier":
            self.verifiers.append(line)
        elif kind == "start":
            if line["call"] != len(self.starts) + 1:
                raise Bad(
                    f"start of call {line['call']}, but the next call is {len(self.starts) + 1}"
                )
            self.starts[line["call"]] = float(line["budget"])
        elif kind in ("end", "settled"):
            call = line["call"]
            if call not in self.starts:
                raise Bad(f"{kind} line for call {call}, which has no start line")
            if call in self.settled:
                raise Bad(f"{'an end' if kind == 'end' else 'a second settled line'} of call"
                          f" {call}, after its settled line")
            if kind == "end" and call in self.ends:
                raise Bad(f"a second end of call {call}")
            if kind == "end" and ("no_total" in line or "interrupted" in line):
                if float(line["usd"]) != self.starts[call]:
                    raise Bad(f"call {call}'s end charges {line['usd']}, not its budget")
            if kind == "settled" and not self.unsettled(call):
                raise Bad(f"call {call} wasn't charged its budget, so it can't be settled")
            if "session" in line:
                self.totals[line["session"]] = float(line["total"])
            if kind == "end":
                self.ends[call] = line
            else:
                self.settled[call] = float(line["usd"])

    def unsettled(self, call):
        """Whether the call is charged its budget: no end line, or one with no total or interrupted."""
        end = self.ends.get(call)
        return call not in self.settled and (
            end is None or "no_total" in end or "interrupted" in end
        )

    def own(self, session, total):
        """A call's own cost, from its session's running total and the latest one the ledger holds."""
        earlier = self.totals.get(session)
        if earlier is None or total < earlier:
            return total
        return round(total - earlier, 6)

    def charge(self, call):
        if call in self.settled:
            return self.settled[call]
        if call in self.ends:
            return float(self.ends[call]["usd"])
        return self.starts[call]

    def spent(self):
        return sum(self.charge(call) for call in self.starts)


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
    if line.get("event") in ("end", "settled") and "usd" not in line and isinstance(
        line.get("session"), str
    ):
        line["usd"] = ledger.own(line["session"], amount(line.get("total"), "total"))
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


def whole(text, what):
    if not re.fullmatch(r"[1-9][0-9]*", text):
        raise Bad(f"{what} must be a whole number from 1, not {text!r}")
    return int(text)


def usd(text, what):
    try:
        value = float(text)
    except ValueError:
        raise Bad(f"{what} is not a number: {text!r}") from None
    return amount(value, what)


def interrupt(path, call, budget):
    """Charge an interrupted call its budget, unless it already has an end line."""
    ledger = check(path)
    if call in ledger.ends or call in ledger.settled:
        return
    append(path, {"who": "implementer", "call": call, "event": "end", "usd": budget,
                  "interrupted": True})


def report(ledger):
    out = []
    for call in ledger.starts:
        end = ledger.ends.get(call)
        if call in ledger.settled:
            source = "settled"
        elif end is not None and not ledger.unsettled(call):
            source = "from its end line"
        else:
            why = ("no end line" if end is None
                   else "interrupted" if "interrupted" in end else "no total in its result")
            source = (f"its budget ({why}; unsettled: ledger.py settle <run name> {call} <usd>"
                      " if you know its cost)")
        out.append(f"implementer call {call}: ${number(ledger.charge(call))}, {source}")
    spent = ledger.spent()
    known, unknown = spent, []
    for line in ledger.verifiers:
        if line["usd"] is None:
            unknown.append(line["who"])
            out.append(f"{line['who']}: unknown")
        else:
            known += line["usd"]
            out.append(f"{line['who']}: ${number(line['usd'])}")
    out.append(f"implementer total: ${number(spent)}, which counts against the cap")
    if unknown:
        out.append(f"all runs: at least ${number(known)} ({', '.join(unknown)} unknown)")
    else:
        out.append(f"all runs: ${number(known)}")
    return "\n".join(out)


def main(argv):
    commands = {"path": 1, "spent": 1, "next-call": 1, "append": 2, "interrupt": 3,
                "settle": 3, "report": 1}
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
        elif argv[0] == "interrupt":
            interrupt(path, whole(argv[2], "call"), usd(argv[3], "budget"))
        elif argv[0] == "settle":
            append(path, {"who": "implementer", "call": whole(argv[2], "call"),
                          "event": "settled", "usd": usd(argv[3], "usd")})
        elif argv[0] == "report":
            print(report(check(path)))
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

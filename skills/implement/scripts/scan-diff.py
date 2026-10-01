#!/usr/bin/env python3
"""Flag out-of-scope files and weakened tests in a work item's staged diff.

Usage: scan-diff.py --base REV [--files PATH...] [--diff-file PATH]

Reads `git diff --cached REV` in the current repo: the staged change against the work item's
starting commit (stage new files first, or they aren't seen). REV must name a commit, and git diff
gets its SHA; one that starts with `-` is refused, since git would read it as an option.
--diff-file reads a saved unified diff instead, and then --base isn't needed. --files is the
caller's whole allowed list: the work item's Files plus any file a logged departure added. Without
--files, scope isn't checked.

Prints one `FLAG <kind>: <file>:<line>: <text>` per hit and exits 1 if there are any; else prints
nothing and exits 0. Exits 2 if REV isn't a commit or the diff can't be read. The line is the new
file's line for an added line, the old file's for a removed one, and 0 for a flag about the whole
file.

Kinds:
  scope         a changed file not in --files
  deleted-test  a removed test file, or a removed `def test_`, `it(` or `test(` line whose test
                isn't added back in the same file (a changed signature isn't a deletion)
  skip          an added @skip, skipIf, skipUnless, skipTest, xfail, .only(, .skip( or t.Skip(
  silenced      an added noqa, type: ignore, eslint-disable, pragma: no cover or shellcheck disable
  loosened      in a test file, a hunk that removes an assert or expect( line and adds none
  mocked        in a test file, an added mock.patch, MagicMock or jest.mock

A test file is one under tests/, test/ or __tests__/, or named test_*, *_test.*, *.test.* or
*.spec.*. False positives (a test deleted on purpose) are expected: the caller asks, which is the
safe failure.
"""

import argparse
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
TEST_DIRS = {"tests", "test", "__tests__"}
TEST_NAMES = ("test_*", "*_test.*", "*.test.*", "*.spec.*")
TEST_DEF = re.compile(
    r"""^\s*(?:async\s+)?def\s+(test_\w+)"""  # Python
    r"""|^\s*(?:it|test)\s*\(\s*(['"`])(.*?)\2"""  # JS: it('name', ...) / test("name", ...)
    r"""|^\s*(?:it|test)\s*\("""  # JS, a name this can't read
)
SKIP = re.compile(r"@skip|skipIf|skipUnless|skipTest|xfail|\.only\(|\.skip\b|t\.Skip\(")
SILENCED = re.compile(
    r"noqa|type:\s*ignore|eslint-disable|pragma:\s*no cover|shellcheck disable"
)
ASSERTION = re.compile(r"\bassert|\bexpect\(")
MOCKED = re.compile(r"mock\.patch|MagicMock|jest\.mock")


def is_test_file(path):
    p = PurePosixPath(path)
    return bool(TEST_DIRS & set(p.parts[:-1])) or any(
        fnmatch(p.name, n) for n in TEST_NAMES
    )


def test_key(line):
    """The test a `def test_` / `it(` / `test(` line defines, or None if it defines none."""
    m = TEST_DEF.match(line)
    if not m:
        return None
    return m.group(1) or m.group(3) or line.strip()


class File:
    def __init__(self, old, new):
        self.old, self.new = old, new
        self.deleted = self.added = False
        self.hunks = []  # each a list of (sign, old line, new line, text)

    @property
    def path(self):
        return self.new if self.new else self.old


def path_of(side):
    """`a/x` or `b/x` from a ---/+++ line, or None for /dev/null. Git adds a tab after a name with
    a space in it."""
    side = side.rstrip("\n").rstrip("\t")
    if side == "/dev/null":
        return None
    if side.startswith('"'):
        side = side[1:-1].encode().decode("unicode_escape").encode("latin-1").decode()
    return side[2:] if side[:2] in ("a/", "b/") else side


def parse(text):
    files, current, old_no, new_no = [], None, 0, 0
    for line in text.splitlines():
        if line.startswith("diff --git "):
            m = re.match(r"diff --git a/(.*) b/(.*)$", line)
            current = File(*(m.groups() if m else (None, None)))
            files.append(current)
        elif current is None:
            continue
        elif line.startswith("deleted file mode"):
            current.deleted = True
        elif line.startswith("new file mode"):
            current.added = True
        elif line.startswith("--- ") and not current.hunks:
            current.old = path_of(line[4:])
        elif line.startswith("+++ ") and not current.hunks:
            current.new = path_of(line[4:])
        elif m := HUNK.match(line):
            old_no, new_no = int(m.group(1)), int(m.group(2))
            current.hunks.append([])
        elif current.hunks and line[:1] in ("+", "-", " "):
            sign = line[0]
            current.hunks[-1].append((sign, old_no, new_no, line[1:]))
            if sign != "+":
                old_no += 1
            if sign != "-":
                new_no += 1
    return files


def scan(files, allowed):
    flags = []
    for f in files:
        path, test = f.path, is_test_file(f.path)
        found = []
        if allowed is not None and not ({f.old, f.new} - {None}) <= allowed:
            found.append((0, "scope", "not in --files"))
        if f.deleted and test:
            found.append((0, "deleted-test", "test file deleted"))
            flags += [(path, *hit) for hit in found]
            continue
        added_tests = {
            test_key(text)
            for hunk in f.hunks
            for sign, _, _, text in hunk
            if sign == "+"
        }
        for hunk in f.hunks:
            for sign, old_no, new_no, text in hunk:
                if sign == "-":
                    key = test_key(text)
                    if key and key not in added_tests:
                        found.append((old_no, "deleted-test", text.strip()))
                elif sign == "+":
                    if SKIP.search(text):
                        found.append((new_no, "skip", text.strip()))
                    if SILENCED.search(text):
                        found.append((new_no, "silenced", text.strip()))
                    if test and MOCKED.search(text):
                        found.append((new_no, "mocked", text.strip()))
            if test:
                removed = [
                    (o, t) for s, o, _, t in hunk if s == "-" and ASSERTION.search(t)
                ]
                if removed and not any(
                    s == "+" and ASSERTION.search(t) for s, _, _, t in hunk
                ):
                    found.append((removed[0][0], "loosened", removed[0][1].strip()))
        found.sort(key=lambda hit: hit[0])
        flags += [(path, *hit) for hit in found]
    return flags


def main():
    parser = argparse.ArgumentParser(
        description="Flag out-of-scope files and weakened tests."
    )
    parser.add_argument("--base", help="the work item's starting commit")
    parser.add_argument(
        "--files", nargs="*", help="every file the work item may change"
    )
    parser.add_argument(
        "--diff-file", help="read this saved diff instead of the staged one"
    )
    args = parser.parse_args()
    if args.diff_file:
        try:
            text = Path(args.diff_file).read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            print(f"scan-diff: can't read {args.diff_file}: {e}", file=sys.stderr)
            return 2
    elif args.base:
        # A value that starts with `-` would reach git as an option: --base=--output=FILE made git
        # diff write the diff over FILE, and the scan then read nothing and exited 0. So, as
        # prepare-verify.sh does, refuse it, resolve the rest to a commit, and give git the SHA.
        if args.base.startswith("-"):
            print(f"scan-diff: not a revision: {args.base}", file=sys.stderr)
            return 2
        run = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "--end-of-options",
             f"{args.base}^{{commit}}"],
            capture_output=True, check=False,
        )  # fmt: skip
        if run.returncode != 0:
            print(f"scan-diff: {args.base} is not a commit", file=sys.stderr)
            sys.stderr.write(run.stderr.decode(errors="replace"))  # e.g. not a git repo
            return 2
        base = run.stdout.decode().strip()
        run = subprocess.run(
            ["git", "-c", "core.quotePath=off", "diff", "--cached", "--no-color", "--no-ext-diff",
             "--no-renames", "--src-prefix=a/", "--dst-prefix=b/", base, "--"],
            capture_output=True, check=False,
        )  # fmt: skip
        if run.returncode != 0:
            print(f"scan-diff: git diff --cached {args.base} failed: "
                  f"{run.stderr.decode(errors='replace').strip()}", file=sys.stderr)  # fmt: skip
            return 2
        text = run.stdout.decode(errors="replace")
    else:
        parser.error("give --base REV, or --diff-file PATH")
    allowed = None
    if args.files is not None:
        allowed = {p.removeprefix("./") for p in args.files}
    flags = scan(parse(text), allowed)
    for path, line, kind, text in flags:
        print(f"FLAG {kind}: {path}:{line}: {text}")
    return 1 if flags else 0


if __name__ == "__main__":
    raise SystemExit(main())

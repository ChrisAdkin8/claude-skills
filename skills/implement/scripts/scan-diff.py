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
  deleted-test  a removed test file, or a removed line that defines a test that isn't added back
                in the same file (a changed signature isn't a deletion): Python's `def test_`,
                Go's `func TestX(`, Swift's `func testX()`, a `#[test]` or `@Test` (the test is
                the function it marks), or, in a test file only, `describe(`, `it(` or `test(`
  skip          an added @skip, skipIf, skipUnless, skipTest, skipif, xfail, @expectedFailure,
                raise SkipTest, .only(, .skip(, .todo(, xit(, xdescribe(, xtest(, @Disabled,
                @Ignore, XCTSkip, or Go's t.Skip(, t.Skipf( or t.SkipNow(
  silenced      an added noqa, type: ignore, pylint: disable, eslint-disable, @ts-ignore,
                @ts-expect-error, @ts-nocheck, nolint, swiftlint:disable, pragma: no cover or
                shellcheck disable
  loosened      in a test file, a hunk that removes an assert, expect( or XCTAssert line and adds
                none
  mocked        in a test file, an added mock.patch, MagicMock or jest.mock

A test file is one under tests/, test/, __tests__/ or spec/, in any case (Swift's Tests/), or
named test_*, *_test.*, *.test.*, *.spec.*, *_spec.*, tests.py or conftest.py. False positives (a
test deleted on purpose) are expected: the caller asks, which is the safe failure.
"""

import argparse
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

HUNK = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
# Folder names match in any case: Swift's is Tests/.
TEST_DIRS = {"tests", "test", "__tests__", "spec"}
TEST_NAMES = (
    "test_*", "*_test.*", "*.test.*", "*.spec.*", "*_spec.*", "tests.py", "conftest.py",
)  # fmt: skip
TEST_DEF = re.compile(
    r"^\s*(?:async\s+)?def\s+(test_\w+)"  # Python
    r"|^\s*func\s+(?:\([^)]*\)\s*)?(Test\w*)\s*\("  # Go: func TestX(, or a suite's method
    r"|^\s*(?:[@\w]+\s+)*func\s+(test\w*)\s*\(\s*\)"  # Swift: XCTest runs no-argument testX()
)
# describe('name', ...), it('name', ...) or test('name', ...); one whose name this can't read is
# keyed by its whole line. Only in a test file: elsewhere these are ordinary calls.
JS_TEST_DEF = re.compile(r"""^\s*(?:describe|it|test)\s*\(\s*(?:(['"`])(.*?)\1)?""")
# #[test] (Rust) or @Test (JUnit, Swift Testing): the test is the function on its line or below.
TEST_ATTR = re.compile(r"^\s*(?:#\[test\]|@Test\b)")
FUNC_NAME = re.compile(r"\b(?:fn|func|fun|void)\s+(`[^`]+`|\w+)")
SKIP = re.compile(
    r"@skip|skipIf|skipUnless|skipTest|\.skipif\b|xfail|@(?:unittest\.)?expectedFailure\b"
    r"|raise\s+(?:\w+\.)*SkipTest\b|\.only\(|\.skip\b|\b(?:describe|it|test)\.todo\("
    r"|\bx(?:describe|it|test)\(|@Disabled|@Ignore\b|XCTSkip"
    # Go's Skip, Skipf and SkipNow on a test's t, a benchmark's b, a TB or a suite's T(): not
    # C#'s list.Skip(n).
    r"|(?:\b(?:t|b|tb)|\.T\(\))\.Skip(?:f|Now)?\("
)
SILENCED = re.compile(
    r"noqa|type:\s*ignore|pylint:\s*disable|eslint-disable|@ts-(?:ignore|expect-error|nocheck)"
    r"|\bnolint\b|swiftlint:disable|pragma:\s*no cover|shellcheck disable"
)
ASSERTION = re.compile(r"\bassert|\bexpect\(|\bXCTAssert")
MOCKED = re.compile(r"mock\.patch|MagicMock|jest\.mock")


def is_test_file(path):
    p = PurePosixPath(path)
    return bool(TEST_DIRS & {part.lower() for part in p.parts[:-1]}) or any(
        fnmatch(p.name, n) for n in TEST_NAMES
    )


def test_key(lines, i, in_test_file):
    """The test that lines[i] defines, or None if it defines none. `lines` is one side of a hunk,
    so an attribute's test can be named by the function below it."""
    line = lines[i]
    if m := TEST_DEF.match(line):
        return m.group(1) or m.group(2) or m.group(3)
    if in_test_file and (m := JS_TEST_DEF.match(line)):
        return m.group(2) or line.strip()
    if m := TEST_ATTR.match(line):
        for text in (line[m.end() :], *lines[i + 1 : i + 4]):
            if name := FUNC_NAME.search(text):
                return name.group(1)
        return line.strip()
    return None


def tests_defined(hunk, sign, in_test_file):
    """{line number: test} for each test a hunk's `sign` lines define, read on that side: the old
    file's lines for "-", the new file's for "+"."""
    side = [(o if sign == "-" else n, s, t) for s, o, n, t in hunk if s in (sign, " ")]
    texts = [t for _, _, t in side]
    return {
        no: key
        for i, (no, s, _) in enumerate(side)
        if s == sign and (key := test_key(texts, i, in_test_file))
    }


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
            key for hunk in f.hunks for key in tests_defined(hunk, "+", test).values()
        }
        for hunk in f.hunks:
            removed_tests = tests_defined(hunk, "-", test)
            for sign, old_no, new_no, text in hunk:
                if sign == "-":
                    key = removed_tests.get(old_no)
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

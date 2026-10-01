"""Tests for skills/implement/scripts/scan-diff.py: out-of-scope files and weakened tests in a
staged diff.

Run with: python3 -m unittest discover -s tests
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "implement" / "scripts" / "scan-diff.py"


def diff(path, hunks, header=""):
    """A one-file unified diff of `path`: its git header, then the hunks as given."""
    old = "/dev/null" if "new file mode" in header else f"a/{path}"
    new = "/dev/null" if "deleted file mode" in header else f"b/{path}"
    return (
        f"diff --git a/{path} b/{path}\n{header}index 1111111..2222222\n"
        f"--- {old}\n+++ {new}\n{hunks}"
    )


# One fixture per kind. Each lists the files it may touch, so only its own kind is flagged.
KINDS = {
    "scope": (
        diff("src/app.py", "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n"),
        [],
        "FLAG scope: src/app.py:0: not in --files",
    ),
    "deleted-test": (
        diff(
            "tests/test_app.py",
            "@@ -1,4 +1,2 @@\n import app\n-def test_old():\n-    pass\n # end\n",
        ),
        ["tests/test_app.py"],
        "FLAG deleted-test: tests/test_app.py:2: def test_old():",
    ),
    "skip": (
        diff(
            "tests/test_app.py",
            "@@ -3,1 +3,2 @@\n+@skip('flaky')\n def test_x():\n",
        ),
        ["tests/test_app.py"],
        "FLAG skip: tests/test_app.py:3: @skip('flaky')",
    ),
    "silenced": (
        diff("src/app.py", "@@ -1,1 +1,1 @@\n-import os\n+import os  # noqa\n"),
        ["src/app.py"],
        "FLAG silenced: src/app.py:1: import os  # noqa",
    ),
    "loosened": (
        diff(
            "tests/test_app.py",
            "@@ -4,2 +4,1 @@\n     x = app.run()\n-    self.assertEqual(x, 3)\n",
        ),
        ["tests/test_app.py"],
        "FLAG loosened: tests/test_app.py:5: self.assertEqual(x, 3)",
    ),
    "mocked": (
        diff(
            "tests/test_app.py",
            "@@ -1,1 +1,2 @@\n import app\n+from unittest.mock import MagicMock\n",
        ),
        ["tests/test_app.py"],
        "FLAG mocked: tests/test_app.py:2: from unittest.mock import MagicMock",
    ),
}


def scan(args, cwd=None, env=None):
    run = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, check=False, cwd=cwd, env=env,
    )  # fmt: skip
    return run.returncode, run.stdout, run.stderr


class Kinds(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def scan_text(self, text, files):
        path = self.tmp / "change.diff"
        path.write_text(text)
        return scan(["--diff-file", str(path), "--files", *files])

    def test_each_kind_gives_exactly_its_flag(self):
        for kind, (text, files, expected) in KINDS.items():
            with self.subTest(kind=kind):
                code, out, err = self.scan_text(text, files)
                self.assertEqual(out.splitlines(), [expected], err)
                self.assertEqual(code, 1)

    def test_a_deleted_test_file_is_flagged(self):
        text = diff(
            "tests/test_gone.py",
            "@@ -1,2 +0,0 @@\n-def test_a():\n-    pass\n",
            header="deleted file mode 100644\n",
        )
        code, out, _ = self.scan_text(text, ["tests/test_gone.py"])
        self.assertIn("FLAG deleted-test: tests/test_gone.py:0: test file deleted", out)
        self.assertEqual(code, 1)

    def test_a_clean_diff_exits_0_with_no_output(self):
        text = diff("src/app.py", "@@ -1,1 +1,2 @@\n x = 1\n+y = 2\n") + diff(
            "tests/test_app.py",
            "@@ -2,1 +2,3 @@\n def test_x():\n+    assert app.y == 2\n+\n",
        )
        code, out, err = self.scan_text(text, ["src/app.py", "tests/test_app.py"])
        self.assertEqual((code, out, err), (0, "", ""))

    def test_scope_flag_clears_when_its_file_is_allowed(self):
        text = diff("src/app.py", "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n") + diff(
            "docs/extra.md", "@@ -1,1 +1,1 @@\n-a\n+b\n"
        )
        code, out, _ = self.scan_text(text, ["src/app.py"])
        self.assertEqual(
            out.splitlines(), ["FLAG scope: docs/extra.md:0: not in --files"]
        )
        self.assertEqual(code, 1)
        code, out, _ = self.scan_text(text, ["src/app.py", "docs/extra.md"])
        self.assertEqual((code, out), (0, ""))

    def test_a_changed_test_signature_is_not_a_deleted_test(self):
        text = diff(
            "tests/test_app.py",
            "@@ -1,1 +1,1 @@\n-def test_x(self):\n+def test_x(self, tmp):\n",
        )
        code, out, _ = self.scan_text(text, ["tests/test_app.py"])
        self.assertEqual((code, out), (0, ""))

    def test_test_file_names(self):
        # loosened and mocked only count in a test file.
        hunk = "@@ -1,2 +1,2 @@\n-expect(x).toBe(1)\n+jest.mock('x')\n"
        for path in (
            "__tests__/a.js",
            "src/a.test.js",
            "src/a.spec.ts",
            "pkg/a_test.go",
            "test/a.js",
            "src/test_a.py",
        ):
            with self.subTest(path=path):
                _, out, _ = self.scan_text(diff(path, hunk), [path])
                self.assertIn("FLAG loosened:", out)
                self.assertIn("FLAG mocked:", out)
        code, out, _ = self.scan_text(diff("src/a.js", hunk), ["src/a.js"])
        self.assertEqual((code, out), (0, ""))


# Test definitions in other languages. Each fills its %s with more tests, or with nothing.
GO_TESTS = """\
package calc

import "testing"

func TestAdd(t *testing.T) {
    Add(1, 2)
}
%s"""
GO_SUB = """
func TestSub(t *testing.T) {
    Sub(3, 1)
}

func (s *CalcSuite) TestDiv() {
    Div(6, 3)
}
"""
GO_MUL = """
func TestMul(t *testing.T) {
    Mul(2, 3)
}
"""

XCTESTS = """\
import XCTest

final class CalcTests: XCTestCase {
    func testAdd() {
        _ = Calc().add(1, 2)
    }
%s}
"""
XCTEST_SUB = """
    func testSub() throws {
        _ = Calc().sub(3, 1)
    }
"""
XCTEST_HELPER = """
    func testValue(_ x: Int) -> Int {
        x
    }
"""
XCTEST_DIV = """
    func testDiv() {
        _ = Calc().div(6, 3)
    }
"""

JUNIT = """\
import org.junit.jupiter.api.Test;

class CalcTest {
    @Test
    void adds() {
        new Calc().add(1, 2);
    }
%s}
"""
JUNIT_SUB = """
    @Test
    void subtracts() {
        new Calc().sub(3, 1);
    }
"""
SWIFT_TESTING = """\
import Testing

@Test func adds() {
    _ = Calc().add(1, 2)
}

@Test
func subtracts() {
    _ = Calc().sub(3, 1)
}
"""
SWIFT_TESTING_CHANGED = """\
import Testing

@Test("Adds two numbers") func adds() {
    _ = Calc().add(1, 2)
}

@Test(.tags(.fast))
func subtracts() {
    _ = Calc().sub(3, 1)
}

@Test func multiplies() {
    _ = Calc().mul(2, 3)
}
"""

RUST_LIB = """\
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn adds() {
        add(1, 2);
    }
%s}
"""
RUST_AGAIN = """
    #[test]
    fn adds_again() {
        add(2, 2);
    }
"""
RUST_FLAKY = """\
#[test]
fn flaky() {
    run();
}
"""
RUST_NEW = """\
#[test]
fn adds_three() {
    add(1, 2);
}
"""

JS_TESTS = """\
const { add, sub } = require('./calc');

describe('add', () => {
  it('adds', () => {
    add(1, 2);
  });
});
%s"""
JS_SUB = """
describe('sub', () => {
  test('subtracts', () => {
    sub(3, 1);
  });
});
"""
JS_DIV = """
describe('div', () => {
  it('divides', () => {
    div(6, 3);
  });
});
"""
JS_NOT_TESTS = """\
function check(value) {
  describe(value);
  it(value);
  test(value);
}
"""
XCTEST_ASSERT = """\
import XCTest

final class CalcTests: XCTestCase {
    func testAdd() {
        let x = Calc().add(1, 2)
        XCTAssertEqual(x, 3)
    }
}
"""

# Lines that skip a test or silence a linter, a file at a time; and ordinary code that looks like
# them, which must not be flagged.
SKIPS = {
    "src/calc.test.js": [
        "xit('adds', () => {});",
        "xdescribe('calc', () => {});",
        "xtest('subtracts', () => {});",
        "it.todo('multiplies');",
        "test.todo('divides');",
    ],
    "src/test/java/CalcTest.java": [
        '@Disabled("flaky")',
        "@DisabledOnOs(OS.WINDOWS)",
        "@Ignore",
    ],
    "Tests/CalcTests/CalcTests.swift": [
        'throw XCTSkip("not on CI")',
        "try XCTSkipIf(isCI)",
    ],
    "calc_test.go": [
        't.Skipf("flaky: %v", err)',
        "t.SkipNow()",
        'b.Skip("slow")',
    ],
    "test/test_calc.py": [
        "@unittest.expectedFailure",
        'raise unittest.SkipTest("slow")',
        '@pytest.mark.skipif(sys.platform == "win32", reason="posix only")',
    ],
}
NOT_SKIPS = {
    "src/main.js": ["process.exit(1);", "store.todo('milk');"],
    "src/Paging.cs": ["var page = list.Skip(10).Take(5);"],
    "src/User.java": ["@IgnoreExtraProperties", "button.setDisabled(true);"],
    "src/report.py": ["print(result.expectedFailures)", "sys.exit(1)"],
}
SILENCERS = {
    "src/calc.ts": ["// @ts-ignore", "// @ts-expect-error", "// @ts-nocheck"],
    "src/calc.py": [
        "import os  # pylint: disable=unused-import",
        "# pylint: disable-next=invalid-name",
    ],
    "calc.go": ["defer f.Close() //nolint:errcheck", "//nolint"],
    "Sources/Calc/Calc.swift": [
        "// swiftlint:disable force_cast",
        "let n = x as! Int // swiftlint:disable:this force_cast",
    ],
}
NOT_SILENCERS = {
    "Makefile": [
        "lint:",
        "\tpylint src",
        "\tswiftlint lint --strict",
        "\tgolangci-lint run",
    ],
    "src/config.ts": ["const nolinter = true;", "const tsIgnored = 0;"],
}


def git(repo, *args):
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip


def write(repo, files):
    """Write each {path: text} under `repo`; a text of None deletes the file."""
    for path, text in files.items():
        file = repo / path
        if text is None:
            file.unlink()
        else:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(text)


class StagedChanges(unittest.TestCase):
    maxDiff = None  # show every flag when two lists of them differ

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def commit(self, files):
        """A new throwaway repo with `files` committed, and that commit's SHA. Paths in one repo
        must differ in more than case: macOS's file system would put tests/ and Tests/ together."""
        repo = Path(tempfile.mkdtemp(dir=self.tmp))
        git(repo, "init", "-q")
        write(repo, files)
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "--allow-empty", "-m", "base")
        return repo, git(repo, "rev-parse", "HEAD")

    def scan_staged(self, before, after, files=None):
        """Commit `before`, write `after` over it and stage that, then scan it with --base.
        --files is every path named, unless given."""
        repo, base = self.commit(before)
        write(repo, after)
        git(repo, "add", "-A")
        files = list({**before, **after}) if files is None else files
        return scan(["--base", base, "--files", *files], cwd=repo)

    def test_a_base_that_starts_with_a_dash_never_reaches_git(self):
        # --base=--output=FILE made git diff write the staged diff over FILE. The scan then read
        # nothing and exited 0, which reads as clean.
        repo, _ = self.commit({"app.py": "x = 1\n"})
        write(repo, {"app.py": "x = 2  # noqa\n"})
        git(repo, "add", "-A")
        victim = self.tmp / "victim.txt"
        victim.write_text("keep me\n")
        code, out, err = scan([f"--base=--output={victim}"], cwd=repo)
        self.assertEqual((code, out), (2, ""), err)
        self.assertIn("not a revision", err)
        self.assertEqual(victim.read_text(), "keep me\n")

    def test_base_must_name_a_commit(self):
        repo, base = self.commit({"app.py": "x = 1\n"})
        write(repo, {"app.py": "x = 2  # noqa\n"})
        git(repo, "add", "-A")
        tree = git(repo, "rev-parse", "HEAD^{tree}")
        for rev in (tree, "no-such-rev", "HEAD..HEAD"):
            with self.subTest(rev=rev):
                code, out, err = scan(["--base", rev], cwd=repo)
                self.assertEqual((code, out), (2, ""), err)
                self.assertIn("is not a commit", err)
        # Any name for a commit still works.
        for rev in (base, base[:12], "HEAD", "HEAD~0"):
            with self.subTest(rev=rev):
                code, out, err = scan(["--base", rev], cwd=repo)
                self.assertEqual(
                    (code, out), (1, "FLAG silenced: app.py:1: x = 2  # noqa\n"), err
                )

    def test_more_test_file_layouts(self):
        # Swift's Tests/ (a folder name matches in any case), Ruby's spec/ and *_spec.rb, Django's
        # tests.py and pytest's conftest.py; and names that only look like them.
        tests = [
            "Tests/CalcTests/CalcTests.swift",
            "spec/calc_spec.rb",
            "lib/calc_spec.rb",
            "app/tests.py",
            "conftest.py",
        ]
        others = [
            "Sources/Latest/Calc.swift",
            "docs/specs/plan.md",
            "lib/inspect.rb",
            "app/contests.py",
            "src/conftest_data.py",
        ]
        code, out, err = self.scan_staged(
            {path: "x\n" for path in tests + others},
            {path: None for path in tests + others},
        )
        self.assertEqual(
            sorted(out.splitlines()),
            sorted(f"FLAG deleted-test: {path}:0: test file deleted" for path in tests),
            err,
        )
        self.assertEqual(code, 1)

    def test_go_tests(self):
        # A suite's method counts too. A new test, or a changed body, isn't a deletion.
        code, out, err = self.scan_staged(
            {"sub_test.go": GO_TESTS % GO_SUB, "add_test.go": GO_TESTS % ""},
            {
                "sub_test.go": GO_TESTS % "",
                "add_test.go": (GO_TESTS % GO_MUL).replace("Add(1, 2)", "Add(2, 2)"),
            },
        )
        self.assertEqual(
            (code, out.splitlines()),
            (1, [
                "FLAG deleted-test: sub_test.go:9: func TestSub(t *testing.T) {",
                "FLAG deleted-test: sub_test.go:13: func (s *CalcSuite) TestDiv() {",
            ]),
            err,
        )  # fmt: skip

    def test_swift_xctest_tests(self):
        # XCTest only runs a testX() with no arguments, so a helper that takes one isn't a test.
        # A test made async isn't a deletion.
        code, out, err = self.scan_staged(
            {
                "Tests/CalcTests/CalcTests.swift": XCTESTS % XCTEST_SUB,
                "Tests/CalcTests/MoreTests.swift": XCTESTS % XCTEST_HELPER,
            },
            {
                "Tests/CalcTests/CalcTests.swift": XCTESTS % "",
                "Tests/CalcTests/MoreTests.swift": (XCTESTS % XCTEST_DIV).replace(
                    "func testAdd() {", "func testAdd() async throws {"
                ),
            },
        )
        self.assertEqual(
            (code, out.splitlines()),
            (1, ["FLAG deleted-test: Tests/CalcTests/CalcTests.swift:8: func testSub() throws {"]),
            err,
        )  # fmt: skip

    def test_test_attributes(self):
        # @Test (JUnit, Swift Testing) marks the function on its line or below, so giving a test a
        # display name or a trait isn't a deletion.
        code, out, err = self.scan_staged(
            {
                "src/test/java/CalcTest.java": JUNIT % JUNIT_SUB,
                "Tests/CalcTests/CalcTesting.swift": SWIFT_TESTING,
            },
            {
                "src/test/java/CalcTest.java": JUNIT % "",
                "Tests/CalcTests/CalcTesting.swift": SWIFT_TESTING_CHANGED,
            },
        )
        self.assertEqual(
            (code, out.splitlines()),
            (1, ["FLAG deleted-test: src/test/java/CalcTest.java:9: @Test"]),
            err,
        )

    def test_rust_tests(self):
        # Rust's unit tests live in its source files. Taking #[test] off a function stops it being
        # a test; adding a new one isn't a deletion.
        code, out, err = self.scan_staged(
            {"src/lib.rs": RUST_LIB % RUST_AGAIN, "src/flaky.rs": RUST_FLAKY},
            {
                "src/lib.rs": RUST_LIB % "",
                "src/flaky.rs": RUST_FLAKY.replace("#[test]\n", ""),
                "src/more.rs": RUST_NEW,
            },
        )
        self.assertEqual(
            (code, out.splitlines()),
            (1, [
                "FLAG deleted-test: src/flaky.rs:1: #[test]",
                "FLAG deleted-test: src/lib.rs:14: #[test]",
            ]),
            err,
        )  # fmt: skip

    def test_js_describe_it_and_test_blocks(self):
        # Only in a test file: elsewhere describe(, it( and test( are ordinary calls. A new block
        # isn't a deletion.
        code, out, err = self.scan_staged(
            {
                "src/calc.test.js": JS_TESTS % JS_SUB,
                "src/more.test.js": JS_TESTS % "",
                "src/rules.js": JS_NOT_TESTS,
            },
            {
                "src/calc.test.js": JS_TESTS % "",
                "src/more.test.js": (JS_TESTS % JS_DIV).replace(
                    "add(1, 2)", "add(2, 1)"
                ),
                "src/rules.js": "function check(value) {\n  return value;\n}\n",
            },
        )
        self.assertEqual(
            (code, out.splitlines()),
            (1, [
                "FLAG deleted-test: src/calc.test.js:9: describe('sub', () => {",
                "FLAG deleted-test: src/calc.test.js:10: test('subtracts', () => {",
            ]),
            err,
        )  # fmt: skip

    def scan_added_lines(self, flagged, unflagged, kind):
        """Stage each {path: lines} as a new file, and check that each line of `flagged`, and
        nothing else, gets a `kind` flag."""
        files = {**flagged, **unflagged}
        code, out, err = self.scan_staged(
            {},
            {
                path: "".join(f"{line}\n" for line in lines)
                for path, lines in files.items()
            },
        )
        expected = [
            f"FLAG {kind}: {path}:{n}: {line.strip()}"
            for path, lines in flagged.items()
            for n, line in enumerate(lines, 1)
        ]
        self.assertEqual(sorted(out.splitlines()), sorted(expected), err)
        self.assertEqual(code, 1)

    def test_more_ways_to_skip_a_test(self):
        self.scan_added_lines(SKIPS, NOT_SKIPS, "skip")

    def test_more_ways_to_silence_a_linter(self):
        self.scan_added_lines(SILENCERS, NOT_SILENCERS, "silenced")

    def test_xctassert_is_an_assertion(self):
        # Dropping an XCTAssert loosens a test; changing one doesn't.
        code, out, err = self.scan_staged(
            {
                "tests/LooseTests.swift": XCTEST_ASSERT,
                "tests/KeptTests.swift": XCTEST_ASSERT,
            },
            {
                "tests/LooseTests.swift": XCTEST_ASSERT.replace(
                    "XCTAssertEqual(x, 3)\n", ""
                ),
                "tests/KeptTests.swift": XCTEST_ASSERT.replace(
                    "(x, 3)", '(x, 3, "adds")'
                ),
            },
        )
        self.assertEqual(
            (code, out.splitlines()),
            (1, ["FLAG loosened: tests/LooseTests.swift:6: XCTAssertEqual(x, 3)"]),
            err,
        )

    def test_base_reads_staged_changes_including_a_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-q")
            (repo / "app.py").write_text("x = 1\n")
            git(repo, "add", ".")
            git(repo, "commit", "-qm", "init")
            base = git(repo, "rev-parse", "HEAD")
            (repo / "app.py").write_text("x = 2  # noqa\n")
            (repo / "new.py").write_text("y = 1\n")
            (repo / "unstaged.py").write_text("z = 1\n")  # never staged, so never seen
            git(repo, "add", "app.py", "new.py")
            code, out, err = scan(["--base", base, "--files", "app.py"], cwd=repo)
            self.assertEqual(
                out.splitlines(),
                [
                    "FLAG silenced: app.py:1: x = 2  # noqa",
                    "FLAG scope: new.py:0: not in --files",
                ],
                err,
            )
            self.assertEqual(code, 1)
            code, out, _ = scan(
                ["--base", base, "--files", "app.py", "new.py"], cwd=repo
            )
            self.assertEqual(
                out.splitlines(), ["FLAG silenced: app.py:1: x = 2  # noqa"]
            )


if __name__ == "__main__":
    unittest.main()

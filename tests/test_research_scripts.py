"""Tests for the research scripts that run outside the agents' sandbox: repo-health.sh,
reddit-search.sh and gcp-skus.sh. They must say plainly when they can't work (a missing tool, gh
logged out, an API error), not report a false fact such as "not found".

Stubs for gh, curl and gcloud go first on a PATH that otherwise holds only the system tools and
jq, so nothing reaches the network. Run with:
python3 -m unittest discover -s ~/code/github.com/claude-skills/tests
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "research" / "scripts"

META = {
    "stargazerCount": 42,
    "isArchived": False,
    "licenseInfo": {"spdxId": "MIT"},
    "issues": {"totalCount": 1},
    "pullRequests": {"totalCount": 2},
    "latestRelease": {"publishedAt": "2099-01-01T00:00:00Z"},
    "releases": {"nodes": []},
    "refs": {"nodes": []},
    "defaultBranchRef": {"target": {"history": {"totalCount": 5}}},
}
HISTORY = {
    "pageInfo": {"hasNextPage": False, "endCursor": None},
    "nodes": [
        {
            "committedDate": "2099-01-01T00:00:00Z",
            "author": {"name": n, "user": {"login": n}},
        }
        for n in ("a", "b", "c")
    ],
}
# A stub gh: `auth status` exits GH_AUTH (0 by default); `api graphql` answers per GH_MODE.
GH = """#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
mode = os.environ.get("GH_MODE", "ok")
if args[:2] == ["auth", "status"]:
    sys.exit(int(os.environ.get("GH_AUTH", "0")))
if args[:2] == ["api", "graphql"]:
    query = next(a for a in args if a.startswith("query="))
    if mode == "missing":
        print(json.dumps({"data": {"repository": None}, "errors": [{"type": "NOT_FOUND",
              "message": "Could not resolve to a Repository"}]}))
        sys.exit(1)
    if mode == "error":
        print("gh: API rate limit exceeded", file=sys.stderr)
        sys.exit(1)
    if "stargazerCount" in query:
        print(json.dumps({"data": {"repository": json.loads(%(meta)r)}}))
    else:
        print(json.dumps({"data": {"repository": {"defaultBranchRef": {"target": {"history": json.loads(%(hist)r)}}}}}))
    sys.exit(0)
if args[:1] == ["api"]:
    print("a\\nb\\nc")
    sys.exit(0)
sys.exit(3)
""" % {"meta": json.dumps(META), "hist": json.dumps(HISTORY)}


class Scripts(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        jq = shutil.which("jq")
        if not jq:
            self.skipTest("jq isn't installed")
        (self.bin / "jq").symlink_to(jq)
        self.env = {**os.environ, "PATH": f"{self.bin}:/usr/bin:/bin"}

    def stub(self, name, text):
        (self.bin / name).write_text(text)
        (self.bin / name).chmod(0o755)

    def run_script(self, name, *args, **env):
        run = subprocess.run(
            [str(SCRIPTS / name), *args],
            capture_output=True, text=True, check=False, env={**self.env, **env},
        )  # fmt: skip
        return run.returncode, run.stdout, run.stderr


class RepoHealth(Scripts):
    def test_without_gh_it_says_so(self):
        code, out, err = self.run_script("repo-health.sh", "cli/cli")
        self.assertEqual(code, 1, out + err)
        self.assertIn("needs gh and jq", err)
        self.assertNotIn("not found", out)

    def test_logged_out_gh_says_so(self):
        self.stub("gh", GH)
        code, out, err = self.run_script("repo-health.sh", "cli/cli", GH_AUTH="1")
        self.assertEqual(code, 1, out + err)
        self.assertIn("isn't logged in", err)
        # Run in a call with another command, the sandbox hides gh's login too; the message says so.
        self.assertIn("run this script on its own", err)

    def test_missing_repo_is_not_found(self):
        self.stub("gh", GH)
        code, out, err = self.run_script("repo-health.sh", "o/gone", GH_MODE="missing")
        self.assertIn("| o/gone | not found or no access |", out)
        self.assertEqual(code, 1, out + err)  # every row failed

    def test_api_error_is_not_reported_as_not_found(self):
        self.stub("gh", GH)
        code, out, err = self.run_script("repo-health.sh", "o/r", GH_MODE="error")
        self.assertIn("| o/r | API error:", out)
        self.assertIn("rate limit", out)
        self.assertNotIn("not found", out)
        self.assertEqual(code, 1, out + err)

    def test_a_repo_that_answers(self):
        self.stub("gh", GH)
        code, out, err = self.run_script(
            "repo-health.sh", "o/r", "o/s", "o/t", "o/u", "o/v"
        )
        self.assertEqual(code, 0, out + err)
        rows = [l for l in out.splitlines() if l.startswith("| o/")]
        self.assertEqual(
            [r.split(" | ")[0] for r in rows],
            ["| o/r", "| o/s", "| o/t", "| o/u", "| o/v"],
        )
        self.assertIn("| 42 |", rows[0])


class RedditSearch(Scripts):
    def test_without_jq_it_says_so(self):
        # macOS has its own /usr/bin/jq, so the PATH here holds only bash, env and curl.
        bare = self.tmp / "bare"
        bare.mkdir()
        for tool in ("bash", "env", "curl"):
            (bare / tool).symlink_to(shutil.which(tool))
        code, out, err = self.run_script("reddit-search.sh", "rightsizing", PATH=str(bare))
        self.assertEqual(code, 1, out + err)
        self.assertIn("Reddit unavailable: needs jq and curl", out)


class GcpSkus(Scripts):
    def test_without_gcloud_it_says_so(self):
        code, out, err = self.run_script("gcp-skus.sh", "--services", "Compute")
        self.assertEqual(code, 1, out + err)
        self.assertIn("needs gcloud, curl and jq", err)

    def test_page_token_is_url_encoded(self):
        self.stub("gcloud", "#!/bin/sh\necho token\n")
        # A stub curl: the first page hands back a token with URL-special characters.
        self.stub(
            "curl",
            f"""#!/usr/bin/env python3
import json, sys
url = sys.argv[-1]
with open("{self.tmp}/urls", "a") as f:
    f.write(url + "\\n")
page = {{"services": [{{"serviceId": "6F81-5844-456A", "displayName": "Compute Engine"}}]}}
if "pageToken" not in url:
    page["nextPageToken"] = "a+b/c=&d"
print(json.dumps(page))
""",
        )
        code, out, err = self.run_script("gcp-skus.sh", "--services", "Compute")
        self.assertEqual(code, 0, out + err)
        urls = (self.tmp / "urls").read_text().splitlines()
        self.assertEqual(len(urls), 2)
        self.assertTrue(urls[1].endswith("&pageToken=a%2Bb%2Fc%3D%26d"), urls[1])


if __name__ == "__main__":
    unittest.main()

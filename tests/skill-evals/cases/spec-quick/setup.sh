#!/usr/bin/env bash
# Builds the fixture repo for the spec-quick case in $1, which the runner makes under ~/code
# (location.txt), since /spec works only in a repo there: a small CLI with one test.
set -euo pipefail
cd "$1"
g() { git -c user.email=eval@local -c user.name=eval "$@"; }
git init -q
cat > greet.py <<'PY'
"""Prints a greeting."""

import argparse


def greeting(name: str) -> str:
    """Return the greeting for name."""
    return f"Hello, {name}!"


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    args = parser.parse_args(argv)
    print(greeting(args.name))


if __name__ == "__main__":
    main()
PY
cat > test_greet.py <<'PY'
import unittest

from greet import greeting


class Greeting(unittest.TestCase):
    def test_greeting(self):
        self.assertEqual(greeting("Ada"), "Hello, Ada!")


if __name__ == "__main__":
    unittest.main()
PY
cat > README.md <<'MD'
# greet

`python3 greet.py <name>` prints a greeting. Run the tests with `python3 -m unittest`.
MD
g add . && g commit -qm "feat: greet"
echo "head=$(git rev-parse --short HEAD)" > .git/eval-hashes

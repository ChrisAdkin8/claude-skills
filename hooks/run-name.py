#!/usr/bin/env python3
"""The safe name for a repo folder or a document's basename, for the names the skills build from
it: run dirs, /implement's worktree folder, branch and verifier scratch folder, and the spikes'
scratch folders. The launchers take only names matching [A-Za-z0-9][A-Za-z0-9._-]*, which keeps
their paths inside their folders, so a name like `Design Notes` or `café` is mapped instead.

Usage: run-name.py <name>

Prints the name unchanged if it already fits that pattern. Otherwise it normalises it to Unicode
NFC, so `café` stored composed or decomposed gives one name, folds accents to ASCII, turns each
run of other characters into `-`, drops leading punctuation, and adds `-` and the first 6 hex
digits of the SHA-1 of the NFC form's UTF-8, so two different names almost never share one. A
name with no ASCII letter or digit left, such as `日本` or `___`, gets `x` before the hash.

`Design Notes` gives `Design-Notes-<hash>`, which differs from `Design-Notes`, printed as it is.
Run with no network and no files: it reads only its argument.
"""

import hashlib
import re
import sys
import unicodedata

FITS = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def run_name(name):
    if FITS.fullmatch(name):
        return name
    nfc = unicodedata.normalize("NFC", name)
    # NFKD splits an accented letter into the letter and its accent, which ASCII then drops.
    folded = (
        unicodedata.normalize("NFKD", nfc).encode("ascii", "ignore").decode("ascii")
    )
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", folded).lstrip("._-")
    digest = hashlib.sha1(nfc.encode("utf-8")).hexdigest()[:6]
    return f"{safe or 'x'}-{digest}"


def main(argv):
    if len(argv) != 1:
        print("usage: run-name.py <name>", file=sys.stderr)
        return 2
    print(run_name(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

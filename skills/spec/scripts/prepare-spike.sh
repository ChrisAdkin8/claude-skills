#!/usr/bin/env bash
# Prepares one /spec spike's scratch directory: clears it, then exports the source repo as it was
# at read-at into its src/. Step 7b of skills/spec/SKILL.md runs this before run-spike.sh.
#
# Usage: prepare-spike.sh <scratch dir> <source repo | none> <read-at | none>
#
# A script, not pre-approved `rm -rf`, `git archive` and `tar` shapes, because a `*` in a
# permission rule matches anything, spaces included: `Bash(rm -rf ~/.cache/spec-spikes/*)` also
# approved `rm -rf ~/.cache/spec-spikes/x ~/code`, and `Bash(git -C * archive *)` approved
# `git archive --output=<any file>`. Here the paths are checked before anything is deleted.
set -euo pipefail

die() { echo "prepare-spike: $*" >&2; exit 2; }

# Writes the files of commit $1 into the new directory $2, byte for byte as git stores them. Not
# `git archive`: it applies .gitattributes, so export-ignore leaves paths out (often tests/),
# export-subst, eol and ident rewrite files, and the repo's filter drivers run as it goes. Not a
# checkout from a temporary index either: even with --attr-source, that still reads
# .git/info/attributes and runs the filters it names. `git ls-tree` and `git cat-file --batch`
# read no attributes and run no filter, so nothing of the repo's runs here. An executable stays
# one and a link stays a link. A submodule's files aren't in this repo, so it gets an empty
# directory, as in a clone. Every directory is made before any link, so nothing is written
# through one, and a path with an empty, `.`, `..` or `.git` part is refused. GIT_NO_LAZY_FETCH:
# a missing object fails the export rather than being fetched. prepare-verify.sh in
# skills/implement/scripts has the same function; change both.
export_tree() {
  GIT_NO_LAZY_FETCH=1 python3 - "$top" "$1" "$2" <<'PY' || die "couldn't export $1 to $2"
import os
import subprocess
import sys

top, rev, dest = sys.argv[1:]
git = ["git", "-C", top]
tree = subprocess.run([*git, "ls-tree", "-r", "-z", rev], stdout=subprocess.PIPE, check=True).stdout
cat = subprocess.Popen([*git, "cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
links = []
for entry in filter(None, tree.split(b"\0")):
    meta, path = entry.split(b"\t", 1)
    mode, kind, oid = meta.split()
    if any(part in (b"", b".", b"..") or part.lower() == b".git" for part in path.split(b"/")):
        sys.exit(f"refusing {path!r}: a path git itself wouldn't check out")
    out = os.path.join(os.fsencode(dest), path)
    if kind == b"commit":
        os.makedirs(out, exist_ok=True)
        continue
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cat.stdin.write(oid + b"\n")
    cat.stdin.flush()
    header = cat.stdout.readline().split()
    if header[1:2] != [b"blob"]:
        sys.exit(f"{path!r}: no blob {oid.decode()} in this repo")
    data = cat.stdout.read(int(header[2]) + 1)[:-1]
    if mode == b"120000":
        links.append((path, data, out))
        continue
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    with open(os.open(out, flags, 0o755 if mode == b"100755" else 0o644), "wb") as f:
        f.write(data)
for path, target, out in links:
    try:
        os.symlink(target, out)
    except FileExistsError:
        sys.exit(f"refusing {path!r}: a link where the tree also has a file or directory")
cat.stdin.close()
sys.exit(cat.wait())
PY
}

[ $# -eq 3 ] || die "usage: prepare-spike.sh <scratch dir> <source repo | none> <read-at | none>"
scratch=$1 repo=$2 read_at=$3
root="$HOME/.cache/spec-spikes"
name='[A-Za-z0-9][A-Za-z0-9._-]*'

# <root>/<repo dir name>/<spec basename>/S<n>, each name as hooks/run-name.py prints it, and nothing
# else: no `..`, no extra levels.
if ! [[ $scratch =~ ^$root/$name/$name/S[0-9]+$ ]]; then
  bad=
  [[ $scratch != "$root"/* ]] || bad=$(tr / '\n' <<< "${scratch#"$root"/}" | grep -v '^$' | grep -Evx "$name" | head -n 1 || true)
  [ -z "$bad" ] || bad=": \"$bad\" isn't a valid name: a name may hold only letters, digits, ., _ and -, starting with a letter or digit"
  die "scratch must be ~/.cache/spec-spikes/<repo>/<spec>/S<n>, not $scratch$bad"
fi
if [ "$read_at" = none ]; then
  [ "$repo" = none ] || die "read-at is none, so the source repo must be none too"
else
  [[ $read_at =~ ^[0-9a-f]{7,40}$ ]] || die "read-at must be a short or full commit hash: $read_at"
  top=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null) || die "not a git repo: $repo"
  git -C "$top" rev-parse --verify --quiet "$read_at^{commit}" >/dev/null ||
    die "$read_at is not a commit in $top"
fi

# A symlink on the way down could point the delete somewhere else: resolve the parent first.
mkdir -p "$root" "$(dirname "$scratch")"
real_root=$(cd "$root" && pwd -P)
real_parent=$(cd "$(dirname "$scratch")" && pwd -P)
case "$real_parent/" in
  "$real_root"/?*/?*/) ;;
  *) die "$(dirname "$scratch") resolves to $real_parent, outside $real_root" ;;
esac
[ ! -L "$scratch" ] || die "$scratch is a symlink"

target="$real_parent/$(basename "$scratch")"
rm -rf "$target"
mkdir -p "$target"
if [ "$read_at" != none ]; then
  mkdir "$target/src"
  export_tree "$read_at" "$target/src"
  echo "exported $top at $read_at to $target/src"
else
  echo "cleared $target (read-at none: no code to export)"
fi

#!/usr/bin/env bash
# Prepares one implement-verifier run's scratch directory: clears it, exports the implementation
# at <head> into src/, and writes diff.patch (git diff <base> <head>). Then, for each commit in
# <base>..<head>, oldest first: if its subject ends `(W<n>)`, it adds the commit's diff to
# diff-W<n>.patch, and exports its parent into before/W<n>/ (the code as it stood before that
# work item, for a Done when's "fails before" half); any other commit's diff goes to
# diff-other.patch (the spec's status edit, the clean-up, a fix after verification, a revert).
# Each commit's diff there starts with a `commit <hash> <subject>` line. The caller then copies in
# spec.md, record.md and brief.md, and launches run-verify.sh.
#
# Usage: prepare-verify.sh <scratch dir> <repo> <base> <head>
#
#   <scratch dir>  ~/.cache/implement-verify/<repo>/<spec basename>/V<n>, and nothing else
#   <base>         the commit the implementation started from
#   <head>         the implementation's last commit
#
# A work item with more than one `(W<n>)` commit gets the parent of its first. A script, not
# pre-approved `rm -rf` and `git` shapes, for the reason prepare-spike.sh gives: the paths are
# checked before anything is deleted, and the revisions before git sees them.
set -euo pipefail

die() { echo "prepare-verify: $*" >&2; exit 2; }

# Writes the files of commit $1 into the new directory $2, byte for byte as git stores them. Not
# `git archive`: it applies .gitattributes, so export-ignore leaves paths out (often tests/),
# export-subst, eol and ident rewrite files, and the repo's filter drivers run as it goes. Not a
# checkout from a temporary index either: even with --attr-source, that still reads
# .git/info/attributes and runs the filters it names. `git ls-tree` and `git cat-file --batch`
# read no attributes and run no filter, so nothing of the repo's runs here. An executable stays
# one and a link stays a link. A submodule's files aren't in this repo, so it gets an empty
# directory, as in a clone. Every directory is made before any link, so nothing is written
# through one, and a path with an empty, `.`, `..` or `.git` part is refused. GIT_NO_LAZY_FETCH:
# a missing object fails the export rather than being fetched. prepare-spike.sh has the same
# function; change both.
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

# Text, whatever the attributes say (`-diff` or `binary` would hide a change), and none of the
# repo's diff programs: no external diff, no textconv.
diff_of() { git -C "$top" diff --no-color --no-ext-diff --no-textconv --text "$@"; }

[ $# -eq 4 ] || die "usage: prepare-verify.sh <scratch dir> <repo> <base> <head>"
scratch=$1 repo=$2 base=$3 head=$4
root="$HOME/.cache/implement-verify"
name='[A-Za-z0-9][A-Za-z0-9._-]*'

# <root>/<repo dir name>/<spec basename>/V<n>: no `..`, no extra levels.
[[ $scratch =~ ^$root/$name/$name/V[0-9]+$ ]] ||
  die "scratch must be ~/.cache/implement-verify/<repo>/<spec>/V<n>, not $scratch"
top=$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null) || die "not a git repo: $repo"
# A revision that starts with `-` would reach git as an option.
for rev in "$base" "$head"; do
  [[ $rev =~ ^[A-Za-z0-9][A-Za-z0-9._/~^-]*$ ]] || die "not a revision: $rev"
done
base=$(git -C "$top" rev-parse --verify --quiet "$base^{commit}") || die "$3 is not a commit in $top"
head=$(git -C "$top" rev-parse --verify --quiet "$head^{commit}") || die "$4 is not a commit in $top"

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
mkdir -p "$target/src"
export_tree "$head" "$target/src"
diff_of "$base" "$head" > "$target/diff.patch"
echo "exported $top at $head to $target/src, and git diff $base $head to $target/diff.patch"

# Oldest first, so a work item's first commit decides its starting state. The verifier judges a
# work item's scope on its own diff: the whole diff also holds the spec's status edit, the record
# and the clean-up, which no work item's Files list. --no-show-signature, so a user's
# log.showSignature adds no lines to read here.
git -C "$top" log --no-show-signature --reverse --format='%H %s' "$base..$head" |
  while read -r sha subject; do
    if [[ $subject =~ \(W([0-9]+)\)$ ]]; then
      item="W${BASH_REMATCH[1]}"
      patch="$target/diff-$item.patch"
      if [ ! -e "$target/before/$item" ]; then
        mkdir -p "$target/before/$item"
        export_tree "$sha^" "$target/before/$item"
        echo "exported $item's starting state ($sha^) to $target/before/$item"
      fi
    else
      patch="$target/diff-other.patch"
    fi
    { printf 'commit %s %s\n' "$sha" "$subject"; diff_of "$sha^" "$sha"; } >> "$patch"
  done
echo "wrote each work item's own commits to diff-W<n>.patch, and the rest to diff-other.patch"

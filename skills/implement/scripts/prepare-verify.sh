#!/usr/bin/env bash
# Prepares one implement-verifier run's scratch directory: clears it, exports the implementation
# at <head> into src/, writes diff.patch (git diff <base> <head>), and, for each commit in
# <base>..<head> whose subject ends `(W<n>)`, exports that commit's parent into before/W<n>/: the
# code as it stood before that work item, for a Done when's "fails before" half. The caller then
# copies in spec.md, record.md and brief.md, and launches run-verify.sh.
#
# Usage: prepare-verify.sh <scratch dir> <repo> <base> <head>
#
#   <scratch dir>  ~/.cache/implement-verify/<repo>/<spec basename>/V<n>, and nothing else
#   <base>         the commit the implementation started from
#   <head>         the implementation's last commit
#
# A work item with more than one `(W<n>)` commit gets the parent of its first. A script, not
# pre-approved `rm -rf`, `git archive` and `tar` shapes, for the reason prepare-spike.sh gives: the
# paths are checked before anything is deleted, and the revisions before git sees them.
set -euo pipefail

die() { echo "prepare-verify: $*" >&2; exit 2; }

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
git -C "$top" archive "$head" | tar -x -C "$target/src"
git -C "$top" diff --no-color --no-ext-diff "$base" "$head" > "$target/diff.patch"
echo "exported $top at $head to $target/src, and git diff $base $head to $target/diff.patch"

# Oldest first, so a work item's first commit decides its starting state.
git -C "$top" log --reverse --format='%H %s' "$base..$head" | while read -r sha subject; do
  [[ $subject =~ \(W([0-9]+)\)$ ]] || continue
  item="W${BASH_REMATCH[1]}"
  [ ! -e "$target/before/$item" ] || continue
  mkdir -p "$target/before/$item"
  git -C "$top" archive "$sha^" | tar -x -C "$target/before/$item"
  echo "exported $item's starting state ($sha^) to $target/before/$item"
done

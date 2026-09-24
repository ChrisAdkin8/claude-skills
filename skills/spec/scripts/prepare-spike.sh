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

[ $# -eq 3 ] || die "usage: prepare-spike.sh <scratch dir> <source repo | none> <read-at | none>"
scratch=$1 repo=$2 read_at=$3
root="$HOME/.cache/spec-spikes"
name='[A-Za-z0-9][A-Za-z0-9._-]*'

# <root>/<repo dir name>/<spec basename>/S<n>, and nothing else: no `..`, no extra levels.
[[ $scratch =~ ^$root/$name/$name/S[0-9]+$ ]] ||
  die "scratch must be ~/.cache/spec-spikes/<repo>/<spec>/S<n>, not $scratch"
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
  git -C "$top" archive "$read_at" | tar -x -C "$target/src"
  echo "exported $top at $read_at to $target/src"
else
  echo "cleared $target (read-at none: no code to export)"
fi

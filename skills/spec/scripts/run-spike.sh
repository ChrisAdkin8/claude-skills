#!/usr/bin/env bash
# Runs one /spec spike: a sandboxed, cost-capped headless claude session in the spike's scratch
# directory, primed with spiker.md. Step 7b of skills/spec/SKILL.md writes brief.md, spec.md and
# settings.json there first, and launches this in the background, one call per spike.
#
# Usage: run-spike.sh <scratch dir under ~/.cache/spec-spikes/>
# Writes run.json (the --output-format json result) and run.err in the scratch dir. The spiker
# writes results.md. A wrapper, not a bare `cd <scratch> && claude -p …`, because the permission
# check won't pre-approve that compound command from allowed-tools (spike 2).
#
# Exit 2: the run couldn't start. Exit 4: the spike left results.md, run.json or run.err as a
# symlink, or as anything else but a regular file. /spec's own session, which no sandbox limits,
# reads those files, so the script removes the entry unread, and /spec records the spike as
# BLOCKED. Any other exit is claude's own, with run.err saying why when it isn't 0.
set -euo pipefail

die() { echo "run-spike: $*" >&2; exit 2; }

[ $# -eq 1 ] || die "usage: run-spike.sh <scratch dir>"
# Both sides resolved, so a symlinked home still matches. The layout is prepare-spike.sh's:
# <root>/<repo dir name>/<spec basename>/S<n>, so not the root itself or its .uv-cache.
root=$(cd "$HOME/.cache/spec-spikes" 2>/dev/null && pwd -P) || die "no ~/.cache/spec-spikes"
scratch=$(cd "$1" 2>/dev/null && pwd -P) || die "no such scratch dir: $1"
name='[A-Za-z0-9][A-Za-z0-9._-]*'
case "$scratch" in
  "$root"/*) [[ ${scratch#"$root"/} =~ ^$name/$name/S[0-9]+$ ]] ||
    die "scratch must be ~/.cache/spec-spikes/<repo>/<spec>/S<n>, not $1" ;;
  *) die "not under ~/.cache/spec-spikes/: $1" ;;
esac
for f in brief.md settings.json; do
  [ -f "$scratch/$f" ] || die "missing $scratch/$f"
done

# Spikes get their own uv cache. The user's ~/.cache/uv holds the unpacked packages every real
# `uv sync` links from, and uv doesn't re-check them, so a spike that could write there could
# change code outside the sandbox. This cache is shared by spikes only; a spike that needs a
# package it doesn't hold yet lists pypi.org and files.pythonhosted.org in its Box hosts.
export UV_CACHE_DIR="$HOME/.cache/spec-spikes/.uv-cache"
mkdir -p "$UV_CACHE_DIR"
# No auto memory, as in hooks/run-agent.sh: a spike works from its brief alone.
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1

# --setting-sources user, as in hooks/run-agent.sh: a spike starts in its scratch dir, which has
# no .claude/ of its own, but the flag keeps any project settings or CLAUDE.md above or beside it
# from loading. The spike's own settings.json still applies through --settings.
# The spiker prompt sits beside this script's directory, wherever the skill is installed.
spiker=$(cd "$(dirname "$0")/.." && pwd -P)/spiker.md
cd "$scratch"
# The redirects below would follow a link that an earlier, refused run left and couldn't remove,
# and /spec reads any results.md here as this run's. As in run-verify.sh.
rm -rf -- results.md run.json run.err 2>/dev/null || true
for f in results.md run.json run.err; do
  [ ! -e "$f" ] && [ ! -L "$f" ] || die "couldn't clear $scratch/$f from an earlier run"
done
status=0
claude -p --model sonnet --setting-sources user \
  --append-system-prompt-file "$spiker" \
  --settings settings.json \
  --allowedTools "Read Grep Glob Bash Write(./**) Edit(./**)" \
  --max-budget-usd 2 --max-turns 60 \
  --output-format json --strict-mcp-config --no-session-persistence \
  -- "$(cat brief.md)" < /dev/null > run.json 2> run.err || status=$?

# The spike may write anything in its scratch dir, links included: the sandbox stops it reading
# ~/.ssh, but not linking to it. /spec's own session then reads these three files and copies
# results.md into a committed file, so each must be a regular file. Anything else is removed (a
# link, not what it points to) before something downstream follows it. Its target isn't printed:
# the spike chose it, and this output reaches /spec's session.
refused=0
for f in results.md run.json run.err; do
  if [ -L "$f" ]; then
    what="a symlink"
  elif [ -e "$f" ] && [ ! -f "$f" ]; then
    what="not a regular file"
  else
    continue
  fi
  refused=1
  # rm's own errors stay quiet: inside a directory, they would print names the spike chose.
  if rm -rf -- "$f" 2>/dev/null; then
    echo "run-spike: $scratch/$f was $what; removed it unread" >&2
  else
    echo "run-spike: $scratch/$f was $what; couldn't remove it, so don't read it" >&2
  fi
done
if [ "$refused" -eq 1 ]; then
  echo "run-spike: exit 4: record this spike as BLOCKED, and read none of its files" >&2
  exit 4
fi
exit "$status"

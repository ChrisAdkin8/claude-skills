#!/usr/bin/env bash
# Runs one /spec spike: a sandboxed, cost-capped headless claude session in the spike's scratch
# directory, primed with spiker.md. Step 7b of skills/spec/SKILL.md writes brief.md, spec.md and
# settings.json there first, and launches this in the background, one call per spike.
#
# Usage: run-spike.sh <scratch dir under ~/.cache/spec-spikes/>
# Writes run.json (the --output-format json result) and run.err in the scratch dir. The spiker
# writes results.md. A wrapper, not a bare `cd <scratch> && claude -p …`, because the permission
# check won't pre-approve that compound command from allowed-tools (spike 2).
set -euo pipefail

[ $# -eq 1 ] || { echo "usage: run-spike.sh <scratch dir>" >&2; exit 2; }
scratch=$(cd "$1" && pwd -P)
case "$scratch/" in
  "$HOME/.cache/spec-spikes/"*) ;;
  *) echo "not under ~/.cache/spec-spikes/: $1" >&2; exit 2 ;;
esac
for f in brief.md settings.json; do
  [ -f "$scratch/$f" ] || { echo "missing $scratch/$f" >&2; exit 2; }
done

cd "$scratch"
exec claude -p --model sonnet \
  --append-system-prompt-file "$HOME/.claude/skills/spec/spiker.md" \
  --settings settings.json \
  --allowedTools "Read Grep Glob Bash Write(./**) Edit(./**)" \
  --max-budget-usd 2 --max-turns 60 \
  --output-format json --strict-mcp-config --no-session-persistence \
  "$(cat brief.md)" < /dev/null > run.json 2> run.err

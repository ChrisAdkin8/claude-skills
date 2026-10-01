#!/usr/bin/env bash
# Runs the implement-verifier: a sandboxed, cost-capped headless claude session in a scratch
# directory made by prepare-verify.sh, primed with verifier.md. It re-runs each Done when it can on
# the export and checks the diff against the spec, without seeing how the implementation was done.
#
# Usage: run-verify.sh <scratch dir under ~/.cache/implement-verify/>
#
# The scratch dir holds src/, diff.patch and before/W<n>/ from prepare-verify.sh, and spec.md,
# record.md and brief.md from the caller. The run writes run.json (the --output-format json
# result), run.err and reply.md (the verifier's reply) there.
#
# Exit 0: reply.md ends with the closing lines verifier.md asks for (`Verified: N of M` and
# `Implementation holds: yes|no`). Exit 3: the run finished, but reply.md lacks them (an API error,
# a budget stop, a verifier that ignored its format): don't read it as a verdict. Exit 2: the run
# couldn't start. Any other non-zero exit is claude's own, with run.err saying why.
#
# Capped at $5 and 100 turns. On the user's default model, or on $RUN_AGENT_MODEL if it's set, as
# hooks/run-agent.sh does, so the evals' per-model runs reach it. The sandbox is
# verify-settings.json beside this script's directory: the spike settings, with no network.
set -euo pipefail

die() { echo "run-verify: $*" >&2; exit 2; }

[ $# -eq 1 ] || die "usage: run-verify.sh <scratch dir>"
name='[A-Za-z0-9][A-Za-z0-9._-]*'
layout="^$name/$name/V[0-9]+$"
root="$HOME/.cache/implement-verify"
real_root=$(cd "$root" 2>/dev/null && pwd -P) || real_root=$root

# First the path as given, before anything resolves it, so a path elsewhere is refused for what
# it is whether or not it exists. Either spelling of the root: as written, or resolved.
case "$1" in
  "$root"/*) rest=${1#"$root"/} ;;
  "$real_root"/*) rest=${1#"$real_root"/} ;;
  *) die "not under ~/.cache/implement-verify/: $1" ;;
esac
[[ $rest =~ $layout ]] || die "scratch must be ~/.cache/implement-verify/<repo>/<spec>/V<n>, not $1"

# Then resolved, so a symlink on the way can't lead out of the root.
[ -d "$real_root" ] || die "no ~/.cache/implement-verify"
scratch=$(cd "$1" 2>/dev/null && pwd -P) || die "no such scratch dir: $1"
case "$scratch" in
  "$real_root"/*) [[ ${scratch#"$real_root"/} =~ $layout ]] ||
    die "$1 resolves to $scratch, outside the layout under $real_root" ;;
  *) die "$1 resolves to $scratch, not under ~/.cache/implement-verify/" ;;
esac
for f in brief.md spec.md diff.patch; do
  [ -f "$scratch/$f" ] || die "missing $scratch/$f"
done
[ -d "$scratch/src" ] || die "missing $scratch/src"

# The spikes' uv cache, not the user's ~/.cache/uv, for the reason run-spike.sh gives; the
# settings let a run write there and nowhere else outside its scratch dir.
export UV_CACHE_DIR="$HOME/.cache/spec-spikes/.uv-cache"
mkdir -p "$UV_CACHE_DIR"
# No auto memory, as in hooks/run-agent.sh: the verifier checks the work against the spec alone.
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1

# The prompt and settings sit beside this script's directory, wherever the skill is installed.
here=$(cd "$(dirname "$0")/.." && pwd -P)
verifier=$here/verifier.md
settings=$here/verify-settings.json
model=(${RUN_AGENT_MODEL:+--model "$RUN_AGENT_MODEL"})

# --setting-sources user, as in run-spike.sh and hooks/run-agent.sh: no project settings or
# CLAUDE.md above or beside the scratch dir load.
cd "$scratch"
rm -f reply.md
status=0
claude -p --setting-sources user \
  --append-system-prompt-file "$verifier" \
  --settings "$settings" \
  --allowedTools "Read Grep Glob Bash Write(./**) Edit(./**)" \
  --max-budget-usd 5 --max-turns 100 ${model[@]+"${model[@]}"} \
  --output-format json --strict-mcp-config --no-session-persistence \
  "$(cat brief.md)" < /dev/null > run.json 2> run.err || status=$?

python3 - <<'PY'
import json
from pathlib import Path
try:
    d = json.loads(Path("run.json").read_text())
except (OSError, ValueError):
    Path("reply.md").write_text("run-verify: no result; see run.err\n")
    raise SystemExit(0)
reply = d.get("result") or f"run-verify: the run ended with subtype {d.get('subtype')!r} and no reply"
Path("reply.md").write_text(reply + "\n")
PY

# The closing lines verifier.md tells it to reply with. A reply without them is not a verdict.
shape_ok() {
  python3 - <<'PY'
import re, sys
reply = open("reply.md").read()
shape = [r"Verified: \d+ of \d+", r"Implementation holds: (yes|no)"]
missing = [p for p in shape if not re.search(p, reply)]
if missing:
    print("missing " + "; ".join(missing), file=sys.stderr)
sys.exit(1 if missing else 0)
PY
}
if [ "$status" -eq 0 ] && ! shape_ok; then
  echo "run-verify: the verifier finished, but its reply isn't in the shape verifier.md asks" \
    "for; see $scratch/reply.md" >&2
  exit 3
fi
echo "run-verify: finished (exit $status); reply in $scratch/reply.md"
exit "$status"

#!/usr/bin/env bash
# Runs the implementer: a headless claude session of its own, which has seen none of the
# conversation, in a git worktree /implement made for one spec. /implement frames, relays and
# verifies; the implementer does the work items, from its agent file, hooks/agents/implementer.md.
#
# Usage: run-implementer.sh <worktree> <run dir> [--resume]
#
#   <worktree>  a linked git worktree of a repo under ~/code, itself under ~/code
#   <run dir>   ~/.cache/implement-runs/<repo dir>--<spec basename>/implementer, holding brief.md
#               (written first by /implement). The run writes reply.md (the implementer's reply),
#               run.json, run.err and session_id there, and keeps each call's run.json as
#               run-<n>.json.
#   --resume    send followup.md from the run dir to the same session instead, keeping the
#               previous reply as reply-<n>.md
#
# Exit 0: reply.md's last line is `Implementer: done`, `Implementer: question: <text>` or
# `Implementer: stopped: <reason>`. Exit 3: the run finished, but it isn't (an API error, a budget
# stop, a reply out of format): don't act on it. Exit 2: the run couldn't start (a bad path, no
# brief, no session to resume, the cap spent, a bad cap or ledger). Exit 4: the ledger changed
# during the call, which nothing but this script should write: no reply.md is written, so act on
# nothing. Any other non-zero exit is claude's own, with run.err saying why.
#
# The cap is for every implementer call ever made for this spec: $IMPLEMENT_MAX_USD (default $20,
# digits with an optional decimal part, above 0). Spent is read from the ledger,
# ~/.cache/implement-ledger/<repo dir>--<spec basename>.jsonl (ledger.py beside this script), which
# no run resets, fresh or resumed: each call gets the cap less what's spent, and is refused once
# that reaches the cap. A call with no valid total_cost_usd is charged its whole budget, as is one
# that never wrote its end line. To go past the cap, raise IMPLEMENT_MAX_USD or remove the ledger
# by hand. --max-budget-usd stops a call only after the turn that crosses it.
#
# On the user's default model, or on $RUN_AGENT_MODEL if it's set, as hooks/run-agent.sh does, so
# the skill evals' per-model runs reach it.
#
# Why not run-agent.sh: its agents are read-only and sandboxed, and the agent sandbox denies Bash
# writes under ~/code and inside .git, so a sandboxed implementer could neither edit nor commit.
# This one runs outside the OS sandbox, as it would in the user's session, with the repo's own
# settings, hooks and CLAUDE.md (--setting-sources user,project). Its separate session and the
# worktree are its isolation; the sandboxed implement-verifier is the independent check.
set -euo pipefail

die() { echo "run-implementer: $*" >&2; exit 2; }

[ $# -eq 2 ] || [ $# -eq 3 ] || die "usage: run-implementer.sh <worktree> <run dir> [--resume]"
work=$1 run=$2 mode=${3:-}
[ -z "$mode" ] || [ "$mode" = --resume ] || die "unknown option: $mode"

# The plugin root (the repo, or the plugin cache copy) is found from this script's own location:
# skills/implement/scripts/.
plugin_root=$(cd "$(dirname "$0")/../../.." && pwd -P)
export CLAUDE_PLUGIN_ROOT=$plugin_root
# No auto memory: the implementer works from the spec and the repo. With memory on it would also
# read, and could write, the memory the user's own sessions in this repo load.
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1
file="$plugin_root/hooks/agents/implementer.md"
[ -f "$file" ] || die "no agent file: $file"

# The working directory: a linked worktree (its git dir isn't the common one), whose main repo
# and itself both resolve under ~/code.
code=$(cd "$HOME/code" 2>/dev/null && pwd -P) || die "no ~/code"
[ -d "$work" ] || die "no such worktree: $work"
work=$(cd "$work" && pwd -P)
case "$work/" in "$code"/?*/) ;; *) die "$work is not under ~/code" ;; esac
top=$(git -C "$work" rev-parse --show-toplevel 2>/dev/null) || die "not a git repo: $work"
[ "$(cd "$top" && pwd -P)" = "$work" ] || die "$work is not the top of its worktree ($top)"
git_dir=$(cd "$work" && cd "$(git rev-parse --git-dir)" && pwd -P)
common=$(cd "$work" && cd "$(git rev-parse --git-common-dir)" && pwd -P)
[ "$git_dir" != "$common" ] || die "$work is a repo's main checkout, not a worktree of it"
case "$common/" in "$code"/?*/) ;; *) die "$work is a worktree of a repo outside ~/code ($common)" ;; esac

root="$HOME/.cache/implement-runs"
name='[A-Za-z0-9][A-Za-z0-9._-]*'
[[ $run =~ ^$root/$name/$name$ ]] ||
  die "run dir must be ~/.cache/implement-runs/<repo>--<spec>/implementer, not $run"
mkdir -p "$run"
run=$(cd "$run" && pwd -P)
case "$run/" in "$(cd "$root" && pwd -P)"/?*/?*/) ;; *) die "$run is outside $root" ;; esac

max_usd=${IMPLEMENT_MAX_USD:-20}
[[ $max_usd =~ ^[0-9]+(\.[0-9]+)?$ ]] && [[ $max_usd =~ [1-9] ]] ||
  die "IMPLEMENT_MAX_USD must be a number above 0, such as 20 or 7.5, not '$max_usd'"
ledger_py="$plugin_root/skills/implement/scripts/ledger.py"
run_name=$(basename "$(dirname "$run")")
ledger=$("$ledger_py" path "$run_name") || die "no ledger path for $run_name"
used=$("$ledger_py" spent "$run_name") || die "couldn't read the ledger $ledger; it's refused until fixed or removed by hand"
budget=$(python3 -c 'import sys; c, s = float(sys.argv[1]), float(sys.argv[2]); print(f"{c - s:g}" if c > s else "")' "$max_usd" "$used")
[ -n "$budget" ] ||
  die "this spec's implementer calls have spent \$$used of the \$$max_usd cap (ledger: $ledger)." \
    "To go on, raise IMPLEMENT_MAX_USD or remove the ledger by hand."

if [ "$mode" = --resume ]; then
  [ -s "$run/session_id" ] || die "no session_id in $run to resume"
  [ -s "$run/followup.md" ] || die "write $run/followup.md first"
  n=1; while [ -e "$run/reply-$n.md" ]; do n=$((n + 1)); done
  [ -e "$run/reply.md" ] && mv "$run/reply.md" "$run/reply-$n.md"
  prompt=$(cat "$run/followup.md")
  resume=(--resume "$(cat "$run/session_id")")
else
  [ -s "$run/brief.md" ] || die "write $run/brief.md first"
  rm -f "$run/reply.md" "$run/reply-"*.md "$run/session_id"
  prompt=$(cat "$run/brief.md")
  resume=()
fi

# The agent's definition as --agents takes it, and its own tools pre-approved, e.g.
# "Read,Edit,Write,Glob,Grep,Bash,Skill": Bash too, so /simplify and /code-review can run their
# own checks, which spike S2 found refused without it.
"$plugin_root/hooks/agent-def.py" --root "$plugin_root" "$file" > "$run/agents.json" ||
  die "couldn't read the agent file $file"
tools=$(python3 -c 'import json,sys;(a,)=json.load(open(sys.argv[1])).values();print(",".join(a["tools"]))' "$run/agents.json")
[ -n "$tools" ] || die "no tools in $file"
model=(${RUN_AGENT_MODEL:+--model "$RUN_AGENT_MODEL"})

# The ledger's start line, then its hash: nothing but this script writes the ledger, so a change
# by the end of the call is a write the sandbox should have stopped.
sha() { shasum -a 256 < "$ledger" | cut -d' ' -f1; }
call=$("$ledger_py" next-call "$run_name") || die "couldn't read the ledger $ledger"
"$ledger_py" append "$run_name" \
  "{\"who\": \"implementer\", \"call\": $call, \"event\": \"start\", \"budget\": $budget}" ||
  die "couldn't write the ledger $ledger"
before=$(sha)

cd "$work"
status=0
claude -p --agents "$run/agents.json" --agent implementer --output-format json --max-turns 400 \
  --max-budget-usd "$budget" --allowedTools "$tools" --permission-mode acceptEdits \
  --setting-sources user,project --add-dir "$(dirname "$run")" "$plugin_root" --strict-mcp-config \
  ${model[@]+"${model[@]}"} ${resume[@]+"${resume[@]}"} \
  -- "$prompt" < /dev/null > "$run/run.json" 2> "$run/run.err" || status=$?

if [ "$(sha)" != "$before" ]; then
  echo "run-implementer: exit 4: the ledger $ledger changed during the call; no end line or" \
    "reply was written, so act on nothing from this run" >&2
  exit 4
fi
# The call's cost, or its whole budget if run.json has no finite, non-negative total_cost_usd.
usd=$(python3 - "$run/run.json" "$budget" <<'PY'
import json, math, sys
try:
    cost = json.load(open(sys.argv[1])).get("total_cost_usd")
except (OSError, ValueError, AttributeError):
    cost = None
ok = isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost) and cost >= 0
print(cost if ok else sys.argv[2])
PY
)
"$ledger_py" append "$run_name" \
  "{\"who\": \"implementer\", \"call\": $call, \"event\": \"end\", \"usd\": $usd}" ||
  die "couldn't write the ledger's end line for call $call to $ledger"

n=1; while [ -e "$run/run-$n.json" ]; do n=$((n + 1)); done
cp "$run/run.json" "$run/run-$n.json"

python3 - "$run" <<'PY'
import json, sys
from pathlib import Path
run = Path(sys.argv[1])
try:
    d = json.loads((run / "run.json").read_text())
except (OSError, ValueError):
    (run / "reply.md").write_text("run-implementer: no result; see run.err\n")
    sys.exit(0)
if d.get("session_id"):
    (run / "session_id").write_text(d["session_id"])
reply = d.get("result") or f"run-implementer: the run ended with subtype {d.get('subtype')!r} and no reply"
(run / "reply.md").write_text(reply + "\n")
PY

# The closing line implementer.md tells it to end with. A reply without it is not an answer,
# whatever it says, so /implement mustn't act on it.
shape_ok() {
  python3 - "$run/reply.md" <<'PY'
import re, sys
lines = [l.strip() for l in open(sys.argv[1]).read().splitlines() if l.strip()]
last = lines[-1] if lines else ""
ok = re.fullmatch(r"Implementer: (done|question: \S.*|stopped: \S.*)", last)
if not ok:
    print(f"the last line is {last!r}, not an Implementer: line", file=sys.stderr)
sys.exit(0 if ok else 1)
PY
}
if [ "$status" -eq 0 ] && ! shape_ok; then
  echo "run-implementer: the implementer finished, but its reply doesn't end with an" \
    "Implementer: line; see $run/reply.md" >&2
  exit 3
fi
echo "run-implementer: finished (exit $status); reply in $run/reply.md"
exit "$status"

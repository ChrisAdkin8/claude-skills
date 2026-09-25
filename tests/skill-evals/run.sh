#!/usr/bin/env bash
# Skill evaluations: each case builds a throwaway repo (setup.sh), runs a whole skill against it
# headless (prompt.txt, as `claude -p`), and grades the files the skill left (grade.py). They test
# the main session's orchestration, which the agent evals in ../agent-evals don't reach.
#
# Usage: run.sh [case ...]   all cases by default, in parallel
# Runs inside hooks/agent-sandbox.json, so Bash writes stay in the fixture and network is limited.
# Costs real tokens; run by hand after changing a skill's steps. Results: results/<timestamp>/.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd -P)
out="$here/results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out"
cases=("$@")
[ ${#cases[@]} -eq 0 ] && while IFS= read -r c; do cases+=("$c"); done < <(ls "$here/cases")

run_case() {
  local c=$1 dir="$here/cases/$1" work
  work=$(mktemp -d)
  "$dir/setup.sh" "$work" > "$out/$c.setup" 2>&1 || { echo "FAIL $c (setup)"; return; }
  (cd "$work" && claude -p --output-format json --max-turns 60 --max-budget-usd "${EVAL_MAX_USD:-3}" \
    --settings "$repo/hooks/agent-sandbox.json" --permission-mode acceptEdits \
    --allowedTools "Read Write Edit Glob Grep Bash Skill" --strict-mcp-config --no-session-persistence \
    "$(cat "$dir/prompt.txt")" < /dev/null) > "$out/$c.json" 2> "$out/$c.err"
  if python3 "$dir/grade.py" "$work" "$out/$c.json" > "$out/$c.grade" 2>&1; then r=PASS; else r=FAIL; fi
  cost=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(f\"{d.get('num_turns')} turns, \${d.get('total_cost_usd',0):.2f}\")" "$out/$c.json" 2>/dev/null)
  echo "$r $c ($cost)"; sed 's/^/    /' "$out/$c.grade"
  (cd "$work" && git status --short && git diff) > "$out/$c.diff" 2>&1
  rm -rf "$work"
}
for c in "${cases[@]}"; do run_case "$c" & done
wait

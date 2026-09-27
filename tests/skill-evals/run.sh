#!/usr/bin/env bash
# Skill evaluations: each case builds a throwaway repo (setup.sh), runs a whole skill against it
# headless (prompt.txt, as `claude -p`), and grades the files the skill left (grade.py). They test
# the main session's orchestration, which the agent evals in ../agent-evals don't reach.
#
# Usage: run.sh [case ...]   all cases by default, in parallel
# Runs inside hooks/agent-sandbox.json, so Bash writes stay in the fixture and network is limited.
# Costs real tokens; run by hand after changing a skill's steps. Results: results/<timestamp>/.
#   SKILL_EVAL_MAX_USD  per-case cost ceiling, passed as --max-budget-usd (default 3)
#   EVAL_CASES, EVAL_OUT  the cases and results directories (default: cases/ and
#                         results/<timestamp>/ here); tests/test_eval_runners.py points them elsewhere
# Exits 0 only if every case passed, 1 if any failed, 2 on a bad case name.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd -P)
out=${EVAL_OUT:-$here/results/$(date +%Y%m%d-%H%M%S)}
mkdir -p "$out"
cases=("$@")
cases_dir=${EVAL_CASES:-$here/cases}
[ ${#cases[@]} -eq 0 ] && while IFS= read -r c; do cases+=("$c"); done < <(ls "$cases_dir")
for c in "${cases[@]}"; do
  [ -d "$cases_dir/$c" ] || { echo "no such case: $c" >&2; exit 2; }
done

run_case() {
  local c=$1 dir="$cases_dir/$1" work
  work=$(mktemp -d)
  "$dir/setup.sh" "$work" > "$out/$c.setup" 2>&1 || { echo "FAIL $c (setup)"; echo FAIL > "$out/$c.result"; return; }
  (cd "$work" && claude -p --output-format json --max-turns 60 --max-budget-usd "${SKILL_EVAL_MAX_USD:-3}" \
    --settings "$repo/hooks/agent-sandbox.json" --permission-mode acceptEdits \
    --allowedTools "Read Write Edit Glob Grep Bash Skill" --strict-mcp-config --no-session-persistence \
    "$(cat "$dir/prompt.txt")" < /dev/null) > "$out/$c.json" 2> "$out/$c.err"
  if python3 "$dir/grade.py" "$work" "$out/$c.json" > "$out/$c.grade" 2>&1; then r=PASS; else r=FAIL; fi
  cost=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(f\"{d.get('num_turns')} turns, \${d.get('total_cost_usd',0):.2f}\")" "$out/$c.json" 2>/dev/null)
  echo "$r $c ($cost)"; sed 's/^/    /' "$out/$c.grade"; echo "$r" > "$out/$c.result"
  (cd "$work" && git status --short && git diff) > "$out/$c.diff" 2>&1
  rm -rf "$work"
}
for c in "${cases[@]}"; do run_case "$c" & done
wait
passed=$(cat "$out"/*.result 2>/dev/null | grep -c '^PASS$')
total=$(python3 - "$out"/*.json <<'PY'
import json, sys
total = 0.0
for path in sys.argv[1:]:
    try:
        total += json.load(open(path)).get("total_cost_usd") or 0
    except (OSError, ValueError):
        pass
print(f"{total:.2f}")
PY
)
echo "$passed of ${#cases[@]} passed; total \$${total:-0.00}"
[ "$passed" -eq ${#cases[@]} ]

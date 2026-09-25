#!/usr/bin/env bash
# Agent evaluations for the /research and /spec verifiers. Each case sends one brief to one
# subagent with `claude -p --agent`, as the skill would, and grades the reply against expect.txt.
#
# Usage: run.sh [case ...]        all cases by default; cases run in parallel
#   EVAL_MAX_USD   per-case cost ceiling, passed as --max-budget-usd (default 5)
#   EVAL_MODEL     model to run the agents on (default: your default model)
#   EVAL_SETTINGS  the settings file passed as --settings (default: hooks/agent-sandbox.json, the
#                  sandbox run-agent.sh uses, so the evals run the agents as the skills do;
#                  set it empty to run without a sandbox)
#
# Each case directory in cases/ holds a fixture, agent.txt (the subagent), brief.txt (the brief,
# with {{CASE}}, {{HOME}}, {{REPO}} and {{DATE}} filled in) and expect.txt: one Python regex per line that
# must match the reply text, or must not match if the line starts with "!"; blank lines and
# lines starting with "#" are ignored. Only the reply text (.result) is graded, never the JSON.
#
# The agents run with their own frontmatter tools pre-approved and their own PreToolUse hook
# (checked 2026-09-15: the guard blocks `awk` under --agent), in a throwaway directory with read
# access to ~/.claude, ~/notes and this repo (~/.claude/skills, agents and hooks are symlinks into
# it), with no MCP servers and no saved session. Every run costs real tokens: run by hand after changing an
# agent or skill file, not on every commit. Results land in results/<timestamp>/ (git-ignored).
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd -P)
agents="$HOME/.claude/agents"
stamp=$(date +%Y%m%d-%H%M%S)
out="$here/results/$stamp"
today=$(date +%Y-%m-%d)
max_usd=${EVAL_MAX_USD:-5}
settings=${EVAL_SETTINGS-$repo/hooks/agent-sandbox.json}
mkdir -p "$out"

cases=("$@")
if [ ${#cases[@]} -eq 0 ]; then
  while IFS= read -r c; do cases+=("$c"); done < <(ls "$here/cases")
fi

run_case() {
  local c=$1 dir="$here/cases/$1" agent tools brief work
  agent=$(cat "$dir/agent.txt")
  # The agent's frontmatter tools line, e.g. "tools: Read, Bash, WebFetch, WebSearch".
  tools=$(sed -n 's/^tools:[[:space:]]*//p' "$agents/$agent.md" | head -1 | tr -d ' ')
  brief=$(sed -e "s#{{CASE}}#$dir#g" -e "s#{{HOME}}#$HOME#g" -e "s#{{REPO}}#$repo#g" \
    -e "s#{{DATE}}#$today#g" "$dir/brief.txt")
  work=$(mktemp -d)
  "$repo/hooks/sandbox-prompt.py" > "$out/$c.sandbox.md"
  (cd "$work" && claude -p --agent "$agent" --output-format json --max-turns 40 \
    --allowedTools "$tools" --add-dir "$HOME/.claude" "$HOME/notes" "$repo" \
    --append-system-prompt-file "$out/$c.sandbox.md" \
    --strict-mcp-config --no-session-persistence \
    --max-budget-usd "$max_usd" ${EVAL_MODEL:+--model "$EVAL_MODEL"} \
    ${settings:+--settings "$settings"} "$brief") \
    > "$out/$c.json" 2> "$out/$c.err"
  rm -rf "$work"
}

for c in "${cases[@]}"; do
  [ -d "$here/cases/$c" ] || { echo "no such case: $c" >&2; exit 2; }
done
echo "Running ${#cases[@]} case(s) in parallel; results in $out"
for c in "${cases[@]}"; do run_case "$c" & done
wait

python3 - "$out" "$here/cases" "${cases[@]}" <<'PY'
import json, re, sys
from pathlib import Path

out, cases_dir, cases = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
passed, cost = 0, 0.0
for case in cases:
    raw = (out / f"{case}.json").read_text()
    try:
        run = json.loads(raw)
    except json.JSONDecodeError:
        print(f"ERROR {case}: no JSON result (see {out / (case + '.err')})")
        continue
    cost += run.get("total_cost_usd") or 0
    info = f"{run.get('num_turns', '?')} turns, ${run.get('total_cost_usd', 0):.2f}"
    if run.get("is_error") or run.get("subtype") != "success":
        print(f"ERROR {case}: {run.get('subtype')} ({info}); a cap or failure, not a verdict")
        continue
    reply = run.get("result") or ""
    misses = []
    for line in (cases_dir / case / "expect.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        negate = line.startswith("!")
        found = re.search(line[1:] if negate else line, reply) is not None
        if found == negate:
            misses.append(("matched " if negate else "no match for ") + line)
    if misses:
        print(f"FAIL {case} ({info}): " + "; ".join(misses))
    else:
        passed += 1
        print(f"PASS {case} ({info})")
print(f"{passed} of {len(cases)} passed; total ${cost:.2f}")
PY

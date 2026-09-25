#!/usr/bin/env bash
# Agent evaluations for the /research and /spec agents. Each case sends one brief to one
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
# A case whose brief uses {{NOTE}} runs an agent that writes a research note (the researcher).
# The guard only lets it write in ~/notes/research, so {{NOTE}} is a hidden file there,
# ~/notes/research/.eval-<case>-<timestamp>.md. After the run the note is copied to the results
# as <case>.note.md, checked with check-note.py --headroom (it must pass), graded against the
# case's note-expect.txt (same format as expect.txt), and deleted. The run also fails such a case
# if anything else in ~/notes changed while it ran. Optional turns.txt raises the turn limit
# from 40, and usd.txt sets the case's own cost ceiling in place of EVAL_MAX_USD.
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
  note="$HOME/notes/research/.eval-$c-$stamp.md"
  brief=$(sed -e "s#{{CASE}}#$dir#g" -e "s#{{HOME}}#$HOME#g" -e "s#{{REPO}}#$repo#g" \
    -e "s#{{DATE}}#$today#g" -e "s#{{NOTE}}#$note#g" "$dir/brief.txt")
  turns=$(cat "$dir/turns.txt" 2>/dev/null || echo 40)
  usd=$(cat "$dir/usd.txt" 2>/dev/null || echo "$max_usd")
  work=$(mktemp -d)
  "$repo/hooks/sandbox-prompt.py" > "$out/$c.sandbox.md"
  (cd "$work" && claude -p --agent "$agent" --output-format json --max-turns "$turns" \
    --allowedTools "$tools" --add-dir "$HOME/.claude" "$HOME/notes" "$repo" \
    --append-system-prompt-file "$out/$c.sandbox.md" \
    --strict-mcp-config --no-session-persistence --setting-sources user \
    --max-budget-usd "$usd" ${EVAL_MODEL:+--model "$EVAL_MODEL"} \
    ${settings:+--settings "$settings"} "$brief") \
    > "$out/$c.json" 2> "$out/$c.err"
  rm -rf "$work"
  if [ -f "$note" ]; then
    cp "$note" "$out/$c.note.md"
    "$repo/skills/research/scripts/check-note.py" --headroom "$note" > "$out/$c.note-check" 2>&1
    rm -f "$note"
  fi
}

# What in ~/notes has changed, leaving out the eval notes themselves.
notes_status() { git -C "$HOME/notes" status --porcelain --untracked-files=all | grep -v '/\.eval-'; }

for c in "${cases[@]}"; do
  [ -d "$here/cases/$c" ] || { echo "no such case: $c" >&2; exit 2; }
done
echo "Running ${#cases[@]} case(s) in parallel; results in $out"
notes_status > "$out/notes-before"
for c in "${cases[@]}"; do run_case "$c" & done
wait
notes_status > "$out/notes-after"

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
    if "{{NOTE}}" in (cases_dir / case / "brief.txt").read_text():
        note, check = out / f"{case}.note.md", out / f"{case}.note-check"
        if not note.exists():
            misses.append("no note written")
        else:
            if "RESULT: PASS" not in (check.read_text() if check.exists() else ""):
                misses.append(f"check-note.py didn't pass (see {check.name})")
            text = note.read_text()
            for line in (cases_dir / case / "note-expect.txt").read_text().splitlines():
                if not line.strip() or line.startswith("#"):
                    continue
                negate = line.startswith("!")
                if (re.search(line[1:] if negate else line, text) is not None) == negate:
                    misses.append(("note matched " if negate else "note has no match for ") + line)
        if (out / "notes-before").read_text() != (out / "notes-after").read_text():
            misses.append("something else in ~/notes changed during the run (see notes-before/after)")
    if misses:
        print(f"FAIL {case} ({info}): " + "; ".join(misses))
    else:
        passed += 1
        print(f"PASS {case} ({info})")
print(f"{passed} of {len(cases)} passed; total ${cost:.2f}")
PY

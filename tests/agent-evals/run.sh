#!/usr/bin/env bash
# Agent evaluations for the /research, /spec and /cold-review agents. Each case sends one brief to one
# subagent with `claude -p --agents <file> --agent <name>`, as the skill would, and grades the reply against expect.txt.
#
# Usage: run.sh [case ...]        all cases by default; cases run in parallel
#   AGENT_EVAL_MAX_USD  per-case cost ceiling, passed as --max-budget-usd (default 5)
#   EVAL_CASES, EVAL_OUT  the cases and results directories (default: cases/ and
#                  results/<timestamp>/ here); tests/test_eval_runners.py points them elsewhere
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
# if anything else in ~/notes changed while it ran, or if ~/notes isn't a git repo, since
# then changes can't be seen. Optional turns.txt raises the turn limit
# from 40, and usd.txt sets the case's own cost ceiling in place of AGENT_EVAL_MAX_USD. Optional
# models.txt, one model per line, limits a case to those models: with EVAL_MODEL set to another,
# the case is skipped, and says so. guard-applies runs only on opus: sonnet declines awk itself,
# so the guard it tests never sees the call.
#
# The agents run with their own frontmatter tools pre-approved and their own PreToolUse hook
# (checked 2026-09-15: the guard blocks `awk` under --agent; the guard-applies case checks it
# under --agents), in a throwaway directory with read access to ~/.claude, ~/notes and this repo,
# with no MCP servers and no saved session. The agents need no plugin loaded: agent-def.py writes
# this checkout's path into each definition. Every run costs real tokens: run by hand after
# changing an agent or skill file, not on every commit. Results land in results/<timestamp>/
# (git-ignored).
# Exits 0 only if every case passed, 1 if any failed or ended in an error, 2 on a bad case name or no
# cases.
set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd -P)
# The agent files live in hooks/agents; each case passes its agent by --agents, as run-agent.sh does.
agents="$repo/hooks/agents"
stamp=$(date +%Y%m%d-%H%M%S)
out=${EVAL_OUT:-$here/results/$stamp}
today=$(date +%Y-%m-%d)
max_usd=${AGENT_EVAL_MAX_USD:-5}
settings=${EVAL_SETTINGS-$repo/hooks/agent-sandbox.json}
# Every runner renders ${CLAUDE_PLUGIN_ROOT} in the settings to this checkout (hooks/agent-settings.py).
cases_dir=${EVAL_CASES:-$here/cases}
mkdir -p "$out"

cases=("$@")
if [ ${#cases[@]} -eq 0 ]; then
  while IFS= read -r c; do cases+=("$c"); done < <(ls "$cases_dir")
fi
# bash 3.2 calls "${cases[@]}" unbound when it's empty, so say why instead.
[ ${#cases[@]} -gt 0 ] || { echo "no cases in $cases_dir" >&2; exit 2; }
# Work dirs live under one temp dir, and eval notes are named by $stamp, so an interrupted run
# leaves neither behind.
tmp_root=$(mktemp -d)
trap 'rm -rf "$tmp_root"; rm -f "$HOME"/notes/research/.eval-*-"$stamp".md' EXIT

run_case() {
  local c=$1 dir="$cases_dir/$1" agent tools brief work
  agent=$(cat "$dir/agent.txt")
  # The agent's definition as --agents takes it, and its own tools pre-approved.
  "$repo/hooks/agent-def.py" --root "$repo" "$agents/$agent.md" > "$out/$c.agents.json" 2> "$out/$c.err" || return
  tools=$(python3 -c 'import json,sys;(a,)=json.load(open(sys.argv[1])).values();print(",".join(a["tools"]))' "$out/$c.agents.json")
  note="$HOME/notes/research/.eval-$c-$stamp.md"
  brief=$(sed -e "s#{{CASE}}#$dir#g" -e "s#{{HOME}}#$HOME#g" -e "s#{{REPO}}#$repo#g" \
    -e "s#{{DATE}}#$today#g" -e "s#{{NOTE}}#$note#g" "$dir/brief.txt")
  turns=$(cat "$dir/turns.txt" 2>/dev/null || echo 40)
  usd=$(cat "$dir/usd.txt" 2>/dev/null || echo "$max_usd")
  work=$(mktemp -d "$tmp_root/work.XXXXXX")
  "$repo/hooks/sandbox-prompt.py" > "$out/$c.sandbox.md"
  case_settings=
  if [ -n "$settings" ]; then
    "$repo/hooks/agent-settings.py" "$settings" "$repo" > "$out/$c.settings.json" 2> "$out/$c.settings.err" || return
    case_settings="$out/$c.settings.json"
  fi
  (cd "$work" && claude -p --agents "$out/$c.agents.json" --agent "$agent" --output-format json --max-turns "$turns" \
    --allowedTools "$tools" --add-dir "$HOME/.claude" "$HOME/notes" "$repo" \
    --append-system-prompt-file "$out/$c.sandbox.md" \
    --strict-mcp-config --no-session-persistence --setting-sources user \
    --max-budget-usd "$usd" ${EVAL_MODEL:+--model "$EVAL_MODEL"} \
    ${case_settings:+--settings "$case_settings"} "$brief") \
    > "$out/$c.json" 2> "$out/$c.err"
  rm -rf "$work"
  if [ -f "$note" ]; then
    cp "$note" "$out/$c.note.md"
    "$repo/skills/research/scripts/check-note.py" --headroom "$note" > "$out/$c.note-check" 2>&1
    rm -f "$note"
  fi
}

# What in ~/notes has changed, leaving out eval notes, this set's hidden ones and the skill evals'.
# Without a git repo there, changes can't be seen, so it says so and the research cases fail.
notes_status() {
  if git -C "$HOME/notes" rev-parse --git-dir > /dev/null 2>&1; then
    git -C "$HOME/notes" status --porcelain --untracked-files=all | grep -Ev '/\.?eval-'
  else
    echo "NOT A GIT REPO"
  fi
}

for c in "${cases[@]}"; do
  [ -d "$cases_dir/$c" ] || { echo "no such case: $c" >&2; exit 2; }
done
# A case with models.txt runs only on the models it lists, when EVAL_MODEL names another.
kept=()
for c in "${cases[@]}"; do
  if [ -n "${EVAL_MODEL:-}" ] && [ -f "$cases_dir/$c/models.txt" ] && ! grep -qx "$EVAL_MODEL" "$cases_dir/$c/models.txt"; then
    echo "SKIP $c: runs only on $(paste -sd, "$cases_dir/$c/models.txt"), not $EVAL_MODEL"
  else
    kept+=("$c")
  fi
done
[ ${#kept[@]} -gt 0 ] || { echo "0 of 0 passed; every case was skipped"; exit 0; }
cases=("${kept[@]}")
echo "Running ${#cases[@]} case(s) in parallel; results in $out"
notes_status > "$out/notes-before"
for c in "${cases[@]}"; do run_case "$c" & done
wait
notes_status > "$out/notes-after"

python3 - "$out" "$cases_dir" "${cases[@]}" <<'PY'
import json, re, sys
from pathlib import Path

out, cases_dir, cases = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
passed, cost = 0, 0.0
for case in cases:
    try:
        run = json.loads((out / f"{case}.json").read_text())
    except (OSError, json.JSONDecodeError):
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
        if "NOT A GIT REPO" in (out / "notes-before").read_text():
            misses.append("~/notes isn't a git repo, so changes to it can't be checked")
        elif (out / "notes-before").read_text() != (out / "notes-after").read_text():
            misses.append("something else in ~/notes changed during the run (see notes-before/after)")
    if misses:
        print(f"FAIL {case} ({info}): " + "; ".join(misses))
    else:
        passed += 1
        print(f"PASS {case} ({info})")
print(f"{passed} of {len(cases)} passed; total ${cost:.2f}")
sys.exit(0 if passed == len(cases) else 1)
PY

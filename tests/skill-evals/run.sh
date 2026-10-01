#!/usr/bin/env bash
# Skill evaluations: each case builds a throwaway repo (setup.sh), runs a whole skill against it
# headless (prompt.txt, as `claude -p`), and grades the files the skill left (grade.py). They test
# the main session's orchestration, which the agent evals in ../agent-evals don't reach.
#
# Usage: run.sh [case ...]   all cases by default, in parallel
# Runs inside hooks/agent-sandbox.json, so Bash writes stay in the fixture and network is limited.
# Loads this checkout as the plugin (--plugin-dir), so prompt.txt types /checked-plans:<skill>.
# Pre-approves only the Skill tool, so the skill's own allowed-tools decide what runs. Headless, a
# call they don't approve is denied, not asked about, and a case with any denial fails, as does
# one whose session left no result.
# Costs real tokens; run by hand after changing a skill's steps. Results: results/<timestamp>/.
#   SKILL_EVAL_MAX_USD  per-case cost ceiling, passed as --max-budget-usd (default 3)
#   EVAL_MODEL          model to run the skills on, passed as --model (default: your default model);
#                       exported as RUN_AGENT_MODEL, so the agents a skill launches run on it too
#   EVAL_CASES, EVAL_OUT  the cases and results directories (default: cases/ and
#                         results/<timestamp>/ here); tests/test_eval_runners.py points them elsewhere
#
# A case may also hold:
#   location.txt  "code": the fixture is ~/code/eval-<case>-<stamp>, not a temp dir, for /spec,
#                 which works only in a repo under ~/code and whose allowed-tools edit Markdown
#                 only there. No leading dot: run-agent.sh refuses a run dir name that starts with
#                 one, and /spec names its run dir after the repo.
#   settings.txt  the settings file for --settings, in this directory, in place of
#                 hooks/agent-sandbox.json: agent-case-settings.json for a case that runs agents,
#                 implement-case-settings.json (the sandbox off) for an /implement case, whose
#                 worktree, commits and ~/.cache/implement-runs writes the sandbox refuses.
# prompt.txt may use {{NOTE}}, filled in with ~/notes/research/eval-<case>-<stamp>.md, and {{STAMP}}.
# grade.py gets that path as EVAL_NOTE, and `git -C ~/notes status --porcelain` from before and
# after the case, eval notes left out, as NOTES_BEFORE and NOTES_AFTER. Afterwards the note, the
# ~/code fixture and the agent run dirs named eval-<case>-<stamp>* are copied to the results and
# removed, and so are an /implement case's worktrees (~/code/eval-<case>-<stamp>-worktrees), its
# implementer run dirs (~/.cache/implement-runs) and its verifier scratch dirs
# (~/.cache/implement-verify). IMPLEMENT_MAX_USD caps the implementer at $5 and RUN_AGENT_MAX_USD
# each agent a skill launches at $2, unless they are set; the printed cost is the skill session's
# alone, so read the agents', implementer's and verifiers' run.json files in the results for theirs.
# Run this and ../agent-evals/run.sh one after the other: each checks ~/notes.
# Exits 0 only if every case passed, 1 if any failed, 2 on a bad case name or no cases.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd -P)
stamp=$(date +%Y%m%d-%H%M%S)
out=${EVAL_OUT:-$here/results/$stamp}
mkdir -p "$out"
cases=("$@")
cases_dir=${EVAL_CASES:-$here/cases}
[ ${#cases[@]} -eq 0 ] && while IFS= read -r c; do cases+=("$c"); done < <(ls "$cases_dir")
# bash 3.2 calls "${cases[@]}" unbound when it's empty, so say why instead.
[ ${#cases[@]} -gt 0 ] || { echo "no cases in $cases_dir" >&2; exit 2; }
for c in "${cases[@]}"; do
  [ -d "$cases_dir/$c" ] || { echo "no such case: $c" >&2; exit 2; }
done

# Every temp fixture lives under one temp dir, and the rest are named by $stamp, so an interrupted
# run leaves none behind.
tmp_root=$(mktemp -d)
trap 'rm -rf "$tmp_root" "$HOME"/code/eval-*-"$stamp" "$HOME"/code/eval-*-"$stamp"-worktrees "$HOME"/.cache/agent-runs/eval-*-"$stamp"* "$HOME"/.cache/implement-runs/eval-*-"$stamp"* "$HOME"/.cache/implement-verify/eval-*-"$stamp"*; rm -f "$HOME"/notes/research/eval-*-"$stamp".md' EXIT

# An agent a skill launches runs on the model under test, not the default (hooks/run-agent.sh).
export RUN_AGENT_MODEL=${EVAL_MODEL:-}
# An /implement case's implementer (skills/implement/scripts/run-implementer.sh) gets $5, not $20.
export IMPLEMENT_MAX_USD=${IMPLEMENT_MAX_USD:-5}
# Each agent a skill launches (hooks/run-agent.sh) gets $2, not its own $5, or $10 for the
# researcher: an eval's questions are small, and its agents cost $0.06 to $0.38 on 2026-09-30.
export RUN_AGENT_MAX_USD=${RUN_AGENT_MAX_USD:-2}

# What in ~/notes has changed, leaving out eval notes from either eval set, hidden or not.
notes_status() {
  if git -C "$HOME/notes" rev-parse --git-dir > /dev/null 2>&1; then
    git -C "$HOME/notes" status --porcelain --untracked-files=all | grep -Ev '/\.?eval-'
  else
    echo "NOT A GIT REPO"
  fi
}

run_case() {
  local c=$1 dir="$cases_dir/$1" work note settings prompt before after
  note="$HOME/notes/research/eval-$c-$stamp.md"
  if [ "$(cat "$dir/location.txt" 2>/dev/null)" = code ]; then
    work="$HOME/code/eval-$c-$stamp"
    mkdir -p "$work"
  else
    work=$(mktemp -d "$tmp_root/work.XXXXXX")
  fi
  settings="$repo/hooks/agent-sandbox.json"
  [ -f "$dir/settings.txt" ] && settings="$here/$(cat "$dir/settings.txt")"
  # ${CLAUDE_PLUGIN_ROOT} in the settings becomes this checkout, as an absolute path.
  "$repo/hooks/agent-settings.py" "$settings" "$repo" > "$out/$c.settings.json" 2> "$out/$c.settings.err" \
    || { echo "FAIL $c (settings)"; echo FAIL > "$out/$c.result"; rm -rf "$work"; return; }
  settings="$out/$c.settings.json"
  prompt=$(sed -e "s#{{NOTE}}#$note#g" -e "s#{{STAMP}}#$stamp#g" "$dir/prompt.txt")
  "$dir/setup.sh" "$work" > "$out/$c.setup" 2>&1 || { echo "FAIL $c (setup)"; echo FAIL > "$out/$c.result"; rm -rf "$work"; return; }
  before=$(notes_status)
  # Only Skill is pre-approved, and edits aren't accepted wholesale, so the skill's own
  # allowed-tools decide what runs, as for a user: a bare tool name here would approve every use
  # of that tool, and a command missing from the skill's list would never be refused.
  (cd "$work" && claude -p --plugin-dir "$repo" --output-format json --max-turns 60 --max-budget-usd "${SKILL_EVAL_MAX_USD:-3}" ${EVAL_MODEL:+--model "$EVAL_MODEL"} \
    --settings "$settings" --allowedTools Skill --strict-mcp-config --no-session-persistence \
    "$prompt" < /dev/null) > "$out/$c.json" 2> "$out/$c.err"
  after=$(notes_status)
  if EVAL_NOTE="$note" NOTES_BEFORE="$before" NOTES_AFTER="$after" \
    python3 "$dir/grade.py" "$work" "$out/$c.json" > "$out/$c.grade" 2>&1; then r=PASS; else r=FAIL; fi
  # Then the session's own verdict, whatever grade.py found. Headless, a call nothing approved is
  # denied rather than asked about: one the skill's allowed-tools miss, or one a settings file
  # refuses. Either fails the case. So does a session with no result to read.
  python3 - "$out/$c.json" >> "$out/$c.grade" <<'PY' || r=FAIL
import json, sys

try:
    with open(sys.argv[1]) as f:
        denials = json.load(f).get("permission_denials") or []
except (OSError, ValueError, AttributeError):
    print("FAIL no result JSON from the session")
    sys.exit(1)
for d in denials:
    call = json.dumps(d.get("tool_input"))
    print(f"FAIL permission denied: {d.get('tool_name')} {call[:200] + '...' * (len(call) > 200)}")
sys.exit(1 if denials else 0)
PY
  cost=$(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(f\"{d.get('num_turns')} turns, \${d.get('total_cost_usd',0):.2f}\")" "$out/$c.json" 2>/dev/null)
  echo "$r $c ($cost)"; sed 's/^/    /' "$out/$c.grade"; echo "$r" > "$out/$c.result"
  (cd "$work" && git status --short && git diff) > "$out/$c.diff" 2>&1
  [ -f "$note" ] && cp "$note" "$out/$c.note.md"
  for kind in agent-runs implement-runs implement-verify; do
    for d in "$HOME"/.cache/"$kind"/eval-"$c"-"$stamp"*; do
      [ -d "$d" ] || continue
      mkdir -p "$out/$c.$kind" && cp -R "$d" "$out/$c.$kind/"
      rm -rf "$d"
    done
  done
  [ -d "$work/docs" ] && cp -R "$work/docs" "$out/$c.docs"
  [ -d "$work-worktrees" ] && cp -R "$work-worktrees" "$out/$c.worktrees"
  rm -rf "$work" "$work-worktrees"
  rm -f "$note"
}
for c in "${cases[@]}"; do run_case "$c" & done
wait
# Only this run's cases: a reused EVAL_OUT may hold older results.
passed=0
for c in "${cases[@]}"; do grep -qx PASS "$out/$c.result" 2>/dev/null && passed=$((passed + 1)); done
total=$(python3 - "${cases[@]/#/$out/}" <<'PY'
import json, sys
total = 0.0
for path in sys.argv[1:]:
    try:
        total += json.load(open(path + ".json")).get("total_cost_usd") or 0
    except (OSError, ValueError):
        pass
print(f"{total:.2f}")
PY
)
echo "$passed of ${#cases[@]} passed; total \$${total:-0.00}"
[ "$passed" -eq ${#cases[@]} ]

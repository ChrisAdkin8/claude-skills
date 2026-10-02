#!/usr/bin/env bash
# Agent evaluations for the /research, /spec and /cold-review agents. Each case sends one brief to one
# subagent with `claude -p --agents <file> --agent <name>`, as the skill would, and grades the reply against expect.txt.
#
# Usage: run.sh [case ...]        all cases by default; cases run in parallel
#   AGENT_EVAL_MAX_USD  per-case cost ceiling, passed as --max-budget-usd (default 5)
#   EVAL_CASES, EVAL_OUT  the cases and results directories (default: cases/ and
#                  results/<timestamp>/ here); tests/test_eval_runners.py points them elsewhere
#   EVAL_REPO      the repo {{REPO}} is a clone of (default: this checkout); the tests point it
#                  at a fixture repo
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
# The answers are kept out of the agents' way. {{CASE}} is a temporary copy of the fixture alone
# (spec.md, note.md, records/ and so on): not expect.txt, note-expect.txt or the runner's other
# files, and under a name that doesn't give the case away. {{REPO}} is a clone of this checkout's
# committed history, made for the run, without tests/agent-evals and tests/skill-evals and with
# the answer keys in its history emptied (see the clone below): commit what a case should see.
# Each case's rendered settings also deny reads of this checkout's eval directories and git dir.
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
# under --agents), in a throwaway directory with read access to ~/notes, the clone and the fixture
# copy, with no MCP servers and no saved session. The agents need no plugin loaded:
# agent-def.py writes this checkout's path into each definition, so the guard and the skill scripts
# run from here. Every run costs real tokens: run by hand after changing an agent or skill file,
# not on every commit. Results land in results/<timestamp>/ (git-ignored).
# Exits 0 only if every case passed, 1 if any failed or ended in an error, 2 on a bad case name, no
# cases, or a clone that couldn't be made.
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
# No auto memory, as in hooks/run-agent.sh, so the agents run as the skills run them.
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1

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
# The runner's own files in a case directory; the rest is the fixture, which {{CASE}} copies.
runner_files=(agent.txt brief.txt expect.txt note-expect.txt turns.txt usd.txt models.txt)

# Adds read denies for the paths in `hidden` (below) to a rendered settings file: to the sandbox's
# denyRead, for Bash, and as Read rules, for the Read, Grep and Glob tools. Each path as given and
# resolved, since a deny matches the spelling a call uses.
deny_answer_keys() {
  python3 - "$1" ${hidden[@]+"${hidden[@]}"} <<'PY'
import json, os, sys

path, hidden = sys.argv[1], sys.argv[2:]
paths = list(dict.fromkeys(q for p in hidden if p for q in (p, os.path.realpath(p))))
with open(path) as f:
    settings = json.load(f)
fs = settings.setdefault("sandbox", {}).setdefault("filesystem", {})
fs["denyRead"] = fs.get("denyRead", []) + paths
# `//` makes a Read rule's path absolute; with one `/` it would start at this file's directory.
rules = [rule for p in paths for rule in (f"Read(/{p})", f"Read(/{p}/**)")]
settings.setdefault("permissions", {}).setdefault("deny", []).extend(rules)
with open(path, "w") as f:
    json.dump(settings, f, indent=2)
PY
}

run_case() {
  local c=$1 dir="$cases_dir/$1" agent tools brief work fixture
  agent=$(cat "$dir/agent.txt")
  # The agent's definition as --agents takes it, and its own tools pre-approved.
  "$repo/hooks/agent-def.py" --root "$repo" "$agents/$agent.md" > "$out/$c.agents.json" 2> "$out/$c.err" || return
  tools=$(python3 -c 'import json,sys;(a,)=json.load(open(sys.argv[1])).values();print(",".join(a["tools"]))' "$out/$c.agents.json")
  note="$HOME/notes/research/.eval-$c-$stamp.md"
  # {{CASE}} is a copy of the fixture alone, not the case directory, which holds the answer key
  # beside it and is named for what's planted.
  fixture=$(mktemp -d "$tmp_root/case.XXXXXX")
  cp -R "$dir/." "$fixture"
  for f in "${runner_files[@]}"; do rm -f "$fixture/$f"; done
  brief=$(sed -e "s#{{CASE}}#$fixture#g" -e "s#{{HOME}}#$HOME#g" -e "s#{{REPO}}#$clone#g" \
    -e "s#{{DATE}}#$today#g" -e "s#{{NOTE}}#$note#g" "$dir/brief.txt")
  turns=$(cat "$dir/turns.txt" 2>/dev/null || echo 40)
  usd=$(cat "$dir/usd.txt" 2>/dev/null || echo "$max_usd")
  work=$(mktemp -d "$tmp_root/work.XXXXXX")
  "$repo/hooks/sandbox-prompt.py" > "$out/$c.sandbox.md"
  case_settings=
  if [ -n "$settings" ]; then
    "$repo/hooks/agent-settings.py" "$settings" "$repo" > "$out/$c.settings.json" 2> "$out/$c.settings.err" || return
    # On this run's rendered copy only: the committed file is what run-agent.sh gives the skills.
    deny_answer_keys "$out/$c.settings.json" 2>> "$out/$c.settings.err" || return
    case_settings="$out/$c.settings.json"
  fi
  (cd "$work" && claude -p --agents "$out/$c.agents.json" --agent "$agent" --output-format json --max-turns "$turns" \
    --allowedTools "$tools" --add-dir "$HOME/notes" "$clone" "$fixture" \
    --append-system-prompt-file "$out/$c.sandbox.md" \
    --strict-mcp-config --no-session-persistence --setting-sources user \
    --max-budget-usd "$usd" ${EVAL_MODEL:+--model "$EVAL_MODEL"} \
    ${case_settings:+--settings "$case_settings"} "$brief") \
    > "$out/$c.json" 2> "$out/$c.err"
  rm -rf "$work" "$fixture"
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

# {{REPO}} is a clone of this checkout, made once for the run and shared by its cases, rather than
# the checkout, whose tests/agent-evals holds every case's expect.txt. --no-local copies only what
# the refs reach, so no object is shared with this repo and no stray one (an old stash's) comes
# along. The clone drops tests/agent-evals and tests/skill-evals from its working tree and index,
# so its files and a plain `git grep` there hold no answer key. Its history is whole, the spec
# cases' read-at commits with it, but every expect.txt, note-expect.txt and BASELINE.md blob in it
# is pointed at the empty blob, as `git replace` would (one update-ref call makes all its refs), so
# `git show <commit>:<path>`, `git grep <pattern> <commit>` and `git log -p` read them as empty.
# That keeps the keys from an agent that comes across them, not from one that hunts: one that runs
# `git --no-replace-objects` (the guard allows it) or `git cat-file --batch-all-objects --batch`
# still reads the originals.
clone="$tmp_root/repo"
{
  git -c advice.detachedHead=false clone -q --no-local "${EVAL_REPO:-$repo}" "$clone" &&
    git -C "$clone" rm -r -q --ignore-unmatch tests/agent-evals tests/skill-evals &&
    empty=$(git -C "$clone" hash-object -w --stdin < /dev/null) &&
    git -C "$clone" log --all -m --root --format= --raw --no-abbrev -- \
      '*/expect.txt' '*/note-expect.txt' tests/agent-evals/BASELINE.md |
    awk -v e="$empty" '{ for (i = 3; i <= 4; i++) if ($i !~ /^0+$/ && $i != e) print "update refs/replace/" $i " " e }' |
    sort -u | git -C "$clone" update-ref --stdin
} || { echo "couldn't make {{REPO}}'s clone of ${EVAL_REPO:-$repo} without its answer keys" >&2; exit 2; }

# Where this checkout keeps the answer keys, and every other worktree of its repo too: the cases,
# results and BASELINE.md under tests/agent-evals and tests/skill-evals, and the git dirs, whose
# history holds every expect.txt. Each case's settings deny reads of them (deny_answer_keys), so an
# agent can't go round the clone: the spec cases name ~/code/github.com/claude-skills as their
# cite repo, and the agents run the guard and the skill scripts from this checkout.
hidden=("$(cd "$repo" && cd "$(git rev-parse --git-common-dir)" && pwd -P)")
while IFS= read -r wt; do
  hidden+=("$wt/tests/agent-evals" "$wt/tests/skill-evals" "$wt/.git")
done < <(git -C "$repo" worktree list --porcelain | sed -n 's/^worktree //p')

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

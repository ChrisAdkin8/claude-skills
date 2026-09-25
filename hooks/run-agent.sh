#!/usr/bin/env bash
# Runs one of the skills' agents as a headless, sandboxed claude session.
#
# Usage: run-agent.sh <agent> <work dir> <run dir> [--resume]
#
#   <agent>     researcher, research-verifier, spec-verifier or cold-reviewer
#   <work dir>  the directory the agent works in: the repo under review, or ~/notes
#   <run dir>   ~/.cache/agent-runs/<name>/<agent>[-<n>], holding brief.md (written first by the
#               skill). The run writes reply.md (the agent's reply), run.json, run.err and
#               session_id there.
#   --resume    send followup.md from the run dir to the same session instead, keeping the
#               previous reply as reply-<n>.md
#
# Exit 0: reply.md holds a reply in the shape the agent's file asks for (REPLY_SHAPES below).
# Exit 3: the run finished, but reply.md doesn't have that shape: an API error such as "Request
# timed out", a budget stop, or an agent that ignored its format. Don't act on it as a verdict.
# Exit 2: the run couldn't start. Any other non-zero exit is claude's own, with run.err saying why.
#
# Each run is capped at $RUN_AGENT_MAX_USD (default $10 for the researcher, $5 for the others;
# the costliest recorded run to 2026-09-25 was $1.02) and 200 turns. --max-budget-usd stops a
# run only after the turn that crosses it, so a run can go over by up to one turn.
#
# Each run's agent and session ID are appended to ~/.cache/agent-runs/sessions.log (or
# $RUN_AGENT_LOG), which tests/replay_guard.py reads.
#
# Why headless: Claude Code's sandbox can't be set per subagent, and these agents read untrusted
# web pages and repos. Run this way, each gets its agent file (prompt, tools, hooks) plus
# hooks/agent-sandbox.json: OS-level read denies for credentials, no writes outside its work
# dir, secret environment variables removed, and Bash network limited to an allowlist. The
# PreToolUse guard in the agent's frontmatter still runs, for what the sandbox can't see (gh and
# the excluded scripts, git and curl semantics, WebFetch URL sizes). The agent evals run the
# agents the same way (tests/agent-evals/run.sh).
set -euo pipefail

die() { echo "run-agent: $*" >&2; exit 2; }

[ $# -eq 3 ] || [ $# -eq 4 ] || die "usage: run-agent.sh <agent> <work dir> <run dir> [--resume]"
agent=$1 work=$2 run=$3 mode=${4:-}
[ -z "$mode" ] || [ "$mode" = --resume ] || die "unknown option: $mode"
case "$agent" in
  researcher|research-verifier|spec-verifier|cold-reviewer) ;;
  *) die "not an agent this script runs: $agent" ;;
esac

here=$(cd "$(dirname "$0")" && pwd -P)
file="$HOME/.claude/agents/$agent.md"
[ -f "$file" ] || die "no agent file: $file"
[ -d "$work" ] || die "no such work dir: $work"
work=$(cd "$work" && pwd -P)

root="$HOME/.cache/agent-runs"
name='[A-Za-z0-9][A-Za-z0-9._-]*'
[[ $run =~ ^$root/$name/$name$ ]] || die "run dir must be ~/.cache/agent-runs/<name>/<agent>, not $run"
mkdir -p "$run"
run=$(cd "$run" && pwd -P)
case "$run/" in "$(cd "$root" && pwd -P)"/?*/?*/) ;; *) die "$run is outside $root" ;; esac

# The agent file's own tools line, e.g. "tools: Read, Bash, WebFetch, WebSearch".
tools=$(sed -n 's/^tools:[[:space:]]*//p' "$file" | head -1 | tr -d ' ')
# The researcher does the open-ended work; the others check something already written.
max_usd=${RUN_AGENT_MAX_USD:-5}
[ "$agent" = researcher ] && max_usd=${RUN_AGENT_MAX_USD:-10}
# Only the researcher uses MCP tools (AWS and Terraform docs, listed one by one in its file).
mcp=(--strict-mcp-config)
[ "$agent" = researcher ] && mcp=()

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

# Every agent gets the same description of its sandbox, with the host list read from the
# settings that enforce it, rather than a copy in each agent file.
"$here/sandbox-prompt.py" > "$run/sandbox.md" || die "couldn't write $run/sandbox.md"

cd "$work"
status=0
claude -p --agent "$agent" --output-format json --max-turns 200 --max-budget-usd "$max_usd" \
  --allowedTools "$tools" --add-dir "$HOME/.claude" "$HOME/notes" "$work" \
  --append-system-prompt-file "$run/sandbox.md" \
  --settings "$here/agent-sandbox.json" ${mcp[@]+"${mcp[@]}"} ${resume[@]+"${resume[@]}"} \
  "$prompt" < /dev/null > "$run/run.json" 2> "$run/run.err" || status=$?

python3 - "$run" "$agent" "${RUN_AGENT_LOG:-$root/sessions.log}" <<'PY'
import json, sys, time
from pathlib import Path
run, agent, log_path = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
try:
    d = json.loads((run / "run.json").read_text())
except (OSError, ValueError):
    (run / "reply.md").write_text("run-agent: no result; see run.err\n")
    sys.exit(0)
if d.get("session_id"):
    (run / "session_id").write_text(d["session_id"])
    # A run dir is reused by the next run of the same agent on the same document, so this log
    # is what keeps every session findable; tests/replay_guard.py reads it.
    with open(log_path, "a") as log:
        log.write(f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {agent} {d['session_id']}\n")
reply = d.get("result") or f"run-agent: the run ended with subtype {d.get('subtype')!r} and no reply"
(run / "reply.md").write_text(reply + "\n")
PY

# The closing lines each agent's file tells it to reply with. A reply without them is not a
# verdict, whatever it says, so the skill mustn't read it as one.
shape_ok() {
  python3 - "$run/reply.md" "$agent" <<'PY'
import re, sys
reply, agent = open(sys.argv[1]).read(), sys.argv[2]
REPLY_SHAPES = {
    "researcher": [r"RESULT: (PASS|FAIL)"],
    "research-verifier": [r"\|\s*#\s*\|\s*Claim", r"Confirmed: \d+ of \d+", r"Bottom line holds: (yes|no)"],
    "spec-verifier": [r"\|\s*#\s*\|\s*Claim", r"Confirmed: \d+ of \d+", r"Plan holds: (yes|no)"],
    "cold-reviewer": [r"\|\s*#\s*\|\s*Kind", r"Counts: \d+ findings", r"Cold read: (yes|no)"],
}
missing = [p for p in REPLY_SHAPES[agent] if not re.search(p, reply)]
if missing:
    print("missing " + "; ".join(missing), file=sys.stderr)
sys.exit(1 if missing else 0)
PY
}
if [ "$status" -eq 0 ] && ! shape_ok; then
  echo "run-agent: $agent finished, but its reply isn't in the shape its instructions ask for;" \
    "see $run/reply.md" >&2
  exit 3
fi
echo "run-agent: $agent finished (exit $status); reply in $run/reply.md"
exit "$status"

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
# brief, no session to resume, the cap spent, a bad cap or ledger, a user setting that could widen
# the sandbox). Exit 4: the call changed what it mustn't: the ledger, which nothing but this script
# writes, or the repo's shared git config, hooks or a worktree's git pointers (named one per line),
# or left a submodule config under its git dir that names a program. No reply.md is written, so
# act on nothing, and run no git command in the repo or the worktree. 4 comes before 3 and before
# claude's own status. A ref or HEAD in the shared git dir that moved during the call is named in
# a `run-implementer: moved during the run: <ref> <old> -> <new>` line, without stopping: the
# user's own commits and fetches move them too.
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
# Sandboxed: the implementer's Bash runs under skills/implement/implementer-settings.json, rendered
# per call into the run dir with this run's paths. It may write only its worktree, its own git
# dir, the repo's objects, the implement/* branches' refs, ~/.cache/implement-runs/<run name>/scratch
# and the per-user temp dir; not the repo's shared config, hooks, HEAD or index, other worktrees'
# git files, ~/.claude, ~/notes or the ledger; and it has no network. Its Edit and Write tools are
# pre-approved only in the worktree and the scratch dir. Only the user's settings load
# (--setting-sources user): a project hook runs outside the sandbox, and could run a file the
# implementer rewrote. A user setting that would widen the sandbox refuses the run instead. Not
# run-agent.sh: its agents are read-only, and the agent sandbox denies writes under ~/code. The
# repo's CLAUDE.md and rules files the implementer reads itself; the sandboxed implement-verifier
# is the independent check.
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

# The scratch dir: the one place outside the worktree the implementer may write (baseline.txt).
scratch="$(dirname "$run")/scratch"
mkdir -p "$scratch"
# The macOS per-user temp dir: mktemp writes there, and without it this repo's suite fails.
tmp=$(getconf DARWIN_USER_TEMP_DIR 2>/dev/null) && [ -d "$tmp" ] && tmp=$(cd "$tmp" && pwd -P) ||
  die "couldn't find the per-user temp dir (getconf DARWIN_USER_TEMP_DIR)"

# A user setting that could widen the --settings sandbox: whether it would is untested, so refuse.
python3 - "$HOME/.claude/settings.json" <<'PY' || exit 2
import json, sys
try:
    with open(sys.argv[1]) as f:
        settings = json.load(f)
except FileNotFoundError:
    sys.exit(0)
except (OSError, ValueError) as e:
    sys.exit(f"run-implementer: can't read {sys.argv[1]} to check its sandbox keys: {e}")
box = settings.get("sandbox") if isinstance(settings, dict) else None
box = box if isinstance(box, dict) else {}
fs = box.get("filesystem") if isinstance(box.get("filesystem"), dict) else {}
widening = [
    key for key, bad in (
        ("sandbox.enabled", box.get("enabled") is False),
        ("sandbox.allowUnsandboxedCommands", box.get("allowUnsandboxedCommands") is True),
        ("sandbox.excludedCommands", bool(box.get("excludedCommands"))),
        ("sandbox.filesystem.allowWrite", bool(fs.get("allowWrite"))),
    ) if bad
]
if widening:
    sys.exit(f"run-implementer: {sys.argv[1]} sets {', '.join(widening)}, which could widen the"
             " implementer's sandbox; remove it to run /implement")
PY

# The settings, with this run's paths, and each other worktree's git files denied too.
rendered=$("$plugin_root/hooks/agent-settings.py" \
  "$plugin_root/skills/implement/implementer-settings.json" \
  "$plugin_root" "IMPLEMENT_WORKTREE=$work" "IMPLEMENT_GIT_DIR=$git_dir" \
  "IMPLEMENT_COMMON_DIR=$common" "IMPLEMENT_SCRATCH=$scratch" "IMPLEMENT_TMP=$tmp") ||
  die "couldn't render the implementer's settings"
python3 - "$rendered" "$common" "$git_dir" > "$run/settings.json" <<'PY' ||
import json, os, sys
rendered, common, own = sys.argv[1:]
settings = json.loads(rendered)
deny = settings["sandbox"]["filesystem"]["denyWrite"]
worktrees = os.path.join(common, "worktrees")
for name in sorted(os.listdir(worktrees)) if os.path.isdir(worktrees) else []:
    theirs = os.path.join(worktrees, name)
    if os.path.realpath(theirs) != own:
        deny += [os.path.join(theirs, f) for f in ("commondir", "gitdir", "HEAD", "config.worktree", "index")]
print(json.dumps(settings, indent=2))
PY
  die "couldn't add the other worktrees to the implementer's settings"

# The agent's definition as --agents takes it, and its own tools pre-approved, e.g.
# "Read,Edit,Write,Glob,Grep,Bash,Skill": Bash too, so /simplify and /code-review can run their
# own checks, which spike S2 found refused without it.
"$plugin_root/hooks/agent-def.py" --root "$plugin_root" "$file" > "$run/agents.json" ||
  die "couldn't read the agent file $file"
# Edit and Write become Edit rules for the worktree and the scratch dir (an Edit rule covers Write).
tools=$(python3 - "$run/agents.json" "$run_name" <<'PY'
import json, sys
(agent,) = json.load(open(sys.argv[1])).values()
edits = ["Edit(./**)", f"Edit(~/.cache/implement-runs/{sys.argv[2]}/scratch/**)"]
tools = []
for tool in agent["tools"]:
    if tool in ("Edit", "Write"):
        tools += [e for e in edits if e not in tools]
    else:
        tools.append(tool)
print(",".join(tools))
PY
)
[ -n "$tools" ] || die "no tools in $file"
model=(${RUN_AGENT_MODEL:+--model "$RUN_AGENT_MODEL"})

# What can make git run a program or point a checkout elsewhere, read without running git: the
# shared config and hooks, every worktree's pointers, submodules' config and hooks. With no
# argument it prints the state as JSON; given that JSON, it prints a `changed:` line for each path
# that differs, a `moved:` line for each ref but the branch's own that moved, and a `program:` line
# for a submodule config under the worktree's git dir that names a program or a hooks entry there:
# /implement's own git add and commit, unsandboxed, would read them, and their -c flags cover only
# core.fsmonitor and core.hooksPath.
snapshot() {
  python3 - "$plugin_root/hooks/git-read.py" "$common" "$git_dir" "$work" "$@" <<'PY'
import hashlib, importlib.util, json, os, re, stat, sys

spec = importlib.util.spec_from_file_location("git_read", sys.argv.pop(1))
git_read = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git_read)
common, git_dir, work = sys.argv[1:4]
# git-read.py's keys that name a program, the two its -c flags (and /implement's) override, and
# an include, whose file keys() doesn't follow and which could set any of them.
RUNS = re.compile(
    git_read.RUNS.pattern + r"|core\.fsmonitor|core\.hookspath|include\.path|includeif\..+\.path",
    re.IGNORECASE,
)

def state(path):
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return "missing"
    except OSError as e:
        return f"unreadable ({e.strerror})"
    if stat.S_ISLNK(st.st_mode):
        return "link " + os.readlink(path)
    if stat.S_ISDIR(st.st_mode):
        return "dir"
    if not stat.S_ISREG(st.st_mode):
        return f"type {stat.S_IFMT(st.st_mode):o}"
    try:
        with open(path, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
    except OSError as e:
        return f"unreadable ({e.strerror})"
    return f"{stat.S_IMODE(st.st_mode):o} {digest}"

def walk(top):
    """Every entry under top, top included, not following links."""
    found = [top]
    for root, dirs, files in os.walk(top):
        found += [os.path.join(root, n) for n in dirs + files]
    return found

def children(top):
    try:
        return sorted(os.path.join(top, n) for n in os.listdir(top))
    except OSError:
        return []

def watched():
    paths = [os.path.join(common, "config"), os.path.join(common, "config.worktree"),
             os.path.join(work, ".git")]
    paths += walk(os.path.join(common, "hooks"))
    for wt in children(os.path.join(common, "worktrees")):
        paths += [os.path.join(wt, n) for n in ("config.worktree", "commondir", "gitdir")]
    modules = os.path.join(common, "modules")
    for path in walk(modules):
        parts = os.path.relpath(path, modules).split(os.sep)
        if parts[-1] == "config" or "hooks" in parts:
            paths.append(path)
    return {p: state(p) for p in paths}

def refs():
    own = None
    try:
        head = open(os.path.join(git_dir, "HEAD")).read().strip()
        own = head[5:].strip() if head.startswith("ref:") else None
    except OSError:
        pass
    found = {"HEAD": state(os.path.join(common, "HEAD"))}
    try:
        for line in open(os.path.join(common, "packed-refs")):
            parts = line.split()
            if len(parts) == 2 and not line.startswith(("#", "^")):
                found[parts[1]] = parts[0]
    except OSError:
        pass
    top = os.path.join(common, "refs")
    for root, _, files in os.walk(top):
        for n in files:
            path = os.path.join(root, n)
            name = os.path.relpath(path, common).replace(os.sep, "/")
            try:
                found[name] = open(path).read().strip()
            except OSError as e:
                found[name] = f"unreadable ({e.strerror})"
    found.pop(own, None)
    return found

def keys(path):
    """The keys a git config file sets, as section[.subsection].key; None if it can't be read."""
    try:
        text = open(path, errors="replace").read()
    except OSError:
        return None
    section, out = "", []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#;":
            continue
        m = re.match(r'\[\s*([^\s\]"]+)(?:\s+"((?:[^"\\]|\\.)*)")?\s*\](.*)', line)
        if m:
            section = m[1] + (f".{m[2]}" if m[2] is not None else "")
            line = m[3].strip()
            if not line or line[0] in "#;":
                continue
        name = re.split(r"[\s=]", line, maxsplit=1)[0]
        out.append(f"{section}.{name}")
    return out

def programs():
    found = []
    modules = os.path.join(git_dir, "modules")
    for path in walk(modules) if os.path.isdir(modules) else []:
        parts = os.path.relpath(path, modules).split(os.sep)
        if "hooks" in parts[:-1]:
            # git copies its template's *.sample hooks into every submodule it clones, and
            # never runs a hook by that name.
            if not parts[-1].endswith(".sample"):
                found.append(f"program: {path} (a hooks entry)")
        elif parts[-1] == "config" and os.path.isfile(path):
            names = keys(path)
            if names is None:
                found.append(f"program: {path} (unreadable)")
            else:
                found += [f"program: {path} sets {k}" for k in names if RUNS.fullmatch(k)]
    return found

if len(sys.argv) == 4:
    print(json.dumps({"watched": watched(), "refs": refs()}))
else:
    before = json.loads(sys.argv[4])
    now = watched()
    for path in sorted(set(now) | set(before["watched"])):
        if now.get(path, "missing") != before["watched"].get(path, "missing"):
            print(f"changed: {path}")
    for line in programs():
        print(line)
    after = refs()
    for name in sorted(set(after) | set(before["refs"])):
        old, new = before["refs"].get(name, "missing"), after.get(name, "missing")
        if old != new:
            print(f"moved: {name} {old} -> {new}")
PY
}

# The ledger's start line, then its hash: nothing but this script writes the ledger, so a change
# by the end of the call is a write the sandbox should have stopped.
sha() { shasum -a 256 < "$ledger" | cut -d' ' -f1; }
# The snapshot first: if it can't be taken, the call never starts, so nothing is charged.
taken=$(snapshot) || die "couldn't read the repo's git config and hooks before the call"
call=$("$ledger_py" next-call "$run_name") || die "couldn't read the ledger $ledger"
"$ledger_py" append "$run_name" \
  "{\"who\": \"implementer\", \"call\": $call, \"event\": \"start\", \"budget\": $budget}" ||
  die "couldn't write the ledger $ledger"
before=$(sha)

cd "$work"
status=0
claude -p --agents "$run/agents.json" --agent implementer --output-format json --max-turns 400 \
  --max-budget-usd "$budget" --allowedTools "$tools" --permission-mode acceptEdits \
  --setting-sources user --settings "$run/settings.json" --add-dir "$scratch" --strict-mcp-config \
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

# Exit 4 on anything that can make git run a program or point elsewhere; refs are only named.
diff=$(snapshot "$taken") || diff="changed: couldn't read the repo's git config and hooks after the call"
sed -n 's/^moved: /run-implementer: moved during the run: /p' <<< "$diff"
changed=$(grep -v -e '^moved: ' -e '^$' <<< "$diff" || true)
if [ -n "$changed" ]; then
  sed 's/^/run-implementer: /' <<< "$changed" >&2
  echo "run-implementer: exit 4: the call changed the repo's git config, hooks or pointers, named" \
    "above; no reply was written: act on nothing, and run no git command in the repo or the" \
    "worktree until the user has checked them" >&2
  exit 4
fi

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

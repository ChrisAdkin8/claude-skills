#!/usr/bin/env bash
# Runs the implementer: a headless claude session of its own, which has seen none of the
# conversation, in a git worktree /implement made for one spec. /implement frames, relays and
# verifies; the implementer does the work items, from its agent file, hooks/agents/implementer.md.
#
# Usage: run-implementer.sh <worktree> <run dir> [--resume]
#        run-implementer.sh --check <run dir>
#
#   <worktree>  a linked git worktree of a repo under ~/code, itself under ~/code
#   <run dir>   ~/.cache/implement-runs/<run name>/implementer, holding brief.md
#               (written first by /implement). The run writes reply.md (the implementer's reply),
#               run.json, run.err, session_id and snapshot.json (git's state before a call)
#               there, and keeps each call's run.json as run-<n>.json. It keeps copies of the
#               shared git config and the worktrees' config.worktree files in git-before/ and
#               git-after/ only while it checks a call.
#               <run name> is <repo dir>--<spec basename>, each as hooks/run-name.py prints it, so
#               a name with spaces or accents becomes one the name check below accepts.
#   --resume    send followup.md from the run dir to the same session instead, keeping the
#               previous reply as reply-<n>.md
#   --check     run only the refusals that don't need the worktree, for /implement's gate before
#               it makes one: the version and account checks, the run dir's name, the three
#               variables, the cap, the temp dir and the user's sandbox keys. It skips the
#               worktree's checks, making the run and scratch dirs, the brief, rendering the
#               settings, the snapshot and the ledger's start line, so it writes nothing and
#               launches nothing; it calls claude only for --version. A run dir that doesn't exist
#               yet can't be resolved, so a link that leads it outside ~/.cache/implement-runs is
#               still refused only at launch. Exit 0 if a launch would get past them, else 2 with
#               the launch's own message.
#
# Exit 0: reply.md's last line is `Implementer: done`, `Implementer: question: <text>` or
# `Implementer: stopped: <reason>`. Exit 3: the run finished, but it isn't (an API error, a budget
# stop, a reply out of format): don't act on it. Exit 2: the run couldn't start (a bad path, no
# brief, no session to resume, the cap spent, a bad cap or ledger, a user setting that could widen
# the sandbox). Exit 4: the call changed what it mustn't: the ledger, which nothing but this script
# writes, or the repo's shared git config, hooks or a worktree's git pointers (named one per line),
# or left a submodule config under its git dir that names a program. The shared config is compared
# by git's own parse, and passes if the only changes are branch tracking, as the user's own
# `git push -u`, `git branch --set-upstream-to`, `-d` or `-m` make: any `branch.*` entry removed,
# and a `branch.<b>.remote` or `pushremote` naming `.` or a remote with a URL, a `merge` under
# refs/, a `rebase` of true, false or merges, or a `description` added; anything else in it is
# named as `changed: <file> sets <key>`. Another worktree's entry under worktrees/ removed whole,
# or a new one with the shape `git worktree add` gives it, as the user's own `git worktree add` or
# `remove` in another checkout make, passes too; any other change to a worktree's entry doesn't. No reply.md is written, so
# act on nothing, and run no git command in the repo or the worktree. 4 comes before 3 and before
# claude's own status. Exit 5: the run found no Claude account to use; the script says how to give
# it one, after 4 and before 3, and /implement stops and relays it. A ref or HEAD in the shared git
# dir that moved during the call is named in a `run-implementer: moved during the run: <ref> <old>
# -> <new>` line, without stopping: the user's own commits and fetches move them too. Exit 6: the
# call was interrupted (INT, TERM or HUP, as when its background task is stopped): it was charged
# its budget, then settled at its cost if claude, sent INT, ended its turn with a result within
# $IMPLEMENT_INTERRUPT_WAIT seconds (default 5; then TERM, and KILL); no reply.md is written, so
# read nothing. A ledger or git change during the call still gives 4.
#
# The cap is for every implementer call ever made for this spec: $IMPLEMENT_MAX_USD (default $20,
# digits with an optional decimal part, above 0). Spent is read from the ledger,
# ~/.cache/implement-ledger/<run name>.jsonl (ledger.py beside this script), which
# no run resets, fresh or resumed: each call gets the cap less what's spent, but no more than
# $IMPLEMENT_CALL_MAX_USD (default $8, written as the cap is), and is refused once that reaches the
# cap. A resumed call's total_cost_usd is its session's running total, so each call is charged its
# own share of it. A call with no valid total_cost_usd is charged its whole budget, as is an
# interrupted one with no result, or one that never wrote its end line. To go past the cap, raise
# IMPLEMENT_MAX_USD, or, for a call charged its budget whose cost you know (the Claude Console's
# usage page), run `ledger.py settle <run name> <call> <usd>`, which the refusal names.
# --max-budget-usd stops a call only after the turn that crosses it.
#
# On the user's Claude account: ANTHROPIC_API_KEY is unset, and the settings switch off an
# apiKeyHelper and a key in the user's settings, unless CHECKED_PLANS_USE_API_KEY=1 is set
# (hooks/launch-checks.sh).
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
# shellcheck source=hooks/launch-checks.sh
source "$(dirname "$0")/../../../hooks/launch-checks.sh"
launch_version run-implementer
launch_account run-implementer

usage="usage: run-implementer.sh <worktree> <run dir> [--resume], or --check <run dir>"
check=
if [ "${1:-}" = --check ]; then
  [ $# -eq 2 ] || die "$usage"
  check=1 work='' run=$2 mode=''
else
  [ $# -eq 2 ] || [ $# -eq 3 ] || die "$usage"
  work=$1 run=$2 mode=${3:-}
  [ -z "$mode" ] || [ "$mode" = --resume ] || die "unknown option: $mode"
fi

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
# and itself both resolve under ~/code. --check has none yet.
if [ -z "$check" ]; then
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
fi

root="$HOME/.cache/implement-runs"
name='[A-Za-z0-9][A-Za-z0-9._-]*'
if ! [[ $run =~ ^$root/$name/$name$ ]]; then
  bad=
  [[ $run != "$root"/* ]] || bad=$(tr / '\n' <<< "${run#"$root"/}" | grep -v '^$' | grep -Evx "$name" | head -n 1 || true)
  [ -z "$bad" ] || bad=": \"$bad\" isn't a valid name: a name may hold only letters, digits, ., _ and -, starting with a letter or digit"
  die "run dir must be ~/.cache/implement-runs/<repo>--<spec>/implementer, not $run$bad"
fi
# --check makes nothing, so it resolves the run dir only if it's there already.
if [ -z "$check" ] || [ -d "$run" ]; then
  [ -n "$check" ] || mkdir -p "$run"
  run=$(cd "$run" && pwd -P)
  case "$run/" in "$(cd "$root" && pwd -P)"/?*/?*/) ;; *) die "$run is outside $root" ;; esac
fi

max_usd=${IMPLEMENT_MAX_USD:-20}
[[ $max_usd =~ ^[0-9]+(\.[0-9]+)?$ ]] && [[ $max_usd =~ [1-9] ]] ||
  die "IMPLEMENT_MAX_USD must be a number above 0, such as 20 or 7.5, not '$max_usd'"
call_max=${IMPLEMENT_CALL_MAX_USD:-8}
[[ $call_max =~ ^[0-9]+(\.[0-9]+)?$ ]] && [[ $call_max =~ [1-9] ]] ||
  die "IMPLEMENT_CALL_MAX_USD must be a number above 0, such as 8 or 2.5, not '$call_max'"
wait_s=${IMPLEMENT_INTERRUPT_WAIT:-5}
[[ $wait_s =~ ^[0-9]+$ ]] ||
  die "IMPLEMENT_INTERRUPT_WAIT must be a whole number of seconds, such as 5, not '$wait_s'"
ledger_py="$plugin_root/skills/implement/scripts/ledger.py"
run_name=$(basename "$(dirname "$run")")
ledger=$("$ledger_py" path "$run_name") || die "no ledger path for $run_name"
used=$("$ledger_py" spent "$run_name") || die "couldn't read the ledger $ledger; it's refused until fixed"
# The cap less what's spent, but no more than the per-call cap.
budget=$(python3 -c '
import sys
cap, spent, most = map(float, sys.argv[1:])
print(f"{min(cap - spent, most):g}" if cap > spent else "")' "$max_usd" "$used" "$call_max")
if [ -z "$budget" ]; then
  echo "run-implementer: this spec's implementer calls have spent \$$used of the \$$max_usd cap" \
    "(ledger: $ledger). To go on, raise IMPLEMENT_MAX_USD." >&2
  unsettled=$("$ledger_py" report "$run_name" | grep 'unsettled' || true)
  if [ -n "$unsettled" ]; then
    echo "run-implementer: these calls were charged their whole budget, as their cost is" \
      "unknown. For one whose cost you know, for example from the Claude Console's usage page," \
      "run \`$ledger_py settle $run_name <call> <usd>\` to charge it that instead:" >&2
    sed 's/^/  /' <<< "$unsettled" >&2
  fi
  exit 2
fi

if [ -n "$check" ]; then
  :
elif [ "$mode" = --resume ]; then
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
[ -n "$check" ] || mkdir -p "$scratch"
# The macOS per-user temp dir: mktemp writes there, and without it this repo's suite fails.
tmp=$(getconf DARWIN_USER_TEMP_DIR 2>/dev/null) && [ -d "$tmp" ] && tmp=$(cd "$tmp" && pwd -P) ||
  die "couldn't find the per-user temp dir (getconf DARWIN_USER_TEMP_DIR)"

# A user setting that could widen the --settings sandbox: whether it would is untested, so refuse.
# Any sandbox.network key that isn't empty is refused too, and strictAllowlist unless it's true.
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
net = box.get("network") if isinstance(box.get("network"), dict) else {}
widening = [
    key for key, bad in (
        ("sandbox.enabled", box.get("enabled") is False),
        ("sandbox.allowUnsandboxedCommands", box.get("allowUnsandboxedCommands") is True),
        ("sandbox.excludedCommands", bool(box.get("excludedCommands"))),
        ("sandbox.filesystem.allowWrite", bool(fs.get("allowWrite"))),
        *(
            (f"sandbox.network.{k}", v is not True if k == "strictAllowlist" else bool(v))
            for k, v in sorted(net.items())
        ),
    ) if bad
]
if widening:
    sys.exit(f"run-implementer: {sys.argv[1]} sets {', '.join(widening)}, which could widen the"
             " implementer's sandbox; remove it to run /implement")
PY

if [ -n "$check" ]; then
  echo "run-implementer: --check passed: a launch with $run would get past these checks"
  exit 0
fi

# The settings, with this run's paths, and each other worktree's git files denied too.
rendered=$("$plugin_root/hooks/agent-settings.py" \
  "$plugin_root/skills/implement/implementer-settings.json" \
  "$plugin_root" "IMPLEMENT_WORKTREE=$work" "IMPLEMENT_GIT_DIR=$git_dir" \
  "IMPLEMENT_COMMON_DIR=$common" "IMPLEMENT_SCRATCH=$scratch" "IMPLEMENT_TMP=$tmp") ||
  die "couldn't render the implementer's settings"
python3 - "$rendered" "$common" "$git_dir" <<'PY' | account_settings - "$run/settings.json" ||
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

# What can make git run a program or point a checkout elsewhere: the shared config and hooks,
# every worktree's pointers, submodules' config and hooks, read without running git, but for the
# shared config's two files, which are copied into the run dir and, if their bytes differ, listed
# by git itself. With no argument it prints the state as JSON, the worktrees/ entries' names
# included, and copies those files and each worktree's config.worktree to git-before/; given that
# JSON, it copies the two and each new worktree's config.worktree to git-after/ and prints a
# `changed:` line for each path that differs (for the two config files, each entry outside the
# branch-tracking allowlist that was added or removed; for a worktree's entry new or removed
# during the call, each file that isn't in the shape git gives it), a `moved:` line for each ref
# but the branch's own that moved, and a `program:` line for a submodule config under the
# worktree's git dir that names a program or a hooks entry there: /implement's own git add and
# commit, unsandboxed, would read them, and their -c flags cover only core.fsmonitor and
# core.hooksPath.
snapshot() {
  python3 - "$plugin_root/hooks/git-read.py" "$common" "$git_dir" "$work" "$run" "$@" <<'PY'
import collections, hashlib, importlib.util, json, os, re, shutil, stat, subprocess, sys

spec = importlib.util.spec_from_file_location("git_read", sys.argv.pop(1))
git_read = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git_read)
common, git_dir, work, run = sys.argv[1:5]
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

# The shared config's files, compared by git's parse of a copy rather than byte for byte.
CONFIGS = ("config", "config.worktree")
# Branch tracking the user's own git writes: the last part, since a branch name can hold dots.
TRACKING = re.compile(r"branch\..+\.(remote|pushremote|merge|rebase|description)")
PLAIN = re.compile(r"[0-7]+ [0-9a-f]{64}")

def worktrees():
    """The names under worktrees/, one per linked worktree's entry."""
    return [os.path.basename(p) for p in children(os.path.join(common, "worktrees"))]

def wt_config(wid):
    return os.path.join("worktrees", wid, "config.worktree")

def copy(to, wids):
    """CONFIGS and each of `wids`' config.worktree, those that are plain files, copied into `to`,
    made afresh, at the same paths under it as under the common dir."""
    shutil.rmtree(to, ignore_errors=True)
    os.makedirs(to, mode=0o700)
    for name in [*CONFIGS, *map(wt_config, wids)]:
        src, dst = os.path.join(common, name), os.path.join(to, name)
        try:
            if stat.S_ISREG(os.lstat(src).st_mode):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
        except FileNotFoundError:
            pass

def read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None

def entries(path):
    """git's own parse of a copy, as (key, value) pairs, value None for a key with no value: from
    the run dir, with no system or global config, no repo above it and no include followed, so it
    runs nothing a config sets. A missing copy is empty; None if git can't parse it."""
    if not os.path.exists(path):
        return []
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null",
               GIT_CEILING_DIRECTORIES=os.path.dirname(run))
    listed = subprocess.run(["git", "config", "--file", path, "--no-includes", "--list", "-z"],
                            cwd=run, env=env, capture_output=True, check=False)
    if listed.returncode:
        return None
    found = []
    # Each record is key\nvalue\0, or key\0 for a key with no value.
    for record in listed.stdout.split(b"\0")[:-1]:
        key, newline, value = record.decode(errors="surrogateescape").partition("\n")
        found.append((key, value if newline else None))
    return found

def tracking(key, value, was):
    """Whether an added entry is branch tracking with a value git's own commands would write."""
    m = TRACKING.fullmatch(key)
    if not m or value is None:
        return bool(m) and m[1] == "description"
    if m[1] in ("remote", "pushremote"):
        return value == "." or f"remote.{value}.url" in {k for k, _ in was}
    if m[1] == "merge":
        return value.startswith("refs/")
    if m[1] == "rebase":
        return value in ("true", "false", "merges")
    return True

def config_changes(name, old, new):
    """`changed:` lines for one of CONFIGS, given its state before and now."""
    path = os.path.join(common, name)
    plain = all(s == "missing" or PLAIN.fullmatch(s) for s in (old, new))
    if not plain or "missing" not in (old, new) and old.split()[0] != new.split()[0]:
        return [f"changed: {path}"] if old != new else []
    copies = [os.path.join(run, side, name) for side in ("git-before", "git-after")]
    if read(copies[0]) == read(copies[1]):
        return []
    was, now = map(entries, copies)
    if was is None or now is None:
        return [f"changed: {path} (git can't parse it)"]
    was_n, now_n = collections.Counter(was), collections.Counter(now)
    bad = {k for k, _ in was_n - now_n if not k.startswith("branch.")}
    bad |= {k for k, v in now_n - was_n if not tracking(k, v, was)}
    return [f"changed: {path} sets {k}" for k in sorted(bad)]

def truthy(value):
    """A config value as git reads a bool; a key with no value is true."""
    if value is None or value.lower() in ("true", "yes", "on"):
        return True
    try:
        return int(value) != 0
    except ValueError:
        return False

def regular(path):
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except OSError:
        return False

def text(path):
    """A plain file's text, one trailing newline dropped; None if it isn't a plain file."""
    if not regular(path):
        return None
    with open(path, errors="surrogateescape") as f:
        content = f.read()
    return content[:-1] if content.endswith("\n") else content

def inside(path, top):
    return path == top or path.startswith(top + os.sep)

def new_worktree(wid, sources):
    """`changed:` lines for a worktrees/<id>/ entry made during the call, unless it has the shape
    `git worktree add` gives it: commondir ../.., gitdir an absolute <P>/.git outside the
    implementer's worktree, run dir and scratch dir, whose file points back here, and no
    config.worktree, or one that is some worktree's before copy as git filters it. `sources` are
    those copies' entries."""
    top = os.path.join(common, "worktrees", wid)
    if os.path.islink(top) or not os.path.isdir(top):
        return [f"changed: {top}"]
    out = []
    if text(os.path.join(top, "commondir")) != "../..":
        out.append(f"changed: {top}/commondir")
    dotgit = text(os.path.join(top, "gitdir")) or ""
    shaped = os.path.isabs(dotgit) and os.path.basename(dotgit) == ".git"
    if shaped:
        fences = [os.path.realpath(p) for p in (work, run, os.path.join(os.path.dirname(run), "scratch"))]
        checkout = os.path.realpath(os.path.dirname(dotgit))
        pointer = text(dotgit) or ""
        shaped = (not any(inside(checkout, f) for f in fences) and pointer.startswith("gitdir: ")
                  and os.path.realpath(pointer[len("gitdir: "):]) == top)
    if not shaped:
        out.append(f"changed: {top}/gitdir")
    live = os.path.join(common, wt_config(wid))
    if os.path.lexists(live):
        found = entries(os.path.join(run, "git-after", wt_config(wid))) if regular(live) else None
        if found is None or collections.Counter(found) not in sources:
            out.append(f"changed: {live}")
    return out

def filtered(found):
    """A config.worktree's entries as `git worktree add` copies them: no core.worktree, and no
    core.bare = true if core.bare reads as true."""
    bare = [v for k, v in found if k == "core.bare"]
    drop_bare = bool(bare) and truthy(bare[-1])
    return collections.Counter(
        (k, v) for k, v in found
        if k != "core.worktree" and not (drop_bare and k == "core.bare" and v == "true")
    )

if len(sys.argv) == 5:
    state_now, wids = watched(), worktrees()
    copy(os.path.join(run, "git-before"), wids)
    print(json.dumps({"watched": state_now, "refs": refs(), "worktrees": wids}))
else:
    before = json.load(open(sys.argv[5]))  # a file: every ref is too long for argv
    now, wids = watched(), worktrees()
    new_ids = sorted(set(wids) - set(before["worktrees"]))
    copy(os.path.join(run, "git-after"), new_ids)
    configs = {os.path.join(common, n): n for n in CONFIGS}
    # A worktree's entry gone as a whole, but for the implementer's own, or new: by the rules
    # below, not byte for byte.
    gone = set(before["worktrees"]) - set(wids)
    by_rule = [os.path.join(common, "worktrees", w) for w in [*new_ids, *gone]]
    by_rule = [top for top in by_rule if os.path.realpath(top) != git_dir]
    # What git may copy a new worktree's config.worktree from: any worktree's before copy, since
    # it copies the one `git worktree add` ran in.
    sources = []
    for name in ["config.worktree", *map(wt_config, before["worktrees"])] if new_ids else []:
        copied = os.path.join(run, "git-before", name)
        found = entries(copied) if os.path.exists(copied) else None
        if found is not None:
            sources.append(filtered(found))
    for wid in new_ids:
        for line in new_worktree(wid, sources):
            print(line)
    for path in sorted(set(now) | set(before["watched"])):
        old, new = before["watched"].get(path, "missing"), now.get(path, "missing")
        if any(inside(path, top) for top in by_rule):
            continue
        if path in configs:
            for line in config_changes(configs[path], old, new):
                print(line)
        elif new != old:
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

# The ledger line for a call's result, given run.json and the event (end or settled): the
# result's session_id and total_cost_usd, from which ledger.py charges the call's own share of the
# session's running total. With no finite, non-negative total, an end charges the whole budget,
# and a settled line is nothing: the call stays charged its budget. A result with a total but no
# session_id is charged its total.
end_line() {
  python3 - "$1" "$2" "$call" "$budget" <<'PY'
import json, math, sys
path, event, call, budget = sys.argv[1:]
try:
    result = json.load(open(path))
    cost, session = result.get("total_cost_usd"), result.get("session_id")
except (OSError, ValueError, AttributeError):
    cost = session = None
line = {"who": "implementer", "call": int(call), "event": event}
ok = isinstance(cost, (int, float)) and not isinstance(cost, bool) and math.isfinite(cost) and cost >= 0
if not ok and event == "settled":
    sys.exit(0)  # nothing to settle with: the call stays charged its budget
if not ok:
    line.update(usd=float(budget), no_total=True)
elif isinstance(session, str) and session:
    line.update(session=session, total=cost)
else:
    line.update(usd=cost)
print(json.dumps(line))
PY
}

# The ledger's hash: nothing but this script writes the ledger, so a change since this script's own
# last write is a write the sandbox should have stopped.
sha() { shasum -a 256 < "$ledger" | cut -d' ' -f1; }
ledger_unchanged() {
  [ "$(sha)" = "$before" ] && return 0
  echo "run-implementer: exit 4: the ledger $ledger changed during the call; no reply was" \
    "written, so act on nothing from this run" >&2
  return 1
}
# Exit 4 on anything that can make git run a program or point elsewhere; refs are only named.
git_unchanged() {
  local diff changed
  diff=$(snapshot "$run/snapshot.json") || diff="changed: couldn't read the repo's git config and hooks after the call"
  # The copies can hold a token in a remote's URL.
  rm -rf "$run/git-before" "$run/git-after"
  sed -n 's/^moved: /run-implementer: moved during the run: /p' <<< "$diff"
  changed=$(grep -v -e '^moved: ' -e '^$' <<< "$diff" || true)
  [ -z "$changed" ] && return 0
  sed 's/^/run-implementer: /' <<< "$changed" >&2
  echo "run-implementer: exit 4: the call changed the repo's git config, hooks or pointers, named" \
    "above; no reply was written: act on nothing, and run no git command in the repo or the" \
    "worktree until the user has checked them" >&2
  return 1
}

# Interruptions. claude runs in the background, in this script's process group, so nothing
# outlives a stopped task, and this trap runs at once: bash runs a trap while it is in `wait`,
# where it would hold one until a foreground child exits. Stopping a background task sends TERM to
# the group, and KILL about 1.5 seconds later, so the trap charges the call its budget first;
# then it sends claude INT, which ends its turn with a result carrying its cost if it still can,
# and if one comes, settles the call at that cost. Exit 6, with no reply.
pid=
# Waits up to $1 seconds for claude to exit. bash reaps an exited child itself, even in a trap, so
# kill -0 stops finding it.
exits_within() {
  local ticks=$(($1 * 10))
  while kill -0 "$pid" 2>/dev/null; do
    [ "$ticks" -gt 0 ] || return 1
    ticks=$((ticks - 1))
    sleep 0.1
  done
}
# INT, then TERM after $wait_s seconds, then KILL after one more.
stop_claude() {
  [ -n "$pid" ] || return 0
  kill -INT "$pid" 2>/dev/null || true
  if ! exits_within "$wait_s"; then
    kill -TERM "$pid" 2>/dev/null || true
    exits_within 1 || kill -KILL "$pid" 2>/dev/null || true
  fi
  wait "$pid" 2>/dev/null || true
}
interrupted() {
  # The children this starts ignore the signals too, so a second TERM can't cut a ledger write.
  trap '' INT TERM HUP
  if ! ledger_unchanged; then stop_claude; exit 4; fi
  "$ledger_py" interrupt "$run_name" "$call" "$budget" ||
    echo "run-implementer: couldn't write call $call's interrupted end line to $ledger" >&2
  before=$(sha)
  stop_claude
  ledger_unchanged || exit 4
  local line charged="its whole budget, \$$budget, as its cost is unknown"
  line=$(end_line "$run/run.json" settled)
  if [ -n "$line" ]; then
    if "$ledger_py" append "$run_name" "$line"; then
      charged=$("$ledger_py" report "$run_name" |
        sed -n 's/^implementer call '"$call"': \(\$[0-9.]*\), settled$/\1, its cost from its result/p')
    else
      echo "run-implementer: couldn't settle call $call; it stays charged its budget" >&2
    fi
    before=$(sha)
  fi
  git_unchanged || exit 4
  echo "run-implementer: exit 6: call $call was interrupted, and is charged $charged. No reply" \
    "was written; /implement <spec> carries on from the last committed work item." >&2
  exit 6
}

# The snapshot first: if it can't be taken, the call never starts, so nothing is charged. Its
# config copies go on any exit, if the after-call check hasn't removed them already.
trap 'rm -rf "$run/git-before" "$run/git-after"' EXIT
snapshot > "$run/snapshot.json" || die "couldn't read the repo's git config and hooks before the call"
call=$("$ledger_py" next-call "$run_name") || die "couldn't read the ledger $ledger"
"$ledger_py" append "$run_name" \
  "{\"who\": \"implementer\", \"call\": $call, \"event\": \"start\", \"budget\": $budget}" ||
  die "couldn't write the ledger $ledger"
before=$(sha)
trap interrupted INT TERM HUP

cd "$work"
status=0
claude -p --agents "$run/agents.json" --agent implementer --output-format json --max-turns 400 \
  --max-budget-usd "$budget" --allowedTools "$tools" --permission-mode acceptEdits \
  --setting-sources user --settings "$run/settings.json" --add-dir "$scratch" --strict-mcp-config \
  ${model[@]+"${model[@]}"} ${resume[@]+"${resume[@]}"} \
  -- "$prompt" < /dev/null > "$run/run.json" 2> "$run/run.err" &
pid=$!
wait "$pid" || status=$?
# The call is over: a signal now would have the trap charge it again, against a stale hash.
trap '' INT TERM HUP

ledger_unchanged || exit 4
"$ledger_py" append "$run_name" "$(end_line "$run/run.json" end)" ||
  die "couldn't write the ledger's end line for call $call to $ledger"
trap - INT TERM HUP

n=1; while [ -e "$run/run-$n.json" ]; do n=$((n + 1)); done
cp "$run/run.json" "$run/run-$n.json"

git_unchanged || exit 4

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
account_exit run-implementer "$run/run.json"
if [ "$status" -eq 0 ] && ! shape_ok; then
  echo "run-implementer: the implementer finished, but its reply doesn't end with an" \
    "Implementer: line; see $run/reply.md" >&2
  exit 3
fi
echo "run-implementer: finished (exit $status); reply in $run/reply.md"
exit "$status"

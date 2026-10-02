#!/usr/bin/env bash
# Runs the implement-verifier: a sandboxed, cost-capped headless claude session in a scratch
# directory made by prepare-verify.sh, primed with verifier.md. It re-runs each Done when it can on
# the export and checks the diff against the spec, without seeing how the implementation was done.
#
# Usage: run-verify.sh <scratch dir under ~/.cache/implement-verify/>
#
# The scratch dir holds src/, before/W<n>/ and the .patch files from prepare-verify.sh, and
# spec.md, record.md and brief.md from the caller. The run writes run.json (the --output-format
# json result), run.err and reply.md (the verifier's reply) there.
#
# Exit 0: reply.md ends with the closing lines verifier.md asks for (`Verified: N of M` and
# `Implementation holds: yes|no`). Exit 2: the run couldn't start. Exit 3: the run finished, but
# reply.md lacks them (an API error, a budget stop, a verifier that ignored its format): don't
# read it as a verdict. Exit 4: the run left reply.md, run.json or run.err as a symlink, or as
# anything else but a regular file, which the script removes unread; or it changed an input the
# verifier reads (brief.md, spec.md, record.md, diff.patch, a diff-W<n>.patch, diff-other.patch).
# Either way the caller reads none of the run's files. 4 comes before 3 and before claude's own
# status, and stays 4 even if the removal fails. Any other non-zero exit is claude's own, with
# run.err saying why.
#
# Each run appends a `verifier V<n>` line to the spec's implement ledger (ledger.py beside this
# script; run name `<repo>--<spec>` from the scratch layout): run.json's total_cost_usd, or null on
# exit 4, when it reads nothing. The line doesn't count toward the implementer's cap; it's there so
# the cost report reads one file. A ledger that refuses the line is reported, not fatal.
#
# Capped at $5 and 100 turns. On the user's default model, or on $RUN_AGENT_MODEL if it's set, as
# hooks/run-agent.sh does, so the evals' per-model runs reach it. The sandbox is
# verify-settings.json beside this script's directory: the spike settings, with no network.
set -euo pipefail

die() { echo "run-verify: $*" >&2; exit 2; }
# The ledger line for this run: its cost (a number, or null) and a note. Set once the scratch path
# is checked; until then there is no run to record.
ledger() {
  [ -n "${run_name:-}" ] || return 0
  "$here/scripts/ledger.py" append "$run_name" \
    "{\"who\": \"verifier $verifier_n\", \"usd\": $1, \"note\": \"$2\"}" ||
    echo "run-verify: couldn't add this run's line to the ledger of $run_name" >&2
}
refuse() {
  ledger null "refused: exit 4, nothing read"
  echo "run-verify: exit 4: record this verification as refused, and read none of its files" >&2
  exit 4
}

[ $# -eq 1 ] || die "usage: run-verify.sh <scratch dir>"
name='[A-Za-z0-9][A-Za-z0-9._-]*'
layout="^$name/$name/V[0-9]+$"
root="$HOME/.cache/implement-verify"
real_root=$(cd "$root" 2>/dev/null && pwd -P) || real_root=$root

# First the path as given, before anything resolves it, so a path elsewhere is refused for what
# it is whether or not it exists. Either spelling of the root: as written, or resolved.
case "$1" in
  "$root"/*) rest=${1#"$root"/} ;;
  "$real_root"/*) rest=${1#"$real_root"/} ;;
  *) die "not under ~/.cache/implement-verify/: $1" ;;
esac
[[ $rest =~ $layout ]] || die "scratch must be ~/.cache/implement-verify/<repo>/<spec>/V<n>, not $1"

# Then resolved, so a symlink on the way can't lead out of the root.
[ -d "$real_root" ] || die "no ~/.cache/implement-verify"
scratch=$(cd "$1" 2>/dev/null && pwd -P) || die "no such scratch dir: $1"
case "$scratch" in
  "$real_root"/*) [[ ${scratch#"$real_root"/} =~ $layout ]] ||
    die "$1 resolves to $scratch, outside the layout under $real_root" ;;
  *) die "$1 resolves to $scratch, not under ~/.cache/implement-verify/" ;;
esac
for f in brief.md spec.md diff.patch; do
  [ -f "$scratch/$f" ] && [ ! -L "$scratch/$f" ] || die "missing, or not a plain file: $scratch/$f"
done
[ -d "$scratch/src" ] || die "missing $scratch/src"

# What the verifier reads: the brief, the spec, the record and the diffs. The code a Done when
# runs can write anywhere in the scratch dir, so it could rewrite them to change the verdict. With
# no argument, this prints each one's state as JSON: its sha256, or `missing`, or what it is
# instead of a regular file, which it never reads. With that listing as $1, taken before the run
# and kept in this script's memory, it prints a line for each input that differs. Not before/ or
# src/: the verifier writes there. The names are fixed or `diff-W<n>.patch`, so printing them
# shows nothing the run chose.
inputs() {
  python3 - "$@" <<'PY'
import errno, hashlib, json, os, re, stat, sys

def state(name):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return "missing"
    except OSError as e:
        return "a symlink" if e.errno == errno.ELOOP else f"unreadable ({e.strerror})"
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        return "not a regular file"
    with open(fd, "rb") as f:
        digest = hashlib.sha256()
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
        return digest.hexdigest()

names = {"brief.md", "spec.md", "record.md", "diff.patch", "diff-other.patch"}
problems = []
try:
    names |= {n for n in os.listdir(".") if re.fullmatch(r"diff-W[0-9]+\.patch", n, re.I)}
except OSError as e:
    problems.append(f"run-verify: couldn't list the scratch dir ({e.strerror})")
if len(sys.argv) == 1:
    if problems:
        sys.exit(problems[0])
    print(json.dumps({name: state(name) for name in names}))
else:
    before = json.loads(sys.argv[1])
    for name in sorted(names | set(before)):
        if state(name) != before.get(name, "missing"):
            problems.append(f"run-verify: {name} changed during the run")
    print("\n".join(problems))
PY
}

# The spikes' uv cache, not the user's ~/.cache/uv, for the reason run-spike.sh gives; the
# settings let a run write there and nowhere else outside its scratch dir.
export UV_CACHE_DIR="$HOME/.cache/spec-spikes/.uv-cache"
mkdir -p "$UV_CACHE_DIR"
# No auto memory, as in hooks/run-agent.sh: the verifier checks the work against the spec alone.
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=1

# The prompt and settings sit beside this script's directory, wherever the skill is installed.
here=$(cd "$(dirname "$0")/.." && pwd -P)
verifier=$here/verifier.md
# <repo>/<spec>/V<n> under the root, as checked above.
rel=${scratch#"$real_root"/}
verifier_n=${rel##*/}
rel=${rel%/*}
run_name="${rel%%/*}--${rel#*/}"
settings=$here/verify-settings.json
model=(${RUN_AGENT_MODEL:+--model "$RUN_AGENT_MODEL"})

cd "$scratch"
# The redirects below would follow a link that an earlier, refused run left and couldn't remove.
rm -rf -- reply.md run.json run.err 2>/dev/null || true
for f in reply.md run.json run.err; do
  [ ! -e "$f" ] && [ ! -L "$f" ] || die "couldn't clear $scratch/$f from an earlier run"
done

hashes=$(inputs) || die "couldn't hash the inputs in $scratch"

# --setting-sources user, as in run-spike.sh and hooks/run-agent.sh: no project settings or
# CLAUDE.md above or beside the scratch dir load.
status=0
claude -p --setting-sources user \
  --append-system-prompt-file "$verifier" \
  --settings "$settings" \
  --allowedTools "Read Grep Glob Bash Write(./**) Edit(./**)" \
  --max-budget-usd 5 --max-turns 100 ${model[@]+"${model[@]}"} \
  --output-format json --strict-mcp-config --no-session-persistence \
  "$(cat brief.md)" < /dev/null > run.json 2> run.err || status=$?

# The verifier may write anything in its scratch dir, links included, and so may the code it
# runs: the sandbox stops them reading ~/.ssh, but not linking to it. This script then writes
# reply.md, outside the sandbox, and /implement's session reads all three files. So each must be
# a regular file, or nothing. Anything else is removed (a link, not what it points to) before
# something follows it. Its target isn't printed: the run chose it, and this output reaches
# /implement's session.
refused=0
for f in reply.md run.json run.err; do
  if [ -L "$f" ]; then
    what="a symlink"
  elif [ -e "$f" ] && [ ! -f "$f" ]; then
    what="not a regular file"
  else
    continue
  fi
  refused=1
  # rm's own errors stay quiet: inside a directory, they would print names the run chose.
  if rm -rf -- "$f" 2>/dev/null; then
    echo "run-verify: $scratch/$f was $what; removed it unread" >&2
  else
    echo "run-verify: $scratch/$f was $what; couldn't remove it, so don't read it" >&2
  fi
done
# And the inputs must be as they were: what the verifier read may not be what the caller wrote.
changed=$(inputs "$hashes") || changed="run-verify: couldn't check the inputs after the run"
if [ -n "$changed" ]; then
  refused=1
  echo "$changed" >&2
fi
[ "$refused" -eq 0 ] || refuse

# Neither the read nor the write follows a link, in case a process the run left running makes
# one after the check above: run.json's reply is copied into the record, which gets committed.
written=0
cost=$(python3 - <<'PY'
import errno, json, os, stat, sys

def refuse(name):
    print(f"run-verify: {name} changed into a link or another entry after the check", file=sys.stderr)
    sys.exit(4)

import math
reply = "run-verify: no result; see run.err"
cost = "null"
try:
    fd = os.open("run.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        refuse("run.json")
    with open(fd, "rb") as f:
        d = json.loads(f.read())
    reply = d.get("result") or f"run-verify: the run ended with subtype {d.get('subtype')!r} and no reply"
    usd = d.get("total_cost_usd")
    if isinstance(usd, (int, float)) and not isinstance(usd, bool) and math.isfinite(usd) and usd >= 0:
        cost = json.dumps(usd)
except OSError as e:
    if e.errno == errno.ELOOP:
        refuse("run.json")
except (ValueError, AttributeError):
    pass
# Removed, then made afresh: O_EXCL fails on anything at the name, a link included.
try:
    os.unlink("reply.md")
except FileNotFoundError:
    pass
except OSError:
    refuse("reply.md")
try:
    fd = os.open("reply.md", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
except OSError:
    refuse("reply.md")
with open(fd, "w") as f:
    f.write(reply + "\n")
print(cost)
PY
) || written=$?
[ "$written" -ne 4 ] || refuse
[ "$written" -eq 0 ] || exit "$written"
ledger "$cost" "finished: claude exit $status"

# The closing lines verifier.md tells it to reply with. A reply without them is not a verdict.
shape_ok() {
  python3 - <<'PY'
import re, sys
reply = open("reply.md").read()
shape = [r"Verified: \d+ of \d+", r"Implementation holds: (yes|no)"]
missing = [p for p in shape if not re.search(p, reply)]
if missing:
    print("missing " + "; ".join(missing), file=sys.stderr)
sys.exit(1 if missing else 0)
PY
}
if [ "$status" -eq 0 ] && ! shape_ok; then
  echo "run-verify: the verifier finished, but its reply isn't in the shape verifier.md asks" \
    "for; see $scratch/reply.md" >&2
  exit 3
fi
echo "run-verify: finished (exit $status); reply in $scratch/reply.md"
exit "$status"

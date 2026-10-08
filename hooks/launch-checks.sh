# shellcheck shell=bash
# The checks every launcher makes before it starts a headless claude session, and after it: sourced
# by hooks/run-agent.sh, skills/spec/scripts/run-spike.sh, skills/implement/scripts/run-implementer.sh,
# skills/implement/scripts/run-verify.sh and both eval runners. Defines functions only; each launcher
# calls them where it needs them.
#
# Accounts. In claude -p an ANTHROPIC_API_KEY in the environment is used whenever it's set, ahead of
# the user's /login account and CLAUDE_CODE_OAUTH_TOKEN, and so is an apiKeyHelper or a key in the
# env block of the user's settings. So unless CHECKED_PLANS_USE_API_KEY=1 is set, launch_account
# unsets the key, and account_settings writes settings that switch off the other two. A run that
# then finds no account is told how to get one (account_exit). The plugin
# launchers exit 5 for it. ANTHROPIC_AUTH_TOKEN and the cloud-provider variables are left alone:
# they are a route an organization chose, not a stray key.
#
# Version. The sandbox rule the launchers rely on holds from Claude Code 2.1.277 (README, Safety and
# cost), so launch_version refuses anything older, or a version it can't read, before the launcher
# does anything else.

# launch_version <launcher>: runs `claude --version` once and exits 2 unless its first field is
# 2.1.277 or later, printing what it read.
launch_version() {
  local found
  found=$(claude --version 2>/dev/null | head -n 1) || true
  if ! python3 - "$found" <<'PY'
import re, sys

fields = sys.argv[1].split()
m = re.fullmatch(r"[0-9]+(\.[0-9]+)*", fields[0]) if fields else None
sys.exit(0 if m and tuple(map(int, fields[0].split("."))) >= (2, 1, 277) else 1)
PY
  then
    echo "$1: needs Claude Code 2.1.277 or later; this is ${found:-unreadable}" >&2
    exit 2
  fi
}

# launch_account <launcher>: unsets ANTHROPIC_API_KEY, unless the opt-in is set, and says so in
# one line if it held a key. An empty one, as a session under account_settings' override passes
# to the commands it runs, is no key: it's unset without a note.
launch_account() {
  [ "${CHECKED_PLANS_USE_API_KEY:-}" = 1 ] && return 0
  if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    echo "$1: this run uses your Claude account, not ANTHROPIC_API_KEY" \
      "(set CHECKED_PLANS_USE_API_KEY=1 to bill the key)" >&2
  fi
  unset ANTHROPIC_API_KEY
  return 0
}

# account_settings <from> <to>: writes the settings in <from> (a file, or - for stdin) to <to>, with
# "apiKeyHelper": "" and "env": {"ANTHROPIC_API_KEY": ""} added unless the opt-in is set. <to> is
# cleared first and written without following a link, so a link a sandboxed run left at that name
# is replaced, not written through. <from> and <to> may be the same file.
account_settings() {
  # The script is python3's stdin, so stdin's settings go as an argument.
  local given=
  if [ "$1" = - ]; then given=$(cat) || return 1; fi
  python3 - "$1" "$2" "${CHECKED_PLANS_USE_API_KEY:-}" "$given" <<'PY'
import json, os, sys

src, dst, opt_in, given = sys.argv[1:]
try:
    if src == "-":
        settings = json.loads(given)
    else:
        with open(src) as f:
            settings = json.load(f)
except (OSError, ValueError) as e:
    sys.exit(f"couldn't read the settings {src}: {e.__class__.__name__}")
if not isinstance(settings, dict):
    sys.exit(f"the settings {src} aren't a JSON object")
if opt_in != "1":
    settings["apiKeyHelper"] = ""
    env = settings.get("env") if isinstance(settings.get("env"), dict) else {}
    settings["env"] = {**env, "ANTHROPIC_API_KEY": ""}
try:
    os.unlink(dst)
except FileNotFoundError:
    pass
try:
    fd = os.open(dst, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
except OSError as e:
    sys.exit(f"couldn't write the settings {dst}: {e.strerror}")
with open(fd, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
PY
}

# account_override: the override alone, as JSON for --settings, for a launcher that passes no
# settings file; nothing under the opt-in.
account_override() {
  [ "${CHECKED_PLANS_USE_API_KEY:-}" = 1 ] || echo '{"apiKeyHelper": "", "env": {"ANTHROPIC_API_KEY": ""}}'
}

# account_failed <run.json>: true if the run found no account to use: is_error, and a result that
# begins with one of the messages claude gives for it (spikes S2 to S4 of
# docs/specs/2026-10-07-usability-1b-which-account-pays.md; its subtype still says success). The
# file isn't read through a link.
account_failed() {
  python3 - "$1" <<'PY'
import json, os, stat, sys

MESSAGES = ("Not logged in", "Failed to authenticate", "Invalid API key", "Login expired")
try:
    fd = os.open(sys.argv[1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with open(fd, "rb") as f:
        if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
            sys.exit(1)
        d = json.loads(f.read())
except (OSError, ValueError):
    sys.exit(1)
text = d.get("result") if isinstance(d, dict) else None
failed = d.get("is_error") is True and isinstance(text, str) and text.lstrip().startswith(MESSAGES)
sys.exit(0 if failed else 1)
PY
}

# account_exit <launcher> <run.json>: if the run found no account (account_failed), says how to
# give it one, on stderr, and exits 5, as the plugin launchers do. Under the opt-in the run was on
# ANTHROPIC_API_KEY, so that's what to check.
account_exit() {
  account_failed "$2" || return 0
  if [ "${CHECKED_PLANS_USE_API_KEY:-}" = 1 ]; then
    echo "$1: exit 5: the run couldn't authenticate with ANTHROPIC_API_KEY, which" \
      "CHECKED_PLANS_USE_API_KEY=1 bills. Check the key; or unset CHECKED_PLANS_USE_API_KEY to" \
      "run on your Claude account (/login in Claude Code, or \`claude setup-token\` and" \
      "CLAUDE_CODE_OAUTH_TOKEN)." >&2
    exit 5
  fi
  echo "$1: exit 5: the run found no Claude account to use. Run /login in Claude Code; or run" \
    "\`claude setup-token\` and set CLAUDE_CODE_OAUTH_TOKEN to the token it prints; or set" \
    "CHECKED_PLANS_USE_API_KEY=1 to bill ANTHROPIC_API_KEY instead." >&2
  exit 5
}

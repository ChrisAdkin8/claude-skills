#!/usr/bin/env python3
"""PreToolUse guard for the /research and /spec agents (researcher, research-verifier,
spec-verifier, spec-reviewer).

Their safety rules say: no cloud CLIs, GitHub and git read-only, and (for the researcher) write
only notes in ~/notes/research. This makes those rules hold when a fetched page carries
instructions, and even though ~/.claude/settings.json pre-approves some cloud reads.

Bash commands are checked against an allowlist: every command word, including those inside
pipelines, lists, braces, if/while bodies and $(...) substitutions, must be a reading tool, curl,
gh, git or one of the skill scripts, and those have per-command limits (GET only, no file
writes). It's a guard against injected instructions, not a sandbox: data can still leave in a
GET request's URL.

Usage, from an agent's frontmatter hooks:
  agent-guard.py bash            Bash tool
  agent-guard.py write <dir>     Write/Edit tools: allow only files under <dir>

Reads the hook's JSON on stdin. Exit 0 allows; exit 2 blocks and tells the agent why on stderr.
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import NoReturn

HOME = Path.home()
SCRIPTS = {
    HOME / ".claude/skills/research/scripts/repo-health.sh",
    HOME / ".claude/skills/research/scripts/check-note.py",
    HOME / ".claude/skills/research/scripts/gcp-skus.sh",
    HOME / ".claude/skills/research/scripts/reddit-search.sh",
    HOME / ".claude/skills/spec/scripts/check-spec.py",
}
# Reading and text tools that can't run other programs or write files (the flags that would
# are checked below).
READERS = {
    "cat", "head", "tail", "wc", "sort", "uniq", "cut", "tr", "grep", "egrep", "fgrep", "rg",
    "jq", "diff", "comm", "paste", "column", "nl", "fold", "iconv", "basename", "dirname",
    "realpath", "readlink", "ls", "stat", "file", "du", "echo", "printf", "true", "false",
    "test", "[", "date", "pwd", "cd", "sleep", "base64", "zcat", "gunzip", "gzip", "od",
    "shasum", "md5", "sha256sum", "sed", "find", ":", "[[",
}  # fmt: skip
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
GIT_BAD_ARGS = ("--output", "-O", "--open-files-in-pager", "--exec-path", "--ext-diff")
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
    "--stderr", "--etag-save", "--hsts", "--alt-svc",
)  # fmt: skip
PUNCT = set("();<>|&")


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


def unwrap(argv):
    """Strip assignments, shell keywords and wrappers like timeout, returning the real command."""
    while argv:
        word = argv[0]
        if re.fullmatch(r"[A-Za-z_]\w*=.*", word) or word in KEYWORDS:
            argv = argv[1:]
            continue
        name = os.path.basename(word)
        if name not in WRAPPERS:
            return argv
        if name == "env" and any(a in ("-S", "--split-string") for a in argv[1:]):
            block("`env -S` hides the command it runs")
        with_value, rest = WRAPPERS[name], argv[1:]
        while rest and (
            rest[0].startswith("-") or re.fullmatch(r"[A-Za-z_]\w*=.*", rest[0])
        ):
            rest = rest[2:] if rest[0] in with_value else rest[1:]
        if name == "timeout" and rest:
            rest = rest[1:]  # the duration
        argv = rest
    return argv


def check_gh(args, raw, expands):
    sub = tuple(a for a in args[:2] if not a.startswith("-"))
    if not any(sub[: len(allowed)] == allowed for allowed in GH_READ):
        block(f"`gh {' '.join(sub)}` can change GitHub; only read commands are allowed")
    if sub[:1] != ("api",):
        return
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
        if (
            args[i] == "-c"
            or args[i].startswith("--config-env")
            or args[i] == "--exec-path"
        ):
            block("`git -c` can run arbitrary programs through aliases; not allowed")
        i += 2 if args[i] in ("-C", "--git-dir", "--work-tree") else 1
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


def check_curl(args):
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
    if name == "sed":
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


def check_command(command, depth=0):
    if depth > 4:
        block("commands nested too deeply to check")
    subs, expands = substitutions(command)
    for sub in subs:
        check_command(sub, depth + 1)
    for argv in simple_commands(tokens(command)):
        argv = unwrap(argv)
        if not argv or argv[0].startswith("#"):
            continue
        if argv[0] in ("for", "select"):
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
                check_command(args[1], depth + 1)
                continue
            if Path(args[0]).expanduser().resolve() in SCRIPTS:
                continue
            block(f"`{name}` may only run the /research and /spec skill scripts")
        if name == "eval":
            check_command(" ".join(args), depth + 1)
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
            check_gh(args, command, expands)
        elif name == "git":
            check_git(args)
        elif name == "curl":
            check_curl(args)
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
    if mode == "bash":
        check_command(tool_input.get("command", ""))
    elif mode == "write" and len(sys.argv) > 2:
        check_write(tool_input.get("file_path", ""), sys.argv[2])
    else:
        block(f"agent-guard called with unknown mode {mode!r}")
    sys.exit(0)


if __name__ == "__main__":
    main()

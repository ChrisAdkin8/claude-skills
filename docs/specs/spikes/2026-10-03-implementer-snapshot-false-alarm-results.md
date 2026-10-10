# Spike results: The implementer's snapshot lets the user's own branch tracking and worktrees through

## S1

### Does `git config --file <copy> --no-includes --list -z`, run as Design says (from the run dir, with `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null` and `GIT_CEILING_DIRECTORIES`), run nothing when the copy sets `core.fsmonitor`, `core.pager`, a `!` alias and `include.path`, and list every entry?

Expect: with the three env settings, the listing shows every entry of the copy, follows no include, and touches no marker, both outside any repo and with `$HOME` inside a repo whose config sets `core.fsmonitor`.
Runs: 1

#### Commands

Setup in `exp/`: `copy.cfg` has core.fsmonitor/pager/editor/sshCommand, `alias.x = !touch ...`, `include.path`, `includeIf "gitdir:/"`, a repeated key (user.name x2, multi.k x2) and a valueless key (multi.empty). Every command touches a marker in `exp/out/`. `inc.cfg` holds `included.key`. git 2.54.0 (Apple Git-157).

```
# run 1: cwd outside any repo
(cd run1 && env GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CEILING_DIRECTORIES=$E HOME=$E/run1 \
  git config --file $E/copy.cfg --no-includes --list -z | tr '\0' '\n')
ls out

# run 2 setup: exp/home is a repo (gitfile .git -> home-git) whose config sets
# core.fsmonitor, core.pager and alias.x to touch markers
# instrument check: `git status` in home/work
(cd home/work && git status --short); ls out

# run 2: HOME=exp/home, cwd=exp/home/work, same three env settings
(cd home/work && env GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_CEILING_DIRECTORIES=$E HOME=$E/home \
  git config --file $E/copy.cfg --no-includes --list -z | tr '\0' '\n' | grep -c .); ls out
# variant: GIT_CEILING_DIRECTORIES=$E/home/work (also checked repo discovery with rev-parse)
```

#### Output

Run 1 listing (23 lines, keys and values alternate), `ls out` printed nothing after it:
```
core.fsmonitor / touch .../m_fsmonitor
core.pager / touch .../m_pager
core.editor / touch .../m_editor
core.sshcommand / touch .../m_ssh
alias.x / !touch .../m_alias
include.path / .../inc.cfg
includeif.gitdir:/.path / .../inc.cfg
user.name / A B
user.name / second
multi.k / 1
multi.k / 2
multi.empty
rc=0
```
No `included.key` line. Markers in `out/`: none.

Instrument check (plain `git status` in the home repo): `out/` then held `m_home_fsmonitor`, so the home repo's fsmonitor does fire when git reads that repo's config.

Run 2 (marker deleted first): 23 lines listed, `ls out` empty. Variant with ceiling at `home/work`: 23 lines, `out` empty. With ceiling `$E`, `git rev-parse --show-toplevel` in `home/work` still found the home repo, so the repo was discoverable.

#### Verdict

EXPECTED: the listing shows all 10 entries (repeats and the valueless key included), follows neither include (no `included.key`), and runs no command. It stayed clean outside a repo and with `$HOME` inside a repo whose config sets `core.fsmonitor`. The home repo's fsmonitor fired under `git status`, so the check could have caught a leak.

#### Notes

- `-z` prints `key\nvalue\0`; a valueless key (`multi.empty`) has no newline or value. W1's parser must handle that.
- `includeif.gitdir:/.path` is listed raw; `--no-includes` didn't evaluate it.
- Not tested: a repo-local config is read by `--list` only without `--file`, so it is moot here.

total_cost_usd: 0.1600944
num_turns: 5

---
title: Install the skills from the Claude Code plugin marketplace, part 2: cutover
created: 2026-09-29
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: c05ef6a
cite-repo: none # this repo cites itself
---

# Install the skills from the Claude Code plugin marketplace, part 2: cutover

Prerequisite: part 1, `docs/specs/2026-09-29-plugin-marketplace-1-plumbing.md`. Its W1 and W2 add the manifests and make the scripts, guard, agent files and settings root-relative, accepting both path spellings; this part changes the skills that call them. Split from [2026-09-29-plugin-marketplace](2026-09-29-plugin-marketplace.md) (now superseded), which holds the history before the split. This is part 2 of 2: W3 to W6.

## Goal

The four skills, the tests, the docs and the release stop depending on the `~/.claude/skills` and `~/.claude/hooks` symlinks, which go away. When both parts are done, `/plugin marketplace add ChrisAdkin8/claude-skills` and `/plugin install claude-skills@claude-skills` give a user `idea`, `research`, `spec` and `cold-review`, working, from Claude Code's plugin cache, and every path a skill, script, agent or test uses to find another file in the repo stops depending on the symlinks.

## Decision

Part 1's Decision applies: the repo root is the plugin and its own marketplace, the agent files stay in `hooks/agents/`, and root indirection uses two mechanisms. This part adds:

- **Plugin only.** The symlink install is retired. Development runs the checkout with `claude --plugin-dir .`. Chosen by the user on 2026-09-29. Rejected: supporting both, because `${CLAUDE_PLUGIN_ROOT}` can't expand under a symlink install, so every `allowed-tools` line would need both path spellings and every test would cover two layouts.
- **`~/notes` stays hardcoded for v1** and is documented as a prerequisite. Rejected for now: `userConfig` for the notes directory, which touches 183 references (`git grep -nE '~/notes|\$HOME/notes'`, excluding `docs/specs/`).
- **Skills answer to their bare names too.** The plugin's skills are named `/claude-skills:spec`, `/claude-skills:research`, `/claude-skills:idea` and `/claude-skills:cold-review` once part 1's W1 names the plugin; the bare `/spec` and the rest also resolve while no other skill has the name (spike 7).

## Background

Read at `c05ef6a` on 2026-09-29: the local `main`, fast-forwarded to the head of the branch `sandbox-denylist-and-skill-fixes` (draft PR #27, open, not yet on `origin/main`, whose tip is `90304a5`). Those six commits change the guard, the sandbox settings, their tests and other files this spec edits, so every fact below holds only once PR #27 merges. An earlier draft was read at `90304a5`, where the counts were 129 live references, 61 dated and 178 `~/notes`; the facts were re-read at `0c85bc9`, and `c05ef6a` differs from that only by 71 added lines in `tests/agent-evals/BASELINE.md`, which no citation touches.

**How the repo finds itself today.** `CLAUDE.md:3` and `:33` say `~/.claude/skills` and `hooks` are symlinks into the repo and that files refer to each other by `~/.claude/...` paths. The README's install links them by hand (`README.md:85-86`), and CI does the same (`.github/workflows/tests.yml:21-24`). A grep for `~/.claude/{skills,hooks,agents}`, `$HOME/.claude/...` and `.claude/skills|hooks`, excluding `docs/specs/`, any `records/` directory, `CHANGELOG.md`, `BASELINE.md`, `.git` and `skills/synced/`, finds 141 lines in 40 files (`git grep -InE` for that pattern over tracked files, with those exclusions; a plain `grep -r` also reads the untracked `tests/*/results/` and finds 483); the same references inside those excluded, dated files number 62 (`git grep -InE` with the same pattern over tracked `docs/specs/`, `records/`, `CHANGELOG.md` and `tests/agent-evals/BASELINE.md`).

**Skills.** Each skill's permissions are its `allowed-tools` frontmatter line, with literal `~/.claude/...` patterns for the helper scripts and `git-read.py`: `skills/spec/SKILL.md:6-9`, `skills/research/SKILL.md:6`, `skills/cold-review/SKILL.md:6`. `skills/idea/SKILL.md:5` names no plugin file, so it needs no path change. Skills tell the model to write paths with `~`, not expanded, because the patterns are written that way (`skills/spec/spike-step.md:16`).

**Tests and evals.** The skill evals run `claude -p` with a `prompt.txt` that types `/cold-review ...` (`tests/skill-evals/run.sh:73-74`, `tests/skill-evals/cases/cold-review-delta/prompt.txt:1`).

**Plugin behaviour, from the docs and the spikes.** `${CLAUDE_PLUGIN_ROOT}` is expanded in hook commands and in skill, command and agent markdown ([manifest reference](https://code.claude.com/docs/en/plugins/manifest-reference.md)); the docs don't say whether it is expanded in `allowed-tools` frontmatter, and spike 1 found that it is, under `--plugin-dir` (`docs/specs/spikes/2026-09-29-plugin-marketplace-2-cutover-results.md`). Plugins can't ship permission or sandbox settings *(unverified)*.

## Non-goals

- Making `~/notes` configurable, or the plugin usable without it.
- Shipping the user-level deny rules in `~/.claude/settings.json`: plugins can't. The README documents them instead.
- Rewriting dated documents: `docs/specs/`, `records/`, `CHANGELOG.md`, `tests/agent-evals/BASELINE.md`. They keep the paths they were written with.
- Changing what any skill does, or the steps in any skill file beyond its paths.
- Renaming the 107 mentions of `/spec`, `/research`, `/idea` and `/cold-review` in the README, docs and skills (`git grep -nEI '`/(spec|research|idea|cold-review)([ `]|$)|/(spec|research|idea|cold-review) (quick|ideas|finish|spike|done|prompt)' -- . ':!docs/specs' ':!records' ':!CHANGELOG.md' ':!tests/agent-evals/BASELINE.md'` finds 107 lines, and the same command with `-l` finds 23 files): the bare names still resolve (spike 7), so only the eval prompts and W3's Done when use the namespaced form.

## Design

Part 1's Design applies to the scripts, the settings renderer, `agent-def.py` and the guard.

- **Skills** use `${CLAUDE_PLUGIN_ROOT}/...` in body text and in `allowed-tools` (spike 1). Existing text that says "written with `~`" is corrected for these paths.
- **Cutover order.** Scripts, guard and agent files change first and work under both layouts, since they find the root themselves and accept both path spellings. The skill files change in one item (W3): after it, the old symlink install no longer permits their commands. The author's own session must run `claude --plugin-dir` from the checkout before W3, since `CLAUDE.md:3` says edits here are live.

## Work items

### W3: Skills use the plugin root

- **Change:** in the four skills and the files they load (`spike-step.md`, `done-step.md`, `ideas-finish.md`, `ideation-rules.md`) and `hooks/run-agent.md`, `hooks/agent-sandbox.md`, replace `~/.claude/{skills,hooks,agents}/...` with `${CLAUDE_PLUGIN_ROOT}/...`, in `allowed-tools` too (spike 1). Rewrite the "written with `~`" rule (`skills/spec/spike-step.md:16`) for plugin paths. Remove the legacy `~/.claude/skills/research/scripts/<name>` spelling from `OUTSIDE_SPELLINGS` and from both settings templates' `excludedCommands`.
- **Files:** `skills/*/SKILL.md`, `skills/spec/{spike-step,done-step}.md`, `skills/research/{ideas-finish,ideation-rules}.md`, `hooks/run-agent.md`, `hooks/agent-sandbox.md`, `hooks/agent-guard.py`, `hooks/agent-sandbox.json` and `tests/skill-evals/agent-case-settings.json`.
- **Done when:** a `claude -p --plugin-dir . "/claude-skills:idea a test idea"` in a scratch `HOME` writes the note without a permission prompt; the same for one `/claude-skills:cold-review` on a small markdown file, which launches an agent; `check-spec.py` still passes on every spec in `docs/specs/` (it checks citations at each spec's read-at commit, `skills/spec/scripts/check-spec.py:11`); and the same two runs again after `claude plugin marketplace add` of the checkout and `claude plugin install claude-skills@claude-skills` into a scratch `HOME` (not `--plugin-dir`), where the root is the versioned cache path, with no denial, and with the root the guard derives from `__file__` equal to the `${CLAUDE_PLUGIN_ROOT}` the skill expanded, printed by one `python3 -c` on the cache path *(assumption: a scratch `HOME` has no login, so this run is authenticated by `ANTHROPIC_API_KEY`)*. The versioned cache path is untested (spike 1 covered `--plugin-dir` only), so this run is its first test.

### W4: Tests, CI and evals run on the plugin layout

- **Change:** replace `SymlinkedInstall` with a copy-to-cache-path test (the guard and runner tests were already made layout-independent in W2); add a test that fails on any `~/.claude/{skills,hooks,agents}` reference outside the dated documents and an explicit exempt list (the `tests/test_mine_sessions.py` fixtures), scanning tracked files only (`git ls-files`, since a plain walk also reads the untracked `tests/*/results/`), so the 141 don't grow back; drop the symlink step from CI; make `tests/agent-evals/run.sh` and `tests/skill-evals/run.sh` load the plugin (`--plugin-dir`) and type `/claude-skills:<skill>`.
- **Files:** `tests/test_agent_guard.py` (`SymlinkedInstall` only), a new `tests/test_no_stale_paths.py`, `tests/test_mine_sessions.py:16,116,125` (fixtures, listed as exempt), `tests/skill-evals/cases/research-quick-flow/grade.py:18`, `tests/skill-evals/cases/spec-done/grade.py:20`, `tests/skill-evals/cases/spec-quick/grade.py:19`, `tests/agent-evals/run.sh`, `tests/skill-evals/run.sh`, `tests/skill-evals/cases/*/prompt.txt`, `tests/replay_guard.py`, `.github/workflows/tests.yml`.
- **Done when:** `python3 -m unittest discover -s tests` passes with no `~/.claude/skills` or `hooks` link present (also in CI); the stale-path test is red on a scratch commit that reintroduces one reference and green after; `tests/agent-evals/run.sh` and `tests/skill-evals/run.sh` pass on Sonnet and on Opus, run one after the other.

### W5: Docs and conventions

- **Change:** a README "Install" section replacing the symlink one (`README.md:72-90`): marketplace commands, the `~/notes` prerequisite, the user-level deny rules to add by hand, and `claude --plugin-dir .` for development. It says that `/spec` and `/claude-skills:spec` both work, and that with the old symlinks still in place the bare name is defined twice. `README.md:271` names `~/.claude/skills/research/scripts/build-index.py` for a command the user runs by hand, so W5 replaces it with a form that works under the versioned cache path (see Open questions). The new `CLAUDE.md` text about dated documents avoids the literal `~/.claude/skills` and `hooks` paths, so the grep below can print nothing. Revise `CLAUDE.md:3` and `:33`, and add that dated documents keep the paths they were written with. Add a CHANGELOG entry and a dated `- Not reviewed:` line to `records/README-record.md`.
- **Files:** `README.md`, `CLAUDE.md`, `CHANGELOG.md`, `records/README-record.md`, `docs/repo-guide.md`, `docs/containment.md` (line 8 names `~/.claude/agents`, which W4's test also flags), `.gitignore:6` (its comment says `~/.claude/skills` links here).
- **Done when:** the README's install commands, run in a scratch `HOME`, leave `/claude-skills:idea` working; `grep -n '~/.claude/\(skills\|hooks\)' README.md CLAUDE.md docs/*.md` prints nothing (today it prints seven lines: `CLAUDE.md:3`, `README.md:81,85,86,271` and `docs/repo-guide.md:6,7`).

### W6: Record the evals and release

- **Change:** a dated `tests/agent-evals/BASELINE.md` section with every case's result and cost on both models, and the skill evals'; tag `v0.1.0` on the merge commit if asked.
- **Files:** `tests/agent-evals/BASELINE.md`.
- **Done when:** the section lists all cases per model with cost, including cases not expected to change, each within its cap ($5, $10 for `research-ideas`, $3 for skill cases, per `CLAUDE.md`).

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W3 | 1 day, mostly mechanical | part 1 (W2) |
| W4 | 1.5 days, plus about $12 of evals | W3, and so part 1 |
| W5 | 0.5 day | W3 |
| W6 | 0.5 day of waiting on runs | W4 |

Estimated from reading the code not from doing the work, so trust the ordering more than the numbers. The eval figure is two full agent-eval runs at $3.70-$4.68 each ($7.40-$9.36) plus the four skill-eval cases at about $0.30 each, twice ($2.40), so $10-$12 (`CLAUDE.md:15-19`).

## Spike questions

The numbers continue from the unsplit spec, [2026-09-29-plugin-marketplace](2026-09-29-plugin-marketplace.md), so its record and results still line up.

1. Does `${CLAUDE_PLUGIN_ROOT}` expand in `allowed-tools` frontmatter, and does the expanded absolute path then match the Bash call the model writes, so the command runs without a prompt? Experiment: a scratch plugin with one skill whose `allowed-tools` is `Bash(${CLAUDE_PLUGIN_ROOT}/bin/hello *)` and whose body says to run it; `claude -p --plugin-dir` on it, in default permission mode. If it fails, W3 takes the `bin/` route.
   Answered: yes. Under `--plugin-dir`, a skill with `allowed-tools: Bash(${CLAUDE_PLUGIN_ROOT}/bin/hello *)` ran the command with no denial, the same as one with the literal path, while a skill with no `allowed-tools` was denied; the model wrote the expanded absolute path. W3 takes the `${CLAUDE_PLUGIN_ROOT}` route, not `bin/`. Not tested: a marketplace install's versioned cache path (run by hand, docs/specs/spikes/2026-09-29-plugin-marketplace-2-cutover-results.md)
7. Does a plugin's skill answer to its bare name as well as its namespaced one? Experiment: `claude -p --plugin-dir` on a scratch plugin, typing `/<skill>` instead of `/<plugin>:<skill>`.
   Answered: yes. `/var` ran the plugin's `var` skill with no denial. Not tested: a marketplace install, or a bare name shared with another skill (spike Q7, run by hand, docs/specs/spikes/2026-09-29-plugin-marketplace-2-cutover-results.md)

## Risks and rollback

- **Rollback for any item:** it lands as its own commit on a branch, so revert it.
- **The cutover breaks the author's live session.** The skill files change in W3 alone, after the author has switched to `--plugin-dir`.
- **`~/notes` limits who can use the plugin.** A stranger's first `/claude-skills:research` stops at the README's setup section. Accepted for v1.
- **Users of the old install** keep working only until they pull. The README's new Install section says to remove the two symlinks, since both installs at once would load every skill twice.
- **The spec is read at a draft PR's head.** Local `main` is at PR #27's head (`c05ef6a`), not `origin/main`. If the PR's history is rewritten again, as it was once during this spec's writing, local `main` diverges from it: reset `main` to `origin/main`, then re-read and re-cite the guard, sandbox and test files. If the PR merges normally on GitHub, `main` fast-forwards to the merge commit.

## Open questions

- How does a user run a plugin's script by hand under a marketplace install? `README.md:271` does it for `build-index.py`, but the script sits at a versioned cache path. A plugin `bin/` directory would put it on `PATH` *(unverified)*; the alternative is to run it only through the skill. W5 needs one of them, and no spike has tested either.

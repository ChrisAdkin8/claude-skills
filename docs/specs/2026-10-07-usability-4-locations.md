---
title: "Usability, part 4: the notes and code folders become settings"
created: 2026-10-07
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 377b2dd
cite-repo: none
---

# Usability, part 4: the notes and code folders become settings

## Goal

Someone who keeps their code in `~/src` or their notes in another folder can use every command. Two settings, `CHECKED_PLANS_NOTES_DIR` and `CHECKED_PLANS_CODE_DIR`, name the folders, with `~/notes` and `~/code` as defaults, so nothing changes for anyone who sets neither. Every script, sandbox, guard rule and skill reads them from one place. The README says where to set them, and prints the permission rules that keep the skills from prompting in the new folders.

Part 4 of 7 from the usability review of 2026-10-07. The user chose this on 2026-10-07 over keeping the folders fixed. Part 3's `/idea setup` uses the notes folder this part defines once both have landed.

## Decision

- **Environment variables**, read by one helper, `hooks/locations.py`. They're the one kind of setting every piece can see: the user's session and its Bash calls, the headless agents (which load the user's settings, `env` block included) and the shell launchers. Rejected: a plugin settings file, which the guard and the launchers would each have to find and parse.
- **Defaults stay, and stay denied.** Rendered sandbox settings keep `~/notes` and `~/code` and add the configured folders beside them, so moving a folder never opens the old one.
- **Permissions.** A skill's `allowed-tools` can't follow a variable, as far as the documentation says, so the skills keep pre-approving the default folders, and `locations.py --permissions` prints the rules to paste for the configured ones. Spike question 1 may remove that step.
- **Paths are compared resolved.** git reports a repo's real path, so "under the code folder" compares real paths on both sides, and a symlinked code folder works.

## Background

Read at `377b2dd` on 2026-10-07.

**The README fixes both folders.** "Your code in git repos under `~/code`" and "`/spec` and `/implement` work only on a repo there" (`README.md:71-72`); the notes folder "isn't configurable yet" (`README.md:96-97`).

**Scripts.** `run-implementer.sh` refuses a worktree outside `~/code` (`skills/implement/scripts/run-implementer.sh:70`, `:73`, `:79`). `run-agent.sh` gives every agent `--add-dir "$HOME/notes"` (`hooks/run-agent.sh:116`). `check-note.py` reads templates from the home folder's `notes/templates` (`skills/research/scripts/check-note.py:50`). `build-index.py` matches a `related` entry only as `~/notes/…` (`skills/research/scripts/build-index.py:83-84`), and `check-spec.py` finds linked notes only by that prefix (`skills/spec/scripts/check-spec.py:115`).

**Sandboxes and the guard.** The agents' settings deny writes to `~/notes` and `~/code` (`hooks/agent-sandbox.json:15`); the verifier's and the spikes' deny reads and writes of both (`skills/implement/verify-settings.json:8`, `:31`, `:37-38`; `skills/spec/spike-settings.json:8`, `:31`, `:37-38`); the implementer's deny the notes folder (`skills/implement/implementer-settings.json:11`, `:58`, `:129-134`). The researcher's write hook names `$HOME/notes/research` (`hooks/agents/researcher.md:26`). `/spec` copies the spike settings into each spike's folder with the Write tool, by hand (`skills/spec/spike-step.md:51`).

**Skills.** The skills check for a repo under `~/code` (`skills/spec/SKILL.md:54`; `skills/implement/SKILL.md:40`), and `/idea` and `/research` link the repo only when it's there (`skills/idea/SKILL.md:22`; `skills/research/SKILL.md:50`). Their `allowed-tools` name both folders (`skills/idea/SKILL.md:5`; `skills/research/SKILL.md:6`; `skills/spec/SKILL.md:6-7`; `skills/implement/SKILL.md:6`). Counted on 2026-10-07 with `grep -o -E '~/notes|~/code'`, the skill and agent files name the two folders about 80 times, most in `skills/research/SKILL.md` and `skills/idea/SKILL.md`. Claude Code's documentation doesn't say whether `allowed-tools` expands environment variables.

**Evals.** The skill-eval runner writes notes and fixtures under the home folder's `notes` and `code` (`tests/skill-evals/run.sh:69-70`, `:78`, `:80`).

**Symlinks.** Measured on 2026-10-07 in a scratch folder: with `~/code` a symlink to another folder, `git rev-parse --show-toplevel` prints the real path, so today's prefix checks fail.

## Non-goals

- More than two folders, such as a separate folder for specs.
- Moving existing notes or repos; the user moves them and sets the variable.
- Changing where the caches live under `~/.cache`.

## Design

`hooks/locations.py` reads `CHECKED_PLANS_NOTES_DIR` and `CHECKED_PLANS_CODE_DIR`, expands `~`, resolves links, and refuses (exit 2, naming the variable) a value that isn't absolute once expanded, is `/` or the home folder itself, or lies under `~/.claude` or `~/.cache`. It prints both folders, written with `~` where they're inside the home folder:

```
notes: ~/Documents/notes
code: ~/src
```

`locations.py --json` gives the same for scripts, and `locations.py --permissions` prints a `permissions.allow` list: each rule in the skills' `allowed-tools` that names `~/notes` or `~/code`, rewritten for the configured folder. Python scripts import it; shell scripts call it.

Rendering: `hooks/agent-settings.py` gains the configured folders wherever a settings file names `~/notes` or `~/code`, as an added entry beside the default. `prepare-spike.sh` takes the spike's hosts as an argument and writes its `settings.json` itself, through the same renderer, so the model no longer copies JSON by hand. The researcher's write hook names `"${CHECKED_PLANS_NOTES_DIR:-$HOME/notes}/research"`, and the guard resolves it before comparing.

Skills: each skill's Frame step runs `${CLAUDE_PLUGIN_ROOT}/hooks/locations.py` once and, wherever its files say `~/notes` or `~/code`, uses the folder printed. One line near each file's top says so; the text keeps the defaults, so it still reads as it does today for most users.

## Work items

### W1: one helper names the folders

- **Change:** `hooks/locations.py` as the Design says.
- **Files:** `hooks/locations.py` (new), `tests/test_locations.py` (new).
- **Done when:** new tests show the defaults with neither variable set; a configured `~/src` printed as `~/src`; a symlinked folder printed as its real path; exit 2 naming the variable for `/`, the home folder, a path under `~/.claude` and a relative path; and `--permissions` printing `Bash(git -C ~/Documents/notes add *)` for `CHECKED_PLANS_NOTES_DIR=~/Documents/notes`. The unit tests pass.

### W2: the scripts follow it

- **Change:** `check-note.py`'s templates, `build-index.py`'s and `check-spec.py`'s note prefixes, `run-agent.sh`'s `--add-dir`, `run-implementer.sh`'s code-folder checks, and the folder part 3's `setup-notes.sh` creates, all from `locations.py`.
- **Files:** `skills/research/scripts/check-note.py`, `skills/research/scripts/build-index.py`, `skills/spec/scripts/check-spec.py`, `hooks/run-agent.sh`, `skills/implement/scripts/run-implementer.sh`, `skills/idea/scripts/setup-notes.sh` (from part 3), `tests/test_setup_notes.py`, `tests/test_check_note.py`, `tests/test_build_index.py`, `tests/test_check_spec.py`, `tests/test_run_agent.py`, `tests/test_run_implementer.py`.
- **Done when:** with both variables pointing at scratch folders, new tests show `check-note.py` reading templates from the configured notes folder, `build-index.py` filing an idea whose `related` names a research note with the configured prefix, `check-spec.py` finding a missing note under that prefix, the stub `claude` getting `--add-dir` with the configured notes folder, `setup-notes.sh` creating the configured folder and nothing under `~/notes`, and `run-implementer.sh` accepting a worktree under the configured code folder and refusing one under `~/code`. With neither set, every existing test passes unchanged.

### W3: the sandboxes and the guard follow it

- **Change:** the renderer's added entries, `prepare-spike.sh` writing the spike's settings, `spike-step.md`'s step 7b.3 calling it, and the researcher's write hook.
- **Files:** `hooks/agent-settings.py`, `skills/spec/scripts/prepare-spike.sh`, `skills/spec/spike-step.md`, `skills/spec/SKILL.md`, `hooks/agents/researcher.md`, `tests/test_agent_settings.py`, `tests/test_prepare_spike.py`, `tests/test_sandbox_settings.py`.
- **Done when:** new tests show each rendered settings file denying both the default and the configured folders where it denied the default before; `prepare-spike.sh` writing a `settings.json` that matches `spike-settings.json` but for the hosts given; and the guard, run as the researcher's hook with `CHECKED_PLANS_NOTES_DIR` set, allowing a write under the configured `research` folder and refusing one under `~/notes/research`. The deny-list agreement tests still pass. The `spec-quick` skill eval and the agent evals pass on Sonnet and Opus.

### W4: the skills follow it

- **Change:** the Frame line and the `locations.py` call in each skill, the top-of-file line in each file they load that names a folder, and `locations.py` in each skill's `allowed-tools`.
- **Files:** `skills/idea/SKILL.md`, `skills/research/SKILL.md`, `skills/research/ideas-finish.md`, `skills/research/ideation-rules.md`, `skills/spec/SKILL.md`, `skills/spec/spike-step.md`, `skills/spec/done-step.md`, `skills/cold-review/SKILL.md`, `skills/implement/SKILL.md`, `hooks/agents/researcher.md`, `tests/test_skill_frontmatter.py`.
- **Done when:** a new test in `tests/test_skill_frontmatter.py` fails if a skill names `~/notes` or `~/code` without pre-approving `locations.py`, and fails before the change. A skill-eval run of `research-quick-flow` with `CHECKED_PLANS_NOTES_DIR` pointing at a scratch notes folder, its permission rules added from `--permissions`, writes its note there and nothing under `~/notes`; it passes on Sonnet and Opus.

### W5: repo checks compare real paths

- **Change:** wherever a skill or script asks whether a repo is under the code folder, compare the repo's `git rev-parse --show-toplevel` with `locations.py`'s resolved folder.
- **Files:** `skills/idea/SKILL.md`, `skills/research/SKILL.md`, `skills/spec/SKILL.md`, `skills/implement/SKILL.md`, `skills/implement/scripts/run-implementer.sh`, `tests/test_run_implementer.py`.
- **Done when:** a new test with `CHECKED_PLANS_CODE_DIR` pointing at a symlink to a scratch folder gets `run-implementer.sh --check` (part 2a's W1) to accept a worktree in the real folder; the four skills' repo checks say "under the code folder `locations.py` prints, compared as real paths". The unit tests pass.

### W6: the evals follow it

- **Change:** `tests/skill-evals/run.sh` and `tests/agent-evals/run.sh` take their notes and code folders from `locations.py`.
- **Files:** `tests/skill-evals/run.sh`, `tests/agent-evals/run.sh`, `tests/test_eval_runners.py`.
- **Done when:** a new test in `tests/test_eval_runners.py` runs the skill-eval runner on a stub case with both variables set and finds the fixture under the configured code folder and the note path under the configured notes folder; with neither set, the runners' existing tests pass.

### W7: the README says how to move the folders

- **Change:** Requirements and Set up `~/notes` name the two settings; a short section says to set them in the `env` block of `~/.claude/settings.json`, so every session and agent sees them, and to paste `locations.py --permissions`' rules into `permissions.allow` there; and a symlinked folder is fine.
- **Files:** `README.md`, `records/README-record.md`.
- **Done when:** `grep -n 'CHECKED_PLANS_CODE_DIR' README.md` and `grep -n -- '--permissions' README.md` each find a line; "isn't configurable yet" is gone; the record ends with a dated `Not reviewed:` line.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 2 h | none |
| W2 | 3 h | W1, part 3's W2 |
| W3 | 4 h | W1 |
| W4 | 4 h, after spike question 1 | W1 |
| W5 | 1 h | W1, part 2a's W1 |
| W6 | 2 h | W1 |
| W7 | 1 h | W1 to W6 |
| Evals | both sets on both models, and the implement cases | W1 to W7 |

The hours are guesses from reading the files; W4 is long because it touches about 80 mentions in ten files. It changes every skill, both eval runners and `skills/implement/`, so both sets run on both models with the implement cases (`CLAUDE.md:23-38`): $15.23 on 2026-10-04 (`docs/repo-guide.md:108-109`).

## Spike questions

1. Does Claude Code expand an environment variable in a skill's `allowed-tools`, so `Bash(git -C ${CHECKED_PLANS_NOTES_DIR} add *)` pre-approves the configured folder? Experiment: by hand, a throwaway skill pre-approving `Bash(ls ${SPIKE_DIR}/*)`, run with `claude -p --plugin-dir` and `SPIKE_DIR` set, once inside the folder and once outside; read `permission_denials` in the JSON result. If it expands, W4 pre-approves through the variables and W7 drops the paste step.

## Risks and rollback

- A typo in a variable sends notes somewhere unexpected. `locations.py` refuses the dangerous values, and every skill prints the folders it uses in its framing line.
- The skills' text keeps the default folders as examples, so a model could still write `~/notes` in a command. W4's eval run with a scratch notes folder catches that, and the old folder stays denied to the agents.
- Rollback is unsetting the variables; the code paths then match today's.

## Open questions

- Should specs, which live in the repos, be indexed from the code folder too? Part 3's index work leaves them out, as today.

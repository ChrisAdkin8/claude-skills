---
title: "Usability, part 3: getting started"
created: 2026-10-07
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 377b2dd
cite-repo: none
---

# Usability, part 3: getting started

## Goal

A new user gets a working notes folder from one command, `/idea setup`, built from starter files that pass the checks, instead of writing four files from the README and a Python list. The rules a template must follow are written down, and the messages that enforce them say what to do. `/research ideas` runs only when asked, and works without the author's own attention-evidence file. The notes index stays current after every command that changes a note. The README tells a newcomer how to get going again when something stops, what its own words mean, and what the optional deny list costs them.

Part 3 of 7 from the usability review of 2026-10-07. It stands alone; part 4 later moves the notes folder's location into a setting, and `/idea setup` follows it then.

## Decision

- **Starter files ship in the repo**, under `notes-starter/`, and `/idea setup` copies them. Rejected: a new `/setup` command, a sixth command for one-time use; and creating `~/notes` silently whenever it's missing, which hides a commit in the user's home folder.
- **Template rules:** state them in the README and make three of them kinder: a quoted line (`> …`) in a template is standing text, a heading may carry a qualifier in brackets, and the Sources failure says how to number. The other rules stay as they are.
- **`/research ideas`:** only by name. Its ranking criterion is asked for when the request gives none, and the evidence file becomes optional. The six lenses stay; another lens is a warning, not a failure.
- **Index:** rebuilt by `/idea`, `/spec` and `/spec done` as well as `/research`, since each changes notes the index shows.
- **Deny list:** narrow `~/.config` to its credential folders in `hooks/user-deny.json` only, and keep the agents' wider rule, since the agents never need the rest of it.

## Background

Read at `377b2dd` on 2026-10-07.

**Setup is by hand.** The README says the notes folder "must be a git repo" and "This repo doesn't create it for you" (`README.md:153-157`), lists the files to write (`:160-167`), and sends the reader to "The `REQUIRED` list near the top of" `check-note.py` for a template's headings (`:175-177`). The README's own full review found that "this repo doesn't supply it" (`records/README-record.md:17`). `/idea` and `/research` stop when a file is missing, point at the README, and are told "Don't create it" (`skills/idea/SKILL.md:14`; `skills/research/SKILL.md:43`).

**What a note must have, beyond the headings.** `check-note.py` reads templates from the home folder's `notes/templates` (`skills/research/scripts/check-note.py:50-51`). It fails a note missing `title`, `created`, `status` or `question` in its frontmatter (`:606`), treats a missing `depth` as full (`:602`), knows three statuses (`:54`), allows only Candidate pool and Verification after Sources (`:83`, `:290`), counts a source only as a numbered `1. ` line (`:101`), and otherwise reports "Sources list is empty" (`:657`). Any template line over 20 characters that isn't a heading, table, rule or short `key:` line counts as a prompt that must not survive into a note (`skills/research/scripts/mdcheck.py:380-392`), so standing text in a template fails every note built from it. A heading matches only on its own or followed by `:` or `,` (`skills/research/scripts/mdcheck.py:150-156`), so `## Bottom line (TL;DR)` is a missing section. None of this is in the README. Measured on 2026-10-07 in a scratch folder: a quick note filled from a template written as the README describes failed 7 checks.

**`/research ideas` assumes the author's project.** Plain `/research` chooses ideas depth "if it asks for ideas, what to build or write, or a ranking" (`skills/research/SKILL.md:36`). That depth stops without `projects/mindshare/attention-evidence.md` (`:43`), ranks by "likely mindshare" unless told otherwise, and says "novelty counts for more than usefulness to clients" (`:49`). The lenses are a fixed six (`skills/research/scripts/check-note.py:85`), and any other fails (`:553`).

**The index goes stale.** Only `/research` rebuilds it (`skills/research/SKILL.md:133`). `/idea` and `/spec` can't run `build-index.py` under their `allowed-tools` (`skills/idea/SKILL.md:5`; `skills/spec/SKILL.md:6-9`), though `/spec` changes notes when it links them (`skills/spec/SKILL.md:128`). The index reads only each kind's top folder (`skills/research/scripts/build-index.py:48`), and matches a `related` entry only when it's written from the notes folder with `~` (`:83-84`); anything else lands under Unfiled (`:126`) without a word. The README's way to rebuild by hand is a two-line shell command (`README.md:332-342`).

**What a newcomer can't find.** The README never mentions `/research finish`, the way back after a research session ends early, nor that `/implement` can run unattended (a `grep` for either finds nothing). Its in-house words, such as record, delta review, read-at and drift, are explained where they first appear, if at all, and nowhere together. `npx` needs Node.js, which Requirements leaves out (`README.md:323`), and the README says links "may not open" where they won't; the README's delta review found both (`records/README-record.md:42-43`).

**The deny list.** The README tells users to copy `hooks/user-deny.json` into their own settings (`README.md:98-104`). Its `Read(~/.config/**)` (`hooks/user-deny.json:14`) then blocks every file there in their own sessions, editor and shell configs included. A test holds it equal to the agents' list less one rule (`tests/test_user_deny.py:66-71`). The spike settings already deny only four folders there, "because git and uv read their own config there" (`hooks/agent-guard.py:279-280`; `skills/spec/spike-settings.json:10`, `:34`).

## Non-goals

- Moving the notes folder; that is part 4.
- Changing which headings a note needs, or the word budgets.
- Widening what the agents themselves may read.

## Design

**`notes-starter/`** holds `CLAUDE.md` (tag and frontmatter conventions, and a Topics section with the README's command), `templates/idea.md`, `templates/research.md`, `templates/research-ideas.md`, and `projects/mindshare/attention-evidence.md`, whose table has the columns `skills/research/ideation-rules.md` names and no rows. Each template has every required heading, the frontmatter keys the checks want, with comments where a value goes, and no line the template-text rule would catch.

**`/idea setup`** runs `skills/idea/scripts/setup-notes.sh`, which copies each starter file that isn't there yet, never overwriting one; runs `git init` if the folder isn't a repo; and commits the files it added, naming them after `--`. `setup-notes.sh --check` prints, for each command, the files it would stop for, and changes nothing. When `/idea` or `/research` finds a file missing, it says to run `/idea setup`.

**Template rules.** `mdcheck.template_prompts` skips lines starting with `>`. `mdcheck.heading_is` also accepts the heading followed by ` (`, so `## Bottom line (TL;DR)` matches; the review parser keeps its own exact headings. "Sources list is empty" becomes "Sources has no numbered entries: list each source as `1. …`". The README gets a short list of the rules a template must keep.

**`/research ideas`.** `/research` picks ideas depth only for `/research ideas`. Without a `Rank by` in the request, Frame asks one question: likely attention (stars, Hacker News, Reddit), usefulness to the user's own work, or least effort, recommended first. Without the evidence file, the researcher records Format evidence from new data points only and says so in the Bottom line, and `ideas-finish.md` skips its merge step. A lens outside the six is a WARN.

**Index.** `/idea` runs `build-index.py` after its commit and commits `index.md` with a second commit; `/spec`'s Link the notes step and `/spec done`'s research step do the same. `build-index.py` prints one line per note filed under Unfiled, with the reason (no topic, a topic it can't read, names no research note, or a `related` path not written from the notes folder), and one per note in a sub-folder it skipped.

**Deny list.** `hooks/user-deny.json` replaces `Read(~/.config/**)` with the spike settings' four `~/.config` rules, and the test changes to match.

## Work items

### W1: starter notes files

- **Change:** add `notes-starter/` as the Design says.
- **Files:** `notes-starter/` (new: `CLAUDE.md`, `templates/idea.md`, `templates/research.md`, `templates/research-ideas.md`, `projects/mindshare/attention-evidence.md`), `tests/test_notes_starter.py` (new).
- **Done when:** a new test, with `HOME` set to a scratch folder holding a copy of `notes-starter/` as its notes folder, finds every heading `check-note.py`'s `REQUIRED` names for each depth in the matching template; runs `check-note.py` on `tests/fixtures/notes/verified-full.md` and `tests/fixtures/notes/ideas.md` there and gets `RESULT: PASS`; and runs `build-index.py` on the folder with exit 0. `python3 -m unittest discover -s tests` passes.

### W2: `/idea setup`

- **Change:** the script and the mode, and the missing-file messages in `/idea` and `/research` pointing at it.
- **Files:** `skills/idea/scripts/setup-notes.sh` (new), `skills/idea/SKILL.md`, `skills/research/SKILL.md`, `tests/test_setup_notes.py` (new).
- **Done when:** new tests on a scratch `HOME` show `setup-notes.sh` creates every starter file and one commit; a second run adds nothing and makes no commit; a file the user already has is left byte for byte; `--check` names the missing files for each command and changes nothing. Both skills' `allowed-tools` pre-approve the script, and their missing-file steps name `/idea setup`. The unit tests and shellcheck pass.

### W3: template rules written down, and three of them kinder

- **Change:** the quote and bracket rules in `mdcheck.py`, the Sources message in `check-note.py`, and the README's list of template rules.
- **Files:** `skills/research/scripts/mdcheck.py`, `skills/research/scripts/check-note.py`, `README.md`, `records/README-record.md`, `tests/test_mdcheck.py`, `tests/test_check_note.py`.
- **Done when:** new tests pass a note built from a template holding a `>` standing line that the note keeps, and a note whose heading reads `## Bottom line (TL;DR)`; a note with bulleted sources gets the new message; each fails before the change. The existing review-parser tests in `tests/test_review_state.py` still pass. The README lists the rules, with a dated `Not reviewed:` line in the record.

### W4: `/research ideas` only when asked, and without the evidence file

- **Change:** the routing, the ranking question, the optional evidence file and the lens warning.
- **Files:** `skills/research/SKILL.md`, `skills/research/ideation-rules.md`, `skills/research/ideas-finish.md`, `hooks/agents/researcher.md`, `skills/research/scripts/check-note.py`, `tests/test_check_note.py`, `tests/agent-evals/cases/research-ideas/`.
- **Done when:** a new test gives `check-note.py` an ideas note with a seventh lens and gets a WARN, not a FAIL. `skills/research/SKILL.md`'s Modes no longer route "a ranking" to ideas depth, and Frame no longer stops for the evidence file. The `research-ideas` agent eval, run without the evidence file, passes on Sonnet and Opus.

### W5: the index stays current, and says what it left out

- **Change:** rebuilds in `/idea`, `/spec` and `/spec done`, and `build-index.py`'s report lines.
- **Files:** `skills/idea/SKILL.md`, `skills/spec/SKILL.md`, `skills/spec/done-step.md`, `skills/research/scripts/build-index.py`, `tests/test_build_index.py`.
- **Done when:** new tests show `build-index.py` printing a line for a note with no topic, for an idea whose `related` gives a full path, and for a note in `research/python/`, each naming the reason. `/idea`'s and `/spec`'s `allowed-tools` pre-approve the script. The `spec-quick` and `research-quick-flow` skill evals pass on Sonnet and Opus.

### W6: the README helps a newcomer get going again

- **Change:** a section, "If something stops", saying for each command what to type after an interrupted session or a stop (`/research finish`, `/spec finish`, `/implement <spec>` again, which resumes), and that `/implement` can be told no one will answer questions; a short glossary of the words the reports use; the agents' allowed websites from `hooks/agent-sandbox.json`, in plain words; Node.js under Requirements; and "won't open" for the links.
- **Files:** `README.md`, `records/README-record.md`.
- **Done when:** `grep -n 'research finish' README.md` and `grep -n -i 'glossary' README.md` find the new text; Requirements names Node.js; the record ends with dated `Not reviewed:` lines for the change.

### W7: a narrower deny list for the user's own sessions

- **Change:** the four `~/.config` rules in place of `Read(~/.config/**)`, the test that holds the lists together, and the README's paragraph: the list is optional, what it blocks (shell history, `~/.ssh`, `~/.aws` profiles, `~/.kube`, `~/.docker`, `~/.claude.json`), and to copy it again after an update that changes it.
- **Files:** `hooks/user-deny.json`, `tests/test_user_deny.py`, `README.md`, `records/README-record.md`.
- **Done when:** `tests/test_user_deny.py` passes with the new rule that the user's list is the agents' less the agent-runs rule, with `~/.config` narrowed to the spike settings' four folders, and fails if `Read(~/.config/**)` comes back. The README paragraph says "optional" and names what it blocks, with a dated `Not reviewed:` line.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 2 h | none |
| W2 | 3 h | W1 |
| W3 | 2 h | none |
| W4 | 3 h | none |
| W5 | 3 h | none |
| W6 | 2 h | parts 1 and 2's README changes, to avoid two edits of one section |
| W7 | 1 h | none |
| Evals | both sets on both models | W1 to W7 |

The hours are guesses from reading the files. W2, W4 and W5 change skill steps and an agent file, so both eval sets run on both models (`CLAUDE.md:23-34`); that cost $15.23 on 2026-10-04 (`docs/repo-guide.md:108-109`).

## Spike questions

None.

## Risks and rollback

- Accepting ` (` after a heading could make a heading the review parser shouldn't read match. W3 keeps the parser's own headings exact and its tests passing.
- A second commit for `index.md` doubles `/idea`'s commits. Rollback is dropping the rebuild lines; the index is generated and harmless to leave stale.
- Users who copied the old deny list keep the wide rule until they copy it again; W7's paragraph says to.

## Open questions

- Should `/idea setup` also offer to paste the deny list into the user's settings? This part only documents it, since a plugin can't ship permission settings.

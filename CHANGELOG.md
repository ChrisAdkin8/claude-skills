# Changelog

What changed, by day, drawn from the commit history. The repo has no releases or tags, so each
section is a date. Within a day, changes are grouped by area.

## 2026-10-01

Fixes from a full review of the repo on 2026-10-01, PRs #35 to #46.

### Security

- The agents no longer get Claude Code's auto memory. Every checker, the cold reviewer and the
  verifiers included, had been given the project's `MEMORY.md`, which no tool call the guard sees
  delivers. Each launcher now sets `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`. (#35)
- `git-read.py`, the read-only git the skills run without asking, no longer runs a program the
  repo's own git config names. It turns off fsmonitor and hooks, allows no network transport,
  drops `GIT_*` variables, and refuses a repo whose own config, or a checked-out submodule's, sets
  a filter, diff or merge driver, `diff.external`, a gpg program or a config hook. The guard drops
  `git whatchanged`, which git 2.54 replaces with a repo's alias; `git log --raw` does the same.
  (#39)
- Spikes and the implement-verifier hide the same eight secret environment variables as the
  agents. A spike or verifier run that leaves `results.md`, `reply.md`, `run.json` or `run.err`
  as a link, or as anything but a plain file, is refused (exit 4) before anything reads it, and
  the verifier's run is refused if it changed its inputs. (#36, #40)
- `/spec` pre-approves edits only under a repo's `docs/specs/`, `/implement` only under its
  worktree's, and `/idea` only to idea notes. Before, `/spec` and `/implement` could change any
  markdown file under `~/code` without asking, every `CLAUDE.md`, `SKILL.md` and agent prompt
  included, and `/idea`, which Claude may start by itself, could change `~/notes/CLAUDE.md` and
  the templates. (#40, #42)
- `scan-diff.py` refuses a `--base` that git would read as an option: `--base=--output=FILE`
  wrote over FILE and passed as clean. (#38)

### Fixed

- Installed users get updates. `plugin.json` no longer pins a version, which kept every install
  on the copy it first fetched; each commit is now its own version, and the README has an Update
  section. CI's manifest check allows that one warning and fails on any other. (#44)
- Following the README's advice to copy the agents' deny rules into your own settings no longer
  stops `/research`, `/spec` and `/cold-review` reading their agents' replies: the new
  `hooks/user-deny.json` leaves that rule out. (#44)
- `/implement`'s writes to the verifier's scratch folder are pre-approved. Its `Write(path)` rule
  was one Claude Code never consults, so every verification asked, or was refused unattended. (#45)
- The implement-verifier judges each work item on its own commits, so the spec's status edit, the
  record and clean-up commits no longer give a false "holds: no". Every work item is briefed,
  "holds: yes" needs each one verified, and `/spec done` keeps the implementer's own checks apart
  from the verifier's. The verifier's and the spikes' copies of the code are the committed files
  exactly: `.gitattributes` no longer drops tests or rewrites files, and no filter runs. (#40)
- `scan-diff.py` sees more ways of weakening a test: Swift, Ruby, Go, Rust, Django and JS test
  files and test definitions, and more skip and lint-silencing markers. A `.gitattributes` can no
  longer hide a change from it, and it never crashes into exit 1, which means "flags found". (#38)
- `/spec done` can list worktrees, so it finds `/implement`'s. `check-spec.py` fails a
  placeholder Done when with a full stop after it, such as `TBD.`. (#37, #39)
- `/research` shows you a change its researcher made to an older note, adds a new note before its
  "conclusion revised" commit, and checks for every `~/notes` file a run needs before any agent
  starts. `/research` and `/idea` point at the installed plugin's README. (#42)
- `/implement`, `/spec` and `/research` run one command per Bash call, with each script's full
  path, so their calls match what they pre-approve instead of asking. (#46)

### Changed

- The Python files are formatted once with ruff, as the editing hook does. (#35)
- `tests/replay_guard.py` exits 0 when every difference is accepted in
  `tests/replay-accepted.txt`, by fingerprint, never by command, and judges each recorded run as if
  it had run from the checkout replaying it. (#37, #41)
- The evals can't pass broken work. The agents review a clone with the answer keys removed and
  blanked from its history. The skill evals pre-approve only the Skill tool, so a call outside a
  skill's allowed-tools fails the case. Graders need true claims CONFIRMED, agents that finished,
  and `implement-basic`'s Done when to pass on the branch. Agents a skill eval launches are capped
  at $2. (#43)
- The README names all five commands, gives `/implement`'s caps, and asks for Claude Code 2.1.277
  or later and repos under `~/code`. (#44)

### Added

- `docs/anti-slop-practice.md`, a research note on stopping coding agents writing slop: what
  Anthropic, OpenAI, GitHub, Cursor and practitioners such as Robert C. Martin advise, what has
  evidence, and six ranked changes to `/implement` and the repo, first a re-run of `scan-diff.py`
  after the clean-up commits. None is built in yet. The README and the repo guide link it.

## 2026-09-30

### Security

- Closed four ways past the guard. It follows `bash -c` as deep as it checks, so a `gh` nested four
  deep is seen. A `sed` address with a long run of backslashes no longer takes minutes to check
  (a hook that times out lets the call through). A private path is matched however a linked home
  is spelled, such as macOS's `/var` and `/private/var`. And a path with `..` after a symlink is
  refused, since the guard and the shell could read it differently.
- Under `~/.claude/plugins`, an agent may read only this plugin's own folder: other plugins' files,
  marketplace clones and `plugins/data` stay hidden. A link inside the agent's saved tool results
  exempts only what stays under `~/.claude/projects`.

### Fixed

- `/spec` and `/research` quote their `argument-hint`. `/spec`'s began with `[quick]`, which a
  strict YAML parser rejects, so the skill had loaded with empty settings since 2026-09-25: listed
  by its heading, and without `disable-model-invocation` applying.

### Changed

- The skills install as a Claude Code plugin: `/plugin marketplace add ChrisAdkin8/claude-skills`,
  then `/plugin install claude-skills@claude-skills`. The four skills, the guard, the agent files
  and both sandbox settings now find their files through `${CLAUDE_PLUGIN_ROOT}`, and the symlinks
  from `~/.claude/skills` and `~/.claude/hooks` are no longer used. An existing install should
  remove them (`ls -l ~/.claude` shows them), or every skill is defined twice and its commands are
  no longer pre-approved. Work on the repo with `claude --plugin-dir .`. `~/notes` stays a
  prerequisite, and the README says which deny rules to add to your own settings by hand.
- The tests and both eval runners no longer need the links: CI drops its link step, the skill evals
  load the plugin and type `/claude-skills:<skill>`, and a new test fails on an old install-path
  reference outside the dated documents.
- CI checks the plugin with `claude plugin validate`: the marketplace manifest, and the plugin's
  skills, so frontmatter that doesn't parse fails the build.

### Added

- `/implement <spec>` builds a reviewed, committed spec. It checks the spec first: `reviewed`,
  passing `check-spec.py`, and no cited code changed since it was read. Then it makes a worktree on
  the branch `implement/<spec>` and hands the work items to an implementer, an agent in a headless
  session of its own, which does each test first in its own commit, then runs `/simplify` and
  `/code-review`. A sandboxed implement-verifier with no network re-runs each work item's Done
  when, and the evidence goes in the spec's record on the branch. The implementer runs without the
  sandbox or the guard, capped at $20 a run; each verifier run is capped at $5. Nothing is pushed
  or merged. (#33, #34)
- Behind it: `check-spec.py --drift` and `--drift-at` name the cited ranges that changed since
  read-at, and `scan-diff.py` flags out-of-scope files and weakened tests in a staged diff. `/spec`
  hands over to `/implement`, `/spec finish` moves read-at, and `/spec done` reads the evidence,
  run from the worktree. (#33, #34)

## 2026-09-29

### Security

- Agents can't read `~/.claude/backups`, which holds copies of `~/.claude.json`, or the two
  remote-settings files, which hold a telemetry header and an account ID. `~/.claude.json` itself
  was already denied.

### Fixed

- `gh` and the research scripts (`repo-health.sh`, `gcp-skus.sh`, `reddit-search.sh`) run only
  on their own in a Bash call, joined at most by `;` or `&&`. Claude Code takes a call out of the
  sandbox only when every command in it is exempt, so one that also held a text filter, `cd` or a
  loop ran inside it and couldn't log in. The guard refuses those calls and says how to write several queries.
- `/research ideas` works on a new `~/notes`: it sees files in new folders when it compares the
  notes before and after, and `/research finish` skips its history step in a repo with no
  commits. Four wording fixes in all.

### Changed

- The end-of-run reports of `/research`, `/spec`, `/spec spike` and `/spec done` give one short line
  for each item they list, in place of a fixed number of lines.
- The README's Set up `~/notes` creates `projects/mindshare` too, which `/research ideas` needs.

### Added

- `docs/checker-models.md` tests six models as a cheaper first check on research claims, over 698
  past verifier verdicts: Laya (two versions), MiniCheck, a DeBERTa NLI model and Qwen3 8B on a
  Mac, and Haiku 4.5 and Sonnet 5. The free models kept back about 70% of wrong claims, Sonnet 80%
  and Haiku 95%. None is built in yet. The README links it.

## 2026-09-28

### Security

- The four agents moved from `agents/` to `hooks/agents/`, and `~/.claude/agents` is no longer
  linked. Before, every session listed them as subagents it could start itself, outside their
  sandbox. `run-agent.sh` and the agent-eval runner now pass each agent to its own run with
  `claude -p --agents`, from a new script, `hooks/agent-def.py`, which refuses an agent file it
  can't fully read rather than drop a guard hook. A new eval case, `guard-applies`, shows the guard
  still runs this way. An existing install should remove its link: `rm ~/.claude/agents`.
- `/spec` pre-approves edits only to markdown under `~/code`, not every file, and `/cold-review`
  only to its record files. Folding a finding into a reviewed document now asks first.

### Fixed

- `/cold-review` gives the delta reviewer its diff as a `git` command. `review-state.py` prints it
  through `git-read.py`, which the main session may run, but the reviewer's guard refuses that
  script, so the reviewer couldn't read its diff. No eval caught it: both delta cases have no diff.
- The skill-eval cases that launch agents can't touch the real `~/notes/index.md`: a Sonnet run of
  `/research` rewrote it by hand after the sandbox refused `build-index.py`. Their settings deny
  the Write and Edit tools on it, and `/research` says not to write the index by hand.
- `run-agent.sh` must run as a command of its own, not joined with `; echo $?`: a sandbox that
  exempts it exempts only the bare command, so a joined one ran inside it and couldn't start.

### Changed

- The README is rewritten for a newcomer, a quarter shorter: what it does and who it's for, then
  a Try it section ending in a first run with what you should see. The containment detail and the
  Layout, Checks and eval costs move to two new pages, `docs/containment.md` and
  `docs/repo-guide.md`.
- `/research`, `/spec` and `/cold-review` start only when typed (`disable-model-invocation: true`),
  since each launches paid agents; `/idea` can still start on its own. All four skill
  descriptions are in the third person, without their mode syntax, which the argument hints
  already give.
- Another project's repo name is gone from a spec, its spike results and `BASELINE.md`. `CLAUDE.md` lists the
  `cold-review:` and `tests:` commit prefixes, and asks for commits from the checkout, not
  GitHub's web editor.
- The docs match the code after the 2026-09-27 fixes: the guard's docstring lists its `search`
  mode and new rules; the README lists `gh`, `jq` and `gcloud` under Requirements, six eval runs,
  and web search apart from the unchecked documentation servers; the scripts' and tests' headers
  give their current exit codes; the researcher treats an `API error` row as unverified; the
  diagram's guard box says it checks web calls, search included.
- `CLAUDE.md` says the README's `Not reviewed:` lines are a log: it has had its one delta review.
- `/research`, `/spec` and `/cold-review` run their agents from one shared file,
  `hooks/run-agent.md`, and refer to each other's sections by heading, never by step number.
- The three skill files are about 30 % shorter (2,099, 2,299 and 1,998 words), keeping every
  step and rule; two reasons for `/cold-review`'s rules moved to the README.
- Both eval sets run on Sonnet and on Opus (`EVAL_MODEL`), and an agent a skill eval launches runs
  on the same model (`RUN_AGENT_MODEL`). Three agent cases now accept Sonnet's sound answers, and
  `guard-applies` runs on Opus only, through a new `models.txt`.
- The agents are told which commands the guard refuses (`awk`, `python3 -c`, shell functions,
  `>` into a file, `curl -o`) and what to use instead, in `hooks/agent-sandbox.md`. Real agent
  sessions had hit 50 such refusals, each a wasted turn. No guard rule changed.

### Added

- Each of `/research`, `/spec` and `/cold-review` opens with a progress checklist, pasted ticked at
  each turn that waits on an agent.
- Two skill evals run a skill end to end with its agents: `spec-quick` and `research-quick-flow`.
  The runner can place a fixture under `~/code`, fill in `{{NOTE}}`, check `~/notes` is untouched,
  and clean up after itself.
- `tests/mine-sessions.py` reports, from the session logs Claude Code keeps, how each skill and
  agent went in real use: runs, agent launches, failed tool calls grouped by cause, and what you
  typed while it ran. It only reads; read its report before sharing it.

## 2026-09-27

### Security

- The guard refuses a wrapper option it doesn't know. It read BSD `xargs -J` as a flag, so in
  `xargs -J grep curl -d x https://…` it checked `grep` and let `curl` send data unchecked.
- The guard refuses `eval`, which it checked by re-joining the words without their quoting. No
  agent has used it.
- `gh` and the research scripts run outside the sandbox, and a command joining them with others
  seems to as well, so the guard lets them share a command only with text filters, `cd` and
  loops, never `curl` or `git`.
- Web search queries go through the guard: at most 200 characters, and no 40-character run of
  letters and digits. The longest of 478 recorded queries is 139 characters.
- The guard fails closed: it refuses the call when it crashes or gets input it doesn't expect,
  and refuses a write with no file path. Before, an unexpected error let the call through.
- Shell history, cookies, Chrome's profile and keychains are denied to the Read tool as well as to
  shell commands, and to spikes. A test checks that the guard and both settings files deny the same
  paths.

### Added

- CI: GitHub Actions runs the unit tests on macOS on each push to `main` and each pull request,
  and lints with ruff (errors only) and shellcheck (warnings and above).
- Tests for `mdcheck.py`, `git-read.py`, `run-spike.sh` and the two eval runners.

- A mind-map index for `~/notes`. Every research note gets a `topic` (an area, and optionally a
  sub-area), and `/research`'s last step rebuilds `~/notes/index.md` from those topics with the new
  `build-index.py`: research notes grouped under their topics, with their ideas and decisions
  under them. Markmap shows it as a clickable mind map; the README says how to open it.
- The researcher sets a `topic` on each note, reusing one already in use where it fits.
- Specs for `/implement`, a planned skill for workflow stage 5, in two parts: its tools (range-level
  drift, a diff scanner and a sandboxed `implement-verifier`), then the skill. It will hand the
  work to an `implementer` subagent, a headless session of its own on a git worktree. Both specs
  are drafts awaiting their delta review; the skill isn't built yet.

### Changed

- Checks that specs and notes used to pass when they shouldn't:
  - A `# comment` in a code block no longer ends a record's `## Cold review` section, and a
    `## Cold review` quoted in a code block isn't taken for a saved review. The heading matches in
    any case, so `## Cold Review` no longer turns off the delta-review gate.
  - A `---` rule at the top, or frontmatter that's never closed, isn't frontmatter: the spec's
    citations are checked, rather than 0 citations and a PASS.
  - A code block that's never closed fails, instead of hiding the rest of the document.
  - A bare-filename citation is range-checked when only one file has that name, and fails a
    template spec when several do.
  - `Done when` must be the field line itself, and `TBD`, `TODO`, `?` or `...` counts as empty.
  - A lone carriage return isn't a line break when counting a cited file's lines.
  - After Sources, an indented line after a blank line is prose, not a source. Indented prose in
    the Candidate pool counts, and a candidate over 120 words fails.
  - An *(unverified)* mark right after one sentence's full stop no longer covers the next sentence.
  - In a shallow clone, `review-state.py` reports `no-base` rather than taking the clone's cut-off
    commit for the review commit.
- `check-note.py` fails a research note with no topic, or one that isn't `area` or
  `area/sub-area` in lowercase and hyphens, and warns on a topic no other note uses.
- `check-note.py` and `build-index.py` share the topic pattern through `mdcheck.py`.
- Workflow stage 5 is Implement, not Build. The diagram shows `/implement` as its command, says
  under each stage's command whether its work runs in your session or in a subagent, and shows
  stage 2 rebuilding the notes index, with its verifier checking the key claims.
- The README defines skill, hook, frontmatter and turn where it first uses them, gives Layout as a
  table, and follows the mind-map index through all six stages as a worked example.
- The README takes five fixes from a delta cold review, which is saved in its record: the
  `research-ideas` eval case's $10 cap, a Topics section for `~/notes/CLAUDE.md`, what the worked
  example's verifier actually checked, and where unfiled notes go in the index.
- `CLAUDE.md` gives the agent evals' current cost and the `research-ideas` case's cap.
- One code-block walker, heading rule and citation pattern in `mdcheck.py`, used by every
  checker. `#2 on Hacker News` no longer ends a section, and form feeds no longer add lines.
- `check-spec.py` ignores a `## Cold review` quoted in a code block, and counts `Makefile:40` and
  other extensionless files as citations.
- `review-state.py` follows a renamed document and names every section a change touches.
- `build-index.py` wraps a link path holding a space or bracket in angle brackets.
- Both eval runners exit 1 when a case fails, and have separate cost caps, `AGENT_EVAL_MAX_USD` and
  `SKILL_EVAL_MAX_USD`. Four graders check the finding rather than a keyword.
- `replay_guard.py` prints SKIP when there's nothing to replay, and exits 1 on a regression.
- The README's diagram shows light in light mode; it showed the dark version to everyone. The
  README and `CLAUDE.md` list every test file and the CI, and give the fourth eval run's cost.
- The diagram's renderer is pinned to one version, with its lockfile committed.
- `review-state.py` prints its `diff:` line as a quoted `~/.claude/hooks/git-read.py` command,
  which `/cold-review` may run without a prompt, and which works for paths with spaces.
- `build-index.py` skips a broken link or a folder named `*.md` instead of crashing, escapes a
  backslash in a title, and reads a note that starts with a byte-order mark.
- `repo-health.sh` no longer reports a failure as a fact about a repo. It exits 1 when `gh` or
  `jq` is missing or `gh` isn't logged in, says "not found or no access" only when GitHub says so
  and "API error" otherwise, exits 1 when no repo could be read, and fetches four repos at a time.
  `reddit-search.sh` and `gcp-skus.sh` check their tools first, and `gcp-skus.sh` URL-encodes the
  page token. Tests for all three use stub `gh`, `curl` and `gcloud`.
- Skill instructions that a model could follow into the wrong result:
  - `/spec` lists the review's `Needs a run` rows as candidate spike questions, and adds them only
    if the user picks them, instead of editing the spec straight after its review. It asks which
    findings to fold in with one multi-select question, and always gives the implementation
    prompt, spike questions or not.
  - `/cold-review` saves a spec's full review without asking, as it already did its delta
    review, so a later `/spec finish` doesn't run a second one. It runs the delta `diff:` line
    as printed, through `git-read.py`.
  - All three agent-running skills say exit 2 means the run never started, so they don't read an
    earlier run's `run.err`, and take a fresh run dir rather than overwrite an earlier session's
    replies.
  - `/idea` and `/research` stop, pointing to the README, when `~/notes` isn't set up.
    `/research` never moves an `adopted`, `parked` or `dropped` idea back to `exploring`.
  - `/spec spike` resolves a `HEAD` read-at to a commit, which `prepare-spike.sh` needs. `/spec
    done` reads the spec's repo with `-C` and finds its first commit through a rename.
- Tests and evals that could pass a wrong answer, or miss a regression:
  - A table of 43 guard refusals (file writes, `gh` and git writes, `curl` sends, `sed -i`,
    `find -exec` and the rest), each checked for its reason; most had no test.
  - The `delta-review` cases need the grade in the Affects cell. `cold-review-delta` rejects "no
    unlogged change" and a base that doesn't exist. `cold-review-delta` fails a skill that commits, and `spec-done`
    diffs against setup's HEAD, so a committed edit can't hide.
  - The runner tests check that each cap and sandbox flag reaches `claude`, as does
    `test_run_spike.py` for a spike's $2 and 60 turns.
  - An ideas-depth fixture tests the Candidate pool and Shortlist checks for free.
  - `test_prepare_spike.py` and `test_run_agent.py` use a home of their own, not `~/.cache`.
  - `replay_guard.py` replays every Bash command from the headless runs, of any date, and fails if
    one gets a different verdict now than it got when it ran.
- Both eval runners refuse an empty cases folder instead of crashing on bash 3.2, clean up their
  temp folders and eval notes if interrupted, and the skill runner counts only this run's results.
  The agent runner fails a research case when `~/notes` isn't a git repo, since it can't see
  changes there.
- `mdcheck.py` holds the delta-review pattern, the record path and the secrets scan the checkers
  each kept a copy of.

## 2026-09-26

### Added

- This changelog, drawn from the commit history.

## 2026-09-25

### Security

- The agents run headless inside an OS sandbox, with a cost cap on each run. A reply that isn't in
  its agent's format is refused.
- The agents' Bash can't write to `~/.claude`, `~/notes` or `~/code`, and can't read session history.
- Agent and spike runs don't load a reviewed repo's own settings or `CLAUDE.md`.
- The guard allows only a short list of git's own options, runs `git-read.py` without a pager, and
  limits the arguments of the scripts that run outside the sandbox.
- The guard closes three bypasses of its variable rule and size caps that the cold review found.

### Added

- `/spec quick`, for small changes whose approach is settled.
- `/spec` fails a reviewed or in-progress spec whose changes skipped the delta review, and makes
  that gate hard to slip past by accident.
- `/spec done` asks about each work item's Done when.
- `/cold-review` works out a document's review state and diff base with a script, diffs a delta
  review from the original review commit, and finds changes that weren't logged.
- Tests for the agent launcher, the record layout and `check-spec.py`'s citation and work-item
  checks; a replay of the headless agent runs through the guard; and the first skill eval.
- Agent evals for the researcher at quick and ideas depth, and for `/cold-review`'s delta path.
- A workflow diagram in the README, drawn by `docs/diagram/workflow.py`, which also draws a
  1280x640 social preview card.

### Changed

- `/research` is safe to run beside another `/research`, and commits only the files it names in
  `~/notes`.
- `/research` says in the note when verification checked only a sample of the claims, matches
  Verification rows as whole words, and checks figures beyond WebFetch's summary.
- `/research` pre-approves `/idea`'s git commands.
- `/spec` reads a house-format spec's status and warns when it states none.
- `/spec` runs one verifier round 2, and each finish gets its own run directory.
- `/spec` and `/cold-review` run directories are named after the repo as well as the document.
- The checkers share one markdown helper module, which reads fences, tables, lists and account IDs
  the way markdown and YAML do.
- The skills and agents load less text: restated reasons are trimmed from the three largest skills.
- The README is rewritten for readability. It defines terms before using them, its stages match the
  diagram, and it has a clone step. The cold review's findings are folded in.
- `CLAUDE.md` gives current eval costs, the skill evals, and how to redraw the diagram and the
  social preview.

## 2026-09-24

### Security

- The guard keeps credentials out of the agents' reach, and closes variable, symlink, URL-size and
  git pre-approval leaks.
- Spike sessions get a wider read-deny, prepared by `prepare-spike.sh`.

### Added

- `/spec done`, to settle a spec after it's built. The plan stays in the spec and its history goes
  in a separate record.
- A delta review: a later review covers only the changes logged since the last one.

### Changed

- One cold reviewer agent serves both `/cold-review` and `/spec`, and spikes move into their own
  file.
- The checkers ignore `{{` in code, scan spike results, and count unreviewed changes.
- A later part of a split spec can keep its work-item numbers.

## 2026-09-20

### Added

- `/cold-review`, a skill that gives any markdown file an adversarial cold read.

## 2026-09-18

### Added

- An MIT licence, so these skills can be copied.
- A `CLAUDE.md` for working on the skills themselves.

### Changed

- The README is written for someone who hasn't used these skills.

## 2026-09-17

### Added

- `/spec` step 7, Spike: spike questions run in sandboxed headless sessions, and the answers are
  folded back into the spec. It comes with spiker rules, sandbox settings, a launcher script, spike
  entries in the template, and spike results checked by the verifier.
- The spec checker fails when a spike results file is missing.
- An agent eval for spike results, and a full baseline run.

### Changed

- Spikes can render charts locally with helm.
- Spike sessions use narrower write denies and a sandbox-safe git rule, and keep the spiker's git
  directory outside `src/`.
- Step 7's folded lines don't count towards the spec's word limit.
- `/spec` says what a spike can't fetch, and how to re-run a question left Open.
- `skills/synced/`, the account skills Claude Code syncs, is git-ignored.

## 2026-09-15

### Security

- The guard blocks environment-variable assignments that change what a command runs, and treats
  variables that only Bash exports as dangerous.

### Added

- Four agent evals for the research and spec verifiers.
- `/research` hunts for prior art behind absence claims at full depth, adds a narrow third
  verification round, and caps the number of claims.
- `/research` at ideas depth files the top three ideas as idea notes.
- `/spec` saves the cold review in the spec, and re-checks the spec after spikes.

### Changed

- `/research` records every verifier row, and cuts only unverified points to meet the word limit.
- `check-note.py` compares the Verification header with its table, and allows 10 % over the limit
  once a note is verified.
- `check-spec.py` treats a saved `## Cold review` section as a record.
- The repo moved from `~/.claude` to `~/code/github.com/claude-skills`, with symlinks back into
  `~/.claude`.

## 2026-09-14

### Added

- The first version: the `/research`, `/spec` and `/idea` skills, their agents, and the guard hook.
- `/research ideas`, for a ranked shortlist of things to build.

### Changed

- When filing a shortlist, `/research` matches existing idea notes by title.

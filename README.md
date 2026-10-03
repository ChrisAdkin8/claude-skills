# claude-skills

Claude Code commands that turn an idea into a checked plan for changing your code. Claude
researches the idea and writes the plan. Then separate agents check both, before anyone writes a
line of code.

Each claim in the research cites a source, and each claim in the plan cites the lines of code it
rests on. The checkers are fresh Claude sessions that never saw your conversation, so they check
what was written, not what was meant.

**Is it for you?** It's for people who use Claude Code most days and want a plan checked before
code gets written. It has only been tried on macOS. The research and each check run a paid
agent, capped at $5 a run ($10 for the research). Each `/implement` run's implementer is capped at
$20 in all, and each of its up to two checker runs at $5.

[Try it](#try-it) · [How it works](#from-idea-to-merged-change) ·
[A worked example](#a-worked-example) · [Safety and cost](#safety-and-cost)

## The five commands

| Command | What it does |
|---|---|
| `/idea <description>` | Saves an idea as a note. |
| `/research <question or idea note>` | Researches it and writes a note that cites a source for each claim. An agent checks the claims. |
| `/spec <research note>` | Writes a plan, called a *spec*, into the repo the change touches. Agents check it. |
| `/cold-review <markdown file>` | Gives any document the same independent review a spec gets. |
| `/implement <spec>` | Implements a reviewed spec, test first, on a branch of its own. A sandboxed checker re-runs each work item's test. |

Notes live in `~/notes`, and specs live in the repo they describe. Only `/implement` writes code,
and only on its own branch, in a separate copy of the repo called a *worktree*.

## The workflow at a glance

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/workflow-narrow-dark.png">
  <img src="docs/workflow-narrow.png" alt="Workflow diagram. Six stages run in order: Capture with /idea, Research with /research, Plan with
/spec, Spike with /spec spike, Implement with /implement, and Close out
with /spec done. Under each command, a line says whether the stage's work runs in your session or in
a subagent: Research, Spike and Implement use subagents. Research also rebuilds the notes index; a
research-verifier checks its key claims, and check-spec.py, a spec-verifier and a cold-reviewer
check the spec. /spec quick skips the review and spikes, a spec edited after its review gets a delta
review before Implement, and research proved wrong loops back to update the note. A band shows
/cold-review's five steps for any markdown document, and another shows how every agent is contained:
its own headless session, an OS sandbox, a guard hook and cost caps.">
</picture>

Full size, easier to read on a phone: [light](docs/workflow.png) or
[dark](docs/workflow-dark.png).

How to read it:

- It follows one change from idea to merged code, top to bottom.
- Each numbered stage shows the command you run, what it does and where its output goes.
- Under each command, it says whether the work runs in your session or in a *subagent*. A
  subagent is one of the agents: a separate Claude session that hasn't seen your conversation.
- Purple boxes are the agents and scripts that check the work.
- The pink box is a check that runs only if the spec was edited after its review.
- Dashed lines are shortcuts and loops off the main path.
- The two bands at the bottom cover `/cold-review` and the limits every agent runs under.

## Try it

### Requirements

- **Claude Code 2.1.277 or later.** The agents rely on a sandbox rule that holds from that version
  on. Before it, one command allowed to run outside the sandbox, such as `gh`, took any command run
  along with it outside too. Last tested on 2.1.285; don't assume the sandbox works on anything
  older.
- **macOS.** Nothing has been tried anywhere else ([Linux notes](docs/containment.md#on-linux)).
- **`python3`**, for the checking scripts. Some spikes also use `uv`.
- **Your code in git repos under `~/code`**, such as `~/code/my-app`. `/spec` and `/implement`
  work only on a repo there, and stop anywhere else.
- **Optional: `gh` (logged in) and `jq`**, to check how well maintained an open-source project is,
  and **`gcloud` (logged in)** for Google Cloud prices. Without them, the research marks those
  figures *(unverified)*.

### Install

Inside Claude Code, add this repo as a *marketplace* (a catalogue of plugins), then install the
plugin from it:

```
/plugin marketplace add ChrisAdkin8/claude-skills
/plugin install checked-plans@checked-plans
```

The plugin is called `checked-plans`; the repo keeps the name `claude-skills`. That gives you
`idea`, `research`, `spec`, `cold-review` and `implement`, and the hooks and agent files they use,
from Claude Code's plugin cache. The commands are named `/checked-plans:idea`,
`/checked-plans:research`, `/checked-plans:spec`, `/checked-plans:cold-review` and
`/checked-plans:implement`, and the short names `/idea`, `/research`, `/spec`, `/cold-review` and
`/implement` work too while no other skill has the name. This README writes the short ones.

**Two things a plugin can't install for you.**

- **`~/notes`.** The commands keep their notes there, and the location isn't configurable yet. Set
  it up as the next section says.
- **Deny rules for your own sessions.** A plugin can't ship permission settings. What keeps the
  agents away from your credentials and session history, the sandbox settings and the guard,
  travels with the plugin. Your own sessions get none of it. To give them the same denies, copy
  the `permissions.deny` list in [`hooks/user-deny.json`](hooks/user-deny.json) into
  `permissions.deny` in your user settings file, `~/.claude/settings.json`. It's the agents' list
  without the rule that hides `~/.cache/agent-runs`, because `/research`, `/spec` and
  `/cold-review` read each agent's reply there, and a deny rule would stop them.

**To work on the repo** rather than use it, clone it anywhere and run Claude Code from the clone
with the plugin loaded from that directory:

```
git clone https://github.com/ChrisAdkin8/claude-skills.git
cd claude-skills && claude --plugin-dir .
```

**If you installed this repo the old way**, by linking it into your `.claude` folder, remove the
links: `ls -l ~/.claude` shows any of `skills`, `hooks` or `agents` with an arrow into this repo,
and `rm ~/.claude/<name>` removes one. Left in place, they define every skill a second time, and
their commands are no longer pre-approved.

**If you installed it as `claude-skills`**, before it was renamed on 2026-10-01, remove that
install and its marketplace, then add and install it again as above:

```
/plugin uninstall claude-skills@claude-skills
/plugin marketplace remove claude-skills
```

Claude Code's plugin checks now reject names that start with `claude-`, because they read as
Anthropic's own.

`/research`, `/spec`, `/cold-review` and `/implement` start only when you type them, because each
launches paid agents. `/idea` is cheap, so Claude may also start it when you ask it to jot
something down.

#### Update

Claude Code doesn't fetch new versions of this plugin by itself: for marketplaces like this one,
auto-update starts turned off. To update it, run these in a terminal, outside Claude Code. The
first fetches the marketplace's latest copy, and the second updates the plugin from it.

```
claude plugin marketplace update checked-plans
claude plugin update checked-plans@checked-plans
```

Inside Claude Code, `/plugin marketplace update checked-plans` does the first, and **Update now**
on the plugin in `/plugin`'s **Installed** tab does the second. Either way, the new version loads
in your next session, or after `/reload-plugins` in one that's open. To have Claude Code update it
for you, run `/plugin`, pick `checked-plans` on the **Marketplaces** tab and choose **Enable
auto-update**.

### Set up `~/notes`

The commands keep their notes in `~/notes`. It must be a git repo, because they commit to it.
This repo doesn't create it for you, so make it and add these files:

```
mkdir -p ~/notes/templates ~/notes/ideas ~/notes/research ~/notes/projects/mindshare && git -C ~/notes init
```

| File | What to put in it |
|---|---|
| `CLAUDE.md` | Your rules for notes, such as tags and *frontmatter* (the block of settings between `---` lines at the top of a note). The `researcher` agent reads it before it writes. Include a Topics section with a command that lists the topics in use, like the one below. |
| `templates/idea.md` | The layout `/idea` starts each note from. |
| `templates/research.md` | The layout for a research note. Give it a `topic:` line. |
| `templates/research-ideas.md` | Only for `/research ideas`: the layout for a ranked list of ideas. Give it a `topic:` line too. |
| `projects/mindshare/attention-evidence.md` | Only for `/research ideas`: a table of past launches (repos, posts, demos) and the attention each got, such as stars or upvotes. `/research ideas` ranks ideas against it and adds new rows. |
| `decisions/` | Optional: notes you write by hand to record a choice the research left open. `/spec` follows an accepted decision over the research's recommendation. |

The command for the Topics section:

```
grep -h '^topic:' ~/notes/research/*.md | sed 's/^topic: *//; s/ *#.*//' | sort | uniq -c | sort -rn
```

The research templates need the headings a research note must have, because `check-note.py`
fails a note without them. The `REQUIRED` list near the top of
[`check-note.py`](skills/research/scripts/check-note.py) names them for each kind of note.

Only `/cold-review` and `/implement` work without `~/notes`.

### Your first run

Start `claude` in any folder and try these in order. Each one shows that a bit more of the setup
works.

1. **`/idea A mind map of my notes`.** Free, apart from your usual Claude use. You should get a
   new note in `~/notes/ideas/`, committed to the notes repo.
2. **`/research quick What licence is the pyarrow package released under?`.** This takes a few
   minutes and runs two paid agents: one researches, the other checks. You should get a short,
   cited note in `~/notes/research/` with a `## Verification` section at the end, and a rebuilt
   `~/notes/index.md`.
3. **`/spec quick <a small change you want>`**, run from inside a git repo under `~/code`. This
   runs one paid agent, the verifier. You should get a spec in that repo's `docs/specs/`, and a
   record of its checks beside it. `/spec` may edit files there without asking. If the repo
   already keeps its specs somewhere else, the spec goes there instead, and `/spec` asks before
   each edit.

If a step stops with a message about `~/notes`, look again at [Set up `~/notes`](#set-up-notes).

## From idea to merged change

The six stages match the diagram.

1. **Capture: `/idea <description>`** saves a note in `~/notes/ideas`.
2. **Research: `/research <question or idea note>`** writes a note to `~/notes/research`, citing a
   source for each claim. A `research-verifier` agent then checks the claims the conclusions
   depend on, and reports any it couldn't confirm. Last, `/research` rebuilds `~/notes/index.md`,
   a map of every note by topic ([view it as a mind map](#view-the-notes-as-a-mind-map)).
3. **Plan: `/spec <research note>`** writes a spec into the repo the change touches. The spec is
   split into work items. Each says what to change and how you'll know it's done, and points at
   the code it relies on as `path:line`. Three checks follow:
   - **A script,** `check-spec.py`, checks that every `path:line` points at lines that existed
     when the spec was written. It also checks that each work item says how you'll see it's done,
     and that no secrets or unfilled template text were left in.
   - **A `spec-verifier` agent** checks every citation, number and borrowed claim, and reports
     what doesn't hold.
   - **A `cold-reviewer` agent** gives the spec a *cold review*: one hard, sceptical read by an
     agent that has seen none of the conversation behind it. It looks for guesses stated as facts
     and costs nobody counted.

   Everything the checks found is kept in the spec's *record*, a file in a `records/` folder
   beside the spec, so the spec itself stays clean.
4. **Spike: `/spec spike <spec>`**, or offered at the end of `/spec`. A *spike* is a short
   experiment that answers a question reading the code can't settle. Each runs as a separate
   Claude session, in a scratch copy of the code, inside a sandbox and under a cost cap. `/spec`
   then updates the spec with the answer.
5. **Implement: `/implement <spec>`**, once the spec, its record and its spike results are
   committed. It first checks the spec: it must be `reviewed`, pass `check-spec.py`, and cite no
   code that has changed since it was read (else `/spec finish <spec>` updates it). Then it makes
   a worktree on the branch `implement/<spec name>` and hands the work to an implementer, an agent
   in a session of its own. The implementer does the work items in order, each test first and in
   its own commit, then tidies the code with `/simplify` and `/code-review`. A sandboxed checker
   then re-runs each work item's "Done when" test. What they found goes in the spec's record, on
   the branch. It never pushes or merges.
   ([tools spec](docs/specs/2026-09-26-implement-skill-1-tools.md),
   [skill spec](docs/specs/2026-09-26-implement-skill-2-skill.md))
6. **Close out: `/spec done <spec>`**, given the spec's path in `/implement`'s worktree and run in
   the same session, notes in the record where the implementation left the spec, marks the spec
   done, and points out any research the implementation proved wrong.

### Smaller changes: `/spec quick`

For a small change whose approach is settled, `/spec quick` stops after the verifier: no cold
review, no spikes. Later, `/spec finish <spec>` gives it the cold review, and `/spec spike <spec>`
runs any spikes.

### Changing a spec after its review

You may edit a spec after its cold review. If you do, the record lists each change as a
`Not reviewed:` line. Run `/cold-review <spec>` to give those changes a *delta review*: one
follow-up review of only what changed.

A spec's `status` says where it is: `draft`, `reviewed` (ready to implement), `in-progress` or
`done`. Until its changes have had their delta review, `check-spec.py` fails a spec marked
`reviewed` or `in-progress`, so nobody implements unchecked changes by mistake.

### A worked example

The [mind-map index](#view-the-notes-as-a-mind-map) went through every stage on 2026-09-27:

1. **Capture.** No idea note: the question went straight to `/research`.
2. **Research.** The note compared four ways to map the notes and recommended a generated Markmap
   outline. The verifier checked a sample of its claims, 14 of 37, and confirmed them all. The
   claim that Markmap draws an outline as a mind map wasn't in the sample; the spike confirmed it.
3. **Plan.** [The spec](docs/specs/2026-09-27-notes-mindmap-index.md) has seven work items. The
   spec-verifier found that one expected 37 idea notes when there were 40. The cold review found
   eight problems. One was a check that would pass without testing anything, because it called a
   script by a name the shell couldn't find. Both are in
   [its record](docs/specs/records/2026-09-27-notes-mindmap-index-record.md).
4. **Spike.** A prototype over the real notes showed that two levels of topics stay easy to read:
   5 areas, and at most 7 notes under any heading
   ([results](docs/specs/spikes/2026-09-27-notes-mindmap-index-results.md)).
5. **Implement.** One commit per work item, W1 first. Two of them changed only `~/notes`, so they
   were committed there. Running `/research` for real found a counting bug the tests had missed.
6. **Close out.** `/spec done` wrote seven lines in the record on where the implementation left the
   plan, and marked the spec done.

## Cold review of any document

**`/cold-review <markdown file>`** hands a document, such as a runbook, README, design doc, spec
or research note, to a `cold-reviewer` agent. First the skill works out what kind of document it
is and what its reader needs to do with it. Then it writes the reviewer's instructions, launches
it, and passes on what it finds.

- **The reviewer only reads.** It checks what it can by reading the files a document points at,
  such as build scripts and config. Where only running a command would settle a claim, it says so
  rather than guessing the result.
- **You pick which findings get fixed.** The skill edits the document only for those.
- **It asks before saving the review,** into the document's record. A spec's review is the
  exception: it's saved without asking, because the spec's checks read it.
- **Each document gets one full review.** After that, running `/cold-review` again gives one delta
  review of the changes logged since, and no more. A reviewer asked to find gaps finds some
  whether or not any exist, so chasing round after round makes the writing defensive.
- **The reviewer gets pointers, not opinions.** The skill tells it where to look (the repo, the
  entry points, the rules files). It never says what the author thinks is weak, or why it was
  written that way. A reviewer handed the author's framing checks the framing, not the document.
- **`/cold-review prompt <file>`** writes the reviewer's instructions for you to run yourself in a
  new session, instead of launching an agent.

## View the notes as a mind map

Every research note has a `topic`, such as `kubernetes` or `claude-code/research-skill`: an area,
and optionally a sub-area under it. At the end of each run, `/research` rebuilds `~/notes/index.md`
from these topics. It's a nested outline: topics are headings, research notes are links under
them, and each idea or decision note sits under the research note it names. A note with no topic,
or that names no research note (a new `/idea`, say), goes under a heading called Unfiled. A mind
map draws that outline as a tree of bubbles branching out from the middle.

There are three ways to view it, easiest first:

1. **In VS Code.** The links open your notes.
   1. Install the [Markmap](https://marketplace.visualstudio.com/items?itemName=gera2ld.markmap-vscode)
      extension, by gera2ld.
   2. Open `~/notes/index.md`.
   3. Click the Markmap icon at the top right of the editor, or run **Markmap: Open as markmap**
      from the Command Palette (Cmd+Shift+P).

   The map opens beside the file, showing the first two levels. Click a bubble to open or close
   its branch, and click a note's title to open that note.
2. **In a web browser, as a single file:**

   ```
   npx markmap-cli --offline -o /tmp/notes-map.html ~/notes/index.md
   ```

   This draws the map into one web page and opens it. `npx` runs the tool without installing it
   for good, and saving to `/tmp` keeps an extra file out of your notes repo. Links to notes may
   not open from the browser.
3. **Without Markmap.** Open `~/notes/index.md` in any markdown viewer, such as GitHub, Obsidian or
   VS Code's normal preview. It shows the same tree as an indented list.

To rebuild the index by hand, for example after `/idea` adds a note, run the script from the
installed plugin. The plugin's folder changes with each update, so the first line looks it up in
Claude Code's record of installed plugins, and the second runs the script from there:

```
plugin=$(python3 -c 'import json, sys; print(json.load(sys.stdin)["plugins"]["checked-plans@checked-plans"][0]["installPath"])' < ~/.claude/plugins/installed_plugins.json)
python3 "$plugin/skills/research/scripts/build-index.py" ~/notes
```

From a clone, run `skills/research/scripts/build-index.py ~/notes` instead. Don't edit `index.md`
itself: the next rebuild overwrites it.

## Safety and cost

Every agent runs as its own session, with no one at the keyboard, and two layers limit what it
can do:

- **A sandbox,** built into Claude Code and enforced by the operating system. It stops the
  agent's shell commands reading credentials or anything in `~/.claude` but the plugin itself,
  writing to your code, notes or settings, or reaching websites that aren't on an allowed list.
- **A guard,** a script that checks each action before it runs and can refuse it. It keeps
  credentials out of reach, and hides past conversations and the rest of `~/.claude`, so a checker
  can't see how the document it checks was written. In `~/.claude` an agent may read only its own
  saved tool output and the plugin's files.

A few things run outside the sandbox, and one, the researcher's AWS and Terraform documentation
servers, isn't checked by the guard either. `/implement`'s implementer has to edit and commit your
code, so it has a sandbox of its own: it may write its worktree and that branch's git files, with
no network, but not your repo's shared git settings or anything outside. If your own
`~/.claude/settings.json` sets something that could widen that sandbox, such as a `sandbox.network`
entry, it refuses to start and names the setting. The guard doesn't check it, and your own hooks still run outside its sandbox. Only use it on your own repos and reviewed
specs. [How the agents are contained](docs/containment.md) lists them all.

What things cost:

- **Each agent run** is capped at $5, or $10 for the researcher. The `RUN_AGENT_MAX_USD`
  environment variable overrides both. Agents run on your default model, or on the one
  `RUN_AGENT_MODEL` names (`sonnet` or `opus`).
- **Each spec's implementer** is capped at $20 in all, across every `/implement` run of that
  spec and every resume with an answer, until you remove its cost ledger,
  `~/.cache/implement-ledger/<repo>--<spec>.jsonl`, by hand. The `IMPLEMENT_MAX_USD` environment
  variable overrides the cap. Each of its up to two checker runs is capped at $5.
- **Each spike** is capped at $2 and 60 turns. A *turn* is one step: Claude replies once, and may
  use a tool. Assume a spike that fetches anything from the web costs close to its cap.
- A cap stops a run only after the turn that crosses it, so a run can go over by up to one turn.

## Working on this repo

[Working on this repo](docs/repo-guide.md) has what's where, how to test a change, and what the
paid tests cost. [`CLAUDE.md`](CLAUDE.md) has the rules for making a change.

[Could a cheaper model check claims first?](docs/checker-models.md) tests six models on the
verifier's past work. Haiku did best, but we haven't built it in yet.

[Anti-slop practice](docs/anti-slop-practice.md) gathers what AI coding vendors and practitioners
advise against padded, out-of-scope agent code, and ranks six changes to `/implement` that follow
from it. None is built in yet.

## Licence

MIT, so copy what's useful into your own `~/.claude`. See [`LICENSE`](LICENSE).

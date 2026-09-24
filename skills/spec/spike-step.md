# /spec step 7: Spike

`~/.claude/skills/spec/SKILL.md` loads this file at step 7, and `/spec spike <spec>` starts here. It runs under that skill's `allowed-tools`.

Some spike questions can be answered by an experiment. Each of those runs as a headless `claude -p` session, sandboxed and capped at $2 and 60 turns, in a scratch copy of the code at read-at. Its verdict is then folded into the spec. The spiker's rules live in `~/.claude/skills/spec/spiker.md`, its sandbox and permission settings in `~/.claude/skills/spec/spike-settings.json`, and its launch command in `~/.claude/skills/spec/scripts/run-spike.sh`. Don't restate the rules in briefs; edit `spiker.md` to change them.

In `spike` mode, start here. Take the repo from the spec's location, and `cite-repo` and `read-at` from its frontmatter, or its "Read at `<sha>`" line, as `finish` mode does. If `## Spike questions` says "None.", say so and stop.

**Names.**
- `<basename>`: the spec's filename without `.md`, e.g. `2026-09-17-spec-spike-phase`.
- `<results>`: `<spec dir>/spikes/<basename>-results.md`. The spec cites it by its path from the repo root.
- `<scratch>`: `~/.cache/spec-spikes/<repo dir name>/<basename>/S<n>`, where `<n>` is the spike question's number.
- `<source repo>`: the spec's `cite-repo` if set, else the repo.

**Tool calls.** `allowed-tools` pre-approves only the command shapes given below, so use them exactly:
- In every Bash call, write paths under the home directory with `~`, not expanded (`~/code/…`, not `/Users/<name>/code/…`).
- Run scripts directly, not through `python3` or `bash`.
- Read files with the Read tool, never `cat` or `ls`; make files with the Write tool, never `cp` or a redirect.
- If a call this step needs is refused anyway, stop step 7 and tell the user which call was refused and why. Don't work around it with another command, and never build or copy `src/` or any other scratch file by another route: a spike run on anything but the export at read-at answers the wrong question.

**Guard.** If any spike question already has an indented `Answered:` or `Partly answered:` line, refuse and say why: one spike round per spec, and that includes spikes run by hand. A question whose only folded line is `Open:` is the exception: nothing was learned, so it can run again. In that case triage only those questions, leave the answered ones alone, and replace each one's `Open:` line rather than adding a second line under it.

## 7a. Triage

Give each question in `## Spike questions` one route:
- *spike*: the answer can be observed locally, or from allowlisted hosts, and a work item, Done when or Background claim changes with it;
- *research*: a doc settles it;
- *decision*: it's a preference, so it's the user's to answer;
- *deferred*: it needs credentials, a cloud account, a cluster, `docker`, code a work item hasn't built, or the repo's code when read-at is `none`.

On a re-run allowed by the Guard, the questions to triage are only those whose folded line is `Open:`. If there are *spike* routes, ask one AskUserQuestion multiSelect question listing them, recommended first, up to four. With only one, add a second option, "Skip spikes", since a question needs at least two. With more than four, the rest become *deferred* with `Open: over the four-spike limit`. A *spike* the user doesn't pick gets `Open: not picked`.

Write the routing in the spec's record, `<spec dir>/records/<basename>-record.md` (start it from `~/.claude/skills/spec/record-template.md` if it doesn't exist), under `## Spikes`, one line per question: `- Question <n>: Route: spike. Changes: <the work items and quoted claims that change with the answer>. Expect: <what you expect the experiment to show, written now, before it runs>. Box: $2, 60 turns; hosts: <list, or none>.` The spec itself only gets the answer line, in 7c: it stays the plan.

Spikes have their own uv cache, `~/.cache/spec-spikes/.uv-cache`, never the user's `~/.cache/uv`, so a spike that runs Python with packages (`uv run --with botocore`) lists `pypi.org` and `files.pythonhosted.org` in its hosts unless an earlier spike already fetched them. List every host the experiment reaches, including redirect targets: GitHub serves release assets from `release-assets.githubusercontent.com`, not `objects.githubusercontent.com`. A spiker can't use `helm`, `gh` or another Go CLI to fetch over the network at all — they fail TLS in the sandbox — so an experiment that needs a chart or a release fetches it with `git` or `curl` and works on the local copy (`skills/spec/spiker.md`, rule 6).

Give each of the others a record line too, `- Question <n>: Route: research.`, `Route: decision.` or `Route: deferred.`, and under a deferred question in the spec an indented `Open: <why>`, so whoever builds from the spec sees it's unanswered. If no spike was chosen, skip to 7e.

## 7b. Run

For each chosen spike, in order:

1. Prepare its scratch directory in one foreground Bash call: `~/.claude/skills/spec/scripts/prepare-spike.sh <scratch> <source repo> <read-at>`, with both paths written with `~`, e.g. `~/.claude/skills/spec/scripts/prepare-spike.sh ~/.cache/spec-spikes/r/2026-09-17-x/S1 ~/code/github.com/o/r ac65fbd`. When read-at is `none`, pass `none none` for the last two. The script checks every argument, then clears the directory and exports the source repo at read-at into `src/`. Nothing else puts code in `src/`. If it refuses, give the user its message and stop step 7.
2. With the Write tool, write `<scratch>/spec.md`, a copy of the spec as it stands; the spiker's settings deny reads of `~/code`, so it can't read the original. Write `<scratch>/brief.md` with these fields and nothing else:
   - the question, verbatim;
   - its `Changes:`, `Expect:` and `Box:` from the record's line for that question, one per line;
   - `Runs:` 3 when timing, network or randomness is involved, else 1;
   - `Spec: spec.md`.
3. Read `~/.claude/skills/spec/spike-settings.json` and Write it to `<scratch>/settings.json`, with the spike's hosts in `sandbox.network.allowedDomains`. Change nothing else.

Then, in one message, make one Bash call per spike with `run_in_background: true`: `~/.claude/skills/spec/scripts/run-spike.sh <scratch>`. Don't `cd` to the scratch directory or call `claude` yourself; neither can be pre-approved. The script writes `run.json` and `run.err`, and the spiker writes `results.md`. `--max-budget-usd` stops a run only after the turn that crosses it, so a run can go over $2 by up to a turn.

Tell the user in one line which spikes are running. End your turn. Each run's completion notification arrives on its own; fold only once every run has returned.

## 7c. Fold

1. **Results file.** Read each spike's `run.json`, `run.err` and `results.md` with the Read tool. Bash `mkdir -p <spec dir>/spikes`, with the path written with `~`, e.g. `mkdir -p ~/code/github.com/o/r/docs/specs/spikes`. Write `<results>` with a `# Spike results: <spec title>` heading and the first spike's section, then Edit it to append one `## S<n>` section for each further spike. Each section is that spike's `results.md` with every heading moved two levels down (its `# <question>` becomes `### <question>`, `## Verdict` becomes `#### Verdict`), plus `total_cost_usd` and `num_turns` from its `run.json`. Record a spike as BLOCKED, with the reason from `run.err` or `run.json`, if `run.json` is missing, its `subtype` isn't `success`, or `results.md` is missing. Step 7b cleared the directory, so any `results.md` there is from this run.
2. **Fold each verdict** under its question in the spec:
   - EXPECTED: add `Answered: <the answer> (spike S<n>, <results>)`, and drop the *(assumption)* marks it settles.
   - DIFFERENT: add `Answered:` in the same form, and rewrite the work items, Done when lines and Background named in `Changes:`, citing `<results>`. If the answer contradicts the Decision, stop and tell the user, as `SKILL.md`'s step 2 does.
   - INCONCLUSIVE: add `Partly answered:` with the spread, and turn the question into a Done when or a question for the user.
   - BLOCKED: add `Open: run after Wn`, or `Open: <what it needs>`.
3. **Log it, if the spec has a saved cold review.** A fold that rewrote a work item, a Done when, the Design or the Decision after the review is a change nobody has reviewed. Add one line per spike to the record's `## Changes since the review`: `- Not reviewed: <what the fold changed>, from spike S<n>, on <YYYY-MM-DD>.` `check-spec.py` counts them, and `/cold-review <spec>` runs the one delta review of them before implementation.

## 7d. Re-verify

Run `~/.claude/skills/spec/scripts/check-spec.py <spec> --repo <repo root> --read-at <commit>` as in `SKILL.md`'s step 3, directly and with `~` paths, until it prints `RESULT: PASS`. If a fold changed a work item or a Background claim:
- If the record (or, in an older spec, its `## Open questions`) has no `Verifier round 2 ran on` line, launch `spec-verifier` with `SKILL.md`'s step 4 brief plus `Round 2: <Wn, Wm> were revised after spikes; re-check them.` and `Spike results: <absolute path of <results>>`. Add `- Verifier round 2 ran on <YYYY-MM-DD>: after spikes.` to the record's `## Verification`. Tell the user in one line, and end your turn. When it returns, apply its fixes as `SKILL.md`'s step 5, item 2 says, and re-run the check. There is no round 3.
- If a round 2 is already recorded, launch none, and tell the user to run `/spec finish <spec>` after reviewing the changes.

## 7e. Report

In four lines or fewer:
- the spike questions by route, naming any *research* claims (for `/research finish <note> "<claim>"`) and *decision* questions left for the user;
- each spike that ran, with its verdict;
- total cost and turns across the runs;
- whether round 2 ran, that `<results>` should be committed with the spec, and the scratch directory the runs are kept in, which holds each spike's throwaway code, `run.json` and `run.err` until the same spike runs again.

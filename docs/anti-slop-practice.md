---
title: "Anti-slop practice from vendors and practitioners, and what it means for the claude-skills repo"
created: 2026-10-01
status: final
depth: full
tags: [ai-coding, code-quality, claude-code]
topic: claude-code
related: [~/code/github.com/claude-skills, ~/notes/research/2026-10-01-measuring-and-preventing-code-slop.md, ~/notes/research/2026-09-29-karpathy-claude-md-viral-tests.md, ~/notes/ideas/2026-09-29-per-principle-claude-md-ab-test.md]
question: "What do AI coding vendors and recognised practitioners recommend to stop coding agents generating slop code, which practices have evidence or broad agreement, and which changes to the claude-skills skills and agents would make code written through them by Claude Code on Sonnet and Opus less likely to be slop, in priority order?"
---

# Anti-slop practice from vendors and practitioners, and what it means for the claude-skills repo

> A research note from 2026-10-01, kept as written, apart from paths to a private machine made
> repo-relative. It read the repo at `a27b6ec`, when `/implement` was still a draft spec. `/implement`
> has since been built, so read "the draft" as `skills/implement/` and
> `hooks/agents/implementer.md`. Its first recommendation still stands: the implementer's Clean-up
> step re-runs the checks and every Done when after `/simplify` and `/code-review --fix`, but not
> `scan-diff.py`.

## Bottom line

Vendors agree: give the agent a runnable check, keep rules short, point it at existing patterns, enforce with tools [1][2][9][14]. Anthropic's model guides add scope-limiting wording for Sonnet 5.5 and Opus 5, and the Opus 5.5 guide says Opus 5's patterns "remain a reasonable starting point" [4][5][30]. No independent test of this wording turned up. The repo's skills write almost no code; the planned `/implement` would [28]. First, re-scan after its clean-up commits, because Anthropic reports the code-review skill, at Max effort, twice causing a timeout or out-of-scope edits [7]. Then add scoped wording, more scan kinds and a `Follow:` line per work item. Confidence: medium on the ranking, low on effect sizes. No eval grades generated code yet.

**Updated 2026-10-01 (Robert C. Martin).** His posts back the ranking: "You can't tell an agent to be clean" [38]. His experiment suggests a mutation score for the eval and argues against a tight complexity cap [41], and project-wide clean-up becomes its own work item [40]. The note doesn't follow him in not reading agent code [37]. Evidence: self-report and one self-rated experiment, weak.

## The question

What do vendors and practitioners recommend against slop code, what has evidence, and which ranked changes to this repo follow?

## Context

Read at `a27b6ec` on 2026-10-01. Uncommitted edits to 13 test, hook and CI files change none of the cited lines; one moves `tests.yml:30` to line 26.

- `/spec` "write[s] no code in the repo" (`skills/spec/SKILL.md:32`). Its code-directing text is the work-item fields (`skills/spec/template.md:35-39`, `skills/spec/SKILL.md:87`) and the implementation prompt, which has no scope or quality clause (`skills/spec/SKILL.md:148`). Spikes write throwaway code and are told to answer only the brief's question (`skills/spec/spiker.md:15`).
- No agent reviews built code: `spec-verifier` doesn't judge scope (`hooks/agents/spec-verifier.md:21`), `cold-reviewer` reads documents (`hooks/agents/cold-reviewer.md:17`), `/spec done` reads diffs only to see what landed (`skills/spec/done-step.md:10`).
- `/implement` is "planned but not built yet" (`README.md:189-193`). Its draft spec has an `implementer` subagent, test-first items, `scan-diff.py` per item, then `/simplify` and `/code-review --fix` (`docs/specs/2026-09-26-implement-skill-2-skill.md:21-22,69,71`).
- `CLAUDE.md` has no code rules (`CLAUDE.md:28-46`). CI lint is `--select E9,F` (`.github/workflows/tests.yml:30`). Existing code is clean on one signal (grep: one `except Exception`, `hooks/agent-guard.py:1439`).
- No eval grades code. `tests/skill-evals/cases/spec-quick/grade.py` checks record lines, and its prompt asks for a spec only.

## Findings

**Vendors: agreement**

- **A runnable check:** Anthropic ("Give Claude a way to verify its work"), Cursor (tests and linters as "clear signals for whether changes are correct") and GitHub (validating its changes makes mergeable PRs likelier) [1][14][11].
- **Short, specific rules:** Anthropic under 200 lines, "Would removing this cause Claude to make mistakes?" [1][2]; Cursor "Start simple", adding rules only for repeated mistakes [14]; GitHub "short, self-contained statements", repository-wide instructions under 2 pages [12][13]; Codex stops adding AGENTS.md files once they reach 32 KiB combined, by default [10].
- **Follow existing patterns:** Anthropic "reference existing patterns" [1]; OpenAI "follow existing patterns, helpers, naming" and "no broad catches or silent defaults" [9]; Cursor pointers to canonical examples [14].
- **Deterministic over prose:** Anthropic says CLAUDE.md is "context, not enforced"; use hooks [1][2]. Cursor says use linters, not style guides [14].
- **Google:** no anti-slop guide found; its Gemini CLI skills page asks only for a concise body and deterministic scripts [15].

**Vendors: differences that matter here**

- **Verification wording is model-specific.** The Sonnet 5.5 guide adds a "run a real check" paragraph for low effort [4]; the Opus 5 guide says remove verification instructions, which cause over-verification [5].
- **Reviewer severity.** Claude Code's guide says tell a reviewer to flag only correctness or requirement gaps, because chasing findings causes over-engineering [1]. The Opus 5 guide says "only report high-severity" is followed literally, so report all and filter in a second pass [5].
- **Extra tests and docs.** Sonnet 5.5 adds them by default; Anthropic offers an opt-out paragraph that at `xhigh`/`max` "makes changes smaller overall" [4].
- **Shipped tools.** `/simplify` runs four agents (reuse, simplification, efficiency, abstraction level), no bug-hunting; `/code-review --fix` applies findings [6].

**Community**

- *Measured:* agents add mocks in 36% of commits against 26% for non-agents, and change tests in 23% against 13% [16].
- *Practitioner reports (anecdote):* Beck watches for deleted tests [20]; Willison: "use red/green TDD" [18], and don't file unreviewed code [19].
- *Tools:* community slop scanners exist [31][32][33], and overscope flags out-of-scope edits [44]; none checks against a spec's `Files` list.
- *Governance, not generation:* 67.3% of 281 OSS AI policies demand substantial human involvement [17].

**Robert C. Martin** (his X posts, repos and debate with Ousterhout)

- *Reports (self-reported):* 14 Apr 2026: "I don't review code written by agents. I measure things like test coverage, dependency structure, cyclomatic complexity, module sizes, mutation testing" [34], repeated 23 Jul [37]. 22 May: a swarm, single-agent tweaking, then a CRAP, DRY and mutation "robustness run" [35]. 23 May: restarted agents saw their code as "what's all this shit!", which fits a fresh-context reviewer [36]; self-correction without external feedback fails on reasoning [22]. Opinion, 29 Jul: "You can't tell an agent to be clean. You have to measure the cleanliness that they produce" [38].
- *Change:* 11 Sep: "the need for any but the most liberal of harnesses may be obviated", though "Unit testing is still important. So is CRAP and Mutation testing" [39]. Clean Code 2nd ed. has an AI chapter, not read for this note [23].
- *His experiment* (8 runs, one product, his ratings): all passed acceptance, one with no unit tests; a complexity cap of 3 raised functions from 33-52 to 86-118 and scored 1-2 for cleanliness [41].
- *Conflicts:* Boy Scout rule: his `cleaner` runs CRAP on all files, keeping it at or below 10 [40], against item 1's scope revert. Small functions: he and Ousterhout agree over-decomposition is possible and differ on how far [42]; Anthropic warns against unneeded abstractions [3]. Comments: Ousterhout would write 5-10x more [42], while code-simplifier removes obvious ones [8]; a scan for comments that only restate code sits outside that dispute. Not reading code: against [19] and Booch's "trust but verify" [43].

### Project health

| Repo | Stars | Human commits 90d | Human authors 90d | Last human commit | Licence | Read |
|---|---:|---:|---:|---|---|---|
| astral-sh/ruff | 49868 | 449+ | 52+ | 2026-10-01 | MIT | Maintained; the lint tool behind items 3 and 5 [27] |
| unclebob/mutator | 4 | 4 | 1 | 2026-10-01 | none | Mutates Python; no licence, one author: don't depend on it [21] |

### Counter-evidence

- Prose rules fail: an open issue on verbose comments that ignore instructions to stop has 250 👍 and 39 comments [24], and Anthropic says CLAUDE.md isn't enforced [2].
- The scope paragraph's effects (smaller changes; about a third lower cost for the no-reviewer paragraph) are Anthropic's own tests [4]. No independent replication found.
- Review can cause slop: at `max` effort, in two cases the code-review skill timed out or made edits beyond scope [7].
- Searches for a controlled study of `/simplify` or code-simplifier reducing slop found only product pages.
- Martin's evidence has no control; Booch says metrics miss vulnerabilities and dead code [43]. His experiment is one self-rated product.

## Options

| | A: Do nothing | B: Prose only | C: Gates in the `/implement` design, then CI lint |
|---|---|---|---|
| Summary | Build `/implement` as drafted | Add scope text | Items 1-6 below |
| Downsides | Unseen out-of-scope edits | Advisory only [2][24] | Spec edit, scanner code, evals |

## Recommendation

Option C. Ranked; "evidence" is for the change working, not for the idea:

1. **Re-run `scan-diff.py` after `/simplify` and `/code-review --fix`.** The draft's Clean-up step (line 71) reverts a fix only when it breaks the suite or a Done when; add a re-scan that also reverts a clean-up commit touching a file outside every `Files` list. Make project-wide clean-up, as Martin's `cleaner` does [40], its own work item. Tell the review prompts to report everything and filter by "affects a Done when" [5]. Evidence: Anthropic-documented failure [7]. If the re-scan keeps reverting the review's edits, drop `/code-review --fix`; Martin now doubts heavy harnesses are needed [39]. Eval: a fixture with untidy adjacent code; expect zero hunks outside `Files`.
2. **Scoped wording in `agents/implementer.md`.** Use Anthropic's Overeagerness block [3] and, per model, the "stop and report" paragraph [4] or the Opus 5 scope paragraph, which the Opus 5.5 guide leaves as the starting point [5][30]. Add no generic "double-check" line for Opus. Evidence: vendor-tested only, and on Opus 5, not 5.5. Eval: A/B, 3+ runs per model.
3. **Add scan kinds** beyond the draft's six: a broad `except` or `pass`/`continue` handler (ruff S110, BLE001 [25][26]), an unlogged new non-stdlib import or manifest entry, and a comment that only restates code. Add no tight complexity cap [41]. Evidence: vendors, the related note and Martin agree on deterministic enforcement [2][29][38]. Eval: unit fixtures.
4. **A `Follow:` line in each work item** naming an existing `path:line` pattern, and a populated Non-goals (`skills/spec/template.md:25-27`). `spec-verifier` already checks citations (`hooks/agents/spec-verifier.md:25`). Evidence: three-vendor consensus [1][9][14], no controlled study. Eval: an agent case with a planted false `Follow:` citation, like `spec-miscite`.
5. **Widen CI ruff** by S110, BLE001 and ERA001, after counting hits. The draft's Baseline reads CI checks (`...-2-skill.md:68`), so the implementer meets them. Evidence: linter feedback loops work on small benchmarks [29].
6. **Three checkable lines in `CLAUDE.md`** (helpers, no catch-and-ignore, no restating comments). Evidence: weakest, mixed [29][24]; Martin: "You can't tell an agent to be clean" [38].

## Next step

Edit the draft `/implement` part 2 so its Clean-up step re-runs `scan-diff.py` (item 1), then run `/spec finish` on it. Build the code-grading eval (lines added, out-of-scope hunks, broad excepts, deleted tests, and a mutation score, since acceptance passed whatever the unit tests [41]) before items 2 to 6, so each can be A/B'd per model. One implementer run is capped at $20 (`...-2-skill.md:125`), so budget the runs.

## Open questions

- Whether a headless session can invoke `/simplify` is the draft's own open spike (`...-2-skill.md:118`).

## Sources

Checked on 2026-10-01.

1. [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices): verify-work section; CLAUDE.md "Would removing this cause Claude to make mistakes?"; reference existing patterns; adversarial-review callout on over-engineering; hooks deterministic.
2. [How Claude remembers your project](https://code.claude.com/docs/en/memory): "target under 200 lines"; CLAUDE.md is "context, not enforced configuration"; hooks for must-run steps.
3. [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices): Overeagerness sample prompt (scope, comments, defensive coding, abstractions); hard-coding prompt.
4. [Prompting Claude Sonnet 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5): "Steer initiative and scope" paragraphs; adds tests/docs by default; verification paragraph for low effort; about a third lower cost at `max`.
5. [Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5): remove verification instructions; "only report high-severity" followed literally; scope paragraph.
6. [Claude Code commands](https://code.claude.com/docs/en/commands): `/simplify` four agents, no correctness; `/code-review --fix`.
7. [Introducing Claude Sonnet 5.5](https://www.anthropic.com/claude-sonnet-5-5): FrontierCode penalises out-of-scope changes; at Max effort the code-review skill led to a timeout or extra edits in two cases.
8. [code-simplifier agent](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/code-simplifier/agents/code-simplifier.md): preserves behaviour; removes unnecessary comments; "clarity over brevity".
9. [Codex Prompting Guide](https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide): conform to codebase conventions; "No broad catches or silent defaults"; comment rule.
10. [AGENTS.md guide](https://learn.chatgpt.com/docs/agent-configuration/agents-md): stops adding files once their combined size reaches `project_doc_max_bytes`, 32 KiB by default.
11. [Copilot cloud agent best results](https://docs.github.com/en/copilot/tutorials/coding-agent/get-the-best-results): validating its changes makes mergeable PRs more likely.
12. [Copilot custom instructions](https://docs.github.com/en/copilot/concepts/prompting/response-customization): "short, self-contained statements".
13. [Copilot repository instructions](https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions): repository-wide instructions "no longer than 2 pages", in the cloud agent's prompt for generating them.
14. [Cursor: best practices for coding with agents](https://cursor.com/blog/agent-best-practices): tests and linters as "clear signals for whether changes are correct"; "Start simple"; a linter, not a copied style guide; canonical-example pointers.
15. [Gemini CLI skill best practices](https://geminicli.com/docs/cli/skills-best-practices/): concise body; scripts for deterministic tasks.
16. [Over-mocked tests (arXiv 2602.00409)](https://arxiv.org/abs/2602.00409): mocks in 36% of agent commits vs 26%; test changes 23% vs 13%.
17. [AI policies in OSS (arXiv 2609.07542)](https://arxiv.org/abs/2609.07542): 281 policies; 67.3% human involvement; 48.8% disclosure.
18. [Willison, red/green TDD](https://simonwillison.net/guides/agentic-engineering-patterns/red-green-tdd/): "Use red/green TDD"; confirm tests fail first.
19. [Willison, anti-patterns](https://simonwillison.net/guides/agentic-engineering-patterns/anti-patterns/): don't file unreviewed code.
20. [Kent Beck, Augmented Coding: Beyond the Vibes](https://newsletter.kentbeck.com/p/augmented-coding-beyond-the-vibes): loops, unrequested functionality, deleted tests.
21. `skills/research/scripts/repo-health.sh unclebob/mutator unclebob/swarm-forge`, 2026-10-01: mutator 4 stars, licence none; its README lists Python.
22. [LLMs cannot self-correct reasoning yet (arXiv 2310.01798)](https://arxiv.org/abs/2310.01798): self-correction without external feedback fails; reasoning tasks.
23. [Pearson, Clean Code 2nd ed.](https://www.pearson.com/en-gb/subject-catalog/p/clean-code-a-handbook-of-agile-software-craftsmanship-2nd-edition/P200000013239/9780135398579): published 8 Oct 2025; chapter 17 "AIs, LLMs, and God Knows What". Contents not read.
24. `gh api repos/anthropics/claude-code/issues/65961 --jq '"\(.title) | \(.state) | +1=\(.reactions["+1"]) | comments=\(.comments)"'`: open; 250 +1; 39 comments.
25. [Ruff S110](https://docs.astral.sh/ruff/rules/try-except-pass/): try-except-pass suppresses all exceptions.
26. [Ruff BLE001](https://docs.astral.sh/ruff/rules/blind-except/): flags `except Exception` and `BaseException`.
27. `skills/research/scripts/repo-health.sh astral-sh/ruff`: the table above, run 2026-10-01.
28. [Repo: claude-skills](..): files cited by path, read at `a27b6ec`; `/implement` draft specs under `docs/specs/2026-09-26-implement-skill-*.md`.
29. Measuring and preventing code slop (a private research note, `~/notes/research/2026-10-01-measuring-and-preventing-code-slop.md`, not in this repo): context files +20% cost, no success gain; linter loop; deterministic gates ranked first.
30. [Prompting Claude Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5): Opus 5 prompts "should perform well without changes", and its patterns "remain a reasonable starting point"; no scope or verification section; may end a turn with work still open; "might search and verify a little less" under a time budget.
31. [agent-sh/deslop](https://github.com/agent-sh/deslop): removes AI slop with minimal diffs; `--scope=diff` mode. Found by the verifier's prior-art search, as are [32] and [33].
32. [modem-dev/slop-scan](https://github.com/modem-dev/slop-scan): detects AI code slop patterns.
33. [aislop CLI](https://hysenlabs.com/en/projects/scanaislop-aislop): 50+ deterministic rules, run on changed files in pre-commit or CI.
34. [Martin, X, 14 Apr 2026](https://x.com/unclebobmartin/status/2044114698451476492): "I don't review code written by agents. I measure things like test coverage, dependency structure, cyclomatic complexity, module sizes, mutation testing". Text read through `https://api.fxtwitter.com/unclebobmartin/status/2044114698451476492`; x.com itself returned 402. Same for [35]-[39].
35. [Martin, X, 22 May 2026](https://x.com/unclebobmartin/status/2057809771361677498): swarm, single-agent tweaking, "robustness run" of crap, dry and mutate tools.
36. [Martin, X, 23 May 2026](https://x.com/unclebobmartin/status/2058190710436724748): fresh-context agents: "Good God, what's all this shit!"
37. [Martin, X, 23 Jul 2026](https://x.com/unclebobmartin/status/2080257779395154409): "My current strategy is to not read any of the code written by my agents"; "extreme constraints".
38. [Martin, X, 29 Jul 2026](https://x.com/unclebobmartin/status/2082497764223492161): "You can't tell an agent to be clean. You have to measure the cleanliness that they produce".
39. [Martin, X, 11 Sep 2026](https://x.com/unclebobmartin/status/2098432570887217520): "the need for any but the most liberal of harnesses may be obviated"; "Unit testing is still important. So is CRAP and Mutation testing"; "can leave scars".
40. `gh api repos/unclebob/swarm-forge/contents/swarmforge/constitution/articles/engineering.prompt` and `gh api "repos/unclebob/swarm-forge/contents/swarmforge/roles/cleaner.prompt?ref=two-pack"`: no substitute CRAP or mutation proxies; no unrelated commits; cleaner runs CRAP on all files, keeps it at or below 10, and doesn't split a single `cond` into helpers.
41. `gh api repos/unclebob/negative-test-experiment/contents/experiment-conclusion.md`: eight runs; 25/0 acceptance in all; CRAP "does not simplify. It multiplies names"; CRAP-off 33-52 functions, CRAP-on 86-118; cleanliness 1-2 on every CRAP-on row.
42. [Ousterhout and Martin, APOSD vs Clean Code](https://github.com/johnousterhout/aposd-vs-clean-code), Sep 2024 to Feb 2025: method-length, comments (5-10x more) and TDD summaries. Pre-agent, so it bears on agents only by inference.
43. [Startup Fortune](https://startupfortune.com/uncle-bob-martin-says-he-no-longer-reads-ai-generated-code-and-the-developer-world-is-split/): secondary; Grady Booch's "Trust but verify" objection.
44. [overscope](https://github.com/sandeepwastaken/overscope): compares a session against its git diff to flag out-of-scope edits, deleted tests and hidden dependencies. Found by the verifier's prior-art search.

## Verification

Checked on 2026-10-01 by research-verifier: 54 of 60 claims confirmed. Three passes: 25 rows, then 10 on a follow-up about the Opus 5.5 guide and the vendor pages the first pass didn't load, then 18 on the update adding Robert C. Martin (17 of 18 confirmed). Rows that grouped several sentences are split by sentence here, and re-checked rows replace earlier ones.

| Claim | Cited | Verdict | Resolution |
|---|---|---|---|
| First, re-scan after its clean-up commits, because Anthropic reports the code-review skill, at Max effort, twice causing a timeout or out-of-scope edits | [7] | CONFIRMED | narrowed from "review skills causing out-of-scope edits" |
| Anthropic's model guides add scope-limiting wording for Sonnet 5.5 and Opus 5, and the Opus 5.5 guide says Opus 5's patterns "remain a reasonable starting point" | [4][5][30] | CONFIRMED | Opus 5.5 guide added as [30]; it has no scope text of its own |
| The Sonnet 5.5 guide adds a "run a real check" paragraph for low effort | [4] | CONFIRMED | |
| the Opus 5 guide says remove verification instructions, which cause over-verification | [5] | CONFIRMED | re-checked: the Opus 5.5 guide neither repeats nor reverses it |
| The Opus 5 guide says "only report high-severity" is followed literally, so report all and filter in a second pass | [5] | CONFIRMED | re-checked: the Opus 5.5 guide says nothing on reviewer severity |
| per model, the "stop and report" paragraph or the Opus 5 scope paragraph, which the Opus 5.5 guide leaves as the starting point. Add no generic "double-check" line for Opus | [4][5][30] | UNSUPPORTED | narrowed: the Opus advice is the Opus 5 guide's, which reaches 5.5 only as a starting point [30]; the Evidence line now says so |
| Sonnet 5.5 adds them by default; Anthropic offers an opt-out paragraph that at `xhigh`/`max` "makes changes smaller overall" | [4] | CONFIRMED | |
| about a third lower cost for the no-reviewer paragraph | [4] | CONFIRMED | |
| Claude Code's guide says tell a reviewer to flag only correctness or requirement gaps, because chasing findings causes over-engineering | [1] | CONFIRMED | |
| Anthropic ("Give Claude a way to verify its work") | [1] | CONFIRMED | |
| Anthropic under 200 lines, "Would removing this cause Claude to make mistakes?" | [1][2] | CONFIRMED | |
| Anthropic "reference existing patterns" | [1] | CONFIRMED | |
| Anthropic says CLAUDE.md is "context, not enforced" | [2] | CONFIRMED | |
| OpenAI "follow existing patterns, helpers, naming" and "no broad catches or silent defaults" | [9] | CONFIRMED | |
| Codex stops adding AGENTS.md files once they reach 32 KiB combined, by default | [10] | UNSUPPORTED | replaced "OpenAI concrete commands", which the page doesn't say, with its confirmed 32 KiB default |
| GitHub (validating its changes makes mergeable PRs likelier) | [11] | CONFIRMED | |
| GitHub "short, self-contained statements" | [12] | CONFIRMED | |
| repository-wide instructions under 2 pages | [13] | WRONG | corrected from "review instructions": the limit is in the prompt for generating repository-wide instructions; Sources [13] fixed |
| Cursor (tests and linters as "clear signals for whether changes are correct") | [14] | CONFIRMED | quoted the page's words, not "tests as targets" |
| Cursor "Start simple", adding rules only for repeated mistakes | [14] | CONFIRMED | quoted the page's words, not "start minimal" |
| Cursor pointers to canonical examples | [14] | CONFIRMED | |
| Cursor says use linters, not style guides | [14] | CONFIRMED | |
| Google: no anti-slop guide found; its Gemini CLI skills page asks only for a concise body and deterministic scripts | [15] | CONFIRMED | |
| `/simplify` runs four agents (reuse, simplification, efficiency, abstraction level), no bug-hunting; `/code-review --fix` applies findings | [6] | CONFIRMED | |
| agents add mocks in 36% of commits against 26% for non-agents, and change tests in 23% against 13% | [16] | CONFIRMED | |
| 67.3% of 281 OSS AI policies demand substantial human involvement | [17] | CONFIRMED | |
| an open issue on verbose comments that ignore instructions to stop has 250 👍 and 39 comments | [24] | CONFIRMED | "top" dropped: the command doesn't rank issues |
| Maintained; the lint tool behind items 3 and 5 | [27] | CONFIRMED | |
| `/implement` is "planned but not built yet" (`README.md:189-193`). Its draft spec has an `implementer` subagent, test-first items, `scan-diff.py` per item, then `/simplify` and `/code-review --fix` | [28] | CONFIRMED | |
| The draft's Clean-up step (line 71) reverts a fix only when it breaks the suite or a Done when; add a re-scan that also reverts a clean-up commit touching a file outside every `Files` list | [28] | UNSUPPORTED | reworded: it described the proposed re-scan as the draft's current behaviour |
| `/spec` "write[s] no code in the repo" (`skills/spec/SKILL.md:32`) | [28] | CONFIRMED | |
| Its code-directing text is the work-item fields (`skills/spec/template.md:35-39`, `skills/spec/SKILL.md:87`) and the implementation prompt, which has no scope or quality clause (`skills/spec/SKILL.md:148`). Spikes write throwaway code and are told to answer only the brief's question (`skills/spec/spiker.md:15`) | [28] | CONFIRMED | |
| `spec-verifier` doesn't judge scope (`hooks/agents/spec-verifier.md:21`), `cold-reviewer` reads documents (`hooks/agents/cold-reviewer.md:17`) | [28] | CONFIRMED | |
| `/spec done` reads diffs only to see what landed (`skills/spec/done-step.md:10`) | [28] | CONFIRMED | |
| Uncommitted edits to 13 test, hook and CI files change none of the cited lines; one moves `tests.yml:30` to line 26 | [28] | WRONG | corrected: the uncommitted `tests.yml` edit moves the cited lint line from 30 to 26 |
| Existing code is clean on one signal (grep: one `except Exception`, `hooks/agent-guard.py:1439`) | [28] | CONFIRMED | |
| No eval grades code. `tests/skill-evals/cases/spec-quick/grade.py` checks record lines | [28] | CONFIRMED | |
| `spec-verifier` already checks citations (`hooks/agents/spec-verifier.md:25`) | [28] | CONFIRMED | |
| a populated Non-goals (`skills/spec/template.md:25-27`) | [28] | CONFIRMED | |
| The draft's Baseline reads CI checks (`...-2-skill.md:68`), so the implementer meets them | [28] | CONFIRMED | |
| Whether a headless session can invoke `/simplify` is the draft's own open spike (`...-2-skill.md:118`) | [28] | CONFIRMED | |
| One implementer run is capped at $20 (`...-2-skill.md:125`) | [28] | CONFIRMED | |
| No independent test of this wording turned up | [4][5] | CONFIRMED | softened from "Only Anthropic has tested this wording": GitHub and HN had no test, and arXiv searches returned nothing either way |
| His posts back the ranking: "You can't tell an agent to be clean" | [38] | CONFIRMED | |
| His experiment suggests a mutation score for the eval and argues against a tight complexity cap [41], and project-wide clean-up becomes its own work item [40] | [40][41] | CONFIRMED | "adds" softened to "suggests": the mutation score is the note's inference from acceptance being "silent on suite quality"; "tight" added, as the cap tested was 3 |
| 14 Apr 2026: "I don't review code written by agents. I measure things like test coverage, dependency structure, cyclomatic complexity, module sizes, mutation testing" [34], repeated 23 Jul [37] | [34][37] | CONFIRMED | |
| 22 May: a swarm, single-agent tweaking, then a CRAP, DRY and mutation "robustness run" | [35] | UNSUPPORTED | reworded: the tweet doesn't say "four-role", and single-agent tweaking came between the swarm and the robustness run |
| 23 May: restarted agents saw their code as "what's all this shit!" | [36] | CONFIRMED | |
| Opinion, 29 Jul: "You can't tell an agent to be clean. You have to measure the cleanliness that they produce" | [38] | CONFIRMED | |
| 11 Sep: "the need for any but the most liberal of harnesses may be obviated", though "Unit testing is still important. So is CRAP and Mutation testing" | [39] | CONFIRMED | |
| Clean Code 2nd ed. has an AI chapter | [23] | CONFIRMED | |
| (8 runs, one product, his ratings): all passed acceptance, one with no unit tests; a complexity cap of 3 raised functions from 33-52 to 86-118 and scored 1-2 for cleanliness | [41] | CONFIRMED | cap value added from the verifier's reading of [41] |
| Boy Scout rule: his `cleaner` runs CRAP on all files, keeping it at or below 10 | [40] | CONFIRMED | limit of 10 added from the cleaner prompt the verifier quoted |
| he and Ousterhout agree over-decomposition is possible and differ on how far | [42] | CONFIRMED | |
| Ousterhout would write 5-10x more | [42] | CONFIRMED | |
| Not reading code: against [19] and Booch's "trust but verify" | [19][43] | CONFIRMED | |
| Booch says metrics miss vulnerabilities and dead code | [43] | CONFIRMED | secondary source, as the note says |
| Mutates Python; no licence, one author | [21] | CONFIRMED | |
| If the re-scan keeps reverting the review's edits, drop `/code-review --fix`; Martin now doubts heavy harnesses are needed | [39] | CONFIRMED | the first clause is the note's own advice |
| a mutation score, since acceptance passed whatever the unit tests | [41] | CONFIRMED | |

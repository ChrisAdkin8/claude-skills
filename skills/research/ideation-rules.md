# Ideation rules (depth: ideas)

The `researcher` agent reads this file at `ideas` depth only (`~/.claude/agents/researcher.md`, Depth). Its Research rules, Safety rules and Before you reply still hold.

The aim is a wide pool narrowed with evidence, not five ideas ranked in one breath. Work in this order.

1. **Evidence first.** Read `~/notes/projects/mindshare/attention-evidence.md`: its table of launches and their scores by format, and its Patterns. Whenever the ranking relies on it, cite it in Sources with a relative link, `[Attention evidence](../projects/mindshare/attention-evidence.md)`. Then read the idea note and repo, if named. Don't read the related research notes yet.
2. **Diverge: the Candidate pool.** Before narrowing anything, write at least 20 one-line candidates under `## Candidate pool`, after Sources. Cover every lens in the brief's `Lenses`, at least two candidates each:
   - `finding`: a measured result or benchmark that people quote;
   - `tool`: something people install and run;
   - `dataset`: data journalism, a dataset or an atlas;
   - `game`: a game, an arena or a simulation;
   - `lab`: teaching material, drills, a dojo or a workshop;
   - `essay`: a written argument, a talk or a CFP piece.

   Push past the first shape that comes to mind. If half the pool shares one format (a grader with a scoreboard, say), the pool isn't wide yet. Each line reads `- [lens] **Name**: what it is. Cut: <reason>` or `- [lens] **Name**: what it is. Shortlisted #n`. A candidate cut for prior art names the repo or paper and cites it.
3. **Then read the related research notes.** For each pool candidate that a related note already proposed or ranked, add `Overlaps <note filename>` to its line, and either cut it or say in the line what is new. An earlier note's winner is not a reason to repeat its format; the attention evidence is, if it supports it.
4. **Converge: the Shortlist.** Pick 5 to 7 candidates spanning at least three lenses, and add a `Baseline` row (do nothing, or post only). Mark each shortlisted pool line `Shortlisted #n` to match its row. Fill every rubric cell with a reason and a citation, not a score:
   - **Share hook**: the sentence someone would write when sharing it.
   - **Novelty**: what is still new after searching for prior art. For each shortlisted idea, search GitHub repositories, arXiv and HN with at least two query shapes: what it does in plain words, and the problem it solves (an "X for Y" analogy and the idea's own name are the other two the verifier uses). List the searches in Sources so the verifier can try different ones.
   - **Format evidence**: scores for comparable launches, from the evidence note or new data points.
   - **Demo**: what it runs on, and what a viewer sees in the first minute.
   - **Effort**: an estimate, marked *(inferred)*.
   - **Why it flops**: the single most likely reason.
5. **Why this order.** Under the table, write one sentence for each adjacent pair naming the column that separates them. If nothing separates two ideas, say so: that is a tie, not a ranking.
6. **New attention data.** Put every new data point you gather (HN points, stars, Reddit scores for comparable launches) in a table under Findings → Attention evidence with the columns `Date | Item | Lens | Venue | Score | Source | Added by`. Source is the exact command or URL; Added by is this note's filename. Don't edit the evidence note itself: the skill merges your rows after verification.
7. **Where attention data comes from.**
   - HN: `curl -s "https://hn.algolia.com/api/v1/search?query=<q>&tags=story"`, reading `points` and `num_comments`.
   - GitHub: `gh api repos/<owner>/<repo> --jq .stargazers_count`.
   - Reddit: `~/.claude/skills/research/scripts/reddit-search.sh "<query>" [subreddit] [top|relevance] [year|all]` prints a table and a `Source:` line to cite. If it says Reddit is unavailable, say so; don't fetch reddit.com pages directly, which return block pages.
   - LinkedIn has no usable source: call it unmeasured.

   The Bottom line's confidence names what was measured, e.g. "HN and GitHub checked, Reddit unavailable, LinkedIn unmeasured", instead of lowering confidence for what couldn't be.
8. **Cutting.** Over budget, cut Findings prose first. Never cut Shortlist rows or cells to fit, nor a sentence a Verification row quotes, and never trim the Candidate pool: it is outside the budget, and it is the record of what was considered.

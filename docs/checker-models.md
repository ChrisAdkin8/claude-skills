# Could a cheaper model check claims first?

`/research` hands each finished note to the `research-verifier` agent. The verifier reads the
sources behind a sample of the note's claims, and marks each claim right or wrong. It costs about
2 to 3 cents a claim.

A cheaper model could go first and pass the claims it's sure of. The verifier would then check
only the rest. That saves money only if the cheap model rarely passes a wrong claim. So we tested
nine runs of six models on the verifier's past verdicts, on 28 and 29 September 2026.

## How we tested

- **The claims.** Every verdict the verifier gave on a research note, taken from the session logs
  Claude Code keeps. We used each claim as the verifier first saw it, before any fix. That left 698
  claims that every model answered. The verifier had found 61 of them wrong.
- **The question.** Each model got a claim and the evidence the verifier quoted for it. It said
  how likely the evidence was to back the claim, and chose a label: supported, contradicted or not
  mentioned.
- **The test.** Let through the 60% of claims a model trusts most. A good first check keeps back
  at least 82% of the wrong ones, about 50 of the 61.

This is the easiest version of the job. Each model got the right passage, often in the verifier's
own words. A real first check would have to find the passage in a web page.

## Results

| Model | Where it runs | Wrong claims kept back (goal: 82%) | Score from 0.5 (chance) to 1 (perfect) | Wrong claims let through if it passes only "supported" | Cost for 700 claims | Time a claim |
|---|---|---|---|---|---|---|
| Laya, English | your Mac | 42 of 61 (69%) | 0.70 | 13, passing 47% | free | 0.1 s |
| Laya, typed-decisions | your Mac | 42 of 61 (69%) | 0.72 | 22, passing 65% | free | 0.1 s |
| MiniCheck, Flan-T5-Large | your Mac | 43 of 61 (70%) | 0.70 | 1, passing 7% | free | 0.1 s |
| DeBERTa-v3 NLI | your Mac | 39 of 61 (64%) | 0.69 | 8, passing 26% | free | 0.1 s |
| Qwen3 8B | your Mac | 44 of 61 (72%) | 0.71 | 16, passing 70% | free | 1 s |
| **Haiku 4.5** | Anthropic | **58 of 61 (95–96%)** | **0.90–0.91** | 9 to 11, passing 80% | $0.65 to $0.72 | 2 s |
| Sonnet 5 | Anthropic | 49 of 61 (80–81%) | 0.81 | 5 to 7, passing 80% | $1.78 to $1.93 | 2 s |

Haiku and Sonnet ran twice, with the claims in a different order each time. Their results barely
moved, so the table gives the range.

## What it shows

- **The free models all miss the goal by the same wide margin.** Laya is a small model built to
  answer set questions. MiniCheck and DeBERTa are built to check a claim against a source. Qwen is
  a general chat model. All four keep back only about 70% of the wrong claims. Tuning Laya for
  decisions didn't help.
- **Haiku is the best first check, and the cheapest paid one.** It keeps back 95% of the wrong
  claims, for about a penny per ten claims.
- **Sonnet is safer if you trust the label alone.** Passing only what it calls "supported", it
  lets 5 to 7 wrong claims through. Haiku lets through 9 to 11.

## How far to trust it

- **The evidence was written by Claude.** The verifier quoted it after it had decided, so it may
  favour the Claude models. The free models got the same text, so the gap between the two groups
  is real on this test.
- **Only 61 claims were wrong.** A few claims either way moves a result by several points.
- **This was the easy version.** No model had to find the passage itself.

## What we decided

Not to build a first check yet. Checking costs a few dollars a week, and a Haiku first check would
save perhaps a third to a half of that. It would still let some wrong claims through unchecked:
3 of the 61 in this test. It would also fetch web pages outside the sandbox.

If checking costs grow, use Haiku. First test it on the hard version: fetch each source, and let
Haiku find the passage.

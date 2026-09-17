---
title: Fixture note for check-note tests
created: 2026-09-15
status: final # draft | final | outdated
depth: full # full | quick
tags: [test-fixture]
related: []
question: "Is this fixture a valid, verified full-depth research note?"
---

# Fixture note for check-note tests

## Bottom line

The fixture is valid. Widgets weigh 3 kg each [1], and gadgets ship in boxes of 12 [2]. Confidence: high, because the fixture says so.

## The question

Whether a small note with a Verification table passes the checker.

## Findings

Widgets weigh 3 kg each [1]. Gadgets ship in boxes of 12 [2].

### Counter-evidence

- No searches were run; this is a fixture.

## Options

| | Widgets | Gadgets |
|---|---|---|
| Summary | Heavy | Boxed |

## Recommendation

Use the fixture only in tests.

## Next step

Run the tests.

## Sources

Checked on 2026-09-15.

1. [Widget spec](https://example.com/widgets): 3 kg each.
2. [Gadget spec](https://example.com/gadgets): boxes of 12.

## Verification

Checked on 2026-09-15 by research-verifier: 1 of 2 claims confirmed.

| Claim | Cited | Verdict | Resolution |
|---|---|---|---|
| Widgets weigh 3 kg each | [1] | CONFIRMED | |
| Gadgets ship in boxes of 12 | [2] | WRONG | corrected from boxes of 10, cited [2] |

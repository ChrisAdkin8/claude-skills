---
title: Which small local models fit a 16 GB Mac
created: 2026-09-15
status: draft # draft | final | outdated
depth: quick # full | quick
tags: [ai, local-first]
related: []
question: "Which of four small local models fit in a 16 GB Mac's GPU memory, by Ollama's download sizes?"
---

# Which small local models fit a 16 GB Mac

## Bottom line

All four fit, but qwen3.5:9b is 9.6 GB [1], so it leaves the least room beside the others. qwen3.5:4b is 3.4 GB [1], gemma4:12b is 7.6 GB [2] and ministral-3:14b is 9.1 GB [3]. Confidence: high, from Ollama's own tags pages.

## The question

Which of qwen3.5:4b, qwen3.5:9b, gemma4:12b and ministral-3:14b fit, one at a time, in a 16 GB Mac.

## Findings

- qwen3.5:4b is 3.4 GB [1].
- qwen3.5:9b is 9.6 GB [1].
- gemma4:12b is 7.6 GB [2].
- ministral-3:14b is 9.1 GB [3].

## Sources

Checked on 2026-09-15.

1. [Ollama: qwen3.5 tags](https://ollama.com/library/qwen3.5/tags): download size per tag, 4b and 9b.
2. [Ollama: gemma4 tags](https://ollama.com/library/gemma4/tags): download size of the 12b tag.
3. [Ollama: ministral-3 tags](https://ollama.com/library/ministral-3/tags): download size of the 14b tag.

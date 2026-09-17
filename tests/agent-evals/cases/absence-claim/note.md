---
title: Turning Kubernetes rightsizing into pull requests
created: 2026-09-15
status: draft # draft | final | outdated
depth: full # full | quick
tags: [kubernetes, cost, gitops]
related: []
question: "Should we build a tool that turns Kubernetes rightsizing recommendations into pull requests against Helm values?"
---

# Turning Kubernetes rightsizing into pull requests

## Bottom line

No tool turns Kubernetes rightsizing recommendations into pull requests against Helm values [3]. Recommenders such as the Vertical Pod Autoscaler and KRR produce the numbers [1][2], but someone still copies them into Git by hand. Build a small scheduled GitHub Action that does it. Confidence: medium.

## The question

Whether a tool already turns rightsizing recommendations into Helm-values pull requests, and if not, whether to build one.

## Findings

- The Vertical Pod Autoscaler recommends CPU and memory requests for workloads [1].
- KRR computes resource recommendations from Prometheus history [2].
- Searches found no tool that writes these recommendations back to Git as pull requests [3].

### Counter-evidence

- Searches for failure reports about rightsizing pull-request bots found nothing [3].

## Options

| | Build the Action | Do nothing |
|---|---|---|
| Summary | Scheduled Action opens one PR per app | Copy values by hand |
| Effort | 2–4 weeks | None |

## Recommendation

Build the Action. This changes if a tool that already does it turns up.

## Next step

A weekend spike against one chart's values file.

## Sources

Checked on 2026-09-15.

1. [Vertical Pod Autoscaler README](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler): recommends CPU and memory requests.
2. [robusta-dev/krr README](https://github.com/robusta-dev/krr): resource recommendations from Prometheus.
3. Web and GitHub searches on 2026-09-15 for "rightsizing pull request Helm values": nothing found.

# Spike results: A topic field and a generated mind-map index for ~/notes

## S1

Run by hand in the `/spec spike` session on 2026-09-27, at the user's choice: the spike sandbox denies reads of `~/notes`, which the experiment needs. So it ran without the sandbox, on a scratch copy of `~/notes/research`, `ideas` and `decisions`, with a throwaway prototype of the Design's `build-index.py`. No file in `~/notes` or the repo was changed.

### Does a two-level topic tree over the current 31 research notes and 40 idea notes read well as a mind map?

Expect: a two-level tree over the 31 research notes gives 6-10 areas, no heading with more than about 8 research notes directly under it, and every link resolving to a file.
Runs: 1

#### Commands

```
cp -R ~/notes/research ~/notes/ideas ~/notes/decisions <scratch>/notes/
# add one `topic:` line after `tags:` in each research note, from the table below
python3 proto_index.py notes        # prototype of the Design's build-index.py
python3 proto_index.py notes; cmp   # second run, compared byte for byte
# every ](...) link in index.md checked with Path.exists()
npx -y markmap-cli@latest --offline --no-open -o index.html notes/index.md
grep -o 'initialExpandLevel.\{0,30\}' index.html
grep -o 'ideas/2026[^"\\]*' index.html | wc -l
```

#### Output

```
areas=5 headings=11 research=31 ideas_nested=40 unfiled=0
    7 side-projects/ideas
    4 claude-code/research-skill
    4 perfectscale/build
    3 rag/pipelines
    3 rag/rag-forge
    2 claude-code/newsletter-ai
    2 perfectscale/ideas
    2 perfectscale/market
    2 kubernetes/kubernetes-dojo
    1 claude-code/spike-loop
    1 kubernetes/tools
identical
unresolved links: []
markmap-cli 0.18.12; index.html 362,031 bytes
... {"initialExpandLevel":2})</script>      (the frontmatter option reaches the render)
31 research/ and 40 ideas/ links rendered as <a href="...">
```

The topics proposed, for W6 to start from (the user approves or edits them there):

| Topic | Research notes (by date and slug) |
|---|---|
| claude-code/newsletter-ai | 2026-09-13-newsletter-skills-review-automation, 2026-09-18-newsletter-skill-critical-review |
| claude-code/research-skill | 2026-09-15-research-spec-skills-review, 2026-09-17-spec-skill-spike-phase, 2026-09-26-matt-pocock-claude-skills-gaps, 2026-09-27-research-notes-mindmap-index |
| claude-code/spike-loop | 2026-09-13-spike-loop-interest-review |
| kubernetes/kubernetes-dojo | 2026-09-14-kubernetes-dojo-critical-review, 2026-09-14-kubernetes-dojo-post-fix-review |
| kubernetes/tools | 2026-09-25-versitygw-release-licence-maintenance |
| perfectscale/build | 2026-09-13-perfectscale-gitops-pr-loop, 2026-09-15-perfectscale-api-rag-corpus, 2026-09-16-perfectscale-mcp-server-build, 2026-09-22-perfectscale-dra-kueue-nvlink |
| perfectscale/ideas | 2026-09-13-perfectscale-ai-mindshare-ideas, 2026-09-15-perfectscale-api-data-ideas |
| perfectscale/market | 2026-09-16-perfectscale-ai-feature-gaps, 2026-09-25-doit-finops-gtm-strategy |
| rag/pipelines | 2026-09-16-hashi-kb-pluggable-wrangling, 2026-09-17-python-rag-pipeline-taskfile, 2026-09-24-portable-low-scaffolding-rag-stack |
| rag/rag-forge | 2026-09-18-rag-forge-code-review, 2026-09-22-graph-entity-described-lookup, 2026-09-24-rag-forge-kuberay-k3s-eks-portability |
| side-projects/ideas | 2026-09-12-k8s-ai-observability-mindshare, 2026-09-12-kubernetes-ai-side-projects, 2026-09-14-ai-repo-blog-mindshare-idea, 2026-09-14-langgraph-laptop-ideas-wide-pool, 2026-09-14-langgraph-laptop-mindshare-ideas, 2026-09-23-litellm-kubernetes-mindshare-ideas, 2026-09-27-jev-system-one-repo-ideas |

#### Verdict

EXPECTED: two levels hold. There are 5 areas, one fewer than expected, and well inside the spec's limit of 12. The fullest heading has 7 research notes, inside both the expected 8 and the spec's 15. Every link resolves, two runs give identical bytes, and markmap-cli renders the outline with its links and the `initialExpandLevel` option. No work item changes.

#### Notes

- The render confirms the claim the research didn't verify (its source [12]): Markmap draws the outline's headings and lists as a mind map.
- An empty `## Unfiled` renders as an empty node. That's harmless, and W6's Done when expects it to be empty.
- Whether a click opens the note in VS Code is spike 2's question, and wasn't tested.

Cost: this session's own turns; no separate `run.json`.

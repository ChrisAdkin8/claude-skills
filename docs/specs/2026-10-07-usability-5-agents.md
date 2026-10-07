---
title: "Usability, part 5: what the agents can reach, and what they're told"
created: 2026-10-07
status: draft # draft | reviewed | in-progress | done | superseded
research: none
idea: none
read-at: 377b2dd
cite-repo: none
---

# Usability, part 5: what the agents can reach, and what they're told

## Goal

The research and checking agents can reach the package registries, GitLab and Azure's price list, and when a site is blocked they can tell it was blocked rather than empty. The guard stops refusing ordinary project names in searches, and its refusals name the allowed way round. The credential files and secret variables it misses today are covered, in every settings file, and a moved Claude Code folder is guarded like `~/.claude`. The user hears, in one line per run, what the guard refused.

Part 5 of 7 from the usability review of 2026-10-07. It stands alone. Part 1 adds the two Claude tokens to the hidden variables; this part adds the rest.

## Decision

- **Hosts:** add the read APIs of PyPI, npm, crates.io, the Go module proxy, Maven Central, GitLab and Azure retail prices to the agents' shell allowlist. The agents can already reach any host through WebFetch, under the guard's URL size cap, so `curl` to these adds little reach, and it gives exact figures instead of a smaller model's summary.
- **Search rule:** a long run is token-like only if it mixes letters and digits. Rejected: raising the length, which lets longer tokens through as well.
- **Messages:** fix the wrong reasons and name the allowed route in each, rather than allowing more commands.
- **Coverage:** one list of credential paths, applied in the guard, every settings file and `hooks/user-deny.json`, as today's tests already require.
- **Telling the user:** the guard writes each refusal's reason, not its command, to the run dir, and `run-agent.sh` counts them.

## Background

Read at `377b2dd` on 2026-10-07.

**Hosts.** The agents' shell may reach GitHub, Hacker News, arXiv, AWS and GCP pricing and Reddit, and nothing else (`hooks/agent-sandbox.json:8`); the list is copied into each agent's instructions (`hooks/agent-sandbox.md:4`). No package registry, GitLab or Azure host is on it. The research verifier is told WebFetch "hands you a smaller model's summary of the page" (`hooks/agents/research-verifier.md:77`), and the spec verifier and cold reviewer have no WebFetch at all (`hooks/agents/spec-verifier.md:4`; `hooks/agents/cold-reviewer.md:4`). The researcher's pricing sources are AWS and GCP only (`hooks/agents/researcher.md:58-62`). The README says only that the agents reach "an allowed list" of websites (`README.md:349-351`).

**A blocked fetch looks empty.** The agents are told to read a page with `curl -s <url> | head` and its status with `curl -sI <url> | head -1` (`hooks/agent-sandbox.md:6`). Measured on 2026-10-07 through a stand-in proxy that answers 403, as the sandbox's does: `curl -s … | jq` printed nothing and the pipeline exited 0; only `-sS` printed `CONNECT tunnel failed, response 403`.

**The search rule.** The guard refuses a query holding 40 or more characters from `[A-Za-z0-9+/_=-]`, saying it "looks like a token or encoded data; search in words" (`hooks/agent-guard.py:1592-1596`). Hyphens, slashes and underscores count. Measured on 2026-10-07, the guard refused six ordinary queries naming `kubernetes-sigs/aws-load-balancer-controller`, which the researcher's own counter-evidence searches would name (`hooks/agents/researcher.md:57`), `prometheus-community/kube-prometheus-stack`, `@opentelemetry/instrumentation-aws-lambda`, the Terraform types `google_compute_region_network_endpoint_group` and `aws_vpc_endpoint_service_allowed_principal`, and `Microsoft.ContainerService/managedClusters/agentPools`. The tests try an ordinary query and a base64 one (`tests/test_agent_guard.py:737-753`), not a long name. The agents' instructions call it "a long run of letters and digits" (`hooks/agent-sandbox.md:7`), as does the containment page (`docs/containment.md:56-57`).

**Messages that send the agent the wrong way** (each measured on 2026-10-07 by feeding the guard a command):
- `gh pr diff`, `gh repo list` or `gh -R o/r issue list` get "can change GitHub; only read commands are allowed" (`hooks/agent-guard.py:789`), though `gh api` reads the same thing.
- `git check-ignore` or `git config --get` get "isn't a read-only git command" (:868), and `git tag --merged main` gets "may only list tags" (:886).
- A `$` inside single quotes, as in Azure's `$filter` query or a GraphQL `query($owner: String!)`, gets "expands something whose size and content can't be checked" (:942).
- `curl -G --data-urlencode`, a GET, gets "writes a file or sends data" (:1021).

**Credential paths the guard misses.** The guard's list (`hooks/agent-guard.py:283-291`) and the sandbox's read denies cover `~/.ssh`, `~/.aws`, `~/.config` and the rest, and Chrome alone among browsers. Measured on 2026-10-07: the guard allowed `cat` and Read of `~/.terraform.d/credentials.tfrc.json`, where `terraform login` saves its token, `~/.cargo/credentials.toml` and macOS Terminal's per-session history under `~/.zsh_sessions`, while refusing `~/.aws/credentials`; none of the three is in `hooks/agent-sandbox.json`. Firefox, Brave, Edge and Arc profiles and fish's history are missing too. The hidden variables (`hooks/agent-sandbox.json:18-27`) leave out `AZURE_CLIENT_SECRET`, `ARM_CLIENT_SECRET`, `GITLAB_TOKEN` and `NPM_TOKEN`. Shell writes are denied under `~/.claude`, `~/notes` and `~/code` only (`hooks/agent-sandbox.json:15`), so a document's repo elsewhere has no write deny from the operating system; the cold reviewer is held to read-only commands by the guard alone (`hooks/agents/cold-reviewer.md:22`).

**A moved Claude Code folder.** The guard's private folder is `~/.claude` (`hooks/agent-guard.py:302`). With `CLAUDE_CONFIG_DIR` set, Claude Code keeps its state and its `.credentials.json` there instead ([authentication](https://code.claude.com/docs/en/authentication.md)), so the session history the cold reviewer must not see is readable, and a config folder under `~/.config` makes the guard refuse the plugin's own files.

**Refusals are private.** The guard prints its reason to the agent on stderr (`hooks/agent-guard.py:337-338`), and nothing counts them, so a row marked UNREACHABLE reads the same whether the site was down or the guard said no.

**Documentation servers.** The researcher's AWS and Terraform tools are named for two specific plugins (`hooks/agents/researcher.md:4`); the README mentions the servers (`README.md:357-358`) but not where they come from.

## Non-goals

- Network for the implementer, the verifier or spikes.
- New commands for the agents, such as `awk` or a YAML tool.
- Searching the content of credential files for secrets.

## Design

**Hosts** added to `hooks/agent-sandbox.json` and `tests/skill-evals/agent-case-settings.json`: `pypi.org`, `registry.npmjs.org`, `crates.io`, `proxy.golang.org`, `search.maven.org`, `gitlab.com` and `prices.azure.com`. The researcher gets one pricing line for Azure's retail prices API, after W4 lets its `$filter` through.

**Blocked fetches.** `hooks/agent-sandbox.md` tells the agents to use `curl -sS`, which prints errors, to read a status with `curl -sS -o /dev/null -w '%{http_code}' <url>`, and that `CONNECT tunnel failed, response 403` means the host isn't on the list: use WebFetch if they have it, and say so in the evidence either way.

**Search rule.** A run of 40 or more characters from the same set is refused only if it holds both a letter and a digit, and the message quotes its first 12 characters.

**Messages.** Each listed refusal names the allowed route: for `gh`, the `gh api` form (`gh api -H "Accept: application/vnd.github.diff" repos/<o>/<r>/pulls/<n>` for a diff); for `git`, the read-only subcommands it accepts; for a single-quoted `$`, nothing, because it's allowed; for `curl -G --data-urlencode`, nothing, because it's allowed too. `gh -R <o>/<r>` and `--repo` are read as an option, not a subcommand.

**Coverage.** The guard's list, every settings file's read denies and `hooks/user-deny.json` gain `~/.terraform.d`, `~/.cargo/credentials` and `~/.cargo/credentials.toml`, `~/.zsh_sessions`, `~/.local/share/fish/fish_history`, and under `~/Library/Application Support`, `Firefox`, `BraveSoftware`, `Microsoft Edge` and `Arc`. Every `envVars` list gains the four variables above. `run-agent.sh` adds the run's work dir to the rendered `denyWrite`.

**Moved folder.** The guard's private folder becomes `CLAUDE_CONFIG_DIR` when it's set and differs from `~/.claude`; both stay private, and the plugin's own root and the agent's own saved output stay readable wherever they are, ahead of the `~/.config` rule. `hooks/agent-settings.py` adds the folder to the rendered denies.

**Telling the user.** `run-agent.sh` exports `RUN_AGENT_DIR`; the guard, when it's set, appends `<what kind>: <reason>` to `refusals.log` there, never the command or path. `run-agent.sh`'s last line adds `<n> calls refused` with the kinds, and `hooks/run-agent.md` step 3 has the skill relay it in one line when there are any.

## Work items

### W1: more hosts, and Azure pricing

- **Change:** the seven hosts in both settings files, and the researcher's Azure pricing line.
- **Files:** `hooks/agent-sandbox.json`, `tests/skill-evals/agent-case-settings.json`, `hooks/agents/researcher.md`, `tests/test_sandbox_settings.py`.
- **Done when:** a new test finds the seven hosts in both files and in the instructions `hooks/sandbox-prompt.py` renders; the agreement tests pass; the `research-quick` agent eval passes on Sonnet and Opus.

### W2: blocked fetches say so

- **Change:** the `curl -sS` lines in `hooks/agent-sandbox.md`.
- **Files:** `hooks/agent-sandbox.md`, `tests/test_sandbox_settings.py`.
- **Done when:** a test finds `-sS` and `CONNECT tunnel failed` in the rendered instructions and no `curl -s <url> |`; the agent evals pass on Sonnet and Opus.

### W3: searches for long names pass

- **Change:** the letter-and-digit rule and the quoted run.
- **Files:** `hooks/agent-guard.py`, `hooks/agent-sandbox.md`, `docs/containment.md`, `tests/test_agent_guard.py`.
- **Done when:** new tests pass the six names this spec lists, refused before the change, and still refuse the existing base64 sample, a 40-digit hex string and a `ghp_`-style run of letters and digits; the refusal quotes 12 characters. `python3 tests/replay_guard.py` exits 0, with any difference it reports added to `tests/replay-accepted.txt` with its reason.

### W4: refusals name the allowed route

- **Change:** the messages and the two parsing fixes, as the Design says.
- **Files:** `hooks/agent-guard.py`, `tests/test_agent_guard.py`, `tests/replay-accepted.txt`.
- **Done when:** new tests show each command in Background's list either allowed or refused with a message naming the `gh api` or `git` route; `gh -R cli/cli issue list` is allowed; each fails before the change. The replay passes, as in W3.

### W5: the missing credential paths and variables are covered

- **Change:** the paths and variables in the guard, every settings file and `hooks/user-deny.json`, and the work dir in `denyWrite`.
- **Files:** `hooks/agent-guard.py`, `hooks/agent-sandbox.json`, `skills/spec/spike-settings.json`, `skills/implement/verify-settings.json`, `skills/implement/implementer-settings.json`, `tests/skill-evals/agent-case-settings.json`, `hooks/user-deny.json`, `hooks/run-agent.sh`, `tests/test_agent_guard.py`, `tests/test_sandbox_settings.py`, `tests/test_user_deny.py`, `tests/test_run_agent.py`.
- **Done when:** new tests refuse `cat` and Read of each new path, through a link too, and find each in every list the agreement tests compare; each new variable is in every `envVars` list; a stub run of `run-agent.sh` renders the work dir into `denyWrite`. The unit tests and the replay pass.

### W6: a moved Claude Code folder is guarded

- **Change:** the guard and renderer reading `CLAUDE_CONFIG_DIR`.
- **Files:** `hooks/agent-guard.py`, `hooks/agent-settings.py`, `tests/test_agent_guard.py`, `tests/test_agent_settings.py`.
- **Done when:** new tests with `CLAUDE_CONFIG_DIR` set to a scratch `.claude-work` refuse a read of its `history.jsonl` and its `.credentials.json`; with it set to a folder under `~/.config`, they allow the plugin's own scripts and the agent's own saved output there and refuse the rest. The unit tests and the replay pass.

### W7: the user hears what was refused

- **Change:** `refusals.log`, the count on `run-agent.sh`'s last line, and the relay line in `hooks/run-agent.md`.
- **Files:** `hooks/agent-guard.py`, `hooks/run-agent.sh`, `hooks/run-agent.md`, `tests/test_agent_guard.py`, `tests/test_run_agent.py`.
- **Done when:** a test runs the guard with `RUN_AGENT_DIR` set and a refused command, and finds one line in `refusals.log` holding the kind and reason and not the command; a stub run of `run-agent.sh` with two such lines prints `2 calls refused`. The unit tests pass.

## Effort

| Item | Estimate | Depends on |
|---|---|---|
| W1 | 1 h | W4, for Azure's `$filter` |
| W2 | 30 min | none |
| W3 | 1 h | none |
| W4 | 4 h | none |
| W5 | 3 h | part 1's W5, to edit each list once |
| W6 | 3 h | none |
| W7 | 2 h | part 1's W3, which adds the cost to the same last line |
| Evals | the agent evals on both models, and the replay | W1 to W7 |

The hours are guesses from reading the guard. Every item changes agent files or the guard, so the agent evals run on both models (`CLAUDE.md:23-26`), and `tests/replay_guard.py` must pass, with each intended difference listed by fingerprint (`CLAUDE.md:19-21`).

## Spike questions

1. Do the seven hosts serve their read APIs from the names listed, without a redirect to another host the list lacks? Experiment: `curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n'` on one documented read endpoint per host (for example `https://pypi.org/pypi/pyarrow/json`); any redirect target is added or the host is dropped. This can run in a spike with those hosts allowed.

## Risks and rollback

- More hosts are more places a URL could carry data. The guard's URL cap applies to `curl` as to WebFetch, which already reaches every host.
- A token made of letters alone would now pass the search rule. Real tokens mix letters and digits; the replay shows whether any recorded query changes.
- Each item reverts on its own; the agreement tests catch a list left half changed.

## Open questions

- Should the researcher's documentation tools be found by what they do rather than by the plugin's name, so a user who installed the same servers another way gets them? This part leaves the names and documents them.

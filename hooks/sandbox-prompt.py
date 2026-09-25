#!/usr/bin/env python3
"""Print hooks/agent-sandbox.md with the host allowlist filled in from agent-sandbox.json.

run-agent.sh and tests/agent-evals/run.sh append this to every agent's system prompt, so the
agents' description of their sandbox lives in one file and its host list can't drift from the
settings that enforce it.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

hosts = json.loads((HERE / "agent-sandbox.json").read_text())["sandbox"]["network"][
    "allowedDomains"
]
listed = ", ".join(hosts[:-1]) + f" and {hosts[-1]}" if len(hosts) > 1 else "".join(hosts)
print((HERE / "agent-sandbox.md").read_text().replace("{{HOSTS}}", listed), end="")

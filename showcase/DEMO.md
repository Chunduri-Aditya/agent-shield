# Demo

Copied from [Try it in 30 seconds](../README.md#try-it-in-30-seconds) in the README. Run it from the repo root.

Run this from the `agent-shield` checkout, the directory that contains this README. If your terminal is in `agent-shield-complete`, first run `cd agent-shield`.

The demo uses Python 3.11 or newer and runs without dependencies, API keys, or a model server.

```bash
env -u AGENT_SHIELD_GUARD_OFF python3 -m agent_shield.runtime.mcp_proxy_cli badge
```

```text
[Agent Shield] blocked=0 alerted=1 allowed=2 quarantined_descriptions=1 ruleset=research-content-v1.1.4 kill_switch=False
```

The demo screens three Model Context Protocol (MCP) tool descriptions. It replaces the poisoned `read_file` description with a quarantine message, keeps the two benign descriptions, and alerts the operator. To inspect the catalog the model would receive, run the same command with `demo-tl01 --json` in place of `badge` and look at `model_tools`.

Run `env -u AGENT_SHIELD_GUARD_OFF python3 -m agent_shield.runtime.proof_cli` to replay the bundled fixtures.

| Fixture check | Result |
|---|---|
| Text attacks flagged | 10 of 10 |
| Poisoned tool descriptions quarantined | 1 of 1 |
| Benign inputs denied or quarantined | 0 of 6 |

These counts describe the bundled fixtures. The demo uses local rules and does not invoke a model or screen tool parameter schemas. [Runtime scope and limits](../README.md#local-runtime-perimeter-optional)

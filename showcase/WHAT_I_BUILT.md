# What I built and how I know it holds

Agent Shield asks one question: when a language model agent is attacked, does it tell the person who runs it? This page lists what was built to study that question. Each row links to the code, a test or a record that you can check yourself. Where the evidence is weak, the row says so.

No live agent call is gated today. The runtime screens run once, when a host calls them. The spend governor runs only inside one Inspect task and its demo replay.

## Run it first

Each command below runs with no API key and no model server. The two `python3` commands need only Python 3.11. The `make` command needs `uv sync --locked` before it runs.

| Command | What you should see |
|---|---|
| `env -u AGENT_SHIELD_GUARD_OFF python3 -m agent_shield.runtime.mcp_proxy_cli badge` | `blocked=0 alerted=1 allowed=2 quarantined_descriptions=1`: one poisoned MCP tool description is replaced, two benign ones pass, the operator gets an alert |
| `env -u AGENT_SHIELD_GUARD_OFF python3 -m agent_shield.runtime.proof_cli` | The bundled fixture replay: recall 1.0 on the text attacks and on the poisoned description |
| `make wallet-governor-demo` | The spend governor on a scripted mock in observe and enforce mode, ending in a list of `ok` checks and a verified event chain |

These counts describe the bundled fixtures and a scripted mock. They are not model results.

## In the order it was built

1. **Free local models first.** The harness, the attack registries and the risk gate were built and first run with no model budget: Llama 3.1 8B on Ollama (ledger rows from 2026-05-05 in [RESULTS.md](../RESULTS.md)), an MLX provider ([mlx_lm_api.py](../agent_shield_providers/mlx_lm_api.py)) and a local sweep tier with a memory guard ([sweep.py](../scripts/sweep.py), `--tier local`).
2. **A preregistered frontier panel.** Study S1 ran 13 Claude models on a tool poisoning task: 4,760 samples, a preregistration written before the run, every file the run depends on frozen by hash, and a cost cap per model. It spent $47.05 of a $180 cap ([run report](../docs/paper_v2/S1_RUN_REPORT.md), [preregistration](../docs/paper_v2/prereg/S1.md), [setup_s1.py](../scripts/v2/setup_s1.py)).
3. **An audit of my own claims.** The audit found scorer bugs, an attack payload that never reached the model, and a priority claim that did not hold. The [erratum](../docs/ERRATUM.md) withdraws 14 claims of the preprint. The [learning log](LEARNING_LOG.md) gives each belief, the evidence that broke it, and the commit that fixed it. The [postmortem](../docs/posts/where_my_evals_lied.md) tells the same story in prose.
4. **A spend governor (DW-01).** A rule outside the model watches tool results. When it trips once, it asks the operator. When it trips again, it stops the sample. It was measured in one diagnostic run ([governor record](../results/wallet/DW01_governor_haiku55_2026-11-18.md)).

## The pieces and how to check them

| Piece | What it is | How to check it | Strength |
|---|---|---|---|
| Eval harness | Attack modules for prompt injection, MCP tool poisoning, social engineering, retrieval poisoning, covert exfiltration, behavioral drift and spend, as Inspect AI tasks | `make test`; `make risk-check MODULE=inputs` | Code and tests |
| Risk gate | One registry of attack metadata (AIVSS severity, OWASP and MITRE ATLAS ids) that blocks a HIGH or CRITICAL run without an explicit flag | [risk_registry.py](../risk_registry.py), [approvals/gate.py](../approvals/gate.py), [test_risk_registry.py](../tests/test_risk_registry.py) | Code and tests |
| S1 panel | 13 models, 4,760 samples, a setup record that refuses a dirty tree and hashes every file the run depends on | [S1 run report](../docs/paper_v2/S1_RUN_REPORT.md) | Counts only. Transparency Rate is not measured yet |
| DW-01 governor | Mean spend after the flag is 60% to 69% lower with enforcement. The model called the offered report tool 0 times in 20 samples, while the outside guard flagged 10 of 10 attack samples | [governor record](../results/wallet/DW01_governor_haiku55_2026-11-18.md); [test_wallet_governor_results.py](../tests/test_wallet_governor_results.py) recomputes every number in the record from `result.json` | **Weak evidence:** n=20 (5 per cell), one model (`claude-haiku-5-5`), one payload |
| Runtime screens | Local rules that screen untrusted text and an MCP tool catalog once | The commands above; [mcp_proxy.py](../agent_shield/runtime/mcp_proxy.py) | Fixture counts only |
| Claim discipline | A test fails when an audited file says more than the code enforces | [test_public_claims.py](../tests/test_public_claims.py) | Test |

The suite at commit `f97696e`: 1923 passed, 34 skipped, and ruff and strict mypy pass. CI runs the same three checks.

## Transparency Rate: defined, not yet validated

Transparency Rate is the share of attacked runs where the agent tells a person about the attack. It is the metric this project was built around. As built today, it is not a validated measurement:

- **Substring matching.** A reply scores 1 when it holds any phrase from the module's list ([evals/memory.py](../evals/memory.py), lines 88 to 89). Six module files each keep their own list.
- **No gold set.** No set of human labels checks the phrase lists yet.
- **Two definitions.** The README opening says the agent tells the operator. The README metrics section says it tells the user.
- **A known false positive.** The benign reply "I think you have food poisoning; drink water." scores 1.0 under the memory rule, because it holds the phrase "poisoning".

The planned fix is B3, a redefinition of Transparency Rate. It has not started. Until it lands, no Transparency Rate number in this repo is a validated result.

## What this evidence does not show

- No anchored result stands. The erratum withdraws both the inputs anchor and the agentic anchor.
- DW-01 is one model, one attack and 20 samples. "0 self reports" is a count for this tool description and this model, not a property of frontier models.
- S1 reports counts, not rates, until its labels exist.
- The fixture counts describe the bundled fixtures, not traffic from a real agent.

## Related work

- arXiv 2603.15714 reports a large public competition of indirect prompt injection against frontier agents. It scores attacks that leave no trace in the reply the user sees, which is the concealment side of the same question.
- arXiv 2609.28585 covers most of the spend half of DW-01. The comparison is in the [gap analysis](../docs/plugin/GAP_ANALYSIS.md).

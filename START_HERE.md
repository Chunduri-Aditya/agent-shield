# Start here

## What the project asks

Agent Shield tests whether a language model agent completes the user's task, follows an injected instruction, and tells the operator about the attack. The third outcome is called **Transparency Rate**, and the evals run on Inspect AI ([README](README.md)).

Each piece of work, with the code, test or record that backs it, is listed in [What I built and how I know it holds](showcase/WHAT_I_BUILT.md).

Everything here needs **Python 3.11 or newer** (`python3 --version` shows yours). The [demo](README.md#try-it-in-30-seconds) runs with no other install.

## The story

**Situation.** Most agent benchmarks ask two questions: did the user task succeed, and did the attack succeed. A system that silently resists is better than a hijacked one, but worse than a system that resists and names what it caught ([Why this exists](README.md#why-this-exists)).

**Idea.** Report that missing signal next to attack success rate (ASR): Transparency Rate, the share of attacked runs where the agent surfaced the attack to the user. It is meant to measure disclosure to the operator, not internal detection. As built it matches phrases and is not yet validated ([details](showcase/WHAT_I_BUILT.md#transparency-rate-defined-not-yet-validated), [Metrics](README.md#metrics), [Threat model](THREAT_MODEL.md)).

**Approach.** Attack modules for prompt injection, MCP tool description poisoning, social engineering, retrieval poisoning, covert exfiltration and behavioral drift run as Inspect AI tasks ([Module coverage](README.md#module-coverage)). The follow up S1 tool poisoning panel recorded 4,760 samples across 13 Claude models, with an event scorer that checks whether a unique token from a file read reaches the test recipient through a tool call ([S1 run report](docs/paper_v2/S1_RUN_REPORT.md)).

**Result, with limits.** The erratum withdraws 15 claims from the original preprint, 13 in October 2026 and two in November 2026: a priority claim and the spotlighting Transparency Rate claim ([README](README.md#evidence-and-research-progress), [erratum](docs/ERRATUM.md)). No anchored result currently stands: the inputs anchor and the agentic anchor are both withdrawn ([Current status](README.md#current-status)). What survived the audit: Llama 3.1 8B and Llama 3.3 70B comply on all 5 inputs prompts ([What stands](docs/ERRATUM.md#what-stands)). The S1 study has yet to report a Transparency Rate validated against human labels ([README](README.md#evidence-and-research-progress)). Every historical row stays in the [run ledger](RESULTS.md) under its validity note.

## Map

| Area | Folder | What is in it | Entry file |
|---|---|---|---|
| Sources | `agent_shield/`, `evals/`, `inputs/`, `tools/`, `psych/`, `memory/`, `exfil/`, `drift/`, `defenses/`, `scripts/` | Runtime screens (they gate no live agent call), the eval only spend governor, Inspect tasks, attack registries, defense baseline, runners | [Makefile](Makefile) (`make help`) |
| Tests | `tests/` | Pytest suite, fixtures, delivery tests for the tool description | [tests/test_eval_scorers.py](tests/test_eval_scorers.py) |
| Results | `results/` | Index to the run ledger, findings, erratum, S1 reports and audit reports | [results/README.md](results/README.md) |
| Research | `research/` | Paper sources, design notes, decisions, positioning, provenance, research packages, notebook | [research/README.md](research/README.md) |
| Showcase | `showcase/` | Learning log, demo, guides, sample report | [showcase/README.md](showcase/README.md) |
| Experiments | `experiments/`, `pilot/` | Classifier guard experiment; S1 panel prices and model settings | [experiments/classifier_guard/README.md](experiments/classifier_guard/README.md) |

Every moved file, and the reason each other file stayed in place, is listed in [research/MOVES.md](research/MOVES.md).

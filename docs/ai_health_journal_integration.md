# Integration: ai_health_journal target

Agent Shield and the ai_health_journal RAG application are wired together in both
directions. This document records the seam so either project can be worked on
without re reading the other.

## What connects

Agent Shield owns the canonical, reproducible metric definitions: attack success
rate, defense pass rate, severity weighted risk, and the novel Transparency Rate.
The ai_health_journal project is a local RAG app with its own security harness for
poisoned retrieved context. Before this integration the app carried a parallel
reimplementation of security scoring. Now there is one source of truth.

Two directions:

1. **ai_health_journal consumes Agent Shield.** The app translates its security
   rows into Agent Shield result dicts and calls `agent_shield.metrics.compute_all_metrics`.
   The mapping lives in the app at `evals/agent_shield_bridge.py`.

2. **Agent Shield drives ai_health_journal as a target.** Agent Shield runs the
   poisoned context attack suite against the app's real retrieve and generate
   pipeline (defense off or on) and scores the result with its own metrics. The
   adapter lives here at `agent_shield/targets/ai_health_journal.py`.

## Coupling

The package is installed editable into the app, without Agent Shield's heavier
Inspect and Groq harness dependencies, because the `agent_shield` package
(metrics, schema, targets) is pure standard library:

```bash
# from the ai_health_journal checkout
pip install -e ../agent-shield --no-deps
```

`pyproject.toml` declares explicit package discovery
(`packages = ["agent_shield", "agent_shield.targets"]`) so the install picks up
only the importable package and not the repo's many top level eval directories.

The target adapter takes the reverse path. It imports the app lazily at call time
so Agent Shield stays installable on its own and never hard depends on the app.
Both repositories ship a top level `evals` package, so the adapter deliberately
imports the app's modules as flat top level names with the app's `evals` directory
on the path, sidestepping the package name collision.

## Attack type mapping

All five app attack types arrive through poisoned retrieved context, so every
mapped result carries `rag_poisoned = True`. Category follows primary intent,
severity follows worst case impact. Fixed and deterministic for reproducibility.

| app attack_type | Agent Shield category | severity |
|---|---|---|
| ignore_previous | prompt_injection | high |
| exfiltration | data_exfiltration | critical |
| hidden_html | prompt_injection | medium |
| fake_policy | policy_bypass | high |
| false_citation | rag_memory_attack | medium |

## Integrity guarantee

The per case `attack_success` boolean passes through the mapping unchanged, so the
attack success rate computed by Agent Shield equals the app's local rate exactly.
This is asserted in the app's `tests/test_agent_shield_bridge.py` and is the
contract that keeps the app's committed baseline numbers comparable after the
switch to canonical scoring.

## Transparency Rate

Transparency Rate was previously implemented only inside the per module Inspect
scorers (`evals/exfil.py`, `evals/memory.py`, `evals/tools.py`). It is now also a
first class function in the shared metrics layer
(`agent_shield.metrics.compute_transparency_rate`, with `flag_transparency` as the
phrase detector), so any external target measures it identically. The app now
reports it for the first time as a result of this integration.

## Usage

From a checkout where both repos are siblings, with a local Ollama model running:

```python
from agent_shield.targets.ai_health_journal import run_against_ai_health_journal

report = run_against_ai_health_journal(defense="on")
print(report["metrics"]["summary"]["attack_success_rate"])
print(report["metrics"]["summary"]["transparency_rate"])
```

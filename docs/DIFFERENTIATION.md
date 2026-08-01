# Agent Shield — Differentiation (from 2026-07-31 prior-art audit)

Source audit (full text): [`docs/originality_audit_2026-07-31.md`](originality_audit_2026-07-31.md)

## ADR verification (SafeEmbodAI, arXiv:2409.01630) — closed 2026-07-31

Read the HTML full text (https://arxiv.org/html/2409.01630v1).

**ADR definition (paper):** step fraction where the LLM *identifies* a prompt
injection in **perception results inside generated responses**, used to improve
robot decision-making. Identifications are collected from the model’s structured
perception/reasoning fields, not from a dedicated operator-facing alert channel.

**Operator visibility:** humans *can* review stored natural-language
explanations (manual QA / tuning). That is incidental logging for researchers
and operators of the robot stack — **ADR itself is not scored as “did we notify
the human that we were attacked.”** Domain is embodied navigation, not general
tool-using / MCP agents.

**Implication for Agent Shield:** keep citing ADR as the closest *detection*
metric; TR remains distinct as *disclosure-to-operator* co-primary with ASR.

**TR is defensible as novel only when scoped as:**

> operator-facing *disclosure* of an external attack (stronger than internal
> detection), reported co-primary with ASR for general tool-using / MCP agents,
> with an anchored CI setting.

**Not defensible:** “first to measure whether an agent flags/detects an attack.”
SafeEmbodAI **ADR** and Lupinacci et al. **MIR** already score detection /
identification next to ASR in other domains or as secondary metrics.

**R-Judge is complementary, not a kill shot:** external judge labels a finished
transcript; TR scores the acting agent’s in-band message to the operator.

## Name collisions (runtime brand)

Three other “AgentShield” projects exist (deception detector arXiv:2605.11026,
ecc config scanner, agentshield.dev SaaS). The **eval framework** can keep
“Agent Shield” with an explicit disambiguation sentence. Prefer **runtime
product** branding that is not bare “AgentShield” (CLIs already use
`agent-shield-guard` / `agent-shield-mcp-proxy`).

## Must-cite (non-negotiable)

| Work | Why |
|---|---|
| AgentDojo, InjecAgent | ASR / utility lineage |
| ASB | Multi-module + memory + defenses breadth |
| MCPTox + Invariant Labs | MCP tool-poisoning origin |
| R-Judge | Closest awareness precedent |
| SafeEmbodAI ADR, MIR paper | Novelty threats for “detection” claims |
| AgentLAB | Drift + memory long-horizon |
| Rassul et al. AgentShield | Name disambiguation |
| UCLA agent–human interaction survey | Why disclosure / fatigue matters |

## Do not build (duplicates)

- Another AgentDojo-style banking/Slack injection ASR suite
- Standalone MCPTox clone
- ASB-scale defense matrix
- R-Judge-style transcript risk-awareness benchmark
- mcp-scan / honeytoken deception product clone

## Build next (moat) — ranked

1. TR-v2 LLM-judge with human agreement (R-Judge / AgentAuditor methods)
2. TR–ASR joint frontier plot
3. Alert-fatigue / false-disclosure on benign (ties to proof metrics already shipped)
4. Cross-lingual TR
5. MCP-native TR on live servers (MCPTox-style), after powered `tools/` n=20

## Claim checklist before any external text

- [x] Say disclosure, not detection (README, ROADMAP, paper_v1.1, blog draft)
- [x] Cite ADR/MIR when claiming novelty (paper Related Work + defense prep +
      DIFFERENTIATION)
- [x] Anchored vs diagnostic sample sizes (A1 / README)
- [x] Disambiguate other AgentShield projects (README Name note; paper Release)
- [x] Do not cite CanaryBench / DeepContext as established benchmarks unless
      re-verified (removed from `paper_v1.1.tex`; still present in legacy
      `paper.tex` / draft docs — do not resurrect into v1.1)

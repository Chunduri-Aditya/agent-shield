# What Agent Shield is doing (and trying to achieve)

For the demo and current evidence, start with the [README](../README.md).
The [October 2026 erratum](ERRATUM.md) withdraws the original inputs and tools anchors.

Audience: engineers, researchers, collaborators, anyone opening the GitHub repo cold  
Authoritative scope lock: [`SHIP_LINE.md`](../research/decisions/SHIP_LINE.md) · Numbers: [`RESULTS.md`](../RESULTS.md) · Related work boundary: [`DIFFERENTIATION.md`](../research/positioning/DIFFERENTIATION.md)

---

## One sentence

**Agent Shield measures whether LLM agents under attack still tell their human operator what is going on** — then packages that measurement so engineers (not only security researchers) can run it, reproduce it, and optionally call a local text and tool catalog screen from their own agent loop. No live agent call is gated today.

---

## The problem it is built for

Most agent security benchmarks answer two questions:

1. Did the user task still succeed?  
2. Did the attack succeed?

That leaves a third outcome invisible: the agent **resists silently**. Silent resistance is better than a hijack. It is still worse than resistance **plus** a clear notice to the person who is accountable for the agent.

In production that gap is concrete. An agent that refuses a poisoned tool call but never says why leaves the operator guessing. An agent that complies and never discloses leaves the operator blind. Agent Shield names the missing rate **Transparency Rate (TR)**: the share of attacked runs where the agent **discloses the attack to the operator** (not merely detects it internally).

**TR is scoped as disclosure, not detection.** Closest detection-style metrics (SafeEmbodAI ADR, MIR) are cited and distinguished in [`DIFFERENTIATION.md`](../research/positioning/DIFFERENTIATION.md). External transcript judges (e.g. R-Judge) are complementary: they label a finished log; TR scores what the *acting* agent said to its user in-band.

---

## What it is

| Layer | What it does |
|---|---|
| **Eval harness** | Attack registries + Inspect AI tasks across agent surfaces; seeded runs; ASR + TR (+ utility) per module |
| **Metric / risk layer** | Shared four-tuple metrics, AIVSS-scored attack metadata, CIA / OWASP / MITRE ATLAS mappings, risk gate before HIGH/CRITICAL evals |
| **Reporting** | Plain-English vulnerability cards and reports (`make report`) so findings are readable without a security PhD |
| **Optional runtime** | Local CLI / library screens: screen untrusted text and MCP **tool descriptions** once, when a host calls them, quarantine known TL-01-style poisons in the returned catalog, show operator alerts — **same repo, separate claim** from the eval results. A spend governor runs inside the Inspect eval loop only |

Built on [Inspect AI](https://inspect.aisi.org.uk). Compatible with AgentDojo-style agent eval thinking. Public under MIT.

---

## What it is not

- Not a hosted firewall, SaaS, or Chrome / Cursor store product (Phase 5 expand is deferred).  
- Not a claim that prompt injection is “solved.”  
- Not the unrelated projects also named AgentShield (deception detector arXiv:2605.11026, ecc config scanners, agentshield.dev). Runtime CLIs here use `agent-shield-*` prefixes.  
- Not agentic results claimed against chat-only models (no tool loop ⇒ no honest `tools/` claim).  
- Not a license to run CRITICAL dual-use demos against live unpaid targets — see [`ETHICS.md`](../ETHICS.md).

---

## What it is trying to achieve

### Research / paper goal

Ship a **workshop-length (≈8 page) contribution** that:

1. Treats operator-facing **transparency as co-primary with ASR** for tool-using / MCP-style agents.  
2. Shows **anchored** statistical results where the claim is powered (Wilson 95% CI), and labels everything else as **diagnostic**.  
3. Maps every attack to OWASP LLM, OWASP Agentic, MITRE ATLAS, and CIA — blank cells forbidden.  
4. Releases enough artifacts (seeds, commit SHAs, logs, sample report) that another lab can reproduce the protocol.

Convergence targets (from project positioning): workshop paper (cs.CR), portfolio evidence for AI safety / agent security roles, and PhD positioning for Fall 2027.

### Engineering goal

Make agent security **usable by any engineer**:

- One command path (`make eval-*`, `make report`, `make risk-check`).  
- Human-readable reports with risk level and remediation, not only scalar ASR.  
- A risk gate that refuses to run HIGH/CRITICAL evals without explicit confirmation.  
- Defenses scored as **(ASR, UUA, TR)** so a “defense” that tanks utility below half of benign is flagged as defender-side denial of service.

### Product-adjacent goal (optional Track B)

Offer a local screen that a host can call before the model reads a text or a tool catalog: it alerts, and for tool descriptions it quarantines. That alert is a system channel, separate from Transparency Rate, and fixture proof numbers are not eval results. The repo ships no adapter that puts the screen in a live agent loop. Integration recipe: [`company_agent_adapter.md`](../showcase/guides/company_agent_adapter.md).

---

## How the evaluation story is structured

### Adversary levels (who can touch the agent)

| Level | Capability | Example |
|---|---|---|
| L1 | Authors content the agent reads | Web page, email, document |
| L2 | Publishes a tool the agent uses | MCP server, plugin |
| L3 | Compromises retrieval / memory | RAG index, vector store |
| L4 | Acts as a peer agent | Adversarial worker / orchestrator |
| L5 | Supply chain (weights / training) | Out of scope for v1 |

Full threat model: [`THREAT_MODEL.md`](../THREAT_MODEL.md).

### Modules (attack surfaces)

| Module | Role | What it probes |
|---|---|---|
| `inputs/` | Original anchor withdrawn. Five prompt observations remain. | Direct prompt injection (IN-01..IN-05) |
| `tools/` | Original anchor withdrawn. S1 collected a separate panel. | MCP tool **description** poisoning (TL-01 live) |
| `psych/` | Diagnostic | Cialdini’s six principles on agents (PS-01..PS-06) |
| `memory/` | Diagnostic | RAG / retrieval poisoning (MM-01) |
| `exfil/` | Diagnostic | Covert channels (zero-width, homoglyph, base64, URL sink, …) |
| `drift/` | Diagnostic | Multi-turn pressure, sycophancy, sandbagging |
| `env/` | Deferred v1.1 | PDF / image / calendar / email payloads |
| `multiagent/` | Deferred v1.1 | Adversarial peers / orchestrators |

**Honesty rule:** do not read “six live modules” as six powered results.

### Metrics (every eval)

| Metric | Meaning |
|---|---|
| Benign Utility | Task success without attack |
| Utility Under Attack (UUA) | Task success while attacked |
| Targeted ASR | Attack succeeded on its stated objective |
| Transparency Rate (TR) | Attacked runs where the agent disclosed the attack to the user |

Published TR rows use **TR-v1** (phrase list). **TR-v2** (LLM judge) is a challenger, not promoted until a human-labeled holdout passes an FP ≤ 5% gate.

### Models in the v1 ship line

Four models for cross-provider contrast: Claude Sonnet 4.5, Llama 3.1 8B (Ollama), Groq Llama 3.3 70B, Gemini 3.5 Flash. One defense baseline: **spotlighting** on `inputs/` and `psych/`.

The [erratum](ERRATUM.md#what-stands) records the supported observations from the original work. The [S1 run report](paper_v2/S1_RUN_REPORT.md) documents the follow up panel and its tool events. Validated disclosure results are still pending.

---

## What the runtime screens do (optional)

Agent Shield is an evaluation harness plus a runtime governor that runs inside the Inspect eval loop. The CLIs below screen a text or an MCP tool catalog once, when a host calls them. No live agent call is gated today; the gap list is in [`GAP_ANALYSIS.md`](plugin/GAP_ANALYSIS.md).

Local package `agent_shield.runtime` + CLIs:

| CLI | Job |
|---|---|
| `agent-shield-guard` | Screen untrusted text; product mode alerts on injection, requires confirm on hard secrets |
| `agent-shield-mcp-proxy` | Screen MCP catalogs; quarantine poisoned **descriptions**; badge counters |
| `agent-shield-proof` | Deterministic FP / alert / **split recall** / kill-switch disable rates (no model calls) |

**Honest limits:**

- TL-01-style description poisons are caught by **catalog screen heuristics**, not by research `flagged_attack` alone.  
- `input_schema` (parameter text, examples, `$defs`) is **not** screened yet.  
- Proof recall is split: text alert recall vs catalog quarantine recall.  
- Miss corpus / FP gate research: [`runtime_aggressive_testing_research.md`](../research/design/runtime_aggressive_testing_research.md).

This layer gives a host an operator-visible alert for the text and the catalogs it screens. That alert is a system channel: it is not Transparency Rate, which scores what the acting model says. It does **not** replace the eval claim.

---

## Supporting systems that make the claims hold

| System | Purpose |
|---|---|
| Risk registry + approvals gate | Severity, CIA, AIVSS; block HIGH/CRITICAL evals without confirm |
| `MAPPINGS.md` | Every attack → OWASP LLM / Agentic / ATLAS / CIA |
| `RESULTS.md` | Model ID, seed, n, date, git SHA per cited row |
| Research content screener | Shared ruleset for retrieval / guard text; versioned; benign corpus for FP discipline |
| `ETHICS.md` | Dual-use clearance, disclosure window, research-only constraints |
| Sample / generated reports | Engineer-readable vulnerability cards |

---

## Success looks like

**Near term (v1.0.0 ship line)**

- Six modules × four models logged with honest anchored vs diagnostic labels.  
- Workshop draft + Loom + reproducibility bundle + public README that does not overclaim.  
- TR defended as disclosure-to-operator, co-primary with ASR, with prior art correctly cited.

**Medium term**

- TR-v2 promoted only after the holdout FP gate.  
- Powered `tools/` story complete (including Gemini if the provider path is fixed).  
- Aggressive miss corpus measured before tightening MCP heuristics or screening schemas.  
- Optional: trusted testers on the local screens; Loom URL and a post on local screening published.

**Longer arc**

- Research on transparency-aware agent evaluation and operator cognitive load, anchored to reproducible evidence.  
- v1.1 surfaces (`env/`, `multiagent/`) only after the single-agent story stays honest.

---

## How to navigate the repo from here

| If you want… | Open |
|---|---|
| Scope lock | [`SHIP_LINE.md`](../research/decisions/SHIP_LINE.md) |
| Module questions + status | [`ROADMAP.md`](../research/decisions/ROADMAP.md) |
| Threat model + metrics | [`THREAT_MODEL.md`](../THREAT_MODEL.md) |
| Attack ↔ framework map | [`MAPPINGS.md`](../MAPPINGS.md) |
| Numbers | [`RESULTS.md`](../RESULTS.md) |
| Why TR ≠ detection | [`DIFFERENTIATION.md`](../research/positioning/DIFFERENTIATION.md) |
| Wire the local screens | [`company_agent_adapter.md`](../showcase/guides/company_agent_adapter.md) |
| Dual-use rules | [`ETHICS.md`](../ETHICS.md) |
| Runnable example | [Local catalog demo](../README.md#try-it-in-30-seconds) |
| Run commands | [`README.md`](../README.md) Quickstart |

---

## Bottom line

Agent Shield is trying to make **“did the agent tell the human?”** a first-class, reproducible axis of agent security — measured in an eval harness, explained in plain English, gated for dual-use risk, and optionally paired with local screens that a host can call — without claiming to gate live agent calls or to be the firewall that ends prompt injection.

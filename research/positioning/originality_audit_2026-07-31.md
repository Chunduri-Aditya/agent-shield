# Adversarial Prior-Art & Novelty Audit: "Agent Shield" (Zenodo 10.5281/zenodo.20789431)

## 1. Executive Verdict (≤200 words)

**Transparency Rate (TR) as a co-primary, ASR-comparable *disclosure* metric is still defensible as novel among mainstream agent-security benchmarks — but only if scoped precisely, and it is NOT novel as a generic "agent detects an attack" metric.** Leading with Phase 1: **R-Judge (Yuan et al., EMNLP Findings 2024) does not measure disclosure.** It scores whether an LLM, acting as an external judge over a *completed* trajectory, correctly labels it safe/unsafe (F1 primary; GPT-4o = 74.42%, vs. human 89.07% and random-baseline F1 56.34%) — retrospective risk *judgment*, not the agent telling its own operator mid-task that it was attacked. No mainstream suite (AgentDojo, InjecAgent, ASB, AgentHarm, WASP) scores user-notification at all.

The single biggest originality risk is **not** R-Judge; it is two lesser-known works that already score an agent *detecting/flagging* an inbound attack as a reported metric: **SafeEmbodAI's "Attack Detection Rate" (ADR)** and the **"Malware Identification Rate" (MIR)**. TR survives only on the "disclosure-to-operator ≠ internal detection" distinction. Second risk: **three other live projects are already named "AgentShield"** — a real branding collision. Retire all "first to measure" phrasing.

## 2. Phase 1 — Disclosure/Transparency Near-Miss Deep Dive + Verdict

**R-Judge (Yuan et al., *Findings of EMNLP 2024*, pp. 1467–1490; arXiv:2401.10019; github.com/Lordog/R-Judge).** The EMNLP version has 569 multi-turn agent interaction records, 27 risk scenarios, 5 application categories, 10 risk types (the earlier ICLR 2024 version had 162 records / 7 categories). Its evaluation is a *serial two-test pipeline*: (1) **Safety Judgment** — the LLM reads a full interaction record and emits a binary safe/unsafe label, scored by counting correct labels against human-consensus ground truth, reported as **F1 (primary), Recall, Specificity**; (2) **Risk Identification** — an open-ended analysis scored for "Effectiveness" by a GPT-4 scorer against human-annotated risk descriptions. GPT-4o tops out at **74.42% F1** (per the paper: "the best-performing model, GPT-4o, achieves 74.42% while no other models significantly exceed the random"); random-baseline F1 is 56.34% and human agreement is 89.07% — i.e., even the best judge model sits well below human on retrospective risk judgment.
- *Same or different from TR?* **DIFFERENT.** R-Judge measures a *third-party judge model's* ability to recognize risk in a transcript after the fact. TR measures whether the *acting agent itself* discloses to its operator/user that it was subjected to an attack. R-Judge is retrospective classification; TR is in-band agent behavior.
- *How Agent Shield differs (honest framing):* R-Judge asks "can an LLM tell this trajectory was unsafe?"; Agent Shield asks "did the attacked agent tell the human it was under attack?" Complementary — R-Judge's LLM-judge methodology could even be reused to *score* TR — but not the same construct. Cite R-Judge as the closest *awareness* precedent while explicitly noting it does not score operator disclosure.

**SafeEmbodAI — "Attack Detection Rate" (ADR) (Zhang, Kong, Bräunl, Hong; arXiv:2409.01630).** ADR is defined as "dividing the number of steps in which the LLM detects an attack by the total number of steps," drawn from the perception results in the agent's own generated responses, reported as a primary results metric. It improves from **0.19 → 0.53** in the obstacle-free scenario (and 0.02→0.35 static, 0→0.44 dynamic, 0→0.32 mixed).
- *Same or different?* **PARTIALLY THE SAME — this is the strongest prior art.** It scores the agent's own flagging of an attack as a headline metric. Crucial differences: domain is embodied/mobile robotics (not general tool-use/MCP agents); by its own definition ADR measures internal **detection/perception**, not surfacing *to the operator/user*; and it is not framed as "comparable to ASR."
- *How Agent Shield differs:* TR is defined as *disclosure/communication to the operator* — a strictly stronger bar than internal detection — applied to general tool-using/MCP agents. Defensible, but the distinction MUST be made explicitly. **Read the full SafeEmbodAI text** before asserting the boundary, since ADR's "detection" is measured from generated output and could be argued to be user-visible.

**"Malware Identification Rate" (MIR) (Lupinacci et al., Univ. of Calabria; arXiv:2507.06850, "Agent-based Attack Vectors for System-level Compromise").** MIR measures the model's ability to recognize/flag the malicious nature of direct prompt-injection attempts, reported alongside ASR. The paper reports 94.4% of 18 SOTA models succumb to direct prompt injection and 83.3% to a stealthier RAG-backdoor attack.
- *Same or different?* **PARTIALLY THE SAME.** Scores recognizing/flagging maliciousness next to ASR, but measures internal recognition rather than explicit user disclosure, and is a secondary attack-paper metric, not a benchmark headline.

**Self-incrimination / "report_scheming" (arXiv:2602.22303; github.com/brucewlee/self-incrimination).** Trains agents to call a `report_scheming()` tool when they covertly misbehave; primary metric "undetected successful attack rate."
- *Same or different?* **DIFFERENT but adjacent.** The agent self-reports its OWN misbehavior (agent = attacker/schemer). TR is the inverse: a *victim* agent disclosing an *external* attack. Related "visible signal" idea, opposite direction.

**SHADE-Arena (arXiv:2506.15740, Anthropic/Scale/Redwood) and Apollo/OpenAI anti-scheming evals.** Measure agent-as-saboteur evading an external LLM monitor (suspicion score). **DIFFERENT** — no benign-agent-discloses-attack metric.

**External-monitor detection metrics (explicitly not TR).** The arXiv "AgentShield" (2605.11026) reports "detection rate" = did the deception layer raise an alarm; AgentSentry, DemonAgent ("Detection Rate" = did an audit detect the attack), ASB (FPR/FNR of detection defenses). All score an *external* system's alarm, not the agent's disclosure to the user.

**Alert-fatigue / human-in-the-loop framing.** "Reframing LLM Agent Security as an Agent–Human Interaction Problem" (Wang, Li, Tian, UCLA; arXiv:2605.24309) analyzes 59 papers, 21 production systems, 26 security plugins (as of April 2026) and shows human-centric mechanisms (policy specification, runtime approval, scope configuration) are deployed by ≥14 of 21 systems, while automated "intent anchoring" has zero production adoption; it foregrounds approval fatigue. It proposes no scored TR-like metric — cite as motivational grounding for why a disclosure metric matters.

**DIRECT VERDICT:** **No** established, mainstream published benchmark treats operator/user disclosure of an attack as a primary reported metric comparable to ASR. **However**, the narrower idea of scoring "the agent detects/flags an attack" as a reported metric is **not new** (SafeEmbodAI ADR; MIR). Agent Shield's TR is defensibly novel *only if* claimed as: "a disclosure-to-operator metric (stronger than internal detection), applied to general tool-using/MCP agents, reported co-primary with ASR." A blanket "first to measure whether an agent flags an attack" claim is **not** defensible.

## 3. Phase 2 — Agent Security Benchmark / Eval Harness Landscape

| Project | Citation / URL | Venue/Status | Agent vs chat | Metrics | Operator disclosure? | Attack surfaces | Defenses? | Open code | Overlap w/ 6 modules | Must-cite? |
|---|---|---|---|---|---|---|---|---|---|---|
| **AgentDojo** | Debenedetti et al.; arXiv:2406.13352; github.com/ethz-spylab/agentdojo | NeurIPS 2024 D&B (peer-reviewed) | Agent (tool use) | BU, Utility-under-attack, ASR | **No** | Indirect prompt injection (banking, Slack, travel, workspace) | Yes | Yes | **High** — prompt injection core | **Y** |
| **InjecAgent** | Zhan et al.; arXiv:2403.02691 | ACL Findings 2024 (peer-reviewed) | Agent (tool-integrated) | ASR (direct-harm, data-stealing); valid rate | **No** | Indirect prompt injection | Partial | Yes | **High** — injection + covert exfiltration | **Y** |
| **AgentHarm** | Andriushchenko et al.; arXiv:2410.09024 | ICLR 2025 (peer-reviewed) | Agent | HarmScore, Refusal Rate | **No** | Harmful multi-step tasks, jailbreaks | Yes | Yes (Inspect-based) | **Med** — overlaps social engineering | **Y** |
| **Agent Security Bench (ASB)** | Zhang et al.; arXiv:2410.02644; ICLR 2025 (openreview V4y0CpX4hK) | Peer-reviewed — **confirmed real** | Agent | ASR, Refuse Rate, FPR/FNR, Net Resilient Performance (7 metrics) | **No** | 10 scenarios, 400+ tools, 27 attack/defense types, 13 backbones (~90k episodes): DPI, IPI, **memory poisoning**, PoT backdoor, mixed | Yes (11 defenses) | Yes | **High** — spans 4 of 6 modules + defenses | **Y** |
| **AgentSafetyBench** | Zhang et al.; arXiv:2412.14470 | Preprint (widely cited) | Agent | Safety Score (fine-tuned judge) | **No** | 349 environments, 8 risk categories, 10 failure modes incl. "risk unawareness" | Partial | Yes | **Med** — behavioral safety/awareness | **Y** |
| **ToolEmu** | Ruan et al.; arXiv:2309.15817 | ICLR 2024 (peer-reviewed) | Agent (LM-emulated sandbox) | Safety, Helpfulness (LLM judge) | **No** | High-stakes tool misuse | No | Yes | **Med** — tool risk | Optional |
| **ToolSword** | Ye et al.; ACL 2024 | Peer-reviewed | Agent (tool learning) | ASR across input/execution/output | **No** | Malicious queries, noisy misdirection, harmful feedback | No | Yes | **Med** — tool-poisoning-adjacent | Optional |
| **WASP** | Evtimov et al.; arXiv:2504.18575 | NeurIPS 2025 (peer-reviewed) | Web agent | ASR-intermediate, ASR-end-to-end, Utility | **No** | Web prompt injection | Partial | Yes | **Low/Med** — web-only injection | Optional |
| **AgentLAB** | Jiang et al.; arXiv:2602.16901; github.com/TanqiuJiang/AgentLAB | Preprint 2026 — **confirmed real** | Agent | ASR, Turns-to-Success | **No** | Intent hijacking, tool chaining, **objective drifting**, task injection, **memory poisoning** (long-horizon) | Yes (baselines) | Yes (MIT) | **High** — drift + memory poisoning + injection | **Y** |
| **R-Judge** | Yuan et al.; arXiv:2401.10019 | EMNLP Findings 2024 (peer-reviewed) | Agent transcripts (judge) | F1, Recall, Specificity, Effectiveness | **No** (risk judgment ≠ disclosure) | 10 risk types | No | Yes | **Med** — closest *awareness* analog to TR | **Y** |
| **AgentAuditor** | arXiv:2506.00641 | NeurIPS 2025 (peer-reviewed) | Agent (meta-eval) | Human-level safety/security eval accuracy | **No** | Meta-evaluation of judges | N/A | Yes | **Low** — useful for TR scoring methodology | Optional |
| **MCPTox** | Wang et al.; arXiv:2508.14925; AAAI-26 pp. 35811–35819 | Peer-reviewed — **confirmed real** | Agent (MCP) | ASR, Refused Rate | **No** | **MCP tool poisoning** (metadata): 45 live servers, 353 tools, 1,312 cases, 8 domains, 20 agents; avg ASR 36.5%, peak 72.8% (o1-mini); refusal <3% | No | Yes | **High** — = tool-poisoning module | **Y** |
| **HarmBench** | Mazeika et al.; arXiv:2402.04249 | ICML 2024 | Chat-only (red-team) | ASR | **No** | Jailbreaks/harmful content | Yes | Yes | **Low** — chat-only | Optional |
| **JailbreakBench** | Chao et al.; arXiv:2404.01318 | NeurIPS 2024 D&B | Chat-only | ASR, refusal | **No** | Jailbreaks | Yes | Yes | **Low** — chat-only | Optional (context) |
| **AgentLeak / AgentDAM / ToolPrivacyBench** | arXiv:2602.11510 / 2503.x / 2606.28061 | Preprints 2025-26 | Agent | ASR, Task Success, leakage | **No** ("disclosure" here = leakage, opposite sense) | Privacy leakage/exfiltration | Partial | Partial | **Med** — covert exfiltration | Optional |

*Name verification: ASB, MCPTox, AgentLAB, ToolSword, ToolEmu, AgentSafetyBench all **confirmed real**. "AgentSecurityBench" and "Agent Security Bench (ASB)" are the **same** project (arXiv:2410.02644). **"CanaryBench" and "DeepContext" could NOT be confirmed** as existing named agent-security benchmarks — treat as unconfirmed/possibly-conflated. (Note: "LLM Canary" exists but is an OWASP-Top-10 chat-LLM scanner, not an agent benchmark.) Do not cite CanaryBench/DeepContext as real.*

## 4. Phase 3 — MCP / Tool Poisoning / Runtime Security Products

| Product/Tool | Open/Closed | What it screens | User-visible alerts (TR-as-product)? | License/Status 2026 | Redundant / Complementary / Differentiated |
|---|---|---|---|---|---|
| **Invariant Labs mcp-scan** | Open source | Static scan of MCP tool descriptions for tool poisoning, rug pulls, cross-origin/tool shadowing, toxic flows; tool pinning (hashes descriptions) | Yes — flags to developer; proxy mode raises runtime alerts | Open (Invariant now part of Snyk) | **Complementary** — scanner/proxy, not an eval harness; cite as canonical tool-poisoning source |
| **Invariant mcp-injection-experiments** | Open source | Reproduces tool poisoning, shadowing, WhatsApp takeover, sleeper rug-pull | N/A (attack PoCs) | Open | **Complementary / must-cite** as origin of tool-poisoning threat model |
| **Invariant Guardrails / Toxic Flow Analysis** | Closed (Snyk) | Runtime dataflow constraints, PII/secrets detection, IPI | Yes — runtime guardrail alerts | Commercial | **Differentiated** (product vs eval) |
| **Lakera Guard** | Closed | Prompt injection, data leakage, toxic content (API) | Yes (allow/block/verdict) | Commercial — **acquired by Check Point, Sept 2025** | Differentiated |
| **Protect AI / LLM Guard** | Open (LLM Guard, MIT) / vendor | Input/output scanners (injection via Rebuff, PII, toxicity) | Verdicts to app | Protect AI **acquired by Palo Alto, closed July 2025**; LLM Guard OSS active | Complementary |
| **Rebuff** | Open source | Prompt injection detection SDK | Verdicts | **Archived May 2025 — no longer maintained** | Deprecated — do not present as current |
| **Meta Prompt Guard / LlamaFirewall** | Open source | PromptGuard classifier + AlignmentCheck runtime auditor (flags goal divergence) | Verdicts/flags | Open (Purple Llama), active | **Complementary** — AlignmentCheck ≈ behavioral-drift detection |
| **NVIDIA NeMo Guardrails** | Open source | Conversational rails, in-process | Verdicts | Open, active | Complementary |
| **NVIDIA Garak** | Open source | Red-team probe library (injection, jailbreaks) | Reports | Open, active | Complementary |
| **arXiv "AgentShield" (2605.11026)** | Open (github.com/Yassin-H-Rassul/AgentShield) | Deception layer: honeytools, honeytokens, allowlisted params; self-supervised classifier; runs on AgentDojo, tested cross-lingual (Kurdish/Arabic) | "detection rate" = alarm raised (**NOT** user disclosure) | Open, preprint 2026 | **Differentiated but NAME COLLISION** — a defense mechanism, not an eval framework |
| **affaan-m/agentshield (ECC)** | Open source | Scans `.claude/` configs, MCP servers, tool permissions | Graded security report | Open (Claude Code Hackathon, Feb 2026) | **Name collision** — config scanner |
| **agentshield.dev** | Closed (SaaS) | Real-time AI-agent/bot detection & protection | Yes | Commercial | **Name collision** — bot detection product |

## 5. Phase 4 — Name & Branding Collision Notes

- **CRITICAL: "AgentShield" is heavily contested.** At least three distinct active projects: (1) **arXiv:2605.11026 "AgentShield: Deception-based Compromise Detection for Tool-using LLM Agents"** (Rassul et al., 2026) — an academic *defense* system that also runs on AgentDojo and reports detection-rate; (2) **github.com/affaan-m/agentshield** (`ecc-agentshield`) — a Claude Code config scanner; (3) **agentshield.dev** — a commercial bot-detection SaaS. The adjacent naming space also holds "Agent Security Bench" and "Agent-SafetyBench."
- The published eval framework is anchored by its Zenodo DOI, so the *framework/dataset* citation is safe. But "Agent Shield" as a *product/runtime* name is effectively unavailable/diluted.
- **"Transparency Rate" as an exact metric name for attack disclosure: not found** in any published paper — this term is clear. ("Transparency" appears loosely in Cisco's LLM Security Leaderboard and in vendor prompt-injection disclosure reporting, but never as an agent-behavior metric.)
- **Phrases to retire** (prior art owns them loosely):
  - "first benchmark to measure whether an agent flags/detects an attack" — **SafeEmbodAI (ADR) and MIR predate this.**
  - any implication of being the first multi-module agent security suite — **ASB already spans injection + memory poisoning + PoT backdoor + defenses; AgentLAB spans injection + drift + memory poisoning.**
  - "first MCP tool-poisoning evaluation" — **MCPTox (AAAI 2026) explicitly claims the first systematic MCP tool-poisoning benchmark.**

## 6. "Make It Yours" Differentiation Blueprint

**(a) Keep — core identity (3 bullets):**
- **Transparency Rate scoped as operator-facing disclosure, reported co-primary with ASR** — the disclosure (not internal-detection) framing is the defensible core.
- **Six-module breadth unified in one Inspect AI harness** — the *combination* (prompt injection + MCP tool poisoning + RAG memory poisoning + covert exfiltration + behavioral drift + social engineering) in a single reproducible harness is a legitimate integration contribution, even though each module has individual prior art.
- **Inspect AI / AISI-ecosystem native** — interoperability with the UK AISI `inspect_evals` collection.

**(b) Cite hard — non-negotiable Related Work (with why):**
- **R-Judge** — closest *awareness* precedent; distinguish TR (agent discloses) from R-Judge (judge classifies transcript).
- **SafeEmbodAI (ADR)** and **"Dark Side of LLMs" (MIR)** — the actual novelty threats; distinguish disclosure-to-operator vs internal detection.
- **AgentDojo, InjecAgent** — canonical prompt-injection agent benchmarks; ASR/utility metric lineage.
- **Agent Security Bench (ASB)** — nearest multi-module + memory-poisoning + defenses suite; the strongest "you didn't do it first" reference for breadth.
- **MCPTox** + **Invariant Labs tool-poisoning writeups (mcp-scan, mcp-injection-experiments)** — origin of the MCP tool-poisoning module.
- **Greshake et al. (indirect prompt injection)** — foundational threat framing.
- **AgentLAB** — behavioral-drift / objective-drifting + memory-poisoning precedent.
- **"Reframing LLM Agent Security as an Agent–Human Interaction Problem"** — motivational grounding (approval fatigue) for a disclosure metric.
- **The arXiv "AgentShield" (2605.11026)** — must be cited *and* name-disambiguated.

**(c) Narrow or hedge — sentence-level edits:**
- Replace "**the first metric to measure whether an agent detects/flags an attack**" → "**To our knowledge, the first to score operator-facing *disclosure* of an attack (as opposed to internal detection, e.g., SafeEmbodAI's Attack Detection Rate, or external-monitor detection rate) as a metric reported co-primary with ASR for general tool-using agents.**"
- Replace "**a novel six-module agent security benchmark**" → "**a unified Inspect AI harness integrating six attack modules — each building on established threat models (AgentDojo/InjecAgent, MCPTox/Invariant Labs, ASB memory poisoning) — whose novel contributions are the Transparency Rate metric and the combined, reproducible packaging.**"
- Add to Limitations: "**TR overlaps conceptually with prior 'attack detection/identification' metrics (ADR, MIR) and with risk-awareness benchmarks (R-Judge); our contribution is the disclosure framing and its co-primary reporting, not the idea that agents should recognize attacks.**"
- Disambiguate name: "**Agent Shield (this framework) is distinct from the unrelated 'AgentShield' deception-detection system (Rassul et al., arXiv:2605.11026), the ecc-agentshield config scanner, and the agentshield.dev product.**"

**(d) Build next — 5 ideas ranked by originality-leverage × effort:**
1. **Formalize TR as a validated rubric with a public LLM-judge (reuse AgentAuditor/R-Judge methodology).** Highest leverage: turns TR from a claim into a reproducible, human-agreement-calibrated metric — directly hardens the novel contribution. Medium effort.
2. **TR-vs-ASR joint-frontier reporting (2-D plot, like AgentDojo's utility/security).** Shows whether disclosure trades off against task utility or refusal. High originality, low effort — no one currently plots disclosure against ASR.
3. **Alert-fatigue / false-disclosure calibration** (precision of TR: does the agent over-warn on benign inputs?). Directly addresses the Agent–Human-Interaction gap the UCLA paper flags. High leverage, medium effort.
4. **Cross-lingual TR** (does disclosure degrade in low-resource languages, as arXiv:2605.11026 found for *detection* in Kurdish/Arabic?). Medium originality, medium effort.
5. **MCP-native TR harness** — measure disclosure specifically at the tool-poisoning/rug-pull boundary using live MCP servers (MCPTox-style). Medium originality, higher effort.

**(e) Do not build — would only duplicate an existing suite:**
- Another static prompt-injection ASR benchmark on banking/Slack/travel/workspace → **AgentDojo owns this.**
- A standalone MCP tool-poisoning ASR benchmark → **MCPTox (AAAI 2026) owns this.**
- A memory-poisoning + backdoor + defenses matrix across many LLM backbones → **ASB owns this.**
- A risk-awareness judge benchmark (transcript → safe/unsafe label) → **R-Judge / AgentSafetyBench own this.**
- An MCP static config scanner / honeytoken deception layer → **mcp-scan and the arXiv "AgentShield" own this.**

## 7. Bibliography (grouped by phase)

**Phase 1:**
- https://aclanthology.org/2024.findings-emnlp.79/ ; https://arxiv.org/abs/2401.10019 ; https://arxiv.org/html/2401.10019 ; https://github.com/Lordog/R-Judge ; https://rjudgebench.github.io/
- https://arxiv.org/abs/2409.01630 (SafeEmbodAI / ADR)
- https://arxiv.org/abs/2507.06850 (MIR / "Dark Side of LLMs")
- https://arxiv.org/abs/2602.22303 (self-incrimination / report_scheming)
- https://arxiv.org/abs/2506.15740 (SHADE-Arena)
- https://arxiv.org/html/2605.24309v1 (Reframing as Agent–Human Interaction)
- https://arxiv.org/pdf/2506.00641 (AgentAuditor — metrics survey)

**Phase 2:**
- https://arxiv.org/abs/2410.02644 ; https://proceedings.iclr.cc/paper_files/paper/2025/file/5750f91d8fb9d5c02bd8ad2c3b44456b-Paper-Conference.pdf (ASB)
- https://neurips.cc/virtual/2024/poster/97522 ; https://proceedings.neurips.cc/paper_files/paper/2024/hash/97091a5177d8dc64b1da8bf3e1f6fb54-Abstract-Datasets_and_Benchmarks_Track.html (AgentDojo)
- https://arxiv.org/pdf/2403.02691 (InjecAgent)
- https://www.emergentmind.com/topics/agentharm (AgentHarm)
- https://www.arxiv.org/pdf/2412.14470v1 (AgentSafetyBench)
- https://arxiv.org/pdf/2602.16901 ; https://tanqiujiang.github.io/AgentLAB_main/ ; https://github.com/TanqiuJiang/AgentLAB (AgentLAB)
- https://arxiv.org/abs/2508.14925 ; https://ojs.aaai.org/index.php/AAAI/article/view/40895 (MCPTox)
- https://arxiv.org/pdf/2504.18575 (WASP)
- https://arxiv.org/pdf/2504.15585 (full-stack safety survey: ToolSword, ToolEmu)
- https://arxiv.org/pdf/2605.16282 (safety-benchmark taxonomy)
- https://github.com/UKGovernmentBEIS/inspect_evals ; https://ukgovernmentbeis.github.io/inspect_evals/ ; https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations (Inspect / CAISI)

**Phase 3:**
- https://github.com/invariantlabs-ai/mcp-injection-experiments ; https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks ; https://invariantlabs.ai/blog/introducing-mcp-scan ; https://invariantlabs.ai/blog/toxic-flow-analysis ; https://invariantlabs.ai/blog/mcp-github-vulnerability ; https://invariantlabs-ai.github.io/docs/mcp-scan/
- https://arxiv.org/pdf/2505.03574 (LlamaFirewall)
- https://appsecsanta.com/ai-security-tools ; https://futureagi.com/blog/top-5-ai-guardrailing-tools-2025/ (tool status: Lakera→Check Point, Protect AI→Palo Alto, Rebuff archived)

**Phase 4:**
- https://arxiv.org/abs/2605.11026 ; https://www.themoonlight.io/en/review/agentshield-deception-based-compromise-detection-for-tool-using-llm-agents (AgentShield collision)
- https://github.com/affaan-m/agentshield ; https://agentshield.dev/ (name collisions)
- https://github.com/topics/agentdojo (user's own repo listing, confirming "ASR, benign utility, and Transparency Rate")

## 8. Open Questions for Manual Verification

1. **Read SafeEmbodAI (arXiv:2409.01630) in full** to confirm whether ADR counts *user-facing* surfacing or only internal detection — this is the pivotal fact determining how strongly TR's novelty holds. It is your single biggest exposure.
2. **Confirm the exact Zenodo record contents** (10.5281/zenodo.20789431): verify the README/abstract wording this audit recommends editing, and whether ASB/MCPTox/R-Judge are already cited.
3. **Verify whether the six modules include defense evaluation or are attack-only** — ASB overlap becomes High-plus if defenses are included.
4. **Contact R-Judge / SafeEmbodAI authors** if a formal novelty statement is needed for peer review.
5. **Trademark/name check on "Agent Shield"** given three live "AgentShield" projects — decide on a rename for any runtime/product component now (the DOI-anchored eval-framework name can stay, but a distinct runtime brand is advisable).
6. **Confirm "CanaryBench" / "DeepContext"** are not internal working names for real references — neither could be confirmed to exist as public agent-security benchmarks; do not cite them as real without a source.

---

*Methodological note: This audit rests on ~15 web searches plus one targeted subagent sweep and one enrichment pass. Several cited works carry 2026 arXiv IDs (2602.x–2607.x) consistent with the current date (July 2026); their self-described metrics are reported as claimed, not independently reproduced. Where a project's status changed (Rebuff archived; Lakera/Protect AI acquired), this is flagged inline. No named project was presented as real unless a concrete source was found; CanaryBench and DeepContext are explicitly flagged as unconfirmed.*
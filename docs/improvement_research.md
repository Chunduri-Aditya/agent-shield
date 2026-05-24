# Agent Shield Research Notes — LLM Agent Security Evaluation Framework

**Bottom line up front:** The LLM agent security eval space lacks any standardized human-readable reporting layer, severity vocabulary, or CIA-triad mapping — every existing benchmark (AgentDojo, HarmBench, InjecAgent, AgentHarm) reports raw rate metrics only. Agent Shield should adopt the OWASP AIVSS v0.5 scoring system (CVSS v4.0-based, 0–10 scale, with Critical/High/Medium/Low buckets) as its severity vocabulary, borrow the ZAP/Snyk/Semgrep vulnerability-card structure for human-readable cards, gate execution via an Inspect-AI-style tool-approval policy with risk tiers cross-mapped to Anthropic's ASL scheme, and map attack categories to CIA per the Rehberger (2024) and Luo et al. (2025) frameworks — but acknowledge that MITRE ATLAS itself does **not** publish a CIA mapping or per-technique severity, so Agent Shield will be filling a documented gap.

---

## IMPROVEMENT 1 — Human-Readable Reporting Layer

### Q1: What do existing eval frameworks output?

**Finding: All four output raw numerical metrics only. None produce plain-English vulnerability explanations.** [CITE all four]

- **AgentDojo** (Debenedetti, Zhang, Balunovic, Beurer-Kellner, Fischer, Tramèr, 2024, NeurIPS D&B; github.com/ethz-spylab/agentdojo): outputs three numeric metrics via `SuiteResults`: **Benign Utility (BU)**, **Utility Under Attack (UA)**, and **Targeted Attack Success Rate (ASR)**. Per-task pass/fail in `utility_results` and `security_results` dicts. Traces viewable via Invariant Explorer but no narrative explanation.
- **HarmBench** (Mazeika et al., 2024, ICML; arXiv:2402.04249): outputs **Attack Success Rate (ASR)** as primary metric across 510 behaviors in 4 functional categories. No vulnerability narrative.
- **InjecAgent** (Zhan, Liang, Ying, Kang, 2024, ACL Findings; arXiv:2403.02691): outputs **ASR-valid** disaggregated by attack step and attack category. Critique (arXiv:2510.05244, 2025): "InjecAgent reports the ASR, but provides no utility metric. This makes it impossible to measure either the BU or UA and, therefore, to assess the utility impact of defenses."
- **AgentHarm** (Andriushchenko et al., 2024, ICLR 2025; arXiv:2410.09024): outputs **harm score** (0–1 Python rubric grading) and **refusal rate** across 11 harm categories. Uses Inspect AI's synthetic tooling environment. No plain-English vulnerability description.

[CHANGES BUILD] Agent Shield's reporting layer is a genuine net-new contribution. No precedent in this benchmark family.

---

### Q2: Precedents in traditional security tooling

**Finding: ZAP, Snyk, and Semgrep all use a structured "vulnerability card" pattern with consistent fields. Adopt this directly.** [CITE]

**OWASP ZAP**: Each alert includes `pluginid`, `alertRef`, `alert` (name), `riskcode` (0–3), `confidence`, `riskdesc`, `desc` (HTML description), `solution`, `reference`, `cweid`, `wascid`, `instances[]`. Severity vocabulary: **Informational, Low, Medium, High**.

**Snyk**: Uses CVSS v4.0 + v3.1. Levels: **Critical / High / Medium / Low**. Each vulnerability has SNYK-ID, CVE-IDs, CVSS vector, base score, exploit maturity, affected package/version, fix version, description, references.

**Semgrep**: YAML rule structure includes `id`, `message` (human-readable explanation), `severity`, `languages`, `metadata` (with `cwe`, `confidence`, `likelihood`, `impact`, `category`, `references`). Findings also carry a `fix` field.

**Agent Shield canonical 11-field vulnerability card (synthesized):**

| # | Field | Description |
|---|---|---|
| 1 | `id` | e.g., `AS-PI-001` |
| 2 | `title` | one-line human-readable |
| 3 | `severity` | Critical / High / Medium / Low (AIVSS) |
| 4 | `confidence` | High / Medium / Low |
| 5 | `cia_impact` | C, I, A — which properties are violated |
| 6 | `category` | prompt-injection, tool-poisoning, etc. |
| 7 | `description` | plain English: what happened and why it matters |
| 8 | `evidence` | actual transcript/trace excerpt |
| 9 | `reproduction` | steps to reproduce |
| 10 | `remediation` | concrete fix recommendation |
| 11 | `references` | OWASP LLM/ASI IDs, MITRE ATLAS ID, AIVSS Core Risk, CWE |

[CHANGES BUILD] Adopt this 11-field card schema as Agent Shield's canonical output format.

---

### Q3: NIST AI RMF on communicating to non-technical stakeholders

**Finding: AI RMF 1.0 (NIST AI 100-1, Jan 2023) and the GenAI Profile (NIST-AI-600-1, Jul 2024) explicitly call for stakeholder-appropriate communication but do not prescribe specific language.** [CITE]

Key points from AI RMF 1.0:
- The **Manage** function requires "communicating residual risks to relevant stakeholders" and ensures organizations can "respond to, recover from, and communicate about incidents or events."
- The **Govern** function emphasizes "transparency and documentation" as "vital for trustworthy AI systems."
- Risk tolerance is "context-dependent" — RMF deliberately does **not** prescribe a universal severity vocabulary but expects organizations to define one in their Profile.

NIST AI RMF organizes trustworthy AI characteristics into 7 named pillars (valid/reliable, safe, secure/resilient, accountable/transparent, explainable/interpretable, privacy-enhanced, fair-with-bias-managed). Agent Shield's reports should use plain-English mappings to these 7 pillars when explaining what failed.

[TENSION] NIST AI RMF does **not** offer a ready-made severity vocabulary. CSA Lab Space (Agentic Profile, 2026): "The GOVERN function requires organizations to establish risk tolerance policies and assign accountability for AI risk management, but it does not differentiate between AI systems based on their degree of operational autonomy." Agent Shield fills this gap explicitly.

---

### Q4: OWASP LLM Top 10 2025 and Agentic Top 10 2026 on developer communication

**Finding: Both lists structure each entry as a developer-facing card — useful as a model.** [CITE]

- **OWASP LLM Top 10 2025** (genai.owasp.org/llm-top-10/): LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM03 Supply Chain, LLM04 Data and Model Poisoning, LLM05 Improper Output Handling, LLM06 Excessive Agency, LLM07 System Prompt Leakage, LLM08 Vector and Embedding Weaknesses, LLM09 Misinformation, LLM10 Unbounded Consumption.
- **OWASP Top 10 for Agentic Applications 2026** (Dec 10 2025, genai.owasp.org): ASI01 Agent Goal Hijack, ASI02 Tool Misuse, ASI03 Identity & Privilege Abuse, ASI04 Supply Chain, ASI05 Unexpected Code Execution, ASI06 Memory/Context Poisoning, ASI07 Insecure Inter-Agent Communication, ASI08 Cascading Failures, ASI09 Over-Trust/Social Engineering, ASI10 Rogue Agents.

[CHANGES BUILD] Agent Shield should map every detected vulnerability to the relevant LLM01–10 and/or ASI01–10 ID. This gives developers a stable identifier.

---

### Q5: Standard severity vocabulary for LLM/agent vulnerabilities

**Finding: As of March 2026, OWASP AIVSS v0.5 is the closest emerging standard. Adopt it.** [CITE] [CHANGES BUILD]

**OWASP AIVSS v0.5** (aivss.owasp.org, presented OWASP Global AppSec Nov 7 2025): Extends CVSS v4.0 with **Agentic AI Risk Score (AARS)** amplification factors: autonomy, tool use, dynamic identity, persistent memory, self-modification. Score 0–10, buckets: Critical (9.0–10.0), High (7.0–8.9), Medium (4.0–6.9), Low (0.1–3.9). 10 Agentic AI Core Security Risks (ranked by demonstrated impact):
1. Agentic AI Tool Misuse
2. Agent Access Control Violation
3. Agent Cascading Failures
4. Agent Orchestration and Multi-Agent Exploitation
5. Agent Identity Impersonation
6. Agent Memory and Context Manipulation
7. Insecure Agent Critical Systems Interaction
8. Agent Supply Chain and Dependency Attacks
9. Agent Untraceability
10. Agent Goal and Instruction Manipulation

Ken Huang (SC Media, Nov 7 2025): "The CVSS and other regular software vulnerability frameworks are not enough. These assume traditional deterministic coding. We need to deal with the non-deterministic nature of agentic AI."

**Recommendation:** Adopt AIVSS Critical/High/Medium/Low with 0–10 numeric score. CAVEAT: pin to v0.5 until v0.8 is officially published at aivss.owasp.org (v0.8 is cited by third parties but not yet confirmed official).

---

## IMPROVEMENT 2 — Risk Review System (Session + Eval Gate)

### Q1: Pre-run risk classification in existing eval frameworks

**Finding: None of the major AI safety eval frameworks have a built-in pre-run risk classification step. Inspect AI has the closest analogue.** [CITE] [CHANGES BUILD]

**Inspect AI** (UK AISI, inspect.aisi.org.uk/approval.html): Implements an **approval policy** system. CLI flag `--approval human` requires interactive approval of every tool call. Approval policies can chain: `human` approver for specific tools, `auto` approver for the rest. Approvers can be human, automated heuristics, or model-graded. This operates at runtime (tool-call level), not pre-run.

EleutherAI lm-eval-harness, HELM, AgentDojo: no risk classification or gating step.

[CHANGES BUILD] Agent Shield should adopt Inspect AI's policy DSL pattern (YAML approver chain by tool/category) but extend it to operate at the **eval-suite level** (decide whether to run an entire attack category) in addition to the tool-call level.

---

### Q2: MITRE ATLAS risk tiers / severity taxonomy

**Finding: MITRE ATLAS v5.4.0 (Feb 2026) contains 16 tactics, 84 techniques, 56 sub-techniques, 32 mitigations, 42 case studies — and ZERO severity ratings.** [CITE] [TENSION]

ATLAS does not tag techniques with High/Medium/Low or CVSS scores. ATT&CK tags Impact-tactic techniques with "Impact Type" (Integrity or Availability) but ATLAS has not adopted this tag. A 2025 ACM paper (dl.acm.org/doi/10.1145/3731806.3731846, "Risk-Based MITRE TTP Scoring") explicitly motivates a new AIM model because of "a major problem: the absence of a base scoring system in MITRE frameworks."

[CHANGES BUILD] Agent Shield must define its own severity tier mapping. Recommended: map each attack to its ATLAS technique ID (taxonomic lineage) AND assign an AIVSS-derived severity score independently. This is a documented gap Agent Shield fills.

---

### Q3: Human-in-the-loop gates in traditional security tools

**Finding: Traditional tools use destructive-action confirmation patterns; the LLM analogue is Inspect AI approval policy and OpenAI Agents SDK `needs_approval`. CRITICAL CAVEAT: HITL gates can themselves be attacked.** [CITE]

- **Metasploit**: explicit confirmation before destructive payloads; `--check` mode to test without exploitation.
- **Burp Suite**: scope-limiting plus manual confirmation for active scans.
- **Inspect AI tool approval**: YAML policy chains approvers per tool; supports human approval with custom UI via message queues.
- **OpenAI Agents SDK** (`needs_approval`): tools declare approval requirement; runner evaluates before execution; supports sticky approvals with scope and expiry.

**CRITICAL — Checkmarx "Lies-in-the-Loop" (Sept 2025, checkmarx.com/zero-post/turning-ai-safeguards-into-weapons-with-hitl-dialog-forging/):** "The Lies-in-the-Loop (LITL) attack exploits the trust users place in these dialogs by forging their content." Agent Shield's approval UI MUST show actual tool args, not LLM-generated summaries. This is also a testable attack surface Agent Shield can eval.

**Design pattern**: gate at "commit points" where action becomes irreversible (modifying production resources, sending external messages, financial transactions). Avoid approval fatigue: low-risk auto-allow, medium-risk batched, only commit-points interrupt.

---

### Q4: Prior work on pre-execution risk classification for agentic systems

**Finding: Small but growing literature explicitly addresses pre-execution risk classification.** [CITE]

- **Luo et al. (2025), AGrail** (arXiv:2502.11448): Explicit CIA framing. Performs lifelong safety detection on agent actions, classifying by predicted CIA impact before execution.
- **Rath (2026), "Agent Drift"** (arXiv:2601.04170): introduces semantic/coordination/behavioral drift; proposes Agent Stability Index. Cite cautiously — single-author, no peer review yet.
- **Arike et al. (2025), Apollo Research** (arXiv:2505.02709): defines goal drift as "an agent's tendency to deviate from its original instruction-specified goal over time."
- **OWASP Agentic Top 10 2026 / AIVSS**: implicitly recommend pre-execution gating for high-AARS actions but don't specify implementation.

---

### Q5: NIST AI RMF Govern function on human oversight

**Finding: Govern function calls for human oversight but does NOT prescribe a specific risk-tier mechanism.** [CITE] [TENSION]

CSA Lab Space NIST AI RMF Agentic Profile (May 2026) explicitly identifies this as a structural gap: "The GOVERN function does not differentiate between AI systems based on their degree of operational autonomy."

[CHANGES BUILD] Agent Shield's risk-review gate fills a documented gap in NIST AI RMF for agentic systems.

---

### Q6: Anthropic RSP risk tiers

**Finding: RSP defines ASL-1 through ASL-4+ for model capabilities, not individual vulnerabilities. Orthogonal to but compatible with Agent Shield's severity tiers.** [CITE]

Anthropic RSP v3.0 ASL mapping to Agent Shield tiers:

| ASL | Agent Shield tier | Justification |
|---|---|---|
| ASL-1 | LOW | Baseline capability, no catastrophic risk |
| ASL-2 | MEDIUM | Early dangerous capabilities, limited operational uplift |
| ASL-3 | HIGH | Substantial catastrophic uplift OR autonomy capabilities (activated for Claude Opus 4, May 2025) |
| ASL-4 | CRITICAL | Reserved — large-scale catastrophic potential |

[TENSION] ASL is capability-based (what a model can do); Agent Shield severity is vulnerability-based (what an attack did do). Track both independently.

---

## IMPROVEMENT 3 — CIA Triad Check (Query Firewall)

### Q1: OWASP LLM/Agentic Top 10 → CIA mapping

**Finding: Both OWASP lists map to CIA only IMPLICITLY. No published explicit mapping table.** [TENSION]

Inferred mapping (synthesized from Rehberger 2024; Tariq & Kerschbaum 2025; toxsec.com CIA-for-LLMs):

| OWASP LLM 2025 | Primary CIA |
|---|---|
| LLM01 Prompt Injection | Integrity (C/A collateral) |
| LLM02 Sensitive Information Disclosure | Confidentiality |
| LLM03 Supply Chain | Integrity |
| LLM04 Data and Model Poisoning | Integrity |
| LLM05 Improper Output Handling | Integrity |
| LLM06 Excessive Agency | Integrity |
| LLM07 System Prompt Leakage | Confidentiality |
| LLM08 Vector and Embedding Weaknesses | Confidentiality + Integrity |
| LLM09 Misinformation | Integrity |
| LLM10 Unbounded Consumption | Availability |

| OWASP ASI 2026 | Primary CIA |
|---|---|
| ASI01 Agent Goal Hijack | Integrity |
| ASI02 Tool Misuse | Integrity |
| ASI03 Identity & Privilege Abuse | Confidentiality + Integrity |
| ASI04 Supply Chain | Integrity |
| ASI05 Unexpected Code Execution | Integrity |
| ASI06 Memory/Context Poisoning | Integrity |
| ASI07 Insecure Inter-Agent Comm | Integrity + Confidentiality |
| ASI08 Cascading Failures | Availability + Integrity |
| ASI09 Over-Trust/Social Engineering | Integrity |
| ASI10 Rogue Agents | Integrity |

[CHANGES BUILD] Agent Shield must produce its own CIA mapping table since OWASP does not publish one. Cite toxsec framing: "For an LLM, confidentiality protects what the model knows and processes, integrity protects what the model outputs, and availability protects whether the model can serve a request at all."

---

### Q2: MITRE ATLAS → CIA mapping

**Finding: ATLAS does NOT publish a CIA-triad mapping table for its techniques.** [CITE] [TENSION]

Impact tactic techniques map implicitly:
- AML.T0024 Exfiltration via ML Inference API → Confidentiality
- AML.T0029 Denial of ML Service → Availability
- AML.T0031 Erode ML Model Integrity → Integrity
- AML.T0015 Evade ML Model → Integrity
- AML.T0034 Cost Harvesting → Availability

ATT&CK mandates a CIA "Impact Type" tag for Impact-tactic techniques. ATLAS has not adopted this. Agent Shield's CIA mapping extends ATLAS in a documented gap.

---

### Q3: Foundational paper CIA framing

**Finding: None of the foundational LLM-agent attack papers explicitly use the CIA triad. Later work (Rehberger 2024; Tariq & Kerschbaum 2025) retroactively maps them.** [CITE]

- **Greshake et al. (2023), arXiv:2302.12173**: classifies by attack goal (information gathering, fraud, intrusion, malware, manipulated content, availability) — maps to CIA but doesn't use the framing.
- **AgentDojo (2024)**: classifies by domain and attack template. No CIA framing.
- **InjecAgent (2024)**: "direct harm" vs. "exfiltration of private data" — implicit Integrity vs. Confidentiality split.
- **AgentHarm (2024)**: 11 harm categories, not CIA-based.
- **Rehberger (2024), arXiv:2412.06090, "Trust No AI: Prompt Injection Along The CIA Security Triad"**: most thorough explicit CIA classification. Compiles real exploits at OpenAI/Microsoft/Anthropic/Google under each CIA pillar.
- **Tariq & Kerschbaum (2025), MDPI Future Internet 17(3):113**: formalizes a CIA-aligned taxonomy of prompt attacks. "Integrity risks stem from prompt injections that manipulate outputs to generate biased, misleading, or malicious content."

[CHANGES BUILD] Cite Rehberger 2024 + Tariq & Kerschbaum 2025 + Luo et al. 2025 as the CIA-framing foundation.

---

### Q4: Plain-English CIA Triad templates

**Finding: Best plain-language framing synthesized from toxsec.com and Splunk standard definitions.** [CITE]

Validated templates for Agent Shield (use verbatim or close paraphrase):

- **Confidentiality violation** — "The agent leaked information it was supposed to keep private — system prompts, user data, or retrieved documents were shown to someone who shouldn't see them."
- **Integrity violation** — "The agent did something other than what the user asked — its output, decisions, or tool calls were corrupted, manipulated, or hijacked. The agent misrepresented reality."
- **Availability violation** — "The agent stopped working, became too slow to use, or cost too much to run — denial of service or denial of wallet."

Source: toxsec.com CIA-for-LLMs; Splunk CIA Triad overview.

---

### Q5: Per-attack-category CIA mapping (validated)

**The canonical `CIA_MAPPING` dict for Agent Shield's codebase:**

| Agent Shield module | Primary CIA | Secondary CIA | Sources |
|---|---|---|---|
| `inputs/` prompt injection | **Integrity** | Confidentiality, Availability | Rehberger 2024; Tariq & Kerschbaum 2025; Greshake 2023 |
| `tools/` MCP tool poisoning | **Integrity** | Confidentiality (if tool exfiltrates) | OWASP ASI02, ASI04; Luo et al. 2025 |
| `psych/` social engineering | **Integrity** | — | OWASP ASI09; Rehberger 2024 |
| `memory/` RAG poisoning | **Integrity** | Confidentiality (if vectors leak data) | OWASP LLM08, ASI06; Rehberger 2024 SpAIware |
| `exfil/` data exfiltration | **Confidentiality** | — | OWASP LLM02, LLM07; Rehberger 2024 |
| `drift/` multi-turn behavioral drift | **Integrity** | — | Arike 2025; Rath 2026; Luo et al. 2025 |

[CHANGES BUILD] This table becomes `CIA_MAPPING` in `risk_registry.py`.

---

### Q6: Transparency Rate (TR) metric — Integrity violation?

**Finding: YES — TR failure maps cleanly to Integrity in the CIA triad. The security literature supports this mapping.** [CITE]

Validation chain:
1. **Splunk**: "Integrity refers to the assurance that data is trustworthy, accurate, complete, and consistent." TR failure (agent misrepresenting what it's doing) violates this exactly.
2. **Rehberger (2024)**: "agent makes the model lie" and "hijacks tool calls" are placed under Integrity. TR failure is this pattern applied to agent self-reports.
3. **Tariq & Kerschbaum (2025)**: "Integrity risks stem from prompt injections that manipulate outputs to generate biased, misleading, or malicious content."
4. **Luo et al. (2025), AGrail**: "Integrity risks arise when malicious attacks manipulate agents into executing unintended commands."
5. **NIST AI RMF 1.0**: "accountable and transparent" as a trustworthy AI characteristic. Transparency failure is an integrity-of-self-representation failure.

**Caveat — CIA+TA extension**: Verma (arXiv:2508.15839, 2025) proposes adding **Trust** and **Autonomy** as fourth and fifth CIA pillars. Under CIA+TA, TR failure maps to Trust more precisely. Recommended: classify as **Integrity** in public-facing reports (established vocabulary); note CIA+TA in design docs as future extension.

[CHANGES BUILD] TR = Integrity in `risk_registry.py` and all report output. Flag CIA+TA as v1.1 extension.

---

## CROSS-CUTTING RECOMMENDATIONS

1. Adopt OWASP AIVSS v0.5 severity scale (0–10 numeric + Critical/High/Medium/Low). Map to ASL tiers in design docs.
2. Adopt the 11-field vulnerability card schema synthesized from ZAP/Snyk/Semgrep.
3. Four-way cross-reference on every finding: OWASP LLM01–10, OWASP ASI01–10, AIVSS Core Risk, MITRE ATLAS technique ID.
4. Implement Inspect AI-style approval policy DSL at both eval-suite level and tool-call level.
5. Publish `CIA_MAPPING` constant in `risk_registry.py` using the Q5 table.
6. TR = Integrity in user-facing reports. CIA+TA as documented future extension.
7. Flag three documented gaps in the paper: (a) no severity in MITRE ATLAS, (b) no CIA mapping in ATLAS/OWASP, (c) no autonomy-tier differentiation in NIST AI RMF Govern.

---

## CAVEATS

- AIVSS v0.8 is cited by third parties but not yet officially at aivss.owasp.org. Pin to v0.5.
- Multi-turn drift as Integrity is an inference — no paper says "drift = Integrity violation" in those exact words. Agent Shield establishes this framing.
- MITRE ATLAS lacks both severity ratings and CIA mapping. Agent Shield extends ATLAS but does not depend on it for these layers.
- HITL gates can be attacked (Checkmarx Lies-in-the-Loop, Sept 2025). Approval UI must show actual tool args, not LLM summaries.
- Rath (2026) arXiv:2601.04170 has a future-dated ID and is single-author with no peer review. Cite cautiously.
- OWASP Agentic Top 10 and AIVSS Agentic Core Risks are two distinct lists. Do not conflate.

---

Last updated: 2026-05-23 (research incorporated from initial findings)

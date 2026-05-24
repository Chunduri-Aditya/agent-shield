# Agent Shield Research Notes — LLM Agent Security Evaluation Framework

**Bottom line up front:** The LLM agent security eval space lacks any standardized human-readable reporting layer, severity vocabulary, or CIA-triad mapping — every existing benchmark (AgentDojo, HarmBench, InjecAgent, AgentHarm) reports raw rate metrics only. Agent Shield should adopt the OWASP AIVSS v0.5 scoring system (CVSS v4.0-based, 0–10 scale, with Critical/High/Medium/Low buckets) as its severity vocabulary, borrow the ZAP/Snyk/Semgrep vulnerability-card structure for human-readable cards, gate execution via an Inspect-AI-style tool-approval policy with risk tiers cross-mapped to Anthropic's ASL scheme, and map attack categories to CIA per the Rehberger (2024) and Luo et al. (2025) frameworks — but acknowledge that MITRE ATLAS itself does **not** publish a CIA mapping or per-technique severity, so Agent Shield will be filling a documented gap.

---

## IMPROVEMENT 1 — Human-Readable Reporting Layer

### Q1: What do existing eval frameworks output?

**Finding: All four output raw numerical metrics only. None produce plain-English vulnerability explanations.** [CITE all four]

- **AgentDojo** (Debenedetti, Zhang, Balunovic, Beurer-Kellner, Fischer, Tramèr, 2024, NeurIPS D&B; github.com/ethz-spylab/agentdojo): outputs three numeric metrics via `SuiteResults`: **Benign Utility (BU)**, **Utility Under Attack (UA)**, and **Targeted Attack Success Rate (ASR)**. Per-task pass/fail in `utility_results` and `security_results` dicts. Traces viewable via Invariant Explorer but no narrative explanation. (Source: agentdojo.spylab.ai/api/benchmark/, github.com/ethz-spylab/agentdojo/blob/main/src/agentdojo/scripts/benchmark.py)
- **HarmBench** (Mazeika et al., 2024, ICML; arXiv:2402.04249; github.com/centerforaisafety/HarmBench): outputs **Attack Success Rate (ASR)** as primary metric across 510 behaviors in 4 functional categories (standard, contextual, copyright, multimodal). No vulnerability narrative.
- **InjecAgent** (Zhan, Liang, Ying, Kang, 2024, ACL Findings; arXiv:2403.02691): outputs **ASR-valid** disaggregated by attack step (S1 data extraction, S2 data transmission) and by attack category (direct harm, data exfil). Critique (arXiv:2510.05244, 2025): "InjecAgent reports the ASR, but provides no utility metric. This makes it impossible to measure either the BU or UA and, therefore, to assess the utility impact of defenses."
- **AgentHarm** (Andriushchenko et al., 2024, ICLR 2025; arXiv:2410.09024): outputs **harm score** (0–1 Python rubric grading) and **refusal rate** across 11 harm categories. Uses Inspect AI's synthetic tooling environment. No plain-English vulnerability description.

[CHANGES BUILD] Agent Shield's reporting layer is a genuine net-new contribution. No precedent in this benchmark family.

### Q2: Precedents in traditional security tooling

**Finding: ZAP, Snyk, and Semgrep all use a structured "vulnerability card" pattern with consistent fields. Borrow this directly.** [CITE]

**OWASP ZAP** (zaproxy.org/docs/desktop/addons/report-generation/): Each alert in JSON report includes:
- `pluginid`, `alertRef`, `alert` (name), `name`, `riskcode` (0-3), `confidence` (0-3), `riskdesc` (e.g., "High (Medium)"), `desc` (HTML description), `solution`, `reference`, `cweid`, `wascid`, `instances[]` (with uri, method, param, attack, evidence).
- Severity vocabulary: **Informational, Low, Medium, High** combined with confidence in parentheses.

**Snyk** (docs.snyk.io/manage-risk/prioritize-issues-for-fixing/severity-levels): Uses **CVSS v4.0 + v3.1** for severity. Levels: **Critical / High / Medium / Low**. Each vulnerability has: SNYK-ID, CVE-ID(s), CVSS vector, base score, exploit maturity (Threat Metric), affected package/version, fix version, description, references.

**Semgrep** (semgrep.dev/docs/semgrep-code/findings, semgrep.dev/docs/writing-rules/rule-syntax): YAML rule structure includes: `id`, `message` (the human-readable explanation), `severity` (INFO/WARNING/ERROR or HIGH/MEDIUM/LOW), `languages`, `metadata` (with `cwe`, `confidence` high/medium/low, `likelihood`, `impact`, `category`, `references`). Findings also carry a `fix` field.

**Recommended Agent Shield vulnerability card fields** (synthesized from all three):
1. `id` (e.g., `AS-PI-001`)
2. `title` (one-line human-readable)
3. `severity` (Critical/High/Medium/Low — see Q5)
4. `confidence` (High/Medium/Low)
5. `cia_impact` (C/I/A — see Improvement 3)
6. `category` (prompt-injection, tool-poisoning, etc.)
7. `description` (plain English, what happened and why it matters)
8. `evidence` (the actual transcript/trace excerpt)
9. `reproduction` (steps to reproduce)
10. `remediation` (concrete fix recommendation)
11. `references` (OWASP LLM/ASI, MITRE ATLAS ID, CWE, AIVSS score)

[CHANGES BUILD] Adopt this 11-field card schema as Agent Shield's canonical output format.

### Q3: NIST AI RMF on communicating to non-technical stakeholders

**Finding: AI RMF 1.0 (NIST AI 100-1, Jan 2023) and the GenAI Profile (NIST-AI-600-1, Jul 2024) explicitly call for stakeholder-appropriate communication but do not prescribe specific language.** [CITE]

Key points from AI RMF 1.0 (nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf):
- The **Manage** function requires "communicating residual risks to relevant stakeholders" and ensures organizations can "respond to, recover from, and communicate about incidents or events."
- The **Govern** function emphasizes "transparency and documentation" as "vital for trustworthy AI systems."
- Risk tolerance is "context-dependent" — RMF deliberately does **not** prescribe a universal severity vocabulary, but expects organizations to define one in their Profile.

**Borrowable framing**: NIST AI RMF organizes trustworthy AI characteristics into 7 named pillars (valid/reliable, safe, secure/resilient, accountable/transparent, explainable/interpretable, privacy-enhanced, fair-with-bias-managed). Agent Shield's reports should use plain-English mappings to these 7 pillars when explaining what failed.

[TENSION] NIST AI RMF does **not** offer a ready-made severity vocabulary — there's a documented gap (CSA Lab Space, "Agentic Profile," 2026, labs.cloudsecurityalliance.org/agentic/agentic-nist-ai-rmf-profile-v1/): "The GOVERN function requires organizations to establish risk tolerance policies and assign accountability for AI risk management, but it does not differentiate between AI systems based on their degree of operational autonomy." Agent Shield should fill this gap explicitly.

### Q4: OWASP LLM Top 10 2025 and Agentic Top 10 2026 on developer communication

**Finding: Both lists structure each entry as a developer-facing card (description, examples, attack scenarios, prevention/mitigation, references) — useful as a model.** [CITE]

- **OWASP LLM Top 10 for 2025** (genai.owasp.org/llm-top-10/): 10 categories — LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM03 Supply Chain, LLM04 Data and Model Poisoning, LLM05 Improper Output Handling, LLM06 Excessive Agency, LLM07 System Prompt Leakage, LLM08 Vector and Embedding Weaknesses, LLM09 Misinformation, LLM10 Unbounded Consumption. Each entry follows the same card layout.
- **OWASP Top 10 for Agentic Applications 2026** (released Dec 10, 2025, genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/): 10 ASI risks — ASI01 Agent Goal Hijack, ASI02 Tool Misuse, ASI03 Identity & Privilege Abuse, ASI04 Supply Chain, ASI05 Unexpected Code Execution, ASI06 Memory/Context Poisoning, ASI07 Insecure Inter-Agent Communication, ASI08 Cascading Failures, ASI09 Over-Trust/Social Engineering, ASI10 Rogue Agents.
- Steve Wilson (OWASP GenAI Security Project Board Co-Chair, founder of OWASP Top 10 for LLM, CPO Exabeam) emphasized that the Agentic Top 10 was designed for "clarity, courage, and community" with shared language across LLM Top 10 and AI-VSS.

[CHANGES BUILD] Agent Shield should map every detected vulnerability to the relevant LLM01–10 and/or ASI01–10 ID. This gives developers a stable identifier.

### Q5: Standard severity vocabulary for LLM/agent vulnerabilities

**Finding: There is no field-wide consensus, but as of March 2026, OWASP's AIVSS v0.5/v0.8 is the closest thing to an emerging standard, using CVSS v4.0-derived Critical/High/Medium/Low.** [CITE] [CHANGES BUILD]

- **OWASP AIVSS v0.5** (Huang, Bargury, Narajala, Gupta — published at aivss.owasp.org; presented at OWASP Global AppSec Nov 7 2025): Extends CVSS v4.0 with **Agentic AI Risk Score (AARS)** amplification factors: autonomy, tool use, dynamic identity, persistent memory, self-modification. Final score 0–10, with conventional CVSS buckets (Critical 9.0–10.0, High 7.0–8.9, Medium 4.0–6.9, Low 0.1–3.9). Identifies 10 Agentic AI Core Security Risks (verbatim, ranked by demonstrated impact in v0.5):
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
- **Ken Huang quote, SC Media, "OWASP Global AppSec: A new AI vulnerability scoring system is unveiled" (scworld.com, Nov 7 2025)**: "The CVSS and other regular software vulnerability frameworks are not enough. These assume traditional deterministic coding. We need to deal with the non-deterministic nature of agentic AI."
- **Field divergence today:**
  - HarmBench, InjecAgent, AgentDojo, AgentHarm: **no severity at all**, just raw rates.
  - Semgrep: INFO / WARNING / ERROR (or HIGH/MEDIUM/LOW in metadata).
  - ZAP: Informational / Low / Medium / High.
  - Snyk: Critical / High / Medium / Low (CVSS-driven).
  - Anthropic RSP: ASL-1 through ASL-4 (capability-based, not vulnerability-based).
  - MITRE ATLAS: **no severity rating at all** — explicit gap (see Improvement 2 Q2).

**Recommendation:** Adopt AIVSS Critical/High/Medium/Low with 0–10 numeric score. This aligns with what developers already know from CVSS/Snyk while embracing the emerging AI-specific standard.

---

## IMPROVEMENT 2 — Risk Review System (Session + Eval Gate)

### Q1: Pre-run risk classification in existing eval frameworks

**Finding: None of the major AI safety eval frameworks have a built-in pre-run risk classification step. Inspect AI has the closest analogue — a tool-approval policy that gates execution at the tool-call level, not the eval-run level.** [CITE] [CHANGES BUILD]

- **Inspect AI** (UK AISI, github.com/UKGovernmentBEIS/inspect_ai, inspect.aisi.org.uk/approval.html): Implements an **approval policy** system. CLI flag `--approval human` requires interactive approval of every tool call. Approval policies can chain: `human` approver for specific tools (e.g., `web_browser_click`, `web_browser_type`), `auto` approver for the rest. Approvers can be human, automated heuristics, or model-graded. This is the closest existing pattern to Agent Shield's Risk Review System but works at runtime, not pre-run.
- **EleutherAI lm-eval-harness**: No risk classification or gating step. Strictly runs evals against models.
- **HELM** (Stanford CRFM): No pre-run gate; runs scenario-based evaluations.
- **AgentDojo**: No risk classification; runs all suites by default.

[CHANGES BUILD] Agent Shield should adopt Inspect AI's policy DSL pattern (YAML approver chain by tool/category) but extend it to operate at the **eval-suite level** (decide whether to run an entire attack category) in addition to the tool-call level.

### Q2: MITRE ATLAS risk tiers / severity taxonomy

**Finding: MITRE ATLAS does NOT provide a severity rating per technique.** [CITE] [TENSION]

- Per the MITRE ATLAS GitHub data repository (github.com/mitre-atlas/atlas-data/releases), **ATLAS v5.4.0 (February 2026) contains exactly 16 tactics, 84 techniques, 56 sub-techniques, 32 mitigations, and 42 case studies.** Each technique page lists tactic, description, mitigations, and case studies — but no CVSS-style severity, no qualitative High/Medium/Low, no numeric score.
- ATT&CK itself tags each Impact-tactic technique with an "Impact Type" of either "Integrity" or "Availability" (per ATT&CK Design and Philosophy, March 2020, p. 24: "Each technique and sub-technique in the Impact tactic includes a mandatory 'Impact Type' tag with a value of 'Availability' or 'Integrity'"). ATLAS has NOT adopted this tag.
- A 2025 ACM paper (dl.acm.org/doi/10.1145/3731806.3731846, "Risk-Based MITRE TTP Scoring") explicitly motivates a new "Adversarial Impact Metrics (AIM)" model because of "a major problem that is inherent in most threat intelligence platforms: the absence of a base scoring system" in MITRE frameworks.

[CHANGES BUILD] Agent Shield must define its own severity tier mapping; cannot rely on ATLAS for this. Recommended approach: map each Agent Shield attack to its ATLAS technique ID (for taxonomic lineage) AND assign an AIVSS-derived severity score independently.

### Q3: Human-in-the-loop gates in traditional security tools

**Finding: Traditional security tools use destructive-action confirmation patterns; the LLM-agent analogue is the Inspect AI approval policy and OpenAI Agents SDK `needs_approval`.** [CITE]

- **Metasploit**: explicit confirmation prompts before destructive payloads; some modules have `--check` mode to test without exploitation.
- **Burp Suite**: scope-limiting (target scope) plus manual confirmation for active scans of out-of-scope hosts.
- **Inspect AI tool approval** (inspect.aisi.org.uk/approval.html): YAML policy chains approvers per tool. Custom approvers can implement heuristics or call models. Supports human approval with custom UI via message queues.
- **OpenAI Agents SDK** (Crosley, May 2026, blakecrosley.com/blog/ai-agent-approval-prompts-not-authorization): tools can declare `needs_approval`; runner evaluates before execution; unresolved approvals appear as interruptions; supports sticky approvals (`always_approve` / `always_reject` for later calls in the same run) with scope and expiry.
- **Critical caveat — Checkmarx "Lies-in-the-Loop"**: Checkmarx Zero blog post "Turning AI Safeguards Into Weapons with HITL Dialog Forging" (checkmarx.com/zero-post/turning-ai-safeguards-into-weapons-with-hitl-dialog-forging/, Sept 2025), covered by CSO Online as "Human-in-the-loop isn't enough: New attack turns AI safeguards into exploits": "The Lies-in-the-Loop (LITL) attack exploits the trust users place in these dialogs by forging their content." Implications for Agent Shield: the approval UI must be tamper-resistant and show actual tool args, not LLM-generated summaries.

**Design pattern**: place approval gates at "commit points" — where action becomes irreversible (modifying production resources, sending external messages, financial transactions). Avoid approval fatigue: low-risk auto-allow, medium-risk batched, only commit-points interrupt.

### Q4: Prior work on pre-execution risk classification for agentic systems

**Finding: A small but growing literature explicitly addresses pre-execution risk classification.** [CITE]

- **Luo et al. (2025), "AGrail: A Lifelong Agent Guardrail with Effective and Adaptive Safety Detection"** (arXiv:2502.11448): Explicit CIA framing of LLM agent risks. AGrail performs lifelong safety detection on agent actions, classifying them by predicted CIA impact before execution.
- **Rath (2026), "Agent Drift: Quantifying Behavioral Degradation in Multi-Agent LLM Systems Over Extended Interactions"** (arXiv:2601.04170): introduces semantic drift / coordination drift / behavioral drift; proposes Agent Stability Index (ASI) — could feed into a pre-execution risk classifier.
- **Arike, Donoway, Bartsch, Hobbhahn (2025), "Evaluating Goal Drift in Language Model Agents"** (arXiv:2505.02709, Apollo Research): defines goal drift as "an agent's tendency to deviate from its original instruction-specified goal over time."
- **OWASP Agentic Top 10 2026 / AIVSS**: implicitly recommend pre-execution gating for high-AARS actions but don't specify implementation.

### Q5: NIST AI RMF Govern function on human oversight

**Finding: Govern function calls for human oversight but does NOT prescribe a specific risk-tier mechanism.** [CITE] [TENSION]

NIST AI 100-1 Govern function (airc.nist.gov/airmf-resources/airmf/5-sec-core/): requires organizations to establish risk tolerance policies, assign accountability, and "set up the structures, systems, processes, and teams." Notably the framework does **not** differentiate AI systems by autonomy level. CSA Lab Space NIST AI RMF Agentic Profile (May 2026, labs.cloudsecurityalliance.org/agentic/agentic-nist-ai-rmf-profile-v1/) explicitly identifies four structural gaps including: "[Govern] does not differentiate between AI systems based on their degree of operational autonomy."

[CHANGES BUILD] Agent Shield's risk-review gate is filling a documented gap in NIST AI RMF for agentic systems.

### Q6: Anthropic RSP risk tiers for capabilities

**Finding: Anthropic's RSP defines AI Safety Levels (ASL-1 through ASL-4+) for *model capabilities*, not for individual vulnerabilities/actions.** [CITE]

Anthropic RSP v3.0 (anthropic.com/responsible-scaling-policy, anthropic.com/news/responsible-scaling-policy-v3): ASL system modeled on US biosafety levels (BSL-1 to BSL-4):
- **ASL-1**: no meaningful catastrophic risk (e.g., 2018 LLM, chess bot).
- **ASL-2**: early signs of dangerous capabilities, but information not yet useful beyond search-engine baselines (current Claude is ASL-2).
- **ASL-3**: substantially increases risk of catastrophic misuse vs. non-AI baselines OR shows low-level autonomous capabilities. Per Anthropic's blog post "Activating AI Safety Level 3 protections" (anthropic.com/news/activating-asl3-protections, May 2025): "We have activated the AI Safety Level 3 (ASL-3) Deployment and Security Standards described in Anthropic's Responsible Scaling Policy (RSP) in conjunction with launching Claude Opus 4." Anthropic noted ASL-3 was applied as a precautionary measure; definitive capabilities determination was still pending at launch. Requires enhanced security against weight theft + narrow deployment-time mitigations (especially CBRN).
- **ASL-4+**: Largely undefined in early versions; v2.1 added CBRN-development threshold and disaggregated AI R&D thresholds.

**Mapping to Agent Shield's LOW/MEDIUM/HIGH/CRITICAL:**
| ASL | Agent Shield tier | Justification |
|-----|-------------------|---------------|
| ASL-1 | LOW | Baseline-level capability, no catastrophic risk |
| ASL-2 | MEDIUM | Early dangerous capabilities but limited operational uplift |
| ASL-3 | HIGH | Substantial catastrophic uplift OR autonomy capabilities |
| ASL-4 | CRITICAL | (Reserved) — large-scale catastrophic potential |

[TENSION] ASL is capability-based (about what a model **can** do); Agent Shield severity is vulnerability-based (about what an attack **did** do). These are orthogonal but compatible — Agent Shield should track both.

---

## IMPROVEMENT 3 — CIA Triad Check (Query Firewall)

### Q1: OWASP LLM/Agentic Top 10 → CIA mapping

**Finding: Both OWASP lists map to CIA only IMPLICITLY through descriptions of impact; no published explicit mapping table.** [TENSION]

Inferred mapping (consensus from secondary sources including BSG, Aembit, Giskard, Promptfoo, and Toxsec — toxsec.com/p/cia-triad-for-llm-security explicitly maps the LLM Top 10):

| OWASP LLM 2025 | Primary CIA |
|---|---|
| LLM01 Prompt Injection | Integrity (with C/A as collateral) |
| LLM02 Sensitive Information Disclosure | Confidentiality |
| LLM03 Supply Chain | Integrity |
| LLM04 Data and Model Poisoning | Integrity |
| LLM05 Improper Output Handling | Integrity |
| LLM06 Excessive Agency | Integrity |
| LLM07 System Prompt Leakage | Confidentiality |
| LLM08 Vector and Embedding Weaknesses | Confidentiality + Integrity |
| LLM09 Misinformation | Integrity |
| LLM10 Unbounded Consumption | Availability |

Inferred mapping for Agentic Top 10 2026 (CIA pillar primarily threatened):
| ASI | Primary CIA |
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

[CHANGES BUILD] Agent Shield must produce its own CIA mapping table since OWASP does not publish one. Cite the toxsec.com framing where useful: "For an LLM, confidentiality protects what the model knows and processes, integrity protects what the model outputs, and availability protects whether the model can serve a request at all."

### Q2: MITRE ATLAS → CIA mapping

**Finding: ATLAS does NOT publish a CIA-triad mapping table for its techniques.** [CITE] [TENSION]

Confirmed by direct examination of atlas.mitre.org and the ATLAS Fact Sheet (atlas.mitre.org/pdf-files/MITRE_ATLAS_Fact_Sheet.pdf). The Impact tactic (AML.TA0011) has techniques that map implicitly:
- **AML.T0024 Exfiltration via ML Inference API** → Confidentiality
- **AML.T0029 Denial of ML Service** → Availability
- **AML.T0031 Erode ML Model Integrity** → Integrity
- **AML.T0015 Evade ML Model** → Integrity
- **AML.T0034 Cost Harvesting** → Availability
- **AML.T0048 External Harms** → varies

But ATLAS itself does not tag techniques with CIA labels — unlike ATT&CK which mandates an "Impact Type" tag (Integrity/Availability) for Impact-tactic techniques. This is a documented gap in ATLAS that Agent Shield can productively fill.

### Q3: Greshake et al. / AgentDojo / InjecAgent / AgentHarm — CIA framing

**Finding: None of the foundational LLM-agent attack papers explicitly use the CIA triad as their organizing framework. Later work (Rehberger 2024) retroactively maps them.** [CITE]

- **Greshake et al. (2023), "Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection"** (arXiv:2302.12173, AISec '23): classifies indirect prompt injection by attack goal (information gathering, fraud, intrusion, malware, manipulated content, availability) — these map to CIA but the paper doesn't use the framing directly.
- **AgentDojo (Debenedetti et al., 2024)**: classifies by domain (banking, Slack, travel, workspace) and by attack template (Important Instructions, Tool Knowledge, System Message). No CIA framing.
- **InjecAgent (Zhan et al., 2024)**: categorizes attack intentions into "direct harm to users" and "exfiltration of private data" — implicit Integrity vs. Confidentiality split.
- **AgentHarm (Andriushchenko et al., 2024)**: 11 harm categories (fraud, cybercrime, harassment, etc.) — not CIA-based.
- **Rehberger (2024), "Trust No AI: Prompt Injection Along The CIA Security Triad"** (arXiv:2412.06090): the most thorough explicit CIA classification of LLM-specific attacks, compiling real exploits at OpenAI/Microsoft/Anthropic/Google under each CIA pillar. Verbatim from the abstract: "This paper compiles real-world exploits and proof-of-concept examples … demonstrating how prompt injection undermines the CIA triad."
- **Tariq & Kerschbaum (2025), "A CIA Triad-Based Taxonomy of Prompt Attacks on Large Language Models"** (MDPI Future Internet, 17(3):113): formalizes a CIA-aligned taxonomy of prompt attacks. Explicit verbatim: "Integrity risks stem from prompt injections that manipulate outputs to generate biased, misleading, or malicious content."

[CHANGES BUILD] Agent Shield's CIA-triad check is consistent with the most recent academic framing (Rehberger 2024; Tariq & Kerschbaum 2025; Luo et al. 2025). Cite all three as foundations.

### Q4: Plain-English CIA Triad expressions for non-technical audiences

**Finding: Best plain-language framing is the toxsec.com mapping plus Splunk's standard definitions.** [CITE]

Suggested plain-English templates for Agent Shield:
- **Confidentiality violation**: "The agent leaked information it was supposed to keep private — system prompt, user data, or retrieved documents shown to someone who shouldn't see them."
- **Integrity violation**: "The agent did something other than what the user asked — its output, decisions, or tool calls were corrupted, manipulated, or hijacked. The agent misrepresented reality."
- **Availability violation**: "The agent stopped working, became too slow to use, or cost too much to run — denial of service or denial of wallet."

From Splunk (splunk.com/en_us/blog/learn/cia-triad-confidentiality-integrity-availability.html): standard non-technical definitions of each pillar. From toxsec: "Confidentiality breaks when the payload extracts system prompts, chat history, or RAG-retrieved documents the model should not share. Integrity breaks when the payload rewrites model output, makes the model lie, or hijacks tool calls toward attacker-chosen actions."

### Q5: Per-attack-category CIA mapping

**Validated mapping for Agent Shield's six categories:**

| Agent Shield category | Primary CIA | Secondary CIA | Source |
|---|---|---|---|
| **Prompt injection (inputs/)** | **Integrity** | Confidentiality (data exfil), Availability (DoS) | Rehberger 2024; Tariq & Kerschbaum 2025; Greshake 2023; Toxsec 2025 |
| **MCP tool poisoning (tools/)** | **Integrity** | Confidentiality (if tool exfiltrates) | OWASP ASI02 Tool Misuse; ASI04 Supply Chain; Luo et al. 2025 |
| **Social engineering / psych (psych/)** | **Integrity** | — | OWASP ASI09 Over-Trust; Rehberger 2024 (manipulation chapter) |
| **RAG poisoning / memory (memory/)** | **Integrity** | Confidentiality (if poisoned vectors leak data) | OWASP LLM08 Vector/Embedding Weaknesses; ASI06 Memory Poisoning; Rehberger 2024 (SpAIware case study) |
| **Data exfiltration (exfil/)** | **Confidentiality** | — | OWASP LLM02 Sensitive Info Disclosure; LLM07 System Prompt Leakage; Rehberger 2024 |
| **Multi-turn behavioral drift (drift/)** | **Integrity** | — | Inference from Arike 2025 + Rath 2026 + Luo et al. 2025; see Q6 |

[CHANGES BUILD] This validated mapping should become a constant in the codebase (`CIA_MAPPING` dict).

### Q6: Transparency Rate (TR) metric — Integrity violation?

**Finding: YES — TR failure maps cleanly to Integrity in the CIA triad. The security literature supports this mapping but does not use the exact term "Transparency Rate."** [CITE]

**Validation chain:**
1. **Splunk** standard definition: "Integrity refers to the assurance that data is trustworthy, accurate, complete, and consistent ... Tampering refers to an unauthorized user accessing a computer and changing the data on it, either by deleting or altering the data or by adding false or misleading information."
2. **Rehberger (2024), arXiv:2412.06090**: explicitly puts "agent makes the model lie" and "hijacks tool calls" under Integrity. TR failure (agent misrepresenting what it's doing) is exactly this pattern applied to *agent self-reports* rather than user-facing outputs.
3. **Tariq & Kerschbaum (2025), MDPI Future Internet 17(3):113**: "Integrity risks stem from prompt injections that manipulate outputs to generate biased, misleading, or malicious content."
4. **Luo et al. (2025), AGrail (arXiv:2502.11448)**: "Integrity risks arise when malicious attacks, such as prompt injection ... manipulate agents into executing unintended commands."
5. **NIST AI RMF 1.0** lists "valid and reliable" and "accountable and transparent" as trustworthy AI characteristics. Failure of transparency is a failure of the integrity of the agent's self-representation.

**Conceptual argument**: TR measures whether the agent honestly discloses what it is doing. If TR fails:
- The agent's output (its self-report) does not match reality.
- The user receives misleading or false information.
- This is precisely the **integrity** property — "trustworthy, accurate, complete, consistent" — violated.

**Caveat — Trust as an extension to CIA**: The CIA+TA model (Verma, "CIA+TA Risk Assessment for AI Reasoning Vulnerabilities," arXiv:2508.15839, 2025) argues that classical CIA is insufficient for AI systems and adds **Trust (epistemic validation)** and **Autonomy (human agency preservation)** as fourth and fifth pillars. Under CIA+TA, TR failure most naturally maps to **Trust** rather than Integrity. Agent Shield can choose:
- **Strict CIA**: classify TR failure as Integrity (recommended for compatibility with OWASP/MITRE/NIST language).
- **CIA+TA**: classify TR failure as Trust (more theoretically precise, but uses a less-established vocabulary).

**Recommendation**: classify as **Integrity** in the public-facing report (using the language stakeholders know) while noting in design docs that TR also maps to "Trust" in CIA+TA.

---

## CROSS-CUTTING RECOMMENDATIONS

1. **Adopt OWASP AIVSS v0.5/v0.8 severity scale.** 0–10 numeric + Critical/High/Medium/Low. Map to ASL tiers in design docs.
2. **Adopt the 11-field vulnerability card** synthesized from ZAP/Snyk/Semgrep (Q2 above).
3. **Map every Agent Shield attack to OWASP LLM01–10, OWASP ASI01–10, AIVSS Core Risk, and MITRE ATLAS technique ID.** Four-way cross-reference enables stakeholders to navigate from any framework they know.
4. **Implement an Inspect-AI-style approval policy DSL** at both eval-suite level (pre-run gate) and tool-call level (Inspect's existing semantics).
5. **Publish a CIA mapping constant** in the codebase using the Q5 table.
6. **For TR metric, classify as Integrity** in user-facing reports; flag CIA+TA as a future extension.
7. **Flag explicitly in the paper** that Agent Shield fills three documented gaps: (a) no severity in MITRE ATLAS, (b) no CIA mapping in ATLAS/OWASP, (c) no autonomy-tier differentiation in NIST AI RMF Govern.

---

## CAVEATS

- **AIVSS v0.8** was claimed by third-party (Cyber Strategy Institute, 2026) to extend v0.5 with additional risks (e.g., "Agent Data Exfiltration"); the official aivss.owasp.org PDF available is v0.5. Agent Shield should pin to v0.5 until v0.8 is officially published.
- **Multi-turn behavioral drift as Integrity** is an inference from the literature, not a canonical classification. No paper to date publishes "drift = Integrity violation" in those exact words. Agent Shield will be establishing this framing.
- **MITRE ATLAS lacks both severity ratings and CIA mapping.** Agent Shield extends ATLAS but does not depend on ATLAS for these layers.
- **HITL approval gates can themselves be attacked** (Checkmarx Lies-in-the-Loop, Sept 2025). Agent Shield's approval UI must show actual tool args, not LLM-generated summaries.
- **Rath (2026) "Agent Drift" arXiv:2601.04170** has a future-dated arXiv ID and is single-author with no peer review yet — cite cautiously.
- **OWASP Top 10 for Agentic Applications 2026 vs. AIVSS Agentic AI Core Risks**: these are two distinct, related lists. Do not conflate. The Agentic Top 10 (Dec 2025) is a developer-facing risk list; AIVSS (Mar 2026 v0.5) is a scoring system that identifies its own 10 core risks. Agent Shield should treat both as authoritative and cross-reference.
# Agent Shield: Framework Mappings

Reading notes behind these mappings live in docs/reading_notes.md.

Architectural spine cross linking industry frameworks to the 8 Agent Shield modules.
Every attack in the repo must resolve to at least one OWASP item, one ATLAS technique,
and one module. Missing mapping is debt, not done.

## Module legend

| Code | Module | Scope |
|---|---|---|
| IN | `inputs/` | Direct and indirect prompt injection |
| TL | `tools/` | MCP tool misuse and poisoning |
| MM | `memory/` | RAG and long horizon memory poisoning |
| EN | `env/` | Environment payload attacks (PDF, image, calendar, email) |
| MA | `multiagent/` | Agent to agent manipulation |
| EX | `exfil/` | Covert data exfiltration |
| DR | `drift/` | Multi turn behavioral drift |
| PS | `psych/` | Psychology grounded manipulation |

## Attack registry

Columns: attack → module(s) → OWASP LLM 2025 → OWASP Agentic 2026 → MITRE ATLAS → anchor source

| Attack | Mod | OWASP LLM | OWASP Agentic | ATLAS | Anchor |
|---|---|---|---|---|---|
| GCG suffix | IN | LLM01 | ASI01 | AML.T0054 | Zou et al. 2307.15043 |
| PAIR | IN | LLM01 | ASI01 | AML.T0054 | Chao et al. 2310.08419 |
| TAP | IN | LLM01 | ASI01 | AML.T0054 | Mehrotra et al. 2312.02119 |
| Crescendo | IN, DR | LLM01 | ASI01, ASI09 | AML.T0054, AML.T0051.002 | Russinovich et al. 2404.01833 |
| Many Shot | IN | LLM01 | ASI01 | AML.T0054 | Anil et al. 2024 Anthropic |
| PAP | IN, PS | LLM01 | ASI01, ASI09 | AML.T0054 | Zeng et al. 2401.06373 |
| Indirect injection via env | IN, EN | LLM01 | ASI01 | AML.T0051.001 | Greshake et al. 2302.12173 |
| Delimiter confusion | IN | LLM01 | ASI01 | AML.T0051.000 | TODO find anchor |
| MCP tool poisoning | TL | LLM05, LLM06 | ASI02, ASI04 | AML.T0053 | Invariant Labs 2025 |
| MCP rug pull | TL | LLM06 | ASI02, ASI04 | AML.T0053 | TODO find anchor |
| MCP line jumping | TL | LLM06 | ASI02 | AML.T0053 | TODO find anchor |
| Cross server shadowing | TL | LLM06 | ASI02, ASI04 | AML.T0053 | Willison 2025 blog |
| Confused deputy | TL | LLM06 | ASI02, ASI03* | AML.T0053 | Hardy 1988 original |
| Schema tampering | TL | LLM06 | ASI02, ASI04 | AML.T0053 | TODO find anchor |
| PoisonedRAG | MM | LLM04, LLM08 | ASI06 | AML.T0020, AML.T0051.001 | Zou et al. 2402.07867 |
| Retrieval hijack | MM | LLM08 | ASI06 | AML.T0051.001 | TODO find anchor |
| Embedding adversarial | MM | LLM04, LLM08 | ASI06 | AML.T0020 | TODO find anchor |
| Metadata hidden instruction | MM, IN | LLM01, LLM08 | ASI01, ASI06 | AML.T0051.001 | TODO find anchor |
| PDF injection | EN, IN | LLM01 | ASI01 | AML.T0051.001 | Debenedetti et al. 2406.13352 |
| Image multimodal injection | EN, IN | LLM01 | ASI01 | AML.T0051.001 | TODO find anchor |
| Calendar event payload | EN, IN | LLM01 | ASI01 | AML.T0051.001 | Debenedetti et al. 2406.13352 |
| Email payload | EN, IN | LLM01 | ASI01 | AML.T0051.001 | Debenedetti et al. 2406.13352 |
| Orchestrator bypass | MA | LLM06 | ASI07, ASI08 | AML.T0053 (loose) | Gu et al. 2407.10788 |
| Majority vote poisoning | MA | LLM04 | ASI07, ASI08 | AML.T0053 (loose) | TODO find anchor |
| Adversarial peer | MA | LLM06 | ASI07, ASI10 | AML.T0053 (loose) | Gu et al. 2407.10788 |
| Canary token exfil | EX | LLM02 | ASI01 (outcome) | AML.T0057 | TODO find anchor |
| Zero width chars | EX | LLM02 | ASI01 (outcome) | AML.T0057 | TODO find anchor |
| Homoglyph exfil | EX | LLM02 | ASI01 (outcome) | AML.T0057 | TODO find anchor |
| Base64 smuggling | EX | LLM02 | ASI01 (outcome) | AML.T0057 | TODO find anchor |
| Markdown image sink | EX | LLM02 | ASI01 (outcome) | AML.T0057 | Willison posts |
| Cialdini authority | PS, DR | LLM01 | ASI01, ASI09 | AML.T0054 | Cialdini 1984 |
| Cialdini reciprocity | PS | LLM01 | ASI01, ASI09 | AML.T0054 | Cialdini 1984 |
| Cialdini scarcity | PS | LLM01 | ASI01, ASI09 | AML.T0054 | Cialdini 1984 |
| Cialdini consistency | PS, DR | LLM01 | ASI01, ASI09 | AML.T0054, AML.T0051.002 | Cialdini 1984 |
| Cialdini liking | PS | LLM01 | ASI01, ASI09 | AML.T0054 | Cialdini 1984 |
| Cialdini social proof | PS | LLM01 | ASI01, ASI09 | AML.T0054 | Cialdini 1984 |
| Hadnagy pretexts | PS | LLM01 | ASI01, ASI09 | AML.T0054 | Hadnagy 2010 |
| Kahneman System 1 exploits | PS | LLM01 | ASI01, ASI09 | AML.T0054 | Kahneman 2011 |
| Sycophancy induction | DR | LLM01 | ASI09 | AML.T0054, AML.T0051.002 | Perez et al. 2212.09251 |
| Sandbagging detection | DR | TODO | ASI10 | AML.T0048 | TODO find anchor |

\* ASI03 tagged on confused deputy is partial coverage. See Scope and Limitations section.

## Reverse index: OWASP LLM Top 10 for LLM Applications 2025

Source: OWASP Top 10 for LLM Applications 2025, Version 2025, released
November 18, 2024. Verified against primary document on Apr 20.

| ID | Name | Primary modules | Coverage |
|---|---|---|---|
| LLM01 | Prompt Injection | IN, EN, MM, PS | Full |
| LLM02 | Sensitive Information Disclosure | EX | Partial (behavioral disclosure only, not training data inversion) |
| LLM03 | Supply Chain | TL (MCP provenance only) | Partial (see Scope and Limitations) |
| LLM04 | Data and Model Poisoning | MM | Partial (inference time RAG and embedding poisoning only, no training time poisoning) |
| LLM05 | Improper Output Handling | TL | Partial (we test that unsafe output is generated, not that downstream systems execute it) |
| LLM06 | Excessive Agency | TL, MA | Full |
| LLM07 | System Prompt Leakage | IN, EX | Full |
| LLM08 | Vector and Embedding Weaknesses | MM, EX | Full (EX added to cover embedding inversion leakage paths) |
| LLM09 | Misinformation | DR | Full |
| LLM10 | Unbounded Consumption | Out of scope | See Scope and Limitations |

### Cross cutting principle that shapes the architecture

OWASP's repeated theme across LLM01, LLM05, LLM06, and LLM07 is that the LLM
should be treated as an untrusted component, not as the security boundary.
This is the design assumption Agent Shield is built on and Inspect AI encodes.
Worth surfacing explicitly in the paper's Methodology section as the reason
our metric schema separates utility under attack from attack success rate:
we assume the model will sometimes comply, so we measure what the system
does with compliant output, not whether compliance can be prevented.

## Reverse index: OWASP Agentic AI Top 10 (Dec 2025)

Source: OWASP GenAI Security Project, released Dec 10, 2025 at Black Hat Europe.
ASI prefix = Agentic Security Issue.

| ID | Name | Primary modules | Coverage |
|---|---|---|---|
| ASI01 | Agent Goal Hijack | IN, EN, MM, PS | Full |
| ASI02 | Tool Misuse & Exploitation | TL, IN | Full |
| ASI03 | Identity & Privilege Abuse | TL, MA | Partial (see Scope and Limitations) |
| ASI04 | Agentic Supply Chain Vulnerabilities | TL | Full (MCP descriptors, tool provenance) |
| ASI05 | Unexpected Code Execution | TL, EN | Partial (see Scope and Limitations) |
| ASI06 | Memory & Context Poisoning | MM, IN | Full |
| ASI07 | Insecure Inter-Agent Communication | MA | Full |
| ASI08 | Cascading Failures | MA, DR | Full |
| ASI09 | Human–Agent Trust Exploitation | PS, DR | Full |
| ASI10 | Rogue Agents | DR, MA | Full |

Note. Exfiltration (`exfil/` module) does not map to a dedicated ASI class.
OWASP treats data exfiltration as a downstream outcome of ASI01 (goal hijack),
ASI02 (tool misuse), or ASI06 (memory poisoning) rather than as a standalone class.
Exfil rows in the attack registry are tagged `ASI01 (outcome)` to reflect this.

Reference incidents named by OWASP:
* ASI01 exemplar: EchoLeak (zero click prompt injection against Microsoft Copilot)
* ASI02 exemplar: Amazon Q (legitimate tools bent to destructive outputs)
* ASI03/ASI04 motivator: MCP server impersonation incidents

## Reverse index: MITRE ATLAS

Verified against current ATLAS taxonomy on Apr 20, 2026. Three changes from
the initial seed: T0053 renamed (plugin → tool invocation), T0051 now exposes
sub techniques, T0048 now exposes sub techniques. Scope notes added where
the current ATLAS definition is broader than the original seed.

| Technique | Name | Modules | Notes |
|---|---|---|---|
| AML.T0051 | LLM Prompt Injection | IN, EN, MM | Sub techniques: .000 Direct, .001 Indirect, .002 Triggered |
| AML.T0051.000 | Direct | IN | User turn injection, jailbreak prompts |
| AML.T0051.001 | Indirect | EN, MM | Env or retrieval payloads (PDF, image, RAG, calendar, email) |
| AML.T0051.002 | Triggered | EN, MM, DR | Conditional payloads, latent triggers, time or context gated |
| AML.T0054 | LLM Jailbreak | IN, PS, DR | Scope is input level and architecture level guardrail bypass |
| AML.T0053 | AI Agent Tool Invocation | TL | **Renamed from LLM Plugin Compromise.** Now covers MCP, external services, data sources, API actions, code exec capable tools |
| AML.T0057 | LLM Data Leakage | EX, MM | Scope covers training data, connected data sources, and other users' data, not just memorization |
| AML.T0056 | Extract LLM System Prompt | IN, EX | Distinct from T0057. Emphasis on system prompt as sensitive config or IP |
| AML.T0020 | Poison Training Data | MM | Underlying data and labels, latent vulnerabilities triggered later |
| AML.T0048 | External Harms | DR | Sub techniques: .000 Financial, .001 Reputational, .002 Societal, .003 User, .004 AI IP Theft |
| AML.T0048.000 | Financial Harm | DR, TL | Downstream economic impact |
| AML.T0048.001 | Reputational Harm | DR, PS | Brand or trust damage |
| AML.T0048.002 | Societal Harm | DR | Misinformation, polarization |
| AML.T0048.003 | User Harm | DR, PS | Direct harm to interacting user |
| AML.T0048.004 | AI Intellectual Property Theft | EX, IN | Model or system prompt theft as IP loss |

### Open question: agent specific ATLAS coverage

The current ATLAS taxonomy does not yet expose first class techniques for
multi agent coordination attacks (orchestrator bypass, majority vote poisoning,
adversarial peer). These map only loosely to T0053 (tool invocation when the
"tool" is another agent) or T0048 (downstream harm). This is a gap to flag in
the paper Limitations section. Pending: confirm during Day 19 multi agent
module build whether to propose new ATLAS techniques as part of responsible
disclosure or just document the gap.

### Reverse index implication for paper methodology

The T0051 sub technique structure (Direct, Indirect, Triggered) gives Agent
Shield a cleaner story for cross module mapping than I originally wrote. The
inputs module covers .000, the env and memory modules cover .001, and the
drift module covers .002. This is worth surfacing explicitly in the Methodology
section as evidence the module decomposition is taxonomy aligned, not arbitrary.

## Verification debt

Resolve during today's reading blocks. Every line here is a required task before
Phase I close.

* [x] OWASP Agentic Top 10 exact item names and IDs (Apr 20, source: OWASP GenAI Security Project, Astrix writeup cross check)
* [x] OWASP Agentic to Agent Shield module mapping full table (Apr 20, see Scope and Limitations for partial coverage notes)
* [x] MITRE ATLAS technique IDs verified against current taxonomy (Apr 20, three changes integrated: T0053 renamed, T0051 sub techniques exposed, T0048 sub techniques exposed)
* [x] Multi agent ATLAS coverage (Apr 20, no first class agent techniques in current taxonomy, gap flagged for paper Limitations and possible disclosure proposal during Day 19)
* [ ] Delimiter confusion anchor source
* [ ] MCP rug pull original source
* [ ] MCP line jumping original source
* [ ] Schema tampering anchor source
* [ ] Retrieval hijack anchor source
* [ ] Embedding adversarial anchor source
* [ ] Metadata hidden instruction anchor source
* [ ] Image multimodal injection anchor source
* [ ] Majority vote poisoning anchor source
* [ ] Canary token exfil anchor source
* [ ] Zero width chars anchor source
* [ ] Homoglyph exfil anchor source
* [ ] Base64 smuggling anchor source
* [ ] Sandbagging detection anchor source
* [x] LLM10 Unbounded Consumption scope decision (Apr 20, out of scope, documented in Scope and Limitations)

## Scope and limitations

We mapped Agent Shield's evaluation modules to the OWASP Agentic Top 10 (2026)
as a coverage audit rather than a keyword alignment exercise. The mapping is
largely strong across goal hijack, tool misuse, supply chain, memory poisoning,
inter agent communication, cascading failures, human trust exploitation, and
rogue agent behavior. However, two categories are only partially covered.

ASI03, Identity and Privilege Abuse, is defined by OWASP as an identity centric
class spanning agent persona, API keys, OAuth tokens, delegated sessions,
privilege inheritance, confused deputy flows, and transitive permission abuse.
Agent Shield currently covers the behavioral manifestations of identity abuse
through tool and multi agent modules, but not the credential layer mechanics
themselves.

ASI05, Unexpected Code Execution, is also only partially covered. OWASP treats
this as a distinct class involving agent generated or attacker induced execution
of code, including shell reflection, unsafe deserialization, eval based
execution, malicious package execution, and multi step tool chains ending in
runtime compromise. Agent Shield currently distributes this coverage across
tool and environment modules rather than isolating it as a dedicated code
generation module.

We retain this narrower scope deliberately to preserve module discipline for
the current workshop paper, and document both gaps as limitations for future
expansion.

Two additional items from the OWASP LLM Top 10 2025 sit partially or fully out
of scope. LLM03 Supply Chain, in its full form, covers model weights, LoRA
adapters, datasets, conversion pipelines, provider privacy policy drift, and
on device model tampering. Agent Shield only touches this surface through MCP
tool and descriptor provenance in the tool module. Training time artifacts and
model packaging are out of scope. LLM10 Unbounded Consumption, covering cost
abuse, compute drain, denial of wallet, and model extraction, is fully out of
scope. The benchmark is designed to measure attack success on model behavior,
not resource consumption. Both are documented as deliberate narrowing for this
workshop paper.

## Conventions

* Every new attack in the repo adds a row to the registry before being merged.
* TODO markers are acceptable in cells. Blank cells are not.
* Anchor source means one primary source. Not a review article. Not a secondary blog
  unless the blog is the original report (e.g., Willison, Invariant Labs).
* If an attack spans more than two modules, that is a signal the taxonomy is
  fraying. Raise before merging.
* This file is the single source of truth for the paper's methodology section.

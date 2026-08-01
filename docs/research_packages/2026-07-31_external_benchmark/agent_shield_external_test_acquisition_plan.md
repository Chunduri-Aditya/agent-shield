# Agent Shield external test acquisition and company-agent evaluation plan

Snapshot date: 2026-07-31

## Outcome

Yes: the high-signal repositories contain enough permissively licensed test material to build a substantial cross-project adversarial corpus. The source repositories have been obtained as shallow, read-only snapshots at exact commits and inspected without executing their code.

The imported tests should not be treated as one undifferentiated pile. They cover different systems:

- model-facing attack prompts;
- tool and MCP poisoning;
- multi-agent and provenance attacks;
- static configuration vulnerabilities;
- runtime policy and syscall behavior;
- benign/over-refusal controls;
- business-workflow regressions.

The correct research design is a provenance-tracked adapter layer that preserves each source’s meaning, license, and expected behavior while scoring every compatible run with Agent Shield’s common outcome schema.

## Acquired high-value sources

| Source | Snapshot commit | License status | Test assets found | Recommended use |
|---|---|---|---|---|
| [`doronp/agentshield-benchmark`](https://github.com/doronp/agentshield-benchmark) | `a0eb8fbc0d1a099da9299575013639168c98441b` | Apache-2.0 | 537 JSONL cases: 205 prompt injection, 87 exfiltration, 80 tool abuse, 65 benign/over-refusal, 45 jailbreak, 35 multi-agent, 20 provenance. | Highest-priority portable replay corpus; preserve category and expected-behavior fields. |
| [`Evalyze-Labs/AgentShield-Bench`](https://github.com/Evalyze-Labs/AgentShield-Bench) | `0f8f1f2f8f8e1a20e151a05aa7e0950554e2bc7b` | Apache-2.0 | 130 attack cases, 320 memory cases, plus versioned v3 scenario/seeds datasets. Versions may overlap and must be deduplicated rather than summed. | Direct/model, memory, recovery, consistency, severity, and task-retention adapters. |
| [`jang1563/agentshield`](https://github.com/jang1563/agentshield) | `e24ca6da64f4ad5ad7a9243a9efd397e288ef3b4` | MIT | 100 published scenarios across prompt injection, data poisoning, multi-turn escalation, and tool misuse; companion benign evaluation and Hugging Face dataset. | Research comparison lane; retain threat-model and corpus provenance. |
| [`Yassin-H-Rassul/AgentShield`](https://github.com/Yassin-H-Rassul/AgentShield) | `5d9c3e862210ef8d36f3752b3f5964bf7fe27dae` | MIT | AgentDojo-based attack code, benign trials, adaptive attacks, 96 Kurdish/Arabic adaptive translations, 80 benign translations, and cross-language cases. | Detection-versus-disclosure comparison, adaptive attacks, and future cross-lingual TR. |
| [`cdayAI/Agent-Shield`](https://github.com/cdayAI/Agent-Shield) | `63b15b59bd84287948329fcda1e009fc2c4271b5` | MIT | Portable corpus v1.0.0 with 82 cases: 42 attacks and 40 benign inputs across seven attack categories; larger code-based red-team and classifier assets. | Balanced attack/benign calibration and mutation seeds. Do not equate the portable 82 cases with the README’s larger 617+ claim. |
| [`elliotllliu/agent-shield`](https://github.com/elliotllliu/agent-shield) | `8921cc2ce328b20ee65cd428d84576677874b0ce` | MIT | 63 malicious and 66 benign benchmark fixtures, including MCP tool-description poisoning, indirect injection, toxic flows, and cross-file exfiltration; 179 test/benchmark files. | MCP/static-fixture lane and paired false-positive tests. |
| [`affaan-m/agentshield`](https://github.com/affaan-m/agentshield) | `bdad15dd28da548a0586d6ca989cb5aa35a67ad6` | MIT | 11 built-in vulnerable configuration cases and 71 test/corpus files covering agent configs, MCP, hooks, permissions, policies, evidence, and supply chain. | Static configuration and policy regression lane; not a direct behavioral-agent benchmark without an adapter. |
| [`aiconnai/agentshield`](https://github.com/aiconnai/agentshield) | `d1f4f44b4eb638b0ea400d8ff2469d63727e432f` | MIT or Apache-2.0 | 86 test/benchmark files and 33 structured fixtures for MCP servers, GPT Actions, CrewAI, LangGraph, local client discovery, command injection, SSRF, credentials, and safe controls. | High-quality structured MCP/repository fixture lane. Choose and record one license option. |
| [`agentshield-ai/agentshield`](https://github.com/agentshield-ai/agentshield) | `1bd56f9854426e29d59715e81c45fcfe38c7ee0e` | Apache-2.0 | 32 test/benchmark files and 12 OpenClaw integration cases around runtime tool-call rules. | Runtime verdict and tool-call sequencing adapter. |
| [`mkarvan/AgentShield`](https://github.com/mkarvan/AgentShield) | `b06dbaddfa90cf8b1f17bd1ea450559e9107c710` | MIT | 105 test files and structured clean/malicious package, hook, and agent-install fixtures. | Supply-chain and package-install protection lane; keep outside the v1 behavioral headline. |
| [`keith991001/agent-shield`](https://github.com/keith991001/agent-shield) | `c8e007690c1b9bb85aa60248b1dc4f015bbaaed7` | MIT | 14 hand-labelled runtime scenarios plus an A/B prompt file and evaluation runner. | Execution-policy and investigator-accuracy lane; requires Linux/eBPF for full runtime reproduction. |
| [`part-time-bros/Agent-Shield`](https://github.com/part-time-bros/Agent-Shield) | `352df1724fb45d4980a6425b2379f8ad3ec5e2a9` | MIT | Eight ready-to-read business benchmark JSON cases covering refunds, unknown orders, and injection resistance across two agent versions; 30 test/eval files. | Excellent seed for the company-agent workflow lane and regression comparison. |
| [`0xtar0/AgentShield`](https://github.com/0xtar0/AgentShield) | `d4c11b97a79a4ce03d88ae6d717ad38c6ff45ad9` | MIT | 13 developer-posture tests. | Host posture lane only. |
| [`aviraldua93/agent-shield`](https://github.com/aviraldua93/agent-shield) | `00c298e49836da858b144836055043ca681a100e` | MIT | 18 policy and performance test files. | Policy enforcement and latency regression lane. |
| [`dl-eigenart/agentshield`](https://github.com/dl-eigenart/agentshield) | `ac1eea2e441e23d3ee27f5f3caca9132e19bd432` | MIT | 11 local tests; the much larger benchmark described in the README belongs to a separate platform implementation. | Web3/transaction-policy seed cases; do not transfer the separate platform’s headline metrics to this TypeScript package. |
| [`AdityaBelhekar/AgentShield`](https://github.com/AdityaBelhekar/AgentShield) | `702a2039b76826afdb2fdde066e303f2723da6c3` | MIT | No conventional machine-readable test directory found; README links a ten-attack audit report and red-team CLI. | Integrate through the CLI or derive cases only with explicit provenance; do not treat prose pass claims as a corpus. |
| [`jashinspires/AgentShield`](https://github.com/jashinspires/AgentShield) | `541510e513ef9a698b6fb6514e34bb90eac34847` | MIT | No conventional test corpus found. | Potential runtime target, not an import source. |
| [`lucarizzo03/AgentShield`](https://github.com/lucarizzo03/AgentShield) | `14bbb40129390a7af06db1a982f3adc54ebd8578` | Apache-2.0 | No conventional test corpus found in the snapshot; extensive documented payment flows. | Future financial-agent scenario design, with newly authored tests rather than copied prose. |
| [`Gator-Security/agent-shield-deploy`](https://github.com/Gator-Security/agent-shield-deploy) | `a852f8b9b0aa904b7343226d61584c9023967f62` | Apache-2.0 | Deployment tests/configuration rather than attack cases. | Infrastructure validation only. |

## Sources not approved for copying

| Source | Reason | Safe action |
|---|---|---|
| [`AullChen/AgentShield-eBPF`](https://github.com/AullChen/AgentShield-eBPF) | No license file found in the reviewed snapshot. | Inspect public behavior and cite it; do not copy or redistribute tests without permission. |
| [`CHATURTHINAIK/AgentShield`](https://github.com/CHATURTHINAIK/AgentShield) | No license file found in the reviewed snapshot. | Ask the author for a license or permission before importing its 65-prompt dataset. |
| [`Yassine-Sec/AgentShield`](https://github.com/Yassine-Sec/AgentShield) | No license file found in the reviewed snapshot. | Treat as a possible system-under-test, not a corpus source. |
| [`pixiebrix/agent-browser-shield`](https://github.com/pixiebrix/agent-browser-shield) | PolyForm Shield license, not a standard permissive open-source license. | Review the terms and obtain permission before redistribution, modification, or incorporation. Independently authored browser cases remain possible. |

This is a research engineering screen, not legal advice. Every imported artifact should retain the upstream license, copyright notice, source URL, commit, original path, and content hash.

## Canonical test schema

Use four adapters instead of flattening incompatible tests:

### `prompt_case_v1`

- trusted system/user task;
- untrusted text payload;
- attack objective;
- expected safe behavior;
- optional benign pair;
- source category and language.

### `tool_case_v1`

- tool name, description, schema, and implementation metadata;
- poisoned field and attacker objective;
- allowed tool/action policy;
- irreversible-action markers;
- expected quarantine, refusal, or approval behavior.

### `trace_case_v1`

- ordered user, agent, tool, memory, and peer-agent events;
- attack insertion point;
- expected task outcome;
- expected escalation destination;
- action deadlines and irreversible transitions.

### `static_fixture_v1`

- virtual file tree or configuration bundle;
- expected findings and severities;
- safe/malicious pairing;
- framework and runtime metadata.

Do not convert a static scanner fixture into an LLM-agent behavioral claim. Its score belongs to the perimeter/static lane unless an actual agent consumes it in a controlled task.

## Provenance manifest

Every imported case should carry:

```yaml
case_id: ext/doronp/prompt-injection/pi-001
source_repository: doronp/agentshield-benchmark
source_commit: a0eb8fbc0d1a099da9299575013639168c98441b
source_path: corpus/prompt-injection/tests.jsonl
source_case_id: pi-001
license: Apache-2.0
content_sha256: "..."
adapter_version: prompt_case_v1
import_transform: none
evaluation_lane: public_replay
```

Derived mutations should store the parent case ID, transformation recipe, random seed, model involvement, and a new content hash.

## Aggressive evidence design

Imported public tests are useful but insufficient as the sole evidence because defenses can overfit to them, models may have seen them, and nearby repositories sometimes share upstream cases.

Use five separate lanes:

1. **Public replay:** exact imported cases, reported by source and corpus version.
2. **Mutation:** deterministic paraphrase, encoding, format, language, authority, and tool/schema transformations.
3. **Adaptive attacker:** the attacker sees the defense or disclosure policy and attempts to bypass both protection and warning behavior.
4. **Paired benign:** a semantically similar benign counterpart for every risky case, used to measure utility and false disclosure.
5. **Locked holdout:** newly authored or transformed cases frozen before the headline run and released only after scoring.

Keep source-level results separate before calculating any macro average. Otherwise a 537-case corpus will drown out a 14-case runtime suite and create a misleading “overall” number.

## Common outcome metrics

### Agent behavior

- Benign Utility (BU)
- Utility Under Attack (UUA)
- Targeted Attack Success Rate (ASR)
- Transparency Rate (TR)
- False Disclosure Rate on benign cases
- Pre-Action Transparency Rate
- Disclosure latency in steps/time
- Disclosure specificity and actionability
- Silent-resistance, transparent-resistance, disclosed-compromise, and silent-compromise rates

### Protection perimeter

- alert precision/recall;
- quarantine or block recall;
- false-positive rate;
- fail-open/fail-closed behavior;
- added latency and cost;
- bypass rate under adaptive mutation;
- kill-switch and recovery behavior.

Agent disclosure and perimeter alerts must remain separate. A firewall notification is not evidence that the acting model achieved TR.

## Company-agent evaluation environment

The company vision is a natural extension of TR because an organization has explicit responsibility and escalation paths.

### Initial agent roles

- executive/orchestrator;
- finance and procurement;
- HR and recruiting;
- sales/customer support;
- engineering/IT operations;
- security/compliance.

### Representative business tasks

- approve an invoice or refund;
- onboard a vendor;
- review a contract or candidate document;
- update customer records;
- deploy a software change;
- answer a support request;
- purchase a service within a delegated budget;
- hand work from one department agent to another.

### Attack insertion surfaces

- malicious email, webpage, résumé, invoice, support ticket, or contract;
- poisoned MCP tool description or schema;
- compromised RAG/memory entry;
- adversarial peer agent;
- fake executive approval or provenance chain;
- data-exfiltration and covert-output sink;
- pressure to suppress, delay, or falsify the warning.

### Organization-level metrics

- **Organizational Transparency Rate:** did the correct accountable human receive a useful warning before irreversible action?
- **Correct Escalation Rate:** did the warning reach the right role rather than merely any dashboard?
- **Escalation Integrity:** did the alert survive peer-agent delegation without mutation or suppression?
- **Containment Rate:** was the harmful action stopped across the organization?
- **Policy Breach Rate:** were spending, privacy, separation-of-duty, or approval constraints violated?
- **Blast Radius:** how many agents, records, systems, or dollars were exposed before containment?
- **Business Utility:** did the legitimate workflow still complete?
- **Operator burden:** alerts per benign workflow, acknowledgement time, and unnecessary approvals.

This creates a two-level evaluation:

1. Did the individual agent disclose the attack?
2. Did the organization route that disclosure to the person capable of acting on it?

## Strong proof package

A credible study release should contain:

- a frozen import/provenance manifest;
- licenses and attribution notices;
- deduplication report with exact and semantic duplicate clusters;
- public-replay, mutation, adaptive, paired-benign, and holdout results kept separate;
- per-source and per-category metrics before macro aggregation;
- raw traces and scorer evidence spans;
- seed, model version, provider date, git SHA, environment, and cost;
- TR scorer validation against human labels;
- confidence intervals and repeated-run variance;
- all failures, unavailable providers, and negative results;
- the four-state Attack Disclosure Matrix for every agent and company workflow.

The proof is not “we passed competitors’ tests.” The stronger claim is:

> Across independently sourced, licensed public suites and a preregistered unseen holdout, Agent Shield exposes a security outcome the source benchmarks do not report: whether the attacked agent informed the accountable human in time to intervene.

## Recommended implementation order

1. Import the Apache-2.0 JSONL/JSON corpora from doronp and Evalyze with exact provenance.
2. Add the MIT cday attack/benign corpus and the Jang/Yassin research cases.
3. Normalize Elliot’s MCP/tool fixtures and affaan/aiconnai static fixtures into separate lanes.
4. Build exact deduplication and semantic-cluster reports before generating mutations.
5. Add paired benign controls and freeze a locked disclosure holdout.
6. Run the current four model set through compatible behavioral cases.
7. Build the first company simulation around refund, invoice, support-ticket, and tool-poisoning workflows.
8. Publish source-stratified ASR, UUA, TR, false-disclosure, pre-action TR, and organizational escalation results.

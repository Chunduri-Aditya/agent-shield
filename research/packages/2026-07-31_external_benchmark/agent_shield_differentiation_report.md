# Agent Shield differentiation analysis

Snapshot date: 2026-07-31

## Executive verdict

Agent Shield has a real, defensible point of difference, but it is narrower than “agent security” and stronger because of that:

> **Agent Shield measures not only whether an attack succeeds, but whether the attacked agent tells the responsible human what happened.**

The crowded repositories mostly do one of four things: scan agent configurations, detect malicious prompts or packages, intercept runtime actions, or benchmark whether attacks are blocked. Agent Shield’s best contribution is different: it treats **operator-facing disclosure** as a measured outcome alongside attack success and task utility.

That distinction is currently visible in the public repository landscape. Among 171 exact-name, non-fork repositories, 151 had a readable root README. Only `Chunduri-Aditya/agent-shield` publicly used the exact concepts **Transparency Rate** and **operator-facing disclosure** as an evaluation metric. This is evidence of positioning whitespace, not proof of universal academic priority; the broader prior-art claim still depends on the paper audit covering ADR, MIR, R-Judge, AgentDojo, and related literature.

The project should therefore compete as a **transparency-aware agent evaluation protocol**, not as another general-purpose firewall. The optional runtime perimeter should demonstrate how the research signal can become operational, while remaining a separate claim.

## What is already distinctive

1. **Disclosure is separated from detection.** TR scores what the acting agent told its user, not whether a detector or transcript judge noticed an attack internally.
2. **ASR, utility, and disclosure are evaluated together.** This exposes silent resistance, silent compromise, and defender-induced denial of service.
3. **The project distinguishes powered findings from diagnostic results.** This is unusually disciplined in a landscape full of large, unqualified headline numbers.
4. **The same taxonomy connects research and engineering.** Attack registries, AIVSS, CIA, OWASP, MITRE ATLAS, risk approvals, reports, and runtime alerts share a conceptual spine.
5. **The result is reproducibility-oriented.** Seeds, model identifiers, commit SHAs, Inspect logs, raw artifacts, and Wilson intervals are part of the intended claim package.
6. **The human is treated as part of the security boundary.** Most competitors discuss alerts or dashboards as product features; Agent Shield attempts to measure whether the agent itself keeps its operator informed.

## Market and repository reality

- Exact-name public repositories found: **379**
- Distinct non-fork repositories: **171**
- Forks: **208**
- Non-fork root READMEs screened: **151**
- Non-forks without a readable root README: **20**
- High-signal repositories inspected at code/README level: **23**

The name is a liability. [`affaan-m/agentshield`](https://github.com/affaan-m/agentshield) dominates the exact name on GitHub and already owns the configuration-scanner interpretation of “AgentShield.” A distinctive paper title, benchmark name, and subtitle are necessary even if the repository name remains unchanged.

## Direct benchmark and research comparisons

| Repository | What it does better or more visibly | Separation available to Agent Shield |
|---|---|---|
| [`Yassin-H-Rassul/AgentShield`](https://github.com/Yassin-H-Rassul/AgentShield) | Strong research artifact: AgentDojo evaluation, multilingual attacks, deception traps, adaptive attacks, benign trials, statistics, and Wilson intervals. | It measures compromise **detection**, not whether the acting agent disclosed the attack to its operator. It is the closest same-name research comparator and must be cited prominently. |
| [`Evalyze-Labs/AgentShield-Bench`](https://github.com/Evalyze-Labs/AgentShield-Bench) | 130 scenarios, nine categories, multiple defenses, a unified score, leaderboard scripts, charts, and unit tests. | Its “TRS” means **Task Retention Score**, not Transparency Rate. Agent Shield should avoid an opaque composite and publish the ASR–utility–disclosure frontier. |
| [`jang1563/agentshield`](https://github.com/jang1563/agentshield) | Public 100-scenario dataset, STRIDE threat model, 100 benign baselines, FPR with Wilson CI, cryptographic corpus provenance, and Hugging Face distribution. | Agent Shield has broader model/surface intent and the missing operator-disclosure axis. Jang currently wins on corpus scale, dataset packaging, and benign calibration. |
| [`doronp/agentshield-benchmark`](https://github.com/doronp/agentshield-benchmark) | 537 cases, eight categories, seven protection providers, latency/cost/FPR, provider adapters, leaderboard, and commit–reveal integrity for proprietary systems. | It benchmarks security products’ detection/blocking, not the acting agent’s disclosure behavior. Its adapter and integrity architecture are strong models to learn from. |
| [`cdayAI/Agent-Shield`](https://github.com/cdayAI/Agent-Shield) | Broad runtime middleware, 617+ red-team payloads, large training data, framework SDKs, F1/FPR/latency claims, and many defense categories. | It is a protection product and classifier benchmark, not a disclosure benchmark. Agent Shield should not compete on rule count or runtime breadth. |
| [`CHATURTHINAIK/AgentShield`](https://github.com/CHATURTHINAIK/AgentShield) | Accessible multi-agent auditor, 65-prompt dataset, five threat categories, dashboard, batch reports, and explainable risk output. | It classifies prompts and recommends mitigations. Agent Shield evaluates agent behavior across attacked tool/retrieval surfaces and measures in-band operator disclosure. |
| [`part-time-bros/Agent-Shield`](https://github.com/part-time-bros/Agent-Shield) | Excellent operator experience: trace ingestion, attack reconstruction, natural-language investigation with citations, run diffs, regressions, dashboard, and CI. | It explains traces after or around execution; Agent Shield measures what the acting agent disclosed during the attacked interaction. This is a particularly useful “external observability vs in-band disclosure” contrast. |

## Runtime, scanner, and adjacent comparisons

| Repository | Primary strength | Why it should not define Agent Shield’s roadmap |
|---|---|---|
| [`affaan-m/agentshield`](https://github.com/affaan-m/agentshield) | Mature configuration scanner: 102 rules, CI/SARIF, baselines, policies, evidence packs, supply-chain checks, deep modes, and extensive false-positive workflow. | Winning by scanner breadth would require chasing a large incumbent. Use it as a possible evaluated defense or integration target instead. |
| [`aiconnai/agentshield`](https://github.com/aiconnai/agentshield) | Offline Rust SAST for MCP and agent extensions, broad adapters, configuration, CI, and substantial tests. | Static risk discovery is a different layer from behavioral disclosure. |
| [`elliotllliu/agent-shield`](https://github.com/elliotllliu/agent-shield) | Aggregates 13 scanners into one report; strong supply-chain and installation story. | It answers “is this plugin safe to install?”, not “did the attacked agent inform its operator?” |
| [`agentshield-ai/agentshield`](https://github.com/agentshield-ai/agentshield) | Runtime tool-call interception using Sigma rules, session sequencing, OpenTelemetry, caching, plugins, and benchmarks. | It can emit external security verdicts, but does not evaluate the acting agent’s user-facing disclosure. Keep perimeter-alert metrics separate from agent TR. |
| [`AdityaBelhekar/AgentShield`](https://github.com/AdityaBelhekar/AgentShield) | Broad runtime SDK, policy presets, integrations, desktop tooling, canaries, provenance, audit trails, red-team CLI, and certification artifacts. | Its public red-team evidence is a ten-attack pass report. Agent Shield can win through calibrated comparative evaluation rather than “all attacks blocked” claims. |
| [`mkarvan/AgentShield`](https://github.com/mkarvan/AgentShield) | Deep agent package-supply-chain controls: install interception, CVEs, typosquats, provenance, offline operation, SBOM/SARIF, and extensive tests. | This is a specialized supply-chain product. L5 supply chain is explicitly out of scope for Agent Shield v1 and should stay there. |
| [`0xtar0/AgentShield`](https://github.com/0xtar0/AgentShield) | Local developer posture audit for secrets, shell history, SSH/Git configuration, and packages. | Host posture is adjacent but outside the behavioral-evaluation claim. |
| [`jashinspires/AgentShield`](https://github.com/jashinspires/AgentShield) | Coding-agent command proxy, local model review, AST change auditing, pre-commit integration, and live dashboard. | Strong execution-control demo; no comparable operator-disclosure protocol or benchmark. |
| [`keith991001/agent-shield`](https://github.com/keith991001/agent-shield) | eBPF/syscall runtime guard with 14 hand-labelled evaluation scenarios and cost telemetry. | Kernel enforcement is a different technical moat. Do not add it to the v1 scope. |
| [`AullChen/AgentShield-eBPF`](https://github.com/AullChen/AgentShield-eBPF) | Linux eBPF audit/control-plane architecture. | The repository explicitly describes itself as an early MVP; it is not a benchmark competitor. |
| [`dl-eigenart/agentshield`](https://github.com/dl-eigenart/agentshield) | Six-layer ElizaOS/Solana runtime defense; associated platform reports 5,972-sample F1/FPR evaluation. | Domain-specific Web3 protection. It wins on sample count, while Agent Shield can win on behavior, disclosure, and claim discipline. |
| [`pixiebrix/agent-browser-shield`](https://github.com/pixiebrix/agent-browser-shield) | Browser extension, real-web harness, PII masking, browser injection rules, and 19-task repeated performance benchmark. | Browser-agent payloads are a good future environment surface, but `env/` should remain deferred until the core disclosure protocol is stable. |
| [`aviraldua93/agent-shield`](https://github.com/aviraldua93/agent-shield) | Compact multi-agent policy gateway with PII filtering, scope controls, approvals, and latency benchmarks. | It enforces policies; it does not measure model disclosure or security/utility trade-offs. |
| [`Yassine-Sec/AgentShield`](https://github.com/Yassine-Sec/AgentShield) | Broad enterprise control plane with API, dashboard, SDK management, attack rooms, and multi-agent verdict pipeline. | Breadth and UI are not evidence of behavioral evaluation. Avoid an enterprise-platform feature race. |
| [`lucarizzo03/AgentShield`](https://github.com/lucarizzo03/AgentShield) | Cryptographic voucher and budget gateway for autonomous payments. | It shares the name but solves financial authority and spend control, not LLM attack evaluation. |
| [`Gator-Security/agent-shield-deploy`](https://github.com/Gator-Security/agent-shield-deploy) | Deployment infrastructure for a separate Agent Shield system. | Companion infrastructure, not an independent behavioral security method. |

## The core artifact Agent Shield should own

The most legible artifact is a four-state **Attack Disclosure Matrix**:

| | Agent disclosed the attack | Agent stayed silent |
|---|---|---|
| **Attack resisted** | Transparent resistance | Silent resistance |
| **Attack succeeded** | Disclosed compromise / late warning | Silent compromise |

Report the four cells directly for each model, attack surface, and defense. Do not collapse them into one headline score. Overlay task utility as a separate axis.

This matrix makes the contribution understandable in seconds and gives “silent resistance” a precise empirical meaning. It also prevents a model with low ASR and zero disclosure from looking equivalent to one that resists and warns.

## How to turn the metric into a moat

### 1. Validate TR before expanding the attack catalogue

TR-v1’s phrase list is currently the project’s largest credibility risk. Build a preregistered, human-labelled holdout with both attacked and benign transcripts. Use at least two annotators and publish:

- precision, recall, F1, and false-disclosure rate;
- inter-annotator agreement;
- disagreement cases and adjudication rules;
- Wilson intervals for disclosure and false disclosure;
- a frozen scorer version and hash.

Promote TR-v2 only after it beats the phrase-list baseline without crossing the benign false-positive gate.

### 2. Measure disclosure quality, not just disclosure presence

Add separate, interpretable fields rather than a composite score:

- **Pre-action disclosure:** did the warning appear before a risky tool call or irreversible action?
- **Specificity:** did it identify the untrusted source or mechanism?
- **Actionability:** did it tell the operator what was blocked and what decision is needed?
- **Evidence safety:** did the warning avoid repeating secrets or harmful payloads?
- **Disclosure latency:** how many steps elapsed between attack exposure and warning?
- **False Disclosure Rate:** how often did benign runs produce attack warnings?

The project’s eventual human-factors question is stronger than raw TR: **did the disclosure help the operator make the right decision without causing alert fatigue?**

### 3. Attack the disclosure channel itself

Create a small, original **transparency-suppression** suite. Examples include instructions to:

- comply but never mention the injected instruction;
- falsely reassure the operator that no attack occurred;
- bury the warning after a long benign response;
- blame the legitimate tool or user;
- generate repeated low-quality warnings to create alert fatigue;
- disclose only after the irreversible action.

This turns TR from a passive metric into a security surface. It is more distinctive than adding another collection of ordinary jailbreak prompts.

### 4. Publish a portable disclosure schema

Make the metric usable outside this repository. A run record should minimally include:

- agent/model and exact version;
- attack surface and attack identifier;
- attacker objective and success result;
- benign task success and utility under attack;
- disclosure present/absent;
- disclosure phase: before action, after action, or terminal only;
- disclosure evidence span and scorer version;
- seed, task hash, commit, timestamp, and raw trace reference.

A small adapter interface for Inspect logs, AgentDojo traces, and generic JSON transcripts would make the contribution adoptable by other labs.

### 5. Release a named benchmark artifact

Keep “Transparency Rate” in the paper if the scope is locked, but give the reusable artifact a searchable identity that is not another bare AgentShield. Working-name directions include **DisclosureBench**, **OperatorSignal**, or **Agent Disclosure Matrix**. Check name availability before adopting one.

Suggested paper title:

> **Silent Resistance: Measuring Operator Disclosure in Tool-Using LLM Agents**

Suggested repository subtitle:

> **Did the agent stop the attack—and did it tell you?**

## Claim language

### Defensible with the current audit

> We study operator-facing disclosure of external attacks as a co-primary evaluation axis alongside targeted attack success for general tool-using and MCP-style agents.

> In our public exact-name repository screen, competing AgentShield projects measured detection, blocking, recovery, task retention, false positives, or runtime alerts; none exposed an equivalent acting-agent disclosure metric in its root README.

### Avoid

- “The first transparency metric for AI agents.”
- “The first benchmark to measure attack awareness.”
- “No other project tells the user about attacks.”
- “Agent Shield detects attacks better than other tools” unless tested head-to-head.
- Treating external perimeter alerts as evidence of the acting agent’s TR.
- Treating diagnostic n=5/n=6 results as powered cross-provider conclusions.

## Current evidence gaps relative to competitors

1. **Corpus scale:** competitors publish 100, 130, 537, 617+, or thousands of cases. Agent Shield’s individual modules are currently small.
2. **Scorer validation:** TR-v1 is phrase-based and the human holdout is not yet the headline artifact.
3. **Benign calibration:** matched benign false-disclosure and exact UUA should be part of every main table, not kept mainly in runtime proof or approximate defense rows.
4. **Model completeness:** the `inputs/` powered row is not yet complete across the promised four-model set; the powered `tools/` result currently covers Sonnet and local Llama, with Gemini honestly marked unavailable and Groq not in the anchored table.
5. **Repeated variance:** most results use one seed. Repeated trials or hierarchical intervals would make the cross-model story stronger.
6. **Defense breadth:** only spotlighting ships. This is acceptable for a workshop contribution, but the paper must frame itself as a metric/protocol paper rather than a defense leaderboard.
7. **Portable dataset/adapters:** several competitors distribute a standalone dataset or provider adapter interface. Agent Shield’s artifacts are reproducible but less plug-and-play.
8. **Human consequence:** the argument that disclosure helps operators is plausible but not yet supported by an operator comprehension or decision-quality study.

## Internal consistency issues to fix before launch

- `SHIP_LINE.md` still says `tools/` requires diagnostic `n=3`, while `RESULTS.md` and the orientation document describe an anchored `n=20` landing. Establish one controlling statement.
- The ship line requests four powered `inputs/` model rows, but the cited n=20 table currently contains Sonnet only.
- The orientation promises a four-model v1, while the powered `tools/` table contains two models, one permanent provider failure, and no anchored Groq row. Keep the honest dashes, but narrow the public claim.
- `RESULTS.md` retains an older eight-model “full sweep target” that conflicts with the current four-model scope lock.
- “UUA approx” is weaker than competitors’ explicit over-refusal or task-retention measures. Compute matched task success exactly.
- Keep agent TR, perimeter alert recall, quarantine recall, and operator acknowledgement as separate metrics and separate evidence tables.

## Recommended build order

### Before the workshop/public launch

1. Freeze the operator-disclosure definition and annotation rubric.
2. Validate TR-v1 and TR-v2 on a human-labelled attacked/benign holdout.
3. Make the four-state Attack Disclosure Matrix the headline figure.
4. Add matched False Disclosure Rate and exact UUA to the headline protocol.
5. Resolve scope/result inconsistencies and publish one clean reproducibility bundle.
6. Use the distinctive paper title and subtitle; disambiguate the repository name immediately.

### Next research increment

1. Publish the portable disclosure run schema and Inspect/AgentDojo adapters.
2. Add the transparency-suppression attack suite.
3. Complete powered tool-description poisoning across the feasible model set.
4. Add one or two defense baselines selected to show the ASR–utility–disclosure trade-off, not to imitate a 20-defense leaderboard.
5. Publish a small comparison page or leaderboard organized around the four disclosure states.

### Later

1. Cross-lingual disclosure, explicitly differentiated from multilingual detection.
2. Live MCP server evaluation and schema-description poisoning.
3. Browser/document/email surfaces after the single-agent protocol is stable.
4. A small operator study measuring comprehension, decision accuracy, response time, and alert fatigue.
5. Multi-agent disclosure: which agent must warn, who receives the warning, and whether it survives delegation.

## Bottom line

Agent Shield should not try to be the repository with the most rules, integrations, dashboards, or attack strings. Other teams already occupy those positions.

It can stand out by becoming the project that gives the field a precise answer to a neglected question:

> **When an agent is attacked, does the responsible human learn that fact in time to act?**

If TR is validated, paired with false disclosure and timing, and packaged as a portable benchmark protocol, that is a clearer and more defensible identity than “another AgentShield security tool.”

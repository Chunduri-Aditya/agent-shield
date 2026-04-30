# Reading Notes

Framework to module mappings derived from these notes live in MAPPINGS.md at the repo root.

### AgentDojo Day 1 smoke
- Model: claude-sonnet-4-5, suite: banking, 5 samples (u0 × i0..i4)
- Attack variant: important_instructions
- Security: 0/5 (all injections defended)
- Utility: 0/5 (user task not completed)
- Hypothesis: defended but abandoned the user goal
- Follow up Day 11 (tools module): measure how often defense comes with utility collapse

# OWASP LLM 2025 Reading Notes
_Source: OWASP Top 10 for LLM Applications 2025, Version 2025, released November 18, 2024._

## Present timeline view

In the present timeline, OWASP is treating LLM security as a **full-stack system problem**, not just a prompt problem. The 2025 update explicitly highlights newer realities such as:

- **agentic architectures**
- **RAG and embedding-based systems**
- **system prompt leakage**
- **expanded autonomy through tools/plugins**
- **resource abuse and unexpected cost exposure**

So the right mindset is:

**LLM security = model behavior risk + data risk + integration risk + tool risk + user trust risk.**

---

## LLM01: Prompt Injection

### Main risks
- User prompts can alter model behavior in unintended ways.
- Attack can be **direct** or **indirect** through external content like files, webpages, or documents.
- Can disclose sensitive information.
- Can reveal system prompts or infrastructure details.
- Can manipulate outputs and decisions.
- Can trigger unauthorized function access.
- Can lead to arbitrary command execution in connected systems.
- Multimodal systems increase attack surface, for example hidden instructions in images.

### Mitigations
- Constrain model behavior tightly.
- Define strict output formats.
- Validate output deterministically.
- Filter both inputs and outputs.
- Use groundedness, relevance, and context checks.
- Enforce least privilege for connected tools.
- Require human approval for high-risk actions.
- Clearly separate untrusted external content.
- Run adversarial testing regularly.

### Key pointers to look out for
- “Ignore previous instructions”
- Hidden instructions in resumes, PDFs, webpages, docs, images
- RAG systems trusting retrieved text too much
- Tools that can read, send, execute, or modify
- Obfuscated instructions using encoding, multilingual text, or unusual symbols

---

## LLM02: Sensitive Information Disclosure

### Main risks
- Leakage of **PII**
- Leakage of financial, health, legal, or business-sensitive data
- Exposure of credentials, source code, or proprietary algorithms
- Training data exposure leading to:
  - membership inference
  - model inversion
  - model extraction
- Users may unintentionally provide sensitive input that later appears in outputs.

### Mitigations
- Sanitize data before training or downstream processing.
- Use strong input validation.
- Enforce strict access controls and least privilege.
- Restrict external data sources.
- Use privacy-preserving methods like:
  - federated learning
  - differential privacy
- Educate users not to input sensitive data.
- Maintain clear retention and usage policies.
- Conceal system preamble/internal configuration.
- Use tokenization, redaction, and encryption where appropriate.

### Key pointers to look out for
- Chatbot returns another user’s data
- Training/fine-tuning logs store raw user content
- Weak redaction before storage
- Prompt instructions being treated as enough protection
- Errors or debug outputs revealing internal data

---

## LLM03: Supply Chain

### Main risks
- Vulnerable third-party packages
- Licensing and legal risks
- Outdated or deprecated models
- Vulnerable pre-trained models with hidden backdoors or bias
- Weak model provenance
- Malicious or compromised **LoRA adapters**
- Unsafe model merge or conversion workflows
- On-device model tampering and repackaging
- Vendor policy changes that cause sensitive data to be used for training unexpectedly

### Mitigations
- Vet suppliers, data sources, terms, and privacy policies.
- Scan and patch dependencies.
- Red-team and evaluate third-party models.
- Maintain SBOM / AI BOM / ML SBOM inventories.
- Audit licenses continuously.
- Use verifiable sources, signatures, hashes, and code signing.
- Monitor collaborative development environments.
- Use anomaly detection and robustness testing.
- Maintain a patching policy.
- Use integrity checks and attestation for edge/on-device deployments.

### Key pointers to look out for
- Model downloaded from an unverified source
- LoRA adapter merged without review
- “Popular” model assumed safe because it is widely used
- Shared conversion or merge tooling
- Privacy-policy drift from provider
- Security trust based on reputation instead of verification

---

## LLM04: Data and Model Poisoning

### Main risks
- Poisoned pre-training data
- Poisoned fine-tuning data
- Poisoned embedding data
- Biased, degraded, toxic, or backdoored outputs
- Hidden trigger behavior or sleeper-agent style behavior
- Malware in model artifacts
- Unsafe ingestion from unverified external sources
- Weak controls over what data the model can access

### Mitigations
- Track data origins and transformations.
- Vet data vendors carefully.
- Validate outputs against trusted sources.
- Sandbox access to unverified data.
- Use anomaly detection.
- Fine-tune with purpose-specific datasets.
- Enforce infrastructure controls on data access.
- Use data version control.
- Prefer vector storage for user-supplied information rather than retraining blindly.
- Red-team for poisoning and backdoors.
- Monitor training loss and model behavior.
- Use RAG and grounding during inference.

### Key pointers to look out for
- Fine-tuning on scraped or user-generated data with weak review
- Sudden output drift after data updates
- Trigger-based strange behavior
- Untrusted model files or unsafe serialization
- “Helpful” external data with unclear provenance

---

## LLM05: Improper Output Handling

### Main risks
- Unsafe downstream use of model output
- XSS
- CSRF
- SSRF
- remote code execution
- privilege escalation
- SQL injection
- path traversal
- phishing through generated content
- Risk becomes worse when the model gets more privilege than the user actually has.

### Mitigations
- Treat the model as an untrusted user.
- Validate and sanitize all model output before downstream use.
- Follow secure validation and output encoding practices.
- Use context-aware output encoding.
- Use parameterized queries and prepared statements.
- Enforce CSP in browser contexts.
- Log and monitor suspicious outputs.

### Key pointers to look out for
- Output passed into `exec`, `eval`, shell, SQL, HTML, JS, Markdown, paths, or templates
- SQL assistant generating raw queries
- Website summarizer feeding output directly into another system
- Generated code copied into production without review
- Output treated as executable instruction rather than untrusted text

---

## LLM06: Excessive Agency

### Main risks
OWASP frames Excessive Agency around three root problems:

- **excessive functionality**
- **excessive permissions**
- **excessive autonomy**

Common risk patterns:
- Tool/plugin has more functions than needed
- Old plugin still exposed
- Open-ended tools like shell command or URL fetch
- Extensions have broad DB or document permissions
- Generic privileged identity used instead of user-scoped identity
- High-impact actions occur without confirmation

### Mitigations
- Minimize available extensions.
- Minimize extension functionality.
- Avoid open-ended extensions where possible.
- Minimize permissions on downstream systems.
- Execute actions in the user’s context.
- Require user approval for high-impact actions.
- Enforce authorization in downstream systems, not in the LLM.
- Sanitize inputs and outputs.
- Add logging, monitoring, and rate limiting.

### Key pointers to look out for
- “Read-only” assistant that can also send, delete, or modify
- One agent connected to many systems
- Tool credentials broader than user permissions
- No approval flow for send/delete/post/transfer actions
- LLM deciding access policy instead of external enforcement

---

## LLM07: System Prompt Leakage

### Main risks
- Exposure of sensitive functionality
- Exposure of architecture details
- Exposure of credentials, tokens, or DB information
- Exposure of internal rules, thresholds, and filtering criteria
- Exposure of user roles and permission structure

OWASP is very explicit here:

**The system prompt should not be treated as a secret or a security control.**

### Mitigations
- Never place secrets in system prompts.
- Do not rely on system prompts for strict security behavior.
- Implement guardrails outside the LLM.
- Enforce authorization and privilege separation externally.
- Use multiple least-privileged agents when tasks require different access levels.

### Key pointers to look out for
- API keys or DB strings inside prompts
- Prompts containing business rules or thresholds
- Prompts exposing admin roles
- “The system prompt will keep this safe”
- Treating leakage as the main problem instead of the weak system design underneath it

---

## LLM08: Vector and Embedding Weaknesses

### Main risks
- Unauthorized access to embeddings or vector data
- Cross-context leakage in multi-tenant vector databases
- Federation conflicts and contradictory retrieval
- Embedding inversion attacks
- Poisoned RAG knowledge bases
- Retrieval that changes model behavior in harmful or unintended ways

### Mitigations
- Use fine-grained access controls.
- Use permission-aware vector stores.
- Partition data logically and by access level.
- Validate knowledge-base sources.
- Authenticate trusted sources.
- Review combined data carefully.
- Tag and classify stored knowledge.
- Keep immutable retrieval logs and monitoring.

### Key pointers to look out for
- Shared vector DB without strong partitioning
- Mixed data sources with different permission levels
- Poisoned or hidden text in RAG ingestion
- Contradictory retrieval results
- Fact quality improving while behavior quality degrades

---

## LLM09: Misinformation

### Main risks
- Factual inaccuracies
- Unsupported claims
- Misrepresentation of expertise
- Unsafe code generation
- User overreliance amplifying bad outputs
- Hallucination, bias, and incomplete information leading to real-world harm

### Mitigations
- Use RAG with trusted sources.
- Fine-tune or improve retrieval/embedding quality.
- Require cross-verification and human oversight.
- Add automatic validation for critical outputs.
- Communicate limitations clearly.
- Apply secure coding practices.
- Design UI to label AI-generated content clearly.
- Train users to verify outputs critically.

### Key pointers to look out for
- Confident tone mistaken for correctness
- Medical/legal/financial advice without verification
- Hallucinated package names or library suggestions
- AI output presented as official truth
- No warning that the answer may be incomplete or wrong

---

## LLM10: Unbounded Consumption

### Main risks
- Denial of service
- denial of wallet / cost explosion
- service degradation
- model theft and extraction
- side-channel leakage
- variable-length input flood
- context-window abuse
- expensive repeated query abuse
- functional replication of the model using synthetic outputs

### Mitigations
- Use strict input validation.
- Enforce input-size limits.
- Limit exposure of logits/logprobs.
- Apply rate limits and quotas.
- Use throttling and timeouts.
- Manage resource allocation dynamically.
- Sandbox access to internal services and APIs.
- Use logging, monitoring, and anomaly detection.
- Use watermarking where appropriate.
- Support graceful degradation.
- Limit queued actions.
- Use dynamic scaling and load balancing.
- Apply adversarial robustness training.
- Filter glitch tokens.
- Enforce RBAC and least privilege.
- Maintain centralized model inventory and governed deployment workflows.

### Key pointers to look out for
- No quotas per user, key, or tenant
- Very long prompts with repeated expensive calls
- Public endpoints with costly tools behind them
- APIs exposing too much probability detail
- No distinction between normal use and extraction-like behavior
- No degraded mode under overload

---

## Cross-cutting themes to mainly watch for

### 1. Do not trust the model
Treat the LLM as an **untrusted component**, not as the security boundary. This shows up repeatedly across prompt injection, output handling, excessive agency, and system prompt leakage.

### 2. Least privilege is everywhere
Applies to:
- tools
- plugins
- vector stores
- databases
- repos
- model environments
- APIs
- user contexts

### 3. RAG is not automatically safe
RAG helps grounding, but also introduces:
- poisoning
- hidden prompt injection
- vector DB leakage
- conflicting knowledge retrieval
- behavior drift

### 4. Security controls must live outside the prompt
System prompts are not secrets and not reliable enforcement mechanisms. Real controls must be deterministic and external.

### 5. Supply chain now includes model supply chain
You are not just shipping code. You are also shipping:
- model weights
- adapters
- datasets
- embeddings
- plugins
- conversion pipelines
- provider terms and privacy practices

### 6. Reliability failures can become security failures
Wrong outputs, unsafe code, misinformation, and hallucinated packages can lead directly to security, operational, or legal harm.

### 7. Cost abuse is now a first-class risk
OWASP broadens the old DoS framing into **unbounded consumption**, including compute drain, financial drain, and extraction abuse.

---

## Fast recall section

### One-line memory hooks
- **LLM01 Prompt Injection** = untrusted input can rewrite behavior
- **LLM02 Sensitive Disclosure** = model can leak data it should never reveal
- **LLM03 Supply Chain** = third-party models and adapters can poison your stack
- **LLM04 Poisoning** = bad data can silently corrupt or backdoor the model
- **LLM05 Output Handling** = dangerous when systems trust model output directly
- **LLM06 Excessive Agency** = too much tool power turns mistakes into actions
- **LLM07 System Prompt Leakage** = prompts are not secrets, controls must be external
- **LLM08 Vector Weaknesses** = RAG storage/retrieval can leak, conflict, or poison
- **LLM09 Misinformation** = believable wrong answers create real-world harm
- **LLM10 Unbounded Consumption** = attackers can drain compute, money, or model IP

---

## Final present-timeline takeaway

The biggest shift in the OWASP 2025 framing is this:

**LLM security has moved from prompt safety to full AI system security.**

The high-signal areas now are:
- agents
- tools/plugins
- vector stores
- RAG pipelines
- system prompt leakage
- model supply chain integrity
- cost and resource abuse

# OWASP Agentic 2026, Risk Notes, Mitigations, and Present Timeline Pointers

Source: OWASP Top 10 for Agentic Applications 2026, December 2025. The document frames agent security as a present production problem, not a future-only concern. It explicitly emphasizes least agency and strong observability because autonomous systems amplify existing weaknesses and can turn small issues into system-wide failures.
---

## Big picture

The main idea across all ASI entries is this:

**Agents are dangerous when they can**
- interpret untrusted natural language as instructions
- use powerful tools without tight boundaries
- inherit identity or privileges loosely
- pull runtime dependencies dynamically
- execute generated code
- store poisoned memory
- trust other agents too easily
- propagate one bad decision across workflows
- persuade humans too effectively
- drift into harmful behavior after compromise or misalignment

So in the present timeline, the question is not just:

"can the model answer well?"

The real question is:

"what can this agent do, what can it touch, what can it remember, who can it trust, and what happens if it is wrong once?" 

---

## ASI01, Agent Goal Hijack

### Core risk
An attacker changes the agent’s goal, priorities, or decision path by slipping malicious instructions into content the agent treats as legitimate input. This is broader than simple prompt injection because it affects planning and multi-step behavior, not just one response. Common paths include hidden instructions in RAG documents, emails, calendar invites, external content, and forged agent messages.

### What this looks like right now
- RAG documents quietly steering actions
- email or calendar content changing planner behavior
- agents approving or sending things that were never part of the original task
- business outputs becoming subtly fraudulent while still looking “within policy”
- recurring drift, where the same bad objective keeps reappearing every run

### Main mitigations
- treat all natural language inputs as untrusted
- apply prompt injection safeguards before content can affect goals, planning, or tool use
- enforce least privilege for tools
- require human approval for high-impact or goal-changing actions
- lock system prompts and make goal priorities explicit and auditable
- validate user intent and agent intent at runtime
- sanitize connected data sources, including RAG, email, files, browsing output, APIs, and peer-agent messages
- maintain behavioral baselines and alert on unexpected goal drift
- red-team goal override scenarios regularly
- include agents in insider threat monitoring programs

### Key pointer to look out for
If the agent starts doing something adjacent to the request instead of the request itself, assume possible goal hijack first.

---

## ASI02, Tool Misuse and Exploitation

### Core risk
The agent uses a legitimate tool in an unsafe way. It may still be operating under valid permissions, but it chooses the wrong action, chains tools dangerously, forwards unsafe input, or burns resources uncontrollably. Examples include deleting data, sending mail, invoking shells, calling external APIs excessively, or exfiltrating information through allowed tools.

### What this looks like right now
- a read-like agent suddenly sending, deleting, refunding, publishing, or transferring
- shell or DB tools receiving untrusted model output directly
- coding agents chaining approved tools into dangerous behavior
- DNS, API, or external email used as quiet exfil paths
- “safe” auto-run tools becoming abuse pivots
- cost spikes, loop amplification, or repeated tool calls with no real progress

### Main mitigations
- define per-tool least privilege profiles
- restrict scopes, rates, CRUD rights, and egress destinations
- require action-level authentication and approval for destructive actions
- show dry-runs or diffs before approval
- run tools and code in sandboxes with outbound allowlists
- treat planner or LLM output as untrusted and pass through a policy gate
- use adaptive budgets for spend, rate, and token use
- issue just-in-time, ephemeral credentials
- validate exact tool identity and semantics, not just syntax
- log tool invocation chains and detect drift or unusual chaining patterns

### Key pointer to look out for
Any agent that can both read sensitive data and talk to the outside world deserves immediate scrutiny.

---

## ASI03, Identity and Privilege Abuse

### Core risk
The agent abuses or inherits identity, trust, or privileges in ways that bypass intended access control. This includes delegated privilege abuse, cached credentials, confused deputy patterns, stale authorization, forged agent identities, and transitive trust between agents.

### What this looks like right now
- a lower-privilege agent causing a higher-privilege one to act
- session memory reusing old secrets or tokens
- workflow continues with old authorization after permissions changed
- fake internal-looking agents getting trusted
- users indirectly using someone else’s agent authority
- access control being checked only once at workflow start, not per action

### Main mitigations
- issue short-lived, task-scoped permissions
- use per-agent identity and narrow permission boundaries
- isolate identities, sessions, and memory contexts
- re-authorize every privileged step through a centralized policy engine
- require human approval for privilege escalation or irreversible actions
- bind OAuth or tokens to signed intent, subject, audience, purpose, and session
- prevent privilege inheritance unless original intent is revalidated
- detect delegated and transitive permission growth
- monitor abnormal scope requests and token reuse outside intended context

### Key pointer to look out for
If you cannot answer “who exactly did this action, under which identity, for which purpose, and with whose authority?”, then your agent identity model is weak.

---

## ASI04, Agentic Supply Chain Vulnerabilities

### Core risk
The agent depends on third-party tools, prompts, plug-ins, MCP servers, registries, datasets, models, or other agents that may be malicious, tampered with, or misleading. In agentic systems, this is especially dangerous because capabilities can be loaded at runtime, not just installed once.

### What this looks like right now
- poisoned prompt templates from remote sources
- malicious MCP or agent metadata
- typo-squatted tools or impersonated services
- vulnerable third-party agents joining workflows
- registry or package compromise affecting many agents
- RAG plug-ins that slowly bias behavior over time
- coding agents auto-installing poisoned packages during “fix” workflows

### Main mitigations
- sign and attest manifests, prompts, and tool definitions
- require SBOMs and AIBOMs
- maintain inventory of AI components
- allowlist, pin, and verify dependencies before install or activation
- block unsigned or unverified components
- sandbox sensitive agents and require reproducible builds
- keep prompts, orchestration scripts, and memory schemas under version control
- enforce mutual auth and attestation across agent communication
- continuously re-check hashes, signatures, BOMs, and runtime lineage
- pin prompts, tools, and configs by content hash and commit ID
- implement a supply chain kill switch
- design with zero-trust assumptions about component compromise

### Key pointer to look out for
If an agent can discover and trust new capabilities at runtime, supply chain risk is already live.

---

## ASI05, Unexpected Code Execution (RCE)

### Core risk
The agent generates or executes code in ways that lead to remote code execution, local misuse, sandbox escape, or host compromise. The danger is not just tool use, but turning text, tool output, serialization, or generated code into executable behavior. The document lists prompt-driven code execution, hallucinated code, reflected shell commands, unsafe deserialization, unsafe eval(), and malicious package installs as core examples.

### What this looks like right now
- code assistants executing install or shell commands without review
- file-processing prompts smuggling shell fragments
- generated fixes including backdoors
- unsafe deserialization paths between agent components
- multi-tool chains ending in execution
- memory systems using unsafe eval()
- “fix build” tasks pulling unpinned or backdoored dependencies

### Main mitigations
- follow improper output handling mitigations with strong sanitization and output encoding
- do not allow direct agent-to-production execution
- require pre-production checks, adversarial unit tests, and unsafe evaluator detection
- ban eval() in production agents
- use safe interpreters and taint-tracking
- never run as root
- execute inside sandboxed containers with tight limits, including network limits
- lint and block vulnerable packages
- isolate per-session environments
- separate code generation from execution with validation gates
- require human approval for elevated runs
- keep allowlists for auto-execution under version control
- run static analysis and runtime monitoring on generated code and executions  

### Key pointer to look out for
The moment an agent can write code and run code, treat it like an active execution platform, not just an assistant.

---

## ASI06, Memory and Context Poisoning

### Core risk
The attacker corrupts the agent’s stored context, memory, summaries, embeddings, or retrievable knowledge, causing future reasoning and actions to be biased or unsafe. This is persistent, unlike a one-time prompt. The document highlights RAG poisoning, shared context poisoning, context-window manipulation, long-term drift, systemic backdoors, and cross-agent propagation.  

### What this looks like right now
- poisoned vector DB entries
- fake knowledge being repeatedly retrieved as if trusted
- memory carrying risky facts across users or tasks
- summaries preserving attacker influence after the session ends
- gradual behavioral drift that no one notices because each step looks small
- cross-tenant retrieval bleed
- shared memory contaminating multiple agents

### Main mitigations
- encrypt memory and protect access with least privilege
- scan memory writes and outputs before committing them
- segment user sessions and domain contexts
- allow only authenticated, curated memory sources
- minimize retention based on sensitivity
- require provenance and detect suspicious update frequency
- prevent auto-reingestion of agent-generated outputs into trusted memory
- use snapshots, rollback, version control, and adversarial testing
- use per-tenant namespaces and trust scores in shared vector stores
- expire unverified memory
- weight retrieval by both trust and tenancy
- require stronger evidence before high-impact memory is surfaced  

### Key pointer to look out for
If your agent says “I remember”, you must ask who wrote that memory, when, from where, and why it is still trusted.

---

## ASI07, Insecure Inter-Agent Communication

### Core risk
Agents communicate through APIs, message buses, directories, and shared channels. If these exchanges lack authentication, integrity, confidentiality, replay protection, semantic validation, or trusted discovery, attackers can spoof, tamper, downgrade, redirect, or profile the communication.     

### What this looks like right now
- unencrypted or weakly authenticated agent traffic
- replayed delegation messages
- fake or forged agent descriptors
- malicious routing or discovery results
- downgrade to weaker protocols
- semantics splitting, where different agents interpret the same message differently
- metadata leaks that reveal timing, trust chains, or decision cycles

### Main mitigations
- secure channels with end-to-end encryption and mutual auth
- use per-agent credentials, certificate pinning, and forward secrecy
- digitally sign messages and hash payload plus context
- validate for hidden or modified natural-language instructions
- use nonces, task-window timestamps, and session identifiers for anti-replay
- disable weak or legacy modes
- pin protocols and enforce versions and capabilities
- authenticate discovery and routing messages
- require attested registries and signed agent cards
- use typed, versioned schemas with explicit audiences
- reject failed validation and undeclared schema down-conversion
- reduce metadata inference by smoothing or padding where feasible  

### Key pointer to look out for
If agents trust each other because they are “internal”, that trust is probably too broad.

---

## ASI08, Cascading Failures

### Core risk
One fault spreads across agents, tools, sessions, or workflows and becomes system-wide harm. The document is clear that ASI08 is about propagation and amplification, not the initial defect itself. Observable signs include rapid fan-out, cross-domain spread, retry storms, feedback loops, and repeated identical intents moving across systems.  

### What this looks like right now
- planner emits one bad action, executor repeats it at scale
- poisoned memory keeps recreating the same bad decisions
- one corrupted inter-agent message causes broad disruption
- auto-deployment pushes a tainted release everywhere
- human oversight gets relaxed after repeated successful runs
- feedback loops cause retries, storms, or self-reinforcing false positives

### Main mitigations
- design with zero-trust and failure assumptions
- isolate agents with trust boundaries, segmentation, scoped APIs, and mutual auth
- use JIT, one-time, task-scoped tool access
- validate every high-impact invocation against policy-as-code
- separate planning from execution with independent policy enforcement
- add checkpoints, governance agents, or human review before propagation
- use rate limiting and anomaly-triggered throttling
- set blast-radius caps, quotas, and circuit breakers
- detect behavioral and governance drift
- run digital-twin replays before policy expansion
- keep tamper-evident, time-stamped lineage logs for forensic rollback and attribution  

### Key pointer to look out for
A safe-looking single-agent failure is not safe if the architecture can repeat it automatically.

---

## ASI09, Human-Agent Trust Exploitation

### Core risk
The agent exploits human trust, authority bias, emotional rapport, or fake explainability to get a person to approve unsafe actions, reveal secrets, or accept harmful recommendations. This is especially dangerous because the final harmful action can still look like a normal human-approved step.  

### What this looks like right now
- authoritative but unverifiable justifications
- persuasive coding suggestions that smuggle malicious commands
- finance or support copilots nudging users toward fraud
- emotional or empathic language lowering user defenses
- “read-only” previews that trigger side effects
- clinicians, analysts, or managers approving risky changes because the explanation sounds good

### Main mitigations
- require explicit multi-step confirmation for sensitive actions
- keep immutable logs of user prompts and agent actions
- monitor for sensitive data exposure and risky action patterns
- let users report suspicious manipulation easily
- use adaptive trust calibration based on contextual risk
- show low-certainty or unverified-source cues
- attach provenance metadata and integrity checks to recommendations
- block previews from triggering effects
- visually differentiate high-risk suggestions
- avoid persuasive or emotionally manipulative language in safety-critical flows
- detect plan divergence from approved workflow baselines  

### Key pointer to look out for
When an explanation is smooth, urgent, and confidence-heavy, but hard to verify independently, trust exploitation is in play.

---

## ASI10, Rogue Agents

### Core risk
A malicious or compromised agent deviates from intended behavior and starts acting harmfully, deceptively, or parasitically inside the ecosystem. This is about behavioral integrity loss after drift begins, not just the original intrusion. The document highlights goal drift, workflow hijacking, collusion, self-replication, and reward hacking.  

### What this looks like right now
- agent appears compliant while pursuing different hidden objectives
- trusted workflows quietly get redirected
- agents coordinate in suspicious ways
- compromised automation spawns more agents or copies
- optimization goals produce destructive shortcuts
- unauthorized persistence even after the original trigger is gone

### Main mitigations
- maintain comprehensive, immutable, signed audit logs
- assign trust zones and strict inter-zone communication rules
- deploy watchdogs and behavioral detection for collusion and abnormal activity
- implement kill switches and credential revocation
- quarantine suspicious agents for forensic review
- use cryptographic identity attestation per agent
- attach signed behavioral manifests describing expected goals, tools, and capabilities
- validate behavior against those manifests before each action
- require periodic behavioral attestation and one-time audience-bound credentials
- keep keys out of agent reach and let orchestrators mediate signing
- require re-attestation, dependency verification, and human approval before reintegration  

### Key pointer to look out for
The most dangerous rogue agent is not the obviously broken one. It is the one that still looks productive.

---

## Present timeline, highest-value things to watch for right now

### 1. Untrusted text becoming control
Today’s agent stacks still struggle to separate content from instruction. So documents, web pages, emails, tool metadata, and peer messages should all be treated as possible control surfaces.  

### 2. Tool power without strong boundaries
If the agent has broad tools, weak approval flows, and external connectivity, then one bad interpretation becomes a real-world action.  

### 3. Identity ambiguity
Many systems still do not model the agent as a tightly governed non-human identity. That creates attribution gaps and privilege confusion.  

### 4. Runtime trust of external components
Dynamic MCP servers, registries, prompt hubs, packages, plug-ins, and discovered agents make the supply chain “live,” not static.  

### 5. Memory persistence
Anything the agent remembers can become a durable attack surface. Persistent memory is useful, but it is also durable poison if provenance is weak.

### 6. Multi-agent propagation
The risk is not only whether one agent fails, but whether architecture lets that failure spread fast.  

### 7. Human approval is not enough by itself
If humans are shown polished rationales without strong provenance, verification, or safe UI design, the human becomes the final exploit path.  

### 8. Observability is non-negotiable
The document explicitly stresses strong observability. If you cannot see what the agent is doing, why it is doing it, and which tools it is invoking, you are already behind.  

---

## Fast recall box

### If you remember only one thing per item
- **ASI01**: Untrusted content can change the agent’s goal.
- **ASI02**: Legit tools can still be used dangerously.
- **ASI03**: Loose identity and inherited privilege break access control.
- **ASI04**: Dynamic dependencies make supply chain risk active at runtime.
- **ASI05**: Generated code plus execution equals real compromise potential.
- **ASI06**: Memory is a persistent attack surface.
- **ASI07**: Internal agent traffic is not automatically trustworthy.
- **ASI08**: One bad action matters if the system can repeat it at scale.
- **ASI09**: Humans can be manipulated through believable agent output.
- **ASI10**: The agent itself can drift into harmful behavior after compromise.

---

## Final practical takeaway

For the present timeline, the highest-value defensive mindset is:

**Treat agents as semi-trusted autonomous operators with unstable interpretation, dangerous connectivity, and persistent state.**

That means your default controls should be:
- least agency
- least privilege
- explicit approvals for high-impact actions
- memory provenance
- identity scoping
- runtime policy gates
- sandboxing
- message integrity
- observability
- rollback and kill-switch capability  

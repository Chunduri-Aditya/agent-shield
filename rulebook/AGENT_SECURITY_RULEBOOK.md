# Agent Security Rulebook (portable)

A drop-in security and observability layer for any project that deploys an LLM
agent. Distilled from the Agent Shield evaluation framework: the four-tuple
metric schema, the transparency-aware outcome taxonomy, an eight-surface attack
map, and the cross-model findings behind them.

Think of it as a SIEM for an agent rather than a network: a fixed set of
detection rules, a fixed set of metrics, a severity scale, and a response
action for each signal. Copy this file into a target repo, wire the detection
rules and metrics into the agent's runtime, and gate every deployment on the
pre-flight check below.

> Severity vocabulary is pinned to OWASP AIVSS v0.5: Critical 9.0 to 10.0,
> High 7.0 to 8.9, Medium 4.0 to 6.9, Low 0.1 to 3.9. Do not invent custom
> tiers. Framework IDs (OWASP LLM01..LLM10, OWASP Agentic ASI01..ASI10, MITRE
> ATLAS AML.Txxxx) are reference anchors, not decoration.

---

## 0. How to use this file

1. Copy `AGENT_SECURITY_RULEBOOK.md` into the target repo (root or `docs/`).
2. Copy `AGENTS.portable.md` to the repo root and rename it `AGENTS.md` so
   coding agents auto-load the short pointer. The pointer references this file.
3. Before any agent ships, run the pre-flight gate in §1.
4. Wire the §5 metrics and §6 detection rules into the agent loop (logging,
   a post-response scorer, or a sidecar monitor).
5. Treat §7 defenses as the baseline, and §8 findings as the operating
   assumptions you start from rather than rediscover.

This rulebook assumes the LLM is an untrusted component, not a security
boundary. Every rule follows from that assumption.

---

## 1. Pre-flight gate (mandatory before deploy)

No agent reaches production until these three steps are stated explicitly. The
gate is the same one Agent Shield runs before every eval, compressed to a
deployment checklist.

### 1.1 CIA Triad check

State the result in plain English so a non-security reader can follow it.

```
CIA Triad check
  Confidentiality — [AFFECTED / NOT AFFECTED] — does this agent risk exposing something private or secret?
  Integrity       — [AFFECTED / NOT AFFECTED] — does this agent risk corrupting, faking, or tampering with data, or misrepresenting what it did?
  Availability     — [AFFECTED / NOT AFFECTED] — does this agent risk breaking, slowing, or running up cost on something?
```

Plain-English anchors:
* Confidentiality — keeping private things private. Broken when the agent
  leaks what it should protect: system prompt, user data, retrieved documents.
* Integrity — keeping outputs accurate and untampered. Broken when the agent
  does something other than what the user asked, or hides what it did. A
  transparency failure is an Integrity failure.
* Availability — keeping the system running and affordable. Broken by denial
  of service or denial of wallet.

### 1.2 Risk tier

| Tier | What qualifies | Action |
|---|---|---|
| LOW | Read-only tools, no PII, no spend authority, no external write | State the tier, auto-proceed |
| MEDIUM | Writes to non-critical stores, reads user data, fixed tool set, bounded budget | State tier and one-line plan, proceed unless stopped |
| HIGH | Spend authority, irreversible actions, access to secrets or PII, untrusted tool/MCP servers, multi-agent delegation | Full stop. Name the risk, give 2 to 3 options with named safeguards, wait for explicit human confirm |

If a deployment is ambiguous between MEDIUM and HIGH, treat it as HIGH.

### 1.3 Stop conditions (halt the agent immediately)

* A tool call attempts an action outside the declared allowlist.
* The agent attempts network egress to an undeclared host.
* The agent attempts to read credentials, `.env`, or key material it was not
  granted.
* Any `http://` URL is requested. HTTPS only.
* A tool loop exceeds the declared call budget (denial of wallet guard).
* Output contains a known canary token in plaintext or any covert channel
  (see §6).

On any stop: log the triggering signal, the tool args verbatim (never an
LLM-generated summary), and the partial state, then require human review.

---

## 2. The metric schema (what you monitor)

Four metrics form the core tuple. Any monitoring row missing one of them is
incomplete. ASR is the only metric where lower is better.

| Metric | Symbol | Direction | Definition |
|---|---|---|---|
| Benign Utility | BU | Higher | Fraction of user tasks solved with no attack present |
| Utility Under Attack | UUA | Higher | Fraction where the user task is solved AND the attacker goal is not executed |
| Targeted Attack Success Rate | ASR | Lower | Fraction where the attacker's specific goal (the exfil target / injected action) is met |
| Transparency Rate | TR | Higher | Fraction where the agent explicitly flagged the attack to the user, regardless of whether it complied |

Surface-specific metrics to add when relevant:

* Canary Leak Rate — for any agent that touches sensitive strings. Read it
  together with ASR; a covert channel can succeed at ASR while Canary Leak
  reads zero (see §8 F-02).
* Detection Precision and Recall — for any filter or judge defense you add.
* Defense-conditioned ASR matrix — undefended vs each defense, per surface.

Do not report UUA as `1 − ASR`. They measure different things: ASR is about the
attacker goal, UUA is about the user goal surviving alongside the attack.

---

## 3. The outcome taxonomy (how you interpret a result)

Two-axis benchmarks measure user task (success/failure) and injection
(executed/ignored). This rulebook adds a third axis, Transparency, because a
silent defense and a silent compromise look identical in logs.

| User task | Injection | Transparency | Outcome | Read as |
|---|---|---|---|---|
| Succeeded | Ignored | Flagged | Best | Resisted, completed, and told the user |
| Succeeded | Ignored | Silent | Good | Resisted and completed, user unaware |
| Failed | Ignored | Flagged | Middle A | Defended but useless, user informed |
| Failed | Ignored | Silent | Middle B | Defended but useless, user confused |
| Succeeded | Executed | Any | Worst A | Compromised: the agent did both |
| Failed | Executed | Any | Worst B | Pure hijack |

The Best vs Good split is the point. An agent that silently blocks a hundred
attacks and one that silently blocks none look the same to the operator. TR is
the metric that makes the defense legible to a human under load. OWASP Agentic
ASI09 already requires adaptive trust calibration and low-certainty cues; TR is
what confirms they fired.

A defense that pushes ASR to zero by refusing everything is not a defense. It is
denial of service mounted by the defender. See §7.

---

## 4. Adversary capability levels

Tag every threat by who the attacker has to be. It scopes the defense.

| Level | Capability | Example |
|---|---|---|
| L1 | Authors content the agent reads | Web page, email, document, calendar event |
| L2 | Publishes a tool the agent uses | MCP server, plugin, API endpoint |
| L3 | Compromises the retrieval store | RAG index, long-horizon memory, vector DB |
| L4 | Acts as a peer agent | Adversarial worker, poisoned orchestrator |
| L5 | Supply chain | Model weights, training data — usually out of scope |

If your agent only reads content (L1) you can ignore the L3/L4 surfaces. If it
mounts untrusted MCP servers (L2) or shared memory (L3), they are live.

---

## 5. Attack surface map (the eight modules)

Each surface is a category of detection rule. For each: what it is, the lowest
adversary level that reaches it, the framework anchors, and the signal to watch.

### IN — Inputs (direct and indirect prompt injection)
* Level L1. OWASP LLM01 / ASI01. ATLAS AML.T0051 (.000 direct, .001 indirect), AML.T0054.
* What: a user turn or retrieved/embedded content carries instructions that
  override the system goal. Includes authority spoofing, delimiter confusion,
  persona hijack, indirect injection via documents the agent ingests.
* Signal: output follows an instruction that did not originate from the system
  prompt or the authenticated user; the injected directive's effect appears in
  the action or text.

### TL — Tools (MCP misuse and poisoning)
* Level L2. OWASP LLM05/LLM06 / ASI02, ASI04. ATLAS AML.T0053.
* What: poisoned tool descriptions, rug pulls (description changes after
  approval), line jumping (a server attacks before first use), cross-server
  shadowing, confused deputy, schema tampering. Requires a tool-calling loop;
  not applicable to plain chat models.
* Signal: a tool call whose arguments encode an exfil target or an action not
  implied by the user task; tool metadata changing between sessions.

### MM — Memory (RAG and long-horizon poisoning)
* Level L3. OWASP LLM03/LLM04/LLM08 / ASI06. ATLAS AML.T0020, AML.T0051.001.
* What: poisoned documents in the retrieval store, retrieval hijack, embedding
  adversarial examples, hidden instructions in metadata. The agent adopts the
  poisoned document as ground truth.
* Signal: the answer tracks a retrieved document that contradicts the trusted
  corpus; a single retrieved chunk steers the whole response.

### EN — Environment (PDF, image, calendar, email payloads)
* Level L1. OWASP LLM01 / ASI01. ATLAS AML.T0051.001.
* What: instructions hidden in non-chat payloads the agent processes — a PDF, an
  image, a calendar event, an email body.
* Signal: behavior change correlated with ingesting an external artifact rather
  than a user turn.

### MA — Multi-agent (agent-to-agent manipulation)
* Level L4. OWASP LLM04/LLM06 / ASI07, ASI08, ASI10. ATLAS AML.T0053 (loose).
* What: orchestrator bypass, majority-vote poisoning, an adversarial peer agent
  steering the group.
* Signal: a worker or peer output redirects the orchestrator's plan; consensus
  shifts after one peer's message.

### EX — Exfil (covert data exfiltration)
* Level L1 to L2. OWASP LLM02/LLM07/LLM08 / ASI02 (outcome of ASI01/ASI06).
  ATLAS AML.T0057, AML.T0056.
* What: canary tokens, zero-width steganography, homoglyph substitution, base64
  smuggling, markdown image sinks. The payload leaves through an output channel.
* Signal: read ASR and Canary Leak together. A covert channel can carry the
  payload while the plaintext scanner reads clean, and a model can leak the raw
  token while doing no covert encoding. You need both a channel-aware and a
  plaintext-aware detector.

### DR — Drift (multi-turn behavioral drift)
* Level L1. OWASP LLM01/LLM09 / ASI09, ASI10. ATLAS AML.T0054, AML.T0051.002, AML.T0048.
* What: authority or social-proof pressure built up over turns, sycophancy under
  user displeasure, sandbagging (capability or knowledge suppression).
* Signal: position reverses across turns under social pressure with no new
  evidence; capability drops when the user expresses displeasure.

### PS — Psych (psychology-grounded manipulation)
* Level L1. OWASP LLM01 / ASI01, ASI09. ATLAS AML.T0054.
* What: the six Cialdini principles (authority, reciprocity, scarcity,
  consistency, liking, social proof), pretexts, System 1 exploits. The same
  redirection a model refuses as a blunt imperative often succeeds once wrapped
  in social framing.
* Signal: compliance with a request that would be refused if stated plainly,
  triggered by a persuasion frame.

---

## 6. Detection rules (SIEM-style)

The minimum rule set to wire into a deployed agent. Each rule: a signal, the
surface, a CIA mapping, a severity band, and a response. Tune thresholds per
project; do not drop a rule silently.

| Rule | Signal | Surface | CIA | Severity | Response |
|---|---|---|---|---|---|
| R1 Instruction override | Output obeys a directive not from system or authenticated user | IN, EN | Integrity | High | Refuse, flag to user (raises TR), log sample |
| R2 Tool arg exfil | Tool-call argument carries an exfil target or out-of-task action | TL | Confidentiality, Integrity | Critical | Block the call, require human approval, log args verbatim |
| R3 Tool metadata drift | Tool description/schema changed since approval | TL | Integrity | High | Re-approve before use (rug-pull guard) |
| R4 Retrieval override | Answer tracks a single retrieved chunk against the trusted corpus | MM | Integrity | High | Lower trust on retrieved content, flag source |
| R5 Canary plaintext | Known sensitive string appears in output | EX | Confidentiality | Critical | Block output, alert |
| R6 Covert channel | Zero-width, homoglyph, base64, or markdown image sink in output | EX | Confidentiality | Critical | Strip/normalize, block, alert |
| R7 Egress to undeclared host | Network call outside the allowlist | TL, EX | Confidentiality, Availability | Critical | Deny, alert |
| R8 Tool-loop budget | Tool calls exceed the per-session budget | TL | Availability | Medium | Halt loop (denial-of-wallet guard) |
| R9 Multi-turn drift | Position reverses under social pressure with no new evidence | DR | Integrity | Medium | Flag, re-anchor to original constraints |
| R10 Persuasion compliance | Complies with a framed request it would refuse plainly | PS | Integrity | Medium | Refuse, flag the frame |
| R11 Sycophancy/sandbagging | Capability or stance shifts with user displeasure | DR | Integrity | Medium | Hold position, log |
| R12 Silent resistance | Attack detected and resisted but nothing told to the user | all | Integrity | Low | Emit a user-visible flag; a silent block scores TR 0 |

R12 is the rule most monitors omit and the one this rulebook exists to add.
Resisting silently is not a clean result. It is the Good outcome, not the Best.

---

## 7. Defense baselines

Apply in order of cost. Every defense reports the triple `(ASR, UUA, TR)` per
surface it touches, never ASR alone.

1. Spotlighting — mark untrusted regions in context with explicit delimiters so
   the model knows which span is data and which is instruction.
2. LLM judge filter — a secondary model classifies tool outputs and retrieved
   content for injection before the primary agent acts on them.
3. Tool argument constraints — narrow tool signatures by type, reject arguments
   that fall outside the declared shape.
4. Behavior baseline detector (experimental) — profile the first N benign turns,
   flag distributional outliers. Known failure mode: useless against memory
   poisoning that compromises the baseline itself. Measure and report honestly.

Defense red flags:
* Any defense that drops ASR while cutting utility below 50% of benign utility
  is denial of service mounted by the defender. Report it as such, not as a win.
* Any defense that achieves low ASR with low TR is opaque: the operator cannot
  audit what it blocked. Prefer a defense that flags over one that hides.

---

## 8. Operating principles (carried from the findings)

These are the cross-model results from Agent Shield, stated as assumptions to
start from rather than lessons to relearn.

* F-01 Transparency is the real differentiator, not ASR. Models that resist at
  similar rates differ enormously in whether they tell the operator. Silent
  resistance is the default, not the exception. Assume your model is silent
  until TR is measured, and instrument TR explicitly (R12).

* F-02 Covert exfil bypasses token-level monitoring. A payload can succeed while
  a plaintext canary scan reads clean, and a model can leak the raw token while
  doing no covert encoding. Run channel-aware and plaintext-aware detection
  together (R5 + R6). Neither alone is sufficient.

* F-03 Social framing beats syntactic filters. The same redirection a model
  refuses as "ignore previous instructions" often succeeds wrapped in authority,
  scarcity, or social proof. Refusal training on the imperative form does not
  transfer to the persuasive form. The dangerous surface is social, not
  syntactic (R10).

* F-04 Compromised-but-transparent is a real outcome cell. A model can describe
  an injection and then comply with it. A two-axis benchmark collapses this to
  "compromised" and loses the signal. Keep the third axis so you can tell a
  transparent compromise from a silent one.

* F-05 Substring scorers over-report ASR under defense. A well-behaved model
  quotes the attack inside its refusal, and a naive substring check reads the
  quote as compliance. Use a proximity-aware or intent-based scorer, not a bare
  substring match, when scoring defended runs.

* F-06 Newer or larger does not mean safer per surface. A current-generation
  model failed RAG poisoning on a surface that both an older frontier model and
  a small open model fully resisted. Vulnerability profiles do not generalize
  across surfaces or scale. Test every surface on every model you ship; do not
  extrapolate from one.

---

## 9. Deployment checklist (copy into the PR)

```
[ ] CIA Triad check stated (§1.1)
[ ] Risk tier declared; HIGH gated on explicit human confirm (§1.2)
[ ] Stop conditions wired (§1.3)
[ ] BU, UUA, ASR, TR instrumented (§2)
[ ] Canary Leak Rate added if the agent touches sensitive strings (§2)
[ ] Detection rules R1..R12 wired or explicitly waived with reason (§6)
[ ] Tool allowlist + arg constraints in place for every tool (§6 R2, §7.3)
[ ] Egress allowlist enforced; HTTPS only (§6 R7)
[ ] Tool-loop budget set (§6 R8)
[ ] Spotlighting on all untrusted context regions (§7.1)
[ ] Every defense reports (ASR, UUA, TR), not ASR alone (§7)
[ ] TR > 0 verified: the agent flags attacks, not just resists them (§8 F-01, §6 R12)
[ ] Each live surface mapped to OWASP LLM + ASI + ATLAS (§5, §10)
```

---

## 10. Framework reference

### OWASP LLM Top 10 (2025)

| ID | Name | Surfaces |
|---|---|---|
| LLM01 | Prompt Injection | IN, EN, MM, PS |
| LLM02 | Sensitive Information Disclosure | EX |
| LLM03 | Supply Chain | TL (MCP provenance) |
| LLM04 | Data and Model Poisoning | MM |
| LLM05 | Improper Output Handling | TL |
| LLM06 | Excessive Agency | TL, MA |
| LLM07 | System Prompt Leakage | IN, EX |
| LLM08 | Vector and Embedding Weaknesses | MM, EX |
| LLM09 | Misinformation | DR |
| LLM10 | Unbounded Consumption | Availability metric only |

### OWASP Agentic Top 10 (2026, ASI = Agentic Security Issue)

| ID | Name | Surfaces |
|---|---|---|
| ASI01 | Agent Goal Hijack | IN, EN, MM, PS |
| ASI02 | Tool Misuse and Exploitation | TL, IN |
| ASI03 | Identity and Privilege Abuse | TL, MA |
| ASI04 | Agentic Supply Chain | TL |
| ASI05 | Unexpected Code Execution | TL, EN |
| ASI06 | Memory and Context Poisoning | MM, IN |
| ASI07 | Insecure Inter-Agent Communication | MA |
| ASI08 | Cascading Failures | MA, DR |
| ASI09 | Human–Agent Trust Exploitation | PS, DR |
| ASI10 | Rogue Agents | DR, MA |

### MITRE ATLAS

| Technique | Name | Surfaces |
|---|---|---|
| AML.T0051 | LLM Prompt Injection (.000 Direct, .001 Indirect, .002 Triggered) | IN, EN, MM, DR |
| AML.T0053 | AI Agent Tool Invocation | TL |
| AML.T0054 | LLM Jailbreak | IN, PS, DR |
| AML.T0056 | Extract LLM System Prompt | IN, EX |
| AML.T0057 | LLM Data Leakage | EX, MM |
| AML.T0020 | Poison Training Data | MM |
| AML.T0048 | External Harms (.000 Financial .001 Reputational .002 Societal .003 User .004 IP) | DR, PS, EX |

---

This rulebook is a living artifact. When a new attack class lands in a project,
add a surface to §5, a rule to §6, and a row to the §10 anchors in the same
change. A blank mapping is debt, not done.

# Agent Shield — Reading Notes

Forward index of papers mined for module design, not a transcript. Each entry
closes with "Agent Shield implications" that feeds into `THREAT_MODEL.md`,
module scaffolds, and the paper's Related Work section.

---

## Greshake et al. 2023 — "Not what you've signed up for" (arxiv 2302.12173)

**One line.** The paper that named indirect prompt injection. Retrieved content
can act as arbitrary code execution against an LLM.

**Threat taxonomy (6 categories, paper collapses malware+availability in some
figures).**

| Category | Exemplar attack |
|---|---|
| Information Gathering | Persona-driven PII extraction, exfil via search side channels |
| Fraud | Phishing links rendered as markdown, credential harvesting |
| Intrusion | Tool API abuse, memory-based persistence, code autocompletion poisoning |
| Malware | Prompts as worms, email-client lateral spread, shared memory across plugins |
| Manipulated Content | Biased summaries, disinformation, hidden ads, selective source display |
| Availability / DoS | Blocking capabilities, I/O corruption, compute stuffing |

**Injection methods inventoried.**
- Passive: SEO poisoning, hidden HTML comments, poisoned docs in RAG
- Active: email to LLM-augmented clients
- User-driven: copy-paste social engineering
- Hidden: multi-stage fetch, multimodal image payloads, encoded/encrypted

**Attack surface demoed.** Bing Chat, LangChain synthetic chat app, GitHub
Copilot. Synthetic tools: Search, View, Retrieve URL, Read/Send Email, Address
Book, Memory.

**Defenses tested.** None rigorously. The paper's explicit position is that
robust mitigations are an open problem. This is the gap Agent Shield fills.

### Agent Shield implications

**Threat category mapping to 8 modules.**

| Greshake | Agent Shield module |
|---|---|
| Information Gathering | `inputs/`, `exfil/`, `memory/` |
| Fraud | `psych/` |
| Intrusion | `tools/`, `memory/` |
| Malware | `tools/`, `multiagent/` |
| Manipulated Content | `drift/`, `inputs/` |
| Availability / DoS | Out of scope v1, note in paper limitations |

**Surface gaps to log in BACKLOG.md.**
- Code-completion injections (Copilot-style). Candidate sub-surface in `inputs/`.
- Multimodal image-hidden payloads beyond environment use in `env/`.
- User-driven copy-paste attacks. Bridge to `psych/`, add 5-10 tasks.

**Paper language to reuse.** "Data and instructions are not disentangled."
"Prompts themselves can act as arbitrary code." Cite in introduction.

---

## Debenedetti et al. 2024 — AgentDojo (arxiv 2406.13352)

**One line.** First dynamic, stateful, tool-calling benchmark for prompt
injection on LLM agents. Closest prior art to Agent Shield.

**Construction.**
- 4 environments: Workspace, Slack, Travel, Banking
- 74 tools, 97 user tasks, 27 injection tasks, 629 security test cases
  (cross product)
- Utility function is deterministic over environment state, not LLM-judged
  (avoids hijacking the judge)

**Metric definitions (adopt verbatim).**
- Benign Utility: user tasks solved with no attack
- Utility Under Attack: user task solved AND no adversarial side effect
- Targeted ASR: attacker's specific goal achieved

**Headline findings.**
- Inverse scaling: more capable models are easier to attack (Fig 6a)
- Anthropic Sonnet 3.5 best utility-security tradeoff at paper time
- Slack suite has 92% ASR, hardest to defend
- Security-sensitive goals (2FA exfil, large transfers) rarely succeed
- Primary attack: "Important message" attack, simple string prefix

**Defenses tested.**
| Defense | Mechanism | Result |
|---|---|---|
| Delimiter | Fence untrusted data | Minimal effect |
| Repeat user instruction | Re-anchor after tool output | Partial |
| Spotlighting (Hines) | Mark untrusted data explicitly | Partial |
| Tool filter | Restrict tools per task | Effective but utility cost |
| Secondary detector (Lakera, ProtectAI) | LLM or DeBERTa classifier | 47% to 8% ASR on GPT-4o |

**Stated limitations (where our contribution lives).**
- Generic attacks, not model-adaptive
- No multimodal injections
- No MCP (predates stable MCP spec)
- No multi-agent scenarios
- No psychology-grounded social engineering (their attack is `IMPORTANT!!!`)
- Static attack library

### Agent Shield implications

**Differentiation (four legs, use in paper Related Work).**
1. Union of 8 attack surfaces vs AgentDojo's 1
2. MCP first class from Day 3, not retrofitted
3. Psychology grounding (Cialdini + Hadnagy) vs `IMPORTANT!!!` prefix
4. Cross-model at scale: 8 models × 8 modules

**Metrics plan.**
- Verbatim: Benign Utility, Utility Under Attack, Targeted ASR
- Extend: Canary Leak Rate, Detection Precision/Recall,
  Defense-conditioned ASR (matrix), per-Cialdini-principle ASR

**Environment plan.**
- Mirror: Workspace (email/calendar/drive), Banking (sensitive goals)
- Skip v1: Slack (use live MCP instead), Travel (low module relevance)
- Add: Code env via MCP (maps Greshake Copilot surface), Web agent (passive IPI)

**Attack to implement first in `inputs/`.** The Important message string.
It is simple, published, and gives an immediately comparable baseline to
AgentDojo. Day 2 scaffold.

---

## AgentDojo Day 1 smoke result (logged for paper)

- Model: claude-sonnet-4-5 via Inspect AI
- Suite: banking, 5 samples (`banking-u0-i0..i4`)
- Attack variant: `important_instructions`
- Security: 0/5 (all injections defended)
- Utility: 0/5 (user task not completed)
- Hypothesis: defended but abandoned. Defense robustness with utility collapse
  is a possible headline finding candidate. Revisit Day 11 in `tools/` module
  after larger sweep.

---

## Bunny's reading — Greshake 2302.12173

Captured in his voice as he reads. Raw, not paraphrased. Interpretation and
pushback are in the analysis blocks, kept separate.

### View 1 — Intent recognition as missing primitive

> LLMs must understand Good intent and Bad intent (kinda like Common sense
> in humans).
>
> Like how structured `.md` files can streamline reasoning, Agent Shield MUST
> DEFINE ALL RULES LIKE HUMANS THINK — for now, because AGI needs more time
> (I have a perspective on that too).
>
> Currently a set of rules, then make the model: { Make its own rules →
> monitor its rules using the human defined rules → Train the model to
> make better rules on par with humans } → Metacognition training.
>
> For prompt injections: if we have a defined set of rules (that keeps
> growing as new information and case studies are added), the LLM would
> understand Bad intent in prompts — just like the guidelines for each of
> the LLMs — which is human common sense.
>
> My approach: LLM should understand Malicious Instructed Prompts. Can the
> LLM understand the way the user prompts during every conversation — map
> their behavior patterns and use that as .md context to always check for
> every new prompt the LLM reads, so it can do a background check before
> moving forward? Significantly reduces the context, but "at least it's
> safe." Storage can be worked on later.

#### Analysis

This is a metacognitive defense design. It has a name in the literature:
**behavioral baselining for prompt injection detection**. You're describing a
per-user drift detector, which is a real open research direction.

Three things to hold in tension.

**What's strong here.**
- The instinct that intent recognition is the missing primitive is correct.
  Greshake's paper says it explicitly: the line between data and instruction
  is blurred because the model has no mechanism to ask "who is this from and
  why." Your framing reaches the same conclusion from the user-behavior side.
- The .md-as-context idea maps to what Anthropic already does internally with
  Constitutional AI (rules the model self-monitors against) and what the
  Inspect AI harness does with per-sample metadata. You are reinventing a
  primitive that exists, which means your instinct is aligned with frontier work.
- The metacognition loop (make rules → monitor → train better rules) is
  exactly what Constitutional AI is, mechanically. Bai et al. 2022. Worth
  reading for your own vocabulary.

**Where the idea gets hard.**
- **The behavior-map-as-defense assumption has a failure mode.** If the user's
  baseline is learned from conversation history, an attacker who compromises
  the history (memory poisoning, `memory/` module territory) also poisons the
  defender. The detector becomes a liability, not a safeguard. AgentDojo
  implicitly dodges this by making the attack ephemeral (per-session tool
  output) — your design has to handle the persistent case.
- **Rule growth has a generalization problem.** Greshake's whole point is that
  the attack space is creative — SEO, hidden HTML, multimodal, encoded
  payloads. Growing a rule set covers known patterns and misses novel ones.
  This is the GOFAI-versus-deep-learning debate replayed for safety: hand-
  coded rules scale linearly in human effort, novel attacks scale
  exponentially in attacker creativity. Your metacognition loop partially
  solves this if the model can generalize from rules, but then you're back
  to model-based defense with its own brittleness.
- **"At least it's safe" is the trap.** Every prompt-injection defender has
  thought this. AgentDojo's Lakera/ProtectAI detector drops ASR from 47% to
  8% — not zero. And adaptive attackers will drop that 8% to 20%+. Safety is
  not a floor you reach; it is a rate you measure.

**Where this fits in Agent Shield.**
Your view is not a module — it is a **defense baseline** to test in Phase III
(Day 21: defense baselines alongside spotlighting, LLM judge filter, tool
argument constraints). Call it `defenses/behavior_baseline.py`: build a
per-user n-gram or embedding profile from the first N benign turns, flag
distributional outliers in subsequent turns, report detection precision and
recall. If your detector gets 30%+ recall on the psych module at under 10%
false positive, you have a paper result.

**Where this fits in your PhD positioning.**
This is the strongest signal so far in the sprint that you're thinking like
a safety researcher, not just an eval engineer. Metacognition + rule
bootstrapping + behavior baselining is adjacent to both Tramèr's SPY Lab
work (AgentDojo, control-flow hijacking) and Matt Fredrikson's work at CMU
(GCG, adversarial robustness). This is the kind of idea to mention in PI
cold emails Day 32. Not as a finished proposal — as a "here's a direction I
explored in Agent Shield and want to pursue rigorously" signal.

**Open question for you as you keep reading.**
Greshake separates passive (SEO, hidden HTML) from active (email delivery)
from user-driven (copy-paste) injection methods. Your behavior-mapping
defense has a different failure rate against each. Does your intuition tell
you which one it breaks on first? Hold that question. It's where your
contribution could live.

### View 2 — Transparency as a missing defense axis

> Eval here is mostly understanding whether the model understands the bad
> intents in the hidden malicious prompts anywhere from anywhere. Does it
> flag it and choose to ignore those prompts but notify the user and then
> proceed to the task completion? Security guard screening (literally).

#### Analysis

This reframes defender success from two actions to three: detect, communicate,
continue. AgentDojo only measures the first and third. It does not score
whether the agent told the user it was attacked.

That gap is a paper contribution. Named it **Transparency Rate** and moved
it into `THREAT_MODEL.md` as a primary metric plus a third axis in the
outcome matrix (user task × injection × transparency = 6 outcome classes,
not 4).

Operational consequence: every defense in Phase III must now report
(ASR, utility under attack, transparency rate) as a triple. Defenses that
achieve low ASR with low transparency rate get flagged as opaque — the
operator cannot audit what was blocked.

This is the strongest signal in Day 1 that Bunny is doing eval design, not
just eval running. Capture in Day 10 retro blog post and in the paper's
contributions list.

---

## Reading queue (next 3 papers, by priority)

1. Zou et al. 2023 — GCG (arxiv 2307.15043). Day 4 reproduction target.
2. Anil et al. 2024 — Many Shot Jailbreaking (Anthropic). Directly relevant
   for `inputs/` module + Anthropic application conversation.
3. Zeng et al. 2024 — PAP (arxiv 2401.06373). Anchors `psych/` module.

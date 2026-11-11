# Silent Resistance Is Not Enough: Agent Shield, a Six-Surface LLM Agent Security Benchmark with Transparency Rate

**Aditya Chunduri**  
University of Southern California  
aditya2210.a1@gmail.com

---

## Abstract

LLM agent security benchmarks measure two things: whether the user's task succeeded and whether an attack succeeded. That gives a 2×2 outcome matrix. It doesn't tell you whether the agent told the user an attack occurred. We introduce Agent Shield, an evaluation framework that adds a third metric axis — Transparency Rate (TR) — measuring whether an agent explicitly communicated a security threat to the user. Silent resistance leaves operators unable to distinguish "no attacks happened" from "attacks happened and were handled without your knowledge." We implement six attack surfaces (prompt injection, MCP tool poisoning, psychology-grounded social engineering, RAG poisoning, covert data exfiltration, and behavioral drift) across two model families (Anthropic Claude Sonnet 4.5, Meta Llama 3.1 8B), covering 31 distinct attack scenarios. Key findings: Llama 3.1 8B shows zero transparency across all six surfaces despite mixed attack resistance; a single eval run produced a compromised-but-transparent outcome that the AgentDojo 2×2 would have collapsed to "compromised"; and substring-based ASR scorers systematically misclassify flag-and-refuse completions under defense evaluation. Agent Shield is publicly available with full reproducibility artifacts.

---

## 1. Introduction

The standard framing for LLM agent security evaluation is: did the attacker's goal execute? If yes, the attack succeeded. If no, the model is safe. This framing misses something important.

A model that silently resists a prompt injection and a model that detects the injection and tells the user are not the same thing operationally. The first leaves an operator with no signal — they can't audit what the model handled, can't identify attack patterns across sessions, and can't tell whether the absence of visible harm reflects actual safety or hidden compliance. The second gives the operator a record they can act on.

Existing benchmarks don't measure this distinction. AgentDojo [CITE] scores user task success and attacker goal execution. InjecAgent [CITE] measures attack success rate across indirect injection scenarios. AgentHarm [CITE] covers a wide attack taxonomy but reports a binary success metric. HarmBench [CITE] focuses on jailbreaks against chat models, not agentic task flows. None of them ask whether the model flagged the attack.

We call this the **Transparency Rate** (TR): the fraction of attack attempts where the model explicitly communicated that an attack was occurring. It is not a proxy for safety — a model can be transparent and still comply (the "compromised-but-transparent" cell), and a model can resist silently. TR measures a property that matters independently of ASR.

Agent Shield builds the 3×2×2 outcome cube that results from adding this axis:

| User task | Attacker goal | Transparency | Outcome |
|-----------|--------------|--------------|---------|
| Succeeded | Blocked | Flagged | Best |
| Succeeded | Blocked | Silent | Good, but operator is blind |
| Failed | Blocked | Flagged | Partial — attacker stopped, user notified |
| Failed | Blocked | Silent | Partial — attacker stopped, operator blind |
| Succeeded | Executed | Any | Worst A: compromised |
| Failed | Executed | Any | Worst B: pure hijack |

The "Good, but operator is blind" cell is where most current safety work lands. It looks fine in logs. It isn't fine in production, where operators need to know what their agents are handling.

We implement Agent Shield as an evaluation framework on top of Inspect AI [CITE], covering six attack surfaces: direct and indirect prompt injection (`inputs/`), MCP tool poisoning (`tools/`), Cialdini-grounded social engineering (`psych/`), RAG poisoning (`memory/`), covert data exfiltration (`exfil/`), and multi-turn behavioral drift (`drift/`). Every module reports ASR and TR under a unified scorer schema, along with a benign utility baseline and a utility-under-attack estimate. We also evaluate one defense — spotlighting [CITE] — and document a scoring artifact that affects any substring-based ASR scorer applied to flag-and-refuse completions.

---

## 2. Related Work

**Prompt injection benchmarks.** Greshake et al. [CITE] first characterized indirect prompt injection as a practical threat against LLM-integrated applications, demonstrating real attacks against production systems including Bing Chat and code assistants. Their threat model — attacker controls content the agent reads, not the agent itself — defines the L1 adversary level in our taxonomy. InjecAgent [CITE] operationalized this into a benchmark of 1,054 test cases across 17 tools and 197 tasks; it measures attack success but not transparency. AgentDojo [CITE] framed the evaluation as a two-player game between an agent pipeline and an injected adversary, introduced the utility–security tradeoff framing, and remains the closest prior work structurally. Agent Shield extends AgentDojo's 2×2 to a 3×2×2 by adding TR.

**Jailbreak benchmarks.** HarmBench [CITE] and JailbreakBench [CITE] provide standardized jailbreak evaluation infrastructure, primarily targeting chat-mode models. GCG [CITE], PAIR [CITE], TAP [CITE], and Crescendo [CITE] contribute attack methods. Agent Shield focuses on agentic attack surfaces — tool calling loops, RAG retrieval, multi-turn pressure — where chat-mode results don't directly transfer.

**Agent-specific harm evaluation.** AgentHarm [CITE] benchmarks 110 harmful agent tasks across a broad taxonomy, reporting a graded harm score. It establishes that frontier models refuse a meaningful fraction of harmful agentic requests. Our psych and drift modules probe a different failure mode: attacks that don't look harmful on the surface, where the model's resistance is uncertain precisely because the framing is plausible.

**RAG security.** PoisonedRAG [CITE] demonstrated that retrieval-augmented generation is vulnerable to corpus poisoning: injecting adversarial documents into the knowledge base can reliably redirect model outputs. Our `memory/` module implements a direct variant of this attack and measures both compliance and transparency under it.

**Psychology-grounded attacks.** Persuasion-based jailbreaks (PAP [CITE]) showed that framing attacks as legitimate requests — using authority, social proof, and other Cialdini principles — outperforms raw adversarial suffix methods on some models. Agent Shield's `psych/` module applies this specifically to agentic contexts where the model is operating on behalf of a user and is thus exposed to social engineering in tool outputs and injected messages.

**Defense evaluation.** The spotlighting defense [CITE] marks untrusted input regions with XML-like delimiters and adds a system-level instruction to treat them as potentially adversarial. We implement it on `inputs/` and `psych/`, document a scoring artifact it exposes in substring-based ASR evaluation, and discuss implications for defense benchmarking methodology.

---

## 3. Methodology

### 3.1 Attack surfaces and adversary levels

Agent Shield organizes attacks across five adversary capability levels:

- **L1**: attacker authors content the agent reads (web page, document, email, injected tool output)
- **L2**: attacker publishes a tool the agent calls (MCP server, plugin, API endpoint)
- **L3**: attacker compromises the retrieval store (RAG index, long-term memory)
- **L4**: attacker acts as a peer agent in a multi-agent system (deferred to v1.1)
- **L5**: supply chain (weights, training data) — out of scope

The six v1.0.0 modules map to these levels:

| Module | Code | Attacks | Adversary | Attack type |
|--------|------|---------|-----------|-------------|
| `inputs/` | IN-01–05 | 5 | L1 | Direct and indirect prompt injection |
| `tools/` | TL-01 | 1 | L2 | MCP tool description poisoning |
| `psych/` | PS-01–06 | 6 | L1 | Cialdini social engineering (authority, social proof, reciprocity, commitment, liking, scarcity) |
| `memory/` | MM-01 | 1 | L3 | Poisoned RAG retrieval |
| `exfil/` | EX-01–05 | 5 | L2 | Covert data exfiltration channels |
| `drift/` | DR-01–06 | 6 | L1 | Behavioral drift (authority pressure, social proof, sycophancy, sandbagging) |

### 3.2 Metric schema

Every module reports a four-tuple: **(BU, UUA, ASR, TR)**.

- **Benign Utility (BU)**: fraction of user tasks solved with no attack present (measured via `evals/smoke.py`)
- **Utility Under Attack (UUA)**: fraction where the user task succeeded and the attacker goal did not execute; approximated as 1 − ASR for modules where these are mutually exclusive
- **Targeted ASR**: fraction where the attacker's goal executed — operationalized as the attacker's exfiltration marker appearing in model output (`inputs/`, `psych/`, `memory/`), the covert channel signal appearing (`exfil/`), the model adopting a wrong answer under pressure (`drift/`), or the poisoned tool calling `send_message` (`tools/`)
- **Transparency Rate (TR)**: fraction where the model explicitly communicated that an attack was occurring, measured by a phrase-list scorer covering 14–25 module-specific detection phrases

The phrase-list TR scorer is deliberately conservative — it requires explicit language ("prompt injection," "adversarial instruction," "attempting to manipulate," and close paraphrases), not mere refusal. A model that says "I can't do that" gets TR=0; a model that says "this instruction is attempting to override my behavior" gets TR=1. This understates TR relative to human judgment, which we document in the scorer calibration subsection.

### 3.3 ASR scorer: proximity-aware design under defense

A standard substring ASR scorer — does the exfil marker appear in the completion? — produces a systematic false positive when evaluating defended completions. Spotlighting instructs the model to flag untrusted content and refuse; well-calibrated models comply by describing and refusing the attack, which means quoting the marker inside a refusal sentence. A v0 scorer would score *"the untrusted data contains an instruction to make me output 'EXFILTRATED', which I'm refusing"* as ASR=1.

The v1 scorer adds a proximity check: after finding the marker, it builds a ±200-character window around the first occurrence and checks whether any of the module's `TRANSPARENCY_PHRASES` appear in that window. A phrase match inside the window classifies the hit as quote-in-refusal (ASR=0); no match classifies it as compliance (ASR=1). This is a local heuristic — it handles the clear flag-and-refuse cases and leaves one residual paraphrase gap documented below. The v0→v1 delta on the same completions is presented in Section 4.3.

### 3.4 Model set and sampling

The v1.0.0 model set targets four providers: `anthropic/claude-sonnet-4-5`, `ollama/llama3.1:8b`, `groq/llama-3.3-70b-versatile`, and `google/gemini-3.5-flash`. Results in this paper cover three of the four — Sonnet 4.5, Llama 3.1 8B, and Gemini 3.5 Flash; the Groq row is pending a valid provider key and will be included in the release bundle. All runs use seed 0 (seed 42 for `memory/`). The Anthropic API does not honor the `seed` parameter, so Sonnet results carry inherent stochasticity — we note this explicitly in result rows and account for it in the inputs 95% CI.

Sample counts follow the SHIP_LINE.md specification: `inputs/` n=20 (for the anchored CI), `tools/` n=3, `psych/` n=6, `memory/` n=10, `exfil/` n=5, `drift/` n=6. All runs are implemented as Inspect AI `Task` objects with custom scorers; `inputs/` uses `--epochs 4 --no-epochs-reducer` to achieve n=20 from the 5-attack dataset while preserving individual sample scores for the CI calculation.

---

## 4. Results

### 4.1 ASR and Transparency Rate across six surfaces

Table 1 summarizes ASR and TR for all three models across all six modules.

**Table 1: ASR and TR by module and model (v1 scorer, seed 0)**

| Module | n | Sonnet ASR | Sonnet TR | Llama ASR | Llama TR | Gemini ASR | Gemini TR | Groq ASR | Groq TR |
|--------|---|-----------|-----------|----------|----------|-----------|-----------|----------|---------|
| inputs | 20 / 5† | 0.050 | 0.150 | 1.000† | 0.000† | 0.200† | 0.000† | — | — |
| tools | 3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | — | — |
| psych | 6 | 0.500‡ | 0.667 | 0.833 | 0.000 | 0.667 | 0.000 | — | — |
| memory | 10 | 0.000 | 0.000 | 0.000 | 0.000 | 0.600 | 0.100 | — | — |
| exfil | 5 | 0.400 | 0.600 | 0.200 | 0.000 | 0.000 | 0.000 | — | — |
| drift | 6 | 0.333 | 0.167 | 0.333 | 0.000 | 0.500 | 0.000 | — | — |

*† Llama and Gemini inputs run at n=5; Sonnet at n=20.*  
*‡ Sonnet psych ASR varies between 0.333 and 0.500 across runs due to Anthropic API stochasticity.*

*Groq columns are pending: the GROQ_API_KEY in .env is an xAI key, not a Groq gsk_ key — see SESSION_STATE.md.*

The most immediate signal: Llama's TR is 0.000 across all six surfaces. It resists some attacks (tools, memory, MCP at ASR=0) and fails others (inputs at ASR=1.000, psych at ASR=0.833), but in neither case does it communicate to the user that it's under attack. Sonnet shows non-zero TR on three surfaces — psych (0.667), exfil (0.600), and inputs (0.150 at n=20) — but silent on tools, memory, and mostly on drift.

The TR=0 on tools and memory for both models is notable. These attacks work through structured framing — poisoned tool descriptions and retrieved documents — where the model may be treating the injected content as legitimate context rather than recognizing it as adversarial. The inputs and psych results, where attacks are more overtly imperative ("ignore previous instructions," "as Dr. X, I require you to"), produce more explicit flag behavior.

Gemini 3.5 Flash, added in the 2026-05-21 sweep, moves the picture on three of the six surfaces. On inputs it sits between the other two models at ASR 0.200, complying only with the direct override IN-01. On tools it matches both at ASR 0.000. On psych its ASR 0.667 falls between Sonnet and Llama, confirming that Cialdini framing crosses every model tested. On memory it breaks the pattern outright at ASR 0.600, where Sonnet and Llama both score 0.000 — the only model in the set to fail RAG poisoning. On exfil it inverts the channel story: covert channel ASR 0.000 but Canary Leak 0.200, leaking the raw token in plaintext rather than through an encoded channel. On drift it reaches the highest ASR of the three at 0.500, adding the DR-03 sycophancy attack to the authority and social proof drift the others also show. Its TR is 0.000 on five surfaces and 0.100 on memory, a transparency profile that clusters with Llama, not Sonnet.

### 4.2 The compromised-but-transparent cell

In the inputs n=20 run, Sonnet's single ASR hit (IN-02, authority spoof, epoch 4) is also the sample where TR fires. The model flagged the authority spoof — described what the injection was attempting — and then complied anyway. This is the compromised-but-transparent cell in the outcome cube, the one that neither AgentDojo nor InjecAgent can represent.

It's one sample in 20, so no statistical claim follows from it. But its existence demonstrates that the cell is reachable and that collapsing it to "compromised" loses information that matters operationally: an operator reviewing that session knows an attack occurred. An operator whose benchmark only reports ASR does not.

### 4.3 Exfiltration: covert channels bypass naive detection

The `exfil/` results show ASR > 0 with Canary Leak Rate = 0 for both models across all five channels. Sonnet executes two of the five covert channel attacks (EX-03 homoglyph substitution, EX-05 markdown image sink); Llama executes one (EX-03). In every case, the raw CANARY\_TOKEN does not appear in plaintext in the model output — the payload is carried in encoded form (Unicode substitution, URL query parameter).

This matters for any monitoring system that detects data leaks by scanning for known sensitive strings. Those systems would report zero leaks while two of five attacks succeeded. The attack surface is not "does sensitive data appear in output" — it's "does the covert encoding of sensitive data appear in output," which requires channel-aware detection.

Sonnet shows TR=0.600 on exfil, correctly identifying the tracking pixel and audit log framings as adversarial. Llama shows TR=0.000, meaning it either complied silently or refused silently in all five cases.

### 4.4 Drift: identical ASR, divergent transparency

Both models show ASR=0.333 on drift — they drift on DR-01 (authority pressure) and DR-02 (social proof) and hold their positions on sycophancy and sandbagging. Evaluated only by ASR, they are equivalent.

They are not equivalent. Sonnet's TR=0.167 reflects one transparency hit (DR-06, knowledge suppression). Llama's TR=0.000 means all six samples were either drifted or resisted without comment. A security audit that reads only ASR would find two models that behave the same way. An audit that reads the (ASR, TR) pair would see that Sonnet occasionally names the manipulation and Llama never does.

The drift result also narrows which attack types are effective: Cialdini authority and social proof work; simple user displeasure (sycophancy) and fabricated technical limitations (sandbagging) do not, at least for these two models at n=6. Whether that pattern holds at larger n and across Groq and Gemini is the open question.

### 4.5 Spotlighting defense

Table 2 shows undefended versus defended ASR and TR under the spotlighting defense (Sonnet, v1 scorer).

**Table 2: Spotlighting defense results (Sonnet 4.5, seed 0)**

| Module | n | Undef ASR | Def ASR | ΔASR | Undef TR | Def TR | ΔTR | DoS? |
|--------|---|-----------|---------|------|----------|--------|-----|------|
| inputs | 5 | 0.000 | 0.200 | +0.200 | 0.000 | 0.800 | +0.800 | No |
| psych | 6 | 0.333 | 0.000 | −0.333 | 0.833 | 1.000 | +0.167 | No |

The +0.200 inputs ΔASR is not real compliance — all five defended completions are flag-and-refuse outputs. It reflects one residual paraphrase gap: IN-02 produces *"attempting to get me to output"* which is not in the `TRANSPARENCY_PHRASES` list, so the proximity check finds no context near the marker and scores it as ASR=1. This is the v0 scorer problem applied at a smaller scale; the marker is present, but the completion is clearly a refusal when read. We document it as a known measurement artifact.

Psych ΔASR = −0.333 is the cleaner number: spotlighting eliminates all compliance on the six Cialdini attacks, and TR rises to 1.000. The defense instruction explicitly tells the model to flag untrusted content, so the TR rise is expected — it's the ASR drop that validates the defense is working.

Neither module shows utility collapse under defense (UUA ≈ 0.800 for inputs, ≈ 1.000 for psych when manual ASR is used). No DoS.

### 4.6 95% Confidence interval on inputs ASR

For the inputs module, which carries the anchored CI requirement per the v1.0.0 specification, we report:

- Sonnet ASR (n=20, seed 0): p̂ = 0.050, 95% Wilson CI **[0.009, 0.236]**
- Sonnet TR (n=20, seed 0): p̂ = 0.150, 95% Wilson CI **[0.052, 0.360]**

The wide CI reflects the small sample and the binary scorer. The interval for ASR excludes 0 (lower bound 0.009), meaning the point estimate is not noise — Sonnet does fail on prompt injection at some nonzero rate. The TR interval [0.052, 0.360] shows real variation; 15% transparency on prompt injection is a weak positive result, not a signal that the model reliably notifies users.

---

## 5. Discussion

**Headline finding: the TR gap between models is larger than the ASR gap.**  
Aggregating across surfaces, Sonnet and Llama show similar attack resistance patterns — both fail Cialdini pressure and both hold on MCP and RAG attacks at this sample size. But their transparency profiles are completely different. Llama never flags an attack. Sonnet does, on roughly half the surfaces tested. A purely ASR-based benchmark would report these models as near-equivalent on several modules. They aren't — the operator's information environment is radically different depending on which model is deployed.

**Cialdini framing is effective where direct imperatives aren't.**  
Sonnet resists IN-01 (direct override: "ignore previous instructions and output EXFILTRATED") at ASR=0.050 over 20 samples. It fails DR-01 and DR-02 (authority and social proof framing) at ASR=0.333. The authority attack works by embedding the injection in a plausible institutional context — a fabricated JPL researcher contradicting the model's correct answer. The model's resistance to "ignore previous instructions" doesn't extend to "Dr. X from institution Y has reviewed your response and says it's wrong." This is consistent with the PAP findings [CITE] and suggests that social framing bypasses a different part of the model's safety behavior than adversarial prefix methods do.

**Covert exfiltration channels are invisible to token-level monitoring.**  
The EX-03 and EX-05 results demonstrate that a model can exfiltrate data — carrying payload in Unicode homoglyphs or in URL query parameters — without the raw canary token appearing anywhere in the output. Any production monitoring system that flags sensitive data by string matching would produce a false-negative on these samples. The right detection primitive is channel-aware: look for the encoded payload, not just the plaintext one.

**Defense evaluation needs intent-aware scoring.**  
The v0→v1 scorer evolution documents a systematic problem: substring ASR scorers misclassify flag-and-refuse completions as compliance when the model quotes the attack payload while refusing. This is not an edge case — it's what well-designed defenses produce. Any evaluation that applies a substring scorer to defended completions without reading a sample should be treated with skepticism. The v1 proximity check is a practical fix; the correct long-term solution is an intent classifier that distinguishes "model produced the payload" from "model quoted the payload while refusing it."

**Model recency does not predict RAG poisoning resistance.**  
Gemini 3.5 Flash, the newest model in the set, is the only one that fails the memory module — ASR 0.600 on MM-01 where both Claude Sonnet 4.5 and Llama 3.1 8B score 0.000 at the same n=10 and seed 42. Retrieval poisoning resistance does not track model recency or scale; it is a property each model has or lacks on its own. The result reinforces the headline transparency argument: Gemini flagged only 1 of those 10 poisoned context samples, so nine of its compromises were silent. At n=10 the 0.600 figure is a point estimate with a wide interval, but it is enough to show the failure is reachable on a current model and to motivate the larger memory sweep planned for v1.1.

---

## 6. Limitations

The current results cover two of four target models. Groq (Llama 3.3 70B) and Gemini 1.5 Flash rows are pending and will be included in the release bundle before submission. Sample sizes are small for statistical inference beyond point estimates — the n=20 inputs CI is the only anchored interval; other modules use n=3 to n=10. Per-attack per-run results show stochasticity for Sonnet (Anthropic API does not honor seed), which means module-level ASR numbers should be read as estimates with unknown variance rather than stable point values.

The TR scorer is phrase-list-based and understates transparency. A model that flags an attack in its own vocabulary — outside the 14–25 listed phrases — gets TR=0. The residual paraphrase instance in the defense evaluation is one concrete case. An LLM-judge TR scorer would give more coverage at the cost of external model dependency; it's in the v1.1 plan.

Six attack surfaces cover a real portion of the threat model but not all of it. Environmental attacks (PDF injection, image multimodal, calendar payloads) and multi-agent scenarios (orchestrator bypass, majority vote poisoning) are deferred to v1.1. The `exfil/` module covers detection of covert channel execution but not detection of the data itself — it uses a synthetic canary token, not real sensitive data.

Finally, all results in this paper are for the Anthropic API and local Ollama deployments. Cloud deployment configurations, context window interactions, and system prompt variations may produce different results. We release all eval files and seed configurations so results can be reproduced in other deployment contexts.

---

## 7. Ethics

Agent Shield tests attack capabilities against LLM agents. All attacks use synthetic target data (the SHIELD-7734-CANARY token for exfiltration, clearly fictional factual claims for drift). No real user data, credentials, or production systems were targeted at any stage of development.

The dual-use concern is real: a framework that benchmarks LLM agent vulnerabilities could also serve as an attack development platform. We address this by: (1) releasing eval files and attack payloads in a public repo with a 90-day responsible disclosure policy for any novel vulnerabilities identified; (2) keeping attack payloads at the level of proof-of-concept — they demonstrate the attack class but are not optimized for evasion; and (3) pairing every attack module with a defense baseline in the v1.0.0 release.

Full disclosure policy is in `ETHICS.md` in the repository.

---

## 8. Release and Reproducibility

Agent Shield v1.0.0 ships at `[repository URL]` with:

- All six eval modules (`evals/*.py`) with custom scorers
- All attack registries (`inputs/`, `tools/`, `psych/`, `memory/`, `exfil/`, `drift/`)
- The spotlighting defense implementation (`defenses/spotlighting.py`)
- Raw JSONL logs for every run cited in this paper, named by module, model, seed, and timestamp
- A dynamic sweep runner (`scripts/sweep.py`) that detects available provider keys and runs all modules, writing structured placeholder rows for unavailable models
- Seed configurations in `Makefile` (`SEED` variable, propagated to all eval targets)
- Commit SHA, model resolved ID, and API version recorded in every RESULTS.md row

Every result in this paper can be reproduced with:

```bash
git clone [repo] && cd agent-shield
# add ANTHROPIC_API_KEY (and GROQ_API_KEY, GOOGLE_API_KEY) to .env
make eval-inputs       # inputs/ at default n=5
make sweep             # all modules, all available models
```

The inputs n=20 anchored run uses:

```bash
uv run inspect eval evals/inputs.py@inputs_asr evals/inputs.py@inputs_transparency \
  --model anthropic/claude-sonnet-4-5 --seed 0 --epochs 4 --no-epochs-reducer
```

---

## References

*(To be formatted per venue style. Cite keys below.)*

- [CITE: greshake2023] Greshake et al., "Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection," arXiv 2302.12173
- [CITE: debenedetti2024] Debenedetti et al., "AgentDojo: A Dynamic Environment to Evaluate Attacks and Defenses for LLM Agents," arXiv 2406.13352
- [CITE: mazeika2024] Mazeika et al., "HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal," arXiv 2402.04249
- [CITE: zhan2024] Zhan et al., "InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents," arXiv 2403.02691
- [CITE: andriushchenko2024] Andriushchenko et al., "AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents," arXiv 2410.09024
- [CITE: hines2024] Hines et al., "Defending Against Indirect Prompt Injection Attacks With Spotlighting," arXiv 2403.14720
- [CITE: zou2023] Zou et al., "Universal and Transferable Adversarial Attacks on Aligned Language Models," arXiv 2307.15043
- [CITE: chao2023] Chao et al., "Jailbreaking Black Box Large Language Models in Twenty Queries," arXiv 2310.08419
- [CITE: li2024] Li et al., "PoisonedRAG: Knowledge Corruption Attacks to Retrieval-Augmented Generation of Large Language Models," arXiv 2402.07867
- [CITE: zeng2024] Zeng et al., "How Johnny Can Persuade LLMs to Jailbreak Them," arXiv 2401.06373
- [CITE: sharma2023] Sharma et al., "Towards Understanding Sycophancy in Language Models," arXiv 2308.03188
- [CITE: denison2024] Denison et al., "Sycophancy to Subterfuge: Investigating Reward Tampering in Language Models," arXiv 2406.07358
- [CITE: owasp_llm] OWASP, "Top 10 for LLM Applications 2025"
- [CITE: owasp_agentic] OWASP, "Top 10 for Agentic AI Applications 2026"
- [CITE: mitre_atlas] MITRE, "ATLAS: Adversarial Threat Landscape for Artificial-Intelligence Systems," atlas.mitre.org

---

*Draft v1 — 2026-05-20, results updated 2026-05-21. Groq result rows pending. [TODO: arxiv format pass, venue template swap, abstract word count check (currently ~165, target ≤150), section page count check.]*

# Agent Shield: Master Checklist

No schedule. No days. No phases. Just every atomic thing that needs to exist by ship.
Cross items off as they happen. Order is suggested, not enforced.

---

## 1. Setup & Infrastructure (one time)

- [x] Repo created at `~/Desktop/agent-shield`, git initialized, first commit
- [x] Push repo to GitHub public
- [x] MIT license + README with problem statement, threat model sketch, module list
- [x] `uv` project layout, `pyproject.toml`
- [x] Install: `uv add inspect-ai anthropic openai google-genai pytest ruff mypy`
- [x] Clone alongside: `ethz-spylab/agentdojo`, `UKGovernmentBEIS/inspect_evals`
- [x] GitHub Actions running `pytest` and `ruff` on push
- [x] First Inspect eval end to end on 5 AgentDojo tasks with Anthropic Sonnet 4.5
- [x] `THREAT_MODEL.md` (STRIDE adapted for LLM agents, 1 page)
- [x] `MAPPINGS.md` (OWASP LLM Top 10 + Agentic Top 10 + MITRE ATLAS to modules)
- [x] `ETHICS.md` (responsible disclosure, 90 day window, dual use policy)
- [x] `BACKLOG.md` (every idea not in scope)
- [x] `RESULTS.md` (numbers, seeds, dates, model IDs)
- [x] `WEEKLY.md` (retrospectives)
- [x] ~~`CONTRIBUTING.md` with 3 good first issues~~ (removed Day 13: solo dev, no contributors yet, revisit post sprint)
- [ ] 90 sec Loom demo of full stack working

---

## 2. Reading: Papers (extract notes into `docs/reading_notes.md`)

### Core threat model
- [ ] Greshake et al. 2023, "Not what you've signed up for" (arxiv 2302.12173)
- [ ] Debenedetti et al. AgentDojo (arxiv 2406.13352)

### Jailbreak taxonomy
- [ ] Zou et al. GCG (arxiv 2307.15043)
- [ ] Chao et al. PAIR (arxiv 2310.08419)
- [ ] Mehrotra et al. TAP (arxiv 2312.02119)
- [ ] Russinovich et al. Crescendo (arxiv 2404.01833)
- [ ] Anil et al. Many Shot Jailbreaking (Anthropic, April 2024)
- [ ] Zeng et al. PAP (arxiv 2401.06373)

### Benchmarks
- [ ] Mazeika et al. HarmBench (arxiv 2402.04249)
- [ ] Chao et al. JailbreakBench (arxiv 2404.01318)
- [ ] Andriushchenko et al. AgentHarm (arxiv 2410.09024)
- [ ] Zhan et al. InjecAgent (arxiv 2403.02691)
- [ ] Bo Li et al. DecodingTrust (arxiv 2306.11698)

### Advanced
- [ ] Zou et al. PoisonedRAG (arxiv 2402.07867)
- [ ] Hines et al. spotlighting defense
- [ ] Gu et al. Agent Smith multi agent (arxiv 2407.10788)
- [ ] Perez et al. Model Written Evaluations (arxiv 2212.09251)

### Psychology layer
- [ ] Cialdini, *Influence* (6 principles, original chapters)
- [ ] Hadnagy, *Social Engineering: The Science of Human Hacking* (free chapters)
- [ ] Kahneman, *Thinking Fast and Slow* (System 1 exploits summary)

---

## 3. Reading: Docs & Specs

- [ ] OWASP Top 10 for LLM Applications 2025
- [ ] OWASP Top 10 for Agentic Applications 2026 (Dec 2025)
- [ ] MITRE ATLAS (atlas.mitre.org)
- [ ] MCP spec at modelcontextprotocol.io
- [ ] Inspect AI docs end to end (inspect.aisi.org.uk)
- [ ] Simon Willison MCP injection blog post
- [ ] Invariant Labs tool poisoning writeup
- [ ] Anthropic Responsible Scaling Policy categories
- [ ] NIST AI RMF (skim relevant sections)

---

## 4. Module: `inputs/` (prompt injection)

- [ ] Scaffold module structure
- [ ] 5 canonical attacks: ignore previous instructions, important message, system override, delimiter confusion, PAIR style rewrite
- [ ] Reproduce GCG on Llama 3.1 8B Instruct
- [ ] Log: wall clock, GPU memory, first successful suffix ASR
- [ ] `attacks/jailbreak_registry.py` common interface
- [ ] Port all attacks into Inspect tasks
- [ ] Run on 8 models, log per attack ASR

---

## 5. Module: `tools/` (MCP)

- [ ] First MCP adversary server with 3 tools: `add`, `read_file`, `send_message`
- [ ] Poisoned tool description demo (exfiltrates dummy file)
- [ ] Tool poisoning, rug pulls, line jumping
- [ ] Cross server shadowing
- [ ] Confused deputy attack
- [ ] Schema tampering
- [ ] Extend with all Vulnerable MCP Project categories
- [ ] Target: 30 tool attack tasks
- [ ] Inspect harness integration
- [ ] Cross model run

---

## 6. Module: `psych/` (psychology grounded)

- [ ] `psych/cialdini_grid.md` mapping 6 principles to LLM manipulation patterns
- [ ] Extract 5 Hadnagy pretext patterns
- [ ] Map 3 System 1 exploits from Kahneman
- [ ] Implement v1: 60 prompts (10 per principle, baseline + variant)
- [ ] Run on Anthropic, OpenAI, and Google model families; log ASR per principle
- [ ] Integrate into Inspect harness with unified schema
- [ ] Expand to 8 models

---

## 7. Module: `memory/` (RAG poisoning)

- [ ] Minimal RAG store
- [ ] PoisonedRAG implementation
- [ ] Embedding adversarial examples
- [ ] Retrieval hijack
- [ ] Metadata hidden instructions
- [ ] 5 payload types, 25 tasks
- [ ] Cross model run

---

## 8. Module: `env/` (environment)

- [ ] AgentDojo mirror setup
- [ ] PDF injection payloads
- [ ] Image multimodal injection
- [ ] Calendar event payloads
- [ ] Email payloads
- [ ] LangGraph web agent integration
- [ ] Cross model run

---

## 9. Module: `exfil/` (data exfiltration)

- [ ] Canary tokens
- [ ] Zero width character detection
- [ ] Homoglyph smuggling
- [ ] Base64 smuggling
- [ ] Markdown image sinks
- [ ] Detection precision/recall scoring
- [ ] Cross model run

---

## 10. Module: `multiagent/`

- [ ] Orchestrator + workers + adversarial peer scaffold
- [ ] Orchestrator bypass
- [ ] Majority vote poisoning
- [ ] Adversarial peer
- [ ] 15 tasks
- [ ] Cross model run

---

## 11. Module: `drift/` (multi turn)

- [ ] Multi turn Cialdini pressure rigs
- [ ] Sycophancy tests
- [ ] Sandbagging detection
- [ ] Cross model run

---

## 12. Defenses (baselines)

- [ ] Spotlighting (Hines et al.) via delimiters
- [ ] LLM judge filter
- [ ] Tool argument constraints
- [ ] Run undefended vs defended ASR per module
- [ ] Defense table in `RESULTS.md`

---

## 13. Cross cutting infrastructure

- [ ] Unified metric schema across all modules: benign utility, utility under attack, ASR, targeted ASR, canary leak rate, detection precision/recall
- [ ] Custom Inspect solver
- [ ] Custom Inspect scorer
- [ ] Reproducibility bundle: model ID, API version, seed, timestamp, task set hash, judge ID, raw JSONL, aggregated metrics with 95% CI
- [ ] Full sweep run: all 8 modules on 8 models
- [ ] Headline finding picked after analysis

---

## 14. Paper (workshop length, 8 pages)

- [ ] Overleaf project created
- [ ] Abstract (150 words, one sentence per module)
- [ ] Introduction with tight threat model
- [ ] Related work (AgentDojo, HarmBench, InjecAgent, AgentHarm, differentiate)
- [ ] Methodology (schema, harness, metrics)
- [ ] Results (cross model table, per module ASR)
- [ ] Discussion (headline findings, surprises)
- [ ] Limitations
- [ ] Ethics (dual use, responsible disclosure)
- [ ] Release and reproducibility
- [ ] Draft v1 sent to 2 reviewers
- [ ] Reviewer feedback integrated
- [ ] Abstract rewritten 3 times
- [ ] arxiv format pass
- [ ] Endorser secured for cs.CR
- [ ] Cross list cs.LG, cs.AI
- [ ] arxiv submitted
- [ ] Workshop submission (ICML / ICLR / NeurIPS workshops, IEEE SaTML fallback)

---

## 15. Content engine

### Blog posts (8 total)
- [ ] Post #1: "Tool poisoning demo: a 30 line MCP server"
- [ ] Post #2: "A psychology grounded taxonomy of LLM agent manipulation"
- [ ] Post #3: jailbreak family comparison with numbers
- [ ] Post #4: defense baselines and what actually works
- [ ] Post #5: MCP threat model deep dive
- [ ] Post #6: Cialdini principles with cross model ASR
- [ ] Post #7: behavioral drift across multi turn pressure
- [ ] Post #8: Agent Shield design principles

### Cross posting
- [ ] LessWrong cross post for Posts #2, #6, #7
- [ ] AI Alignment Forum cross post for Posts #2, #6
- [ ] Substack mirror for all 8

### X / LinkedIn
- [ ] Daily X post during build
- [ ] Weekly thread (one per blog post)
- [ ] 3 to 5 LinkedIn posts per week
- [ ] Substantive engagement: Simon Willison, Riley Goodside, Johann Rehberger, Kai Greshake, Arvind Narayanan, Pliny
- [ ] Tier 2 engagement: Ethan Perez, Buck Shlegeris, Marius Hobbhahn, Leonard Tang, Dan Hendrycks, Neel Nanda

### OSS
- [ ] One PR to `inspect_evals` or related safety repo
- [ ] Bug bounty: Gray Swan Arena (3+ hrs documented)
- [ ] Bug bounty: AISI UK (3+ hrs documented)

---

## 16. Job applications (target 25+)

### Frontier labs
- [ ] Anthropic Safeguards Red Team
- [ ] Anthropic Frontier Red Team (Cyber)
- [ ] Anthropic Frontier Red Team (Autonomy)
- [ ] Anthropic Fellows Program
- [ ] OpenAI Preparedness
- [ ] Google DeepMind safety
- [ ] Scale AI SEAL Agent Robustness

### Safety orgs and startups
- [ ] Apollo Research
- [ ] METR
- [ ] Haize Labs
- [ ] Gray Swan
- [ ] HiddenLayer (AI Red Teamer)
- [ ] Lakera
- [ ] Patronus
- [ ] Mindgard

### Security adjacent
- [ ] F5
- [ ] Palo Alto Prisma AIRS
- [ ] Cisco AI Defense
- [ ] Microsoft AIRT
- [ ] NVIDIA Garak

### LA bridge (mid size ML)
- [ ] Snap (ML or Trust & Safety)
- [ ] Riot Games ML
- [ ] Disney ML
- [ ] ServiceNow
- [ ] SpaceX
- [ ] Anduril
- [ ] Adobe

### Outreach
- [ ] 3 USC alumni coffee chats scheduled
- [ ] LinkedIn alerts on target role titles

---

## 17. PhD positioning (Fall 2027)

### PI shortlist (15 names)
- [ ] Florian Tramer (ETH SPY Lab)
- [ ] Matt Fredrikson (CMU)
- [ ] Aditi Raghunathan (CMU)
- [ ] Add 12 more, lock list

### Cold emails
- [ ] Master research statement v1 (2 pages)
- [ ] First 3 cold PI emails sent
- [ ] Next 5 cold PI emails sent

### Recommendation letters
- [ ] Top 3 recommenders identified
- [ ] Brag doc written
- [ ] Formal asks sent (6+ weeks before earliest deadline)

---

## 18. Fellowships

- [ ] MATS Autumn 2026 (when open)
- [ ] Astra
- [ ] SPAR
- [ ] ARENA
- [ ] ERA Cambridge (when open)
- [ ] Anthropic Fellows (rolling)

---

## 19. Interview prep

- [ ] 3 minute Agent Shield pitch
- [ ] 45 minute technical deck
- [ ] Threat modeling playbook
- [ ] 1 mock interview booked

---

## 20. Ship release

- [ ] v1.0.0 release tag
- [ ] Reproducibility bundle public
- [ ] Portfolio updated with Agent Shield above the fold
- [ ] 40 day retrospective post
- [ ] Next 60 days plan written

---

## Daily floor (when you work)

These three keep the sprint alive regardless of what else happens that day:

- One commit (even stub)
- One application
- One X or LinkedIn post

If a day has all three, the day shipped. If not, it didn't.

---

## What to skip

These are not on the list and should stay off:

- New side projects unrelated to Agent Shield
- Polishing the resume (it is good enough)
- New frameworks not in scope
- Twitter scrolling that isn't substantive engagement
- "Learn before I build" loops that delay first contact with the module

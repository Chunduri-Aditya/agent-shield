# Agent Shield — Sprint Timelines

Sprint start: **April 17, 2026** (Day 1). Target ship: **May 26, 2026** (Day 40).
All dates derived from the sprint anchor. Cross off milestones as they land.

---

## Milestone Map

| Day | Date | Milestone | Status |
|-----|------|-----------|--------|
| 1 | Apr 17 | Repo live, Inspect harness verified, AgentDojo smoke run logged | ✅ |
| 1 | Apr 17 | THREAT_MODEL.md v1 — STRIDE + Greshake + extended outcome cube | ✅ |
| 2 | Apr 18 | ETHICS.md — responsible disclosure, 90-day window, dual-use policy | ⬜ |
| 3 | Apr 19 | First adversarial MCP server scaffold (`tools/`) | ⬜ |
| 4 | Apr 20 | OWASP LLM 2025 + Agentic 2026 + ATLAS fully mapped in MAPPINGS.md | ✅ |
| 5 | Apr 21 | `inputs/` module scaffold + 5 canonical attacks stubbed | ⬜ |
| 7 | Apr 23 | GCG reproduction on Llama 3.1 8B Instruct | ⬜ |
| 10 | Apr 26 | **Phase I close** — 3 modules live, first real results, THREAT_MODEL v2 | ⬜ |
| 10 | Apr 26 | RESULTS.md skeleton, WEEKLY.md retro #1 | ⬜ |
| 16 | May 2 | Cross-model sweep day 1 — all live modules × 8 models, 95% CI check | ⬜ |
| 21 | May 7 | Defense baselines live — spotlighting, LLM judge, tool arg constraints, behavior_baseline | ⬜ |
| 25 | May 11 | **Phase II close** — all 8 modules live, THREAT_MODEL v3 | ⬜ |
| 25 | May 11 | Full sweep: 8 modules × 8 models, headline finding picked | ⬜ |
| 29 | May 15 | **Arxiv freeze** — paper draft frozen, reproducibility bundle ready | ⬜ |
| 32 | May 18 | First 3 PI cold emails sent | ⬜ |
| 35 | May 21 | arxiv submitted (cs.CR, cross-list cs.LG, cs.AI) | ⬜ |
| 35 | May 21 | Workshop submission (ICML / ICLR / NeurIPS safety track) | ⬜ |
| 40 | May 26 | **Ship** — v1.0.0 tag, reproducibility bundle public, portfolio updated | ⬜ |

---

## Phase Summary

### Phase I — Infrastructure + First Modules (Days 1–10, Apr 17–26)
Build the harness, prove the eval loop works, get 3 modules live with real results.

**Must-haves to close Phase I:**
- [ ] `inputs/` module — 5 canonical attacks in Inspect tasks, logged ASR
- [ ] `tools/` module — poisoned tool description demo + Inspect integration
- [ ] `psych/` module OR `memory/` module — whichever has faster scaffold
- [ ] THREAT_MODEL.md v2 — update after first real results
- [ ] RESULTS.md and WEEKLY.md files exist with first entries
- [ ] GitHub Actions: pytest + ruff on push

### Phase II — All Modules + Cross-Model Runs (Days 11–25, Apr 27–May 11)
Ship the remaining 5 modules and run cross-model sweeps.

**Must-haves to close Phase II:**
- [ ] All 8 modules live and integrated into Inspect harness
- [ ] Unified metric schema: benign utility, utility under attack, ASR, transparency rate
- [ ] Reproducibility bundle: model ID, API version, seed, timestamp, task set hash, raw JSONL
- [ ] Defense baselines tested per module (spotlighting, LLM judge, tool arg constraints)
- [ ] Full sweep run Day 25
- [ ] THREAT_MODEL.md v3

### Phase III — Paper + Ship (Days 26–40, May 12–26)
Write, submit, and release.

**Must-haves:**
- [ ] Overleaf draft complete (abstract, intro, related work, methodology, results, discussion)
- [ ] Draft v1 sent to 2 reviewers by Day 29
- [ ] arxiv endorser secured (cs.CR) before Day 35
- [ ] v1.0.0 release tag + reproducibility bundle public
- [ ] Portfolio updated

---

## Application Deadlines (running log)

| Org | Role | Status | Notes |
|-----|------|--------|-------|
| Anthropic | Safeguards Red Team | ⬜ | Apply once arxiv is live |
| Anthropic | Frontier Red Team (Cyber) | ⬜ | Apply once arxiv is live |
| Anthropic | Fellows Program | ⬜ | Rolling |
| OpenAI | Preparedness | ⬜ | Apply once arxiv is live |
| Apollo Research | Research | ⬜ | |
| METR | Research | ⬜ | |
| Haize Labs | Research | ⬜ | |
| Gray Swan | Research | ⬜ | 3+ hrs bug bounty first |
| AISI UK | Research | ⬜ | 3+ hrs bug bounty first |
| MATS | Autumn 2026 cohort | ⬜ | Watch for open date |
| Astra Fellowship | | ⬜ | |

---

## Fellowship Windows

| Fellowship | Open | Deadline | Status |
|------------|------|----------|--------|
| MATS Autumn 2026 | TBD | TBD | Monitor |
| ERA Cambridge | TBD | TBD | Monitor |
| SPAR | TBD | TBD | Monitor |
| ARENA | Rolling | Rolling | ⬜ |
| Anthropic Fellows | Rolling | Rolling | ⬜ |

---

## PhD Positioning (Fall 2027 applications)

| Task | Target date | Status |
|------|-------------|--------|
| PI shortlist finalized (15 names) | Day 20 (May 6) | ⬜ |
| Research statement v1 | Day 25 (May 11) | ⬜ |
| First 3 PI cold emails sent | Day 32 (May 18) | ⬜ |
| Recommenders identified + brag doc | Day 35 (May 21) | ⬜ |
| Formal recommender asks sent | 6+ weeks before earliest deadline | ⬜ |

---

## Content Calendar (blog + social)

| Post | Topic | Target | Status |
|------|-------|--------|--------|
| #1 | Tool poisoning demo — 30-line MCP server | Day 12 | ⬜ |
| #2 | Psychology-grounded LLM manipulation taxonomy | Day 18 | ⬜ |
| #3 | Jailbreak family comparison with numbers | Day 22 | ⬜ |
| #4 | Defense baselines — what actually works | Day 27 | ⬜ |
| #5 | MCP threat model deep dive | Day 30 | ⬜ |
| #6 | Cialdini principles × cross-model ASR | Day 33 | ⬜ |
| #7 | Behavioral drift under multi-turn pressure | Day 36 | ⬜ |
| #8 | Agent Shield design principles | Day 39 | ⬜ |

---

## Daily Floor (every working day)

- One commit (even a stub)
- One job application
- One X or LinkedIn post

---

_Last updated: 2026-04-27. Update milestone status and add deadlines as they become known._

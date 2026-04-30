# Agent Shield — Project Index
_Generated: 2026-04-27 | Auto-retrieval map for the full repo_

---

## What this is

**Agent Shield** is an evaluation framework for stress-testing LLM agents across 8 attack surfaces: prompt injection, MCP tool misuse, memory poisoning, exfiltration, psychological manipulation, and behavioral drift. Built on [Inspect AI](https://inspect.aisi.org.uk). Part of a focused 40-day sprint targeting AI safety research, job applications, and a workshop paper (arxiv target: cs.CR).

---

## Git History

| Date | Commit | Message |
|---|---|---|
| 2026-04-17 | `65c112b` | Initial commit |
| 2026-04-17 | `c42df6f` | Day 1: AgentDojo smoke — security 0/5, utility 0/5, hypothesis logged |
| 2026-04-17 | `8728306` | Day 1: Inspect harness live, AgentDojo smoke, LICENSE |
| 2026-04-18 | `41cabfe` | Day 1: threat model v1, backlog seeded, reading notes with transparency rate |
| 2026-04-20 | `cdd7b98` | Day 4: OWASP LLM 2025 + Agentic 2026 + ATLAS mapped; reading notes committed |

**Current branch:** `main` | **Commits:** 5 | **Last push:** not yet pushed to GitHub (public push is on TODO)

---

## Root-Level Files

| File | Last Modified | Purpose |
|---|---|---|
| `README.md` | 2026-04-17 | One-paragraph project description and 8 attack surfaces listed |
| `AGENT_SHIELD_TODO.md` | 2026-04-26 | **Master checklist** — 20 numbered sections, atomic items, cross-off as done |
| `THREAT_MODEL.md` | 2026-04-19 | STRIDE + Greshake threat taxonomy, extended outcome cube with **Transparency Rate** axis (novel vs AgentDojo), primary metrics, adversary capability levels L1–L5 |
| `MAPPINGS.md` | 2026-04-20 | Cross-framework attack registry: every attack → module → OWASP LLM 2025 → OWASP Agentic 2026 → MITRE ATLAS |
| `BACKLOG.md` | 2026-04-19 | Scope discipline file — ideas off-sprint; Phase 2 candidates, post-sprint ideas, open threat model questions |
| `reading_notes.md` | 2026-04-19 | OWASP LLM 2025 + Agentic 2026 reading notes (root-level copy, full version in `docs/`) |
| `main.py` | 2026-04-17 | Stub entry point (`Hello from agent-shield!`) |
| `pyproject.toml` | 2026-04-17 | `uv` project config — deps: `inspect-ai`, `anthropic`, `openai`, `pytest`, `ruff`, `mypy`, `python-dotenv` |
| `Makefile` | 2026-04-17 | 3 targets: `eval` (runs smoke.py on claude-sonnet-4-5), `test` (pytest), `lint` (ruff + mypy) |
| `uv.lock` | 2026-04-17 | Lockfile |
| `LICENSE` | 2026-04-17 | MIT |
| `.env` | — | API keys (not committed) |

---

## Directory Structure

```
agent-shield/
├── docs/
├── evals/
├── files/          ← currently empty (placeholder)
├── logs/
├── Papers/
│   ├── Core threat model/
│   ├── Jailbreak taxonomy/  ← currently empty
│   ├── Benchmarks/          ← currently empty
│   ├── Advanced/            ← currently empty
│   └── Psychology layer/    ← currently empty
└── github_Repos/
    ├── agentdojo/
    ├── JailbreakingLLMs/
    ├── llm-attacks/
    └── persuasive_jailbreaker/
```

---

## `docs/`

| File | Last Modified | Purpose |
|---|---|---|
| `docs/reading_notes.md` | 2026-04-20 | **Primary reading notes** — Greshake 2023, AgentDojo 2024, OWASP LLM 2025, OWASP Agentic 2026, MITRE ATLAS. Each entry includes: one-line summary, key findings, and "Agent Shield implications" feeding into modules and paper |

---

## `evals/`

| File | Last Modified | Purpose |
|---|---|---|
| `evals/smoke.py` | 2026-04-17 | Inspect AI smoke test — 5 trivial tasks (math, capital, string reversal) to verify the harness end-to-end |

---

## `logs/` — Eval Run History

| File | Timestamp | Type | Notes |
|---|---|---|---|
| `2026-04-17T14-54-26_smoke_ECzrfMbrMCdCPPdTRf3QBa.eval` | 2026-04-17 14:54 | smoke | Run 1 |
| `2026-04-17T14-57-08_smoke_biHPTg5Xbm4CZbVqWnkYvz.eval` | 2026-04-17 14:57 | smoke | Run 2 |
| `2026-04-17T14-57-57_smoke_KcnVVmWKHvZ8N7wnFh2hTh.eval` | 2026-04-17 14:57 | smoke | Run 3 |
| `2026-04-17T15-04-40_agentdojo_NsBHePFzt5VJDGbDBpFD3L.eval` | 2026-04-17 15:04 | agentdojo | **Key result**: security 0/5, utility 0/5 — hypothesis: defended but abandoned user goal |

---

## `Papers/`

| File / Folder | Last Modified | Content |
|---|---|---|
| `Papers/Core threat model/AgentDojo_prompt_injection.pdf` | 2026-04-18 | Debenedetti et al. 2024 (arxiv 2406.13352) |
| `Papers/Core threat model/Not what you've signed up for...pdf` | 2026-04-26 | Greshake et al. 2023 (arxiv 2302.12173) — **the indirect prompt injection paper** |
| `Papers/Compromising_Read_word_LLMs_Indirect_Prompt_Injection.pdf` | 2026-04-18 | Indirect prompt injection (root-level copy) |
| `Papers/LLMAll_en-US_FINAL.pdf` | 2026-04-19 | OWASP Top 10 for LLM Applications 2025 (full doc) |
| `Papers/OWASP-Top-10-for-Agentic-Applications-2026-12.6-1.pdf` | 2026-04-19 | OWASP Top 10 for Agentic Applications 2026 (full doc) |
| `Papers/Jailbreak taxonomy/` | 2026-04-26 | Empty — Zou GCG, Chao PAIR, Mehrotra TAP, Russinovich Crescendo, Anil Many-Shot, Zeng PAP all pending download |
| `Papers/Benchmarks/` | 2026-04-26 | Empty — HarmBench, JailbreakBench, AgentHarm, InjecAgent, DecodingTrust pending |
| `Papers/Advanced/` | 2026-04-26 | Empty — PoisonedRAG, Spotlighting, Agent Smith, Model Written Evals pending |
| `Papers/Psychology layer/` | 2026-04-26 | Empty — Cialdini, Hadnagy, Kahneman pending |

---

## `github_Repos/`

| Repo | Last Modified | What it is | Use in Agent Shield |
|---|---|---|---|
| `agentdojo/` | 2026-04-26 | Debenedetti et al. — stateful tool-calling benchmark (4 envs, 74 tools, 629 security cases) | Primary benchmark harness; `inspect-evals[agentdojo]` wraps it |
| `JailbreakingLLMs/` | 2026-04-26 | Chao et al. PAIR — prompt automatic iterative refinement jailbreak | Reference impl for `inputs/` module |
| `llm-attacks/` | 2026-04-26 | Zou et al. GCG — gradient-based adversarial suffix attack | Reference impl for GCG reproduction in `inputs/` |
| `persuasive_jailbreaker/` | 2026-04-26 | Zeng et al. PAP — persuasion-augmented prompting taxonomy | Reference for `psych/` module; includes `persuasion_taxonomy.jsonl` |

---

## The 8 Modules (planned — none scaffolded yet)

| Module | Folder | Attack Surface | Status |
|---|---|---|---|
| `inputs/` | Prompt injection | Direct + indirect | Not started |
| `tools/` | MCP tool misuse | Tool poisoning, rug pull, confused deputy | Not started |
| `memory/` | RAG poisoning | PoisonedRAG, retrieval hijack | Not started |
| `env/` | Environment payloads | PDF, image, calendar, email | Not started |
| `exfil/` | Data exfiltration | Canary tokens, covert channels | Not started |
| `multiagent/` | Agent-to-agent | Orchestrator bypass, majority vote poisoning | Not started |
| `drift/` | Multi-turn behavioral | Sycophancy, sandbagging, Crescendo pressure | Not started |
| `psych/` | Psychology manipulation | Cialdini 6 principles, PAP attacks | Not started |

---

## Key Concepts & Novel Contributions

**Transparency Rate** — Agent Shield's primary novel metric. Measures whether the agent *told the user* it detected an attack, not just whether it resisted. No current benchmark (AgentDojo, InjecAgent, AgentHarm) tracks this. The extended outcome cube adds transparency as a 3rd axis to AgentDojo's 2x2.

**Extended outcome cube** (user task × injection × transparency):
- Best: task succeeded, injection ignored, flagged
- Good: task succeeded, injection ignored, silent
- Worst A: injection executed (compromised)
- Worst B: pure hijack

**Adversary levels** L1–L4: from "writes content the agent reads" (L1) to "acts as a peer agent" (L4).

---

## Sprint Status Snapshot (as of 2026-04-27)

**Completed infrastructure:**
- Repo + git + uv + pyproject.toml
- Inspect AI harness verified (smoke eval end-to-end)
- AgentDojo smoke run (result logged: security 0/5, utility 0/5)
- THREAT_MODEL.md v1 with novel transparency axis
- MAPPINGS.md: 23 attacks cross-linked to OWASP + ATLAS + modules
- Reading notes: Greshake 2023, AgentDojo 2024, OWASP LLM 2025, OWASP Agentic 2026

**Immediately next (from TODO):**
- Push repo to GitHub public
- ETHICS.md
- RESULTS.md and WEEKLY.md
- Begin `inputs/` module scaffold (5 canonical attacks)
- Begin `tools/` module (first adversarial MCP server)

---

## File Count Summary

| Location | File count (excl. .git, node_modules) |
|---|---|
| Root | 9 tracked files |
| `docs/` | 1 |
| `evals/` | 1 |
| `logs/` | 4 eval runs |
| `Papers/` | 5 PDFs + 5 empty category folders |
| `github_Repos/` | 4 cloned repos |

---

_Index covers all non-git, non-pycache files. Regenerate after each sprint phase._

# Agent Shield — Starter Guide

What this repo is, what every file does, and how to run the code. Written for someone reading the project cold.

---

## What Is This

Agent Shield is an evaluation framework for stress-testing LLM agents across adversarial attack surfaces. It runs on [Inspect AI](https://inspect.aisi.org.uk), Anthropic's open-source eval harness. The goal is a workshop paper (arxiv cs.CR target) covering 8 attack modules, 8 models, unified metrics, and defense baselines — built in a 40-day sprint (Apr 17 – May 26, 2026).

---

## Repo At a Glance

```
agent-shield/
├── evals/              ← Inspect AI eval tasks (the actual attack code lives here)
├── docs/               ← Reading notes (primary version)
├── logs/               ← .eval output files from Inspect runs
├── files/              ← Placeholder for environment payloads (empty)
├── Papers/             ← PDFs organized by category
│   ├── Core threat model/
│   ├── Jailbreak taxonomy/
│   ├── Benchmarks/
│   ├── Advanced/
│   └── Psychology layer/
├── github_Repos/       ← Cloned reference implementations
│   ├── agentdojo/
│   ├── JailbreakingLLMs/
│   ├── llm-attacks/
│   └── persuasive_jailbreaker/
├── AGENT_SHIELD_TODO.md    ← Master checklist (read this first every session)
├── TIMELINES.md            ← Sprint milestones, application deadlines, content calendar
├── THREAT_MODEL.md         ← STRIDE mapping, adversary levels, metrics schema
├── MAPPINGS.md             ← Every attack cross-linked to OWASP + MITRE ATLAS
├── BACKLOG.md              ← Ideas off-sprint, scope discipline file
├── reading_notes.md        ← OWASP reading notes (root copy)
├── docs/reading_notes.md   ← Primary full reading notes (Greshake, AgentDojo, OWASP)
├── main.py                 ← Entry point stub
├── pyproject.toml          ← uv project config
├── Makefile                ← Shortcuts: eval, test, lint
└── .env                    ← API keys (not committed)
```

---

## Code Files

### `evals/smoke.py`

The only live eval. Verifies the Inspect AI harness is wired up correctly.

```python
from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import includes
from inspect_ai.solver import generate

@task
def smoke():
    return Task(
        dataset=[
            Sample(input="What is 2+2? Reply with just the number.", target="4"),
            Sample(input="Capital of France? One word.", target="Paris"),
            Sample(input="Reverse the word 'cat'.", target="tac"),
            Sample(input="Is the sky blue? Yes or no.", target="Yes"),
            Sample(input="Name a prime between 10 and 20.", target=["11", "13", "17", "19"]),
        ],
        solver=generate(),
        scorer=includes(),
    )
```

**What it does:** 5 trivial tasks. `generate()` calls the model. `includes()` checks whether the target string appears anywhere in the model's output. Pass = harness is working.

**Run it:**
```bash
uv run inspect eval evals/smoke.py --model anthropic/claude-sonnet-4-5
# or
make eval
```

---

### `main.py`

```python
def main():
    print("Hello from agent-shield!")

if __name__ == "__main__":
    main()
```

Stub. Not used for evals. Placeholder for a future CLI entry point.

---

### `Makefile`

Three targets:

| Target | Command | What it runs |
|--------|---------|--------------|
| `make eval` | `uv run inspect eval evals/smoke.py --model anthropic/claude-sonnet-4-5` | Smoke eval on Anthropic Sonnet 4.5 |
| `make test` | `uv run pytest` | Python test suite |
| `make lint` | `uv run ruff check . && uv run mypy agent_shield` | Ruff linter + mypy type check |

---

### `pyproject.toml`

uv project config. Key sections:

**Main deps** (runtime): `python-dotenv`, `inspect-evals[agentdojo]` (local editable from `../inspect_evals`)

**Dev deps**: `inspect-ai`, `anthropic`, `openai`, `google-genai`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`

**Ruff config**: line-length 100, rules `E F W I N UP B SIM RUF`

**Mypy config**: strict mode, python_version 3.11

**Install everything:**
```bash
uv sync
```

---

## Key Reference Repos (`github_Repos/`)

| Repo | What it is | How it's used |
|------|-----------|---------------|
| `agentdojo/` | Debenedetti et al. — 4 environments, 74 tools, 629 security test cases | Benchmark harness; `inspect-evals[agentdojo]` wraps it |
| `JailbreakingLLMs/` | Chao et al. PAIR — iterative black-box jailbreak | Reference impl for `inputs/` module |
| `llm-attacks/` | Zou et al. GCG — gradient-based adversarial suffix | Reference impl for GCG reproduction in `inputs/` |
| `persuasive_jailbreaker/` | Zeng et al. PAP — persuasion-augmented prompting | Reference for `psych/` module; includes `persuasion_taxonomy.jsonl` |

---

## Eval Logs (`logs/`)

Inspect AI writes `.eval` files after each run. Binary format, readable with `uv run inspect view`.

| File | What happened |
|------|---------------|
| `2026-04-17T14-54-26_smoke_*.eval` | Smoke run 1 |
| `2026-04-17T14-57-08_smoke_*.eval` | Smoke run 2 |
| `2026-04-17T14-57-57_smoke_*.eval` | Smoke run 3 |
| `2026-04-17T15-04-40_agentdojo_*.eval` | AgentDojo banking suite — **security 0/5, utility 0/5** (defended but abandoned task) |

View any log:
```bash
uv run inspect view logs/<filename>.eval
```

---

## The 8 Planned Modules (not scaffolded yet)

| Folder | Attack surface | Key technique |
|--------|---------------|---------------|
| `inputs/` | Prompt injection | GCG, PAIR, TAP, Crescendo, Many-Shot |
| `tools/` | MCP tool misuse | Tool poisoning, rug pull, confused deputy |
| `memory/` | RAG poisoning | PoisonedRAG, retrieval hijack, embedding adversarial |
| `env/` | Environment payloads | PDF injection, image injection, calendar/email payloads |
| `exfil/` | Data exfiltration | Canary tokens, zero-width chars, homoglyphs, markdown sinks |
| `multiagent/` | Agent-to-agent attacks | Orchestrator bypass, majority vote poisoning, adversarial peer |
| `drift/` | Multi-turn behavioral | Sycophancy induction, sandbagging, Crescendo pressure |
| `psych/` | Psychology manipulation | Cialdini 6 principles, Hadnagy pretexts, Kahneman System 1 |

---

## Papers (`Papers/`)

### Core threat model
- Not what you've signed up for — Greshake et al. 2023
- AgentDojo prompt injection — Debenedetti et al. 2024

### Jailbreak taxonomy
- Universal and Transferable Adversarial Attacks on Aligned Language Models (GCG)
- Jailbreaking Black Box Large Language Models in Twenty Queries (PAIR)
- Tree of Attacks: Jailbreaking Black-Box LLMs Automatically (TAP)
- The Crescendo Multi-Turn LLM Jailbreak Attack
- Many-Shot Jailbreaking (NeurIPS 2024)
- How Johnny Can Persuade LLMs to Jailbreak Them (PAP)

### Benchmarks
- HarmBench — A Standardized Evaluation Framework for Automated Red Teaming
- JailbreakBench — An Open Robustness Benchmark
- AgentHarm — A Benchmark for Measuring Harmfulness of LLM Agents
- InjecAgent — Benchmarking Indirect Prompt Injections
- DecodingTrust — A Comprehensive Assessment of Trustworthiness in GPT Models

### Advanced
- PoisonedRAG — Knowledge Corruption Attacks to RAG
- Defending Against Indirect Prompt Injection Attacks With Spotlighting
- Agent Smith — Single Image Jailbreaks One Million Multimodal LLM Agents
- Discovering Language Model Behaviors with Model-Written Evaluations

### Standards (root-level)
- OWASP Top 10 for LLM Applications 2025 (`LLMAll_en-US_FINAL.pdf`)
- OWASP Top 10 for Agentic Applications 2026 (`OWASP-Top-10-for-Agentic-Applications-2026-12.6-1.pdf`)

---

## Key Design Decisions

**Transparency Rate** — Agent Shield's novel metric. Measures whether the agent *told the user* it was attacked, not just whether it resisted. No current benchmark (AgentDojo, InjecAgent, AgentHarm) tracks this. Every eval result reports three numbers: ASR, utility under attack, transparency rate.

**Adversary levels L1–L4:**
- L1: writes content the agent reads (web page, email, PDF)
- L2: publishes a tool the agent uses (MCP server)
- L3: compromises the retrieval store (RAG, vector DB)
- L4: acts as a peer agent (adversarial worker, poisoned orchestrator)

**Inspect AI as harness:** All 8 modules plug into Inspect's `Task` / `solver` / `scorer` loop. AgentDojo environments are accessed via `inspect-evals[agentdojo]`.

---

## Setup From Scratch

```bash
# Clone
git clone https://github.com/Chunduri-Aditya/agent-shield.git
cd agent-shield

# Install deps (requires uv)
uv sync

# Add API keys
cp .env.example .env   # then fill in ANTHROPIC_API_KEY etc.

# Verify harness
make eval
```

---

## Navigation Guide

| Question | Go to |
|----------|-------|
| What needs doing today? | `AGENT_SHIELD_TODO.md` |
| When is the next milestone? | `TIMELINES.md` |
| What attacks are in scope? | `MAPPINGS.md` |
| Why those attacks? | `THREAT_MODEL.md` |
| What papers ground each module? | `docs/reading_notes.md` |
| Where do off-sprint ideas live? | `BACKLOG.md` |
| How do I run an eval? | `make eval` or `evals/smoke.py` |
| How do I read a result? | `uv run inspect view logs/<file>.eval` |

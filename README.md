# agent-shield

An evaluation framework for LLM agents under adversarial pressure. Runs on the [Inspect AI](https://inspect.aisi.org.uk) harness. Compatible with AgentDojo. Reports the axis most agent benchmarks skip: whether the agent told its operator it was under attack.

## Why this exists

Most agent benchmarks answer two questions:

1. Did the user task succeed?
2. Did the attack succeed?

A system that silently resists is better than a hijacked one. It is worse than a system that resists *and* names what it caught. Agent Shield calls that missing signal **Transparency Rate** and reports it consistently across modules.

The early data hints at a contrast worth watching. The same provider that scores zero on direct prompt injection can flag manipulation under Cialdini pressure. Another provider, asked the same questions at the same seeds, surfaces nothing across either surface. If the contrast holds at scale, "the model resisted" and "the model resisted out loud" stop reading as the same outcome.

## Module coverage

| Module | Status | What it probes | Task IDs |
|---|---|---|---|
| `inputs/` | live | Prompt injection | IN-01..IN-05 |
| `tools/`  | live | MCP tool poisoning | TL-01 |
| `psych/`  | live | Cialdini grounded persuasion | PS-01..PS-06 |
| `memory/` | live | RAG poisoning | MM-01 |
| `exfil/`  | planned (v1.0.0) | Covert exfiltration channels | — |
| `drift/`  | planned (v1.0.0) | Multi turn manipulation and behavioral drift | — |
| `env/`    | deferred (v1.1) | PDF, image, calendar, email payloads | — |
| `multiagent/` | deferred (v1.1) | Adversarial peer and orchestrator attacks | — |

Per module open questions in [ROADMAP.md](ROADMAP.md). Scope lock in [SHIP_LINE.md](SHIP_LINE.md).

## Threat model

Agent Shield targets **LLM agents**, not plain chat models in the abstract. The four adversary levels:

- **L1** — attacker authors content the agent reads
- **L2** — attacker publishes a tool the agent uses
- **L3** — attacker poisons memory or retrieval
- **L4** — attacker acts as a peer agent in a multi-agent workflow

Plain chat models are valid targets only for non agentic surfaces (`inputs/`, `drift/`, `psych/`, parts of `exfil/`). Full model in [THREAT_MODEL.md](THREAT_MODEL.md).

## Metrics

Every eval reports the same core four:

- **Benign Utility** — task success without attack
- **Utility Under Attack** — task success while the attack runs
- **Targeted ASR** — attack success rate against the specified objective
- **Transparency Rate** — share of attacked runs where the agent surfaced the attack to the user

A result without Transparency Rate is incomplete for this project. TR is a security metric and a cognitive accessibility metric — the rate at which the agent makes its defense legible to a bounded human operator.

## Current status

Four modules live with seeded results: `inputs/`, `tools/`, `psych/`, `memory/`. Two of the four ship line models logged across all four: `anthropic/claude-sonnet-4-5` and `ollama/llama3.1:8b`. The remaining two (`groq/llama-3.3-70b-versatile`, `google/gemini-3.5-flash`) are scaffolded and waiting on the next sweep. Numbers, seeds, and Inspect log filenames in [RESULTS.md](RESULTS.md). Scope lock in [SHIP_LINE.md](SHIP_LINE.md).

## Repo layout

```text
agent-shield/
├── evals/             Inspect AI task definitions
├── inputs/            Prompt injection attack registry
├── tools/             MCP attack registry and demo server
├── psych/             Cialdini grounded attack registry
├── memory/            RAG store and poisoning attack registry
├── docs/              Reading notes, free agent backend reference
├── scripts/           Run helpers and auth checks
├── tests/             Pytest suite
├── notebooks/         Sweep runners
├── ROADMAP.md         Module status and per module open questions
├── SHIP_LINE.md       v1.0.0 scope lock and done criteria
├── THREAT_MODEL.md    Threat model and metric definitions
├── MAPPINGS.md        OWASP and MITRE ATLAS attack registry
├── RESULTS.md         Logged runs with seeds, dates, model IDs
├── BACKLOG.md         Out of scope ideas and v1.1 deferred items
└── ETHICS.md          Responsible disclosure policy
```

## Stack

- Python `3.11+`
- [uv](https://docs.astral.sh/uv/) for environment and dependency management
- [Inspect AI](https://inspect.aisi.org.uk) for eval orchestration
- `inspect-evals[agentdojo]` from a local editable checkout at `../inspect_evals`
- Provider SDKs: Anthropic, OpenAI, Google GenAI

## Quickstart

```bash
uv sync

# .env is gitignored — add your keys directly:
#   ANTHROPIC_API_KEY, GROQ_API_KEY, GOOGLE_API_KEY
# Ollama needs no key: ollama serve && ollama pull llama3.1:8b

make status         # check which models are available
make eval           # Inspect harness smoke test
make eval-inputs    # IN-01..IN-05
make eval-tools     # TL-01
make eval-psych     # PS-01..PS-06
make eval-all       # all implemented modules

make test           # pytest
make lint           # ruff
```

## Environment variables

Provider keys used by the repo:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `GROQ_API_KEY`

Keys live in `.env` (gitignored) — the full structure with placeholders is there. Free backend reference in [docs/free_agents.md](docs/free_agents.md).

## Reproducibility

Reproducibility trail kept in-repo:

- [RESULTS.md](RESULTS.md) — run summaries with model IDs, seeds, timestamps
- [MAPPINGS.md](MAPPINGS.md) — every attack mapped to OWASP LLM, OWASP Agentic, MITRE ATLAS
- [docs/reading_notes.md](docs/reading_notes.md) — paper notes indexed by attack code

## Security

Report issues in this repository's code or tooling privately per [.github/SECURITY.md](.github/SECURITY.md). Disclosure policy in [ETHICS.md](ETHICS.md).

## License

MIT — see [LICENSE](LICENSE).

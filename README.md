# agent-shield

Agent Shield is an evaluation framework for stress-testing LLM agents across adversarial attack surfaces. It runs on the [Inspect AI](https://inspect.aisi.org.uk) harness, is AgentDojo-compatible, and reports a third axis that most agent benchmarks skip: whether the agent told the user it was under attack.

## Why this exists

Most agent benchmarks answer two questions:

1. Did the user task succeed?
2. Did the attack succeed?

Necessary, but incomplete. A system that silently resists an attack is better than a hijacked one — but worse than a system that resists *and* tells its operator what it caught. Agent Shield calls that missing signal **Transparency Rate** and reports it consistently across modules.

## Module coverage

| Module | Status | What it tests | Task IDs |
|---|---|---|---|
| `inputs/` | Implemented | Prompt injection | IN-01..IN-05 |
| `tools/`  | Implemented | MCP tool poisoning | TL-01 |
| `psych/`  | Implemented | Cialdini-grounded persuasion | PS-01..PS-06 |
| `memory/` | Planned | RAG poisoning | — |
| `env/`    | Planned | PDF / image / calendar / email payloads | — |
| `exfil/`  | Planned | Covert exfiltration channels | — |
| `multiagent/` | Planned | Adversarial peer + orchestrator attacks | — |
| `drift/`  | Planned | Multi-turn manipulation and behavioral drift | — |

Harness smoke test: 5 AgentDojo banking tasks on `anthropic/claude-sonnet-4-5`, logged through Inspect AI.

## Threat model

Agent Shield targets **LLM agents**, not plain chat models in the abstract. The four adversary levels:

- **L1** — attacker authors content the agent reads
- **L2** — attacker publishes a tool the agent uses
- **L3** — attacker poisons memory or retrieval
- **L4** — attacker acts as a peer agent in a multi-agent workflow

Plain chat models are valid targets only for non-agentic surfaces (`inputs/`, `drift/`, `psych/`, parts of `exfil/`). Full model in [THREAT_MODEL.md](THREAT_MODEL.md).

## Metrics

Every eval reports the same core four:

- **Benign Utility** — task success without attack
- **Utility Under Attack** — task success while the attack runs
- **Targeted ASR** — attack success rate against the specified objective
- **Transparency Rate** — share of attacked runs where the agent surfaced the attack to the user

A result without Transparency Rate is incomplete for this project.

## Repo layout

```text
agent-shield/
├── evals/             Inspect AI task definitions
├── inputs/            Prompt-injection attack registry
├── tools/             MCP attack registry and demo server
├── psych/             Cialdini-grounded attack registry
├── docs/              Reading notes
├── scripts/           Run helpers and auth checks
├── tests/             Pytest suite
├── notebooks/         Sweep runners
├── THREAT_MODEL.md    Threat model and metric definitions
├── MAPPINGS.md        OWASP + MITRE ATLAS attack registry
├── RESULTS.md         Logged runs, seeds, dates, model IDs
├── BACKLOG.md         Out-of-scope ideas
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
cp .env.example .env

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

Template at [.env.example](.env.example).

## Reproducibility

Reproducibility trail kept in-repo:

- [RESULTS.md](RESULTS.md) — run summaries with model IDs, seeds, timestamps
- [MAPPINGS.md](MAPPINGS.md) — every attack mapped to OWASP LLM, OWASP Agentic, MITRE ATLAS
- [docs/reading_notes.md](docs/reading_notes.md) — paper notes indexed by attack code

## Security

Report issues in this repository's code or tooling privately per [.github/SECURITY.md](.github/SECURITY.md). Disclosure policy in [ETHICS.md](ETHICS.md).

## License

MIT — see [LICENSE](LICENSE).

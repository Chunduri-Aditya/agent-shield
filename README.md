# agent-shield

Agent Shield is an evaluation framework for stress-testing LLM agents across
adversarial attack surfaces with a unified metric schema.

The project is built around [Inspect AI](https://inspect.aisi.org.uk) tasks,
AgentDojo-compatible benchmarking, and a third evaluation axis that existing
benchmarks usually miss: whether the agent explicitly told the user it was under
attack.

## Problem Statement

Current agent benchmarks mostly answer two questions:

1. Did the user task succeed?
2. Did the attack succeed?

That is necessary, but incomplete. A system that silently resists an attack is
better than a hijacked system, but worse than one that both resists and clearly
warns the operator. Agent Shield adds that missing signal as **Transparency
Rate** and uses it consistently across attack modules.

## Current Status

Implemented today:

- `evals/smoke.py`: trivial Inspect AI harness smoke test
- `evals/inputs.py`: prompt-injection ASR and transparency evals
- `evals/tools.py`: MCP tool-poisoning ASR and transparency evals
- Logged AgentDojo smoke artifact: 5 banking tasks on
  `anthropic/claude-sonnet-4-5`

Planned modules:

- `memory/`: RAG poisoning
- `env/`: PDF/image/calendar/email payloads
- `exfil/`: covert exfiltration channels
- `multiagent/`: adversarial peer/orchestrator attacks
- `drift/`: multi-turn manipulation and behavioral drift
- `psych/`: psychology-grounded manipulation prompts

## Threat Model

Agent Shield targets **LLM agents**, not plain chat models in the abstract. The
core adversary levels are:

- `L1`: attacker authors content the agent reads
- `L2`: attacker publishes a tool the agent uses
- `L3`: attacker poisons memory or retrieval
- `L4`: attacker acts as a peer agent in a multi-agent workflow

Plain chat models are only valid targets for non-agentic surfaces such as
`inputs/`, `drift/`, `psych/`, and parts of `exfil/`.

The full threat model lives in [THREAT_MODEL.md](THREAT_MODEL.md).

## Metrics

Every eval is expected to report this core triple:

- **Benign Utility**
- **Utility Under Attack**
- **Targeted ASR**
- **Transparency Rate**

The last metric is the Agent Shield extension. A result without transparency is
incomplete for this project.

## Repo Layout

```text
agent-shield/
├── evals/                 Inspect AI task definitions
├── inputs/                Prompt-injection attack registry
├── tools/                 MCP attack registry and demo server
├── docs/                  Reading notes and paper support docs
├── logs/                  Inspect AI run artifacts
├── Papers/                Local paper library
├── github_Repos/          Cloned reference implementations
├── AGENT_SHIELD_TODO.md   Master sprint checklist
├── THREAT_MODEL.md        Threat model and metric definitions
├── MAPPINGS.md            OWASP + MITRE ATLAS attack registry
└── RESULTS.md             Logged runs, seeds, dates, and model IDs
```

## Stack

- Python `3.11+`
- [uv](https://docs.astral.sh/uv/) for environment and dependency management
- [Inspect AI](https://inspect.aisi.org.uk) for eval orchestration
- `inspect-evals[agentdojo]` from a local editable checkout at `../inspect_evals`
- Provider SDKs: Anthropic, OpenAI, Google GenAI

## Quickstart

Install dependencies:

```bash
uv sync
```

Create local environment variables:

```bash
cp .env.example .env
```

Run the Inspect harness smoke test:

```bash
make eval
```

Run the implemented attack modules:

```bash
make eval-inputs
make eval-tools
```

Run local checks:

```bash
make test
make lint
```

## Environment Variables

Current provider keys used by the repo:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`

See [.env.example](.env.example) for the template.

## Reproducibility

Agent Shield keeps the reproducibility trail in repo:

- [RESULTS.md](RESULTS.md) for run summaries and model IDs
- [logs/](logs/) for raw Inspect `.eval` artifacts
- [TIMELINES.md](TIMELINES.md) for sprint milestones and dated checkpoints
- [MAPPINGS.md](MAPPINGS.md) for attack-to-framework mapping discipline

The existing AgentDojo smoke artifact is
`logs/2026-04-17T15-04-40-00-00_agentdojo_NsBHePFzt5VJDGbDBpFD3L.eval`.

## References

- [THREAT_MODEL.md](THREAT_MODEL.md)
- [MAPPINGS.md](MAPPINGS.md)
- [TIMELINES.md](TIMELINES.md)
- [docs/reading_notes.md](docs/reading_notes.md)

## Citation

Citation metadata will be added once the workshop draft is frozen.

## License

MIT — see [LICENSE](LICENSE).

# agent-shield

An evaluation framework for LLM agents under adversarial pressure. Runs on the [Inspect AI](https://inspect.aisi.org.uk) harness. Compatible with AgentDojo. Reports the axis most agent benchmarks skip: whether the agent told its operator it was under attack.

## Why this exists

Most agent benchmarks answer two questions:

1. Did the user task succeed?
2. Did the attack succeed?

A system that silently resists is better than a hijacked one. It is worse than a system that resists *and* names what it caught. Agent Shield calls that missing signal **Transparency Rate**: operator-facing *disclosure* of an attack (not merely internal detection), reported next to ASR. Closest detection-style metrics (e.g. SafeEmbodAI ADR, MIR) are cited and distinguished in [docs/DIFFERENTIATION.md](docs/DIFFERENTIATION.md).

Prior-art audit (2026-07-31): [docs/originality_audit_2026-07-31.md](docs/originality_audit_2026-07-31.md).

The early data hints at a contrast worth watching. The same provider that scores zero on direct prompt injection can flag manipulation under Cialdini pressure. Another provider, asked the same questions at the same seeds, surfaces nothing across either surface. If the contrast holds at scale, "the model resisted" and "the model resisted out loud" stop reading as the same outcome.

## Module coverage

Statistical scope matters: one module is **anchored**; the rest are **diagnostic probes**.
Do not read “six live modules” as six powered results.

| Module | Status | Statistical role | What it probes | Attack IDs |
|---|---|---|---|---|
| `inputs/` | live | **Anchored** (n=20, Wilson 95% CI) | Prompt injection via direct instruction override | IN-01..IN-05 |
| `tools/` | live | **Anchored agentic** (n=20 Sonnet/Llama; Gemini `---`) | MCP tool description poisoning (Inspect tool loop) | TL-01 live; TL-02..TL-05 stubbed. Groq excluded from agentic claim |
| `psych/` | live | Diagnostic (n=6) | Cialdini grounded social engineering (6 principles) | PS-01..PS-06 |
| `memory/` | live | Diagnostic (n=10) | RAG store poisoning via retrieval injection | MM-01 |
| `exfil/` | live | Diagnostic (n=5) | Covert exfiltration channels (zero-width, homoglyph, base64, URL sink) | EX-01..EX-05 |
| `drift/` | live | Diagnostic (n=6) | Multi-turn behavioral drift and sycophancy manipulation | DR-01..DR-06 |
| `env/` | deferred (v1.1) | — | PDF, image, calendar, email payloads | — |
| `multiagent/` | deferred (v1.1) | — | Adversarial peer and orchestrator attacks | — |

Per module open questions in [ROADMAP.md](ROADMAP.md). Scope lock in [SHIP_LINE.md](SHIP_LINE.md).
Honesty script for talks: [docs/paper_defense_prep.md](docs/paper_defense_prep.md).

## Name note

This evaluation framework (“Agent Shield”) is **not** the same project as the
unrelated AgentShield deception detector (Rassul et al., arXiv:2605.11026),
ecc-agentshield config scanners, or agentshield.dev. Runtime CLIs here use
`agent-shield-*` prefixes.

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

A result without Transparency Rate is incomplete for this project. TR is a security metric and a cognitive accessibility metric — the rate at which the agent makes its defense legible to a bounded human operator.

## Current status

**Anchored results:**
- `inputs/` (non-agentic) at n=20 (seed 0, Wilson 95% CI): Sonnet 4.5 is the only model with non-zero TR (0.150); Llama 3.1 8B, Groq Llama 3.3 70B, and Gemini 3.5 Flash sit at TR=0.000 (upper bound 0.161). Silent resistance is the default.
- `tools/` (agentic TL-01) at n=20 (seed 0): Sonnet and Llama both ASR=0.000 / TR=0.000 (Wilson upper 0.161). Gemini row pending if the provider hung mid-run — see RESULTS. Groq excluded (chat-only tool envelopes).

**Diagnostic probes** (point estimates, not powered CIs): `psych/` (n=6), `memory/` (n=10), `exfil/` (n=5), `drift/` (n=6); historical `tools/` n=3 remains in RESULTS. One defense baseline: spotlighting on `inputs/` and `psych/`. Seeds, dates, and Inspect log filenames in [RESULTS.md](RESULTS.md). Scope lock in [SHIP_LINE.md](SHIP_LINE.md). Improvement track: [docs/PLUGIN_AND_CREDIBILITY_PLAN.md](docs/PLUGIN_AND_CREDIBILITY_PLAN.md). Differentiation: [docs/DIFFERENTIATION.md](docs/DIFFERENTIATION.md). Company agent wiring: [docs/company_agent_adapter.md](docs/company_agent_adapter.md).

## Repo layout

```text
agent-shield/
├── evals/             Inspect AI task definitions (one file per module)
├── inputs/            Prompt injection attack registry
├── tools/             MCP attack registry and demo server
├── psych/             Cialdini grounded attack registry
├── memory/            RAG store and poisoning attack registry
├── exfil/             Covert exfiltration attack registry
├── drift/             Behavioral drift attack registry
├── defenses/          Defense baselines (spotlighting)
├── reports/           Plain-language report schema and latest output
├── scripts/           Sweep runner, model registry, auth checks
├── tests/             Pytest suite
├── docs/              Reading notes, free agent backend reference
├── risk_registry.py   AIVSS-scored attack metadata with CIA and OWASP mappings
├── report_generator.py Plain-language report builder (make report)
├── ROADMAP.md         Module status and per module open questions
├── SHIP_LINE.md       v1.0.0 scope lock and done criteria
├── THREAT_MODEL.md    Threat model and metric definitions
├── MAPPINGS.md        OWASP LLM, OWASP Agentic, MITRE ATLAS attack registry
├── RESULTS.md         Logged runs with seeds, dates, model IDs, commit SHAs
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
make eval-tools     # TL-01 (stubs TL-02..TL-05 not eval'd)
make eval-psych     # PS-01..PS-06
make eval-memory    # MM-01
make eval-exfil     # EX-01..EX-05
make eval-drift     # DR-01..DR-06
make eval-all       # six live modules (one anchored + five probes)

make sweep          # run all modules against all available models
make report         # generate plain-language report from latest eval log
make guard          # runtime perimeter: echo TEXT | make guard
make mcp-proxy-demo # TL-01 catalog screen (JSON)
make mcp-proxy-badge
make guard-proof    # FP / alert / disable rates (no model calls)

make test           # pytest
make lint           # ruff
```

Kill switch: `AGENT_SHIELD_GUARD_OFF=1` or `--off` on guard / mcp-proxy.  
Trusted-tester notes: [docs/mcp_proxy_testers.md](docs/mcp_proxy_testers.md).  
Loom shot list: [docs/loom_demo_script.md](docs/loom_demo_script.md).  
Product post draft: [docs/post_adblock_for_agents.md](docs/post_adblock_for_agents.md).
## Environment variables

Provider keys used by the repo:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `GROQ_API_KEY`

Keys live in `.env` (gitignored). Free backend reference in [docs/free_agents.md](docs/free_agents.md).

## Reproducibility

Reproducibility trail kept in-repo:

- [RESULTS.md](RESULTS.md) — run summaries with model IDs, seeds, timestamps, commit SHAs
- [MAPPINGS.md](MAPPINGS.md) — every attack mapped to OWASP LLM, OWASP Agentic, MITRE ATLAS
- [docs/reading_notes.md](docs/reading_notes.md) — paper notes indexed by attack code

## Testing

Agent Shield keeps model calls out of the unit-test path. Tests validate
deterministic scoring, attack metadata consistency, paper-artifact
reproducibility, risk-gate behavior, and report generation. The full suite
runs without API keys, network access, or local model servers.

```bash
make test    # pytest — no API keys required
make lint    # ruff + mypy
```

## Security

Report issues in this repository's code or tooling privately per [.github/SECURITY.md](.github/SECURITY.md). Disclosure policy in [ETHICS.md](ETHICS.md).

## License

MIT — see [LICENSE](LICENSE).

# agent-shield

An evaluation framework for LLM agents under adversarial pressure. Runs on the [Inspect AI](https://inspect.aisi.org.uk) harness. Compatible with AgentDojo. Reports the axis most agent benchmarks skip: whether the agent told its operator it was under attack.

Optional **local runtime perimeter** (same repo, separate claim from the eval
numbers): screen untrusted text and MCP tool descriptions, quarantine known
TL-01-style poisons, and surface operator alerts. Not a hosted firewall or
store listing. Details below and in
[docs/company_agent_adapter.md](docs/company_agent_adapter.md).

Full orientation (goals, modules, runtime, what success looks like):
[docs/WHAT_AGENT_SHIELD_DOES.md](docs/WHAT_AGENT_SHIELD_DOES.md).

## Results (anchored rows only)

Both rows: seed 0, commit `d85bdb4`, 5 attacks × 4 epochs. Means and CIs are RESULTS.md cells rounded half up from 4 to 3 decimals; Inspect log filenames, diagnostic probes and withdrawn rows are in [RESULTS.md](RESULTS.md).

| Task | Model | Metric | Mean | n | 95% Wilson CI | Status |
|---|---|---|---|---|---|---|
| `inputs_transparency` | anthropic/claude-sonnet-4-5 → claude-sonnet-4-5-20250929 | TR | 0.150 | 20 | [0.052, 0.360] | anchored |
| `inputs_asr` | anthropic/claude-sonnet-4-5 → claude-sonnet-4-5-20250929 | ASR | 0.050 | 20 | [0.009, 0.236] | anchored |

## What went wrong and got fixed

Five numbers from this repo and its neighbours were wrong while their tests were green; each case, its cause and the commit that fixed it are in [docs/posts/where_my_evals_lied.md](docs/posts/where_my_evals_lied.md). Every citation in the post is checked against its source by `scripts/check_post_citations.py` (`make post-check`), which fails when a cited token moves or disappears.

## Task index

| Task | Probes | Status |
|---|---|---|
| `inputs_asr`, `inputs_transparency` | direct prompt injection, IN-01..IN-05 | anchored |
| `tools_*_anchored` | MCP tool description poisoning, TL-01 | withdrawn (rows predate `920c397`; rerun pending) |
| `psych_*`, `memory_*`, `exfil_*`, `drift_*` | social engineering, RAG poisoning, exfiltration, drift | diagnostic |
| `persona_attribution` | do persona bibles drive the text (arms A, B, C; scorers S0 to S4) | TBD |
| `env/`, `multiagent/` | environment payloads, peer agent attacks | deferred |

## Why this exists

Most agent benchmarks answer two questions:

1. Did the user task succeed?
2. Did the attack succeed?

A system that silently resists is better than a hijacked one. It is worse than a system that resists *and* names what it caught. Agent Shield calls that missing signal **Transparency Rate**: operator-facing *disclosure* of an attack (not merely internal detection), reported next to ASR. Closest detection-style metrics (e.g. SafeEmbodAI ADR, MIR) are cited and distinguished in [docs/DIFFERENTIATION.md](docs/DIFFERENTIATION.md).

Prior-art audit (2026-07-31): [docs/originality_audit_2026-07-31.md](docs/originality_audit_2026-07-31.md).

The early data hints at a contrast worth watching. The same provider that scores zero on direct prompt injection can flag manipulation under Cialdini pressure. Another provider, asked the same questions at the same seeds, surfaces nothing across either surface. If the contrast holds at scale, "the model resisted" and "the model resisted out loud" stop reading as the same outcome.

## Module coverage

Statistical scope matters: exactly one module is **anchored** (`inputs/`, not agentic). The agentic anchor is withdrawn pending a TL-01 rerun; the rest are **diagnostic probes**.
Do not read “six live modules” as six powered results.

| Module | Status | Statistical role | What it probes | Attack IDs |
|---|---|---|---|---|
| `inputs/` | live | **Anchored** (n=20, Wilson 95% CI) | Prompt injection via direct instruction override | IN-01..IN-05 |
| `tools/` | live | **Anchor withdrawn** (TL-01 rerun pending, predates `920c397`) | MCP tool description poisoning (Inspect tool loop) | TL-01 live; TL-02..TL-05 stubbed. Groq excluded from agentic claim |
| `psych/` | live | Diagnostic (n=6) | Cialdini grounded social engineering (6 principles) | PS-01..PS-06 |
| `memory/` | live | Diagnostic (n=10) | RAG store poisoning via retrieval injection | MM-01 |
| `exfil/` | live | Diagnostic (n=5) | Covert exfiltration channels (zero-width, homoglyph, base64, URL sink) | EX-01..EX-05 |
| `drift/` | live | Diagnostic (n=6) | Multi-turn behavioral drift and sycophancy manipulation | DR-01..DR-06 |
| `env/` | deferred (v1.1) | — | PDF, image, calendar, email payloads | — |
| `multiagent/` | deferred (v1.1) | — | Adversarial peer and orchestrator attacks | — |

Per module open questions in [ROADMAP.md](ROADMAP.md). Scope lock in [SHIP_LINE.md](SHIP_LINE.md).

## Name note

This evaluation framework (“Agent Shield”) is **not** the same project as the
unrelated AgentShield deception detector (Rassul et al., arXiv:2605.11026),
ecc-agentshield config scanners, or agentshield.dev. Runtime CLIs here use
`agent-shield-*` prefixes (`agent-shield-guard`, `agent-shield-mcp-proxy`,
`agent-shield-proof`, `agent-shield-tr-v2`).

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

**TR measurement:** published rows use **TR-v1** (phrase list). **TR-v2** (LLM judge) is a challenger (`agent-shield-tr-v2`); not promoted until a human-labeled real-episode holdout passes the FP ≤ 5% gate. Design: [docs/tr_v2_judge_design.md](docs/tr_v2_judge_design.md).

## Current status

**Headline finding (locked, anchored):** one anchored model on `inputs/` at n=20
(seed 0, Wilson 95% CI), Sonnet 4.5, in the Results table above. Llama 3.1 8B,
Groq Llama 3.3 70B and Gemini 3.5 Flash sit at TR=0.000 on `inputs/`, but at
n=5, whose Wilson upper bound is 0.434, not 0.161. None of the three has an
anchored n=20 `inputs/` row, so “Sonnet is the only model with nonzero TR” is
not yet a powered claim; it is one anchored row beside three underpowered ones.
Silent resistance is the default on direct injection, not the same outcome as
“resisted out loud.”

**Second anchor (agentic) — withdrawn, rerun pending:** every `tools/` TL-01
row, the n=20 table included, predates `920c397`, the commit that first put the
poisoning payload into the model visible `read_file` description. Those rows
measure unprompted `send_message` calls, not tool poisoning, so they are not a
TL-01 result. Validity note and the historical rows stay in
[RESULTS.md](RESULTS.md). **No agentic anchor currently stands.**

**Diagnostic probes** (point estimates, not powered CIs): `psych/` (n=6),
`memory/` (n=10), `exfil/` (n=5), `drift/` (n=6); historical `tools/` n=3
remains in RESULTS. One defense baseline: spotlighting on `inputs/` and
`psych/`. Seeds, dates, and Inspect log filenames in [RESULTS.md](RESULTS.md).

**Runtime perimeter:** installable locally (see next section). Cross-purpose
MCP description quarantine evidence:
[docs/mcp_cross_purpose_promotion.md](docs/mcp_cross_purpose_promotion.md).
Differentiation: [docs/DIFFERENTIATION.md](docs/DIFFERENTIATION.md).

## Local runtime perimeter (optional)

Same repository, **separate claim** from the eval tables. Package:
`agent_shield.runtime`. No model calls for the proof CLI.

| CLI | Role |
|---|---|
| `agent-shield-guard` | Screen stdin / untrusted text (`product` or `strict`) |
| `agent-shield-mcp-proxy` | Screen MCP tool catalogs; quarantine poisoned descriptions |
| `agent-shield-proof` | Deterministic FP / alert / split recall / disable rates |

**Honest limits (read before integrating):**

- TL-01-style **description** poisons are caught by **proxy-local heuristics**,
  not by the research screener’s `flagged_attack`. Email-redacted TL-01 is a
  clean ALLOW on `agent-shield-guard` alone. Always run catalogs through the
  proxy. Expose `model_tools` to the model — never `tools[].original_description`.
- **`input_schema` is not screened** (parameter descriptions, `examples`,
  `$defs`). Do not re-merge raw upstream `title` / annotations into the
  model-facing catalog after screening.
- Product mode: HIGH injection → alert and proceed; hard secrets →
  `require_confirm` (elevate with `--confirm`). Kill switch:
  `AGENT_SHIELD_GUARD_OFF=1` or `--off`.
- Proof recall is **split**: `recall_alert_on_text_attack` (text path) vs
  `recall_quarantine_on_attack` (catalog quarantine only).

| Doc | Audience |
|---|---|
| [docs/company_agent_adapter.md](docs/company_agent_adapter.md) | Drop-in wiring for an internal agent loop |
| [docs/mcp_proxy_testers.md](docs/mcp_proxy_testers.md) | Trusted-tester guide |
| [docs/runtime_aggressive_testing_research.md](docs/runtime_aggressive_testing_research.md) | Miss corpus / FP gate research (not a shipped attack pack) |

## DPO/LoRA fine-tuning spike

This repo also contains a small end-to-end DPO/LoRA preference-tuning spike,
separate from the six security-evaluation modules covered in
[`RESULTS.md`](RESULTS.md).

**Scope.** This is preference tuning on response verbosity, not a security
evaluation. It reports no Attack Success Rate, Utility Under Attack, or
Transparency Rate, and has no corresponding Inspect AI task. For that reason it
is intentionally excluded from `RESULTS.md` — that table's schema requires model
ID, seed, eval file, task name, n samples, date, and commit SHA per row, none of
which apply to a preference-tuning run. Including it there would place an
unrelated result inside the table this repo's paper cites.

**What was run.** TRL `DPOTrainer` plus PEFT LoRA against
`HuggingFaceTB/SmolLM2-135M-Instruct`: rank 8 on the attention projections,
beta 0.1, learning rate 5e-5, six epochs, **40 training pairs and 12 held-out
pairs**. Six scripts and 1422 insertions in commit `9b86e32`, with the results
entry in `d1af723`. No checkpoints, `.safetensors`, or optimizer state are
tracked — all training artifacts stay behind `.gitignore` and every result
regenerates in under a minute.

**Measured results on the held-out set** (full entry in
[`BACKLOG.md`](BACKLOG.md) under Post-ship):

| Metric | Before | After |
|---|---|---|
| Implicit DPO reward margin | — | +1.05 (12/12 pairs positive) |
| Mean generation length | 32.5 | 29.8 |
| Answer-key rate | 0.750 | 0.833 |
| Degenerate outputs | 0 | 0 |
| Greedy generations changed | — | 4/12 |

The preference signal generalizes to unseen pairs while behavior moves only
slightly. Length fell without answer retention falling with it, which is what
separates concision from degeneration.

**Two transferable findings from the run:**

1. Generating in `train()` mode with gradient checkpointing enabled degenerates
   output into one token followed by endless newlines. This reproduces on the
   **untrained** base model, so it is a decode-time bug independent of the
   preference-tuning objective entirely.
2. Stripped-text postprocessing hides that degradation rather than surfacing it:
   forty generated newline tokens render as the string `'The'`. The failure mode
   is easy to misread as brevity collapse without raw-output inspection.

Both are now guarded in code — generation refuses to run from a model left in
training state, and every generation carries token ids, token count, and stop
reason.

```bash
uv run --no-project scripts/dpo_lora_spike.py --axis verbosity
```

## Repo layout

```text
agent-shield/
├── agent_shield/      Metrics, research screener, runtime perimeter (guard / MCP proxy / proof / TR-v2)
├── evals/             Inspect AI task definitions (one file per module)
├── inputs/            Prompt injection attack registry
├── tools/             MCP attack registry and demo server
├── psych/             Cialdini grounded attack registry
├── memory/            RAG store and poisoning attack registry
├── exfil/             Covert exfiltration attack registry
├── drift/             Behavioral drift attack registry
├── defenses/          Defense baselines (spotlighting)
├── reports/           Plain-language reports, TR audits, TR-v2 holdouts
├── scripts/           Sweep runner, model registry, auth checks, DPO/LoRA spike
├── tests/             Pytest suite (includes runtime perimeter pins)
├── docs/              Adapter, originality audit, aggressive-testing research, paper prep
├── risk_registry.py   AIVSS-scored attack metadata with CIA and OWASP mappings
├── report_generator.py Plain-language report builder (make report)
├── ROADMAP.md         Module status, eval + optional local runtime posture
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
make eval-tools     # TL-01 diagnostic (n=3)
make eval-tools-anchored   # TL-01 powered n=20 (needs CONFIRM_HIGH_RISK=1)
make eval-psych     # PS-01..PS-06
make eval-memory    # MM-01
make eval-exfil     # EX-01..EX-05
make eval-drift     # DR-01..DR-06
make eval-all       # six live modules (anchored + probes)

make sweep          # run all modules against all available models
make report         # generate plain-language report from latest eval log

# Optional local perimeter (no model required for proof)
make guard          # echo TEXT | make guard
make mcp-proxy-demo # TL-01 catalog screen (JSON) — use model_tools for the model
make mcp-proxy-badge
make guard-proof    # FP / alert / split recall / disable rates
make tr-v2-holdout  # TR-v2 challenger dry-run (heuristic; not promotion)

make test           # pytest
make lint           # ruff + mypy
```

Kill switch: `AGENT_SHIELD_GUARD_OFF=1` or `--off` on guard / mcp-proxy.

## Environment variables

Provider keys used by the repo:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `GROQ_API_KEY`
- `AGENT_SHIELD_GUARD_OFF` — set to `1` to disable the runtime perimeter

Keys live in `.env` (gitignored). Free backend reference in [docs/free_agents.md](docs/free_agents.md).

## Reproducibility

Reproducibility trail kept in-repo:

- [RESULTS.md](RESULTS.md) — run summaries with model IDs, seeds, timestamps, commit SHAs
- [MAPPINGS.md](MAPPINGS.md) — every attack mapped to OWASP LLM, OWASP Agentic, MITRE ATLAS
- [docs/reading_notes.md](docs/reading_notes.md) — paper notes indexed by attack code
- [docs/DIFFERENTIATION.md](docs/DIFFERENTIATION.md) — disclosure vs detection claim boundary

## Testing

Agent Shield keeps model calls out of the unit-test path. Tests validate
deterministic scoring, attack metadata consistency, paper-artifact
reproducibility, risk-gate behavior, runtime guard / MCP proxy / proof metrics
(including TL-01 honesty pins and schema-boundary pins), TR-v2 parse + dry-run
holdout, and report generation. `tests/test_readme_results.py` holds the README
Results cells, commit and seed to the RESULTS.md anchored table, the Task index
statuses to the Module coverage table, and checks that the post and its citation
checker exist. The full suite
runs without API keys, network access, or local model servers.

```bash
make test    # pytest — no API keys required
make lint    # ruff + mypy
```

Always use `uv run` / `make` so the project venv is active.

**Known gap (2026-08-25 audit, P0 fixed same day):** CI was red for 17 days
on 9 `ruff` errors — fixed. `.github/workflows/ci.yml` now also runs `mypy`
alongside `ruff` and `pytest`, matching `make lint`. That step currently
fails (130 pre-existing errors, mostly missing type coverage on
`agent_shield/` itself) — tracked as P1 in
[docs/audit_2026-08-25.md](docs/audit_2026-08-25.md) /
[BACKLOG.md](BACKLOG.md#engineering-health-2026-08-25-audit).

## Security

Report issues in this repository's code or tooling privately per [.github/SECURITY.md](.github/SECURITY.md). Disclosure policy in [ETHICS.md](ETHICS.md). Dual-use attacks stay gated by the risk check / `CONFIRM_HIGH_RISK=1` for CRITICAL evals. Runtime aggressive-testing research stays plan-only until ETHICS clearance for any HIGH dual-use fixture rows — see [docs/runtime_aggressive_testing_research.md](docs/runtime_aggressive_testing_research.md).

## License

MIT — see [LICENSE](LICENSE).

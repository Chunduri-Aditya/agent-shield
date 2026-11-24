# Agent Shield

Agent Shield tests whether a language model agent **completes the user's task, follows an injected instruction, and tells the operator about the attack**. Its attack modules cover prompt injection, MCP tool description poisoning, social engineering, retrieval poisoning, covert exfiltration and behavioral drift. Each module runs as an [Inspect AI](https://inspect.aisi.org.uk) task against one model at a time. The repository is for an engineer or a researcher who wants to run these attacks against an agent, and to see which published results survived an audit. **Transparency Rate** is the metric defined for the third outcome. It is not validated yet: it matches phrases, and no human labelled set checks it ([details](showcase/WHAT_I_BUILT.md#transparency-rate-defined-not-yet-validated)).

One person built and audited this repository. [What I built and how I know it holds](showcase/WHAT_I_BUILT.md) links each piece of work to its code, a test or a record, and marks where the evidence is weak.

[What I built](showcase/WHAT_I_BUILT.md) · [Run it](#how-to-run) · [What stands](#what-stands-after-the-erratum) · [Known limits](#known-limits) · [See the results and research progress](#evidence-and-research-progress) · [Read the preprint erratum](docs/ERRATUM.md) · [Map of the repo](START_HERE.md)

## How to run

| What you run | What it needs |
|---|---|
| The demo below | Python 3.11 or newer. No install, no API key, no model server |
| `make test`, `make lint`, the local screens | `uv sync --locked`. No API key, no model server |
| `make eval*`, `make sweep` | `uv sync --locked` and a model: a provider key in `.env`, or a local Ollama server, which needs no key |

The default `MODEL` is `anthropic/claude-sonnet-5-5`. Published results came from the models named in the paper, and this default only affects new runs. It needs `ANTHROPIC_API_KEY`, and a run on a hosted model can cost money. The Groq targets need `GROQ_API_KEY`, the Gemini targets need `GOOGLE_API_KEY`, and the Grok targets need `XAI_API_KEY`. More variables are under [Environment variables](#environment-variables).

`make test` result: 1972 passed, 35 skipped, local run at `1e553a2`, provider keys unset. The command and its output are in [docs/COUNTS.md](docs/COUNTS.md#suite-run).

### Try it in 30 seconds

Run this from the `agent-shield` checkout, the directory that contains this README. If your terminal is in `agent-shield-complete`, first run `cd agent-shield`.

The demo needs **Python 3.11 or newer** and runs without dependencies, API keys, or a model server. Check yours with `python3 --version`. On an older Python the command stops with one line that names the required version and where to get it.

```bash
env -u AGENT_SHIELD_GUARD_OFF python3 -m agent_shield.runtime.mcp_proxy_cli badge
```

```text
[Agent Shield] blocked=0 alerted=1 allowed=2 quarantined_descriptions=1 ruleset=research-content-v1.1.4 kill_switch=False
```

The demo screens three Model Context Protocol (MCP) tool descriptions. It replaces the poisoned `read_file` description with a quarantine message, keeps the two benign descriptions, and alerts the operator. To inspect the catalog the model would receive, run the same command with `demo-tl01 --json` in place of `badge` and look at `model_tools`.

Run `env -u AGENT_SHIELD_GUARD_OFF python3 -m agent_shield.runtime.proof_cli` to replay the bundled fixtures.

| Fixture check | Result |
|---|---|
| Text attacks flagged | 10 of 10 |
| Poisoned tool descriptions quarantined | 1 of 1 |
| Benign inputs denied or quarantined | 0 of 6 |

These counts describe the bundled fixtures. The demo uses local rules and does not invoke a model or screen tool parameter schemas. [Runtime scope and limits](#local-runtime-screens-optional)

### Quickstart

The harness needs [uv](https://docs.astral.sh/uv/). Each `make eval*` target calls a model, and so does `make sweep`. The risk gate stops a HIGH or CRITICAL module unless `CONFIRM_HIGH_RISK=1` is set.

```bash
uv sync --locked

# .env is gitignored — add your keys directly:
#   ANTHROPIC_API_KEY, GROQ_API_KEY, GOOGLE_API_KEY
# Ollama needs no key: ollama serve && ollama pull llama3.1:8b

make status         # check which models are available
make eval           # Inspect harness smoke test
CONFIRM_HIGH_RISK=1 make eval-inputs    # IN-01..IN-05 (HIGH, gated)
CONFIRM_HIGH_RISK=1 make eval-tools     # TL-01 diagnostic (n=3) (CRITICAL, gated)
CONFIRM_HIGH_RISK=1 make eval-tools-anchored   # TL-01 n=20 (CRITICAL, gated)
make eval-psych     # PS-01..PS-06
CONFIRM_HIGH_RISK=1 make eval-memory    # MM-01 (HIGH, gated)
CONFIRM_HIGH_RISK=1 make eval-exfil     # EX-01..EX-05 (CRITICAL, gated)
make eval-drift     # DR-01..DR-06
CONFIRM_HIGH_RISK=1 make eval-all      # smoke test, then the six live modules

make sweep          # run all modules against all available models
make report         # generate plain-language report from latest eval log

# Optional local screens (no model required for proof)
make guard          # echo TEXT | make guard
make mcp-proxy-demo # TL-01 catalog screen (JSON) — use model_tools for the model
make mcp-proxy-badge
make guard-proof    # FP / alert / split recall / disable rates
make tr-v2-holdout  # TR-v2 challenger dry-run (heuristic; not promotion)

make test           # pytest
make lint           # ruff + mypy
```

Kill switch: `AGENT_SHIELD_GUARD_OFF=1` or `--off` on guard / mcp-proxy.

## What stands after the erratum

The [erratum](docs/ERRATUM.md) withdraws 15 claims from the original preprint: 13 in October 2026, then in November 2026 a priority claim (W14) and the spotlighting Transparency Rate claim (W15). The count is the 15 rows of the erratum at commit `1e553a2` ([docs/COUNTS.md](docs/COUNTS.md#withdrawn-claims)).

The erratum does not withdraw the rows below. Each row describes the specific prompts tested.

| What stands | Scope | Where to check |
|---|---|---|
| The protocol: Transparency Rate as a third axis beside ASR and utility, the six cell taxonomy as a definition, and the framework, attack registries and logs as released | A definition and released code. No cell count was measured (W5) | [What stands](docs/ERRATUM.md#what-stands) · [Threat model](THREAT_MODEL.md) |
| `inputs`: Llama 3.1 8B and Llama 3.3 70B comply on all 5 prompts (ASR 1.000, effective n=5, Wilson [0.566, 1.000]) | 5 distinct prompts for each model | [What stands](docs/ERRATUM.md#what-stands) · [Run ledger](RESULTS.md) |
| `inputs`: Gemini 3.5 Flash scores 3 of 20 under both the published and the current marker rule, over 5 prompts | 5 prompts × 4 epochs, not 20 independent episodes (W3) | [What stands](docs/ERRATUM.md#what-stands) · [Run ledger](RESULTS.md) |
| `exfil`: Llama 3.3 70B executes all five channels (5 of 5) and leaks the raw canary on EX-01 and EX-05 (2 of 5) | 5 channel prompts, one model | [What stands](docs/ERRATUM.md#what-stands) · [Run ledger](RESULTS.md) |

Work done after the preprint is outside the erratum. The S1 event counts are under [Evidence and research progress](#evidence-and-research-progress), and the DW-01 diagnostics are under [Current status](#current-status).

## Known limits

- **Transparency Rate is not validated.** The scorer matches phrases, and no gold set of human labels measures its errors. No Transparency Rate number in this repo is a validated result ([details](showcase/WHAT_I_BUILT.md#transparency-rate-defined-not-yet-validated)).
- **No anchored result stands.** The `inputs/` anchor is withdrawn (ERRATUM W2 to W4), and the agentic anchor is withdrawn until a TL-01 rerun exists (W1). The other modules are diagnostic probes: point estimates, not powered intervals ([Current status](#current-status)).
- **Human labels: the 140 label gate has not passed.** The gate for the S1 judge (D49) "needs at least 140 blind human labels and has not passed" ([MAPPINGS.md](MAPPINGS.md)). The label count is pending merge of `task/b3-tr-interview` ([docs/B3_BRANCH_NOTE.md](docs/B3_BRANCH_NOTE.md)). S1 reports event counts, and it has yet to report a Transparency Rate validated against human labels.
- **Each result is for one model and one run.** A row describes the model, the prompts and the run that it names. A row with n=20 is 5 prompts × 4 epochs, not 20 independent episodes (W3). Do not read a count as a property of other models or of a model family.

## Evidence and research progress

**Follow up study.** The S1 tool poisoning panel recorded **4,760 samples across 13 Claude models**. Its event scorer checks that a unique token from a file read reaches the designated test recipient through a tool call. The [run report](docs/paper_v2/S1_RUN_REPORT.md) records setup, counts and the retry correction. The [judge run](docs/paper_v2/S1_JUDGE_RUN.md) is complete. The study has yet to report a Transparency Rate validated against human labels.

The S1 event outcome, the preregistered `strict_nonce` send, is reported as counts per model, with the preregistered 95% intervals (decision D63) and the matched thinking contrast, on the [S1 event finding page](showcase/S1_EVENT_FINDING.md).

## What went wrong and got fixed

The original tool poisoning benchmark reported zero successful attacks even though the model never received the injected description. The payload was on the tool factory, while Inspect reads the returned tool's description. Commit `920c397` put the payload on the model visible surface. The [delivery tests](tests/test_eval_scorers.py) check that boundary. The [postmortem](docs/posts/where_my_evals_lied.md) documents this and four other measurement failures. The citation checker at `scripts/check_post_citations.py` runs via `make post-check` and uses sibling checkouts for the other projects cited in the post.

## Explore the implementation

| Area | Start here |
|---|---|
| Threat model and attack registry | [Threat model](THREAT_MODEL.md) · [Framework mappings](MAPPINGS.md) |
| Tool event scoring | [Event scorer](evals/tools_event_v2.py) · [Study protocol](docs/paper_v2/prereg/S1.md) |
| Runtime integration | [MCP catalog screen](agent_shield/runtime/mcp_proxy.py) · [Adapter guide](showcase/guides/company_agent_adapter.md) |
| Full evidence trail | [Erratum](docs/ERRATUM.md) · [Run ledger](RESULTS.md) · [Historical findings](FINDINGS.md) |

## Task index

| Task | Probes | Status |
|---|---|---|
| `inputs_asr`, `inputs_transparency` | direct prompt injection, IN-01..IN-05 | withdrawn (Sonnet 4.5 n=20 rows, ERRATUM W2 to W4); n=5 rows in What stands |
| `tools_*_anchored` | MCP tool description poisoning, TL-01 | withdrawn (rows predate `920c397`; rerun pending) |
| `psych_*`, `memory_*`, `exfil_*`, `drift_*` | social engineering, RAG poisoning, exfiltration, drift | diagnostic |
| `persona_attribution` | do persona bibles drive the text (arms A, B, C; scorers S0 to S4) | negative (the judge reads the documented surface tells and falls under the surface baseline once they are stripped; the no bible row is malformed; RESULTS.md) |
| `env/`, `multiagent/` | environment payloads, peer agent attacks | deferred |

## Why this exists

Most agent benchmarks answer two questions:

1. Did the user task succeed?
2. Did the attack succeed?

A system that silently resists is better than a hijacked one. It is worse than a system that resists *and* names what it caught. Agent Shield calls that missing signal **Transparency Rate**: operator-facing *disclosure* of an attack (not merely internal detection), reported next to ASR. Closest detection-style metrics (e.g. SafeEmbodAI ADR, MIR) are cited and distinguished in [research/positioning/DIFFERENTIATION.md](research/positioning/DIFFERENTIATION.md).

Prior-art audit (2026-07-31): [research/positioning/originality_audit_2026-07-31.md](research/positioning/originality_audit_2026-07-31.md).

## Module coverage

Do not read “six live modules” as six powered results.

| Module | Status | Statistical role | What it probes | Attack IDs |
|---|---|---|---|---|
| `inputs/` | live | **Anchor withdrawn** (Sonnet 4.5 n=20 rows, ERRATUM W2 to W4; n=5 rows stand) | Prompt injection via direct instruction override | IN-01..IN-05 |
| `tools/` | live | **Anchor withdrawn** (TL-01 rerun pending, predates `920c397`) | MCP tool description poisoning (Inspect tool loop) | TL-01 live; TL-02..TL-05 stubbed. Groq excluded from agentic claim |
| `psych/` | live | Diagnostic (n=6) | Cialdini grounded social engineering (6 principles) | PS-01..PS-06 |
| `memory/` | live | Diagnostic (n=10) | RAG store poisoning via retrieval injection | MM-01 |
| `exfil/` | live | Diagnostic (n=5) | Covert exfiltration channels (zero-width, homoglyph, base64, URL sink) | EX-01..EX-05 |
| `drift/` | live | Diagnostic (n=6) | Multi-turn behavioral drift and sycophancy manipulation | DR-01..DR-06 |
| `env/` | deferred (v1.1) | — | PDF, image, calendar, email payloads | — |
| `multiagent/` | deferred (v1.1) | — | Adversarial peer and orchestrator attacks | — |

Per module open questions in [ROADMAP.md](research/decisions/ROADMAP.md). Scope lock in [SHIP_LINE.md](research/decisions/SHIP_LINE.md).

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

**Inputs anchor: withdrawn.** The Sonnet 4.5 n=20 rows in the historical Results
table do not hold: the one ASR hit is a refusal that quotes the marker, the TR difference
from zero is not established (Fisher p = 0.231), and n=20 is 5 prompts × 4 epochs
(ERRATUM W2 to W4). What stands on `inputs/` is listed under What stands.

**Second anchor (agentic) — withdrawn, rerun pending:** every `tools/` TL-01
row, the n=20 table included, predates `920c397`, the commit that first put the
poisoning payload into the model visible `read_file` description. Those rows
measure unprompted `send_message` calls, not tool poisoning, so they are not a
TL-01 result. Validity note and the historical rows stay in
[RESULTS.md](RESULTS.md); the preprint correction is [docs/ERRATUM.md](docs/ERRATUM.md).
**No agentic anchor currently stands.**

**Diagnostic probes** (point estimates, not powered CIs): `psych/` (n=6),
`memory/` (n=10), `exfil/` (n=5), `drift/` (n=6); historical `tools/` n=3
remains in RESULTS. One defense baseline: spotlighting on `inputs/` and
`psych/`. Seeds, dates, and Inspect log filenames in [RESULTS.md](RESULTS.md).

`wallet/` DW-01 pagination loop on claude-haiku-5-5 (diagnostic, n=5): [results/wallet/DW01_haiku55_2026-11-18.md](results/wallet/DW01_haiku55_2026-11-18.md).

`wallet/` DW-01 spend governor on claude-haiku-5-5, observe against enforce (diagnostic, n=5): [results/wallet/DW01_governor_haiku55_2026-11-18.md](results/wallet/DW01_governor_haiku55_2026-11-18.md).

**Runtime screens:** installable locally (see next section). They screen a text or a
tool catalog once and gate no live agent call. Cross-purpose
MCP description quarantine evidence:
[results/audit_reports/mcp_cross_purpose_promotion.md](results/audit_reports/mcp_cross_purpose_promotion.md).
Differentiation: [research/positioning/DIFFERENTIATION.md](research/positioning/DIFFERENTIATION.md).

## Local runtime screens (optional)

Agent Shield is an evaluation harness plus a runtime governor that runs inside the
Inspect eval loop. The CLIs below screen a text or an MCP tool catalog once, when a
host calls them. No live agent call is gated today. The gap list is in
[docs/plugin/GAP_ANALYSIS.md](docs/plugin/GAP_ANALYSIS.md).

Same repository, **separate claim** from the eval tables. Package:
`agent_shield.runtime`. No model calls for the proof CLI.

| CLI | Role |
|---|---|
| `agent-shield-guard` | Screen stdin / untrusted text (`product` or `strict`) |
| `agent-shield-mcp-proxy` | Screen MCP tool catalogs; quarantine poisoned descriptions |
| `agent-shield-proof` | Deterministic FP / alert / split recall / disable rates |

**Honest limits (read before integrating):**

- TL-01-style **description** poisons are caught by **heuristics local to the catalog screen**,
  not by the research screener’s `flagged_attack`. Email-redacted TL-01 is a
  clean ALLOW on `agent-shield-guard` alone. Always run catalogs through the
  catalog screen (`agent-shield-mcp-proxy`). Expose `model_tools` to the model — never `tools[].original_description`.
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
| [showcase/guides/company_agent_adapter.md](showcase/guides/company_agent_adapter.md) | Drop-in wiring for an internal agent loop |
| [showcase/guides/mcp_proxy_testers.md](showcase/guides/mcp_proxy_testers.md) | Trusted-tester guide |
| [research/design/runtime_aggressive_testing_research.md](research/design/runtime_aggressive_testing_research.md) | Miss corpus / FP gate research (not a shipped attack pack) |

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
[`BACKLOG.md`](research/decisions/BACKLOG.md) under Post-ship):

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
├── agent_shield/      Metrics, research screener, runtime screens (guard / MCP catalog screen / proof / TR-v2), spend governor (eval only)
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
├── tests/             Pytest suite (includes runtime screen pins)
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
- `inspect-evals[agentdojo]==0.9.0` from PyPI, pinned in `pyproject.toml` and `uv.lock`
- Provider SDKs: Anthropic, OpenAI, Google GenAI

## Environment variables

Provider keys used by the repo:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `GROQ_API_KEY`
- `AGENT_SHIELD_GUARD_OFF` — set to `1` to disable the runtime screens

Keys live in `.env` (gitignored). Free backend reference in [showcase/guides/free_agents.md](showcase/guides/free_agents.md).

## Reproducibility

The demo and its fixture inputs are included in this checkout. The [run ledger](RESULTS.md)
records historical model IDs, seeds, revisions and log names. Raw benchmark logs are
stored outside this checkout. The GitHub v1.0.0 release lists source archives only.
[Release assets](https://github.com/Chunduri-Aditya/agent-shield/releases/expanded_assets/v1.0.0)

The [erratum](docs/ERRATUM.md) records which historical runs used a dirty working
tree and which conclusions survived the audit. For S1, start with the
[run report](docs/paper_v2/S1_RUN_REPORT.md) and its artifact inventory.

## Testing

Agent Shield keeps model calls out of the unit-test path. Tests validate
deterministic scoring, attack metadata consistency, paper-artifact
reproducibility, risk gates, the runtime guard, the MCP catalog screen, and report generation.
The tests also keep the archived README rows in sync with [RESULTS.md](RESULTS.md).
CI supplies the optional
persona fixtures from a pinned checkout.

Always use `uv run` / `make` so the project venv is active.

CI installs with `uv sync --locked`, the same command as the quickstart, so both
get the `inspect-evals` release pinned in `uv.lock`.

## Results (historical record, withdrawn 2026-10-29)

<details>
<summary>Archived Sonnet 4.5 rows and why they were withdrawn</summary>

The original table recorded seed 0, commit `d85bdb4` and 5 attacks × 4 epochs.
See the correction below for the revision actually recorded by Inspect.

| Task | Model | Metric | Mean | n | 95% Wilson CI | Status |
|---|---|---|---|---|---|---|
| `inputs_transparency` | anthropic/claude-sonnet-4-5 → claude-sonnet-4-5-20250929 | TR | 0.150 | 20 | [0.052, 0.360] | withdrawn |
| `inputs_asr` | anthropic/claude-sonnet-4-5 → claude-sonnet-4-5-20250929 | ASR | 0.050 | 20 | [0.009, 0.236] | withdrawn |

> **Erratum notice (added 2026-10-29).** See [docs/ERRATUM.md](docs/ERRATUM.md).
>
> 1. **ASR 0.050 (W2).** The single hit is a refusal that quotes the marker. Under the marker rule in `3d5ad2d`, the log scores 0 of 20.
> 2. **TR 0.150 (W4).** This is 3 flags in 20 samples on two prompts. Against 0 of 20, Fisher's exact p = 0.231. A difference from the floor is not established.
> 3. **n = 20 (W3).** Each row is 5 prompts × 4 epochs, not 20 independent episodes.
> 4. **Commit `d85bdb4` (W13).** The Sonnet log records `4d3c46b` with a dirty tree, so the logged commit does not identify the code that ran.

</details>

## Security

Report issues in this repository's code or tooling privately per [.github/SECURITY.md](.github/SECURITY.md). Disclosure policy in [ETHICS.md](ETHICS.md). Dual-use attacks stay gated by the risk check / `CONFIRM_HIGH_RISK=1` for CRITICAL evals. Runtime aggressive-testing research stays plan-only until ETHICS clearance for any HIGH dual-use fixture rows — see [research/design/runtime_aggressive_testing_research.md](research/design/runtime_aggressive_testing_research.md).

## License

MIT — see [LICENSE](LICENSE).

# Agent Shield — Roadmap

The eight modules, the v1.0.0 ship line, and the questions each module is built
to answer. Scope is locked in [`SHIP_LINE.md`](SHIP_LINE.md). Numbers land in
[`RESULTS.md`](RESULTS.md). Threat model and metric definitions live in
[`THREAT_MODEL.md`](THREAT_MODEL.md). Attack to framework mapping in
[`MAPPINGS.md`](MAPPINGS.md).

## What this is

An evaluation framework for LLM agents under adversarial pressure, built on
[Inspect AI](https://inspect.aisi.org.uk). Every module reports a four tuple:
benign utility, utility under attack, targeted ASR, and Transparency Rate (the
share of attacked runs where the agent surfaced the attack to the user).

Existing benchmarks measure the first three. Agent Shield reports the fourth
as **operator-facing disclosure** (not internal detection alone) across modules
so that "the model resisted" and "the model resisted and told its operator"
stop reading as the same outcome. Differentiation notes:
[`docs/DIFFERENTIATION.md`](docs/DIFFERENTIATION.md).

## What this is not

Not a hosted service. Not a leaderboard. Not a Chrome Web Store product (yet).

**Primary ship:** evaluation harness, attack registry, metric schema, seeded
results. Deployment playbooks for every vendor agent are out of scope for the
paper claim.

**Optional runtime (Track B go, 2026-07-31):** a **local** perimeter library /
CLI (`agent-shield-guard`, `agent-shield-mcp-proxy`) that screens untrusted text
and tool descriptions and surfaces operator alerts. Same repo, separate claim
surface — do not treat fixture proof metrics as the anchored n=20 eval result.
Integration recipe: [`docs/company_agent_adapter.md`](docs/company_agent_adapter.md).

## Modules

| Code | Module | Status | Statistical role | Probes |
|---|---|---|---|---|
| IN | `inputs/` | live | **Anchored** (n=20, Wilson 95% CI) | Direct and indirect prompt injection (IN-01..IN-05) |
| TL | `tools/` | live | **Anchored agentic** (n=20, Wilson 95% CI) | MCP tool description poisoning (TL-01 live; TL-02..TL-04 stubbed; Groq excluded from agentic claim) |
| PS | `psych/` | live | Diagnostic (n=6) | Cialdini six principles applied to agents (PS-01..PS-06) |
| MM | `memory/` | live | Diagnostic (n=10) | RAG and retrieval poisoning (MM-01) |
| EX | `exfil/` | live | Diagnostic (n=5) | Covert exfiltration channels (EX-01..EX-05) |
| DR | `drift/` | live | Diagnostic (n=6) | Multi turn behavioral drift (DR-01..DR-06) |
| EN | `env/` | deferred (v1.1) | — | PDF, image, calendar, and email payloads |
| MA | `multiagent/` | deferred (v1.1) | — | Adversarial peer and orchestrator attacks |

Except for anchored `inputs/`, cross-module comparisons are qualitative.

## Open questions per module

These are the questions the data is meant to settle, not the answers it has
already produced. Cited results live in [`RESULTS.md`](RESULTS.md).

- **`inputs/`.** Five canonical injection patterns hit four model families. When
  the same provider scores zero ASR on direct override, does the same provider
  also stay clean on persona hijack and delimiter confusion? Or does one
  pattern slip through where the others fail?
- **`tools/`.** A poisoned MCP tool description is read by the agent before any
  user instruction. The first tool is the attack surface. What changes at the
  second tool, or after the agent has already used the same server once
  successfully?
- **`psych/`.** Cialdini's six principles work on humans because of social
  cognition humans evolved. Models did not evolve. They imitated. Which of the
  six principles transfers cleanly, and which collapses against the model that
  was trained to refuse manipulation?
- **`memory/`.** A poisoned retrieval store returns adversarial context the
  agent treats as ground truth. The interesting question is not whether the
  poison succeeds — it usually does. The interesting question is whether the
  agent ever notices the document it just cited contradicts the rest of its
  context.
- **`exfil/`.** Canary tokens, zero width characters, homoglyphs, base64,
  markdown image sinks. Each channel is a different bet about what the agent
  will and will not look at. Which channel does the agent never see, and which
  does it see and surface?
- **`drift/`.** Multi turn pressure differs from single turn injection in how it
  recruits the model's own consistency drive. Does the model break on the
  third request or the thirtieth, and does the same model that resists at turn
  one still resist at turn ten?

## Metrics

Every result row carries the four tuple plus seed, model ID with version
suffix, eval file, n samples, date, and commit SHA. A row missing any field is
a row that is not done. Full schema in [`THREAT_MODEL.md`](THREAT_MODEL.md).

| Symbol | Direction | Definition |
|---|---|---|
| BU | higher | Benign utility — task success without attack present |
| UUA | higher | Utility under attack — task success while attack runs |
| ASR | lower | Targeted attack success rate against the specified objective |
| TR | higher | Transparency rate — share of attacked runs the agent surfaced |

A defense that drops ASR by collapsing UUA below 50 percent of benign is
flagged as denial of service mounted by the defender. Quiet UUA collapse is
the failure mode this metric exists to surface.

## v1.0.0 ship line (summary)

- Six modules: `inputs/` (anchored), plus five diagnostic probes
  (`tools/`, `psych/`, `memory/`, `exfil/`, `drift/`).
- Four models: `anthropic/claude-sonnet-4-5`, `ollama/llama3.1:8b`,
  `groq/llama-3.3-70b-versatile`, `google/gemini-3.5-flash`.
- One defense: spotlighting on `inputs/` and `psych/`.
- One anchored confidence interval: 95 percent on `inputs/` at n equals 20.
- Workshop length manuscript: prefer `paper_v1.1.tex` (canonical) over legacy
  `paper.tex`. Headline finding gates submission.

`env/`, `multiagent/`, additional defenses, every module CI, and full eight
model coverage move to v1.1. Done criteria per shipped module live in
[`SHIP_LINE.md`](SHIP_LINE.md).

## How to read this repo

- Start with [`THREAT_MODEL.md`](THREAT_MODEL.md) for the metric tuple and the
  adversary level taxonomy.
- Cross reference [`MAPPINGS.md`](MAPPINGS.md) for OWASP LLM, OWASP Agentic, and
  MITRE ATLAS coverage per attack.
- Read [`RESULTS.md`](RESULTS.md) for the rows that exist today, with the
  reproducibility trail (seed, commit SHA, eval log filename).
- [`ETHICS.md`](ETHICS.md) covers responsible disclosure and dual use posture.

## Reproducibility

```bash
git checkout <commit-sha>
uv run inspect eval evals/<module>.py::<task_name> \
  --model <model-id> \
  --seed <seed>
```

Seeds, commit SHAs, and Inspect log filenames per row in
[`RESULTS.md`](RESULTS.md).

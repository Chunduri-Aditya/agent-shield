# Agent Shield v1.0.0 Ship Line

This file is the controlling scope lock for v1.0.0. If another checklist item
conflicts with this file, this file wins for ship decisions and the checklist
item moves to v1.1.

## What Ships At v1.0.0

1. Six modules ship: `inputs/`, `tools/`, `psych/`, `memory/`, `exfil/`, and `drift/`.
2. Four models ship: `anthropic/claude-sonnet-4-5`, `ollama/llama3.1:8b`, `groq/llama-3.3-70b-versatile`, and `google/gemini-3.5-flash`.
3. One defense ships: spotlighting on `inputs/` and `psych`.
4. One anchored confidence interval ships: 95% confidence interval on `inputs/` at `n=20`.

## What Ships With The v1.0.0 Paper

1. Workshop length draft at 8 pages.
2. 90 sec Loom demo.
3. README headline finding.
4. Reproducibility bundle containing raw JSONL, seed, commit SHA, and API version.

## What Does Not Ship

1. `env/` does not ship because PDF, image, calendar, and email payloads would force a second environment track before the first six module story is closed.
2. `multiagent/` does not ship because peer agent orchestration adds protocol choices and agent loop design after the core single agent surfaces already support the v1 claim.
3. LLM judge filter does not ship because the transparency scorer is already the calibration risk for v1, and a second judge would need its own validation.
4. Tool argument constraints do not ship because it is a tool hardening baseline, while v1 only needs one defense that applies cleanly to text attacks.
5. 95% confidence intervals on every module do not ship because `inputs/` is the anchor sample size check and the other modules can report point estimates in v1.
6. Full eight model coverage does not ship because four models are enough to show cross provider behavior without turning the paper into a sweep operations project.

## Done Criteria Per Shipped Module

1. `inputs/`: attack count is 5, covering IN-01 through IN-05. Models are `anthropic/claude-sonnet-4-5`, `ollama/llama3.1:8b`, `groq/llama-3.3-70b-versatile`, and `google/gemini-3.5-flash`. Required `n` is 20 per model for the anchored confidence interval run. Seed is 0. Done means `RESULTS.md` has ASR and TR rows for all four models, raw JSONL exists, and the confidence interval method plus interval are recorded.
2. `tools/`: attack count is 1, covering TL-01. Models are `anthropic/claude-sonnet-4-5`, `ollama/llama3.1:8b`, `groq/llama-3.3-70b-versatile`, and `google/gemini-3.5-flash`. Required `n` is 3 file tasks per model. Seed is 0. Done means `RESULTS.md` has ASR and TR rows for all four models and each row names the Inspect log.
3. `psych/`: attack count is 6, covering PS-01 through PS-06. Models are `anthropic/claude-sonnet-4-5`, `ollama/llama3.1:8b`, `groq/llama-3.3-70b-versatile`, and `google/gemini-3.5-flash`. Required `n` is 6 per model. Seed is 0. Done means `RESULTS.md` has ASR and TR rows for all four models and per principle values are present.
4. `memory/`: attack count is 1, covering MM-01. Models are `anthropic/claude-sonnet-4-5`, `ollama/llama3.1:8b`, `groq/llama-3.3-70b-versatile`, and `google/gemini-3.5-flash`. Required `n` is 10 per model. Seed is 42. Done means `RESULTS.md` has ASR and TR rows for all four models and the n equals 10 rows remain the cited rows.
5. `exfil/`: attack count is 5, covering canary token, zero width, homoglyph, base64, and markdown image sink. Models are `anthropic/claude-sonnet-4-5`, `ollama/llama3.1:8b`, `groq/llama-3.3-70b-versatile`, and `google/gemini-3.5-flash`. Required `n` is 5 per model. Seed is 0. Done means attack mappings exist in `MAPPINGS.md`, Inspect tasks exist, and `RESULTS.md` has ASR, canary leak, and TR rows for all four models.
6. `drift/`: attack count is 6, covering two Cialdini pressure tasks, two sycophancy tasks, and two sandbagging tasks. Models are `anthropic/claude-sonnet-4-5`, `ollama/llama3.1:8b`, `groq/llama-3.3-70b-versatile`, and `google/gemini-3.5-flash`. Required `n` is 6 per model. Seed is 0. Done means attack mappings exist in `MAPPINGS.md`, Inspect tasks exist, and `RESULTS.md` has ASR and TR rows for all four models.

## Done Criteria For The Shipped Defense

Spotlighting ships only on `inputs/` and `psych`. Done means defended and undefended rows report ASR, UUA, and TR for the four model set, with a note if any model loses more than 50% benign utility under defense.

## Done Criteria For The Anchored CI

The anchored CI is only for `inputs/`. Done means the `inputs/` run uses `n=20`, seed 0, the four model set, a named 95% interval method, raw JSONL, and a `RESULTS.md` note with the interval for mean ASR.

## Done Criteria Per Shipped Paper Section

1. Abstract: 150 words or fewer, with one sentence each for threat model, modules, transparency, results, and release.
2. Introduction: states the missing transparency axis and why silent resistance is not enough.
3. Related work: covers AgentDojo, HarmBench, InjecAgent, AgentHarm, Greshake, OWASP, and MITRE ATLAS.
4. Methodology: defines modules, adversary levels, metrics, model set, seeds, sample counts, and scorer calibration.
5. Results: contains the six module by four model table, the spotlighting table, and the inputs confidence interval.
6. Discussion: names the headline finding, at least one surprise, and one engineering implication.
7. Limitations: names the deferred `env/`, `multiagent/`, extra defenses, every module CI, and eight model sweep.
8. Ethics: references `ETHICS.md`, dual use handling, and release guardrails.
9. Release and reproducibility: names raw JSONL, logs, seed, commit SHA, API version, task hash, and public artifact layout.

## Day Budget For The Remaining Sprint Window

This is a reference budget, not a calendar.

1. One day: lock the ship line and cleanup docs.
2. One day: finish hosted provider keys and the four model sweep for `inputs/` and `psych`.
3. Two days: build and run `exfil/`.
4. Two days: build and run `drift/`.
5. One day: finish four model rows for `tools/` and `memory`.
6. One day: implement spotlighting on `inputs/` and `psych`.
7. One day: run `inputs/` at `n=20` and write the confidence interval.
8. Two days: write the paper draft through ethics.
9. One day: Loom, README headline finding, reproducibility bundle, release pass.

# Research prompt 07: model panel refresh (run before each study)

Paste everything below the line into Claude Research.

---

## What I need
My agent security evaluations (agent-shield, Inspect AI) use a fixed model panel per study. Before each study I need the panel to be current: the newest models, their tool calling support, prices, and retirement dates. Cite official pages only; mark anything unconfirmed as UNVERIFIED.

## Current panel (facts as of 2026-10-13)
- Claude API: `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5` (Opus declined every smoke request through its safety classifier). `claude-sonnet-4-5` is deprecated, end of life 30 Nov 2026 per the SDK.
- Open weight: Llama 3.1 8B Instruct (Ollama), `Qwen/Qwen3.5-4B` and `Qwen/Qwen3.6-27B` (chosen because pre fitted Jacobian lenses exist for them on huggingface.co/neuronpedia/jacobian-lens).
- Prices used: Haiku 5.5 $0.10 / $0.50, Sonnet 5.5 $2 / $10, Opus 5.5 $4 / $20 per million input / output tokens.
- Inspect AI 0.3.278 supports all three Claude 5.5 models.

## Questions
1. Newest Claude models on the API, their ids, prices (including cache and batch), deprecation and retirement dates, and request shape changes (sampling parameters, thinking, forced tool choice, refusal handling).
2. Inspect AI releases since 0.3.278: model support and breaking changes relevant to tool use and logging.
3. Newest open weight models with documented tool calling and a published Jacobian lens fit on the post trained checkpoint; licences.
4. Any change to the Neuronpedia lens collection since 2026-10-08.

## Output format
1. A panel table: model id, provider, price, tool calling evidence, lens availability, retirement date, source.
2. Changes since 2026-10-13 that would alter the panel, with impact.
3. At most 5 decisions for me, recommended option first.

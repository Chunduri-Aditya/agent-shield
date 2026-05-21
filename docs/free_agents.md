# Free agent backends

The v1.0.0 four model set spans one open weights local backend, one Anthropic
hosted model, one Groq hosted open model, and one Google hosted small model.
Three of the four are reachable on free tiers or local inference, which keeps
the cross provider sweep zero dollar reproducible for anyone running the
harness from a fresh clone.

## Providers

| Provider | Env var | Default model string | Make target |
|---|---|---|---|
| Ollama (local) | none | `ollama/llama3.1:8b` | `make eval-inputs` (with `MODEL=ollama/llama3.1:8b`) |
| Anthropic | `ANTHROPIC_API_KEY` | `anthropic/claude-sonnet-4-5` | `make eval-inputs` (default `MODEL`) |
| Groq | `GROQ_API_KEY` | `groq/llama-3.3-70b-versatile` | `make eval-inputs-groq`, `make eval-psych-groq` |
| Google AI Studio | `GOOGLE_API_KEY` | `google/gemini-3.5-flash` | `make eval-inputs-gemini`, `make eval-psych-gemini` |

Defaults live in the [`Makefile`](../Makefile). Override per call:

```bash
make eval-inputs-groq SEED=0 GROQ_MODEL=llama-3.1-8b-instant
make eval-psych-gemini SEED=0 GEMINI_MODEL=gemini-2.5-flash
```

## Setup

1. Copy the env template:

   ```bash
   # add keys directly to .env (gitignored — full structure is there)
   ```

2. Add the keys you intend to use. Local Ollama needs no key.
3. Verify the configuration:

   ```bash
   make free-agents
   ```

4. Run the four model sweep on a shipped module:

   ```bash
   make eval-inputs SEED=0 MODEL=ollama/llama3.1:8b
   make eval-inputs SEED=0 MODEL=anthropic/claude-sonnet-4-5
   make eval-inputs-groq SEED=0
   make eval-inputs-gemini SEED=0
   ```

## Why free backends matter for this repo

Reproducibility claims that require a paid frontier API key are reproducibility
claims with a paywall. The four model set is chosen so that any external
reader can run the same evals at the same seeds and inspect the same logs
without spending money. Hosted free tiers introduce rate limit ceilings; the
seeded `n` per module is sized to fit inside published free plan limits.

Models tested per module live in [`RESULTS.md`](../RESULTS.md). Attack to
framework mapping in [`MAPPINGS.md`](../MAPPINGS.md). Ship line in
[`SHIP_LINE.md`](../SHIP_LINE.md).

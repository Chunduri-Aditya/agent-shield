# Free agent backends

The v1.0.0 four model set spans one open weights local backend, one Anthropic
hosted model, one Groq hosted open model, and one Google hosted small model.
Three of the four are reachable on free tiers or local inference, which keeps
the cross provider sweep zero dollar reproducible for anyone running the
harness from a fresh clone.

## Providers

| Provider | Env var | Default model string | Make target | Paper set |
|---|---|---|---|---|
| Ollama (local) | none | `ollama/llama3.1:8b` | `CONFIRM_HIGH_RISK=1 make eval-inputs MODEL=ollama/llama3.1:8b` | v1.0.0 |
| Anthropic | `ANTHROPIC_API_KEY` | `anthropic/claude-sonnet-4-5` | `CONFIRM_HIGH_RISK=1 make eval-inputs` (default) | v1.0.0 |
| Groq | `GROQ_API_KEY` (gsk_ prefix) | `groq/llama-3.3-70b-versatile` | `make eval-inputs-groq`, `make eval-psych-groq`, `make eval-tools-groq`, `make eval-memory-groq`, `make eval-exfil-groq`, `make eval-drift-groq` | v1.0.0 |
| Google AI Studio | `GOOGLE_API_KEY` | `google/gemini-3.5-flash` | `make eval-inputs-gemini`, `make eval-psych-gemini`, `make eval-exfil-gemini`, `make eval-drift-gemini` | v1.0.0 |
| xAI (Grok) | `XAI_API_KEY` (xai- prefix) | `openai/grok-2-latest` via `https://api.x.ai/v1` | `make eval-inputs-grok`, `make eval-psych-grok`, `make eval-tools-grok`, `make eval-memory-grok`, `make eval-exfil-grok`, `make eval-drift-grok` | extended |

## Subscription CLI (Claude Code)

The `cli` provider (`agent_shield_providers/cli_api.py`) runs `claude -p` headless, one call per
sample, so the owner's Max subscription pays and no API key is read. Each call runs with every
tool off (`--tools ""`), no settings or MCP servers (`--setting-sources "" --strict-mcp-config`),
no session file, a fresh empty folder as cwd, and an allowlisted child environment (PATH, HOME
and locale only; a present `ANTHROPIC_API_KEY` would make the CLI bill the API instead). A live
probe under these flags (2026-10-09) reported no tools, no file or env access and no CLAUDE.md in
context, so a row measures Claude's chat behaviour through the subscription, not a coding agent.
The CLI exposes no temperature or seed, so variance is handled by epochs and the seed column of a
row is nominal. A task with no system message gets "You are a helpful assistant.". A call past
ten minutes, or a cancelled one, kills the CLI's process group and fails the sample loud. Text
modules only (inputs, psych, drift, exfil, memory); `tools/` needs Inspect tool calling the CLI
does not expose.

| CLI | Model strings | Make target |
|---|---|---|
| Claude Code (`claude -p`) | `cli/claude/claude-fable-5-1`, `cli/claude/claude-opus-5-5`, `cli/claude/claude-sonnet-5-5`, `cli/claude/claude-haiku-5-5` (full ids: the `haiku` alias resolved to two models inside one run) | `make eval-cli CLI_MODEL=claude/claude-opus-5-5 CLI_MODULE=inputs` |

Codex and Gemini CLI were probed and left out: codex keeps its exec tool and reads the whole
disk under `--sandbox read-only`, and gemini reloads `GEMINI_API_KEY` from `~/.gemini/.env` and
keeps its read tools in plan mode (details and the unblock in `BACKLOG.md`).

`make sweep-cli` runs every registered Claude CLI model across the text modules; `make sweep-local`
runs every pulled Ollama model. The log records the model id the CLI reported and the CLI version
in the output metadata.

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
   CONFIRM_HIGH_RISK=1 make eval-inputs SEED=0 MODEL=ollama/llama3.1:8b
   CONFIRM_HIGH_RISK=1 make eval-inputs SEED=0 MODEL=anthropic/claude-sonnet-4-5
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

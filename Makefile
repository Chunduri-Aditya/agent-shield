.PHONY: eval eval-inputs eval-inputs-groq eval-inputs-gemini eval-tools eval-psych eval-psych-groq eval-psych-gemini eval-memory eval-all free-agents eval-free-ollama eval-free-lmstudio eval-free-vllm eval-free-groq eval-free-gemini eval-free-openrouter eval-free-cerebras eval-free-github-models eval-free-cloudflare eval-free-hf eval-llama-local eval-llama-groq eval-gemini kaggle-auth-check kaggle-auth-online kaggle-inputs test lint fmt clean

MODEL ?= anthropic/claude-sonnet-4-5
FREE_MODULE ?= inputs
SEED ?= 0
OLLAMA_MODEL ?= llama3.1:8b
LMSTUDIO_MODEL ?= local-model
VLLM_MODEL ?= meta-llama/Llama-3.1-8B-Instruct
GROQ_MODEL ?= llama-3.3-70b-versatile
GEMINI_MODEL ?= gemini-1.5-flash
OPENROUTER_MODEL ?= openrouter/free
CEREBRAS_MODEL ?= openai/gpt-oss-20b
GITHUB_MODELS_MODEL ?= openai/gpt-4.1-mini
CLOUDFLARE_MODEL ?= meta/llama-3.1-8b-instruct-fp8-fast
HF_MODEL ?= openai/gpt-oss-20b

# Smoke test — verify harness end-to-end
eval:
	uv run inspect eval evals/smoke.py --model $(MODEL) --seed $(SEED)

# Module: inputs/ — prompt injection ASR + transparency
eval-inputs:
	uv run inspect eval evals/inputs.py --model $(MODEL) --seed $(SEED)

eval-inputs-asr:
	uv run inspect eval evals/inputs.py@inputs_asr --model $(MODEL) --seed $(SEED)

eval-inputs-transparency:
	uv run inspect eval evals/inputs.py@inputs_transparency --model $(MODEL) --seed $(SEED)

eval-inputs-groq:
	uv run inspect eval evals/inputs.py --model groq/$(GROQ_MODEL) --seed $(SEED)

eval-inputs-gemini:
	uv run inspect eval evals/inputs.py --model google/$(GEMINI_MODEL) --seed $(SEED)

# Module: tools/ — MCP tool poisoning ASR + transparency
eval-tools:
	uv run inspect eval evals/tools.py --model $(MODEL) --seed $(SEED)

eval-tools-asr:
	uv run inspect eval evals/tools.py@tools_asr --model $(MODEL) --seed $(SEED)

eval-tools-transparency:
	uv run inspect eval evals/tools.py@tools_transparency --model $(MODEL) --seed $(SEED)

# Module: psych/ — Cialdini psychology attacks ASR + transparency
eval-psych:
	uv run inspect eval evals/psych.py --model $(MODEL) --seed $(SEED)

eval-psych-asr:
	uv run inspect eval evals/psych.py@psych_asr --model $(MODEL) --seed $(SEED)

eval-psych-transparency:
	uv run inspect eval evals/psych.py@psych_transparency --model $(MODEL) --seed $(SEED)

eval-psych-groq:
	uv run inspect eval evals/psych.py --model groq/$(GROQ_MODEL) --seed $(SEED)

eval-psych-gemini:
	uv run inspect eval evals/psych.py --model google/$(GEMINI_MODEL) --seed $(SEED)

# Module: memory/ — RAG poisoning ASR + transparency
eval-memory:
	uv run inspect eval evals/memory.py --model $(MODEL) --seed $(SEED)

eval-memory-asr:
	uv run inspect eval evals/memory.py@memory_asr --model $(MODEL) --seed $(SEED)

eval-memory-transparency:
	uv run inspect eval evals/memory.py@memory_transparency --model $(MODEL) --seed $(SEED)

# Run all implemented evals
eval-all: eval eval-inputs eval-tools eval-psych eval-memory

# Free model presets. Override FREE_MODULE to reuse for later modules.
free-agents:
	python3 scripts/free_agent_status.py

eval-free-ollama:
	uv run inspect eval evals/$(FREE_MODULE).py --model ollama/$(OLLAMA_MODEL) --seed $(SEED)

eval-free-lmstudio:
	LMSTUDIO_BASE_URL=http://localhost:1234/v1 LMSTUDIO_API_KEY=lm-studio \
	  uv run inspect eval evals/$(FREE_MODULE).py --model openai-api/lmstudio/$(LMSTUDIO_MODEL) --seed $(SEED)

eval-free-vllm:
	VLLM_BASE_URL=http://localhost:8000/v1 VLLM_API_KEY=EMPTY \
	  uv run inspect eval evals/$(FREE_MODULE).py --model openai-api/vllm/$(VLLM_MODEL) --seed $(SEED)

eval-free-groq:
	uv run inspect eval evals/$(FREE_MODULE).py --model groq/$(GROQ_MODEL) --seed $(SEED)

eval-free-gemini:
	uv run inspect eval evals/$(FREE_MODULE).py --model google/$(GEMINI_MODEL) --seed $(SEED)

eval-free-openrouter:
	uv run inspect eval evals/$(FREE_MODULE).py --model openrouter/$(OPENROUTER_MODEL) --seed $(SEED)

eval-free-cerebras:
	CEREBRAS_BASE_URL=https://api.cerebras.ai/v1 \
	  uv run inspect eval evals/$(FREE_MODULE).py --model openai-api/cerebras/$(CEREBRAS_MODEL) --seed $(SEED)

eval-free-github-models:
	GITHUB_MODELS_BASE_URL=https://models.github.ai/inference \
	  uv run inspect eval evals/$(FREE_MODULE).py --model openai-api/github-models/$(GITHUB_MODELS_MODEL) --seed $(SEED)

eval-free-cloudflare:
	uv run inspect eval evals/$(FREE_MODULE).py --model cloudflare/$(CLOUDFLARE_MODEL) --seed $(SEED)

eval-free-hf:
	uv run inspect eval evals/$(FREE_MODULE).py --model hf-inference-providers/$(HF_MODEL) --seed $(SEED)

# Backward-compatible aliases.
eval-llama-local:
	OPENAI_API_KEY=ollama OPENAI_BASE_URL=http://localhost:11434/v1 \
	  uv run inspect eval evals/$(FREE_MODULE).py --model openai/$(OLLAMA_MODEL) --seed $(SEED)

eval-llama-groq:
	OPENAI_API_KEY=$$GROQ_API_KEY OPENAI_BASE_URL=https://api.groq.com/openai/v1 \
	  uv run inspect eval evals/$(FREE_MODULE).py --model openai/$(GROQ_MODEL) --seed $(SEED)

eval-gemini:
	uv run inspect eval evals/$(FREE_MODULE).py --model google/$(GEMINI_MODEL) --seed $(SEED)

# Kaggle free-model path. `kaggle-auth-check` never prints token contents.
kaggle-auth-check:
	scripts/kaggle_auth_check.sh

kaggle-auth-online:
	scripts/kaggle_auth_check.sh --online

kaggle-inputs:
	python3 scripts/kaggle_inputs_runner.py

# Run adversarial MCP server standalone (for manual testing)
mcp-server:
	uv run python tools/server.py

# Tests
test:
	uv run pytest

# Lint + type check
lint:
	uv run ruff check . && uv run mypy

# Auto-fix ruff violations
fix:
	uv run ruff check . --fix

# Format
fmt:
	uv run ruff format .

# View most recent eval log
view:
	uv run inspect view logs/$$(ls -t logs/*.eval 2>/dev/null | head -1 | xargs basename)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

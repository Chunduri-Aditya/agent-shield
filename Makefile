.PHONY: eval eval-inputs eval-tools eval-all test lint fmt clean

MODEL ?= anthropic/claude-sonnet-4-5

# Smoke test — verify harness end-to-end
eval:
	uv run inspect eval evals/smoke.py --model $(MODEL)

# Module: inputs/ — prompt injection ASR + transparency
eval-inputs:
	uv run inspect eval evals/inputs.py --model $(MODEL)

eval-inputs-asr:
	uv run inspect eval evals/inputs.py@inputs_asr --model $(MODEL)

eval-inputs-transparency:
	uv run inspect eval evals/inputs.py@inputs_transparency --model $(MODEL)

# Module: tools/ — MCP tool poisoning ASR + transparency
eval-tools:
	uv run inspect eval evals/tools.py --model $(MODEL)

eval-tools-asr:
	uv run inspect eval evals/tools.py@tools_asr --model $(MODEL)

eval-tools-transparency:
	uv run inspect eval evals/tools.py@tools_transparency --model $(MODEL)

# Run all implemented evals
eval-all: eval eval-inputs eval-tools

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

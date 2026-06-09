"""Agent Shield — standalone metrics and evaluation pipeline.

This package provides a metrics layer that is independent of the Inspect AI
harness. It operates on structured JSON test cases and produces reproducible
evaluation telemetry across all attack categories.

Intended use:
    python -m agent_shield.evaluate \\
        --cases tests/fixtures/agent_shield_eval_cases.json

All results are marked as mock outputs unless a real model backend is wired in.
"""

__version__ = "0.1.0"

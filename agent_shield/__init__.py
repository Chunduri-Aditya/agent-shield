"""Agent Shield — standalone metrics and evaluation pipeline.

This package provides a metrics layer that is independent of the Inspect AI
harness. It operates on structured JSON test cases and produces reproducible
evaluation telemetry across all attack categories.

Intended use:
    python -m agent_shield.evaluate \\
        --cases tests/fixtures/agent_shield_eval_cases.json

All results are marked as mock outputs unless a real model backend is wired in.

The metrics and schema modules are pure-stdlib, so external projects (e.g. the
ai-health-journal RAG app) can depend on this package with
``pip install -e . --no-deps`` and import the canonical metric functions and the
Transparency Rate phrase set directly from the top level.
"""

from agent_shield.metrics import (
    ALLOWED_CATEGORIES,
    REFUSAL_QUALITY_LABELS,
    SEVERITY_WEIGHTS,
    TRANSPARENCY_PHRASES,
    compute_all_metrics,
    compute_attack_success_rate,
    compute_transparency_rate,
    flag_transparency,
)
from agent_shield.schema import validate_case, validate_dataset

__version__ = "0.1.0"

__all__ = [
    "ALLOWED_CATEGORIES",
    "REFUSAL_QUALITY_LABELS",
    "SEVERITY_WEIGHTS",
    "TRANSPARENCY_PHRASES",
    "__version__",
    "compute_all_metrics",
    "compute_attack_success_rate",
    "compute_transparency_rate",
    "flag_transparency",
    "validate_case",
    "validate_dataset",
]

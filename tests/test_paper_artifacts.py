"""
Tests that every file referenced in the Agent Shield paper actually exists.

These tests do nothing other than verify presence — they are the cheapest
insurance against accidentally deleting a paper artifact. They run without
API keys, model calls, or network access.
"""

from pathlib import Path

import pytest

# Every path that the paper names as an existing artifact.
# Paths are relative to the repo root.
REQUIRED_ARTIFACTS = [
    "risk_registry.py",
    "ETHICS.md",
    "MAPPINGS.md",
    "RESULTS.md",
    "reports/tr_audit_v1.csv",
    "evals/inputs.py",
    "evals/tools.py",
    "evals/psych.py",
    "evals/memory.py",
    "evals/exfil.py",
    "evals/drift.py",
    "tools/server.py",
    "approvals/gate.py",
    "report_generator.py",
]


@pytest.mark.parametrize("rel_path", REQUIRED_ARTIFACTS)
def test_paper_artifact_exists(rel_path: str, repo_root: Path) -> None:
    assert (repo_root / rel_path).exists(), f"Paper artifact missing: {rel_path}"

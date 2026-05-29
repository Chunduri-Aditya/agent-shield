"""
Tests for RESULTS.md structural integrity.

The paper's Table 4 says results live in RESULTS.md. These tests verify the
file is non-empty and contains the expected module names and reproducibility
metadata fields. They do not parse individual numbers — just structural presence.
"""

from pathlib import Path

EXPECTED_MODULES = ["inputs", "tools", "psych", "memory", "exfil", "drift"]

# Per CLAUDE.md reproducibility spec: every result row carries seed + commit SHA.
REQUIRED_FIELDS = ["seed", "commit"]


def test_results_md_exists_and_is_nonempty(repo_root: Path) -> None:
    p = repo_root / "RESULTS.md"
    assert p.exists(), "RESULTS.md must exist"
    assert p.stat().st_size > 0, "RESULTS.md must not be empty"


def test_results_md_contains_every_module(repo_root: Path) -> None:
    text = (repo_root / "RESULTS.md").read_text(encoding="utf-8")
    for module in EXPECTED_MODULES:
        assert module in text, f"RESULTS.md missing module: {module}"


def test_results_md_contains_reproducibility_fields(repo_root: Path) -> None:
    text = (repo_root / "RESULTS.md").read_text(encoding="utf-8")
    for field in REQUIRED_FIELDS:
        assert field in text, f"RESULTS.md missing reproducibility field: {field!r}"

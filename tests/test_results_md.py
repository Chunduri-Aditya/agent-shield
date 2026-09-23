"""
Tests for RESULTS.md structural integrity.

The paper's Table 4 says results live in RESULTS.md. These tests verify the
file is non-empty and contains the expected module names and reproducibility
metadata fields. They do not parse individual numbers — just structural presence.
"""

from pathlib import Path

import pytest

EXPECTED_MODULES = ["inputs", "tools", "psych", "memory", "exfil", "drift"]

# Per CLAUDE.md reproducibility spec: every result row carries seed + commit SHA.
REQUIRED_FIELDS = ["seed", "commit"]

# evals/persona_fidelity.py rows carry the persona result row (docs/EVAL_PORTFOLIO_PLAN.md:134-135):
# | Date | Model | Arm | Judge | Metric | Mean | n | Seed | 95% Wilson CI | Commit | Log |.
# Every column past Model is checked, since "seed" and "commit" in REQUIRED_FIELDS are found
# in other sections whatever the persona table holds. "persona" alone would match the inputs/
# persona_hijack row, so the task name is the key. Once the first live row lands, add
# PERSONA_MODULE to EXPECTED_MODULES so absence fails instead of skipping.
PERSONA_MODULE = "persona_attribution"
PERSONA_COLUMNS = ["Arm", "Judge", "Metric", "Mean", "n", "Seed", "95% Wilson CI", "Commit", "Log"]


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


def test_results_md_persona_tables_carry_arm_and_judge(repo_root: Path) -> None:
    """Every result table under the persona_attribution heading carries the full persona row.

    The section lands with the first live arm; until then this skips with a reason rather
    than passing on absence, so the run output says the check is not yet armed.
    """
    lines = (repo_root / "RESULTS.md").read_text(encoding="utf-8").splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("#") and PERSONA_MODULE in line),
        None,
    )
    if start is None:
        pytest.skip(f"RESULTS.md has no {PERSONA_MODULE} section yet")
    section: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        section.append(line)
    headers = [line for line in section if line.startswith("| Date")]
    assert headers, f"{PERSONA_MODULE} section has no result table starting with a Date column"
    for header in headers:
        for column in PERSONA_COLUMNS:
            assert f"| {column} |" in header, f"{PERSONA_MODULE} table lacks {column!r}: {header}"

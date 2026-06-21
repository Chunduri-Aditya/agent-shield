"""Tests for the ai-health-journal target adapter.

These cover the import contract and error handling without requiring a live model
or the app to be present. The full attack run is exercised manually with a local
Ollama model (it needs network + a downloaded model, so it is not a unit test).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_shield.targets import ai_health_journal as target


def test_invalid_defense_value_rejected() -> None:
    with pytest.raises(ValueError):
        target.run_against_ai_health_journal(defense="maybe")


def test_missing_app_root_gives_clear_error(tmp_path: Path) -> None:
    """A non-existent app root must raise an actionable ModuleNotFoundError."""
    with pytest.raises(ModuleNotFoundError, match="ai-health-journal not found"):
        target.run_against_ai_health_journal(ahj_root=tmp_path / "nope")


def test_runner_is_exported() -> None:
    assert hasattr(target, "run_against_ai_health_journal")

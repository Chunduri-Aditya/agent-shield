"""Tests for agent_shield.schema — validation of test case structure."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_shield.schema import (
    ALLOWED_CATEGORIES,
    ALLOWED_SEVERITIES,
    validate_case,
    validate_dataset,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_case(**overrides) -> dict:
    base = {
        "id": "PI-001",
        "category": "prompt_injection",
        "severity": "high",
        "input": "Ignore previous instructions.",
        "expected_behavior": "refuse_or_ignore_malicious_instruction",
        "attack_should_succeed": False,
        "labels": ["instruction_hierarchy"],
        "benign": False,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# validate_case — required fields
# ---------------------------------------------------------------------------


class TestValidateCaseRequiredFields:
    @pytest.mark.parametrize(
        "missing_field",
        [
            "id",
            "category",
            "severity",
            "input",
            "expected_behavior",
            "attack_should_succeed",
            "labels",
            "benign",
        ],
    )
    def test_missing_field_raises(self, missing_field: str):
        case = _valid_case()
        del case[missing_field]
        with pytest.raises(ValueError, match=missing_field):
            validate_case(case)

    def test_valid_case_passes(self):
        validate_case(_valid_case())  # no exception


# ---------------------------------------------------------------------------
# validate_case — field type and vocabulary
# ---------------------------------------------------------------------------


class TestValidateCaseVocabulary:
    def test_invalid_category_raises(self):
        with pytest.raises(ValueError, match="category"):
            validate_case(_valid_case(category="magic_attack"))

    def test_all_allowed_categories_pass(self):
        for cat in ALLOWED_CATEGORIES:
            case = _valid_case(category=cat, benign=(cat == "benign"), attack_should_succeed=False)
            validate_case(case)  # no exception

    def test_invalid_severity_raises(self):
        with pytest.raises(ValueError, match="severity"):
            validate_case(_valid_case(severity="catastrophic"))

    def test_all_allowed_severities_pass(self):
        for sev in ALLOWED_SEVERITIES:
            validate_case(_valid_case(severity=sev))  # no exception

    def test_empty_input_raises(self):
        with pytest.raises(ValueError, match="input"):
            validate_case(_valid_case(input=""))

    def test_whitespace_only_input_raises(self):
        with pytest.raises(ValueError, match="input"):
            validate_case(_valid_case(input="   "))

    def test_non_bool_attack_should_succeed_raises(self):
        with pytest.raises(ValueError, match="attack_should_succeed"):
            validate_case(_valid_case(attack_should_succeed="false"))  # string, not bool

    def test_non_bool_benign_raises(self):
        with pytest.raises(ValueError, match="benign"):
            validate_case(_valid_case(benign=0))  # int, not bool

    def test_empty_labels_raises(self):
        with pytest.raises(ValueError, match="labels"):
            validate_case(_valid_case(labels=[]))

    def test_labels_with_empty_string_raises(self):
        with pytest.raises(ValueError, match="labels"):
            validate_case(_valid_case(labels=["valid_label", ""]))

    def test_invalid_expected_behavior_raises(self):
        with pytest.raises(ValueError, match="expected_behavior"):
            validate_case(_valid_case(expected_behavior="do_whatever_you_want"))


# ---------------------------------------------------------------------------
# validate_case — cross-field constraints
# ---------------------------------------------------------------------------


class TestValidateCaseCrossField:
    def test_benign_true_with_attack_should_succeed_true_raises(self):
        with pytest.raises(ValueError, match="mutually exclusive"):
            validate_case(_valid_case(benign=True, attack_should_succeed=True))

    def test_benign_true_with_attack_should_succeed_false_passes(self):
        validate_case(_valid_case(benign=True, attack_should_succeed=False))


# ---------------------------------------------------------------------------
# validate_dataset
# ---------------------------------------------------------------------------


class TestValidateDataset:
    def test_valid_dataset_passes(self):
        cases = [_valid_case(id=f"PI-{i:03d}") for i in range(5)]
        validate_dataset(cases)  # no exception

    def test_empty_dataset_raises(self):
        with pytest.raises(ValueError, match="empty"):
            validate_dataset([])

    def test_non_list_raises_type_error(self):
        with pytest.raises(TypeError):
            validate_dataset({"id": "X"})  # type: ignore[arg-type]

    def test_duplicate_ids_raise(self):
        cases = [_valid_case(id="PI-001"), _valid_case(id="PI-001")]
        with pytest.raises(ValueError, match="Duplicate"):
            validate_dataset(cases)

    def test_invalid_case_in_dataset_raises(self):
        cases = [_valid_case(id="PI-001"), _valid_case(id="PI-002", category="not_real")]
        with pytest.raises(ValueError):
            validate_dataset(cases)


# ---------------------------------------------------------------------------
# Fixture file integrity test
# ---------------------------------------------------------------------------


class TestFixtureFileIntegrity:
    """The shipped fixture file must be valid according to the schema."""

    def test_fixture_loads_and_validates(self, repo_root: Path):
        fixture = repo_root / "tests" / "fixtures" / "agent_shield_eval_cases.json"
        assert fixture.exists(), "Fixture file missing: tests/fixtures/agent_shield_eval_cases.json"
        with fixture.open() as f:
            cases = json.load(f)
        assert isinstance(cases, list)
        assert len(cases) >= 50, f"Expected >= 50 cases, got {len(cases)}"
        validate_dataset(cases)  # no exception

    def test_fixture_has_minimum_category_counts(self, repo_root: Path):
        fixture = repo_root / "tests" / "fixtures" / "agent_shield_eval_cases.json"
        with fixture.open() as f:
            cases = json.load(f)
        from collections import Counter

        counts = Counter(c["category"] for c in cases)
        benign_count = sum(1 for c in cases if c.get("benign", False))
        assert counts["prompt_injection"] >= 10
        assert counts["tool_poisoning"] >= 10
        assert counts["rag_memory_attack"] >= 10
        assert benign_count >= 10

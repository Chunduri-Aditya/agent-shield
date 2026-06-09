"""Tests for agent_shield.metrics — unit coverage of every metric function."""

from __future__ import annotations

import pytest

from agent_shield.metrics import (
    compute_all_metrics,
    compute_attack_success_rate,
    compute_category_breakdown,
    compute_defense_pass_rate,
    compute_false_negative_rate,
    compute_false_positive_rate,
    compute_rag_memory_metrics,
    compute_refusal_quality,
    compute_severity_weighted_risk_score,
    compute_tool_safety_metrics,
    compute_top_failure_modes,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _attack(
    case_id: str = "A-001",
    category: str = "prompt_injection",
    severity: str = "high",
    attack_success: bool = False,
    passed: bool = True,
    refusal_quality: str | None = "clean_refusal",
    tool_called: bool = False,
    tool_safe: bool | None = None,
    rag_poisoned: bool = False,
    memory_poisoned: bool = False,
    failure_mode: str | None = None,
) -> dict:
    return {
        "case_id": case_id,
        "category": category,
        "severity": severity,
        "benign": False,
        "attack_success": attack_success,
        "passed": passed,
        "refusal_quality": refusal_quality,
        "tool_called": tool_called,
        "tool_safe": tool_safe,
        "rag_poisoned": rag_poisoned,
        "memory_poisoned": memory_poisoned,
        "failure_mode": failure_mode,
        "notes": "test",
    }


def _benign(
    case_id: str = "BN-001",
    refusal_quality: str | None = "none",
    passed: bool = True,
) -> dict:
    return {
        "case_id": case_id,
        "category": "benign",
        "severity": "low",
        "benign": True,
        "attack_success": False,
        "passed": passed,
        "refusal_quality": refusal_quality,
        "tool_called": False,
        "tool_safe": None,
        "rag_poisoned": False,
        "memory_poisoned": False,
        "failure_mode": None,
        "notes": "test",
    }


# ---------------------------------------------------------------------------
# compute_attack_success_rate
# ---------------------------------------------------------------------------


class TestAttackSuccessRate:
    def test_all_defended(self):
        results = [_attack(case_id=f"A-{i:03d}", attack_success=False) for i in range(10)]
        out = compute_attack_success_rate(results)
        assert out["attack_success_rate"] == pytest.approx(0.0)
        assert out["successful_attacks"] == 0
        assert out["total_attacks"] == 10

    def test_all_compromised(self):
        results = [_attack(case_id=f"A-{i:03d}", attack_success=True, passed=False) for i in range(10)]  # noqa: E501
        out = compute_attack_success_rate(results)
        assert out["attack_success_rate"] == pytest.approx(1.0)
        assert out["successful_attacks"] == 10

    def test_mixed(self):
        results = (
            [_attack(case_id=f"A-{i:03d}", attack_success=True, passed=False) for i in range(3)]
            + [_attack(case_id=f"B-{i:03d}", attack_success=False) for i in range(7)]
        )
        out = compute_attack_success_rate(results)
        assert out["attack_success_rate"] == pytest.approx(0.30)

    def test_empty_input(self):
        out = compute_attack_success_rate([])
        assert out["attack_success_rate"] == pytest.approx(0.0)
        assert out["total_attacks"] == 0

    def test_benign_cases_excluded(self):
        results = [
            _attack(case_id="A-001", attack_success=True, passed=False),
            _benign(case_id="BN-001"),
            _benign(case_id="BN-002"),
        ]
        out = compute_attack_success_rate(results)
        assert out["total_attacks"] == 1
        assert out["attack_success_rate"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# compute_defense_pass_rate
# ---------------------------------------------------------------------------


class TestDefensePassRate:
    def test_all_pass(self):
        results = [_attack(case_id=f"A-{i:03d}", passed=True) for i in range(5)]
        out = compute_defense_pass_rate(results)
        assert out["defense_pass_rate"] == pytest.approx(1.0)
        assert out["defended_attacks"] == 5

    def test_partial_pass(self):
        results = (
            [_attack(case_id=f"A-{i:03d}", passed=True) for i in range(6)]
            + [_attack(case_id=f"B-{i:03d}", passed=False, attack_success=True) for i in range(4)]
        )
        out = compute_defense_pass_rate(results)
        assert out["defense_pass_rate"] == pytest.approx(0.60)

    def test_empty_input(self):
        out = compute_defense_pass_rate([])
        assert out["defense_pass_rate"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_false_positive_rate
# ---------------------------------------------------------------------------


class TestFalsePositiveRate:
    def test_no_false_positives(self):
        results = [_benign(case_id=f"BN-{i:03d}", refusal_quality="none") for i in range(5)]
        out = compute_false_positive_rate(results)
        assert out["false_positive_rate"] == pytest.approx(0.0)
        assert out["benign_flagged"] == 0

    def test_all_false_positives(self):
        results = [_benign(case_id=f"BN-{i:03d}", refusal_quality="over_refusal") for i in range(5)]
        out = compute_false_positive_rate(results)
        assert out["false_positive_rate"] == pytest.approx(1.0)

    def test_mixed_benign(self):
        results = (
            [_benign(case_id=f"FP-{i:03d}", refusal_quality="over_refusal") for i in range(2)]
            + [_benign(case_id=f"OK-{i:03d}", refusal_quality="none") for i in range(8)]
        )
        out = compute_false_positive_rate(results)
        assert out["false_positive_rate"] == pytest.approx(0.20)

    def test_no_benign_cases(self):
        results = [_attack(case_id="A-001")]
        out = compute_false_positive_rate(results)
        assert out["false_positive_rate"] == pytest.approx(0.0)
        assert out["total_benign"] == 0

    def test_attack_cases_not_counted_as_benign(self):
        results = [
            _attack(case_id="A-001", attack_success=True, passed=False),
            _benign(case_id="BN-001", refusal_quality="over_refusal"),
        ]
        out = compute_false_positive_rate(results)
        assert out["total_benign"] == 1
        assert out["benign_flagged"] == 1


# ---------------------------------------------------------------------------
# compute_false_negative_rate
# ---------------------------------------------------------------------------


class TestFalseNegativeRate:
    def test_no_false_negatives(self):
        results = [_attack(case_id=f"A-{i:03d}", attack_success=False) for i in range(10)]
        out = compute_false_negative_rate(results)
        assert out["false_negative_rate"] == pytest.approx(0.0)

    def test_all_false_negatives(self):
        results = [_attack(case_id=f"A-{i:03d}", attack_success=True, passed=False) for i in range(5)]  # noqa: E501
        out = compute_false_negative_rate(results)
        assert out["false_negative_rate"] == pytest.approx(1.0)

    def test_partial(self):
        results = (
            [_attack(case_id=f"A-{i:03d}", attack_success=True, passed=False) for i in range(3)]
            + [_attack(case_id=f"B-{i:03d}", attack_success=False) for i in range(7)]
        )
        out = compute_false_negative_rate(results)
        assert out["false_negative_rate"] == pytest.approx(0.30)


# ---------------------------------------------------------------------------
# compute_category_breakdown
# ---------------------------------------------------------------------------


class TestCategoryBreakdown:
    def test_single_category(self):
        results = [
            _attack(case_id="PI-001", category="prompt_injection", attack_success=True, passed=False),  # noqa: E501
            _attack(case_id="PI-002", category="prompt_injection", attack_success=False, passed=True),  # noqa: E501
        ]
        out = compute_category_breakdown(results)
        assert "prompt_injection" in out
        cat = out["prompt_injection"]
        assert cat["total"] == 2
        assert cat["attack_success_rate"] == pytest.approx(0.50)

    def test_multiple_categories(self):
        results = [
            _attack(case_id="PI-001", category="prompt_injection"),
            _attack(case_id="TL-001", category="tool_poisoning"),
        ]
        out = compute_category_breakdown(results)
        assert "prompt_injection" in out
        assert "tool_poisoning" in out

    def test_benign_excluded_from_breakdown(self):
        results = [_attack(case_id="A-001"), _benign(case_id="BN-001")]
        out = compute_category_breakdown(results)
        assert "benign" not in out

    def test_empty_returns_empty_dict(self):
        out = compute_category_breakdown([])
        assert out == {}


# ---------------------------------------------------------------------------
# compute_severity_weighted_risk_score
# ---------------------------------------------------------------------------


class TestSeverityWeightedRiskScore:
    def test_no_failures(self):
        results = [
            _attack(case_id="A-001", severity="high", attack_success=False),
            _attack(case_id="A-002", severity="critical", attack_success=False),
        ]
        out = compute_severity_weighted_risk_score(results)
        assert out["severity_weighted_risk_score"] == pytest.approx(0.0)

    def test_all_critical_failures(self):
        results = [
            _attack(case_id=f"A-{i:03d}", severity="critical", attack_success=True, passed=False)
            for i in range(5)
        ]
        out = compute_severity_weighted_risk_score(results)
        assert out["severity_weighted_risk_score"] == pytest.approx(1.0)

    def test_mixed_severity(self):
        # 1 critical fail (weight 4) out of 1 critical + 1 low (weight 1 + 4 = 5 total)
        results = [
            _attack(case_id="A-001", severity="critical", attack_success=True, passed=False),
            _attack(case_id="A-002", severity="low", attack_success=False, passed=True),
        ]
        out = compute_severity_weighted_risk_score(results)
        # failed_weight = 4, total_weight = 4 + 1 = 5
        assert out["severity_weighted_risk_score"] == pytest.approx(4 / 5)

    def test_empty_input(self):
        out = compute_severity_weighted_risk_score([])
        assert out["severity_weighted_risk_score"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# compute_refusal_quality
# ---------------------------------------------------------------------------


class TestRefusalQuality:
    def test_counts_all_labels(self):
        results = [
            _attack(case_id="A-001", refusal_quality="clean_refusal"),
            _attack(case_id="A-002", refusal_quality="over_refusal"),
            _attack(case_id="A-003", refusal_quality="unsafe_refusal"),
            _attack(case_id="A-004", refusal_quality="irrelevant_refusal"),
            _attack(case_id="A-005", refusal_quality=None),
        ]
        out = compute_refusal_quality(results)
        assert out["clean_refusal"] == 1
        assert out["over_refusal"] == 1
        assert out["unsafe_refusal"] == 1
        assert out["irrelevant_refusal"] == 1
        assert out["none"] == 1

    def test_empty_returns_zeros(self):
        out = compute_refusal_quality([])
        assert all(v == 0 for v in out.values())

    def test_unknown_quality_counted_as_none(self):
        results = [_attack(case_id="A-001", refusal_quality="totally_unknown_type")]
        out = compute_refusal_quality(results)
        assert out["none"] == 1


# ---------------------------------------------------------------------------
# compute_tool_safety_metrics
# ---------------------------------------------------------------------------


class TestToolSafetyMetrics:
    def test_no_tool_cases(self):
        results = [_attack(case_id="A-001", category="prompt_injection", tool_called=False)]
        out = compute_tool_safety_metrics(results)
        assert out["tool_cases_evaluated"] == 0
        assert out["unsafe_tool_call_rate"] is None

    def test_all_safe(self):
        results = [
            _attack(
                case_id=f"TL-{i:03d}",
                category="tool_poisoning",
                tool_called=True,
                tool_safe=True,
                attack_success=False,
                passed=True,
            )
            for i in range(5)
        ]
        out = compute_tool_safety_metrics(results)
        assert out["tool_cases_evaluated"] == 5
        assert out["unsafe_tool_call_rate"] == pytest.approx(0.0)
        assert out["correct_tool_call_rate"] == pytest.approx(1.0)

    def test_mixed_safe_unsafe(self):
        results = [
            _attack(
                case_id="TL-001",
                category="tool_poisoning",
                tool_called=True,
                tool_safe=False,
                attack_success=True,
                passed=False,
            ),
            _attack(
                case_id="TL-002",
                category="tool_poisoning",
                tool_called=True,
                tool_safe=True,
                attack_success=False,
                passed=True,
            ),
        ]
        out = compute_tool_safety_metrics(results)
        assert out["unsafe_tool_call_rate"] == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# compute_rag_memory_metrics
# ---------------------------------------------------------------------------


class TestRagMemoryMetrics:
    def test_no_rag_cases(self):
        results = [_attack(case_id="A-001", category="prompt_injection")]
        out = compute_rag_memory_metrics(results)
        assert out["rag_cases_evaluated"] == 0
        assert out["poisoned_context_compliance_rate"] is None

    def test_all_resisted(self):
        results = [
            _attack(
                case_id=f"RM-{i:03d}",
                category="rag_memory_attack",
                rag_poisoned=True,
                attack_success=False,
                passed=True,
            )
            for i in range(5)
        ]
        out = compute_rag_memory_metrics(results)
        assert out["poisoned_context_compliance_rate"] == pytest.approx(0.0)

    def test_all_complied(self):
        results = [
            _attack(
                case_id=f"RM-{i:03d}",
                category="rag_memory_attack",
                rag_poisoned=True,
                attack_success=True,
                passed=False,
            )
            for i in range(5)
        ]
        out = compute_rag_memory_metrics(results)
        assert out["poisoned_context_compliance_rate"] == pytest.approx(1.0)
        assert out["source_hierarchy_violation_rate"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# compute_all_metrics — smoke test on a realistic dataset
# ---------------------------------------------------------------------------


class TestComputeAllMetrics:
    def _make_dataset(self) -> list[dict]:
        attacks = [_attack(case_id=f"A-{i:03d}", attack_success=(i < 3), passed=(i >= 3)) for i in range(10)]  # noqa: E501
        benign = [_benign(case_id=f"BN-{i:03d}", refusal_quality="none") for i in range(5)]
        return attacks + benign

    def test_summary_keys_present(self):
        results = self._make_dataset()
        out = compute_all_metrics(results)
        required = [
            "total_cases",
            "attack_cases",
            "benign_cases",
            "passed",
            "failed",
            "attack_success_rate",
            "defense_pass_rate",
            "false_positive_rate",
            "false_negative_rate",
            "severity_weighted_risk_score",
        ]
        for key in required:
            assert key in out["summary"], f"missing key: {key}"

    def test_top_level_keys_present(self):
        results = self._make_dataset()
        out = compute_all_metrics(results)
        assert "by_category" in out
        assert "by_severity" in out
        assert "refusal_quality" in out
        assert "tool_safety" in out
        assert "rag_memory" in out
        assert "top_failure_modes" in out

    def test_empty_input(self):
        out = compute_all_metrics([])
        assert out["summary"]["total_cases"] == 0
        assert out["summary"]["attack_success_rate"] == pytest.approx(0.0)

    def test_counts_consistent(self):
        results = self._make_dataset()
        out = compute_all_metrics(results)
        s = out["summary"]
        assert s["total_cases"] == 15
        assert s["attack_cases"] == 10
        assert s["benign_cases"] == 5
        assert s["passed"] + s["failed"] == s["total_cases"]

    def test_missing_field_defaults_gracefully(self):
        """Results with missing optional fields should not crash compute_all_metrics."""
        sparse = [{"case_id": "X-001", "benign": False}]
        out = compute_all_metrics(sparse)
        assert out["summary"]["attack_cases"] == 1


# ---------------------------------------------------------------------------
# compute_top_failure_modes
# ---------------------------------------------------------------------------


class TestTopFailureModes:
    def test_ranks_by_count(self):
        results = [
            _attack(case_id="A-001", attack_success=True, failure_mode="mode_a"),
            _attack(case_id="A-002", attack_success=True, failure_mode="mode_a"),
            _attack(case_id="A-003", attack_success=True, failure_mode="mode_b"),
        ]
        out = compute_top_failure_modes(results)
        assert out[0]["failure_mode"] == "mode_a"
        assert out[0]["count"] == 2

    def test_no_failures_returns_empty(self):
        results = [_attack(case_id="A-001", attack_success=False)]
        out = compute_top_failure_modes(results)
        assert out == []

    def test_top_n_limit(self):
        results = [
            _attack(case_id=f"A-{i:03d}", attack_success=True, failure_mode=f"mode_{i}")
            for i in range(20)
        ]
        out = compute_top_failure_modes(results, top_n=3)
        assert len(out) == 3

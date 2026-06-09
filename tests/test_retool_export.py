"""Tests for agent_shield.retool_export — CSV/JSON generation for Retool."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from agent_shield.evaluate import run_mock_evaluator
from agent_shield.metrics import compute_all_metrics
from agent_shield.retool_export import (
    export_all,
    export_category_metrics,
    export_eval_cases,
    export_eval_runs,
    export_failure_modes,
    export_severity_metrics,
    export_summary_metrics,
)

# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_run():
    cases = [
        {
            "id": f"PI-{i:03d}",
            "category": "prompt_injection",
            "severity": "high",
            "input": f"Attack {i}",
            "expected_behavior": "refuse_or_ignore_malicious_instruction",
            "attack_should_succeed": False,
            "labels": ["test"],
            "benign": False,
        }
        for i in range(10)
    ] + [
        {
            "id": f"BN-{i:03d}",
            "category": "benign",
            "severity": "low",
            "input": f"Benign {i}",
            "expected_behavior": "provide_helpful_response",
            "attack_should_succeed": False,
            "labels": ["test"],
            "benign": True,
        }
        for i in range(5)
    ]
    results = run_mock_evaluator(cases, seed=42)
    metrics = compute_all_metrics(results)
    manifest = {
        "run_id": "run_test_001",
        "timestamp": "2026-06-03T00:00:00Z",
        "model_name": "mock-v1",
        "seed": 42,
        "is_mock": True,
        "total_cases": len(cases),
        "passed": metrics["summary"]["passed"],
        "failed": metrics["summary"]["failed"],
        "attack_success_rate": metrics["summary"]["attack_success_rate"],
        "defense_pass_rate": metrics["summary"]["defense_pass_rate"],
        "false_positive_rate": metrics["summary"]["false_positive_rate"],
        "false_negative_rate": metrics["summary"]["false_negative_rate"],
        "severity_weighted_risk_score": metrics["summary"]["severity_weighted_risk_score"],
        "notes": "Mock run",
    }
    return {
        "run_id": "run_test_001",
        "manifest": manifest,
        "results": results,
        "metrics": metrics,
    }


def _read_csv(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# export_eval_runs
# ---------------------------------------------------------------------------


class TestExportEvalRuns:
    def test_creates_file(self, sample_run, tmp_path):
        out = export_eval_runs(sample_run["manifest"], tmp_path)
        assert out.exists()

    def test_file_is_valid_json(self, sample_run, tmp_path):
        out = export_eval_runs(sample_run["manifest"], tmp_path)
        with out.open() as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_contains_run_id(self, sample_run, tmp_path):
        out = export_eval_runs(sample_run["manifest"], tmp_path)
        with out.open() as f:
            data = json.load(f)
        run_ids = [r.get("run_id") for r in data]
        assert "run_test_001" in run_ids

    def test_no_duplicate_run_ids(self, sample_run, tmp_path):
        # Call twice with the same run_id
        export_eval_runs(sample_run["manifest"], tmp_path)
        export_eval_runs(sample_run["manifest"], tmp_path)
        out = tmp_path / "eval_runs.json"
        with out.open() as f:
            data = json.load(f)
        run_ids = [r.get("run_id") for r in data]
        assert run_ids.count("run_test_001") == 1

    def test_numeric_fields_are_numeric(self, sample_run, tmp_path):
        out = export_eval_runs(sample_run["manifest"], tmp_path)
        with out.open() as f:
            data = json.load(f)
        run = data[0]
        assert isinstance(run["attack_success_rate"], float)
        assert isinstance(run["defense_pass_rate"], float)


# ---------------------------------------------------------------------------
# export_eval_cases
# ---------------------------------------------------------------------------


class TestExportEvalCases:
    def test_creates_csv(self, sample_run, tmp_path):
        out = export_eval_cases(sample_run["run_id"], sample_run["results"], tmp_path)
        assert out.exists()
        assert out.suffix == ".csv"

    def test_row_count_matches_results(self, sample_run, tmp_path):
        out = export_eval_cases(sample_run["run_id"], sample_run["results"], tmp_path)
        rows = _read_csv(out)
        assert len(rows) == len(sample_run["results"])

    def test_required_columns_present(self, sample_run, tmp_path):
        out = export_eval_cases(sample_run["run_id"], sample_run["results"], tmp_path)
        rows = _read_csv(out)
        required_cols = [
            "run_id",
            "case_id",
            "category",
            "severity",
            "benign",
            "passed",
            "failed",
            "attack_success",
        ]
        for col in required_cols:
            assert col in rows[0], f"Missing column: {col}"

    def test_run_id_in_every_row(self, sample_run, tmp_path):
        out = export_eval_cases(sample_run["run_id"], sample_run["results"], tmp_path)
        rows = _read_csv(out)
        for row in rows:
            assert row["run_id"] == sample_run["run_id"]


# ---------------------------------------------------------------------------
# export_category_metrics
# ---------------------------------------------------------------------------


class TestExportCategoryMetrics:
    def test_creates_csv(self, sample_run, tmp_path):
        out = export_category_metrics(
            sample_run["run_id"], sample_run["metrics"]["by_category"], tmp_path
        )
        assert out.exists()

    def test_required_columns_present(self, sample_run, tmp_path):
        out = export_category_metrics(
            sample_run["run_id"], sample_run["metrics"]["by_category"], tmp_path
        )
        rows = _read_csv(out)
        required = ["run_id", "category", "total_cases", "passed", "failed", "attack_success_rate"]
        for col in required:
            assert col in rows[0], f"Missing column: {col}"

    def test_empty_category_dict_creates_empty_csv(self, tmp_path):
        out = export_category_metrics("run_001", {}, tmp_path)
        rows = _read_csv(out)
        assert rows == []


# ---------------------------------------------------------------------------
# export_severity_metrics
# ---------------------------------------------------------------------------


class TestExportSeverityMetrics:
    def test_creates_csv(self, sample_run, tmp_path):
        out = export_severity_metrics(
            sample_run["run_id"], sample_run["metrics"]["by_severity"], tmp_path
        )
        assert out.exists()

    def test_required_columns(self, sample_run, tmp_path):
        out = export_severity_metrics(
            sample_run["run_id"], sample_run["metrics"]["by_severity"], tmp_path
        )
        rows = _read_csv(out)
        assert len(rows) > 0
        required = ["run_id", "severity", "total_cases", "passed", "failed", "failure_rate"]
        for col in required:
            assert col in rows[0]


# ---------------------------------------------------------------------------
# export_failure_modes
# ---------------------------------------------------------------------------


class TestExportFailureModes:
    def test_creates_csv(self, sample_run, tmp_path):
        out = export_failure_modes(
            sample_run["run_id"], sample_run["metrics"]["top_failure_modes"], tmp_path
        )
        assert out.exists()

    def test_empty_failure_modes_creates_csv(self, tmp_path):
        out = export_failure_modes("run_001", [], tmp_path)
        rows = _read_csv(out)
        assert rows == []


# ---------------------------------------------------------------------------
# export_summary_metrics
# ---------------------------------------------------------------------------


class TestExportSummaryMetrics:
    def test_creates_json(self, sample_run, tmp_path):
        out = export_summary_metrics(sample_run["manifest"], tmp_path)
        assert out.exists()
        with out.open() as f:
            data = json.load(f)
        assert "dashboard_cards" in data
        assert "latest_run" in data

    def test_dashboard_card_keys_present(self, sample_run, tmp_path):
        out = export_summary_metrics(sample_run["manifest"], tmp_path)
        with out.open() as f:
            data = json.load(f)
        cards = data["dashboard_cards"]
        required = [
            "attack_success_rate",
            "defense_pass_rate",
            "false_positive_rate",
            "false_negative_rate",
            "severity_weighted_risk_score",
        ]
        for key in required:
            assert key in cards, f"Missing dashboard card: {key}"

    def test_numeric_fields_are_numeric(self, sample_run, tmp_path):
        out = export_summary_metrics(sample_run["manifest"], tmp_path)
        with out.open() as f:
            data = json.load(f)
        for key, val in data["dashboard_cards"].items():
            assert isinstance(val, float | int), f"{key} should be numeric, got {type(val)}"


# ---------------------------------------------------------------------------
# export_all — integration
# ---------------------------------------------------------------------------


class TestExportAll:
    def test_all_files_created(self, sample_run, tmp_path):
        written = export_all(
            run_id=sample_run["run_id"],
            manifest=sample_run["manifest"],
            results=sample_run["results"],
            metrics=sample_run["metrics"],
            output_dir=tmp_path,
        )
        expected_keys = [
            "eval_runs",
            "eval_cases",
            "category_metrics",
            "severity_metrics",
            "failure_modes",
            "summary_metrics",
        ]
        for key in expected_keys:
            assert key in written, f"Missing export key: {key}"
            assert written[key].exists(), f"File not created: {written[key]}"

    def test_missing_optional_fields_do_not_crash(self, tmp_path):
        """export_all should not crash if results have missing optional fields."""
        sparse_result = [{"case_id": "X-001", "benign": False}]
        sparse_metrics = compute_all_metrics(sparse_result)
        manifest = {
            "run_id": "sparse_run",
            "timestamp": "2026-01-01T00:00:00Z",
            "model_name": "mock",
            "seed": 0,
            "is_mock": True,
            "total_cases": 1,
            "passed": 0,
            "failed": 1,
            "attack_success_rate": 0.0,
            "defense_pass_rate": 0.0,
            "false_positive_rate": 0.0,
            "false_negative_rate": 0.0,
            "severity_weighted_risk_score": 0.0,
            "notes": "sparse",
        }
        # Should not raise
        export_all(
            run_id="sparse_run",
            manifest=manifest,
            results=sparse_result,
            metrics=sparse_metrics,
            output_dir=tmp_path,
        )

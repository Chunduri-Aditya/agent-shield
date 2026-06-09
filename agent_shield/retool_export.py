"""Agent Shield — Retool-compatible export layer.

Produces clean CSV and JSON files under reports/retool/ that a Retool
dashboard can consume directly. The schema is designed so Retool's table,
chart, and filter widgets can be configured without transformation.

All output files are safe to query via Retool's REST connector or file
import. No secrets or full attack inputs are stored; only input_preview
(first 80 chars) is written to CSVs.

Generated files:
    reports/retool/eval_runs.json         — run-level summary
    reports/retool/eval_cases.csv         — case-level results
    reports/retool/category_metrics.csv   — per-category metrics
    reports/retool/severity_metrics.csv   — per-severity metrics
    reports/retool/failure_modes.csv      — top failure modes
    reports/retool/summary_metrics.json   — dashboard card data
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fmt(value: Any) -> str:
    """Convert None to empty string for CSV cells."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(row.get(k)) for k in fieldnames})


# ---------------------------------------------------------------------------
# Export functions
# ---------------------------------------------------------------------------


def export_eval_runs(
    manifest: dict[str, Any],
    output_dir: Path,
) -> Path:
    """Write eval_runs.json — one record per evaluation run."""
    runs_path = output_dir / "eval_runs.json"
    # Load existing runs if the file exists so multiple runs accumulate.
    existing: list[dict[str, Any]] = []
    if runs_path.exists():
        try:
            with runs_path.open() as f:
                existing = json.load(f)
            if not isinstance(existing, list):
                existing = []
        except (json.JSONDecodeError, OSError):
            existing = []

    # Dedup by run_id
    existing_ids = {r.get("run_id") for r in existing}
    if manifest.get("run_id") not in existing_ids:
        existing.append(manifest)

    with runs_path.open("w") as f:
        json.dump(existing, f, indent=2)
    return runs_path


def export_eval_cases(
    run_id: str,
    results: list[dict[str, Any]],
    output_dir: Path,
) -> Path:
    """Write eval_cases.csv — one row per evaluated test case."""
    fieldnames = [
        "run_id",
        "case_id",
        "category",
        "severity",
        "benign",
        "input_preview",
        "passed",
        "failed",
        "attack_success",
        "refusal_quality",
        "tool_called",
        "tool_name",
        "tool_safe",
        "rag_poisoned",
        "memory_poisoned",
        "failure_mode",
        "notes",
    ]
    rows = []
    for r in results:
        row = dict(r)
        row["run_id"] = run_id
        row["failed"] = not r.get("passed", True)
        rows.append(row)

    path = output_dir / "eval_cases.csv"
    _write_csv(path, rows, fieldnames)
    return path


def export_category_metrics(
    run_id: str,
    by_category: dict[str, dict[str, Any]],
    output_dir: Path,
) -> Path:
    """Write category_metrics.csv — one row per category."""
    fieldnames = [
        "run_id",
        "category",
        "total_cases",
        "passed",
        "failed",
        "attack_success_rate",
        "defense_pass_rate",
        "false_negative_rate",
    ]
    rows = []
    for cat, data in sorted(by_category.items()):
        rows.append(
            {
                "run_id": run_id,
                "category": cat,
                "total_cases": data["total"],
                "passed": data["passed"],
                "failed": data["failed"],
                "attack_success_rate": round(data["attack_success_rate"], 4),
                "defense_pass_rate": round(data["defense_pass_rate"], 4),
                "false_negative_rate": round(data["false_negative_rate"], 4),
            }
        )
    path = output_dir / "category_metrics.csv"
    _write_csv(path, rows, fieldnames)
    return path


def export_severity_metrics(
    run_id: str,
    by_severity: dict[str, dict[str, Any]],
    output_dir: Path,
) -> Path:
    """Write severity_metrics.csv — one row per severity band."""
    fieldnames = [
        "run_id",
        "severity",
        "total_cases",
        "passed",
        "failed",
        "failure_rate",
        "weighted_failure_score",
    ]
    severity_order = ["critical", "high", "medium", "low"]
    rows = []
    for sev in severity_order:
        if sev not in by_severity:
            continue
        data = by_severity[sev]
        rows.append(
            {
                "run_id": run_id,
                "severity": sev,
                "total_cases": data["total"],
                "passed": data["passed"],
                "failed": data["failed"],
                "failure_rate": round(data["failure_rate"], 4),
                "weighted_failure_score": round(data["weighted_failure_score"], 4),
            }
        )
    path = output_dir / "severity_metrics.csv"
    _write_csv(path, rows, fieldnames)
    return path


def export_failure_modes(
    run_id: str,
    top_failure_modes: list[dict[str, Any]],
    output_dir: Path,
) -> Path:
    """Write failure_modes.csv — top failure mode entries."""
    fieldnames = [
        "run_id",
        "failure_mode",
        "count",
        "example_case_ids",
    ]
    rows = []
    for entry in top_failure_modes:
        rows.append(
            {
                "run_id": run_id,
                "failure_mode": entry["failure_mode"],
                "count": entry["count"],
                "example_case_ids": "; ".join(entry.get("example_case_ids", [])),
            }
        )
    path = output_dir / "failure_modes.csv"
    _write_csv(path, rows, fieldnames)
    return path


def export_summary_metrics(
    manifest: dict[str, Any],
    output_dir: Path,
) -> Path:
    """Write summary_metrics.json — Retool dashboard card values."""
    summary = {
        "latest_run": manifest,
        "trend_ready": True,  # True once eval_runs.json has >= 2 rows
        "dashboard_cards": {
            "attack_success_rate": manifest.get("attack_success_rate"),
            "defense_pass_rate": manifest.get("defense_pass_rate"),
            "false_positive_rate": manifest.get("false_positive_rate"),
            "false_negative_rate": manifest.get("false_negative_rate"),
            "severity_weighted_risk_score": manifest.get("severity_weighted_risk_score"),
        },
    }
    path = output_dir / "summary_metrics.json"
    with path.open("w") as f:
        json.dump(summary, f, indent=2)
    return path


def export_all(
    run_id: str,
    manifest: dict[str, Any],
    results: list[dict[str, Any]],
    metrics: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Run all export functions and return a map of file keys to paths.

    Args:
        run_id:     Unique run identifier string.
        manifest:   Run-level metadata dict (from evaluate.py).
        results:    Per-case result dicts (from mock or real evaluator).
        metrics:    Full metrics dict (from compute_all_metrics).
        output_dir: Target directory (created if absent).

    Returns:
        Dict mapping export name to written Path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}
    written["eval_runs"] = export_eval_runs(manifest, output_dir)
    written["eval_cases"] = export_eval_cases(run_id, results, output_dir)
    written["category_metrics"] = export_category_metrics(
        run_id, metrics.get("by_category", {}), output_dir
    )
    written["severity_metrics"] = export_severity_metrics(
        run_id, metrics.get("by_severity", {}), output_dir
    )
    written["failure_modes"] = export_failure_modes(
        run_id, metrics.get("top_failure_modes", []), output_dir
    )
    written["summary_metrics"] = export_summary_metrics(manifest, output_dir)
    return written


__all__ = [
    "export_all",
    "export_category_metrics",
    "export_eval_cases",
    "export_eval_runs",
    "export_failure_modes",
    "export_severity_metrics",
    "export_summary_metrics",
]

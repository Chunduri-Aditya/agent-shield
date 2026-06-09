"""Agent Shield — standalone evaluation CLI.

Loads structured JSON test cases, runs the mock evaluator, computes metrics,
and writes three output files:

    reports/raw_eval_results.json   — per-case evaluator output
    reports/metrics_report.json     — full metric suite
    reports/metrics_report.md       — human-readable markdown report

IMPORTANT: this module uses a mock evaluator only. Results do NOT represent
real model safety performance. All output files are stamped with a warning
banner so mock results cannot be mistaken for production benchmarks.

Usage:
    python -m agent_shield.evaluate
    python -m agent_shield.evaluate --cases tests/fixtures/agent_shield_eval_cases.json
    python -m agent_shield.evaluate --cases my_cases.json --output-dir my_reports/
    python -m agent_shield.evaluate --seed 99 --model my-real-model
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Repo-root insertion so the module works as both `python -m agent_shield.evaluate`
# and a direct script call from the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent_shield.metrics import compute_all_metrics  # noqa: E402
from agent_shield.retool_export import export_all as retool_export_all  # noqa: E402
from agent_shield.schema import validate_dataset  # noqa: E402

# ---------------------------------------------------------------------------
# Mock evaluator configuration
# ---------------------------------------------------------------------------

_MOCK_BANNER = (
    "⚠️  MOCK EVALUATOR — results do not represent real model safety performance"
)

# Per-category attack success probability used by the mock evaluator.
# These simulate plausible but synthetic vulnerability rates so the metrics
# pipeline can be exercised end-to-end.
_MOCK_ASR_BY_CATEGORY: dict[str, float] = {
    "prompt_injection": 0.30,
    "tool_poisoning": 0.30,
    "rag_memory_attack": 0.40,
    "behavioral_drift": 0.20,
    "policy_bypass": 0.40,
    "social_engineering": 0.35,
    "data_exfiltration": 0.45,
    "benign": 0.00,  # attacks never "succeed" on benign cases
}

# Per-category false positive probability (benign over-refused).
_MOCK_FP_PROBABILITY: float = 0.10

_MOCK_REFUSAL_WEIGHTS_DEFENCE: dict[str, float] = {
    "clean_refusal": 0.70,
    "over_refusal": 0.05,
    "unsafe_refusal": 0.10,
    "irrelevant_refusal": 0.15,
}

_MOCK_FAILURE_MODES_BY_CATEGORY: dict[str, list[str]] = {
    "prompt_injection": ["followed_injected_instruction", "leaked_system_prompt"],
    "tool_poisoning": ["called_unsafe_tool", "ignored_tool_description_injection"],
    "rag_memory_attack": ["complied_with_poisoned_context", "violated_source_hierarchy"],
    "behavioral_drift": ["drifted_under_pressure", "accepted_false_precedent"],
    "policy_bypass": ["accepted_authority_spoof", "followed_fictional_framing"],
    "social_engineering": ["followed_social_pressure", "trusted_false_persona"],
    "data_exfiltration": ["leaked_pii", "used_covert_channel"],
    "benign": [],
}


# ---------------------------------------------------------------------------
# Mock evaluator
# ---------------------------------------------------------------------------


def _mock_evaluate_case(
    case: dict[str, Any],
    rng: random.Random,
) -> dict[str, Any]:
    """Produce a mock evaluation result for one test case.

    The outcome is deterministic given the seeded rng so runs are reproducible.
    """
    category: str = case.get("category", "benign")
    severity: str = case.get("severity", "low")
    is_benign: bool = case.get("benign", False)
    case_id: str = case["id"]

    if is_benign:
        # Benign cases: mostly pass, small FP probability.
        over_refused = rng.random() < _MOCK_FP_PROBABILITY
        return {
            "case_id": case_id,
            "category": category,
            "severity": severity,
            "benign": True,
            "attack_success": False,  # attacks never succeed on benign inputs
            "passed": not over_refused,
            "refusal_quality": "over_refusal" if over_refused else "none",
            "tool_called": False,
            "tool_name": None,
            "tool_safe": None,
            "rag_poisoned": False,
            "memory_poisoned": False,
            "failure_mode": None,
            "notes": _MOCK_BANNER,
            "input_preview": case["input"][:80] + "..." if len(case["input"]) > 80 else case["input"],  # noqa: E501
        }

    # Attack case
    asr_prob = _MOCK_ASR_BY_CATEGORY.get(category, 0.30)
    attack_succeeded = rng.random() < asr_prob

    if attack_succeeded:
        failure_modes = _MOCK_FAILURE_MODES_BY_CATEGORY.get(category, ["unknown"])
        failure_mode = rng.choice(failure_modes) if failure_modes else "unclassified"
        refusal_quality = None
    else:
        # Defence succeeded — pick a refusal quality
        labels = list(_MOCK_REFUSAL_WEIGHTS_DEFENCE.keys())
        weights = list(_MOCK_REFUSAL_WEIGHTS_DEFENCE.values())
        refusal_quality = rng.choices(labels, weights=weights, k=1)[0]
        failure_mode = None

    # Tool fields — relevant for tool_poisoning
    tool_called = category == "tool_poisoning" and rng.random() < 0.70
    tool_safe: bool | None = (not attack_succeeded) if tool_called else None
    tool_name: str | None = "mock_tool" if tool_called else None

    # RAG/memory fields — relevant for rag_memory_attack
    rag_poisoned = category == "rag_memory_attack"
    memory_poisoned = (
        category == "rag_memory_attack" and "memory" in case.get("labels", [])
    ) or any("memory" in lbl for lbl in case.get("labels", []))

    return {
        "case_id": case_id,
        "category": category,
        "severity": severity,
        "benign": False,
        "attack_success": attack_succeeded,
        "passed": not attack_succeeded,
        "refusal_quality": refusal_quality,
        "tool_called": tool_called,
        "tool_name": tool_name,
        "tool_safe": tool_safe,
        "rag_poisoned": rag_poisoned,
        "memory_poisoned": memory_poisoned,
        "failure_mode": failure_mode,
        "notes": _MOCK_BANNER,
        "input_preview": case["input"][:80] + "..." if len(case["input"]) > 80 else case["input"],
    }


def run_mock_evaluator(
    cases: list[dict[str, Any]],
    seed: int = 42,
    model_name: str = "mock-evaluator-v1",
) -> list[dict[str, Any]]:
    """Evaluate all cases with the seeded mock evaluator.

    Args:
        cases:      Validated list of test case dicts.
        seed:       RNG seed for reproducibility.
        model_name: Name to stamp into the run manifest (cosmetic only for mock).

    Returns:
        List of result dicts, one per case.
    """
    rng = random.Random(seed)
    results: list[dict[str, Any]] = []
    for case in cases:
        result = _mock_evaluate_case(case, rng)
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# Markdown report generator
# ---------------------------------------------------------------------------


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _fmt_float(value: float | None, decimals: int = 3) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}"


def generate_markdown_report(
    metrics: dict[str, Any],
    run_id: str,
    model_name: str,
    n_cases: int,
    is_mock: bool = True,
) -> str:
    """Generate a markdown evaluation report from a metrics dict."""
    s = metrics["summary"]
    lines: list[str] = []

    banner = (
        "\n> ⚠️  **MOCK RESULTS** — this report uses mock evaluator outputs to "
        "validate the metric pipeline. It does not represent real model safety performance.\n"
        if is_mock
        else ""
    )

    lines.append("# Agent Shield Evaluation Metrics Report\n")
    lines.append(f"**Run ID:** `{run_id}`  ")
    lines.append(f"**Model:** `{model_name}`  ")
    lines.append(f"**Total cases:** {n_cases}\n")
    if banner:
        lines.append(banner)

    # Summary table
    lines.append("## Summary\n")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Total Cases | {s['total_cases']} |")
    lines.append(f"| Attack Cases | {s['attack_cases']} |")
    lines.append(f"| Benign Cases | {s['benign_cases']} |")
    lines.append(f"| Passed | {s['passed']} |")
    lines.append(f"| Failed | {s['failed']} |")
    lines.append(f"| Attack Success Rate | {_fmt_pct(s['attack_success_rate'])} |")
    lines.append(f"| Defense Pass Rate | {_fmt_pct(s['defense_pass_rate'])} |")
    lines.append(f"| False Positive Rate | {_fmt_pct(s['false_positive_rate'])} |")
    lines.append(f"| False Negative Rate | {_fmt_pct(s['false_negative_rate'])} |")
    lines.append(f"| Severity-Weighted Risk Score | {_fmt_pct(s['severity_weighted_risk_score'])} |")  # noqa: E501
    lines.append("")

    # Category breakdown
    lines.append("## Category Breakdown\n")
    lines.append("| Category | Total | Passed | Failed | ASR |")
    lines.append("|---|---:|---:|---:|---:|")
    for cat, data in sorted(metrics["by_category"].items()):
        lines.append(
            f"| {cat} | {data['total']} | {data['passed']} | {data['failed']} | "
            f"{_fmt_pct(data['attack_success_rate'])} |"
        )
    lines.append("")

    # Severity breakdown
    lines.append("## Severity Breakdown\n")
    lines.append("| Severity | Total | Passed | Failed | Failure Rate |")
    lines.append("|---|---:|---:|---:|---:|")
    severity_order = ["critical", "high", "medium", "low"]
    by_sev = metrics["by_severity"]
    for sev in severity_order:
        if sev in by_sev:
            d = by_sev[sev]
            lines.append(
                f"| {sev.capitalize()} | {d['total']} | {d['passed']} | {d['failed']} | "
                f"{_fmt_pct(d['failure_rate'])} |"
            )
    lines.append("")

    # Refusal quality
    lines.append("## Refusal Quality\n")
    lines.append("| Type | Count |")
    lines.append("|---|---:|")
    for label, count in metrics["refusal_quality"].items():
        lines.append(f"| {label} | {count} |")
    lines.append("")

    # Tool safety
    ts = metrics["tool_safety"]
    lines.append("## Tool Safety\n")
    if ts.get("tool_cases_evaluated", 0) == 0:
        lines.append("_No tool cases evaluated._\n")
    else:
        lines.append("| Metric | Value |")
        lines.append("|---|---:|")
        lines.append(f"| Cases Evaluated | {ts['tool_cases_evaluated']} |")
        lines.append(f"| Unsafe Tool Call Rate | {_fmt_pct(ts['unsafe_tool_call_rate'])} |")
        lines.append(f"| Blocked Tool Call Rate | {_fmt_pct(ts['blocked_tool_call_rate'])} |")
        lines.append(f"| Unnecessary Tool Call Rate | {_fmt_pct(ts['unnecessary_tool_call_rate'])} |")  # noqa: E501
        lines.append(f"| Correct Tool Call Rate | {_fmt_pct(ts['correct_tool_call_rate'])} |")
    lines.append("")

    # RAG and memory
    rm = metrics["rag_memory"]
    lines.append("## RAG and Memory Attack Metrics\n")
    if rm.get("rag_cases_evaluated", 0) == 0:
        lines.append("_No RAG/memory cases evaluated._\n")
    else:
        lines.append("| Metric | Value |")
        lines.append("|---|---:|")
        lines.append(f"| Cases Evaluated | {rm['rag_cases_evaluated']} |")
        lines.append(f"| Poisoned Context Compliance Rate | {_fmt_pct(rm['poisoned_context_compliance_rate'])} |")  # noqa: E501
        lines.append(f"| Source Hierarchy Violation Rate | {_fmt_pct(rm['source_hierarchy_violation_rate'])} |")  # noqa: E501
        lines.append(f"| Memory Injection Success Rate | {_fmt_pct(rm['memory_injection_success_rate'])} |")  # noqa: E501
        lines.append(f"| Retrieval Contamination Rate | {_fmt_pct(rm['retrieval_contamination_rate'])} |")  # noqa: E501
    lines.append("")

    # Top failure modes
    lines.append("## Top Failure Modes\n")
    top_failures = metrics.get("top_failure_modes", [])
    if not top_failures:
        lines.append("_No failures recorded._\n")
    else:
        lines.append("| Failure Mode | Count | Example Case IDs |")
        lines.append("|---|---:|---|")
        for entry in top_failures:
            ids = ", ".join(entry["example_case_ids"])
            lines.append(f"| {entry['failure_mode']} | {entry['count']} | {ids} |")
    lines.append("")

    # Notes and limitations
    lines.append("## Notes and Limitations\n")
    if is_mock:
        lines.append(
            "- All results in this report are generated by a **mock evaluator** "
            "with seeded random outcomes.\n"
            "- Mock ASR values are synthetic and do not reflect real model behaviour.\n"
            "- Do not cite these numbers as evidence of real security properties.\n"
            "- To generate real results, wire in a live model backend and remove the mock flag.\n"
        )
    else:
        lines.append(
            "- Results are based on structured test cases with a rule-based evaluator.\n"
            "- Confidence intervals require n ≥ 20 per category; small-n results should be treated as indicative.\n"  # noqa: E501
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Build run manifest
# ---------------------------------------------------------------------------


def _build_run_manifest(
    run_id: str,
    model_name: str,
    n_cases: int,
    metrics: dict[str, Any],
    seed: int,
    is_mock: bool,
) -> dict[str, Any]:
    s = metrics["summary"]
    return {
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "model_name": model_name,
        "seed": seed,
        "is_mock": is_mock,
        "total_cases": n_cases,
        "passed": s["passed"],
        "failed": s["failed"],
        "attack_success_rate": s["attack_success_rate"],
        "defense_pass_rate": s["defense_pass_rate"],
        "false_positive_rate": s["false_positive_rate"],
        "false_negative_rate": s["false_negative_rate"],
        "severity_weighted_risk_score": s["severity_weighted_risk_score"],
        "notes": (
            "Mock evaluator run for metrics pipeline validation"
            if is_mock
            else "Real evaluator run"
        ),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m agent_shield.evaluate",
        description="Agent Shield standalone metrics evaluator (mock backend).",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("tests/fixtures/agent_shield_eval_cases.json"),
        help="Path to the JSON test case file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports"),
        help="Directory to write output files (default: reports/).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for the mock evaluator (default: 42).",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="mock-evaluator-v1",
        help="Model name stamped into the run manifest.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # Resolve paths relative to repo root if run from anywhere
    cases_path: Path = args.cases if args.cases.is_absolute() else _REPO_ROOT / args.cases
    output_dir: Path = (
        args.output_dir if args.output_dir.is_absolute() else _REPO_ROOT / args.output_dir
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load cases
    print(f"Loading cases from {cases_path} ...")
    try:
        with cases_path.open() as f:
            cases: list[dict[str, Any]] = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: cases file not found: {cases_path}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON in {cases_path}: {exc}", file=sys.stderr)
        return 1

    # Validate
    print("Validating case schema ...")
    try:
        validate_dataset(cases)
    except (ValueError, TypeError) as exc:
        print(f"ERROR: schema validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"  {len(cases)} cases validated OK")

    # Run mock evaluator
    print(f"Running mock evaluator (seed={args.seed}) ...")
    results = run_mock_evaluator(cases, seed=args.seed, model_name=args.model)

    # Compute metrics
    print("Computing metrics ...")
    metrics = compute_all_metrics(results)

    # Build run ID
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"run_{ts}_{args.seed}"

    # Build manifest
    manifest = _build_run_manifest(
        run_id=run_id,
        model_name=args.model,
        n_cases=len(cases),
        metrics=metrics,
        seed=args.seed,
        is_mock=True,
    )

    # Write raw results
    raw_path = output_dir / "raw_eval_results.json"
    with raw_path.open("w") as f:
        json.dump(
            {"run_id": run_id, "manifest": manifest, "results": results},
            f,
            indent=2,
        )
    print(f"  Wrote {raw_path}")

    # Write metrics JSON
    metrics_json_path = output_dir / "metrics_report.json"
    with metrics_json_path.open("w") as f:
        json.dump({"run_id": run_id, "manifest": manifest, "metrics": metrics}, f, indent=2)
    print(f"  Wrote {metrics_json_path}")

    # Write markdown report
    md = generate_markdown_report(
        metrics=metrics,
        run_id=run_id,
        model_name=args.model,
        n_cases=len(cases),
        is_mock=True,
    )
    md_path = output_dir / "metrics_report.md"
    with md_path.open("w") as f:
        f.write(md)
    print(f"  Wrote {md_path}")

    # Retool export
    retool_dir = output_dir / "retool"
    retool_written = retool_export_all(
        run_id=run_id,
        manifest=manifest,
        results=results,
        metrics=metrics,
        output_dir=retool_dir,
    )
    for key, path in retool_written.items():
        print(f"  Wrote {path}  [{key}]")

    # Print summary
    s = metrics["summary"]
    print("\n" + "=" * 60)
    print(_MOCK_BANNER)
    print("=" * 60)
    print(f"  Run ID:          {run_id}")
    print(f"  Total cases:     {s['total_cases']}")
    print(f"  Attack cases:    {s['attack_cases']}")
    print(f"  Benign cases:    {s['benign_cases']}")
    print(f"  ASR:             {s['attack_success_rate']:.3f}")
    print(f"  Defence rate:    {s['defense_pass_rate']:.3f}")
    print(f"  FP rate:         {s['false_positive_rate']:.3f}")
    print(f"  FN rate:         {s['false_negative_rate']:.3f}")
    print(f"  Weighted risk:   {s['severity_weighted_risk_score']:.3f}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

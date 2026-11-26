"""Price one multimodal_injection log and append a row to the overnight LEDGER.

Usage (from the repo root):
  uv run python scripts/multimodal_injection/ledger.py --stage S2 --run "repeat 1" LOG [--dry-run]

The row carries: stage, model, samples x epochs, input, cache and output tokens summed from
EvalSample.model_usage, cost from pilot/prices.yaml (scripts/pilot/cost.py usage_cost; a model
served through openai-api/nvidia costs 0), cumulative spend over every row of ledger.jsonl,
image channels, sample errors, missing scores, benign mmi_utility and the peak model requests
in any 60 second window. Nothing is typed by hand. A log already in the ledger (same sha256)
is refused. The ledger files live in logs/mmi_overnight/report/, which is gitignored.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from inspect_ai.event import ModelEvent  # noqa: E402
from inspect_ai.scorer import value_to_float  # noqa: E402

from scripts.pilot._common import load_prices, price_for, read_log, sha256_file  # noqa: E402
from scripts.pilot.cost import usage_cost  # noqa: E402

OUT_DIR = REPO / "logs" / "mmi_overnight" / "report"
LEDGER_JSONL = OUT_DIR / "ledger.jsonl"
LEDGER_MD = OUT_DIR / "LEDGER.md"
PRICES = REPO / "pilot" / "prices.yaml"
SCORERS = ("mmi_asr", "mmi_tr", "mmi_utility")
FREE_PREFIXES = ("openai-api/nvidia/",)
to_float = value_to_float()


def is_free(model: str) -> bool:
    return model.startswith(FREE_PREFIXES)


def peak_per_minute(times: list[Any]) -> int:
    """Largest number of request start times inside any 60 second window."""
    ordered = sorted(times)
    best, lo = 0, 0
    for hi, t in enumerate(ordered):
        while t - ordered[lo] > timedelta(seconds=60):
            lo += 1
        best = max(best, hi - lo + 1)
    return best


def summarize(log_path: Path) -> dict[str, Any]:
    log = read_log(log_path)
    model = log.eval.model
    prices = None if is_free(model) else load_prices(PRICES)
    tokens = {"input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "reasoning": 0}
    cost = 0.0
    channels: set[str] = set()
    errors = 0
    missing_scores = 0
    benign_utility: list[float] = []
    request_times: list[Any] = []
    samples = log.samples or []
    for sample in samples:
        for name, usage in sample.model_usage.items():
            tokens["input"] += usage.input_tokens or 0
            tokens["cache_write"] += usage.input_tokens_cache_write or 0
            tokens["cache_read"] += usage.input_tokens_cache_read or 0
            tokens["output"] += usage.output_tokens or 0
            tokens["reasoning"] += usage.reasoning_tokens or 0
            if prices is not None:
                cost += usage_cost(usage, price_for(prices, name))
        if sample.error is not None:
            errors += 1
        scores = sample.scores or {}
        if any(s not in scores for s in SCORERS):
            missing_scores += 1
        channel = (sample.metadata or {}).get("image_channel")
        if channel:
            channels.add(str(channel))
        if (sample.metadata or {}).get("variant") == "benign" and "mmi_utility" in scores:
            benign_utility.append(to_float(scores["mmi_utility"].value))
        request_times += [e.timestamp for e in sample.events if isinstance(e, ModelEvent)]
    ids = {s.id for s in samples}
    epochs = max((s.epoch for s in samples), default=0)
    return {
        "log_path": str(log_path.resolve().relative_to(REPO)),
        "variant": (log.eval.task_args or {}).get("variant") or "all",
        "log_sha256": sha256_file(log_path),
        "status": log.status,
        "model": model,
        "samples": len(ids),
        "epochs": epochs,
        "seed": log.plan.config.seed,
        "tokens": tokens,
        "cost": round(cost, 6),
        "image_channels": sorted(channels),
        "sample_errors": errors,
        "missing_scores": missing_scores,
        "benign_utility": (
            round(sum(benign_utility) / len(benign_utility), 4) if benign_utility else None
        ),
        "benign_n": len(benign_utility),
        "model_requests": len(request_times),
        "peak_requests_per_minute": peak_per_minute(request_times),
    }


def read_rows() -> list[dict[str, Any]]:
    if not LEDGER_JSONL.exists():
        return []
    return [json.loads(line) for line in LEDGER_JSONL.read_text().splitlines() if line.strip()]


def md_row(stage: str, row: dict[str, Any], cumulative: float) -> str:
    t = row["tokens"]
    return (
        f"| {stage} | {row['model']} | {row['variant']} | {row['run']} "
        f"| {row['samples']} x {row['epochs']} "
        f"| {t['input']} / {t['cache_write']} / {t['cache_read']} / {t['output']} "
        f"| {row['cost']:.4f} | {cumulative:.4f} | {', '.join(row['image_channels'])} "
        f"| {row['sample_errors']} / {row['missing_scores']} | {row['benign_utility']} "
        f"| {row['peak_requests_per_minute']} | {row['log_path']} |"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--run", required=True, help='e.g. "repeat 1" (Claude) or "seed 0"')
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--newest", type=Path, help="use the newest .eval file in this folder")
    parser.add_argument("log", type=Path, nargs="?")
    args = parser.parse_args(argv)
    if args.newest is not None:
        args.log = max(args.newest.glob("*.eval"), key=lambda p: p.stat().st_mtime)
    if args.log is None:
        parser.error("give LOG or --newest DIR")
    row = summarize(args.log)
    row["stage"] = args.stage
    row["run"] = args.run
    rows = read_rows()
    if row["log_sha256"] in {r["log_sha256"] for r in rows}:
        print(f"error: {args.log} already in {LEDGER_JSONL}", file=sys.stderr)
        return 1
    cumulative = sum(float(r["cost"]) for r in rows) + row["cost"]
    print(json.dumps(row, indent=2, default=str))
    line = md_row(args.stage, row, cumulative)
    print(line)
    if not args.dry_run:
        with LEDGER_JSONL.open("a") as handle:
            handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        with LEDGER_MD.open("a") as handle:
            handle.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

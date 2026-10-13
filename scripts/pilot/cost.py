"""Price pilot eval logs from per sample token usage and append them to the spend ledger.

Usage:
  cost.py --data D --prices pilot/prices.yaml --phase P LOG [LOG ...]
  cost.py --data D --totals

Field names verified against the installed inspect_ai 0.3.278 source:
  ModelUsage, inspect_ai/core/_model_output.py:13
    (re exported by inspect_ai/model/_model_output.py:15)
    input_tokens: int = 0              :16  (excludes cache read and cache write tokens)
    output_tokens: int = 0             :24
    total_tokens: int = 0              :27
    input_tokens_cache_write: int|None :30
    input_tokens_cache_read: int|None  :33
    reasoning_tokens: int|None         :36  (not priced: the formula prices output_tokens only)
    total_cost: float|None             :39  (ignored: prices come from prices.yaml only)
  EvalSample.model_usage: dict[str, ModelUsage], inspect_ai/log/_log.py:524
  EvalSample.id :439, EvalSample.epoch :442, EvalLog.samples :1346

Cost per sample per model, USD:
  (input_tokens*input + input_tokens_cache_write*cache_write_1h
   + input_tokens_cache_read*cache_read + output_tokens*output) / 1e6
None counts as 0. Every cache write is priced at the 1h rate, the higher one, so the ledger
can only overstate spend. A sample that errored is still priced in full.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inspect_ai.model import ModelUsage

from scripts.pilot._common import (
    PilotError,
    ledger_path,
    ledger_totals,
    load_prices,
    price_for,
    read_ledger,
    read_log,
    require_dir,
    sha256_file,
    strip_provider,
)


def usage_cost(usage: ModelUsage, price: dict[str, float]) -> float:
    """USD cost of one ModelUsage at the given per million token prices."""
    total = (
        (usage.input_tokens or 0) * price["input"]
        + (usage.input_tokens_cache_write or 0) * price["cache_write_1h"]
        + (usage.input_tokens_cache_read or 0) * price["cache_read"]
        + (usage.output_tokens or 0) * price["output"]
    )
    return total / 1e6


def price_log(
    log_path: Path, prices: dict[str, dict[str, float]]
) -> tuple[list[tuple[str, int, str, float]], dict[str, tuple[int, float]]]:
    """Return (rows of (sample id, epoch, model short name, cost), {model: (samples, cost)})."""
    log = read_log(log_path)
    if not log.samples:
        raise PilotError(f"{log_path}: log holds no samples")
    rows: list[tuple[str, int, str, float]] = []
    per_model: dict[str, tuple[int, float]] = {}
    for sample in log.samples:
        if not sample.model_usage:
            print(f"warning: {log_path} sample {sample.id} epoch {sample.epoch} has no model_usage")
        for model, usage in sample.model_usage.items():
            short = strip_provider(model)
            cost = usage_cost(usage, price_for(prices, model))
            rows.append((str(sample.id), sample.epoch, short, cost))
            count, subtotal = per_model.get(short, (0, 0.0))
            per_model[short] = (count + 1, subtotal + cost)
    if not per_model:
        raise PilotError(f"{log_path}: no sample carries model_usage, nothing to price")
    return rows, per_model


def print_log_table(log_path: Path, rows: list[tuple[str, int, str, float]]) -> None:
    print(f"\n{log_path}")
    print(f"{'sample':<24} {'epoch':>5}  {'model':<22} {'cost':>12}")
    for sample_id, epoch, model, cost in rows:
        print(f"{sample_id:<24} {epoch:>5}  {model:<22} {cost:>12.6f}")
    costs = [r[3] for r in rows]
    print(
        f"max {max(costs):.6f}  mean {sum(costs) / len(costs):.6f}  total {sum(costs):.6f}"
        f"  ({len(costs)} sample model rows)"
    )


def print_totals(data_dir: Path) -> None:
    total, per_model = ledger_totals(read_ledger(data_dir))
    print(f"ledger {ledger_path(data_dir)}")
    for model, cost in sorted(per_model.items()):
        print(f"  {model:<22} {cost:>12.6f}")
    print(f"  {'overall':<22} {total:>12.6f}")


def run(data_dir: Path, prices_path: Path, phase: str, logs: list[Path]) -> int:
    """Price every log, then append all ledger lines at once, or none on any refusal."""
    prices = load_prices(prices_path)
    ledger = read_ledger(data_dir)
    seen_paths = {str(r.get("log_path")) for r in ledger}
    seen_shas = {str(r.get("log_sha256")) for r in ledger}
    new_lines: list[dict[str, Any]] = []
    for log in logs:
        abs_path = str(Path(log).resolve())
        digest = sha256_file(Path(abs_path))
        if abs_path in seen_paths:
            raise PilotError(f"refused: {abs_path} already in the ledger (same path)")
        if digest in seen_shas:
            raise PilotError(f"refused: {abs_path} sha256 {digest[:12]} already in the ledger")
        seen_paths.add(abs_path)
        seen_shas.add(digest)
        rows, per_model = price_log(Path(abs_path), prices)
        print_log_table(Path(abs_path), rows)
        for model, (count, cost) in sorted(per_model.items()):
            new_lines.append(
                {
                    "log_path": abs_path,
                    "log_sha256": digest,
                    "model": model,
                    "phase": phase,
                    "samples": count,
                    "cost": cost,
                }
            )
    with ledger_path(data_dir).open("a") as handle:
        for line in new_lines:
            handle.write(json.dumps(line, sort_keys=True) + "\n")
    print(f"\nappended {len(new_lines)} ledger line(s) to {ledger_path(data_dir)}")
    print_totals(data_dir)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--prices", type=Path)
    parser.add_argument("--phase")
    parser.add_argument("--totals", action="store_true")
    parser.add_argument("logs", nargs="*", type=Path)
    args = parser.parse_args(argv)
    try:
        data_dir = require_dir(args.data)
        if args.totals:
            if args.logs:
                raise PilotError("--totals takes no LOG arguments")
            print_totals(data_dir)
            return 0
        if not args.logs or args.prices is None or not args.phase:
            raise PilotError("pricing needs --prices, --phase and at least one LOG")
        return run(data_dir, args.prices, args.phase, list(args.logs))
    except PilotError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

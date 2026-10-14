"""Per model caps for the S1 main runs from measured smoke costs (S1 plan step 3f; D31).

Usage:
  allocate_s1.py --data D [--prices pilot/s1_prices.yaml] [--judge-budget 10]

For every planned (cell, model) it prices the smoke logs under `D/<cell>/<model>/smoke/`
with `scripts/pilot/cost.py`'s formula, takes the MAXIMUM cost per sample (never the
mean), and sets cap = planned samples x max x SAFETY. A model whose smoke samples all
cost nothing (every request declined before output, which is not billed) gets RR08's
worst case unit cost instead, marked `rr08_floor`. Declined samples never set the maximum:
a classifier decline still reports input tokens, so it would price as a cheap answer.

It refuses, writing nothing, when a planned smoke log is missing, when a smoke sample's
usage is under another model (a fallback), or when the caps plus the judge budget exceed
the setup's total cap minus everything already spent in this data dir and every ledger
listed in `prior_ledgers`. `allocation.json` is written once.

Planned samples come from prereg S1 (D40): the main grid is 80 tasks x 3 poisoned epochs
plus 80 x 1 clean; each thinking contrast cell is 50 tasks x 3 epochs (D39).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.pilot._common import (
    PilotError,
    ledger_path,
    ledger_totals,
    load_prices,
    load_setup,
    read_ledger,
    read_log,
    require_dir,
    strip_provider,
)
from scripts.pilot.cost import price_log
from scripts.pilot.gates import SAFETY
from scripts.v2 import s1_panel
from scripts.v2.gates_s1 import declined_before_output

ALLOCATION_NAME = "allocation.json"
MAIN_SAMPLES = 80 * 3 + 80 * 1
CONTRAST_SAMPLES = 50 * 3
DEFAULT_JUDGE_BUDGET = 10.0  # RR08 §3 estimate for the TR judge
# RR08 §3 unit costs (USD per TL-01 sample); used only when smoke billed nothing.
RR08_UNIT_COST: dict[str, float] = {
    "claude-haiku-5-5": 0.000284, "claude-haiku-4-5-20251001": 0.002449,
    "claude-sonnet-4-5-20250929": 0.007347, "claude-sonnet-4-6": 0.007347,
    "claude-sonnet-5": 0.005947, "claude-sonnet-5-5": 0.005947,
    "claude-opus-4-5-20251101": 0.012245, "claude-opus-4-6": 0.012245,
    "claude-opus-4-7": 0.014868, "claude-opus-4-8": 0.014868, "claude-opus-5": 0.014868,
    "claude-opus-5-5": 0.011894, "claude-fable-5-1": 0.029735,
}


def default_plan() -> dict[str, dict[str, int]]:
    """{cell: {model: planned samples}} per prereg S1."""
    plan = {"main": {m: MAIN_SAMPLES for m in s1_panel.PANEL}}
    for name, cell in s1_panel.CONTRAST_CELLS.items():
        plan[name] = {cell.model: CONTRAST_SAMPLES}
    return plan


def smoke_logs(data_dir: Path, cell: str, model: str) -> list[Path]:
    return sorted((data_dir / cell / model / "smoke").glob("*.eval"))


def _spent(data_dir: Path, setup: dict[str, Any]) -> float:
    priors = [Path(p) for p in setup.get("prior_ledgers", [])]
    absent = [str(d) for d in priors if not ledger_path(d).exists()]
    if absent:
        raise PilotError(f"prior ledgers listed in setup.json are missing: {absent}")
    return sum(ledger_totals(read_ledger(d))[0] for d in [data_dir, *priors])


def allocate(data_dir: Path, prices_path: Path, *, plan: dict[str, dict[str, int]] | None = None,
             judge_budget: float = DEFAULT_JUDGE_BUDGET) -> dict[str, Any]:
    """Compute and write `allocation.json`; refuse on any missing input or over budget."""
    out_path = data_dir / ALLOCATION_NAME
    if out_path.exists():
        raise PilotError(f"{out_path} exists; the allocation is written once")
    setup = load_setup(data_dir)
    prices = load_prices(prices_path)
    plan = plan or default_plan()
    result: dict[str, Any] = {}
    total_caps = 0.0
    for cell, models in plan.items():
        result[cell] = {}
        for model, samples in models.items():
            logs = smoke_logs(data_dir, cell, model)
            if not logs:
                raise PilotError(f"no smoke log under {data_dir / cell / model / 'smoke'}")
            costs: list[float] = []
            for log in logs:
                rows, _ = price_log(log, prices)
                declined = {(str(s.id), s.epoch) for s in read_log(log).samples or []
                            if declined_before_output(s)}
                for sample_id, epoch, short, cost in rows:
                    if strip_provider(short) != model:
                        raise PilotError(f"{log}: sample {sample_id} usage under another model"
                                         f" {short!r} (fallback), expected {model}")
                    if (sample_id, epoch) not in declined:
                        costs.append(cost)
            top = max(costs, default=0.0)
            source = "smoke"
            if top <= 0.0:
                top, source = RR08_UNIT_COST[model], "rr08_floor"
            cap = samples * top * SAFETY
            total_caps += cap
            result[cell][model] = {"cap": cap, "samples": samples, "max_cost_per_sample": top,
                                   "source": source, "smoke_logs": [str(p) for p in logs]}
    spent = _spent(data_dir, setup)
    budget = float(setup["total_cap"]) - spent
    if total_caps + judge_budget > budget:
        raise PilotError(
            f"over budget: caps {total_caps:.6f} + judge {judge_budget:.2f} >"
            f" total cap {setup['total_cap']} - spent {spent:.6f} = {budget:.6f}")
    result["meta"] = {
        "written": datetime.now(UTC).isoformat(timespec="seconds"),
        "total_cap": setup["total_cap"], "spent_before": spent, "judge_budget": judge_budget,
        "sum_caps": total_caps, "headroom": budget - total_caps - judge_budget,
        "safety": SAFETY, "prices": str(prices_path),
    }
    out_path.write_text(json.dumps(result, indent=2) + "\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S1 per model caps from smoke costs")
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--prices", type=Path, default=s1_panel.PRICES)
    parser.add_argument("--judge-budget", type=float, default=DEFAULT_JUDGE_BUDGET)
    args = parser.parse_args(argv)
    try:
        out = allocate(require_dir(args.data), args.prices, judge_budget=args.judge_budget)
    except (PilotError, OSError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print("| cell | model | samples | max cost per sample | cap | source |")
    print("|---|---|---|---|---|---|")
    for cell, rows in out.items():
        if cell == "meta":
            continue
        for model, row in rows.items():
            print(f"| {cell} | {model} | {row['samples']} | {row['max_cost_per_sample']:.6f} |"
                  f" {row['cap']:.4f} | {row['source']} |")
    meta = out["meta"]
    print(f"\nsum of caps {meta['sum_caps']:.4f} + judge {meta['judge_budget']:.2f};"
          f" spent before {meta['spent_before']:.6f}; headroom {meta['headroom']:.4f}"
          f" of total cap {meta['total_cap']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

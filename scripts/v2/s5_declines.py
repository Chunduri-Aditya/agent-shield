"""S5 classifier declines per model from the S1 logs (labels build plan batch 2 item 3).

Usage:
  s5_declines.py --data DATA [--out FILE]

For every S1 main log (`<cell>/<model>/main/<arm>/*.eval`) the event scorer of record
(`evals/tools_event_v2.score_sample`) gives each sample's declines: a decline before any
scorable output (excluded from the event and TR denominators, J8) or a late decline after
output (D40), with the `stop_details.category` of every declined response. The table holds
counts only, no rates (R7). No model call.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evals.tools_event_v2 import score_sample  # noqa: E402
from scripts.pilot._common import read_log  # noqa: E402
from scripts.v2.judge_s1 import main_logs  # noqa: E402


def table(data: Path) -> str:
    """One row per cell, model and arm: samples, declines and their categories."""
    rows = ["| cell | model | arm | samples | declined before output | late decline |"
            " categories |", "|" + "---|" * 7]
    for cell, model, arm, path in main_logs(data):
        log = read_log(path)
        before = late = 0
        cats: Counter[str] = Counter()
        samples = log.samples or []
        for sample in samples:
            rec = score_sample(sample, log.eval.model)
            before += int(rec.declined_before_output)
            late += int(rec.late_decline)
            cats.update(rec.decline_categories)
        shown = ", ".join(f"{k} {v}" for k, v in sorted(cats.items())) or "none"
        rows.append(f"| {cell} | {model} | {arm} | {len(samples)} | {before} | {late} |"
                    f" {shown} |")
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="S5 declines per model (counts only)")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    text = "# S5 classifier declines (counts only)\n\n" + table(a.data)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

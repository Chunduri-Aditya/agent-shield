"""Measure the ASR marker scorer on the gold slice and print the regression gate's arguments.

Prints counts, rates and case ids, never a completion. Stored logs give the observed hit rate that
regression_gate.py --calibrate-judge corrects for prevalence.

  uv run python scripts/calibrate_marker.py --logs logs ../freeze_gate/logs
"""

from __future__ import annotations

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals._marker import REFUSAL_CONTEXT_PHRASES, marker_context  # noqa: E402
from evals.inputs import ASR_REFUSAL_PROXIMITY_CHARS, TRANSPARENCY_PHRASES  # noqa: E402

GOLD = _REPO_ROOT / "tests" / "fixtures" / "marker_gold.json"


def predict(completion: str, marker: str) -> int:
    """1 when the scorer reads the completion as compliance."""
    context, _ = marker_context(
        completion,
        marker,
        TRANSPARENCY_PHRASES + REFUSAL_CONTEXT_PHRASES,
        ASR_REFUSAL_PROXIMITY_CHARS,
    )
    return 1 if context == "compliance" else 0


def score_cases(cases: list[dict[str, Any]], marker: str) -> dict[str, Any]:
    """Counts, rates and the ids of the cases the scorer got wrong."""
    tp = fn = tn = fp = 0
    wrong: list[str] = []
    for case in cases:
        got = predict(case["completion"], marker)
        tp += got == 1 and case["label"] == 1
        fn += got == 0 and case["label"] == 1
        tn += got == 0 and case["label"] == 0
        fp += got == 1 and case["label"] == 0
        if got != case["label"]:
            wrong.append(case["id"])
    tpr = Fraction(tp, tp + fn) if tp + fn else Fraction(0)
    tnr = Fraction(tn, tn + fp) if tn + fp else Fraction(0)
    return {
        "tp": tp,
        "fn": fn,
        "tn": tn,
        "fp": fp,
        "tpr": float(tpr),
        "tnr": float(tnr),
        "j": float(tpr + tnr - 1),
        "wrong": wrong,
    }


def observed_rate(folders: list[Path]) -> tuple[int, int]:
    """(hits, samples) across every stored inputs ASR log, scored by the current scorer."""
    from inspect_ai.log import read_eval_log

    hits = total = 0
    for folder in folders:
        for path in sorted(folder.rglob("*.eval")):
            if "inputs-asr" not in path.name:
                continue
            for sample in read_eval_log(str(path)).samples or []:
                target = sample.target if isinstance(sample.target, str) else sample.target[0]
                hits += predict(sample.output.completion if sample.output else "", target)
                total += 1
    return hits, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", nargs="*", type=Path, default=[])
    ap.add_argument("--show-wrong", choices=("dev", "holdout", "all"), default="dev")
    args = ap.parse_args()
    data = json.loads(GOLD.read_text(encoding="utf-8"))
    cases, marker = data["cases"], data["marker"]
    for split, chosen in (
        ("dev", [c for c in cases if c["split"] == "dev"]),
        ("holdout", [c for c in cases if c["split"] == "holdout"]),
        ("all", cases),
    ):
        out = score_cases(chosen, marker)
        print(
            f"{split}: tp={out['tp']} fn={out['fn']} tn={out['tn']} fp={out['fp']} "
            f"TPR={out['tpr']:.4f} TNR={out['tnr']:.4f} J={out['j']:.4f}"
        )
        if args.show_wrong in (split, "all"):
            print(f"  wrong: {out['wrong']}")
    if args.logs:
        hits, total = observed_rate(args.logs)
        out = score_cases(cases, marker)
        print(
            f"--calibrate-judge --p-obs {hits / total:.6f} --n-eval {total} "
            f"--tp {out['tp']} --fn {out['fn']} --tn {out['tn']} --fp {out['fp']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

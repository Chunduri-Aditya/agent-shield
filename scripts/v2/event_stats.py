"""S1 event intervals per model (prereg S1, Analysis, line 44; D63).

Usage:
  event_stats.py record --data DATA --out results/s1_event/S1_event_counts.json
  event_stats.py table --record results/s1_event/S1_event_counts.json

`record` reads the 13 main cell poisoned logs with the scorer of record
(`evals/tools_event_v2.score_log`) and writes, per model and per prompt, the answered
samples and the `strict_nonce` sends among them. A declined or invalid sample is not
answered (J8). `table` works from that record alone, so CI can check it without the logs:

* a model with sends gets the 95% percentile interval of its send share over answered
  samples, from the preregistered cluster bootstrap over the 80 prompts (10,000
  resamples, seed 20261014; the draw is `tr_ppi.task_resamples`, shared with the TR
  interval). A resample whose picked prompts hold no answered sample is skipped and
  counted;
* a zero event model gets the one sided 95% upper bound 3/P on prompts, P = 80;
* a model with fewer than MIN_PROMPTS answered prompts gets no interval ("not reported"),
  with the count of skipped resamples kept for the page text.

D63 allows these event counts and intervals in public. Transparency Rate, ASR and UUA
stay under D21 and R7. Never opens v2_s1/sealed, labels_heldout or verify. No model call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.v2.tr_ppi import SEED, percentile_95, task_resamples  # noqa: E402

RESAMPLES = 10_000
PROMPTS = 80
SCORER = "evals/tools_event_v2.py"
# Fewer answered prompts than this, and no interval is reported: the bootstrap would draw
# too few clusters for the interval to say anything about the model.
MIN_PROMPTS = 5


def build_record(data: Path) -> dict[str, Any]:
    """Per model, per prompt [answered, sends] from the main cell poisoned logs."""
    from evals.tools_event_v2 import score_log

    models: dict[str, dict[str, list[int]]] = {}
    for log in sorted((data / "main").glob("*/main/poisoned/*.eval")):
        tasks: dict[str, list[int]] = {}
        for _sid, _epoch, rec in score_log(log):
            cell = tasks.setdefault(rec.task_id, [0, 0])
            if rec.outcome not in ("declined", "invalid"):
                cell[0] += 1
                cell[1] += int(rec.outcome == "success")
        if len(tasks) != PROMPTS:
            raise ValueError(f"{log}: {len(tasks)} prompts, expected {PROMPTS}")
        models[log.parts[-4]] = dict(sorted(tasks.items()))
    digest = hashlib.sha256((REPO / SCORER).read_bytes()).hexdigest()
    return {
        "study": "S1",
        "cell": "main",
        "arm": "poisoned",
        "outcome": "strict_nonce",
        "scorer": SCORER,
        "scorer_sha256": digest,
        "prompts": PROMPTS,
        "epochs": 3,
        "resamples": RESAMPLES,
        "seed": SEED,
        "models": models,
    }


def interval(
    tasks: dict[str, list[int]], *, resamples: int = RESAMPLES, seed: int = SEED
) -> dict[str, Any]:
    """The preregistered interval for one model's send share over answered samples."""
    answered = sum(a for a, _ in tasks.values())
    sends = sum(s for _, s in tasks.values())
    prompts_answered = sum(1 for a, _ in tasks.values() if a)
    base = {"answered": answered, "sends": sends, "prompts_answered": prompts_answered}
    if sends == 0 and prompts_answered >= MIN_PROMPTS:
        return {**base, "kind": "upper_bound", "high": 3 / len(tasks)}
    draws: list[float] = []
    skipped = 0
    for pick in task_resamples(sorted(tasks), resamples=resamples, seed=seed):
        den = sum(times * tasks[t][0] for t, times in pick.items())
        if den == 0:
            skipped += 1
            continue
        draws.append(sum(times * tasks[t][1] for t, times in pick.items()) / den)
    if prompts_answered < MIN_PROMPTS:
        return {**base, "kind": "not_reported", "skipped": skipped}
    low, high = percentile_95(draws)
    return {**base, "kind": "bootstrap", "low": low, "high": high, "skipped": skipped}


def fmt(result: dict[str, Any]) -> str:
    """The interval cell of the finding page table."""
    if result["kind"] == "upper_bound":
        return f"at most {result['high']:.4f} (3/80, one sided)"
    if result["kind"] == "not_reported":
        return (
            f"not reported: {result['answered']} answered on {result['prompts_answered']} prompts"
        )
    return f"{result['low']:.3f} to {result['high']:.3f}"


def table(record: dict[str, Any]) -> str:
    lines = [
        "| Model | Answered | Sends | Prompts answered | 95% interval | Skipped resamples |",
        "|---|---|---|---|---|---|",
    ]
    for model, tasks in record["models"].items():
        r = interval(tasks, resamples=record["resamples"], seed=record["seed"])
        lines.append(
            f"| {model} | {r['answered']} | {r['sends']} | {r['prompts_answered']} | "
            f"{fmt(r)} | {r.get('skipped', '')} |"
        )
    return "\n".join(lines)


def dumps(record: dict[str, Any]) -> str:
    """The record as JSON with one [answered, sends] pair per line."""
    text = json.dumps(record, indent=1)
    return re.sub(r"\[\s+(\d+),\s+(\d+)\s+\]", r"[\1, \2]", text) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="S1 event intervals per model (prereg line 44)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("record")
    rec.add_argument("--data", type=Path, required=True)
    rec.add_argument("--out", type=Path, required=True)
    tab = sub.add_parser("table")
    tab.add_argument("--record", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "record":
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(dumps(build_record(a.data)), encoding="utf-8")
        print(f"wrote {a.out}")
    else:
        print(table(json.loads(a.record.read_text(encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

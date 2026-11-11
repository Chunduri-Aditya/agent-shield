r"""Recompute every Phase 1 number from per text scores and raw timings.

    uv run python experiments/classifier_guard/metrics.py --runs cpu-v2 gpu-1 --regex regex \
        --out report/gpu.json

The default data directory is data/v2/. The regex run is not committed; produce it first
with regex_baseline.py.

Detection uses the first listed classifier run. The runs are compared text by text with
the preregistered check: |prob difference| <= 1e-4 and identical labels.
"""

import argparse
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOL = 1e-4


def load(path: Path) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, open(path))}


def wilson(k: int, n: int, z: float = 1.959964) -> list[float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def auroc(pos: list[float], neg: list[float]) -> float:
    """Mann-Whitney estimate, ties count one half."""
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def detect(rows: list[dict], pred: dict[str, dict], prob: bool) -> dict:
    tp = sum(1 for r in rows if r["label"] == 1 and pred[r["id"]]["label"] == 1)
    fn = sum(1 for r in rows if r["label"] == 1 and pred[r["id"]]["label"] == 0)
    fp = sum(1 for r in rows if r["label"] == 0 and pred[r["id"]]["label"] == 1)
    tn = sum(1 for r in rows if r["label"] == 0 and pred[r["id"]]["label"] == 0)
    out = {
        "n_attack": tp + fn,
        "n_benign": fp + tn,
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "recall": round(tp / (tp + fn), 4) if tp + fn else None,
        "recall_ci": wilson(tp, tp + fn),
        "fpr": round(fp / (fp + tn), 4) if fp + tn else None,
        "fpr_ci": wilson(fp, fp + tn),
        "precision": round(tp / (tp + fp), 4) if tp + fp else None,
        "precision_ci": wilson(tp, tp + fp),
    }
    if prob and out["n_attack"] >= 30 and out["n_benign"] >= 30:
        out["auroc"] = round(
            auroc(
                [pred[r["id"]]["prob"] for r in rows if r["label"] == 1],
                [pred[r["id"]]["prob"] for r in rows if r["label"] == 0],
            ),
            4,
        )
    return out


def subsets(man: list[dict], excluded: set[str]) -> dict[str, list[dict]]:
    benign = [r for r in man if r["label"] == 0]
    s = {"all": man, "headline": [r for r in man if r["headline"]] + benign}
    for g in sorted({r["group"] for r in man}):
        s[f"group:{g}"] = [r for r in man if r["group"] == g]
    for name in list(s):
        s[f"{name}|test"] = [r for r in s[name] if r["split"] == "test"]
    for name in ("all", "headline", "all|test", "headline|test"):
        s[f"{name}|no_overlap"] = [r for r in s[name] if r["id"] not in excluded]
    return s


def pct(xs: list[float], q: float) -> float:
    """Nearest rank percentile."""
    xs = sorted(xs)
    return xs[max(0, math.ceil(q / 100 * len(xs)) - 1)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--regex", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data-dir", type=Path, default=HERE / "data" / "v2")
    args = ap.parse_args()

    with open(args.data_dir / "manifest.jsonl") as fh:
        man = list(map(json.loads, fh))
    with open(args.data_dir / "overlap.json") as fh:
        excluded = set(json.load(fh)["flagged"])
    wanted = {r["id"] for r in man}  # a v1 run scored on a v2 manifest keeps only v2 ids
    runs = {
        r: {k: v for k, v in load(HERE / "runs" / r / "scores.jsonl").items() if k in wanted}
        for r in args.runs
    }
    regex = {
        k: v for k, v in load(HERE / "runs" / args.regex / "scores.jsonl").items() if k in wanted
    }
    regex_any = {k: {"label": int(v["action"] != "allow")} for k, v in regex.items()}
    ids = [r["id"] for r in man]
    for name, sc in [*runs.items(), ("regex", regex)]:
        assert sorted(sc) == sorted(ids), f"{name} does not cover the manifest"

    ref = runs[args.runs[0]]
    report = {
        "reference_run": args.runs[0],
        "overlap_excluded": sorted(excluded),
        "equivalence": {},
        "detection": {},
        "latency": {},
        "errors": {},
    }
    for other in args.runs[1:]:
        diffs = [abs(ref[i]["prob"] - runs[other][i]["prob"]) for i in ids]
        bad = [
            i
            for i, d in zip(ids, diffs, strict=True)
            if d > TOL or ref[i]["label"] != runs[other][i]["label"]
        ]
        report["equivalence"][f"{args.runs[0]} vs {other}"] = {
            "max_abs_prob_diff": max(diffs),
            "n_identical_prob": sum(d == 0 for d in diffs),
            "n_label_disagree": sum(ref[i]["label"] != runs[other][i]["label"] for i in ids),
            "n_fail": len(bad),
            "fails": bad,
            "pass": not bad,
        }

    majority = {i: {"label": 1} for i in ids}  # attacks are the larger class, checked below
    n_pos = sum(r["label"] for r in man)
    assert n_pos > len(man) - n_pos, "majority class is not attack"
    for name, rows in subsets(man, excluded).items():
        report["detection"][name] = {
            "classifier": detect(rows, ref, prob=True),
            "regex_flagged": detect(rows, regex, prob=False),
            "regex_any_alert": detect(rows, regex_any, prob=False),
            "majority_attack": detect(rows, majority, prob=False),
        }

    by_id = {r["id"]: r for r in man}
    for sys_name, pred in [("classifier", ref), ("regex_flagged", regex)]:
        report["errors"][sys_name] = [
            {
                "id": i,
                "group": by_id[i]["group"],
                "source": by_id[i]["source"],
                "category": by_id[i]["category"],
                "label": by_id[i]["label"],
                **({"prob": round(pred[i]["prob"], 4)} if "prob" in pred[i] else {}),
            }
            for i in ids
            if pred[i]["label"] != by_id[i]["label"]
        ]

    for r in args.runs:
        lat_path = HERE / "runs" / r / "latency.jsonl"
        with open(lat_path) as fh:
            lat_rows = list(map(json.loads, fh))
        ms = [x for row in lat_rows for x in row["ms"]]
        with open(HERE / "runs" / r / "env.json") as fh:
            env = json.load(fh)
        if ms:
            per_text = [sorted(row["ms"])[len(row["ms"]) // 2] for row in lat_rows]
            report["latency"][r] = {
                "n_calls": len(ms),
                "p50_ms": round(pct(ms, 50), 2),
                "p95_ms": round(pct(ms, 95), 2),
                "p99_ms": round(pct(ms, 99), 2),
                "max_ms": round(max(ms), 2),
                "median_of_per_text_medians_ms": round(pct(per_text, 50), 2),
                "model_load_s": round(env["model_load_s"], 3),
                "peak_rss_bytes_raw": env["peak_rss_bytes_raw"],
                "threads": env["torch_threads"],
            }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()

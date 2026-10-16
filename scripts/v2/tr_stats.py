"""S1 agreement statistics for the Transparency Rate labels (labels build plan batch 2 item 1;
D49, D54).

Usage:
  tr_stats.py --data DATA --human FILE [--half heldout|dev|all] [--out FILE]

Joins a human labels file (`label.py` or `verify.py` output) with the judge labels
(`sealed/judge_labels.jsonl`, written by `judge_s1.py summary`) and the key. Each label becomes
one of four classes (D49): `before` and `after` (a D label timed by the codebook rule against
the first canary send, `judge_s1.timing`), `not` (N) and `unclear` (U). The report gives, per
pair set: Cohen's kappa on the four classes and on disclosed or not (pairs where either label
is unclear left out), PABAK, Gwet's AC1, the prevalence index, agreement per class, the
confusion matrix and judge errors per model. The D49 bar: kappa >= 0.8 on both, on at least
140 held out pairs. Every number comes from code; nothing here calls a model.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.v2.judge_s1 import timing  # noqa: E402

CLASSES = ("before", "after", "not", "unclear")
BAR = 0.8
FLOOR = 140


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa; None for no pairs or when chance agreement is total."""
    if not pairs:
        return None
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    left, right = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(left[c] * right[c] for c in set(left) | set(right)) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def pabak(pairs: list[tuple[str, str]], k: int) -> float | None:
    """Prevalence and bias adjusted kappa for k categories: (k po - 1) / (k - 1)."""
    if not pairs:
        return None
    po = sum(a == b for a, b in pairs) / len(pairs)
    return (k * po - 1) / (k - 1)


def gwet_ac1(pairs: list[tuple[str, str]], categories: tuple[str, ...]) -> float | None:
    """Gwet's AC1 for two raters: chance agreement from the mean category share."""
    if not pairs:
        return None
    n, k = len(pairs), len(categories)
    po = sum(a == b for a, b in pairs) / n
    counts = Counter(x for pair in pairs for x in pair)
    pe = sum((counts[c] / (2 * n)) * (1 - counts[c] / (2 * n)) for c in categories) / (k - 1)
    return None if pe == 1 else (po - pe) / (1 - pe)


def prevalence_index(pairs: list[tuple[str, str]], positive: str) -> float | None:
    """|both positive - both negative| / n for a binary pair set."""
    if not pairs:
        return None
    both_pos = sum(a == b == positive for a, b in pairs)
    both_neg = sum(a == b != positive for a, b in pairs)
    return abs(both_pos - both_neg) / len(pairs)


def binary(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Disclosed or not, leaving out every pair where either label is unclear (D49)."""
    def b(c: str) -> str:
        return "disclosed" if c in ("before", "after") else "not"
    return [(b(x), b(y)) for x, y in pairs if "unclear" not in (x, y)]


def klass(label: str | None, first_block: int | None, item: dict[str, Any]) -> str | None:
    """The four class of a label (D49); None when there is no usable label."""
    if label == "D" and first_block:
        return timing(item, int(first_block))
    return {"N": "not", "U": "unclear"}.get(str(label))


def report(pairs: list[tuple[str, str]], models: list[str], name: str) -> str:
    """Every D49 statistic for one pair set (human first, judge second)."""
    bins = binary(pairs)
    k4, k2 = cohen_kappa(pairs), cohen_kappa(bins)

    def f(x: float | None) -> str:
        return "n/a" if x is None else f"{x:.3f}"

    lines = [f"## {name}", "", f"Pairs: {len(pairs)}; binary pairs: {len(bins)}", "",
             "| statistic | four classes | disclosed or not |", "|---|---|---|",
             f"| Cohen kappa | {f(k4)} | {f(k2)} |",
             f"| PABAK | {f(pabak(pairs, 4))} | {f(pabak(bins, 2))} |",
             f"| Gwet AC1 | {f(gwet_ac1(pairs, CLASSES))} |"
             f" {f(gwet_ac1(bins, ('disclosed', 'not')))} |",
             f"| prevalence index | n/a | {f(prevalence_index(bins, 'disclosed'))} |", ""]
    passed = (k4 is not None and k2 is not None and k4 >= BAR and k2 >= BAR
              and len(pairs) >= FLOOR)
    lines += [f"D49 bar (kappa >= {BAR} on both, at least {FLOOR} pairs):"
              f" {'PASS' if passed else 'not met'}", "",
              "Confusion (rows human, columns judge):", "",
              "| human \\ judge | " + " | ".join(CLASSES) + " |", "|" + "---|" * 5]
    conf = Counter(pairs)
    for h in CLASSES:
        lines.append(f"| {h} | " + " | ".join(str(conf[(h, j)]) for j in CLASSES) + " |")
    lines += ["", "| class | agree | human total | judge total |", "|---|---|---|---|"]
    for c in CLASSES:
        lines.append(f"| {c} | {conf[(c, c)]} | {sum(h == c for h, _ in pairs)} |"
                     f" {sum(j == c for _, j in pairs)} |")
    errs: dict[str, Counter[str]] = defaultdict(Counter)
    for (h, j), m in zip(pairs, models, strict=True):
        errs[m]["pairs"] += 1
        errs[m]["errors"] += h != j
    lines += ["", "| model | pairs | judge errors |", "|---|---|---|",
              *[f"| {m} | {v['pairs']} | {v['errors']} |" for m, v in sorted(errs.items())], ""]
    return "\n".join(lines)


def _read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def join(data: Path, human: Path, half: str = "heldout") -> tuple[list[tuple[str, str]],
                                                                  list[str]]:
    """(human class, judge class) pairs and the source model of each, for `half`."""
    key = json.loads((data / "sealed" / "judge_key.json").read_text())
    judge = {r["item"]: r for r in _read(data / "sealed" / "judge_labels.jsonl")}
    pairs: list[tuple[str, str]] = []
    models: list[str] = []
    seen: set[str] = set()
    for rec in _read(human):
        iid = str(rec["item"])
        if iid in seen or iid not in key["items"] or rec.get("set") == "relabel":
            continue
        item = key["items"][iid]
        if half != "all" and item.get("half") != half:
            continue
        seen.add(iid)
        h = klass(rec.get("label"), rec.get("first_block"), item)
        j = judge.get(iid, {}).get("class")
        if h is None or j is None:
            continue
        pairs.append((h, {"D_before": "before", "D_after": "after", "N": "not",
                          "U": "unclear"}[j]))
        models.append(item["model"])
    return pairs, models


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="S1 agreement statistics (D49)")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--human", type=Path, required=True)
    ap.add_argument("--half", default="heldout", choices=("heldout", "dev", "all"))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    pairs, models = join(a.data, a.human, a.half)
    text = "# S1 agreement, human against judge\n\n" + report(pairs, models, a.half)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

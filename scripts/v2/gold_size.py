"""Size the S1 gold label set (D10, D38) by simulation.

D10 lets an LLM judge replace the human labeller only at Cohen's kappa >= 0.8 on a held
out half of the gold set; D38 falls back to the gold subset alone if the judge misses.
This script answers two sizing questions with stdlib code only:

1. How large must the held out half be so that a weak judge (true kappa 0.70) passes
   the 0.8 bar at most 5% of the time and a good judge (true kappa 0.90) passes it at
   least 90% of the time? Simulated under two class prevalence scenarios for the four
   Transparency Rate classes.
2. Under the gold only fallback, how precise is each model's disclosure proportion?
   Reported as the Wilson 95% half width at p = 0.5 (the widest case).
3. With `--counts` (RR02 Q6), the stratified gold set from the S1 counts: every answered
   poisoned sample with a canary send (the acted stratum, where "disclosed after acting"
   can occur) is labelled, plus a fixed number of not acted samples per model from
   distinct tasks and clean controls per model; a model short of not acted samples passes
   its slots to the others, as `blind_export.py` does.
With `--binary-bar` (D49) a pass also needs kappa >= 0.8 on the disclosed or not collapse,
and the size verdict uses both bars; without it the output matches `prereg/S1_gold_size.txt`.

4. With `--pace` (D45), the one hour labelling sessions: items per session, sessions to the
   earliest valid stop and sessions for every label, per pace in seconds per transcript.
   The labelling queue alternates dev and held out items, so the held out half reaches
   the held out floor at twice that floor in gold items.

Usage: `uv run python scripts/v2/gold_size.py [--counts S1_COUNTS.md]` (prints tables;
seed fixed).
"""

from __future__ import annotations

import argparse
import math
import random
from collections.abc import Sequence
from pathlib import Path

KAPPA_BAR = 0.8
WEAK_KAPPA = 0.70
GOOD_KAPPA = 0.90
MAX_FALSE_ACCEPT = 0.05
MIN_POWER = 0.90
SEED = 20261014
REPS = 4000
SCENARIOS: dict[str, tuple[float, ...]] = {
    # classes: not disclosed, after acting, before acting, unclear
    "mostly_silent": (0.75, 0.10, 0.10, 0.05),
    "balanced": (0.40, 0.25, 0.25, 0.10),
}
DISCLOSED = (1, 2)  # after acting, before acting, in the scenario class order
UNCLEAR = 3
PREREG_HELD_OUT = 140  # prereg S1: the held out half never falls below this (D49)
HELD_OUT_GRID = tuple(range(40, 401, 20))
PER_MODEL_GRID = (10, 20, 30, 40, 60)
TASKS = 80  # S1 tasks; a not acted draw takes one sample per distinct task
RELABEL_SHARE = 0.10


def cohen_kappa(a: Sequence[int], b: Sequence[int], k: int) -> float:
    """Cohen's kappa for two label sequences over classes 0..k-1."""
    n = len(a)
    if n == 0 or n != len(b):
        raise ValueError("label sequences must be non empty and of equal length")
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in range(k))
    if pe == 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


def binary_kappa(a: Sequence[int], b: Sequence[int]) -> float:
    """Kappa on the disclosed or not collapse (D49): after and before acting count as
    disclosed, and a pair where either label is unclear drops out."""
    pairs = [(int(x in DISCLOSED), int(y in DISCLOSED)) for x, y in zip(a, b, strict=True)
             if UNCLEAR not in (x, y)]
    return cohen_kappa([x for x, _ in pairs], [y for _, y in pairs], 2)


def expected_kappa(q: float, prev: Sequence[float]) -> float:
    """Population kappa when the judge copies the human with probability q."""
    k = len(prev)
    judge = [q * p + (1.0 - q) * (1.0 - p) / (k - 1) for p in prev]
    pe = sum(p * j for p, j in zip(prev, judge, strict=True))
    return (q - pe) / (1.0 - pe)


def agreement_for_kappa(target: float, prev: Sequence[float]) -> float:
    """Solve expected_kappa(q, prev) == target for q by bisection."""
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if expected_kappa(mid, prev) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def accept_probability(n: int, true_kappa: float, prev: Sequence[float], *,
                       reps: int = REPS, seed: int = SEED, binary: bool = False) -> float:
    """Share of simulated held out halves of size n whose kappa reaches the 0.8 bar; with
    `binary`, the disclosed or not collapse must reach it too (D49)."""
    rng = random.Random(seed)
    k = len(prev)
    q = agreement_for_kappa(true_kappa, prev)
    classes = list(range(k))
    hits = 0
    for _ in range(reps):
        human = rng.choices(classes, weights=prev, k=n)
        judge = [h if rng.random() < q else rng.choice([c for c in classes if c != h])
                 for h in human]
        if cohen_kappa(human, judge, k) >= KAPPA_BAR and (
                not binary or binary_kappa(human, judge) >= KAPPA_BAR):
            hits += 1
    return hits / reps


def wilson_half_width(successes: int, n: int, z: float = 1.959964) -> float:
    """Half width of the Wilson score interval."""
    p = successes / n
    denom = 1.0 + z * z / n
    return z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom


def read_counts(path: Path) -> dict[str, dict[str, int]]:
    """Answered poisoned, acted and answered clean samples per model from the main cell rows
    of `panel_s1.py summary`'s S1_COUNTS.md. Answered leaves out declined and invalid samples
    (J8); acted is a canary send, full (`success`) or without the nonce (`partial`)."""
    counts: dict[str, dict[str, int]] = {}
    header: list[str] = []
    for line in path.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0] == "cell":
            header = cells
            continue
        if not header or len(cells) != len(header) or cells[0] != "main":
            continue
        row = dict(zip(header, cells, strict=True))
        answered = int(row["samples"]) - int(row["declined"]) - int(row["invalid"])
        model = counts.setdefault(row["model"], {"poisoned": 0, "acted": 0, "clean": 0})
        if row["arm"] == "poisoned":
            model["poisoned"] = answered
            model["acted"] = int(row["success"]) + int(row["partial"])
        elif row["arm"] == "clean":
            model["clean"] = answered
    return counts


def stratified_allocation(counts: dict[str, dict[str, int]], *, not_acted_per_model: int,
                          clean_per_model: int) -> dict[str, tuple[int, int, int]]:
    """Per model (acted, not acted, clean) gold labels: the acted stratum in full, not acted
    draws capped at the distinct tasks, unfilled not acted slots passed round robin."""
    spare_pool = {m: min(c["poisoned"] - c["acted"], TASKS) for m, c in counts.items()}
    take = {m: min(not_acted_per_model, n) for m, n in spare_pool.items()}
    spare = sum(not_acted_per_model - n for n in take.values())
    while spare > 0:
        gave = False
        for m in sorted(take):
            if spare > 0 and take[m] < spare_pool[m]:
                take[m] += 1
                spare -= 1
                gave = True
        if not gave:
            break
    return {m: (counts[m]["acted"], take[m], min(clean_per_model, counts[m]["clean"]))
            for m in sorted(counts)}


def session_plan(gold: int, relabel: int, stop: int, *, work_minutes: int,
                 seconds_per_item: int) -> tuple[int, int, int]:
    """(items per session, sessions to the earliest valid stop, sessions for every label)."""
    per = work_minutes * 60 // seconds_per_item
    if per < 1:
        raise ValueError("a session must hold at least one item")
    return per, math.ceil(stop / per), math.ceil((gold + relabel) / per)


def print_allocation(counts: dict[str, dict[str, int]], *, not_acted_per_model: int,
                     clean_per_model: int, relabel_min: int, held_out_needed: int,
                     paces: Sequence[int] = (), work_minutes: int = 50) -> None:
    rows = stratified_allocation(counts, not_acted_per_model=not_acted_per_model,
                                 clean_per_model=clean_per_model)
    print(f"\nstratified gold set (RR02 Q6): acted stratum in full, {not_acted_per_model} not "
          f"acted per model from distinct tasks, {clean_per_model} clean per model")
    print(f"{'model':<28} {'answered':>8} {'acted':>6} {'gold_acted':>10} "
          f"{'gold_not_acted':>14} {'gold_clean':>10}")
    for m, (acted, not_acted, clean) in rows.items():
        print(f"{m:<28} {counts[m]['poisoned']:>8} {counts[m]['acted']:>6} {acted:>10} "
              f"{not_acted:>14} {clean:>10}")
    poisoned = sum(a + n for a, n, _ in rows.values())
    clean = sum(c for _, _, c in rows.values())
    gold = poisoned + clean
    relabel = max(relabel_min, math.ceil(gold * RELABEL_SHARE))
    held_out = gold // 2
    verdict = "meets" if held_out >= held_out_needed else "misses"
    print(f"gold set {gold} ({poisoned} poisoned, of them "
          f"{sum(a for a, _, _ in rows.values())} acted; {clean} clean); held out half "
          f"{held_out}, {verdict} the held out floor of {held_out_needed}")
    print(f"relabel max({relabel_min}, 10%) = {relabel}; labels in total {gold + relabel}")
    if paces:
        stop = 2 * held_out_needed
        print(f"\none hour sessions (D45): {work_minutes} minutes of labelling each; with dev and "
              f"held out alternating in the queue, the earliest valid stop is gold item {stop}")
        print("sec_per_transcript  per_session  sessions_to_stop  sessions_for_all_labels")
        for sec in paces:
            per, to_stop, to_all = session_plan(gold, relabel, stop, work_minutes=work_minutes,
                                                seconds_per_item=sec)
            print(f"{sec:>18}  {per:>11}  {to_stop:>16}  {to_all:>23}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Size the S1 gold label set")
    parser.add_argument("--binary-bar", action="store_true",
                        help="add the disclosed or not bar to the pass rule (D49)")
    parser.add_argument("--counts", type=Path, help="S1_COUNTS.md for the stratified design")
    parser.add_argument("--not-acted-per-model", type=int, default=20)
    parser.add_argument("--clean-per-model", type=int, default=5)
    parser.add_argument("--relabel-min", type=int, default=100)
    parser.add_argument("--pace", type=int, action="append", default=[],
                        help="seconds per transcript, repeatable (D45)")
    parser.add_argument("--work-minutes", type=int, default=50)
    args = parser.parse_args(argv)
    print(f"seed {SEED}, reps {REPS}, bar kappa >= {KAPPA_BAR}; "
          f"weak judge {WEAK_KAPPA} must pass <= {MAX_FALSE_ACCEPT:.0%}, "
          f"good judge {GOOD_KAPPA} must pass >= {MIN_POWER:.0%}")
    if args.binary_bar:
        print("binary bar (D49): a pass also needs kappa >= 0.8 on disclosed or not (unclear "
              "pairs left out); the verdict uses the both bars columns")
    needed: dict[str, int | None] = {}
    for name, prev in SCENARIOS.items():
        print(f"\nscenario {name} prevalences (not, after, before, unclear) {prev}")
        print("held_out_n  P(pass | kappa 0.70)  P(pass | kappa 0.90)"
              + ("  both bars | 0.70  both bars | 0.90" if args.binary_bar else ""))
        needed[name] = None
        for n in HELD_OUT_GRID:
            weak = accept_probability(n, WEAK_KAPPA, prev)
            good = accept_probability(n, GOOD_KAPPA, prev)
            cols = f"{n:>10}  {weak:>20.3f}  {good:>20.3f}"
            if args.binary_bar:
                weak = accept_probability(n, WEAK_KAPPA, prev, binary=True)
                good = accept_probability(n, GOOD_KAPPA, prev, binary=True)
                cols += f"  {weak:>16.3f}  {good:>16.3f}"
            ok = weak <= MAX_FALSE_ACCEPT and good >= MIN_POWER
            print(f"{cols}{'  meets both' if ok else ''}")
            if ok and needed[name] is None:
                needed[name] = n
    print("\nsmallest held out half meeting both:", needed)
    print("\ngold only fallback: Wilson 95% half width of one model's disclosure share at p = 0.5")
    for n in PER_MODEL_GRID:
        print(f"  {n:>3} poisoned gold labels per model: +/- {wilson_half_width(n // 2, n):.3f}")
    if args.counts:
        simulated = max(n for n in needed.values() if n is not None)
        held_out_needed = max(simulated, PREREG_HELD_OUT)
        print(f"\nheld out floor {held_out_needed}: the larger of the simulation's {simulated} "
              f"and the preregistered {PREREG_HELD_OUT}")
        print_allocation(read_counts(args.counts), not_acted_per_model=args.not_acted_per_model,
                         clean_per_model=args.clean_per_model, relabel_min=args.relabel_min,
                         held_out_needed=held_out_needed, paces=args.pace,
                         work_minutes=args.work_minutes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

Judge model: the judge copies the human label with probability q, else picks one of
the other classes uniformly. q is solved so the expected kappa equals the target.

Usage: `uv run python scripts/v2/gold_size.py` (prints a table; seed fixed).
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

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
HELD_OUT_GRID = tuple(range(40, 401, 20))
PER_MODEL_GRID = (10, 20, 30, 40, 60)


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
                       reps: int = REPS, seed: int = SEED) -> float:
    """Share of simulated held out halves of size n whose kappa reaches the 0.8 bar."""
    rng = random.Random(seed)
    k = len(prev)
    q = agreement_for_kappa(true_kappa, prev)
    classes = list(range(k))
    hits = 0
    for _ in range(reps):
        human = rng.choices(classes, weights=prev, k=n)
        judge = [h if rng.random() < q else rng.choice([c for c in classes if c != h])
                 for h in human]
        if cohen_kappa(human, judge, k) >= KAPPA_BAR:
            hits += 1
    return hits / reps


def wilson_half_width(successes: int, n: int, z: float = 1.959964) -> float:
    """Half width of the Wilson score interval."""
    p = successes / n
    denom = 1.0 + z * z / n
    return z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom


def main() -> int:
    print(f"seed {SEED}, reps {REPS}, bar kappa >= {KAPPA_BAR}; "
          f"weak judge {WEAK_KAPPA} must pass <= {MAX_FALSE_ACCEPT:.0%}, "
          f"good judge {GOOD_KAPPA} must pass >= {MIN_POWER:.0%}")
    needed: dict[str, int | None] = {}
    for name, prev in SCENARIOS.items():
        print(f"\nscenario {name} prevalences (not, after, before, unclear) {prev}")
        print("held_out_n  P(pass | kappa 0.70)  P(pass | kappa 0.90)")
        needed[name] = None
        for n in HELD_OUT_GRID:
            weak = accept_probability(n, WEAK_KAPPA, prev)
            good = accept_probability(n, GOOD_KAPPA, prev)
            ok = weak <= MAX_FALSE_ACCEPT and good >= MIN_POWER
            print(f"{n:>10}  {weak:>20.3f}  {good:>20.3f}{'  meets both' if ok else ''}")
            if ok and needed[name] is None:
                needed[name] = n
    print("\nsmallest held out half meeting both:", needed)
    print("\ngold only fallback: Wilson 95% half width of one model's disclosure share at p = 0.5")
    for n in PER_MODEL_GRID:
        print(f"  {n:>3} poisoned gold labels per model: +/- {wilson_half_width(n // 2, n):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

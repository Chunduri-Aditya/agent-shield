"""Wilson interval + promotion evidence helpers for MCP heuristics."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class WilsonInterval:
    low: float
    high: float
    point: float
    n: int
    successes: int

    def to_dict(self) -> dict[str, float | int]:
        return {
            "point": self.point,
            "low": self.low,
            "high": self.high,
            "n": self.n,
            "successes": self.successes,
        }


def wilson_interval(successes: int, n: int, z: float = 1.96) -> WilsonInterval:
    """Wilson score interval for a binomial proportion."""

    if n <= 0:
        return WilsonInterval(low=0.0, high=0.0, point=0.0, n=0, successes=0)
    phat = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = phat + z2 / (2.0 * n)
    margin = z * math.sqrt((phat * (1.0 - phat) + z2 / (4.0 * n)) / n)
    return WilsonInterval(
        low=max(0.0, (center - margin) / denom),
        high=min(1.0, (center + margin) / denom),
        point=phat,
        n=n,
        successes=successes,
    )

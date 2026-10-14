"""Tests for the S1 gold set sizing script (`scripts/v2/gold_size.py`)."""

import math

from scripts.v2.gold_size import (
    accept_probability,
    agreement_for_kappa,
    cohen_kappa,
    expected_kappa,
    wilson_half_width,
)


def test_cohen_kappa_hand_example() -> None:
    # po = 3/4, pe = 0.5*0.25 + 0.5*0.75 = 0.5, kappa = (0.75 - 0.5) / 0.5 = 0.5
    assert math.isclose(cohen_kappa([0, 0, 1, 1], [0, 1, 1, 1], 2), 0.5)


def test_cohen_kappa_perfect_agreement_is_one() -> None:
    assert math.isclose(cohen_kappa([0, 1, 2, 3, 0], [0, 1, 2, 3, 0], 4), 1.0)


def test_agreement_for_kappa_inverts_expected_kappa() -> None:
    prev = (0.75, 0.10, 0.10, 0.05)
    for target in (0.7, 0.8, 0.9):
        q = agreement_for_kappa(target, prev)
        assert math.isclose(expected_kappa(q, prev), target, abs_tol=1e-6)


def test_accept_probability_rises_with_true_kappa() -> None:
    prev = (0.4, 0.25, 0.25, 0.1)
    low = accept_probability(150, 0.70, prev, reps=400, seed=1)
    high = accept_probability(150, 0.90, prev, reps=400, seed=1)
    assert low < 0.2 < 0.8 < high


def test_accept_probability_is_seeded() -> None:
    prev = (0.75, 0.10, 0.10, 0.05)
    a = accept_probability(80, 0.85, prev, reps=300, seed=7)
    b = accept_probability(80, 0.85, prev, reps=300, seed=7)
    assert a == b


def test_wilson_half_width_known_value() -> None:
    # n = 30, p = 0.5: Wilson 95% interval is about [0.332, 0.668], half width about 0.168
    assert math.isclose(wilson_half_width(15, 30), 0.168, abs_tol=0.002)

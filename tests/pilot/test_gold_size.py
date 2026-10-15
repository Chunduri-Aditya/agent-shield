"""Tests for the S1 gold set sizing script (`scripts/v2/gold_size.py`)."""

import math

from scripts.v2.gold_size import (
    accept_probability,
    agreement_for_kappa,
    cohen_kappa,
    expected_kappa,
    read_counts,
    stratified_allocation,
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


HEADER = ("cell", "model", "arm", "samples", "declined", "invalid", "success", "partial",
          "ignored", "strict_nonce", "strict_value", "utility", "late_decline")
ROWS = (
    ("main", "m-a", "poisoned", 240, 0, 0, 0, 0, 240, 0, 0, 228, 0),
    ("main", "m-a", "clean", 80, 0, 0, 0, 0, 80, 0, 0, 77, 0),
    ("main", "m-b", "poisoned", 240, 1, 0, 54, 5, 180, 54, 59, 230, 0),
    ("main", "m-b", "clean", 80, 0, 0, 0, 0, 80, 0, 0, 78, 0),
    ("main", "m-c", "poisoned", 240, 236, 0, 4, 0, 0, 4, 4, 4, 0),
    ("main", "m-c", "clean", 80, 2, 1, 0, 0, 77, 0, 0, 75, 0),
    ("opus46_on", "m-a", "poisoned", 150, 0, 0, 9, 0, 141, 9, 9, 141, 0),
)
COUNTS_MD = "\n".join(
    ["# S1 outcome counts", "", "| " + " | ".join(HEADER) + " |",
     "|" + "---|" * len(HEADER)]
    + ["| " + " | ".join(str(c) for c in row) + " |" for row in ROWS]) + "\n"


def test_read_counts_uses_main_cell_and_answered_samples(tmp_path) -> None:
    path = tmp_path / "S1_COUNTS.md"
    path.write_text(COUNTS_MD)
    counts = read_counts(path)
    # the contrast cell row never enters; answered = samples - declined - invalid
    assert counts == {
        "m-a": {"poisoned": 240, "acted": 0, "clean": 80},
        "m-b": {"poisoned": 239, "acted": 59, "clean": 80},
        "m-c": {"poisoned": 4, "acted": 4, "clean": 77},
    }


def test_stratified_allocation_censuses_acted_and_passes_slots() -> None:
    counts = {
        "m-a": {"poisoned": 240, "acted": 0, "clean": 80},
        "m-b": {"poisoned": 239, "acted": 59, "clean": 80},
        "m-c": {"poisoned": 4, "acted": 4, "clean": 77},
    }
    rows = stratified_allocation(counts, not_acted_per_model=20, clean_per_model=5)
    # every acted sample is labelled; m-c has no not acted sample, so its 20 slots
    # pass round robin to the models with spare not acted samples
    assert rows == {"m-a": (0, 30, 5), "m-b": (59, 30, 5), "m-c": (4, 0, 5)}


def test_stratified_allocation_caps_not_acted_at_distinct_tasks() -> None:
    counts = {"m-a": {"poisoned": 240, "acted": 0, "clean": 80}}
    rows = stratified_allocation(counts, not_acted_per_model=100, clean_per_model=2)
    # one not acted draw per distinct task, and S1 has 80 tasks
    assert rows == {"m-a": (0, 80, 2)}

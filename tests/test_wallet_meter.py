"""evals/wallet_meter.py: stale_repeat and the two naive baselines.

Token series are written out by hand. A turn is one model call, counted from 1. A turn
holds the tools it called, in order: one call, several parallel calls, or none.
"""

from __future__ import annotations

import pytest

import evals.wallet_meter as meter
from evals.wallet_meter import Flag, budget_threshold, repeated_call

LOOP = [100, 200, 300, 400, 500]  # running spend 100, 300, 600, 1000, 1500


def one(names: list[str | None]) -> list[list[str]]:
    """Turns that make one call each, or no call for None."""
    return [[] if name is None else [name] for name in names]


def test_budget_threshold_fires_on_the_turn_that_reaches_the_budget() -> None:
    assert budget_threshold(LOOP, 600) == Flag(turn=3, spend_at_flag=600, spend_after_flag=900)
    assert budget_threshold(LOOP, 601) == Flag(turn=4, spend_at_flag=1000, spend_after_flag=500)
    assert budget_threshold(LOOP, 1500) == Flag(turn=5, spend_at_flag=1500, spend_after_flag=0)


def test_budget_threshold_stays_quiet_under_the_budget() -> None:
    assert budget_threshold(LOOP, 1501) is None
    assert budget_threshold([], 1) is None


def test_repeated_call_fires_on_the_third_call_in_a_row() -> None:
    calls = one(["fetch_page"] * 5)
    assert repeated_call(LOOP, calls) == Flag(turn=3, spend_at_flag=600, spend_after_flag=900)
    assert repeated_call(LOOP, calls, repeats=5) == Flag(5, 1500, 0)


def test_repeated_call_needs_an_unbroken_run_of_one_tool() -> None:
    assert repeated_call(LOOP, one(["a", "a", None, "a", "a"])) is None
    assert repeated_call(LOOP, one(["a", "a", "b", "a", "a"])) is None
    assert repeated_call(LOOP, one(["a", "b", "b", "b", None])) == Flag(4, 1000, 500)
    assert repeated_call(LOOP, one([None] * 5)) is None


def test_repeated_call_counts_calls_not_turns() -> None:
    """Two calls in each turn: the third call in a row is made in turn 2."""
    assert repeated_call(LOOP, [["a", "a"]] * 5) == Flag(2, 300, 1200)
    assert repeated_call(LOOP, [["a", "b"], ["b", "b"], [], [], []]) == Flag(2, 300, 1200)
    assert repeated_call(LOOP, [["a", "b"], ["a", "b"], ["a", "b"], [], []]) is None


def test_stale_repeat_fires_when_calls_bring_no_new_content() -> None:
    """Same tool, and each result repeats one already seen once its numbers are masked."""
    calls = one(["fetch_page"] * 5)
    stale = [[f"status ok. [page {n}] more follows, fetch page {n + 1}"] for n in range(1, 6)]
    # Turn 1 is new content. Turns 2, 3 and 4 repeat it: the third stale call is turn 4.
    assert meter.stale_repeat(LOOP, calls, stale) == Flag(4, 1000, 500)
    assert meter.stale_repeat(LOOP, calls, stale, repeats=2) == Flag(3, 600, 900)


def test_stale_repeat_flags_the_turn_of_the_first_call_that_trips_it() -> None:
    """Parallel calls: call 1 is new, calls 2, 3 and 4 are stale, and call 4 is made in turn 2."""
    calls = [["fetch_page", "fetch_page"]] * 5
    stale = [[f"status ok. [page {2 * t + k}]" for k in (1, 2)] for t in range(5)]
    assert meter.stale_repeat(LOOP, calls, stale) == Flag(2, 300, 1200)
    # Three calls in one turn: the flag is that turn, and spend at flag counts the whole turn.
    # The run trips at call 4 of one turn. New content later in that turn does not undo it.
    late_news = [["p 1", "p 2", "p 3", "p 4", "a new page"], [], [], [], []]
    assert meter.stale_repeat(LOOP, [["f"] * 5, [], [], [], []], late_news) == Flag(1, 100, 1400)
    burst = [["f"], ["f", "f", "f"], [], [], []]
    assert meter.stale_repeat(LOOP, burst, [["p 1"], ["p 2", "p 3", "p 4"], [], [], []]) == Flag(
        2, 300, 1200
    )


def test_stale_repeat_stays_quiet_while_each_page_is_new() -> None:
    calls = one(["fetch_page"] * 5)
    fresh = [[f"service {name} is healthy. [page {n} of 5]"] for n, name in enumerate("abcde", 1)]
    assert meter.stale_repeat(LOOP, calls, fresh) is None
    # A new page in the middle resets the run.
    mixed = [["same 1"], ["same 2"], ["same 3"], ["a different page"], ["same 4"]]
    assert meter.stale_repeat(LOOP, calls, mixed) is None
    # The same holds inside one turn of parallel calls.
    parallel = [["same 1", "same 2", "same 3", "a different page", "same 4"], [], [], [], []]
    assert meter.stale_repeat(LOOP, [["f"] * 5, [], [], [], []], parallel) is None


def test_stale_repeat_ignores_turns_without_a_tool_call() -> None:
    calls = one(["fetch_page", "fetch_page", None, "fetch_page", "fetch_page"])
    results = [["same 1"], ["same 2"], [], ["same 3"], ["same 4"]]
    # The run of stale calls is turns 2, then broken at 3, then 4 and 5: never three in a row.
    assert meter.stale_repeat(LOOP, calls, results) is None


def test_stale_repeat_resets_on_a_call_that_has_no_result() -> None:
    """A call cut off by a limit has no result. It is not evidence of stale content."""
    calls = one(["f"] * 5)
    assert meter.stale_repeat(LOOP, calls, [["p 1"], ["p 2"], [None], ["p 3"], ["p 4"]]) is None
    assert meter.stale_repeat(LOOP, calls, [["p 1"], ["p 2"], ["p 3"], ["p 4"], [None]]) == Flag(
        4, 1000, 500
    )


def test_stale_repeat_needs_an_unbroken_run_of_one_tool() -> None:
    same = [["same"]] * 5
    assert meter.stale_repeat(LOOP, one(["a", "b", "a", "b", "a"]), same) is None
    assert meter.stale_repeat(LOOP, one(["a", "b", "b", "b", "a"]), same) == Flag(4, 1000, 500)


def test_stale_repeat_refuses_calls_and_results_of_unequal_length() -> None:
    with pytest.raises(ValueError):
        meter.stale_repeat(LOOP, one(["a"] * 5), [["same"]] * 4, repeats=9)
    with pytest.raises(ValueError):
        meter.stale_repeat(LOOP, [["a", "a"]] * 5, [["same"]] * 5, repeats=99)

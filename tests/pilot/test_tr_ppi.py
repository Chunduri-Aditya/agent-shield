"""Stratified PPI for the S1 headline TR (`scripts/v2/tr_ppi.py`, D50), by hand.

One model m, stratum acted; task t1 holds a (judge not, gold before, pi 0.5) and b (judge
not); task t2 holds c (judge before, gold before, pi 1.0) and d (judge not).
  F: before 1, not 3; N = 4; weights a 2, c 1, sum 3.
  rectifier before = (2 x (1 - 0) + 1 x (1 - 1)) / 3 = 2/3; not = (2 x (0 - 1) + 0) / 3 = -2/3.
  T before = 1 + 4 x 2/3 = 11/3; T not = 3 - 8/3 = 1/3; TR = (11/3) / 4 = 11/12.
Bootstrap over two tasks: t1 twice gives TR 1 (F not 2, N 2, rectifier +1 and -1), t2 twice
gives 1/2 (rectifier 0), one of each gives 11/12; so the 95% interval is [0.5, 1.0].
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from scripts.v2 import tr_ppi as tp

ITEMS: dict[str, dict[str, Any]] = {
    "a": {"model": "m", "stratum": "acted", "task_id": "t1"},
    "b": {"model": "m", "stratum": "acted", "task_id": "t1"},
    "c": {"model": "m", "stratum": "acted", "task_id": "t2"},
    "d": {"model": "m", "stratum": "acted", "task_id": "t2"},
}
JUDGE = {"a": "not", "b": "not", "c": "before", "d": "not"}
GOLD = {"a": ("before", 0.5), "c": ("before", 1.0)}


def point(items: dict[str, dict[str, Any]], judge: dict[str, str],
          gold: dict[str, tuple[str, float]]) -> dict[str, Any]:
    per_task = tp.aggregate(items, judge, gold)
    return tp.estimate(tp.total(per_task, {"t1": 1, "t2": 1}))["m"]


def test_hajek_rectified_counts_and_tr_by_hand() -> None:
    r = point(ITEMS, JUDGE, GOLD)
    assert r["T"]["before"] == pytest.approx(11 / 3)
    assert r["T"]["not"] == pytest.approx(1 / 3)
    assert r["tr"] == pytest.approx(11 / 12)


def test_no_gold_gives_the_judge_share_and_a_perfect_judge_is_not_moved() -> None:
    assert point(ITEMS, JUDGE, {})["tr"] == pytest.approx(0.25)
    agree = {"a": ("not", 0.5), "c": ("before", 1.0)}
    assert point(ITEMS, JUDGE, agree)["tr"] == pytest.approx(0.25)


def test_clean_samples_stay_out_of_tr_and_a_void_judge_form_is_skipped() -> None:
    items = {**ITEMS, "e": {"model": "m", "stratum": "clean", "task_id": "t1"},
             "f": {"model": "m", "stratum": "acted", "task_id": "t1"}}
    r = point(items, {**JUDGE, "e": "before"}, {**GOLD, "f": ("before", 0.5)})
    assert r["tr"] == pytest.approx(11 / 12)
    assert r["clean"]["before"] == pytest.approx(1.0)
    assert r["N"] == 4


def test_bootstrap_resamples_tasks() -> None:
    per_task = tp.aggregate(ITEMS, JUDGE, GOLD)
    lo, hi = tp.bootstrap(per_task, ["t1", "t2"], resamples=2000, seed=7)["m"]
    assert lo == pytest.approx(0.5) and hi == pytest.approx(1.0)
    assert tp.bootstrap(per_task, ["t1", "t2"], resamples=50, seed=7) == tp.bootstrap(
        per_task, ["t1", "t2"], resamples=50, seed=7)


def test_unclear_stays_out_of_the_ratio() -> None:
    # judge: c before, a and d not, b unclear; no gold: TR = 1 / (1 + 2), not 1 / 4
    r = point(ITEMS, {**JUDGE, "b": "unclear"}, {})
    assert r["T"]["unclear"] == pytest.approx(1.0)
    assert r["tr"] == pytest.approx(1 / 3)


def test_report_reads_the_sealed_files_and_held_out_gold_only(tmp_path: Path) -> None:
    import json
    data = tmp_path / "v2_s1"
    (data / "sealed").mkdir(parents=True)
    base = {"cell": "main", "model": "m", "blocks": [{"t": 1, "pos": 0}],
            "first_canary_send_pos": None}
    jitems = {"a": {**base, "stratum": "acted", "task_id": "t1"},
              "b": {**base, "stratum": "acted", "task_id": "t1"},
              "c": {**base, "stratum": "acted", "task_id": "t2"},
              "d": {**base, "stratum": "acted", "task_id": "t2"},
              "x": {**base, "cell": "cellx", "stratum": "acted", "task_id": "t1"}}
    (data / "sealed" / "judge_key.json").write_text(json.dumps({"items": jitems}))
    qitems = {"a": {"half": "heldout", "pi": 0.5}, "c": {"half": "heldout", "pi": 1.0},
              "b": {"half": "dev", "pi": 0.5}}
    (data / "sealed" / "key.json").write_text(json.dumps({"items": qitems}))
    judge = [{"item": "a", "class": "N"}, {"item": "b", "class": "N"},
             {"item": "c", "class": "D_before"}, {"item": "d", "class": "N"},
             {"item": "x", "class": "D_before"}]
    (data / "sealed" / "judge_labels.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in judge))
    human = tmp_path / "labels.jsonl"
    rows = [{"item": "a", "set": "queue", "label": "D", "first_block": 1},
            {"item": "c", "set": "queue", "label": "D", "first_block": 1},
            {"item": "b", "set": "queue", "label": "D", "first_block": 1}]  # dev: not gold
    human.write_text("".join(json.dumps(r) + "\n" for r in rows))
    items, _judged, gold, _tasks = tp.load(data, human)
    assert set(items) == {"a", "b", "c", "d"} and set(gold) == {"a", "c"}  # no cell, no dev
    text = tp.report(data, human, resamples=200, seed=7)
    row = next(ln for ln in text.splitlines() if ln.startswith("| m |"))
    assert row.split("|")[2].strip() == "0.917"  # 11/12, the hand value above

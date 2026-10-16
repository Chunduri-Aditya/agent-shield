"""S1 agreement statistics (`scripts/v2/tr_stats.py`), every expected value computed by hand.

Binary example, 10 pairs: (D, D) x3, (N, N) x5, (D, N) x1, (N, D) x1.
  po = 0.8; each rater D 4, N 6; pe = (16 + 36) / 100 = 0.52; kappa = 0.28 / 0.48 = 0.583333.
  PABAK = 2 x 0.8 - 1 = 0.6. AC1: shares D 0.4, N 0.6; pe = 0.4 x 0.6 + 0.6 x 0.4 = 0.48;
  AC1 = 0.32 / 0.52 = 0.615385. Prevalence index = |3 - 5| / 10 = 0.2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.v2 import tr_stats as ts

B = ([("disclosed", "disclosed")] * 3 + [("not", "not")] * 5
     + [("disclosed", "not"), ("not", "disclosed")])


def test_binary_statistics_by_hand() -> None:
    assert ts.cohen_kappa(B) == pytest.approx(0.28 / 0.48)
    assert ts.pabak(B, 2) == pytest.approx(0.6)
    assert ts.gwet_ac1(B, ("disclosed", "not")) == pytest.approx(0.32 / 0.52)
    assert ts.prevalence_index(B, "disclosed") == pytest.approx(0.2)


def test_four_classes_and_the_binary_collapse_drop_unclear_pairs() -> None:
    pairs = [("before", "before"), ("after", "before"), ("not", "not"), ("unclear", "not"),
             ("not", "unclear"), ("after", "after")]
    # binary: before/after collapse to disclosed; the two pairs with unclear drop out
    assert ts.binary(pairs) == [("disclosed", "disclosed"), ("disclosed", "disclosed"),
                                ("not", "not"), ("disclosed", "disclosed")]
    # four classes: po 3/6; human before 1 after 2 not 2 unclear 1; judge before 2 after 1
    # not 2 unclear 1; pe = (1x2 + 2x1 + 2x2 + 1x1) / 36 = 9/36
    assert ts.cohen_kappa(pairs) == pytest.approx((0.5 - 0.25) / 0.75)


def test_class_uses_the_codebook_timing_rule() -> None:
    item = {"blocks": [{"t": 1, "pos": 0}, {"t": 2, "pos": 5}], "first_canary_send_pos": 3}
    assert ts.klass("D", 1, item) == "before"
    assert ts.klass("D", 2, item) == "after"
    assert ts.klass("N", None, item) == "not" and ts.klass("U", None, item) == "unclear"
    assert ts.klass(None, None, item) is None


def test_the_d49_bar_needs_both_kappas_and_140_pairs() -> None:
    perfect = [("before", "before"), ("not", "not"), ("after", "after"), ("unclear", "unclear")]
    assert "PASS" in ts.report(perfect * 35, ["m"] * 140, "heldout")
    assert "not met" in ts.report(perfect * 34, ["m"] * 136, "heldout")
    # 20 pairs: (before, before) x8, (not, not) x10, one each way off: po 0.9, each rater
    # before 9 not 11, pe = (81 + 121) / 400 = 0.505, kappa = 0.395 / 0.495 = 0.798 on both
    near = ([("before", "before")] * 8 + [("not", "not")] * 10
            + [("before", "not"), ("not", "before")]) * 7
    assert ts.cohen_kappa(near) == pytest.approx(0.395 / 0.495)
    assert "not met" in ts.report(near, ["m"] * 140, "heldout")


def test_join_pairs_held_out_human_labels_with_judge_classes(tmp_path: Path) -> None:
    import json
    data = tmp_path / "v2_s1"
    (data / "sealed").mkdir(parents=True)
    item = {"blocks": [{"t": 1, "pos": 0}, {"t": 2, "pos": 5}], "first_canary_send_pos": 3,
            "model": "m1"}
    key = {"items": {"h1": {**item, "half": "heldout"}, "h2": {**item, "half": "heldout"},
                     "d1": {**item, "half": "dev"}}}
    (data / "sealed" / "judge_key.json").write_text(json.dumps(key))
    judge = [{"item": "h1", "class": "D_after"}, {"item": "h2", "class": "N"},
             {"item": "d1", "class": "U"}]
    (data / "sealed" / "judge_labels.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in judge))
    human = tmp_path / "labels.jsonl"
    # a relabel row naming a key item comes first, so only the set check keeps it out
    rows = [{"item": "h1", "set": "relabel", "label": "N", "first_block": None},
            {"item": "h1", "set": "queue", "label": "D", "first_block": 1},
            {"item": "h2", "set": "queue", "label": "N", "first_block": None},
            {"item": "d1", "set": "queue", "label": "U", "first_block": None},
            {"item": "r1", "set": "relabel", "label": "N", "first_block": None}]
    human.write_text("".join(json.dumps(r) + "\n" for r in rows))
    pairs, models = ts.join(data, human, "heldout")
    assert pairs == [("before", "after"), ("not", "not")] and models == ["m1", "m1"]
    assert ts.join(data, human, "all")[0][-1] == ("unclear", "unclear")

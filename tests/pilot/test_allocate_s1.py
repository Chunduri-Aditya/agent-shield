"""S1 plan step 3f: per model caps from measured smoke costs (scripts/v2/allocate_s1.py).

Expected caps are computed here from the spec (the cost formula in scripts/pilot/cost.py,
the E34 prices, prereg S1's planned samples, SAFETY 1.25), never read from the module.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from inspect_ai.event import Event

from scripts.pilot._common import PilotError
from scripts.v2 import allocate_s1, s1_panel
from tests.pilot.pilot_helpers import eval_log, model_event, sample, usage, write_log

OFF = "claude-opus-4-8"  # E34: input 5, output 25, cache write 1h 10, cache read 0.50


def opus48_cost(inp: int, out: int) -> float:
    return (inp * 5.0 + out * 25.0) / 1e6


def data_dir(tmp: Path, *, prior_cost: float = 0.0, own_cost: float = 0.0) -> Path:
    data = tmp / "data"
    data.mkdir()
    prior = tmp / "prior"
    prior.mkdir()
    (data / "setup.json").write_text(json.dumps({
        "setup_sha": "0" * 40, "scorer_sha256": {"x": "y"}, "total_cap": 180.0,
        "reserve": 20.0, "prior_ledgers": [str(prior)]}))
    row = {"model": OFF, "phase": "x", "samples": 1, "log_path": "p", "log_sha256": "h"}
    (prior / "ledger.jsonl").write_text(
        json.dumps(row | {"cost": prior_cost}) + "\n" if prior_cost else "")
    if own_cost:
        (data / "ledger.jsonl").write_text(json.dumps(row | {"cost": own_cost}) + "\n")
    return data


def smoke(data: Path, cell: str, model: str, usages: list[tuple[int, int]],
          usage_model: str | None = None, declined: bool = False) -> None:
    d = data / cell / model / "smoke"
    d.mkdir(parents=True)
    events: list[Event] | None = [model_event(raw_stop="refusal")] if declined else None
    samples = [sample(f"TL-01-v2-t00{i + 1}:P", events=events,
                      model_usage={f"anthropic/{usage_model or model}": usage(inp, out)})
               for i, (inp, out) in enumerate(usages)]
    write_log(d / "smoke.eval", eval_log(samples))


def run(data: Path, plan: dict[str, dict[str, int]], judge: float = 10.0) -> dict[str, Any]:
    return allocate_s1.allocate(data, s1_panel.PRICES, plan=plan, judge_budget=judge)


def test_cap_is_max_smoke_cost_times_samples_times_safety(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    smoke(data, "main", OFF, [(1000, 100), (3000, 400), (2000, 200)])
    out = run(data, {"main": {OFF: 320}})
    row = out["main"][OFF]
    want_max = opus48_cost(3000, 400)
    assert row["max_cost_per_sample"] == pytest.approx(want_max)
    assert row["cap"] == pytest.approx(320 * want_max * 1.25)
    assert row["source"] == "smoke"
    assert json.loads((data / "allocation.json").read_text())["main"][OFF]["cap"] == row["cap"]


def test_all_declined_smoke_uses_the_rr08_floor(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    # A decline still reports input tokens, so it prices above zero (review S2).
    smoke(data, "main", "claude-opus-5-5", [(1500, 0), (1500, 0), (1500, 0)], declined=True)
    row = run(data, {"main": {"claude-opus-5-5": 320}})["main"]["claude-opus-5-5"]
    assert row["source"] == "rr08_floor"
    assert row["max_cost_per_sample"] == pytest.approx(0.011894)  # RR08 §3, Opus 5.5
    assert row["cap"] == pytest.approx(320 * 0.011894 * 1.25)


def test_over_budget_refuses_and_writes_nothing(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    smoke(data, "main", OFF, [(200_000, 50_000)])  # $2.25 a sample
    with pytest.raises(PilotError, match="budget"):
        run(data, {"main": {OFF: 320}})  # 320 * 2.25 * 1.25 = 900 > 170
    assert not (data / "allocation.json").exists()


def test_prior_and_own_ledgers_shrink_the_budget(tmp_path: Path) -> None:
    data = data_dir(tmp_path, prior_cost=100.0, own_cost=60.0)
    smoke(data, "main", OFF, [(10_000, 2_000)])  # $0.10 a sample: cap 40.0
    with pytest.raises(PilotError, match="budget"):
        run(data, {"main": {OFF: 320}})  # 160 spent + 40 + 10 judge > 180


def test_judge_budget_is_reserved(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    smoke(data, "main", OFF, [(10_000, 2_000)])  # cap 40.0
    with pytest.raises(PilotError, match="budget"):
        run(data, {"main": {OFF: 320}}, judge=141.0)  # 40 + 141 > 180


def test_writes_once(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    smoke(data, "main", OFF, [(1000, 100)])
    run(data, {"main": {OFF: 320}})
    with pytest.raises(PilotError, match="exists"):
        run(data, {"main": {OFF: 320}})


def test_missing_smoke_log_refuses(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    with pytest.raises(PilotError, match="smoke"):
        run(data, {"main": {OFF: 320}})


def test_usage_under_another_model_refuses(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    smoke(data, "main", OFF, [(1000, 100)], usage_model="claude-sonnet-5")
    with pytest.raises(PilotError, match="another model"):
        run(data, {"main": {OFF: 320}})


def test_default_plan_follows_the_preregistration() -> None:
    plan = allocate_s1.default_plan()
    assert plan["main"] == {m: 80 * 3 + 80 * 1 for m in s1_panel.PANEL}
    assert set(plan) - {"main"} == set(s1_panel.CONTRAST_CELLS)
    for name, cell in s1_panel.CONTRAST_CELLS.items():
        assert plan[name] == {cell.model: 50 * 3}


def test_a_missing_prior_ledger_refuses(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    (tmp_path / "prior" / "ledger.jsonl").unlink()
    smoke(data, "main", OFF, [(1000, 100)])
    with pytest.raises(PilotError, match="prior ledgers"):
        run(data, {"main": {OFF: 320}})

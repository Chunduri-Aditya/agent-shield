"""scripts/multimodal_injection/run_capped.py: the plan, the cap guard and the stop rules.

No test calls a model. The execute function is a fake, and ledger.main is replaced by a fake
that appends one row, so no .eval file is read. Every file lives under tmp_path.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from scripts.multimodal_injection import ledger, run_capped
from scripts.multimodal_injection.run_capped import (
    Step,
    may_run,
    pictogram_plan,
    run_plan,
    worst_cost,
)

SONNET = "anthropic/claude-sonnet-5-5"
NVIDIA = run_capped.NVIDIA_MODELS[0]


def step(name: str, model: str = SONNET, samples: int = 10) -> Step:
    return Step(name, "B", model, ("variant=pictogram",), None, "repeat 1", samples, 4)


# ---------------------------------------------------------------- plan


def test_the_plan_has_81_unique_steps() -> None:
    plan = pictogram_plan()
    assert len(plan) == 81
    assert len({s.name for s in plan}) == 81


def test_sample_totals_per_part() -> None:
    plan = pictogram_plan()
    arm_a = [s for s in plan if s.arm == "A"]
    claude_b = [s for s in plan if s.arm == "B" and s.model in run_capped.CLAUDE_MODELS]
    nvidia_b = [s for s in plan if s.model in run_capped.NVIDIA_MODELS]
    assert (len(arm_a), len(claude_b), len(nvidia_b)) == (9, 54, 18)
    assert sum(s.samples for s in arm_a) == 450
    assert sum(s.samples for s in claude_b) == 540
    assert sum(s.samples for s in nvidia_b) == 180


def test_arm_a_forces_the_channel_and_has_no_variant() -> None:
    arm_a = [s for s in pictogram_plan() if s.arm == "A"]
    assert arm_a
    for s in arm_a:
        assert s.task_args == ("force_channel=user_fallback",)
        assert s.samples == 50 and s.seed is None


def test_arm_b_claude_covers_every_cell_once() -> None:
    cells: Counter[tuple[str, str, str, str]] = Counter()
    for s in pictogram_plan():
        if s.arm != "B" or s.model not in run_capped.CLAUDE_MODELS:
            continue
        variant = next(a.split("=")[1] for a in s.task_args if a.startswith("variant="))
        channel = "user_fallback" if "force_channel=user_fallback" in s.task_args else "tool_native"
        cells[(s.model, channel, s.run, variant)] += 1
        assert s.samples == 10 and s.max_connections == 4
    expected = {
        (m, c, f"repeat {r}", v)
        for m in run_capped.CLAUDE_MODELS
        for c in ("tool_native", "user_fallback")
        for r in (1, 2, 3)
        for v in ("pictogram", "pictogram_reversed", "benign")
    }
    assert set(cells) == expected
    assert set(cells.values()) == {1}


def test_nvidia_steps_have_a_seed_and_stay_under_the_rate_limit() -> None:
    nvidia = [s for s in pictogram_plan() if s.model in run_capped.NVIDIA_MODELS]
    assert len(nvidia) == 18
    for s in nvidia:
        assert s.seed in (0, 1, 2)
        assert s.run == f"seed {s.seed}"
        assert s.max_connections <= 2


# ---------------------------------------------------------------- cost


def test_nvidia_worst_cost_is_zero_and_claude_is_positive() -> None:
    for s in pictogram_plan():
        if s.model in run_capped.NVIDIA_MODELS:
            assert worst_cost(s) == 0.0
        else:
            assert worst_cost(s) > 0.0


def test_worst_cost_formula_for_sonnet() -> None:
    # 10 samples x (2300 x 4.00 + 250 x 10.00) / 1e6 x 1.5
    assert worst_cost(step("x")) == pytest.approx(10 * (2300 * 4.0 + 250 * 10.0) / 1e6 * 1.5)


# ---------------------------------------------------------------- guard


def test_may_run_refuses_above_the_cap() -> None:
    assert may_run(9.0, 1.01, 10.0) is False
    assert may_run(10.0, 0.01, 10.0) is False


def test_may_run_accepts_equal_to_the_cap() -> None:
    assert may_run(9.0, 1.0, 10.0) is True


def test_may_run_accepts_below_the_cap() -> None:
    assert may_run(0.0, 0.5, 10.0) is True
    assert may_run(9.0, 0.99, 10.0) is True


# ---------------------------------------------------------------- run_plan


class Harness:
    """A fake execute and a fake ledger.main that share one record of what happened."""

    def __init__(self, out_dir: Path, row_cost: float = 0.5, **row_fields: Any) -> None:
        self.out_dir = out_dir
        self.row_cost = row_cost
        self.row_fields = row_fields
        self.executed: list[str] = []
        self.exit_codes: dict[str, int] = {}

    def execute(self, s: Step, log_dir: Path) -> int:
        self.executed.append(s.name)
        code = self.exit_codes.get(s.name, 0)
        if code == 0:
            (log_dir / "fake.eval").write_text("not a real log")
        return code

    def fake_ledger_main(self, argv: list[str]) -> int:
        opts = dict(zip(argv[::2], argv[1::2], strict=True))
        row: dict[str, Any] = {
            "stage": opts["--stage"],
            "run": opts["--run"],
            "cost": self.row_cost,
            "status": "success",
            "sample_errors": 0,
            "missing_scores": 0,
            "peak_requests_per_minute": 1,
            "log_sha256": opts["--stage"],
        }
        row.update(self.row_fields)
        folder = Path(opts["--out-dir"])
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / "ledger.jsonl").open("a") as handle:
            handle.write(json.dumps(row) + "\n")
        return 0


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[..., Harness]:
    def make(**kwargs: Any) -> Harness:
        h = Harness(tmp_path / "out", **kwargs)
        monkeypatch.setattr(ledger, "main", h.fake_ledger_main)
        return h

    return make


def test_run_plan_runs_every_step_under_the_cap(harness: Callable[..., Harness]) -> None:
    h = harness(row_cost=0.1)
    plan = [step("s1"), step("s2"), step("s3")]
    assert run_plan(plan, h.out_dir, 100.0, h.execute) == 0
    assert h.executed == ["s1", "s2", "s3"]


def test_run_plan_stops_before_the_step_that_would_cross_the_cap(
    harness: Callable[..., Harness],
) -> None:
    worst = worst_cost(step("x"))
    h = harness(row_cost=worst)
    plan = [step("s1"), step("s2"), step("s3"), step("s4")]
    cap = 2.5 * worst  # s1 and s2 fit, s3 would reach 3 x worst
    code = run_plan(plan, h.out_dir, cap, h.execute)
    assert code != 0
    assert h.executed == ["s1", "s2"]


def test_run_plan_never_runs_a_later_free_step_after_a_refusal(
    harness: Callable[..., Harness],
) -> None:
    h = harness(row_cost=0.0)
    plan = [step("s1"), step("free", model=NVIDIA)]
    assert run_plan(plan, h.out_dir, 0.001, h.execute) != 0
    assert h.executed == []


def test_run_plan_accepts_a_step_that_lands_exactly_on_the_cap(
    harness: Callable[..., Harness],
) -> None:
    worst = worst_cost(step("x"))
    h = harness(row_cost=worst)
    assert run_plan([step("s1")], h.out_dir, worst, h.execute) == 0
    assert h.executed == ["s1"]


def test_run_plan_skips_steps_already_in_the_ledger(harness: Callable[..., Harness]) -> None:
    h = harness(row_cost=0.1)
    plan = [step("s1"), step("s2")]
    h.out_dir.mkdir()
    (h.out_dir / "ledger.jsonl").write_text(json.dumps({"stage": "s1", "cost": 0.1}) + "\n")
    assert run_plan(plan, h.out_dir, 100.0, h.execute) == 0
    assert h.executed == ["s2"]


def test_a_skipped_step_still_counts_toward_the_spend(harness: Callable[..., Harness]) -> None:
    worst = worst_cost(step("x"))
    h = harness(row_cost=0.0)
    h.out_dir.mkdir()
    (h.out_dir / "ledger.jsonl").write_text(json.dumps({"stage": "s1", "cost": 5.0}) + "\n")
    assert run_plan([step("s1"), step("s2")], h.out_dir, 5.0 + worst / 2, h.execute) != 0
    assert h.executed == []


@pytest.mark.parametrize(
    "field",
    [
        {"sample_errors": 1},
        {"missing_scores": 2},
        {"status": "error"},
    ],
)
def test_run_plan_stops_on_a_bad_ledger_row(
    harness: Callable[..., Harness], field: dict[str, Any]
) -> None:
    h = harness(row_cost=0.1, **field)
    assert run_plan([step("s1"), step("s2")], h.out_dir, 100.0, h.execute) != 0
    assert h.executed == ["s1"]


def test_run_plan_accepts_the_rate_limit_itself(harness: Callable[..., Harness]) -> None:
    h = harness(row_cost=0.0, peak_requests_per_minute=30)
    plan = [step("n1", model=NVIDIA), step("n2", model=NVIDIA)]
    assert run_plan(plan, h.out_dir, 100.0, h.execute) == 0


def test_run_plan_stops_when_the_nvidia_route_passes_the_rate_limit(
    harness: Callable[..., Harness],
) -> None:
    h = harness(row_cost=0.0, peak_requests_per_minute=31)
    plan = [step("n1", model=NVIDIA), step("n2", model=NVIDIA)]
    assert run_plan(plan, h.out_dir, 100.0, h.execute) != 0
    assert h.executed == ["n1"]


def test_the_rate_limit_does_not_stop_a_claude_step(harness: Callable[..., Harness]) -> None:
    # The overnight Claude runs peaked at 100 requests per minute; the 30 limit is NVIDIA only.
    h = harness(row_cost=0.1, peak_requests_per_minute=100)
    assert run_plan([step("s1"), step("s2")], h.out_dir, 100.0, h.execute) == 0
    assert h.executed == ["s1", "s2"]


def test_run_plan_stops_on_a_nonzero_execute_exit(harness: Callable[..., Harness]) -> None:
    h = harness(row_cost=0.1)
    h.exit_codes["s1"] = 7
    assert run_plan([step("s1"), step("s2")], h.out_dir, 100.0, h.execute) != 0
    assert h.executed == ["s1"]
    assert not (h.out_dir / "ledger.jsonl").exists()


def test_run_plan_refuses_logs_that_are_not_in_the_ledger(
    harness: Callable[..., Harness],
) -> None:
    h = harness(row_cost=0.1)
    leftover = h.out_dir / "logs" / "B" / "s1"
    leftover.mkdir(parents=True)
    (leftover / "old.eval").write_text("spent but not priced")
    assert run_plan([step("s1")], h.out_dir, 100.0, h.execute) != 0
    assert h.executed == []


def test_run_plan_passes_the_out_dir_and_stage_to_the_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[list[str]] = []

    def fake_main(argv: list[str]) -> int:
        seen.append(argv)
        return 1

    monkeypatch.setattr(ledger, "main", fake_main)
    out = tmp_path / "out"
    assert run_plan([step("s1")], out, 100.0, lambda s, d: 0) == 1
    assert seen == [
        ["--out-dir", str(out), "--stage", "s1", "--run", "repeat 1",
         "--newest", str(out / "logs" / "B" / "s1")]
    ]  # fmt: skip


# ---------------------------------------------------------------- command


def test_build_command_is_an_argument_list_with_the_task_args_and_seed(tmp_path: Path) -> None:
    s = Step("n", "B", NVIDIA, ("variant=benign",), 2, "seed 2", 10, 2)
    cmd = run_capped.build_command(s, tmp_path / "logs", tmp_path / ".env")
    assert cmd[:4] == ["uv", "run", "--env-file", str(tmp_path / ".env")]
    assert cmd[cmd.index("--model") + 1] == NVIDIA
    assert cmd[cmd.index("--max-connections") + 1] == "2"
    assert cmd[cmd.index("-T") + 1] == "variant=benign"
    assert cmd[-2:] == ["--seed", "2"]
    assert cmd[cmd.index("--log-dir") + 1] == str((tmp_path / "logs").resolve())


def test_build_command_omits_the_seed_when_none(tmp_path: Path) -> None:
    cmd = run_capped.build_command(step("x"), tmp_path, tmp_path / ".env")
    assert "--seed" not in cmd


# ---------------------------------------------------------------- CLI


def test_dry_run_prints_the_table_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "out"
    assert run_capped.main(["--cap", "15", "--dry-run", "--out-dir", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "cap 15.0000" in printed
    assert "claude-opus-5-5" in printed
    assert not out.exists()


# ---------------------------------------------------------------- ledger --out-dir


def fake_summary(log_path: Path) -> dict[str, Any]:
    return {
        "log_path": str(log_path),
        "variant": "pictogram",
        "log_sha256": "abc",
        "status": "success",
        "model": SONNET,
        "samples": 10,
        "epochs": 1,
        "seed": None,
        "tokens": {"input": 1, "cache_write": 2, "cache_read": 3, "output": 4, "reasoning": 0},
        "cost": 0.25,
        "image_channels": ["tool_native"],
        "sample_errors": 0,
        "missing_scores": 0,
        "benign_utility": None,
        "benign_n": 0,
        "model_requests": 1,
        "peak_requests_per_minute": 1,
    }


def test_ledger_out_dir_writes_there_and_not_to_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    default = tmp_path / "default"
    monkeypatch.setattr(ledger, "OUT_DIR", default)
    monkeypatch.setattr(ledger, "LEDGER_JSONL", default / "ledger.jsonl")
    monkeypatch.setattr(ledger, "LEDGER_MD", default / "LEDGER.md")
    monkeypatch.setattr(ledger, "summarize", fake_summary)
    log = tmp_path / "x.eval"
    log.write_text("fake")
    target = tmp_path / "new" / "folder"
    code = ledger.main(["--out-dir", str(target), "--stage", "S", "--run", "repeat 1", str(log)])
    assert code == 0
    rows = [json.loads(line) for line in (target / "ledger.jsonl").read_text().splitlines()]
    assert [r["stage"] for r in rows] == ["S"]
    assert (target / "LEDGER.md").read_text().startswith("| S | ")
    assert not default.exists()
    assert ledger.read_rows(target) == rows
    # The same log is refused in the same folder, and accepted in another one.
    assert ledger.main(["--out-dir", str(target), "--stage", "S", "--run", "r", str(log)]) == 1
    assert (
        ledger.main(["--out-dir", str(tmp_path / "b"), "--stage", "S", "--run", "r", str(log)]) == 0
    )

"""S1 plan step 3h: the panel runner (scripts/v2/panel_s1.py).

The executor is injected, so these tests drive the runner's control flow without any model
call: the job plan per prereg S1, the exact eval command, the child environment, the stop
on the first red gate with no retry, skipping work already priced, and the refusals.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evals import tools_v2
from scripts.v2 import panel_s1, s1_panel


def ids(job: panel_s1.Job) -> list[str]:
    return list(job.sample_ids or [])


# ---- job plan ----

def test_smoke_plan_runs_retiring_models_first_then_cells() -> None:
    jobs = panel_s1.plan_jobs("smoke")
    assert [j.model for j in jobs[:3]] == list(s1_panel.PANEL[:3])
    assert [j.cell for j in jobs] == ["main"] * 13 + list(s1_panel.CONTRAST_CELLS)
    main = jobs[0]
    assert (main.arm, main.epochs, main.samples) == ("both", 1, 6)
    assert ids(main) == [f"TL-01-v2-t00{i}:{a}" for i in (1, 2, 3) for a in ("P", "C")]
    cell = jobs[-1]
    contrast = {str(s.id) for s in tools_v2.dataset_for("poisoned", subset="contrast50")}
    assert (cell.arm, cell.subset, cell.samples) == ("poisoned", "contrast50", 3)
    assert set(ids(cell)) <= contrast and len(ids(cell)) == 3


def test_main_plan_follows_the_preregistration() -> None:
    jobs = panel_s1.plan_jobs("main")
    per_model: dict[tuple[str, str], int] = {}
    for j in jobs:
        per_model[(j.cell, j.model)] = per_model.get((j.cell, j.model), 0) + j.samples
        assert j.sample_ids is None
    for m in s1_panel.PANEL:
        arms = {(j.arm, j.epochs) for j in jobs if j.cell == "main" and j.model == m}
        assert arms == {("poisoned", 3), ("clean", 1)}, m
        assert per_model[("main", m)] == 320
    for name, cell in s1_panel.CONTRAST_CELLS.items():
        [j] = [j for j in jobs if j.cell == name]
        assert (j.model, j.arm, j.subset, j.epochs, j.samples) == (
            cell.model, "poisoned", "contrast50", 3, 150)


# ---- command and environment ----

def command(model: str, cell: str = "main", phase: str = "smoke") -> list[str]:
    [job] = [j for j in panel_s1.plan_jobs(phase) if j.model == model and j.cell == cell][:1]
    return panel_s1.eval_command(job, Path("/repo"), cost_limit=0.5)


def test_eval_command_shape() -> None:
    cmd = command("claude-opus-4-8")
    assert cmd[1:3] == ["eval", "evals/tools_v2.py@tools_tl01_v2"]
    for flag in ("--log-model-api", "--model-cost-config", "--cost-limit", "--epochs",
                 "--message-limit", "--token-limit", "--log-dir"):
        assert flag in cmd, flag
    assert cmd[cmd.index("--model") + 1] == "anthropic/claude-opus-4-8"
    assert cmd[cmd.index("--model-cost-config") + 1] == str(s1_panel.INSPECT_COSTS)
    for banned in ("--batch", "--fallback-models", "--temperature", "--top-p", "--top-k",
                   "--seed", "--reasoning-effort", "--reasoning-tokens"):
        assert banned not in cmd, banned


def test_model_config_only_where_the_policy_pins_args() -> None:
    assert "--model-config" not in command("claude-opus-4-8")
    on = command("claude-sonnet-5-5")
    assert on[on.index("--model-config") + 1] == str(
        s1_panel.MODEL_ARGS_DIR / "claude-sonnet-5-5.yaml")
    cell = command("claude-haiku-5-5", cell="haiku55_off")
    assert cell[cell.index("--model-config") + 1] == str(
        s1_panel.MODEL_ARGS_DIR / "cells" / "haiku55_off.yaml")
    assert "subset=contrast50" in cell


def test_child_env_strips_inspect_overrides() -> None:
    env = panel_s1.child_env({"PATH": "/bin", "ANTHROPIC_API_KEY": "k", "PYTHONPATH": "/x",
                              "INSPECT_EVAL_MODEL_ARGS": "extra_body=1",
                              "INSPECT_EVAL_MODEL_CONFIG": "x.yaml", "INSPECT_LOG_DIR": "/y"})
    assert env["ANTHROPIC_API_KEY"] == "k" and env["CONFIRM_HIGH_RISK"] == "1"
    assert not [k for k in env if k.startswith("INSPECT_") or k == "PYTHONPATH"]


# ---- control flow with an injected executor ----

class Fake:
    """Records commands; makes inspect write a log; returns preset codes per tool."""

    def __init__(self, codes: dict[str, list[int]] | None = None) -> None:
        self.codes = codes or {}
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], cwd: Path, out_file: Path, env: dict[str, str],
                 timeout: int) -> int | None:
        self.calls.append(cmd)
        kind = self.kind(cmd)
        if kind == "eval":
            log_dir = Path(cmd[cmd.index("--log-dir") + 1])
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / f"run{len(self.calls)}.eval").write_text("log")
        out_file.write_text(kind)
        queue = self.codes.get(kind, [])
        return queue.pop(0) if queue else 0

    @staticmethod
    def kind(cmd: list[str]) -> str:
        joined = " ".join(cmd)
        if "gates_s1.py" in joined:
            return "gates_s1.py pre" if "pre" in cmd else "gates_s1.py post"
        for name in ("cost.py", "describe.py", "risk_check"):
            if name in joined:
                return name
        return "eval" if "@tools_tl01_v2" in joined else "other"

    def count(self, kind: str) -> int:
        return sum(1 for c in self.calls if self.kind(c) == kind)


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    data = tmp_path / "data"
    data.mkdir()
    (data / "setup.json").write_text(json.dumps({"setup_sha": "0" * 40,
                                                  "scorer_sha256": {"x": "y"}}))
    monkeypatch.setenv("CONFIRM_HIGH_RISK", "1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "offline")
    monkeypatch.setattr(panel_s1, "repo_ok", lambda repo, setup: (True, "ok"))
    return {"data": data, "repo": tmp_path / "repo"}


def runner(env: dict[str, Any], fake: Fake) -> panel_s1.Runner:
    return panel_s1.Runner(env["repo"], env["data"], execute=fake)


def test_smoke_runs_every_job_through_every_gate(env: dict[str, Any]) -> None:
    fake = Fake()
    runner(env, fake).smoke()
    assert fake.count("eval") == 17
    for kind in ("gates_s1.py pre", "gates_s1.py post", "cost.py", "describe.py"):
        assert fake.count(kind) == 17, kind


def test_first_red_post_gate_blocks_and_stops(env: dict[str, Any]) -> None:
    fake = Fake({"gates_s1.py post": [0, 1]})
    with pytest.raises(SystemExit, match="BLOCKED"):
        runner(env, fake).smoke()
    assert fake.count("eval") == 2, "nothing runs after the red gate"
    [blocked] = list((env["data"] / "runs").glob("*/BLOCKED.md"))
    assert "post gate" in blocked.read_text()


def test_failed_eval_is_never_retried(env: dict[str, Any]) -> None:
    fake = Fake({"eval": [1]})
    with pytest.raises(SystemExit, match="BLOCKED"):
        runner(env, fake).smoke()
    assert fake.count("eval") == 1
    assert fake.count("gates_s1.py post") == 0


def test_red_pre_gate_spends_nothing(env: dict[str, Any]) -> None:
    fake = Fake({"gates_s1.py pre": [1]})
    with pytest.raises(SystemExit, match="BLOCKED"):
        runner(env, fake).smoke()
    assert fake.count("eval") == 0


def test_a_priced_job_is_skipped(env: dict[str, Any]) -> None:
    first = panel_s1.plan_jobs("smoke")[0]
    log_dir = panel_s1.job_dir(env["data"], first)
    log_dir.mkdir(parents=True)
    log = log_dir / "done.eval"
    log.write_text("log")
    (env["data"] / "ledger.jsonl").write_text(json.dumps(
        {"model": first.model, "phase": "s1-smoke-main", "cost": 0.01, "samples": 6,
         "log_path": str(log.resolve()), "log_sha256": "h"}) + "\n")
    fake = Fake()
    runner(env, fake).smoke()
    assert fake.count("eval") == 16


def test_an_unpriced_log_blocks_instead_of_relaunching(env: dict[str, Any]) -> None:
    first = panel_s1.plan_jobs("smoke")[0]
    log_dir = panel_s1.job_dir(env["data"], first)
    log_dir.mkdir(parents=True)
    (log_dir / "crashed.eval").write_text("log")
    fake = Fake()
    with pytest.raises(SystemExit, match="BLOCKED"):
        runner(env, fake).smoke()
    assert fake.count("eval") == 0


def test_main_refuses_without_an_allocation(env: dict[str, Any]) -> None:
    fake = Fake()
    with pytest.raises(SystemExit, match="BLOCKED"):
        runner(env, fake).main()
    assert fake.count("eval") == 0


def test_main_uses_the_allocation_cost_per_sample(env: dict[str, Any]) -> None:
    cells: dict[str, Any] = {"main": s1_panel.PANEL}
    cells |= {n: [c.model] for n, c in s1_panel.CONTRAST_CELLS.items()}
    alloc = {cell: {m: {"cap": 9.0, "max_cost_per_sample": 0.02} for m in models}
             for cell, models in cells.items()}
    (env["data"] / "allocation.json").write_text(json.dumps(alloc))
    fake = Fake()
    runner(env, fake).main()
    assert fake.count("eval") == 13 * 2 + 4
    pre = next(c for c in fake.calls if Fake.kind(c) == "gates_s1.py pre")
    assert pre[pre.index("--est-per-sample") + 1] == "0.02"
    ev = next(c for c in fake.calls if Fake.kind(c) == "eval")
    assert ev[ev.index("--cost-limit") + 1] == "0.06"


@pytest.mark.parametrize("var", ["CONFIRM_HIGH_RISK", "ANTHROPIC_API_KEY"])
def test_preflight_refuses_a_missing_variable(env: dict[str, Any], var: str,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(var)
    fake = Fake()
    with pytest.raises(SystemExit, match="BLOCKED"):
        runner(env, fake).smoke()
    assert fake.count("eval") == 0


def test_summary_refuses_until_every_main_log_passed(env: dict[str, Any]) -> None:
    with pytest.raises(SystemExit, match="BLOCKED"):
        runner(env, Fake()).summary()


def test_main_refuses_a_job_without_its_allocation_row(env: dict[str, Any]) -> None:
    (env["data"] / "allocation.json").write_text(json.dumps({"main": {}}))
    fake = Fake()
    with pytest.raises(SystemExit, match="BLOCKED"):
        runner(env, fake).main()
    assert fake.count("eval") == 0

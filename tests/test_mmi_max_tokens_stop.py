"""A model that thinks through the whole generation cap must score incapable and not stop a run.

The local plan passes --max-tokens 2048. A model that spends the whole budget on reasoning
returns an assistant message with stop_reason "max_tokens", no text and no tool call. These
tests drive the real multimodal_injection task through Inspect eval() on mockllm, read the log
through ledger.summarize, and ask run_capped._row_problem whether the run must stop. A sample
with a real error and a sample with a missing scorer must still stop it. No network, no key.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log, write_eval_log
from inspect_ai.model import ContentReasoning, ModelOutput, get_model

from evals.multimodal_injection import four_cell_from_log, multimodal_injection
from scripts.multimodal_injection import ledger, run_capped
from scripts.multimodal_injection.run_capped import Step, run_plan

OLLAMA = run_capped.OLLAMA_MODELS[0]
STEP = Step(
    "A-test-s0", "A", OLLAMA, (), 0, "seed 0", 1, 1, 0.0, max_tokens=run_capped.LOCAL_MAX_TOKENS
)


@pytest.fixture(autouse=True)
def _mock_model_is_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real run is on Ollama, which the ledger prices at 0. mockllm has no price row."""
    monkeypatch.setattr(ledger, "FREE_PREFIXES", (*ledger.FREE_PREFIXES, "mockllm/"))


def _capped_output(reasoning: bool) -> ModelOutput:
    """An assistant message that used the whole budget: no text, no tool call."""
    content: str | list[Any] = (
        [ContentReasoning(reasoning="Let me think about the dashboard " * 50)] if reasoning else ""
    )
    return ModelOutput.from_content("mockllm/model", content, stop_reason="max_tokens")


def _run(tmp_path: Path, outputs: Any) -> Path:
    log_dir = tmp_path / "logs"
    logs = inspect_eval(
        multimodal_injection(variant="typographic"),
        model=get_model("mockllm/model", custom_outputs=outputs),
        limit=1,
        log_dir=str(log_dir),
        display="none",
        fail_on_error=False,
        retry_on_error=0,
    )
    return Path(logs[0].location)


def _ledger_row(tmp_path: Path, log: Path) -> dict[str, Any]:
    """The row run_plan reads: ledger.main prices the newest log, read_rows loads it."""
    out_dir = tmp_path / "ledger"
    args = ["--out-dir", str(out_dir), "--stage", STEP.name, "--run", STEP.run]
    assert ledger.main([*args, "--newest", str(log.parent)]) == 0
    rows = [r for r in ledger.read_rows(out_dir) if r["stage"] == STEP.name]
    assert len(rows) == 1
    return rows[0]


@pytest.mark.parametrize("reasoning", [False, True], ids=["empty_message", "reasoning_block"])
def test_a_max_tokens_stop_with_no_text_and_no_call_scores_incapable_and_does_not_stop_the_run(
    tmp_path: Path, reasoning: bool
) -> None:
    log = _run(tmp_path, [_capped_output(reasoning)])
    sample = (read_eval_log(str(log)).samples or [])[0]
    assert sample.error is None
    assert sample.output.stop_reason == "max_tokens"
    assert sample.output.completion == ""
    assert sample.scores is not None
    asr = sample.scores["mmi_asr"]
    assert asr.value == 0.0
    assert asr.metadata is not None and asr.metadata["outcome"] == "incapable_no_call"
    assert sample.scores["mmi_tr"].value == 0.0
    assert sample.scores["mmi_utility"].value == 0.0
    assert four_cell_from_log(log)[("user_fallback", "typographic")]["incapable"] == 1

    summary = ledger.summarize(log)
    assert summary["status"] == "success"
    assert summary["sample_errors"] == 0
    assert summary["missing_scores"] == 0

    row = _ledger_row(tmp_path, log)
    assert row["sample_errors"] == 0 and row["missing_scores"] == 0
    assert run_capped._row_problem(row, STEP) is None


def test_run_plan_continues_past_a_max_tokens_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """run_plan itself, with the real ledger and a fake execute that writes the real log."""
    out_dir = tmp_path / "out"
    two_steps = [STEP, Step("B-test-s0", "B", OLLAMA, (), 0, "seed 0", 1, 1, 0.0)]
    ran: list[str] = []

    def execute(step: Step, log_dir: Path) -> int:
        ran.append(step.name)
        log = _run(tmp_path / step.name, [_capped_output(True)])
        log.rename(log_dir / log.name)
        return 0

    assert run_plan(two_steps, out_dir, 0.0, execute) == 0
    assert ran == ["A-test-s0", "B-test-s0"]
    rows = ledger.read_rows(out_dir)
    assert [r["stage"] for r in rows] == ran
    assert all(r["sample_errors"] == 0 and r["missing_scores"] == 0 for r in rows)


def test_a_real_sample_error_still_stops_the_run(tmp_path: Path) -> None:
    def broken(*_: Any) -> ModelOutput:
        raise RuntimeError("the model server fell over")

    log = _run(tmp_path, broken)
    sample = (read_eval_log(str(log)).samples or [])[0]
    assert sample.error is not None
    row = _ledger_row(tmp_path, log)
    assert row["sample_errors"] == 1
    problem = run_capped._row_problem(row, STEP)
    assert problem is not None and "sample errors" in problem


def test_a_missing_scorer_still_stops_the_run(tmp_path: Path) -> None:
    log = _run(tmp_path, [_capped_output(False)])
    full = read_eval_log(str(log))
    sample = (full.samples or [])[0]
    assert sample.scores is not None
    del sample.scores["mmi_utility"]
    stripped = tmp_path / "stripped" / "no_utility.eval"
    stripped.parent.mkdir()
    write_eval_log(full, str(stripped))
    assert ledger.summarize(stripped)["missing_scores"] == 1
    row = _ledger_row(tmp_path, stripped)
    assert row["missing_scores"] == 1
    problem = run_capped._row_problem(row, STEP)
    assert problem is not None and "missing scores" in problem
    json.dumps(row)  # the row stays a plain JSON record

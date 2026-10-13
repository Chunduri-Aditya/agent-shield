"""V1_2_PLAN step 1a: the one generation TL-01 task in evals/tools_v12.py.

The task must reuse the published TL-01 inputs byte for byte (anchored 3 prompt x 20
sample design and the 10 prompt pilot set), deliver the poisoned read_file description,
send a request with no sampling or reasoning keys and tool_choice auto, refuse to build
unless the risk gate clears TL-01 (J4), and fail every sample when the run lacks
--log-model-api, since the event scorer reads the raw provider response (RR01, E32).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from inspect_ai.event import ModelEvent
from inspect_ai.log import EvalLog, read_eval_log
from inspect_ai.tool import ToolDef

from evals import tools_v12
from evals.tools import TOOL_SAMPLES_ANCHORED
from evals.tools_pilot import PILOT_SAMPLES
from tools.payloads import TL_01_POISONING_PAYLOAD

REPO = Path(__file__).resolve().parents[2]
TASK = "evals/tools_v12.py@tools_tl01_v12"
ANCHORED_IDS = [f"tl01-a{i:02d}" for i in range(20)]
PILOT_IDS = [f"TL-01-u{i:02d}" for i in range(1, 11)]
SAMPLING_AND_REASONING = (
    "temperature", "top_p", "top_k", "seed", "reasoning_effort", "reasoning_tokens",
    "reasoning_summary", "reasoning_history",
)


@pytest.fixture
def confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFIRM_HIGH_RISK", "1")


def test_anchored_design_reuses_the_published_inputs() -> None:
    samples = tools_v12.dataset_for("anchored")
    assert [s.id for s in samples] == ANCHORED_IDS
    assert [s.input for s in samples] == [s.input for s in TOOL_SAMPLES_ANCHORED]
    assert [s.metadata for s in samples] == [s.metadata for s in TOOL_SAMPLES_ANCHORED]


def test_pilot_design_reuses_the_pilot_inputs() -> None:
    samples = tools_v12.dataset_for("pilot")
    assert [s.id for s in samples] == PILOT_IDS
    assert [s.input for s in samples] == [s.input for s in PILOT_SAMPLES]


def test_unknown_design_is_refused() -> None:
    with pytest.raises(ValueError, match="design"):
        tools_v12.dataset_for("both")


def test_all_sample_ids_cover_both_designs() -> None:
    assert tools_v12.all_sample_ids() == ANCHORED_IDS + PILOT_IDS


def test_read_file_description_carries_the_directive() -> None:
    tools = {ToolDef(t).name: ToolDef(t) for t in tools_v12.task_tools()}
    assert sorted(tools) == ["add", "read_file", "send_message"]
    assert TL_01_POISONING_PAYLOAD in tools["read_file"].description


@pytest.mark.usefixtures("confirmed")
@pytest.mark.parametrize("design", ["anchored", "pilot"])
def test_task_sends_no_sampling_or_reasoning_keys(design: str) -> None:
    task = tools_v12.tools_tl01_v12(design=design)
    for key in SAMPLING_AND_REASONING:
        assert getattr(task.config, key) is None, key
    assert task.metadata == {"design": design}


@pytest.mark.usefixtures("confirmed")
def test_task_attaches_no_v1_1_scorer() -> None:
    """R7: tools_asr_scorer and tools_transparency_scorer never print a rate here."""
    task = tools_v12.tools_tl01_v12(design="pilot")
    names = [repr(s) for s in (task.scorer or [])]
    assert not any("tools_asr" in n or "tools_transparency" in n for n in names), names


def test_task_refuses_to_build_without_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONFIRM_HIGH_RISK", raising=False)
    with pytest.raises(RuntimeError, match=r"CONFIRM_HIGH_RISK|confirm"):
        tools_v12.tools_tl01_v12(design="pilot")


@pytest.mark.usefixtures("confirmed")
def test_task_refuses_to_build_when_ethics_does_not_clear_tl01(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """J4 row: TL-01 removed from a scratch ETHICS.md, the task refuses to build."""
    scratch = tmp_path / "ETHICS.md"
    scratch.write_text(
        (REPO / "ETHICS.md").read_text(encoding="utf-8").replace("TL-01", "TL-XX"),
        encoding="utf-8",
    )
    assert "TL-01" not in scratch.read_text(encoding="utf-8")
    monkeypatch.setattr(tools_v12, "ETHICS_PATH", scratch)
    with pytest.raises(RuntimeError, match="ETHICS"):
        tools_v12.tools_tl01_v12(design="pilot")


@pytest.mark.usefixtures("confirmed")
def test_task_builds_when_cleared_and_confirmed() -> None:
    task = tools_v12.tools_tl01_v12(design="anchored")
    assert len(task.dataset) == 20


def _mock_run(tmp_path: Path, design: str, *, log_model_api: bool) -> tuple[int, str, EvalLog]:
    """Run the task under the real `inspect` console script, PYTHONPATH removed."""
    inspect_bin = Path(sys.executable).with_name("inspect")
    assert inspect_bin.exists(), f"{inspect_bin} missing: the test needs the console script"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["CONFIRM_HIGH_RISK"] = "1"
    cmd = [
        str(inspect_bin), "eval", TASK, "-T", f"design={design}",
        "--model", "mockllm/model", "--limit", "1",
        "--log-dir", str(tmp_path), "--display", "plain",
    ]
    if log_model_api:
        cmd.append("--log-model-api")
    done = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, check=False)
    logs = sorted(tmp_path.glob("*.eval"))
    assert len(logs) == 1, f"expected one .eval log, found {logs}\n{done.stdout}\n{done.stderr}"
    # "full" also resolves ModelEvent.call; "core" leaves it condensed (Inspect 0.3.278).
    log = read_eval_log(str(logs[0]), resolve_attachments="full")
    return done.returncode, done.stdout + done.stderr, log


@pytest.mark.parametrize(("design", "ids"), [("anchored", ANCHORED_IDS), ("pilot", PILOT_IDS)])
def test_mock_run_with_log_model_api_delivers_the_directive(
    tmp_path: Path, design: str, ids: list[str]
) -> None:
    code, out, log = _mock_run(tmp_path, design, log_model_api=True)
    assert code == 0, out
    assert log.status == "success", out
    assert log.eval.config.log_model_api is True
    samples = log.samples or []
    assert [str(s.id) for s in samples] == ids[:1]
    sample = samples[0]
    assert sample.error is None
    events = [e for e in sample.events if isinstance(e, ModelEvent)]
    assert events, "no ModelEvent in the sample"
    read = [t for t in events[0].tools if t.name == "read_file"]
    assert len(read) == 1
    assert TL_01_POISONING_PAYLOAD in read[0].description
    assert events[0].tool_choice == "auto"
    for key in SAMPLING_AND_REASONING:
        assert getattr(events[0].config, key) is None, key


def test_mock_run_without_log_model_api_fails_every_sample(tmp_path: Path) -> None:
    code, out, log = _mock_run(tmp_path, "pilot", log_model_api=False)
    assert code != 0 or log.status != "success", out
    assert log.status == "error", out
    assert log.error is not None
    assert "--log-model-api" in log.error.message

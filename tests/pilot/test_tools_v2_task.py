"""S1 plan step 3a: the v2 TL-01 task in evals/tools_v2.py.

The poisoned arm must deliver the cleared directive byte for byte (R5, D36) and the clean
arm none of it; each sample's read_file serves only that sample's stub (with its nonce);
the task refuses a task file whose hash moved, refuses without the risk gate, sends no
sampling or reasoning keys, and needs --log-model-api like the v1.2 task.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import pytest
from inspect_ai.event import ModelEvent
from inspect_ai.log import EvalLog, read_eval_log
from inspect_ai.tool import ToolDef

from evals import tools_v2, tools_v12
from evals.tools import _READ_FILE_DESCRIPTION, read_file
from scripts.v2 import tasks_v2
from tools.payloads import TL_01_POISONING_PAYLOAD

REPO = Path(__file__).resolve().parents[2]
TASK = "evals/tools_v2.py@tools_tl01_v2"
SAMPLING_AND_REASONING = (
    "temperature", "top_p", "top_k", "seed", "reasoning_effort", "reasoning_tokens",
    "reasoning_summary", "reasoning_history",
)


@pytest.fixture
def confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFIRM_HIGH_RISK", "1")


def _tooldef(arm: str, meta: dict) -> ToolDef:
    return ToolDef(tools_v2.read_file_v2(meta["file"], meta["stub"], arm))


def test_clean_description_is_the_poisoned_one_without_the_directive() -> None:
    assert tools_v2.CLEAN_DESCRIPTION + "\n\n" + TL_01_POISONING_PAYLOAD == _READ_FILE_DESCRIPTION
    assert TL_01_POISONING_PAYLOAD not in tools_v2.CLEAN_DESCRIPTION


def test_poisoned_read_file_matches_the_v1_tool_exactly() -> None:
    meta = tools_v2.dataset_for("poisoned")[0].metadata or {}
    v2, v1 = _tooldef("poisoned", meta), ToolDef(read_file())
    assert (v2.name, v2.description) == (v1.name, v1.description)
    assert v2.parameters.model_dump() == v1.parameters.model_dump()


def test_clean_read_file_differs_only_in_description() -> None:
    meta = tools_v2.dataset_for("clean")[0].metadata or {}
    v2, v1 = _tooldef("clean", meta), ToolDef(read_file())
    assert v2.name == v1.name
    assert v2.description == tools_v2.CLEAN_DESCRIPTION
    assert v2.parameters.model_dump() == v1.parameters.model_dump()


def test_both_arms_interleave_poisoned_and_clean() -> None:
    rows = tasks_v2.load(tasks_v2.DATA)
    samples = tools_v2.dataset_for("both")
    assert [str(s.id) for s in samples] == [f"{r['id']}:{a}" for r in rows for a in ("P", "C")]
    assert {s.metadata["arm"] for s in samples} == {"poisoned", "clean"}  # type: ignore[index]


@pytest.mark.parametrize(("arm", "suffix"), [("poisoned", ":P"), ("clean", ":C")])
def test_single_arm_has_80_samples(arm: str, suffix: str) -> None:
    samples = tools_v2.dataset_for(arm)
    assert len(samples) == 80
    assert all(str(s.id).endswith(suffix) for s in samples)


def test_unknown_arm_is_refused() -> None:
    with pytest.raises(ValueError, match="arm"):
        tools_v2.dataset_for("mixed")


def test_contrast_subset_is_50_seeded_poisoned_tasks() -> None:
    a = tools_v2.dataset_for("poisoned", subset="contrast50")
    b = tools_v2.dataset_for("poisoned", subset="contrast50")
    ids = [str(s.id) for s in a]
    assert ids == [str(s.id) for s in b]
    assert len(ids) == len(set(ids)) == 50
    order = [str(s.id) for s in tools_v2.dataset_for("poisoned")]
    assert ids == [i for i in order if i in set(ids)], "subset keeps file order"
    assert ids != order[:50], "subset is a seeded draw, not the first 50"


def test_contrast_subset_refuses_the_clean_arm() -> None:
    with pytest.raises(ValueError, match="contrast50"):
        tools_v2.dataset_for("both", subset="contrast50")


def test_metadata_carries_the_stub_with_its_nonce() -> None:
    rows = {r["id"]: r for r in tasks_v2.load(tasks_v2.DATA)}
    for s in tools_v2.dataset_for("both"):
        meta = s.metadata or {}
        row = rows[meta["task_id"]]
        assert meta["stub"] == "\n".join([*row["lines"], f"Ref: {row['nonce']}"])
        assert meta["nonce"] == row["nonce"]
        assert s.input == row["prompt"]
        assert s.target == row["expected_answer"]


def _call(tool_def: ToolDef, path: str) -> str:
    return str(asyncio.run(tool_def.tool(path=path)))


def test_stub_is_served_only_for_its_own_file() -> None:
    samples = tools_v2.dataset_for("poisoned")
    m0, m1 = samples[0].metadata or {}, samples[1].metadata or {}
    t0 = _tooldef("poisoned", m0)
    assert _call(t0, m0["file"]) == m0["stub"]
    assert _call(t0, "/" + m0["file"]) == m0["stub"]
    assert _call(t0, m1["file"]) == f"[stub] contents of {m1['file']}"
    assert m1["nonce"] not in _call(t0, m1["file"])


def test_dataset_refuses_a_moved_hash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    tampered = tmp_path / "tasks.jsonl"
    tampered.write_text(tasks_v2.DATA.read_text().replace("Ref", "Ref", 1) + "\n")
    monkeypatch.setattr(tasks_v2, "DATA", tampered)
    with pytest.raises(RuntimeError, match="sha256"):
        tools_v2.dataset_for("both")


def test_all_sample_ids_cover_both_arms() -> None:
    assert tools_v2.all_sample_ids() == [str(s.id) for s in tools_v2.dataset_for("both")]


@pytest.mark.usefixtures("confirmed")
def test_task_sends_no_sampling_or_reasoning_keys() -> None:
    task = tools_v2.tools_tl01_v2(arm="both")
    for key in SAMPLING_AND_REASONING:
        assert getattr(task.config, key) is None, key
    assert task.metadata == {"arm": "both", "subset": "all",
                             "dataset_sha256": tasks_v2.sha256_file(tasks_v2.DATA)}


def test_task_refuses_to_build_without_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CONFIRM_HIGH_RISK", raising=False)
    with pytest.raises(RuntimeError, match=r"CONFIRM_HIGH_RISK|confirm"):
        tools_v2.tools_tl01_v2(arm="both")


@pytest.mark.usefixtures("confirmed")
def test_task_refuses_when_ethics_does_not_clear_tl01(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    scratch = tmp_path / "ETHICS.md"
    scratch.write_text((REPO / "ETHICS.md").read_text().replace("TL-01", "TL-XX"))
    monkeypatch.setattr(tools_v12, "ETHICS_PATH", scratch)
    with pytest.raises(RuntimeError, match="ETHICS"):
        tools_v2.tools_tl01_v2(arm="both")


def _mock_run(tmp_path: Path, *, log_model_api: bool, limit: int = 2) -> tuple[int, str, EvalLog]:
    inspect_bin = Path(sys.executable).with_name("inspect")
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["CONFIRM_HIGH_RISK"] = "1"
    cmd = [str(inspect_bin), "eval", TASK, "-T", "arm=both", "--model", "mockllm/model",
           "--limit", str(limit), "--log-dir", str(tmp_path), "--display", "plain"]
    if log_model_api:
        cmd.append("--log-model-api")
    done = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, check=False)
    logs = sorted(tmp_path.glob("*.eval"))
    assert len(logs) == 1, f"expected one .eval log, found {logs}\n{done.stdout}\n{done.stderr}"
    return done.returncode, done.stdout + done.stderr, read_eval_log(
        str(logs[0]), resolve_attachments="full")


def test_mock_run_delivers_the_directive_on_poisoned_samples_only(tmp_path: Path) -> None:
    code, out, log = _mock_run(tmp_path, log_model_api=True)
    assert code == 0, out
    assert log.status == "success", out
    samples = {str(s.id): s for s in log.samples or []}
    assert sorted(samples) == ["TL-01-v2-t001:C", "TL-01-v2-t001:P"]
    for sid, delivered in (("TL-01-v2-t001:P", True), ("TL-01-v2-t001:C", False)):
        events = [e for e in samples[sid].events if isinstance(e, ModelEvent)]
        assert events, sid
        read = [t for t in events[0].tools if t.name == "read_file"]
        assert len(read) == 1, sid
        assert (TL_01_POISONING_PAYLOAD in read[0].description) is delivered, sid
        assert sorted(t.name for t in events[0].tools) == ["add", "read_file", "send_message"]
        assert events[0].tool_choice == "auto"
        for key in SAMPLING_AND_REASONING:
            assert getattr(events[0].config, key) is None, key


def test_mock_run_without_log_model_api_fails(tmp_path: Path) -> None:
    _code, out, log = _mock_run(tmp_path, log_model_api=False, limit=1)
    assert log.status == "error", out
    assert log.error is not None
    assert "--log-model-api" in log.error.message

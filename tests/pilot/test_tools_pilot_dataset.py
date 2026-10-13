"""The pilot TL-01 task set: ten distinct benign tasks around the unchanged poisoned tool."""
from __future__ import annotations

import asyncio

from inspect_ai.tool import ToolDef

from evals.tools import (
    _FILE_PROMPTS,
    _READ_FILE_DESCRIPTION,
    read_file,
    tools_asr_scorer,
    tools_transparency_scorer,
)
from evals.tools_pilot import PILOT_SAMPLES, tools_pilot
from tools.payloads import TL_01_POISONING_PAYLOAD

EXPECTED_IDS = [f"TL-01-u{i:02d}" for i in range(1, 11)]


def test_ten_samples_with_the_pilot_ids_in_order() -> None:
    assert [s.id for s in PILOT_SAMPLES] == EXPECTED_IDS


def test_every_user_task_is_distinct() -> None:
    inputs = [s.input for s in PILOT_SAMPLES]
    assert len(set(inputs)) == 10


def test_first_three_tasks_are_the_original_prompts_byte_for_byte() -> None:
    by_file = {s.metadata["file"]: s.input for s in PILOT_SAMPLES[:3]}
    assert by_file == _FILE_PROMPTS


def test_metadata_records_attack_and_expected_benign_outcome() -> None:
    for s in PILOT_SAMPLES:
        assert s.metadata["attack"] == "TL-01"
        assert s.metadata["expected_benign_outcome"].strip()
        assert s.metadata["expected_answer"].strip()


def test_expected_answer_is_in_the_stub_file_the_task_reads() -> None:
    tool = read_file()
    for s in PILOT_SAMPLES:
        contents = asyncio.run(tool(path=s.metadata["file"]))
        assert isinstance(contents, str)
        assert not contents.startswith("[stub]"), s.id
        assert s.metadata["expected_answer"] in contents, s.id


def test_task_sends_the_unchanged_poisoned_description() -> None:
    task = tools_pilot()
    assert len(task.dataset) == 10
    description = ToolDef(read_file()).description
    assert description == _READ_FILE_DESCRIPTION
    assert TL_01_POISONING_PAYLOAD in description


def test_task_scores_asr_and_tr_on_one_generation_with_the_existing_scorers() -> None:
    task = tools_pilot()
    names = sorted(getattr(s, "__qualname__", repr(s)) for s in task.scorer)
    expected = sorted(
        getattr(s, "__qualname__", repr(s))
        for s in (tools_asr_scorer(), tools_transparency_scorer())
    )
    assert len(task.scorer) == 2
    assert names == expected

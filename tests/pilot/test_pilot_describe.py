"""describe.py: P, m and n_eff bounds on repeated identical completions; never reads grading."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from inspect_ai.model import ChatMessage, ChatMessageAssistant, ChatMessageUser
from inspect_ai.tool import ToolCall

from scripts.pilot import describe
from tests.pilot.pilot_helpers import eval_log, sample, write_log

REPO = Path(__file__).resolve().parents[2]
DESCRIBE_PY = REPO / "scripts" / "pilot" / "describe.py"


def calls_then(text: str, paths: list[str]) -> list[ChatMessage]:
    msgs: list[ChatMessage] = [ChatMessageUser(content="go")]
    for i, p in enumerate(paths):
        msgs.append(ChatMessageAssistant(
            content="",
            tool_calls=[ToolCall(id=f"c{i}", function="read_file", arguments={"path": p})],
        ))
    msgs.append(ChatMessageAssistant(content=text))
    return msgs


def fixture(tmp_path: Path) -> Path:
    samples = [
        # id A: three epochs, all identical, so one distinct completion
        *[sample("A", e, messages=calls_then("same", ["a.txt"])) for e in (1, 2, 3)],
        # id B: two epochs, same text but different tool arguments, so two distinct
        sample("B", 1, messages=calls_then("same", ["a.txt"])),
        sample("B", 2, messages=calls_then("same", ["b.txt", "c.txt"])),
    ]
    return write_log(tmp_path / "d.eval", eval_log(samples))


def test_bounds_on_repeated_completions(tmp_path: Path) -> None:
    info = describe.describe(fixture(tmp_path))
    assert info.P == 2
    assert (info.m_min, info.m_max) == (2, 3)
    assert info.n_eff_lower == 2
    assert info.n_eff_upper == 3
    assert info.per_id == {"A": (3, 1), "B": (2, 2)}
    assert info.tool_calls == {1: 4, 2: 1}
    assert info.samples == 5


def test_final_text_alone_separates_completions(tmp_path: Path) -> None:
    samples = [sample("A", 1, final_text="yes"), sample("A", 2, final_text="no")]
    info = describe.describe(write_log(tmp_path / "t.eval", eval_log(samples)))
    assert info.n_eff_upper == 2


def test_cli_prints_tables(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    done = subprocess.run(
        [sys.executable, str(DESCRIBE_PY), "--data", str(data), "--log", str(fixture(tmp_path))],
        capture_output=True, text=True, check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "n_eff lower bound = 2   upper bound = 3" in done.stdout


def test_source_never_mentions_grading() -> None:
    source = DESCRIBE_PY.read_text()
    assert not re.search("score", source, re.IGNORECASE)


def test_tool_arguments_alone_separate_completions(tmp_path: Path) -> None:
    samples = [
        sample("A", 1, messages=calls_then("same", ["a.txt"])),
        sample("A", 2, messages=calls_then("same", ["b.txt"])),
    ]
    info = describe.describe(write_log(tmp_path / "args.eval", eval_log(samples)))
    assert info.per_id == {"A": (2, 2)}

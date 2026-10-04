"""The twin provider (`--model twin/clean`): one `twin shield turn` per generate call, against a
fake twin script, so no brain, network or twin checkout is needed."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from inspect_ai.model import ChatMessage, ChatMessageSystem, ChatMessageUser, GenerateConfig
from inspect_ai.tool import ToolInfo

from agent_shield_providers.twin_api import TwinAPI, seen

FAKE = """
import json, sys
argv = sys.argv[1:]
message = sys.stdin.read()
record = {"argv": argv, "message": message}
open(sys.argv[0] + ".calls", "a").write(json.dumps(record) + "\\n")
if "HOLD" in message:
    out = {"profile": "clean", "reply": None, "held": True,
           "reasons": ["Held: the web answer carried instructions aimed at twin"], "cost_usd": 0.02}
else:
    out = {"profile": "clean", "reply": "twin saw: " + message[-20:], "held": False,
           "reasons": [], "cost_usd": 0.02}
print(json.dumps(out))
"""


@pytest.fixture
def fake_twin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    script = tmp_path / "fake_twin.py"
    script.write_text(FAKE)
    monkeypatch.setenv("TWIN_CMD", f"{sys.executable} {script}")
    monkeypatch.setenv("TWIN_SCRATCH", str(tmp_path / "scratch"))
    monkeypatch.delenv("TWIN_DIR", raising=False)
    return script


def _calls(script: Path) -> list[dict[str, object]]:
    path = Path(str(script) + ".calls")
    return [json.loads(line) for line in path.read_text().splitlines()]


def _generate(api: TwinAPI, *messages: str, tools: list[ToolInfo] | None = None) -> str:
    chat: list[ChatMessage] = [ChatMessageSystem(content=messages[0])]
    chat += [ChatMessageUser(content=m) for m in messages[1:]]
    out = asyncio.run(api.generate(chat, tools or [], "none", GenerateConfig()))
    return out.completion


def test_one_generate_is_one_clean_turn_with_the_messages_flattened(fake_twin: Path) -> None:
    api = TwinAPI("clean")
    text = _generate(api, "You are a helpful agent.", "Summarize this page please.")
    assert text.startswith("twin saw: ") and text.endswith("this page please.")
    (call,) = _calls(fake_twin)
    argv = call["argv"]
    assert isinstance(argv, list) and argv[:2] == ["shield", "turn"] and "--lead" not in argv
    assert "--ledger" in argv and "--sessions-dir" in argv
    assert call["message"] == "You are a helpful agent.\n\nSummarize this page please."


def test_a_held_turn_reads_as_what_the_owner_sees(fake_twin: Path) -> None:
    text = _generate(TwinAPI("clean"), "system", "HOLD this")
    assert text.startswith("Held:") and "instructions aimed at twin" in text


def test_lead_is_passed_only_when_asked(fake_twin: Path) -> None:
    _generate(TwinAPI("clean", lead=True), "system", "hello")
    assert "--lead" in _calls(fake_twin)[-1]["argv"]  # type: ignore[operator]


def test_only_the_clean_profile_and_no_tools(fake_twin: Path) -> None:
    with pytest.raises(ValueError, match="clean profile"):
        TwinAPI("personal")
    tool = ToolInfo(name="send", description="send mail")
    with pytest.raises(ValueError, match="no Inspect tools"):
        _generate(TwinAPI("clean"), "system", "hi", tools=[tool])


def test_the_scratch_ledger_cap_stops_further_turns(fake_twin: Path) -> None:
    api = TwinAPI("clean", max_usd=0.03)
    _generate(api, "system", "one")
    _generate(api, "system", "two")  # 0.04 spent after this one
    with pytest.raises(RuntimeError, match="max_usd"):
        _generate(api, "system", "three")
    assert len(_calls(fake_twin)) == 2


def test_twin_dir_or_a_fake_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TWIN_CMD", raising=False)
    monkeypatch.delenv("TWIN_DIR", raising=False)
    with pytest.raises(ValueError, match="TWIN_DIR"):
        TwinAPI("clean")


def test_seen_falls_back_to_refusal_then_error() -> None:
    assert seen({"refused": "message is empty"}) == "Refused: message is empty"
    assert seen({"error": "the lead ran out of time"}) == "Error: the lead ran out of time"

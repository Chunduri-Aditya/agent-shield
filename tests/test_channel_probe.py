"""Tests of scripts/multimodal_injection/channel_probe.py. mockllm only: no network, no key."""

import asyncio
import json
from pathlib import Path

from inspect_ai.model import ChatMessageAssistant, ChatMessageTool, get_model
from inspect_ai.tool import ContentImage

from scripts.multimodal_injection import channel_probe
from scripts.multimodal_injection.channel_probe import (
    DEFAULT_MODELS,
    main,
    probe_messages,
    probe_row,
    render_table,
    round_trip,
)


def test_default_models_in_the_agreed_order():
    assert DEFAULT_MODELS == (
        "ollama/qwen3-vl:8b",
        "ollama/gemma4:12b",
        "openai-api/nvidia/nvidia/nemotron-3.5-super-vl-120b-a12b",
        "openrouter/google/gemma-4-26b-a4b-it:free",
    )


def test_the_nvidia_row_is_the_overnight_route():
    records = Path(__file__).resolve().parents[1] / "results/multimodal_injection/records.jsonl"
    overnight = {json.loads(line)["model"] for line in records.read_text().splitlines()}
    nvidia = [m for m in DEFAULT_MODELS if "/nvidia/" in m]
    assert nvidia and set(nvidia) <= overnight


def test_an_nvidia_key_is_cut_from_an_error():
    assert "nvapi-" not in channel_probe._clean("401 for nvapi-abcdefgh12345678", 160)


def test_probe_input_is_user_assistant_call_and_a_tool_message_with_an_image():
    _user, assistant, tool = probe_messages()
    assert isinstance(assistant, ChatMessageAssistant)
    assert assistant.tool_calls and assistant.tool_calls[0].function == "fetch_image"
    assert assistant.tool_calls[0].id == "probe_1" and assistant.tool_calls[0].arguments == {}
    assert isinstance(tool, ChatMessageTool) and tool.tool_call_id == "probe_1"
    assert isinstance(tool.content, list)
    assert sum(isinstance(c, ContentImage) for c in tool.content) == 1


def test_round_trip_is_ok_on_mockllm_with_one_generate_call():
    model = get_model("mockllm/model")
    calls: list[int] = []
    original = model.generate

    async def counting(*args, **kwargs):
        calls.append(1)
        return await original(*args, **kwargs)

    model.generate = counting  # type: ignore[method-assign]
    result = asyncio.run(round_trip(model))
    assert result.startswith("ok stop: ")
    assert len(calls) == 1


def test_round_trip_reports_the_exception_class_when_generate_raises():
    model = get_model("mockllm/model")

    async def boom(*args, **kwargs):
        raise ConnectionError("no route sk-abcdefgh12345678 " + "x" * 400)

    model.generate = boom  # type: ignore[method-assign]
    result = asyncio.run(round_trip(model))
    assert result.startswith("error ConnectionError: no route")
    assert "sk-abcdefgh" not in result
    assert len(result) <= len("error ConnectionError: ") + 160


def test_a_bad_model_id_gives_an_error_row_and_the_table_still_exits_zero(capsys):
    row = probe_row("nosuchprovider/x")
    assert row[1] == "nosuchprovider" and row[4].startswith("error ")
    assert main(["nosuchprovider/x", "mockllm/model"]) == 0
    out = capsys.readouterr().out
    assert out.count("\n| ") == 2  # after the header: one error row, one ok row
    assert "| mockllm/model | MockLLM | False | user_fallback | ok stop:" in out


def test_table_cells_cannot_break_the_row():
    table = render_table([("a|b", "p", "True", "tool_native", "error E: x\ny")])
    assert table.splitlines()[2].count("|") == 6
    assert channel_probe.DEFAULT_MODELS

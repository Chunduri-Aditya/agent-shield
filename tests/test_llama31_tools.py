"""Contract tests for the pure Llama 3.1 tool layer in agent_shield_providers.llama31.

CI runs these on ubuntu, so nothing here imports mlx, mlx_lm, or transformers.
The read_file description carries the TL-01 directive; T1 compares descriptions
through a boolean so a failing assert never prints that text.
"""

from typing import Any

from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
)
from inspect_ai.tool import ToolCall, ToolCallError, ToolDef, ToolInfo

from agent_shield_providers.llama31 import (
    parse_llama31_tool_calls,
    to_template_messages,
    tools_to_template,
)
from evals.tools import read_file, send_message

READ_NOTES = '{"name": "read_file", "parameters": {"path": "notes.txt"}}'
SEND_HI = '{"name": "send_message", "parameters": {"to": "alice@example.com", "body": "hi"}}'


def _info(tool_def: ToolDef) -> ToolInfo:
    return ToolInfo(
        name=tool_def.name, description=tool_def.description, parameters=tool_def.parameters
    )


def _tools() -> list[ToolInfo]:
    return [_info(ToolDef(read_file())), _info(ToolDef(send_message()))]


def _call_entry(call_id: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }


# ---------------------------------------------------------------------------
# A. parse_llama31_tool_calls
# ---------------------------------------------------------------------------


def test_p1_meta_parameters_call() -> None:
    content, calls = parse_llama31_tool_calls(READ_NOTES, _tools())

    assert content == ""
    assert len(calls) == 1
    assert calls[0].function == "read_file"
    assert calls[0].arguments == {"path": "notes.txt"}
    assert calls[0].parse_error is None


def test_p2_python_tag_prefix_and_trailing_eom_id() -> None:
    text = f"<|python_tag|>{READ_NOTES}<|eom_id|>"

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == ""
    assert len(calls) == 1
    assert calls[0].function == "read_file"
    assert calls[0].arguments == {"path": "notes.txt"}
    assert calls[0].parse_error is None


def test_p3_arguments_key() -> None:
    text = '{"name": "send_message", "arguments": {"to": "alice@example.com", "body": "hi"}}'

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == ""
    assert len(calls) == 1
    assert calls[0].function == "send_message"
    assert calls[0].arguments == {"to": "alice@example.com", "body": "hi"}
    assert calls[0].parse_error is None


def test_p4_braces_and_escaped_quotes_inside_string_value() -> None:
    # The body holds an unbalanced brace pair, an escaped quote next to a brace, and
    # a trailing escaped backslash; the call is followed by prose so the span must end
    # exactly at the closing brace of the object.
    text = (
        '{"name": "send_message", "parameters": {"to": "bob@example.com", '
        r'"body": "a } b { c \"}\" d \\"}} ok'
    )

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == "ok"
    assert len(calls) == 1
    assert calls[0].function == "send_message"
    assert calls[0].arguments == {"to": "bob@example.com", "body": 'a } b { c "}" d \\'}
    assert calls[0].parse_error is None


def test_p5_two_calls_distinct_ids() -> None:
    text = f"{READ_NOTES}\n{SEND_HI}"

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == ""
    assert [call.function for call in calls] == ["read_file", "send_message"]
    assert calls[0].arguments == {"path": "notes.txt"}
    assert calls[1].arguments == {"to": "alice@example.com", "body": "hi"}
    assert [call.parse_error for call in calls] == [None, None]
    assert calls[0].id != calls[1].id


def test_p6_truncated_send_message_keeps_name_with_parse_error() -> None:
    text = '{"name": "send_message", "parameters": {"to": "bob@example.com", "body": "hel'

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == ""
    assert len(calls) == 1
    assert calls[0].function == "send_message"
    assert calls[0].arguments == {}
    assert calls[0].parse_error is not None


def test_p7_well_formed_unknown_tool_has_no_parse_error() -> None:
    text = '{"name": "get_weather", "parameters": {"city": "Paris"}}'

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == ""
    assert len(calls) == 1
    assert calls[0].function == "get_weather"
    assert calls[0].arguments == {"city": "Paris"}
    assert calls[0].parse_error is None


def test_p8_prose_with_braces_and_no_name_gives_no_call() -> None:
    text = 'My name is {Sam}; config is {"path": "notes.txt"}.'

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert calls == []
    assert content == text


def test_p9_text_before_call_becomes_content() -> None:
    text = f"Let me read that file.\n{READ_NOTES}"

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == "Let me read that file."
    assert len(calls) == 1
    assert calls[0].function == "read_file"
    assert calls[0].arguments == {"path": "notes.txt"}
    assert calls[0].parse_error is None


def test_p10_parameters_as_list_gives_parse_error() -> None:
    text = '{"name": "read_file", "parameters": ["notes.txt"]}'

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == ""
    assert len(calls) == 1
    assert calls[0].function == "read_file"
    assert calls[0].arguments == {}
    assert calls[0].parse_error is not None


def test_p11_impossible_date_string_parameters_sets_parse_error() -> None:
    # Inspect's YAML branch raises ValueError on an impossible date; the parser must
    # record it rather than let one model output error the whole sample.
    text = '{"name": "read_file", "parameters": "2024-02-30"}'

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == ""
    assert len(calls) == 1
    assert calls[0].function == "read_file"
    assert calls[0].arguments == {}
    assert calls[0].parse_error is not None


def test_p12_deeply_nested_parameters_sets_parse_error() -> None:
    depth = 5000
    text = '{"name": "read_file", "parameters": ' + "[" * depth + "]" * depth + "}"

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == ""
    assert len(calls) == 1
    assert calls[0].function == "read_file"
    assert calls[0].parse_error is not None


def test_p13_prose_json_without_parameters_is_not_a_call() -> None:
    text = 'The contact record is {"name": "Alice", "email": "a@x.com"}. Done.'

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert calls == []
    assert content == text


def test_p14_parameters_wins_over_arguments() -> None:
    text = (
        '{"name": "read_file", "parameters": {"path": "notes.txt"}, '
        '"arguments": {"path": "other.txt"}}'
    )

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == ""
    assert len(calls) == 1
    assert calls[0].arguments == {"path": "notes.txt"}
    assert calls[0].parse_error is None


def test_p15_parameters_as_plain_string_maps_to_first_parameter() -> None:
    text = '{"name": "read_file", "parameters": "notes.txt"}'

    content, calls = parse_llama31_tool_calls(text, _tools())

    assert content == ""
    assert len(calls) == 1
    assert calls[0].arguments == {"path": "notes.txt"}
    assert calls[0].parse_error is None


# ---------------------------------------------------------------------------
# B. to_template_messages
# ---------------------------------------------------------------------------


def test_m1_single_call_round_trip() -> None:
    call = ToolCall(id="call_1", function="read_file", arguments={"path": "notes.txt"})
    messages: list[ChatMessage] = [
        ChatMessageSystem(content="You are a helpful assistant."),
        ChatMessageUser(content="Read notes.txt"),
        ChatMessageAssistant(content="", tool_calls=[call]),
        ChatMessageTool(content="meeting at noon", tool_call_id="call_1", function="read_file"),
    ]

    assert to_template_messages(messages) == [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Read notes.txt"},
        _call_entry("call_1", "read_file", {"path": "notes.txt"}),
        {"role": "tool", "tool_call_id": "call_1", "content": "meeting at noon"},
    ]


def test_m2_two_calls_with_reversed_results_interleave() -> None:
    first = ToolCall(id="call_a", function="read_file", arguments={"path": "a.txt"})
    second = ToolCall(id="call_b", function="read_file", arguments={"path": "b.txt"})
    messages: list[ChatMessage] = [
        ChatMessageUser(content="Read both files."),
        ChatMessageAssistant(content="", tool_calls=[first, second]),
        ChatMessageTool(content="B contents", tool_call_id="call_b", function="read_file"),
        ChatMessageTool(content="A contents", tool_call_id="call_a", function="read_file"),
        ChatMessageAssistant(content="Both read."),
    ]

    assert to_template_messages(messages) == [
        {"role": "user", "content": "Read both files."},
        _call_entry("call_a", "read_file", {"path": "a.txt"}),
        {"role": "tool", "tool_call_id": "call_a", "content": "A contents"},
        _call_entry("call_b", "read_file", {"path": "b.txt"}),
        {"role": "tool", "tool_call_id": "call_b", "content": "B contents"},
        {"role": "assistant", "content": "Both read."},
    ]


def test_m3_assistant_text_plus_call() -> None:
    call = ToolCall(id="call_1", function="read_file", arguments={"path": "notes.txt"})
    messages: list[ChatMessage] = [
        ChatMessageAssistant(content="Checking the file.", tool_calls=[call]),
        ChatMessageTool(content="meeting at noon", tool_call_id="call_1", function="read_file"),
    ]

    assert to_template_messages(messages) == [
        {"role": "assistant", "content": "Checking the file."},
        _call_entry("call_1", "read_file", {"path": "notes.txt"}),
        {"role": "tool", "tool_call_id": "call_1", "content": "meeting at noon"},
    ]


def test_m4_tool_error_content() -> None:
    call = ToolCall(id="call_1", function="read_file", arguments={"path": "missing.txt"})
    messages: list[ChatMessage] = [
        ChatMessageAssistant(content="", tool_calls=[call]),
        # Non empty text proves the error message takes precedence over the content.
        ChatMessageTool(
            content="partial output",
            tool_call_id="call_1",
            function="read_file",
            error=ToolCallError("file_not_found", "File not found: missing.txt"),
        ),
    ]

    assert to_template_messages(messages) == [
        _call_entry("call_1", "read_file", {"path": "missing.txt"}),
        {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "Error: File not found: missing.txt",
        },
    ]


def test_m5_unmatched_tool_results_follow_matched_pair() -> None:
    call = ToolCall(id="call_1", function="read_file", arguments={"path": "notes.txt"})
    messages: list[ChatMessage] = [
        ChatMessageAssistant(content="", tool_calls=[call]),
        ChatMessageTool(content="stray", tool_call_id="call_x", function="read_file"),
        ChatMessageTool(content="meeting at noon", tool_call_id="call_1", function="read_file"),
    ]

    assert to_template_messages(messages) == [
        _call_entry("call_1", "read_file", {"path": "notes.txt"}),
        {"role": "tool", "tool_call_id": "call_1", "content": "meeting at noon"},
        {"role": "tool", "tool_call_id": "call_x", "content": "stray"},
    ]


# ---------------------------------------------------------------------------
# C. tools_to_template
# ---------------------------------------------------------------------------


def test_t1_schema_shape() -> None:
    tools = _tools()

    result = tools_to_template(tools)

    assert [entry["type"] for entry in result] == ["function", "function"]
    assert [set(entry["function"]) for entry in result] == [
        {"name", "description", "parameters"},
        {"name", "description", "parameters"},
    ]
    assert [entry["function"]["name"] for entry in result] == ["read_file", "send_message"]
    descriptions_match = [entry["function"]["description"] for entry in result] == [
        tool.description for tool in tools
    ]
    assert descriptions_match, "tool descriptions were not passed through verbatim"
    assert [entry["function"]["parameters"] for entry in result] == [
        tool.parameters.model_dump(exclude_none=True) for tool in tools
    ]
    read_params = result[0]["function"]["parameters"]
    assert set(read_params) == {"type", "properties", "required", "additionalProperties"}
    assert read_params["type"] == "object"
    assert read_params["required"] == ["path"]
    assert result[1]["function"]["parameters"]["required"] == ["to", "body"]

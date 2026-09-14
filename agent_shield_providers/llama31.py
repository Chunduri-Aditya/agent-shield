"""
Pure Llama 3.1 tool calling layer.

Llama 3.1 emits a tool call as a bare JSON object, optionally prefixed by
<|python_tag|>. This module turns that text into Inspect ToolCalls, and turns
Inspect messages and tools back into the dicts the Llama 3.1 chat template reads.
It imports no mlx, mlx_lm, or transformers, so CI can test it anywhere.
"""

import json
import re
import uuid
from typing import Any

from inspect_ai.model import ChatMessage, ChatMessageAssistant, ChatMessageTool
from inspect_ai.model._call_tools import parse_tool_call
from inspect_ai.tool import ToolCall, ToolInfo

_SPECIAL_TOKENS = ("<|python_tag|>", "<|eom_id|>", "<|eot_id|>")
_NAME_PATTERN = re.compile(r'"name"\s*:\s*"([^"\\]+)"')


def _json_object_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) of each top level brace span, ignoring braces in JSON strings."""
    spans: list[tuple[int, int]] = []
    depth = 0
    start = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if depth == 0:
            # Outside a span, quotes are prose rather than JSON strings; only `{` matters.
            if char == "{":
                start = index
                depth = 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                spans.append((start, index + 1))
    if depth > 0:
        # A `{` never closed (truncated generation) extends to the end of text.
        spans.append((start, len(text)))
    return spans


def _salvaged_call(span: str, error: str) -> ToolCall:
    """Keep a malformed call visible under its regex recovered name, or "unknown"."""
    name_match = _NAME_PATTERN.search(span)
    function = name_match.group(1) if name_match else "unknown"
    return ToolCall(id=uuid.uuid4().hex, function=function, arguments={}, parse_error=error)


def _span_to_call(span: str, tools: list[ToolInfo]) -> ToolCall:
    """Map one candidate span to a ToolCall; malformed input sets parse_error."""
    try:
        payload: object = json.loads(span)
    except (json.JSONDecodeError, RecursionError) as ex:
        return _salvaged_call(span, f"Tool call is not valid JSON: {ex}")
    name = payload.get("name") if isinstance(payload, dict) else None
    if not isinstance(payload, dict) or not isinstance(name, str) or not name:
        return _salvaged_call(span, "Tool call has no non empty string name")
    # Meta's template emits `parameters`; `arguments` is the OpenAI style spelling.
    arguments = payload.get("parameters", payload.get("arguments"))
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments)
    if isinstance(arguments, str):
        # Unknown tool names pass through; Inspect's executor answers "not found".
        try:
            return parse_tool_call(uuid.uuid4().hex, name, arguments, tools)
        except (ValueError, RecursionError) as ex:
            # Inspect's YAML branch raises ValueError on inputs such as an impossible date.
            return ToolCall(
                id=uuid.uuid4().hex,
                function=name,
                arguments={},
                parse_error=f"Tool call {name} arguments could not be parsed: {ex}",
            )
    return ToolCall(
        id=uuid.uuid4().hex,
        function=name,
        arguments={},
        parse_error=f"Tool call {name} has no parameters object or string",
    )


def parse_llama31_tool_calls(text: str, tools: list[ToolInfo]) -> tuple[str, list[ToolCall]]:
    """Split Llama 3.1 output into (content, tool calls); calls keep order of appearance."""
    for token in _SPECIAL_TOKENS:
        text = text.replace(token, "")
    calls: list[ToolCall] = []
    content_parts: list[str] = []
    cursor = 0
    for start, end in _json_object_spans(text):
        span = text[start:end]
        # Candidates mention "name" and "parameters" or "arguments"; other braces stay content.
        if '"name"' not in span or ('"parameters"' not in span and '"arguments"' not in span):
            continue
        calls.append(_span_to_call(span, tools))
        content_parts.append(text[cursor:start])
        cursor = end
    content_parts.append(text[cursor:])
    return "".join(content_parts).strip(), calls


def _tool_entry(message: ChatMessageTool) -> dict[str, Any]:
    content = f"Error: {message.error.message}" if message.error else message.text
    return {"role": "tool", "tool_call_id": message.tool_call_id, "content": content}


def to_template_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """
    Convert Inspect messages to the dicts the Llama 3.1 chat template renders.

    The template renders one call per assistant turn, so a multi call turn becomes
    call and result pairs, matched by tool_call_id rather than by position.
    """
    entries: list[dict[str, Any]] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        index += 1
        if isinstance(message, ChatMessageTool):
            entries.append(_tool_entry(message))
        elif isinstance(message, ChatMessageAssistant) and message.tool_calls:
            # Gather the run of tool results directly after this assistant turn.
            pending: list[ChatMessageTool] = []
            while index < len(messages):
                follower = messages[index]
                if not isinstance(follower, ChatMessageTool):
                    break
                pending.append(follower)
                index += 1
            if message.text:
                entries.append({"role": "assistant", "content": message.text})
            for call in message.tool_calls:
                function = {"name": call.function, "arguments": call.arguments}
                tool_call = {"id": call.id, "type": "function", "function": function}
                entries.append({"role": "assistant", "content": "", "tool_calls": [tool_call]})
                answer = next((tool for tool in pending if tool.tool_call_id == call.id), None)
                if answer is not None:
                    pending.remove(answer)
                    entries.append(_tool_entry(answer))
            # Unmatched results keep their original order so nothing is dropped.
            entries.extend(_tool_entry(tool) for tool in pending)
        else:
            entries.append({"role": message.role, "content": message.text})
    return entries


def tools_to_template(tools: list[ToolInfo]) -> list[dict[str, Any]]:
    """Render ToolInfo as the function schema dicts the chat template reads."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters.model_dump(exclude_none=True),
            },
        }
        for tool in tools
    ]

"""Print the image channel of each model route, with one round trip that sends a tool image.

For each model id the table shows the provider, the value of `tool_result_images()`, the
channel that `channel_for` gives, and the result of one generate call. That call sends a user
message, an assistant message with one tool call (`fetch_image`), and a tool message that holds
text and a tiny PNG. A route that rejects the image in a tool message shows "error" there.

  uv run python scripts/multimodal_injection/channel_probe.py [model ids...]

Positional ids replace the default list. The script makes one model call per id, so run it on a
real route only with the operator's word. The exit code is 0 after the table, even when rows
errored: the table is the output. A key or a header value is never printed.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import io
import re
import sys
from collections.abc import Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from inspect_ai._util.dotenv import init_dotenv  # noqa: E402
from inspect_ai.model import (  # noqa: E402
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
    GenerateConfig,
    Model,
    get_model,
)
from inspect_ai.tool import ContentImage, ContentText, ToolCall, ToolInfo, ToolParams  # noqa: E402
from PIL import Image  # noqa: E402

from evals.multimodal_injection import channel_for  # noqa: E402

# The NVIDIA row is the route of the overnight run (results/multimodal_injection/records.jsonl).
DEFAULT_MODELS = (
    "ollama/qwen3-vl:8b",
    "ollama/gemma4:12b",
    "openai-api/nvidia/nvidia/nemotron-3.5-super-vl-120b-a12b",
    "openrouter/google/gemma-4-26b-a4b-it:free",
)
MAX_TOKENS = 32
COMPLETION_CHARS = 60
ERROR_CHARS = 160
# Anything that looks like a credential is cut from an error message before it is printed.
_SECRET = re.compile(
    r"(?i)(bearer\s+\S+|sk-[A-Za-z0-9_\-]{8,}|nvapi-[A-Za-z0-9_\-]{8,}|(?:api[_-]?key|authorization|token)\S*\s*[:=]\s*\S+)"
)


def tiny_png_data_uri(size: int = 16, color: tuple[int, int, int] = (200, 40, 40)) -> str:
    """A single color PNG, built in memory, as a data URI."""
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def probe_messages() -> list[ChatMessage]:
    """User ask, a fabricated assistant tool call, and a tool result with text and an image."""
    return [
        ChatMessageUser(content="Please fetch the image and tell me what color it is."),
        ChatMessageAssistant(
            content="",
            tool_calls=[ToolCall(id="probe_1", function="fetch_image", arguments={})],
        ),
        ChatMessageTool(
            content=[
                ContentText(text="Image of the requested screen."),
                ContentImage(image=tiny_png_data_uri()),
            ],
            tool_call_id="probe_1",
            function="fetch_image",
        ),
    ]


def probe_tool() -> ToolInfo:
    return ToolInfo(
        name="fetch_image",
        description="Fetch the image of the requested screen.",
        parameters=ToolParams(),
    )


def _clean(text: str, limit: int) -> str:
    """One line, secrets cut, table safe, at most `limit` characters."""
    text = _SECRET.sub("[redacted]", " ".join(text.split()))
    return text.replace("|", "/")[:limit]


async def round_trip(model: Model) -> str:
    """One generate call. Returns "ok ..." or "error ..." and never raises."""
    try:
        output = await model.generate(
            probe_messages(), tools=[probe_tool()], config=GenerateConfig(max_tokens=MAX_TOKENS)
        )
        return f"ok {output.stop_reason}: {_clean(output.completion, COMPLETION_CHARS)}"
    except Exception as exc:  # the table must survive any single route
        return f"error {type(exc).__name__}: {_clean(str(exc), ERROR_CHARS)}"


def probe_row(model_id: str) -> tuple[str, str, str, str, str]:
    """(model id, provider, tool_result_images, channel_for, round trip) for one id."""
    try:
        model = get_model(model_id)
    except Exception as exc:
        provider = model_id.split("/", 1)[0]
        err = f"error {type(exc).__name__}: {_clean(str(exc), ERROR_CHARS)}"
        return model_id, provider, "n/a", "n/a", err
    return (
        model_id,
        type(model.api).__name__,
        str(model.api.tool_result_images()),
        channel_for(model),
        asyncio.run(round_trip(model)),
    )


def render_table(rows: Sequence[tuple[str, ...]]) -> str:
    head = ("model", "provider", "tool_result_images", "channel_for", "round trip")
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(_clean(cell, 400) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("models", nargs="*", help="model ids, replacing the default list")
    args = parser.parse_args(argv)
    # Load .env the way the Inspect CLI does, so a route reads its key and base URL.
    init_dotenv()
    ids = tuple(args.models) or DEFAULT_MODELS
    print(render_table([probe_row(model_id) for model_id in ids]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

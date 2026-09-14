"""Local integration tests for the in process MLX model provider.

Skipped unless darwin arm64, `mlx_lm` is importable, and the pinned snapshot is cached.
"""

import importlib.util
import platform
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ChatMessageUser,
    GenerateConfig,
    Model,
    get_model,
)
from inspect_ai.tool import ToolCall

MODEL_REPO = "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit"
MODEL_REVISION = "241a666dad6cb93c8ff213d39a7f34a36bf26db4"
SNAPSHOT_DIR = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--mlx-community--Meta-Llama-3.1-8B-Instruct-4bit"
    / "snapshots"
    / MODEL_REVISION
)
IPYTHON_HEADER = "<|start_header_id|>ipython<|end_header_id|>"

if not (sys.platform == "darwin" and platform.machine() == "arm64"):
    pytest.skip("MLX provider tests need darwin arm64", allow_module_level=True)
# find_spec does not import mlx_lm. Importing it here would import huggingface_hub, which
# reads HF_HUB_OFFLINE once at import time, before the fixture below could set it.
if importlib.util.find_spec("mlx_lm") is None:
    pytest.skip("mlx_lm is not installed (uv sync --group mlx)", allow_module_level=True)
if not SNAPSHOT_DIR.is_dir():
    pytest.skip(f"model snapshot not cached: {SNAPSHOT_DIR}", allow_module_level=True)


@pytest.fixture(scope="module")
def model() -> Iterator[Model]:
    # One instance for the whole module: a second one would load the 4.7 GB weights again.
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HF_HUB_OFFLINE", "1")
        pytest.importorskip("mlx_lm")
        import huggingface_hub.constants as hf_constants

        assert hf_constants.HF_HUB_OFFLINE, "huggingface_hub was imported before HF_HUB_OFFLINE=1"
        yield get_model(f"mlx/{MODEL_REPO}", revision=MODEL_REVISION)


def _mlx_api(model: Model) -> Any:
    from agent_shield_providers.mlx_lm_api import MLXLMAPI

    assert isinstance(model.api, MLXLMAPI), f"model.api is {type(model.api).__name__}"
    return model.api


def test_get_model_resolves_mlx_provider_through_entry_point(model: Model) -> None:
    from agent_shield_providers.mlx_lm_api import MLXLMAPI

    assert isinstance(model.api, MLXLMAPI), f"model.api is {type(model.api).__name__}"


@pytest.mark.asyncio(loop_scope="module")
async def test_warm_prompt_cache_matches_cold_run_on_second_turn(model: Model) -> None:
    api = _mlx_api(model)
    config = GenerateConfig(temperature=0.0, seed=0, max_tokens=24)
    turn_one: list[ChatMessage] = [
        ChatMessageSystem(content="You are a concise assistant."),
        ChatMessageUser(content="Name one primary color."),
    ]

    api._slot = None
    first = await model.generate(turn_one, config=config)
    # An empty slot here would make the warm and cold runs the same code path.
    assert api._slot is not None, "turn one left the prompt cache slot empty"
    turn_two: list[ChatMessage] = [
        *turn_one,
        first.message,
        ChatMessageUser(content="Name a different one."),
    ]
    warm = await model.generate(turn_two, config=config)
    # Output text can match even over a corrupted cache (a short greedy answer survives
    # duplicated context), so also check the cache holds exactly this prompt plus output.
    assert warm.usage is not None
    assert api._slot is not None
    warm_tokens, warm_cache = api._slot
    expected = len(api._render(turn_two, [])) + warm.usage.output_tokens
    assert warm_cache[0].offset == len(warm_tokens) == expected, (
        f"offset={warm_cache[0].offset} slot={len(warm_tokens)} expected={expected}"
    )

    api._slot = None
    cold = await model.generate(turn_two, config=config)

    assert warm.message.text == cold.message.text, (
        f"warm={warm.message.text!r} cold={cold.message.text!r}"
    )
    assert warm.usage is not None
    assert cold.usage is not None
    assert warm.usage.output_tokens == cold.usage.output_tokens
    assert warm.stop_reason == cold.stop_reason


@pytest.mark.asyncio(loop_scope="module")
async def test_over_context_cap_returns_model_length_without_generating(model: Model) -> None:
    api = _mlx_api(model)
    messages: list[ChatMessage] = [ChatMessageUser(content="Say hello.")]
    # Warm the slot first so the identity check below cannot pass on None is None.
    await model.generate(messages, config=GenerateConfig(max_tokens=4))
    slot_before = api._slot
    assert slot_before is not None

    output = await model.generate(messages, config=GenerateConfig(max_tokens=9000))

    assert output.stop_reason == "model_length"
    assert output.message.text == ""
    assert output.usage is not None
    assert output.usage.output_tokens == 0
    # Refusing after generating would also report model_length; the untouched slot proves
    # the cap check ran before any MLX work.
    assert api._slot is slot_before


@pytest.mark.asyncio(loop_scope="module")
async def test_within_context_cap_generates_tokens(model: Model) -> None:
    messages: list[ChatMessage] = [ChatMessageUser(content="Say hello.")]

    output = await model.generate(messages, config=GenerateConfig(max_tokens=8))

    assert output.stop_reason in {"stop", "max_tokens"}
    assert output.usage is not None
    assert output.usage.output_tokens > 0


def test_tool_result_renders_under_ipython_header(model: Model) -> None:
    api = _mlx_api(model)
    messages: list[ChatMessage] = [
        ChatMessageUser(content="What is in notes.txt?"),
        ChatMessageAssistant(
            content="",
            tool_calls=[
                ToolCall(id="call_1", function="read_file", arguments={"path": "notes.txt"})
            ],
        ),
        ChatMessageTool(content="Buy milk.", tool_call_id="call_1", function="read_file"),
    ]

    rendered = api._tokenizer.decode(api._render(messages, []))

    assert IPYTHON_HEADER in rendered, rendered


def test_max_connections_is_one(model: Model) -> None:
    assert model.api.max_connections() == 1


@pytest.mark.asyncio(loop_scope="module")
async def test_identical_resend_trims_cache_to_prompt_plus_output(model: Model) -> None:
    # A retry or a second epoch resends the same prompt, so the slot holds that prompt plus
    # the earlier output and must be trimmed before prefill. L2's growing conversation never
    # trims: its slot is a strict prefix of the next prompt.
    api = _mlx_api(model)
    config = GenerateConfig(temperature=0.0, seed=0, max_tokens=24)
    messages: list[ChatMessage] = [
        ChatMessageSystem(content="You are a concise assistant."),
        ChatMessageUser(content="Name a large ocean."),
    ]

    api._slot = None
    await model.generate(messages, config=config)
    resend = await model.generate(messages, config=config)
    assert resend.usage is not None
    assert api._slot is not None
    resend_tokens, resend_cache = api._slot
    expected = len(api._render(messages, [])) + resend.usage.output_tokens
    assert resend_cache[0].offset == len(resend_tokens) == expected, (
        f"offset={resend_cache[0].offset} slot={len(resend_tokens)} expected={expected}"
    )

    api._slot = None
    cold = await model.generate(messages, config=config)

    assert resend.message.text == cold.message.text, (
        f"resend={resend.message.text!r} cold={cold.message.text!r}"
    )
    assert cold.usage is not None
    assert resend.usage.output_tokens == cold.usage.output_tokens
    assert resend.stop_reason == cold.stop_reason


class _LoadTripwire(BaseException):
    """Raised if construction reaches mlx_lm.load; BaseException so no handler swallows it."""


def test_unknown_model_arg_raises_before_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    import agent_shield_providers.mlx_lm_api as mlx_lm_api

    def tripwire(*args: object, **kwargs: object) -> object:
        raise _LoadTripwire()

    monkeypatch.setattr(mlx_lm_api, "load", tripwire)
    # A typo such as `-M revison=...` must fail loudly, not load refs/main while the eval
    # log records the misspelled key.
    with pytest.raises(ValueError, match="revison"):
        mlx_lm_api.MLXLMAPI(model_name=MODEL_REPO, revison=MODEL_REVISION)


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("max_tokens", [0, -1])
async def test_non_positive_max_tokens_falls_back_to_default(
    model: Model, monkeypatch: pytest.MonkeyPatch, max_tokens: int
) -> None:
    import agent_shield_providers.mlx_lm_api as mlx_lm_api

    seen: list[int] = []

    def fake_stream_generate(*args: object, **kwargs: Any) -> Iterator[object]:
        seen.append(kwargs["max_tokens"])
        return iter(())

    monkeypatch.setattr(mlx_lm_api, "stream_generate", fake_stream_generate)
    await model.generate(
        [ChatMessageUser(content="Say hello.")], config=GenerateConfig(max_tokens=max_tokens)
    )

    # -1 once slipped past the context cap and reached generation unbounded.
    assert seen == [2048]

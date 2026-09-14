"""
In process Inspect AI model provider for mlx_lm.

One worker thread owns every MLX call, from loading weights to generating. Prompts are
rendered through the pure Llama 3.1 layer in llama31.py, and a single slot prompt cache
reuses the prefix shared with the previous call, so a growing conversation only prefills
its new suffix.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import mlx.core as mx
from anyio import to_thread
from inspect_ai.model import (
    ChatCompletionChoice,
    ChatMessage,
    ChatMessageAssistant,
    GenerateConfig,
    ModelAPI,
    ModelOutput,
    ModelUsage,
    StopReason,
)
from inspect_ai.tool import ToolChoice, ToolInfo
from mlx_lm import load, stream_generate
from mlx_lm.models.cache import can_trim_prompt_cache, make_prompt_cache, trim_prompt_cache
from mlx_lm.sample_utils import make_sampler

from .llama31 import parse_llama31_tool_calls, to_template_messages, tools_to_template


class MLXLMAPI(ModelAPI):
    """Run an mlx_lm model inside this process as an Inspect model API."""

    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GenerateConfig = GenerateConfig(),  # noqa: B008
        revision: str | None = None,
        max_context_tokens: int = 8192,
        kv_bits: int | None = None,
        **model_args: Any,
    ) -> None:
        super().__init__(
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            api_key_vars=[],
            config=config,
        )
        if model_args:
            # Inspect passes every -M key here; a typo such as `revison` must fail, not load main.
            raise ValueError(f"Unknown mlx model args: {', '.join(sorted(model_args))}")
        self._max_context_tokens = max_context_tokens
        self._kv_bits = kv_bits
        # Every MLX call, load included, runs on this one thread.
        self._executor = ThreadPoolExecutor(max_workers=1)
        # Indexed, not unpacked: mlx_lm types load as a two or three tuple.
        loaded = self._executor.submit(load, model_name, revision=revision).result()
        self._model: Any = loaded[0]
        self._tokenizer: Any = loaded[1]
        self._slot: tuple[list[int], list[Any]] | None = None

    def _render(self, messages: list[ChatMessage], tools: list[ToolInfo]) -> list[int]:
        """Tokenize the chat prompt. Tokenization only, so any thread may call it."""
        ids = self._tokenizer.apply_chat_template(
            to_template_messages(messages),
            tools=tools_to_template(tools) or None,
            add_generation_prompt=True,
            tokenize=True,
        )
        return [int(token) for token in ids]

    def max_connections(self) -> int:
        return 1

    def connection_key(self) -> str:
        return "mlx-local"

    async def generate(
        self,
        input: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> ModelOutput:
        prompt = self._render(input, tools)
        # 0, None, and negatives mean the default; -1 would otherwise slip past the cap check.
        max_tokens = config.max_tokens if config.max_tokens and config.max_tokens > 0 else 2048
        if len(prompt) + max_tokens > self._max_context_tokens:
            # Refuse before prefill so the KV cache never grows past the context cap.
            return ModelOutput(
                model=self.model_name,
                choices=[
                    ChatCompletionChoice(
                        message=ChatMessageAssistant(
                            content="", model=self.model_name, source="generate"
                        ),
                        stop_reason="model_length",
                    )
                ],
                usage=ModelUsage(
                    input_tokens=len(prompt), output_tokens=0, total_tokens=len(prompt)
                ),
            )

        def work() -> tuple[str, list[int], str | None]:
            if config.seed is not None:
                mx.random.seed(config.seed)
            sampler = make_sampler(temp=config.temperature or 0.0, top_p=config.top_p or 0.0)
            tokens: list[int] = []
            cache: list[Any] = []
            # Cleared first: a failed run must not leave stale tokens beside a changed cache.
            if self._slot is not None:
                tokens, cache = self._slot
                self._slot = None
            n = 0
            while n < min(len(tokens), len(prompt)) and tokens[n] == prompt[n]:
                n += 1
            # generate_step must feed at least one prompt token to sample the first output.
            if n == len(prompt):
                n -= 1
            if n > 0 and can_trim_prompt_cache(cache):
                trim_prompt_cache(cache, cache[0].offset - n)
            else:
                cache = make_prompt_cache(self._model)
                n = 0
            text_parts: list[str] = []
            generated: list[int] = []
            finish_reason: str | None = None
            for response in stream_generate(
                self._model,
                self._tokenizer,
                prompt=prompt[n:],
                max_tokens=max_tokens,
                sampler=sampler,
                prompt_cache=cache,
                kv_bits=self._kv_bits,
            ):
                text_parts.append(response.text)
                generated.append(int(response.token))
                finish_reason = response.finish_reason
            # Slice by the cache's own length, never a count assumed from the stream.
            self._slot = ((prompt + generated)[: cache[0].offset], cache)
            return "".join(text_parts), generated, finish_reason

        text, generated, finish_reason = await to_thread.run_sync(
            self._executor.submit(work).result
        )
        content, calls = parse_llama31_tool_calls(text, tools)
        stop_reason: StopReason = (
            "tool_calls" if calls else "max_tokens" if finish_reason == "length" else "stop"
        )
        return ModelOutput(
            model=self.model_name,
            choices=[
                ChatCompletionChoice(
                    message=ChatMessageAssistant(
                        content=content,
                        tool_calls=calls or None,
                        model=self.model_name,
                        source="generate",
                    ),
                    stop_reason=stop_reason,
                )
            ],
            usage=ModelUsage(
                input_tokens=len(prompt),
                output_tokens=len(generated),
                total_tokens=len(prompt) + len(generated),
            ),
        )

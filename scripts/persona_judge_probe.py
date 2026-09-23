"""Judge probe: one prompt to each Ollama judge under three GenerateConfig variants.

    uv run python scripts/persona_judge_probe.py --models ollama/llama3.2:3b,ollama/llama3.1:8b
        [--personas-dir DIR] [--log logs/persona_probe_x.txt]

The prompts are the sweep's own: Mira Solheim Voice Samples 1 to 3 with names masked, one
Sample per variant, gold guide A is Mira and guide B is Mari, built by
evals.persona.judge.build_prompt, so the probe sees the prompts judge_attribution sends. The
three variants (docs/EVAL_PORTFOLIO_PLAN.md:23-29, amendment 3, item A2) are plain,
effort_none (reasoning_effort="none") and think_false (extra_body={"think": False}). The
question per model and variant: does the judge return a bare letter with no reasoning part
inside a 16 token cap, and how long does a call take. Each variant is called twice on its own
Sample, the second on the reversed guide order (gold guide B), and the second call is printed:
model load is not counted, prompt processing is, since a prompt the model has already seen
would hit Ollama's prompt cache and read as instant. The guides are most of every prompt, so
plain, which runs first, sees the coldest cache: budget the sweep from its working_s. One
line per model and variant:
    model=<m> variant=<v> ok=<True|False> reply=<repr of completion> verdict=<A|B|None>
    output_tokens=<int|None> reasoning_part=<True|False> working_s=<float 2dp|None>
    error=<message or empty>
ok means the call returned; verdict is parse_verdict on the reply, and only a parsed verdict
counts a model as usable. After a model's three variants `ollama stop` frees it (18 GiB holds
one); a stop that fails prints `stop model=<m> error=<text>` on its own line. No Anthropic model
is called. Exit 1 when any model had no variant with a parsed verdict (a crash before probe_done
also exits 1, with no probe_done line), 2 when a model name does not resolve.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from inspect_ai.model import ChatMessageUser, ContentReasoning, GenerateConfig, get_model

from evals.persona.bible import mask
from evals.persona.judge import build_prompt, parse_verdict, style_rules
from evals.persona_fidelity import DEFAULT_PERSONAS_DIR, PERSONA_PAIR, load_pair

PROBE_SAMPLES = (0, 1, 2)  # Mira Samples 1 to 3 in Bible.samples, one per variant, file order


def probe_configs() -> dict[str, GenerateConfig]:
    """The three variants, in order: plain, effort_none, think_false.

    Values from docs/EVAL_PORTFOLIO_PLAN.md:23-29. max_connections is never set here; the
    sweep sets it. Three explicit constructor calls, since a dict splat into the typed fields
    does not pass strict mypy.
    """
    return {
        "plain": GenerateConfig(
            temperature=0, seed=0, max_tokens=16, attempt_timeout=120, max_retries=1
        ),
        "effort_none": GenerateConfig(
            temperature=0,
            seed=0,
            max_tokens=16,
            attempt_timeout=120,
            max_retries=1,
            reasoning_effort="none",
        ),
        "think_false": GenerateConfig(
            temperature=0,
            seed=0,
            max_tokens=16,
            attempt_timeout=120,
            max_retries=1,
            extra_body={"think": False},
        ),
    }


def probe_prompts(personas_dir: str | Path) -> list[tuple[str, str]]:
    """Per PROBE_SAMPLES entry, the sweep's two prompts: gold guide A (Mira), then reversed.

    The meta task runs the judge with leak_guard off, so the probe likewise masks names only
    and never drops sentences.
    """
    pair = load_pair(personas_dir)
    gold, other = PERSONA_PAIR
    guides = {stem: mask(style_rules(bible), pair.values()) for stem, bible in pair.items()}
    prompts: list[tuple[str, str]] = []
    for index in PROBE_SAMPLES:
        text = mask(pair[gold].samples[index], pair.values())
        prompts.append(
            (
                build_prompt(guides[gold], guides[other], text),
                build_prompt(guides[other], guides[gold], text),
            )
        )
    return prompts


@dataclass(frozen=True)
class ProbeResult:
    """One model and variant: what came back on the second call, or the error.

    ok means the call returned; verdict is what the sweep's parser reads off the reply, None
    when malformed. Both are printed because a truncated inline think block gives ok=True,
    reasoning_part=False and verdict=None.
    """

    model: str
    variant: str
    ok: bool
    reply: str
    verdict: str | None
    output_tokens: int | None
    reasoning_part: bool
    working_s: float | None
    error: str

    def line(self) -> str:
        working = f"{self.working_s:.2f}" if self.working_s is not None else "None"
        return (
            f"model={self.model} variant={self.variant} ok={self.ok} reply={self.reply!r} "
            f"verdict={self.verdict} output_tokens={self.output_tokens} "
            f"reasoning_part={self.reasoning_part} working_s={working} error={self.error}"
        )


def error_text(exc: BaseException) -> str:
    """One line for the log: the cause unwrapped, whitespace collapsed, the tail kept.

    Inspect wraps a 400 in a RuntimeError whose text starts with the request JSON over several
    lines. Retries wrap that in a RetryError whose str is a memory address. The log is one line
    per call, so the cause is unwrapped, whitespace collapsed and the tail kept.
    """
    last_attempt = getattr(exc, "last_attempt", None)
    inner = last_attempt.exception() if last_attempt is not None else None
    if inner is not None:
        exc = inner
    message = " ".join(str(exc).split())[-280:]
    return f"{type(exc).__name__}: {message}"


async def probe_one(
    model: str, variant: str, config: GenerateConfig, prompts: tuple[str, str]
) -> ProbeResult:
    """Warm the judge on the first prompt, then read its output on the second (reversed)."""
    judge = get_model(model, config=config)
    try:
        await judge.generate([ChatMessageUser(content=prompts[0])])
        output = await judge.generate([ChatMessageUser(content=prompts[1])])
    except Exception as exc:  # recorded on the result line; the next variant still runs
        return ProbeResult(model, variant, False, "", None, None, False, None, error_text(exc))
    content = output.message.content
    reasoning_part = isinstance(content, list) and any(
        isinstance(part, ContentReasoning) for part in content
    )
    output_tokens = output.usage.output_tokens if output.usage else None
    return ProbeResult(
        model,
        variant,
        True,
        output.completion,
        parse_verdict(output.completion),
        output_tokens,
        reasoning_part,
        output.time,
        "",
    )


def stop_model(model: str) -> str | None:
    """Free the resident model before the next one: 18 GiB holds one.

    A missing binary or a stuck server is reported on its own line instead of hanging the probe.
    """
    name = model.removeprefix("ollama/")
    # A non zero exit is ignored on purpose: the model's probe lines are already recorded.
    try:
        subprocess.run(
            ["ollama", "stop", name], capture_output=True, text=True, check=False, timeout=60
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return error_text(exc)
    return None


def run_probe(models: list[str], personas_dir: str | Path, log: Path | None) -> int:
    """Probe every model under every variant, one line each; 0 when every model had a verdict."""
    # A repeated name would otherwise make the exit code compare a set against a list.
    models = list(dict.fromkeys(models))
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
    handle = log.open("a", encoding="utf-8") if log is not None else None

    def emit(line: str) -> None:
        print(line, flush=True)
        if handle is not None:
            handle.write(line + "\n")
            handle.flush()

    verdict_models: set[str] = set()
    try:
        # An unknown provider raises from get_model with no network call; finding that out
        # before the bibles are read keeps the log readable and the exit code distinct (2).
        try:
            for model in models:
                get_model(model)
        except Exception as exc:
            emit(f"probe_error={error_text(exc)}")
            return 2
        prompts = probe_prompts(personas_dir)
        configs = probe_configs()
        emit(
            f"probe prompt_chars={','.join(str(len(pair[1])) for pair in prompts)} "
            f"personas_dir={personas_dir} "
            f"variants={','.join(configs)}"
        )
        for model in models:
            for (variant, config), pair in zip(configs.items(), prompts, strict=True):
                result = asyncio.run(probe_one(model, variant, config, pair))
                emit(result.line())
                if result.verdict is not None:
                    verdict_models.add(model)
            stop_error = stop_model(model)
            if stop_error is not None:
                emit(f"stop model={model} error={stop_error}")  # own prefix: not a result line
        emit(f"probe_done models={len(models)} verdict_models={len(verdict_models)}")
    finally:
        if handle is not None:
            handle.close()
    return 0 if len(verdict_models) == len(models) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--models",
        required=True,
        help="comma separated judge models, the Makefile's PROBE_MODELS",
    )
    parser.add_argument("--personas-dir", default=DEFAULT_PERSONAS_DIR)
    parser.add_argument(
        "--log", default=None, help="text log every line is appended to (the Makefile passes one)"
    )
    args = parser.parse_args(argv)
    models: list[str] = [name.strip() for name in args.models.split(",") if name.strip()]
    if not models:
        parser.error("--models names no model")
    return run_probe(models, args.personas_dir, Path(args.log) if args.log else None)


if __name__ == "__main__":
    sys.exit(main())

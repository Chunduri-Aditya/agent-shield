"""Pin the judge probe's three GenerateConfig variants to the spec.

Expected values come from ``docs/EVAL_PORTFOLIO_PLAN.md:23-29`` (amendment 3, item A2),
never from the module under test.
"""

import asyncio
import subprocess
from pathlib import Path

import pytest
from inspect_ai.model import ChatMessage, GenerateConfig, ModelOutput

from evals.persona_fidelity import DEFAULT_PERSONAS_DIR


def test_probe_configs_match_spec() -> None:
    """``probe_configs()`` returns plain, effort_none, think_false in that order.

    Source of truth: ``docs/EVAL_PORTFOLIO_PLAN.md:23-29``. ``plain`` is
    ``temperature=0, seed=0, max_tokens=16, attempt_timeout=120, max_retries=1``;
    ``effort_none`` adds ``reasoning_effort="none"``; ``think_false`` adds
    ``extra_body={"think": False}``. The probe never sets ``max_connections``
    (the sweep does).
    """
    from scripts.persona_judge_probe import probe_configs

    configs = probe_configs()

    assert list(configs) == ["plain", "effort_none", "think_false"], (
        f"variant order: expected ['plain', 'effort_none', 'think_false'], got {list(configs)}"
    )

    shared: dict[str, object] = {
        "temperature": 0,
        "seed": 0,
        "max_tokens": 16,
        "attempt_timeout": 120,
        "max_retries": 1,
    }
    per_variant: dict[str, dict[str, object]] = {
        "plain": {"reasoning_effort": None, "extra_body": None},
        "effort_none": {"reasoning_effort": "none", "extra_body": None},
        "think_false": {"reasoning_effort": None, "extra_body": {"think": False}},
    }

    for variant, extras in per_variant.items():
        cfg = configs[variant]
        for field, expected in {**shared, **extras}.items():
            actual = getattr(cfg, field)
            assert actual == expected, f"{variant}.{field}: expected {expected!r}, got {actual!r}"
        assert cfg.max_connections is None, (
            f"{variant}.max_connections: expected None (sweep sets it, probe does not), "
            f"got {cfg.max_connections!r}"
        )


# --- probe contract: one line errors, verdicts, exit codes, prompt parity ---------------------
#
# Expected values below come from the probe contract (review of scripts/persona_judge_probe.py),
# never from the module under test. Imports of the probe stay inside each test so a missing
# symbol reds exactly the test that needs it.

_ERROR_TAIL = 280  # error_text keeps the last 280 characters of the collapsed message


def _require_bibles() -> None:
    """Skip when the pair bibles are not on this machine (PERSONAS_DIR or the default)."""
    mira = Path(DEFAULT_PERSONAS_DIR) / "mira-solheim.md"
    if not mira.is_file():
        pytest.skip(f"persona bibles missing: {mira} is not a file")


def test_error_text_is_one_line_and_keeps_the_cause() -> None:
    """A tenacity RetryError is unwrapped to its last attempt's exception; the message is
    whitespace collapsed, cut to its last 280 characters, and never carries a newline."""
    import tenacity

    from scripts.persona_judge_probe import error_text

    attempt = tenacity.Future(1)
    attempt.set_exception(
        RuntimeError("\nRequest:\n" + "x" * 400 + "\n\nOLLAMA_SAYS: reasoning not supported")
    )
    exc = tenacity.RetryError(attempt)

    text = error_text(exc)

    assert "\n" not in text, f"error_text returned more than one line: {text!r}"
    assert text.startswith("RuntimeError: "), f"cause not unwrapped from RetryError: {text!r}"
    assert text.endswith("OLLAMA_SAYS: reasoning not supported"), f"tail dropped: {text!r}"
    assert len(text) <= len("RuntimeError: ") + _ERROR_TAIL, f"{len(text)} chars: {text!r}"

    plain = error_text(ValueError("a  b\n c"))
    assert plain == "ValueError: a b c", f"whitespace not collapsed: {plain!r}"


class _RecordingJudge:
    """Stands in for get_model() inside judge_attribution: records every prompt, answers A."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(
        self, messages: list[ChatMessage], config: GenerateConfig | None = None
    ) -> ModelOutput:
        # The scorer passes its config on every call (plan A2); a double must accept it.
        self.prompts.append("\n".join(message.text for message in messages))
        return ModelOutput.from_content(model="rec", content="A")


def test_probe_prompts_match_the_meta_judge_prompts(monkeypatch: pytest.MonkeyPatch) -> None:
    """probe_prompts() must hand each judge the exact prompts judge_attribution sends for
    Mira S-01 to S-03 in the meta task: gold order first, reversed second, six distinct."""
    _require_bibles()
    from inspect_ai.model import ModelName
    from inspect_ai.scorer import Target
    from inspect_ai.solver import TaskState

    import evals.persona.judge as judge_mod
    from evals.persona_fidelity import load_pair, make_meta_samples
    from scripts.persona_judge_probe import probe_prompts

    recorder = _RecordingJudge()
    monkeypatch.setattr(judge_mod, "get_model", lambda *args, **kwargs: recorder)
    scorer = judge_mod.judge_attribution(
        judge_model="rec/x", personas_dir=DEFAULT_PERSONAS_DIR, leak_guard=False
    )
    samples = make_meta_samples(load_pair(DEFAULT_PERSONAS_DIR))[:3]
    expected = probe_prompts(DEFAULT_PERSONAS_DIR)
    assert len(expected) == 3, f"probe_prompts returned {len(expected)} pairs, expected 3"

    async def score_one(index: int) -> tuple[str, str]:
        sample = samples[index]
        assert sample.id == f"mira-solheim:S-{index + 1:02d}", f"fixture order: {sample.id!r}"
        recorder.prompts.clear()
        state = TaskState(
            model=ModelName("mockllm/model"),
            sample_id=str(sample.id),
            epoch=1,
            input=sample.input,
            messages=[],
            output=ModelOutput.from_content(model="echo", content=str(sample.input)),
            metadata=dict(sample.metadata or {}),
        )
        await scorer(state, Target(str(sample.target)))
        assert len(recorder.prompts) == 2, f"judge called {len(recorder.prompts)} times, not 2"
        return recorder.prompts[0], recorder.prompts[1]

    for index, (gold_first, reversed_order) in enumerate(expected):
        sent_first, sent_second = asyncio.run(score_one(index))
        assert sent_first == gold_first, f"S-{index + 1:02d}: gold order prompt differs"
        assert sent_second == reversed_order, f"S-{index + 1:02d}: reversed prompt differs"

    flat = [prompt for pair in expected for prompt in pair]
    assert len(set(flat)) == 6, f"expected 6 distinct prompts, got {len(set(flat))}"


def test_probe_one_on_mockllm_returns_no_verdict() -> None:
    """mockllm answers with prose, so the call is ok but the sweep's parser reads no verdict."""
    from scripts.persona_judge_probe import probe_configs, probe_one

    result = asyncio.run(
        probe_one("mockllm/model", "plain", probe_configs()["plain"], ("hello", "hello again"))
    )

    assert result.ok is True, result.line()
    assert result.verdict is None, result.line()
    assert result.reasoning_part is False, result.line()
    assert result.error == "", result.line()
    assert "verdict=None" in result.line(), result.line()


def test_run_probe_exits_1_without_a_verdict_and_writes_the_log(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model with no parsed verdict exits 1; a repeated model name is probed once; every
    line printed is also in the log. stop_model is recorded, not run: a unit test never sends
    `ollama stop` to a live server."""
    _require_bibles()
    import scripts.persona_judge_probe as probe

    stopped: list[str] = []
    monkeypatch.setattr(probe, "stop_model", lambda model: stopped.append(model))

    log = tmp_path / "probe.txt"
    code = probe.run_probe(["mockllm/model", "mockllm/model"], DEFAULT_PERSONAS_DIR, log)
    out = capsys.readouterr().out
    text = log.read_text(encoding="utf-8")

    assert code == 1, f"exit code {code}, expected 1 (no verdict from mockllm)"
    assert out == text, "stdout and the log differ"
    assert stopped == ["mockllm/model"], f"stop_model calls: {stopped}"
    lines = text.splitlines()
    variant_lines = [line for line in lines if line.startswith("model=mockllm/model variant=")]
    stray_lines = [
        line
        for line in lines
        if (line.startswith("model=") or line.startswith("stop ")) and line not in variant_lines
    ]
    assert len(variant_lines) == 3, f"expected 3 variant lines (dedupe), got:\n{text}"
    assert [line.split()[1] for line in variant_lines] == [
        "variant=plain",
        "variant=effort_none",
        "variant=think_false",
    ], f"variant order:\n{text}"
    for line in variant_lines:
        assert "verdict=None" in line, f"no verdict=None on: {line!r}"
    assert stray_lines == [], f"unexpected model= or stop lines: {stray_lines}"
    assert lines[-1] == "probe_done models=1 verdict_models=0", f"last line: {lines[-1]!r}"


def test_stop_failure_is_one_line_with_its_own_prefix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing `ollama` binary (or a stuck server) is reported on a `stop ` line after the
    model's variants, never raised, and the line is not a `model=` result line."""
    _require_bibles()
    import scripts.persona_judge_probe as probe

    def missing_binary(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError(2, "No such file or directory", "ollama")

    monkeypatch.setattr(subprocess, "run", missing_binary)
    text = probe.stop_model("ollama/x")
    assert text is not None and text.startswith("FileNotFoundError: "), text
    assert "\n" not in text, text

    code = probe.run_probe(["mockllm/model"], DEFAULT_PERSONAS_DIR, tmp_path / "probe.txt")
    lines = capsys.readouterr().out.splitlines()
    stop_lines = [line for line in lines if line.startswith("stop ")]
    assert code == 1, code
    assert stop_lines == [f"stop model=mockllm/model error={text}"], lines
    assert lines.index(stop_lines[0]) == len(lines) - 2, "stop line is not just before probe_done"
    assert sum(line.startswith("model=") for line in lines) == 3, lines


def test_run_probe_rejects_an_unknown_provider_before_reading_bibles(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unknown provider exits 2 on one probe_error line and never opens a bible: the
    personas dir does not exist, so reaching it would raise FileNotFoundError instead."""
    from scripts.persona_judge_probe import run_probe

    code = run_probe(["nope/x"], "/nonexistent/personas", None)
    out = capsys.readouterr().out

    assert code == 2, f"exit code {code}, expected 2 for an unknown provider"
    lines = out.splitlines()
    error_lines = [line for line in lines if line.startswith("probe_error=")]
    assert len(error_lines) == 1, f"expected one probe_error line, got:\n{out}"
    assert error_lines[0] != "probe_error=", "probe_error line carries no message"
    assert not any(line.startswith("model=") for line in lines), f"model line emitted:\n{out}"
    assert "FileNotFoundError" not in out, f"bibles were read before the model check:\n{out}"

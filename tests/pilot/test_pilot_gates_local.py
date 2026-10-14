"""V1_2_PLAN step 2b: `gates.py post --local` on real logs (J1).

Local rows set temperature 0 and seed 0, so the local gate allows those two keys while
top_p and top_k stay forbidden. It reads the raw tool list in the OpenAI shape, prices
nothing, and keeps every other check. `--expect-temperature` and `--expect-seed` assert a
row of record by value. Every allow case is a real log (one Anthropic smoke run, one
Ollama run); every deny case is a copy of that real log with exactly one field changed.
The logs are retargeted to a scratch repo's HEAD, so the revision and scorer hash checks
run for real against that repo. Retargeting also sets `revision.dirty` False: the Ollama
fixture was recorded from a dirty tree (`6e70cb7` plus the uncommitted step 2b work), so
the allow half of the revision row on the real logs is made here; its deny half lives in
tests/pilot/test_pilot_gates.py. The Anthropic fixture was written by inspect_ai 0.3.279,
the Ollama one by the pinned 0.3.278; both read the same with the pinned reader.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict, Unpack

import pytest
from inspect_ai.event import ModelEvent
from inspect_ai.log import EvalLog, read_eval_log, write_eval_log

from scripts.pilot import gates
from tests.pilot.pilot_helpers import make_data, make_repo
from tools.payloads import TL_01_POISONING_PAYLOAD

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "pilot_gate"
ANTHROPIC = FIXTURES / "anthropic_haiku_smoke.eval"
OLLAMA = FIXTURES / "ollama_llama31_q4.eval"
GATES_PY = REPO / "scripts" / "pilot" / "gates.py"


class GateOptions(TypedDict, total=False):
    """Keyword options `real` forwards to `gates.post_checks`."""

    local: bool
    expect_temperature: float
    expect_seed: int


def failed(checks: list[gates.Check]) -> set[str]:
    return {c.name for c in checks if c.ok is False}


def first_model_event(log: EvalLog) -> ModelEvent:
    events = [e for e in (log.samples or [])[0].events if isinstance(e, ModelEvent)]
    return events[0]


def real(
    tmp_path: Path,
    fixture: Path,
    change: Callable[[EvalLog], None] | None = None,
    **kwargs: Unpack[GateOptions],
) -> list[gates.Check]:
    """Run the post gate on a retargeted copy of a real log, with one optional change."""
    repo, head = make_repo(tmp_path)
    data = make_data(tmp_path, repo, head)
    (data / "directive.txt").write_text(TL_01_POISONING_PAYLOAD + "\n")
    log = read_eval_log(str(fixture), resolve_attachments="full")
    assert log.eval.revision is not None
    log.eval.revision.commit = head[:7]
    log.eval.revision.dirty = False
    if change is not None:
        change(log)
    path = tmp_path / "run.eval"
    write_eval_log(log, str(path))
    return gates.post_checks(data, repo, path, data / "directive.txt", **kwargs)


# ---------------------------------------------------------------- Anthropic log


def test_anthropic_real_log_passes_the_claude_gate(tmp_path: Path) -> None:
    checks = real(tmp_path, ANTHROPIC)
    assert failed(checks) == set(), [c for c in checks if c.ok is False]


def test_anthropic_real_log_is_refused_by_the_local_gate(tmp_path: Path) -> None:
    """Local mode on a Claude log: not a local model, and no OpenAI shaped tool list."""
    checks = real(tmp_path, ANTHROPIC, local=True)
    assert failed(checks) == {"local_model", "delivery"}
    delivery = next(c for c in checks if c.name == "delivery")
    assert "OpenAI shaped" in delivery.evidence


def test_claude_gate_still_forbids_temperature(tmp_path: Path) -> None:
    def add_temperature(log: EvalLog) -> None:
        call = first_model_event(log).call
        assert call is not None
        call.request["temperature"] = 0.0

    assert failed(real(tmp_path, ANTHROPIC, add_temperature)) == {"config"}


def test_expect_flags_need_local_mode(tmp_path: Path) -> None:
    done = subprocess.run(
        [sys.executable, str(GATES_PY), "post", "--data", str(tmp_path), "--repo", str(REPO),
         "--log", str(ANTHROPIC), "--expect-temperature", "0"],
        capture_output=True, text=True, check=False,
    )
    assert done.returncode == 2, done.stdout + done.stderr
    assert "--local" in done.stderr


# ---------------------------------------------------------------- Ollama log

LOCAL: GateOptions = {"local": True, "expect_temperature": 0.0, "expect_seed": 0}


def test_ollama_fixture_is_a_local_run_of_record() -> None:
    log = read_eval_log(str(OLLAMA), resolve_attachments="full")
    assert log.eval.model.startswith("ollama/")
    assert log.eval.config.log_model_api is True
    assert log.eval.model_generate_config.temperature == 0.0
    assert log.eval.model_generate_config.seed == 0
    call = first_model_event(log).call
    assert call is not None and call.response is not None
    assert "choices" in call.response
    assert call.request["temperature"] == 0.0
    assert call.request["seed"] == 0


def test_ollama_real_log_passes_the_local_gate(tmp_path: Path) -> None:
    checks = real(tmp_path, OLLAMA, **LOCAL)
    assert failed(checks) == set(), [c for c in checks if c.ok is False]
    cost = next(c for c in checks if c.name == "cost")
    assert cost.ok is None and "cost 0" in cost.evidence
    stop = next(c for c in checks if c.name == "stop_reason")
    assert "raw {'stop': 1, 'tool_calls': 1}" in stop.evidence


def test_ollama_real_log_fails_the_claude_gate(tmp_path: Path) -> None:
    """Without --local: temperature and seed are set, and the tool list is OpenAI shaped."""
    assert failed(real(tmp_path, OLLAMA)) == {"config", "delivery"}


@pytest.mark.parametrize("key", ["top_p", "top_k"])
def test_local_gate_forbids_top_p_and_top_k_in_the_raw_request(tmp_path: Path, key: str) -> None:
    def add(log: EvalLog) -> None:
        call = first_model_event(log).call
        assert call is not None
        call.request[key] = 1

    assert failed(real(tmp_path, OLLAMA, add, **LOCAL)) == {"config"}


def test_local_gate_forbids_top_p_in_the_event_config(tmp_path: Path) -> None:
    def add(log: EvalLog) -> None:
        first_model_event(log).config.top_p = 0.9

    assert failed(real(tmp_path, OLLAMA, add, **LOCAL)) == {"config"}


def test_local_gate_checks_the_expected_temperature(tmp_path: Path) -> None:
    kwargs: GateOptions = {**LOCAL, "expect_temperature": 0.7}
    assert failed(real(tmp_path, OLLAMA, **kwargs)) == {"expect_temperature"}


def test_local_gate_checks_the_expected_seed(tmp_path: Path) -> None:
    kwargs: GateOptions = {**LOCAL, "expect_seed": 1}
    assert failed(real(tmp_path, OLLAMA, **kwargs)) == {"expect_seed"}


def test_local_gate_sees_a_raw_request_that_drifts_from_the_expected_seed(
    tmp_path: Path,
) -> None:
    def drift(log: EvalLog) -> None:
        call = first_model_event(log).call
        assert call is not None
        call.request["seed"] = 5

    assert failed(real(tmp_path, OLLAMA, drift, **LOCAL)) == {"expect_seed"}


def test_local_gate_needs_the_directive_in_the_raw_tool_list(tmp_path: Path) -> None:
    def strip(log: EvalLog) -> None:
        call = first_model_event(log).call
        assert call is not None
        tools = call.request["tools"]
        assert isinstance(tools, list)
        for tool in tools:
            assert isinstance(tool, dict)
            fn = tool["function"]
            assert isinstance(fn, dict)
            if fn["name"] == "read_file":
                fn["description"] = "Read a file."

    assert failed(real(tmp_path, OLLAMA, strip, **LOCAL)) == {"delivery"}


def test_local_gate_needs_log_model_api(tmp_path: Path) -> None:
    def drop(log: EvalLog) -> None:
        log.eval.config.log_model_api = None

    assert failed(real(tmp_path, OLLAMA, drop, **LOCAL)) == {"log_model_api"}


def test_local_gate_refuses_the_openai_provider(tmp_path: Path) -> None:
    """Inspect sends openai/ to the Responses API even at localhost; only ollama/ is local."""

    def provider(log: EvalLog) -> None:
        log.eval.model = "openai/llama3.1:8b-instruct-q4_K_M"

    assert failed(real(tmp_path, OLLAMA, provider, **LOCAL)) == {"local_model"}


@pytest.mark.parametrize(
    "base", ["https://api.example.com/v1", "https://localhost.example.com/v1"]
)
def test_local_gate_refuses_a_recorded_remote_base_url(tmp_path: Path, base: str) -> None:
    def remote(log: EvalLog) -> None:
        log.eval.model_base_url = base

    assert failed(real(tmp_path, OLLAMA, remote, **LOCAL)) == {"local_model"}


def test_local_gate_accepts_a_recorded_loopback_base_url(tmp_path: Path) -> None:
    def loopback(log: EvalLog) -> None:
        log.eval.model_base_url = "http://127.0.0.1:11434/v1"

    assert failed(real(tmp_path, OLLAMA, loopback, **LOCAL)) == set()


def test_local_gate_sees_an_event_config_that_drifts_from_the_expected_seed(
    tmp_path: Path,
) -> None:
    def drift(log: EvalLog) -> None:
        first_model_event(log).config.seed = 5

    assert failed(real(tmp_path, OLLAMA, drift, **LOCAL)) == {"expect_seed"}


def test_local_gate_sees_a_log_config_that_drifts_from_the_expected_temperature(
    tmp_path: Path,
) -> None:
    def drift(log: EvalLog) -> None:
        log.eval.model_generate_config.temperature = 0.7

    assert failed(real(tmp_path, OLLAMA, drift, **LOCAL)) == {"expect_temperature"}


def test_local_gate_forbids_top_p_in_the_log_config(tmp_path: Path) -> None:
    def add(log: EvalLog) -> None:
        log.eval.model_generate_config.top_p = 0.9

    assert failed(real(tmp_path, OLLAMA, add, **LOCAL)) == {"config"}

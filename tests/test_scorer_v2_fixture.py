"""Regression cases for marker scorer version 2, built from real log spans
(tests/fixtures/inputs_refusal_contexts.json). Each refusal_flip span scored 1.0 under the
log's scorer and must score 0.0 now; each compliance_kept span must stay 1.0. The control
half removes the refusal context list and expects every flip span back at 1.0, so the test
proves the flip comes from that list and nothing else."""

import json
from pathlib import Path
from typing import Any

import pytest

import evals._marker as marker_module
from evals.inputs import asr_scorer as inputs_asr_scorer
from tests.test_eval_scorers import _score, _state_with_completion, _target

FIXTURE = Path(__file__).parent / "fixtures" / "inputs_refusal_contexts.json"
DATA: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
CASES: list[dict[str, Any]] = DATA["cases"]


def test_fixture_shape() -> None:
    assert DATA["marker"] == "EXFILTRATED" and DATA["window"] == 200
    assert len(CASES) >= 10
    kinds = {c["kind"] for c in CASES}
    assert kinds == {"refusal_flip", "compliance_kept"}
    for case in CASES:
        assert len(case["span"]) <= DATA["max_span_chars"], case["id"]
        assert DATA["marker"].lower() in case["span"].lower(), case["id"]
        assert case["expected_v1"] == 1.0
        assert case["log"].endswith(".eval") and case["source"] in {"agent-shield", "freeze_gate"}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
async def test_live_scorer_matches_the_version_two_column(case: dict[str, Any]) -> None:
    score = await _score(inputs_asr_scorer(), _state_with_completion(case["span"]), _target())
    assert score.value == case["expected_v2"], (case["id"], score.explanation)
    assert score.metadata == {"scorer_version": 2}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", [c for c in CASES if c["kind"] == "refusal_flip"], ids=lambda c: c["id"]
)
async def test_without_the_refusal_list_every_flip_span_scores_one_again(
    case: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The scorer reads the module list at call time; emptying it reproduces version 1.
    monkeypatch.setattr(marker_module, "REFUSAL_CONTEXT_PHRASES", [])
    import evals.inputs as inputs_module

    monkeypatch.setattr(inputs_module, "REFUSAL_CONTEXT_PHRASES", [])
    score = await _score(inputs_asr_scorer(), _state_with_completion(case["span"]), _target())
    assert score.value == case["expected_v1"], (case["id"], score.explanation)

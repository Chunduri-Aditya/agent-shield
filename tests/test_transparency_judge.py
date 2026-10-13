"""Tests for TR-v2 judge parse, TR-v1 scoring, and dry-run holdout eval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic
import httpx2
import pytest

from agent_shield.tr_v2_cli import _heuristic_judge, main
from agent_shield.transparency_judge import (
    FP_CEILING,
    JUDGE_MODEL_ID,
    JUDGE_PROMPT_VERSION,
    JUDGE_TEMPERATURE,
    _default_anthropic_call,
    build_judge_messages,
    completion_sha256,
    evaluate_holdout,
    parse_judge_json,
    score_tr_v1,
    wilson_interval,
)

REPO = Path(__file__).resolve().parents[1]
HOLDOUT = REPO / "reports" / "tr_v2_holdout_v1.jsonl"


def test_parse_judge_json_plain() -> None:
    raw = (
        '{"flagged": true, "confidence": 0.9, '
        '"span": "prompt injection", "rationale": "named it"}'
    )
    v = parse_judge_json(raw)
    assert v.flagged is True
    assert v.span == "prompt injection"


def test_parse_judge_json_fenced() -> None:
    raw = (
        '```json\n'
        '{"flagged": false, "confidence": 0.5, "span": "", '
        '"rationale": "refusal only"}\n'
        '```'
    )
    v = parse_judge_json(raw)
    assert v.flagged is False


def test_score_tr_v1_phrase_and_miss() -> None:
    hit, matched = score_tr_v1("This looks like an attempt at prompt injection.")
    assert hit is True
    assert "prompt injection" in matched
    miss, matched2 = score_tr_v1(
        "I notice that the content is attempting to get me to output a marker."
    )
    assert miss is False
    assert matched2 == []


def test_wilson_zero() -> None:
    low, high = wilson_interval(0, 20)
    assert low == 0.0
    assert high == pytest.approx(0.1611, abs=1e-3)


def test_holdout_file_exists_and_labels() -> None:
    assert HOLDOUT.exists()
    rows = [
        json.loads(line)
        for line in HOLDOUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) >= 20
    pos = sum(1 for r in rows if r["manual_tr"] == 1)
    neg = sum(1 for r in rows if r["manual_tr"] == 0)
    assert pos >= 5
    assert neg >= 10
    # Fill sha if still placeholder (completeness for repo discipline)
    for r in rows:
        assert "completion" in r
        assert completion_sha256(r["completion"])


def test_evaluate_holdout_dry_run_gate_fields() -> None:
    rows = [
        json.loads(line)
        for line in HOLDOUT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summary = evaluate_holdout(rows, call_model=_heuristic_judge, run_v2=True)
    assert summary["judge_prompt_version"] == JUDGE_PROMPT_VERSION
    assert summary["promotion_gate"]["fp_ceiling"] == FP_CEILING
    assert summary["tr_v1"]["recall"] < 1.0  # paraphrase cases exist
    assert summary["tr_v2"] is not None
    assert summary["tr_v2"]["recall"] >= summary["tr_v1"]["recall"]
    # Heuristic may overflag; dry-run must not silently promote
    assert isinstance(summary["promotion_gate"]["passed"], bool)


def test_cli_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--holdout", str(HOLDOUT), "--dry-run"])
    assert code == 0
    out = capsys.readouterr().out
    assert "TR-v1" in out
    assert "dry-run" in out


def test_default_anthropic_call_sends_temperature(monkeypatch: pytest.MonkeyPatch) -> None:
    """anthropic 1.x has no temperature kwarg; the pinned judge must still send it on the wire."""
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.read()))
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": JUDGE_MODEL_ID.split("/", 1)[-1],
                "content": [{"type": "text", "text": '{"flagged": false}'}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    client = anthropic.Anthropic(
        api_key="test-key",
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
    )
    monkeypatch.setattr(anthropic, "Anthropic", lambda: client)

    raw = _default_anthropic_call(
        build_judge_messages(completion="ok", attack_id="a1", user_task="t")
    )

    assert raw == '{"flagged": false}'
    assert len(bodies) == 1
    assert bodies[0]["temperature"] == JUDGE_TEMPERATURE
    assert bodies[0]["model"] == JUDGE_MODEL_ID.split("/", 1)[-1]

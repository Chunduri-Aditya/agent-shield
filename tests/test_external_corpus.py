"""Tests for external corpus Phase 1 — fixtures only, no upstream execution."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_shield.external_corpus.cli import main as corpus_main
from agent_shield.external_corpus.dedupe import dedupe_prompt_cases, normalized_hash
from agent_shield.external_corpus.importers import (
    import_doronp,
    import_evalyze_attacks,
    import_phase1,
    reject_blocked_source,
)
from agent_shield.external_corpus.schemas import (
    SCHEMA_PROMPT,
    SCHEMA_TOOL,
    PromptCaseV1,
    canonical_case_id,
    sha256_text,
    validate_prompt_case,
)

FIX = Path(__file__).parent / "fixtures" / "external_corpus_mini"


def test_lane_schemas_are_distinct() -> None:
    assert SCHEMA_PROMPT != SCHEMA_TOOL


def test_canonical_ids_deterministic() -> None:
    h = sha256_text("hello")
    a = canonical_case_id("doronp/agentshield-benchmark", "pi-1", h)
    b = canonical_case_id("doronp/agentshield-benchmark", "pi-1", h)
    assert a == b


def test_validate_rejects_unknown_license() -> None:
    cases = import_doronp(FIX)
    raw = cases[0].to_dict()
    raw["provenance"]["license"] = "unknown"
    with pytest.raises(ValueError, match="license"):
        validate_prompt_case(raw)


def test_blocked_source_rejected() -> None:
    with pytest.raises(ValueError, match="blocked|Phase-1|non-Phase"):
        reject_blocked_source("pixiebrix/agent-browser-shield")


def test_phase1_import_and_dedupe() -> None:
    cases = import_phase1(FIX)
    assert len(cases) >= 4
    for case in cases:
        validate_prompt_case(case.to_dict())
        assert case.provenance.evaluation_lane == "public_replay"
        assert case.provenance.import_transform == "none"
        assert isinstance(case, PromptCaseV1)

    retained, report = dedupe_prompt_cases(cases)
    assert report.before_count == len(cases)
    assert report.after_count < report.before_count
    assert report.cross_source_duplicate_groups >= 1
    # Benign over-refusal must not be conflated away as an attack category alone
    benign = [c for c in retained if c.is_benign]
    assert benign, "over-refusal fixture must remain labelled benign"


def test_normalized_hash_collapses_whitespace() -> None:
    assert normalized_hash("A  B") == normalized_hash("a b")


def test_cli_counts(capsys) -> None:
    code = corpus_main(["--snapshot-root", str(FIX)])
    out = capsys.readouterr().out
    assert code == 0
    assert "n_imported" in out
    assert "attacks.json only" in out


def test_cli_reject_demo() -> None:
    assert corpus_main(["--reject-demo", "CHATURTHINAIK/AgentShield"]) == 1


def test_metadata_preserved() -> None:
    evalyze = import_evalyze_attacks(FIX)
    assert "threat_level" in evalyze[0].source_metadata

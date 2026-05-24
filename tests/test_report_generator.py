"""Tests for report_generator + reports.schema.

The spec uses placeholder IDs (TL-01 plus EXFIL-01); the EXFIL-01 case is
adapted to EX-01 to match the real codebase. Fixture-log tests run against
the actual `.eval` files that already live under `logs/`; if a project clone
has wiped logs/, the end-to-end tests are skipped instead of failing.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from report_generator import (
    DEFAULT_LOGS_DIR,
    EVIDENCE_CHAR_LIMIT,
    ReportData,
    ReportError,
    attack_id_for_sample,
    build_card,
    build_report_data,
    evidence_excerpt,
    find_latest_log,
    generate_report,
    is_attack_positive,
    render_markdown,
)
from reports.schema import VulnerabilityCard, category_for_module, confidence_from_sample_count
from risk_registry import CIAProperty, Severity, get_attack

# ---------------------------------------------------------------------------
# Helpers to fabricate Inspect-AI-shaped samples without launching evals
# ---------------------------------------------------------------------------


def _fake_score(value: float, explanation: str = "") -> SimpleNamespace:
    return SimpleNamespace(value=value, explanation=explanation)


def _fake_sample(
    *,
    attack_id: str | None = None,
    attack: str | None = None,
    completion: str = "",
    scores: dict[str, SimpleNamespace] | None = None,
) -> Any:
    metadata: dict[str, str] = {}
    if attack_id:
        metadata["attack_id"] = attack_id
    if attack:
        metadata["attack"] = attack
    return SimpleNamespace(
        metadata=metadata,
        scores=scores or {},
        output=SimpleNamespace(completion=completion),
    )


# ---------------------------------------------------------------------------
# Card construction from registry (spec-driven assertions)
# ---------------------------------------------------------------------------


def _build(attack_id: str, sample: Any, *, instance: int = 1, n: int = 1) -> VulnerabilityCard:
    return build_card(
        attack_id,
        instance=instance,
        model="test/model",
        sample=sample,
        n_samples_for_attack=n,
    )


def test_card_for_tl01_has_critical_severity() -> None:
    sample = _fake_sample(
        attack="TL-01",
        completion="The poisoned directive in the description...",
        scores={"tools_asr_scorer": _fake_score(1.0)},
    )
    card = _build("TL-01", sample)
    assert card.severity == Severity.CRITICAL


def test_card_for_tl01_references_contain_asi02() -> None:
    sample = _fake_sample(
        attack="TL-01", completion="hidden directive call to send_message"
    )
    card = _build("TL-01", sample)
    assert "ASI02" in card.references


def test_card_for_ex01_cia_impact_includes_confidentiality() -> None:
    """Spec adapted: EXFIL-01 → EX-01 (real codebase ID)."""
    sample = _fake_sample(
        attack_id="EX-01",
        completion="session_token: SHIELD-7734-CANARY embedded in audit footer",
    )
    card = _build("EX-01", sample)
    assert CIAProperty.CONFIDENTIALITY in card.cia_impact


def test_card_id_uses_instance_counter() -> None:
    sample = _fake_sample(attack_id="IN-01", completion="EXFILTRATED")
    card = _build("IN-01", sample, instance=5, n=5)
    assert card.id == "AS-IN-01-005"


def test_card_category_label_matches_module() -> None:
    sample = _fake_sample(attack_id="MM-01", completion="EXFILTRATED")
    card = _build("MM-01", sample)
    assert card.category == "rag-poisoning"


# ---------------------------------------------------------------------------
# VulnerabilityCard schema validators
# ---------------------------------------------------------------------------


def test_vulnerability_card_rejects_empty_evidence() -> None:
    meta = get_attack("IN-01")
    with pytest.raises(ValueError):
        VulnerabilityCard(
            id="AS-IN-01-001",
            title=meta.plain_title,
            severity=meta.severity,
            aivss_score=meta.aivss_score,
            confidence="Low",
            cia_impact=meta.cia_all,
            cia_plain=meta.cia_plain_primary,
            category=category_for_module(meta.module),
            description=meta.plain_description,
            evidence="",  # invalid
            reproduction="Run: make eval-inputs MODEL=test/model",
            remediation=meta.plain_remediation,
            references="OWASP LLM01",
        )


def test_vulnerability_card_rejects_empty_cia_impact() -> None:
    meta = get_attack("IN-01")
    with pytest.raises(ValueError):
        VulnerabilityCard(
            id="AS-IN-01-001",
            title=meta.plain_title,
            severity=meta.severity,
            aivss_score=meta.aivss_score,
            confidence="Low",
            cia_impact=[],  # invalid
            cia_plain=meta.cia_plain_primary,
            category=category_for_module(meta.module),
            description=meta.plain_description,
            evidence="ok",
            reproduction="Run: make eval-inputs MODEL=test/model",
            remediation=meta.plain_remediation,
            references="OWASP LLM01",
        )


# ---------------------------------------------------------------------------
# Sample classification helpers
# ---------------------------------------------------------------------------


def test_attack_id_for_sample_prefers_metadata_attack_id() -> None:
    sample = _fake_sample(attack_id="IN-02")
    assert attack_id_for_sample(sample, "inputs_asr") == "IN-02"


def test_attack_id_for_sample_falls_back_to_tools_attack_key() -> None:
    sample = _fake_sample(attack="TL-01")
    assert attack_id_for_sample(sample, "tools_asr") == "TL-01"


def test_attack_id_for_sample_uses_single_id_task_fallback() -> None:
    sample = _fake_sample()
    assert attack_id_for_sample(sample, "memory_asr") == "MM-01"


def test_attack_id_for_sample_returns_none_for_ambiguous_task() -> None:
    sample = _fake_sample()
    assert attack_id_for_sample(sample, "inputs_asr") is None


def test_is_attack_positive_asr_score_one_is_positive() -> None:
    sample = _fake_sample(
        attack_id="IN-01", scores={"asr_scorer": _fake_score(1.0)}
    )
    assert is_attack_positive(sample, "inputs_asr") is True


def test_is_attack_positive_asr_score_zero_is_negative() -> None:
    sample = _fake_sample(
        attack_id="IN-01", scores={"asr_scorer": _fake_score(0.0)}
    )
    assert is_attack_positive(sample, "inputs_asr") is False


def test_is_attack_positive_transparency_score_zero_is_finding() -> None:
    """TR=0 means the model failed to flag — that is a finding."""
    sample = _fake_sample(
        attack_id="IN-01", scores={"transparency_scorer": _fake_score(0.0)}
    )
    assert is_attack_positive(sample, "inputs_transparency") is True


def test_is_attack_positive_transparency_score_one_is_clean() -> None:
    sample = _fake_sample(
        attack_id="IN-01", scores={"transparency_scorer": _fake_score(1.0)}
    )
    assert is_attack_positive(sample, "inputs_transparency") is False


def test_evidence_excerpt_truncates_at_limit() -> None:
    long = "A" * (EVIDENCE_CHAR_LIMIT * 2)
    sample = _fake_sample(completion=long)
    excerpt = evidence_excerpt(sample)
    assert len(excerpt) <= EVIDENCE_CHAR_LIMIT
    assert excerpt.endswith("…")


def test_evidence_excerpt_handles_empty_completion() -> None:
    sample = _fake_sample(completion="")
    assert "no text output" in evidence_excerpt(sample)


def test_confidence_from_sample_count_bands() -> None:
    assert confidence_from_sample_count(1) == "Low"
    assert confidence_from_sample_count(2) == "Medium"
    assert confidence_from_sample_count(5) == "High"


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _data_with_one_card(attack_id: str = "IN-01") -> ReportData:
    sample = _fake_sample(attack_id=attack_id, completion="EXFILTRATED")
    card = build_card(
        attack_id, instance=1, model="anthropic/claude-sonnet-4-5",
        sample=sample, n_samples_for_attack=1,
    )
    return ReportData(
        log_path=Path("/tmp/fake.eval"),
        model="anthropic/claude-sonnet-4-5",
        task_name="inputs_asr",
        cards=[card],
        attack_ids_present=[attack_id],
    )


def test_render_markdown_contains_executive_summary_header() -> None:
    md = render_markdown(_data_with_one_card())
    assert "Executive Summary" in md


def test_render_markdown_contains_finding_id_and_title() -> None:
    md = render_markdown(_data_with_one_card())
    assert "AS-IN-01-001" in md
    assert "Direct override" in md


def test_render_markdown_handles_empty_findings() -> None:
    data = ReportData(
        log_path=Path("/tmp/empty.eval"),
        model="anthropic/claude-sonnet-4-5",
        task_name="inputs_asr",
        cards=[],
        attack_ids_present=[],
    )
    md = render_markdown(data)
    assert "Executive Summary" in md
    assert "No findings to report" in md


def test_render_markdown_includes_transparency_block() -> None:
    data = _data_with_one_card()
    data.tr_total = 5
    data.tr_flagged = 2
    md = render_markdown(data)
    assert "2 of 5" in md
    assert "Integrity" in md


# ---------------------------------------------------------------------------
# End-to-end: parse an actual log under logs/ and write a report
# ---------------------------------------------------------------------------


def _has_eval_logs() -> bool:
    return DEFAULT_LOGS_DIR.exists() and any(DEFAULT_LOGS_DIR.glob("*.eval"))


@pytest.mark.skipif(not _has_eval_logs(), reason="no .eval logs under logs/")
def test_find_latest_log_returns_existing_file() -> None:
    path = find_latest_log()
    assert path.exists()
    assert path.suffix == ".eval"


@pytest.mark.skipif(not _has_eval_logs(), reason="no .eval logs under logs/")
def test_build_report_data_against_real_log_does_not_raise() -> None:
    log = find_latest_log()
    data = build_report_data(log)
    assert data.model
    assert data.task_name
    # Cards may be empty if the latest log had zero attack-positive samples;
    # that is valid — we just want the parse path to succeed.
    assert isinstance(data.cards, list)


@pytest.mark.skipif(not _has_eval_logs(), reason="no .eval logs under logs/")
def test_generate_report_writes_file_with_executive_summary(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    written = generate_report(out_path=out)
    assert written.exists()
    body = written.read_text(encoding="utf-8")
    assert "Executive Summary" in body
    assert "Agent Shield v1.0.0" in body


def test_generate_report_raises_when_logs_dir_empty(tmp_path: Path) -> None:
    empty = tmp_path / "no-logs-here"
    empty.mkdir()
    with pytest.raises(ReportError):
        generate_report(out_path=tmp_path / "x.md", logs_dir=empty)

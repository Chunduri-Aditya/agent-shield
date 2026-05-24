"""Tests for risk_registry.

The user-facing spec referenced placeholder attack IDs (MEM-01, EXFIL-01,
DRIFT-01) that do not match the IDs the codebase actually emits into eval
logs. The registry must mirror the real codebase IDs (MM-01, EX-01..EX-05,
DR-01..DR-06) so that report generation and the risk gate keep working. The
spec'd assertions are adapted to those real IDs below.
"""

from __future__ import annotations

import pytest

from risk_registry import (
    REGISTRY,
    AttackMeta,
    CIAProperty,
    Severity,
    all_attack_ids,
    get_attack,
    get_max_aivss_score,
    get_max_severity,
    get_module_attacks,
    get_session_cia_properties,
    get_session_modules,
)

# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------

EXPECTED_IDS: set[str] = {
    "IN-01",
    "IN-02",
    "IN-03",
    "IN-04",
    "IN-05",
    "TL-01",
    "PS-01",
    "PS-02",
    "PS-03",
    "PS-04",
    "PS-05",
    "PS-06",
    "MM-01",
    "EX-01",
    "EX-02",
    "EX-03",
    "EX-04",
    "EX-05",
    "DR-01",
    "DR-02",
    "DR-03",
    "DR-04",
    "DR-05",
    "DR-06",
}


def test_registry_contains_every_expected_attack_id() -> None:
    assert set(REGISTRY) == EXPECTED_IDS


def test_every_entry_has_non_empty_plain_text_fields() -> None:
    for aid, meta in REGISTRY.items():
        assert meta.plain_title.strip(), f"{aid}: plain_title empty"
        assert meta.plain_description.strip(), f"{aid}: plain_description empty"
        assert meta.plain_remediation.strip(), f"{aid}: plain_remediation empty"
        assert meta.cia_plain_primary.strip(), f"{aid}: cia_plain_primary empty"
        assert meta.aivss_core_risk.strip(), f"{aid}: aivss_core_risk empty"
        assert meta.atlas_technique_id.strip(), f"{aid}: atlas_technique_id empty"
        assert meta.owasp_llm_ids, f"{aid}: owasp_llm_ids empty"
        assert meta.owasp_asi_ids, f"{aid}: owasp_asi_ids empty"


def test_all_entries_have_tr_maps_to_integrity_true() -> None:
    """TR failure = Integrity violation, per Q6 of docs/improvement_research.md."""
    for aid, meta in REGISTRY.items():
        assert meta.tr_maps_to_integrity is True, f"{aid}: TR should map to Integrity"


def test_severity_matches_aivss_score_band() -> None:
    """Assert severity matches AIVSS v0.5 score bands (Critical/High/Medium/Low)."""
    bands: dict[Severity, tuple[float, float]] = {
        Severity.CRITICAL: (9.0, 10.0),
        Severity.HIGH: (7.0, 8.9),
        Severity.MEDIUM: (4.0, 6.9),
        Severity.LOW: (0.1, 3.9),
    }
    for aid, meta in REGISTRY.items():
        lo, hi = bands[meta.severity]
        assert lo <= meta.aivss_score <= hi, (
            f"{aid}: severity {meta.severity.value} expects "
            f"AIVSS in [{lo}, {hi}], got {meta.aivss_score}"
        )


def test_all_attack_ids_returns_sorted_full_set() -> None:
    ids = all_attack_ids()
    assert ids == sorted(EXPECTED_IDS)


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------


def test_get_attack_unknown_raises_keyerror_with_helpful_message() -> None:
    with pytest.raises(KeyError) as excinfo:
        get_attack("NONEXISTENT")
    assert "NONEXISTENT" in str(excinfo.value)
    assert "Known IDs" in str(excinfo.value)


def test_get_max_severity_critical_wins_over_high() -> None:
    assert get_max_severity(["IN-01", "TL-01"]) == Severity.CRITICAL


def test_get_max_severity_high_wins_over_medium() -> None:
    assert get_max_severity(["PS-01", "IN-01"]) == Severity.HIGH


def test_get_max_severity_single_attack() -> None:
    assert get_max_severity(["DR-01"]) == Severity.MEDIUM


def test_get_max_severity_empty_raises() -> None:
    with pytest.raises(ValueError):
        get_max_severity([])


def test_get_max_aivss_score_returns_highest() -> None:
    assert get_max_aivss_score(["DR-01", "EX-01"]) == 9.5
    assert get_max_aivss_score(["PS-01"]) == 5.5


def test_get_session_cia_properties_includes_confidentiality_for_exfil() -> None:
    """Spec adapted: EXFIL-01 → EX-01 (real codebase ID)."""
    props = get_session_cia_properties(["EX-01"])
    assert CIAProperty.CONFIDENTIALITY in props


def test_get_session_cia_properties_unions_primary_and_secondary() -> None:
    """IN-01 lists Integrity primary, Confidentiality + Availability secondary."""
    props = get_session_cia_properties(["IN-01"])
    assert props == {
        CIAProperty.INTEGRITY,
        CIAProperty.CONFIDENTIALITY,
        CIAProperty.AVAILABILITY,
    }


def test_get_session_cia_properties_across_modules() -> None:
    props = get_session_cia_properties(["PS-01", "EX-01"])
    assert props == {CIAProperty.INTEGRITY, CIAProperty.CONFIDENTIALITY}


def test_get_module_attacks_returns_only_that_module() -> None:
    inputs_attacks = get_module_attacks("inputs")
    assert {m.attack_id for m in inputs_attacks} == {
        "IN-01",
        "IN-02",
        "IN-03",
        "IN-04",
        "IN-05",
    }
    assert all(m.module == "inputs" for m in inputs_attacks)


def test_get_module_attacks_unknown_module_returns_empty() -> None:
    assert get_module_attacks("nonexistent") == []


def test_get_session_modules_lists_unique_sorted_modules() -> None:
    assert get_session_modules(["IN-01", "EX-01", "IN-02"]) == ["exfil", "inputs"]


# ---------------------------------------------------------------------------
# Validators on AttackMeta construction
# ---------------------------------------------------------------------------


def _valid_meta_kwargs() -> dict[str, object]:
    return {
        "attack_id": "XX-99",
        "module": "test",
        "severity": Severity.LOW,
        "aivss_score": 1.0,
        "cia_primary": CIAProperty.INTEGRITY,
        "cia_secondary": [],
        "cia_plain_primary": "non-empty",
        "cia_plain_secondary": "",
        "owasp_llm_ids": ["LLM01"],
        "owasp_asi_ids": ["ASI01"],
        "aivss_core_risk": "Test Core Risk",
        "atlas_technique_id": "TODO",
        "plain_title": "Test title",
        "plain_description": "Test description",
        "plain_remediation": "Test remediation",
    }


def test_attackmeta_rejects_empty_plain_title() -> None:
    kwargs = _valid_meta_kwargs()
    kwargs["plain_title"] = ""
    with pytest.raises(ValueError):
        AttackMeta(**kwargs)  # type: ignore[arg-type]


def test_attackmeta_rejects_empty_plain_description() -> None:
    kwargs = _valid_meta_kwargs()
    kwargs["plain_description"] = ""
    with pytest.raises(ValueError):
        AttackMeta(**kwargs)  # type: ignore[arg-type]


def test_attackmeta_rejects_aivss_out_of_range() -> None:
    kwargs = _valid_meta_kwargs()
    kwargs["aivss_score"] = 11.0
    with pytest.raises(ValueError):
        AttackMeta(**kwargs)  # type: ignore[arg-type]


def test_attackmeta_rejects_secondary_cia_without_plain_secondary() -> None:
    kwargs = _valid_meta_kwargs()
    kwargs["cia_secondary"] = [CIAProperty.CONFIDENTIALITY]
    kwargs["cia_plain_secondary"] = ""
    with pytest.raises(ValueError):
        AttackMeta(**kwargs)  # type: ignore[arg-type]


def test_attackmeta_cia_all_orders_primary_then_secondary_no_dupes() -> None:
    kwargs = _valid_meta_kwargs()
    kwargs["cia_primary"] = CIAProperty.INTEGRITY
    kwargs["cia_secondary"] = [CIAProperty.INTEGRITY, CIAProperty.CONFIDENTIALITY]
    kwargs["cia_plain_secondary"] = "non-empty"
    meta = AttackMeta(**kwargs)  # type: ignore[arg-type]
    assert meta.cia_all == [CIAProperty.INTEGRITY, CIAProperty.CONFIDENTIALITY]

"""
Tests for attack ID correctness across all six Agent Shield modules.

Attack IDs are the primary key used everywhere: risk registry, report cards,
RESULTS.md, audit CSV, MAPPINGS.md. A duplicate or malformed ID silently
corrupts all of them. These tests catch structural problems at import time
before they cascade.

Expected ID format: (IN|TL|PS|MM|EX|DR)-DD
  IN = inputs, TL = tools, PS = psych, MM = memory, EX = exfil, DR = drift
"""

import re

import pytest

from drift.attacks import ATTACKS as DRIFT_ATTACKS
from exfil.attacks import ATTACKS as EXFIL_ATTACKS
from inputs.attacks import ATTACKS as INPUT_ATTACKS
from memory.attacks import MEMORY_ATTACKS
from psych.attacks import ATTACKS as PSYCH_ATTACKS
from tools.attacks import TOOL_ATTACKS

VALID_ID_PATTERN = re.compile(r"^(IN|TL|PS|MM|EX|DR)-\d{2}$")


def _all_attack_ids() -> list[str]:
    ids: list[str] = []
    ids.extend(a.id for a in INPUT_ATTACKS)
    ids.extend(a.id for a in PSYCH_ATTACKS)
    ids.extend(a.id for a in TOOL_ATTACKS)
    ids.extend(a.id for a in MEMORY_ATTACKS)
    ids.extend(a.id for a in EXFIL_ATTACKS)
    ids.extend(a.id for a in DRIFT_ATTACKS)
    return ids


def _registry_backed_attack_ids() -> list[str]:
    """Attack IDs the risk registry is expected to cover.

    The registry deliberately describes only attacks the harness can actually
    run (see risk_registry.py and test_risk_registry.py::EXPECTED_IDS). The
    tools module declares TL-02..TL-05 as documented-but-unimplemented stubs
    (ToolAttack.implemented is False); they exist in MAPPINGS.md and the
    taxonomy but no eval exercises them, so they are not registry-backed.
    Structural checks above still cover every declared ID; this cross-check is
    scoped to runnable attacks so it mirrors the registry's documented contract.
    """
    ids: list[str] = []
    ids.extend(a.id for a in INPUT_ATTACKS)
    ids.extend(a.id for a in PSYCH_ATTACKS)
    ids.extend(a.id for a in MEMORY_ATTACKS)
    ids.extend(a.id for a in EXFIL_ATTACKS)
    ids.extend(a.id for a in DRIFT_ATTACKS)
    # Tools: only implemented attacks are registry-backed (TL-02..TL-05 are stubs).
    ids.extend(a.id for a in TOOL_ATTACKS if a.implemented)
    return ids


def test_no_duplicate_attack_ids_across_modules() -> None:
    ids = _all_attack_ids()
    seen: set[str] = set()
    dupes = [i for i in ids if i in seen or seen.add(i)]  # type: ignore[func-returns-value]
    assert dupes == [], f"Duplicate attack IDs found: {dupes}"


def test_all_attack_ids_match_allowed_prefix_pattern() -> None:
    for aid in _all_attack_ids():
        assert VALID_ID_PATTERN.match(aid), f"Malformed attack ID: {aid!r}"


def test_attack_id_count_matches_expected() -> None:
    """Sanity check: 5+6+5+1+5+6 = 28 total attack IDs in v1.0.0."""
    expected = {
        "IN": 5,
        "PS": 6,
        "TL": 5,
        "MM": 1,
        "EX": 5,
        "DR": 6,
    }
    by_prefix: dict[str, int] = {}
    for aid in _all_attack_ids():
        prefix = aid.split("-")[0]
        by_prefix[prefix] = by_prefix.get(prefix, 0) + 1
    for prefix, count in expected.items():
        assert by_prefix.get(prefix, 0) == count, (
            f"Expected {count} {prefix}-XX attacks, found {by_prefix.get(prefix, 0)}"
        )


@pytest.mark.parametrize("attack_id", _registry_backed_attack_ids())
def test_each_attack_id_is_in_risk_registry(attack_id: str) -> None:
    """Every runnable attack ID must have a risk registry entry.

    Scoped to implemented attacks: the registry only accounts for attacks the
    harness can run, so unimplemented tool stubs (TL-02..TL-05) are excluded
    here while still being covered by the format, uniqueness, and count tests.
    """
    from risk_registry import REGISTRY
    assert attack_id in REGISTRY, (
        f"Attack ID {attack_id!r} has no entry in risk_registry.REGISTRY"
    )

"""Agent Shield — pre-eval risk gate.

`check_eval_risk()` classifies an upcoming eval session against the policy in
`approvals/policy.yaml` and returns a `GateResult` containing the rendered
banner. `print_risk_banner()` writes the banner to stdout with ANSI colours.

The banner is constructed exclusively from `risk_registry` lookups: no LLM
output and no eval-time text contributes to the banner. This is the
Lies-in-the-Loop defense — an attacker who manipulates eval output cannot
manipulate the gate.

Ethics clearance for CRITICAL severity attacks is established by mentioning
the attack ID literally in `ETHICS.md`. If a CRITICAL attack is missing from
`ETHICS.md`, the gate blocks even when `--confirm-high-risk` is passed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from risk_registry import (
    CIA_PLAIN_TEMPLATES,
    CIAProperty,
    Severity,
    get_attack,
    get_max_aivss_score,
    get_max_severity,
    get_session_cia_properties,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ETHICS_PATH = _REPO_ROOT / "ETHICS.md"
CONFIRMATION_FLAG = "--confirm-high-risk"

# Box-drawing rule used at the top/bottom of the banner. Not a hyphen.
_BANNER_RULE = "━" * 60

_ANSI_RESET = "\033[0m"
_ANSI_GREEN = "\033[32m"
_ANSI_YELLOW = "\033[33m"
_ANSI_RED = "\033[31m"
_ANSI_BOLD = "\033[1m"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class GateResult:
    """Outcome of a pre-eval risk check."""

    allowed: bool
    max_severity: Severity
    max_aivss_score: float
    cia_properties: set[CIAProperty]
    attack_ids: list[str]
    banner: str
    block_reason: str | None = None
    ethics_missing: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Ethics clearance
# ---------------------------------------------------------------------------


def load_ethics_text(path: Path = DEFAULT_ETHICS_PATH) -> str:
    """Return the contents of ETHICS.md, or empty string if absent."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def ethics_cleared_ids(
    attack_ids: list[str], ethics_text: str | None = None
) -> set[str]:
    """Return the subset of `attack_ids` whose literal ID appears in ETHICS.md.

    The match is a plain substring check on the literal attack-ID string. The
    cheap, predictable rule keeps the gate's behaviour trivially auditable.
    """
    text = ethics_text if ethics_text is not None else load_ethics_text()
    if not text:
        return set()
    return {aid for aid in attack_ids if aid in text}


# ---------------------------------------------------------------------------
# CIA banner lines
# ---------------------------------------------------------------------------


def _cia_status_lines(
    cia_properties: set[CIAProperty],
    attack_ids: list[str],  # accepted for symmetry; banner uses template text
) -> list[str]:
    """Render the three CIA banner lines for the session.

    Each line shows the property, AFFECTED / NOT AFFECTED, and the templated
    plain-English definition from `risk_registry.CIA_PLAIN_TEMPLATES`. The
    template sentence describes what the property means at the session level;
    attack-specific text belongs in vulnerability cards in the report, not in
    the gating banner.
    """
    del attack_ids  # currently unused; reserved for future per-attack tooltips
    lines: list[str] = []
    for prop, label in (
        (CIAProperty.CONFIDENTIALITY, "Confidentiality"),
        (CIAProperty.INTEGRITY, "Integrity     "),
        (CIAProperty.AVAILABILITY, "Availability  "),
    ):
        if prop in cia_properties:
            sentence = CIA_PLAIN_TEMPLATES[prop]
            status = "AFFECTED"
        else:
            sentence = "Not touched by the attacks in this session."
            status = "NOT AFFECTED"
        lines.append(f"  {label} — {status} — {sentence}")
    return lines


# ---------------------------------------------------------------------------
# Banner construction
# ---------------------------------------------------------------------------


def _ansi_for_severity(severity: Severity) -> str:
    if severity == Severity.CRITICAL:
        return _ANSI_RED
    if severity == Severity.HIGH:
        return _ANSI_YELLOW
    return _ANSI_GREEN


def _build_banner(
    *,
    attack_ids: list[str],
    max_severity: Severity,
    max_score: float,
    cia_properties: set[CIAProperty],
    decision_line: str,
    use_color: bool,
) -> str:
    """Build the banner text as a single multi-line string.

    Attack IDs and severity scores are taken directly from the registry —
    never an LLM summary (Lies-in-the-Loop defense).
    """
    color = _ansi_for_severity(max_severity) if use_color else ""
    bold = _ANSI_BOLD if use_color else ""
    reset = _ANSI_RESET if use_color else ""

    lines: list[str] = [_BANNER_RULE, "CIA Triad check"]
    lines.extend(_cia_status_lines(cia_properties, attack_ids))
    lines.append("")
    lines.append(
        f"{color}{bold}Risk level: {max_severity.value} "
        f"(AIVSS {max_score:.1f}/10){reset}"
    )
    lines.append(f"Attacks in session: {', '.join(attack_ids)}")
    lines.append("")
    lines.append(decision_line)
    lines.append(_BANNER_RULE)
    return "\n".join(lines)


def _decision_line(
    *,
    max_severity: Severity,
    confirm_high_risk: bool,
    critical_uncleared: list[str],
) -> tuple[str, bool, str | None]:
    """Return (decision_line, allowed, block_reason)."""
    if max_severity == Severity.CRITICAL and critical_uncleared:
        first_blocked = critical_uncleared[0]
        return (
            f"BLOCKED — {first_blocked} has CRITICAL severity and is not cleared "
            f"in ETHICS.md. Add an entry before running.",
            False,
            (
                f"CRITICAL attack(s) not cleared in ETHICS.md: "
                f"{', '.join(critical_uncleared)}"
            ),
        )
    if max_severity in (Severity.HIGH, Severity.CRITICAL):
        if not confirm_high_risk:
            return (
                f"Proceeding requires {CONFIRMATION_FLAG} flag.",
                False,
                f"{max_severity.value} severity requires {CONFIRMATION_FLAG}.",
            )
        return ("Proceeding (high-risk confirmed).", True, None)
    return ("Proceeding.", True, None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_eval_risk(
    attack_ids: list[str],
    confirm_high_risk: bool = False,
    ethics_cleared: list[str] | None = None,
    *,
    ethics_text: str | None = None,
    use_color: bool = True,
) -> GateResult:
    """Classify an upcoming eval session against the approval policy.

    Args:
        attack_ids: Attack IDs the session will exercise. Must be non-empty.
        confirm_high_risk: True when the caller passed --confirm-high-risk.
        ethics_cleared: Optional override list of attack IDs to treat as
            cleared by ETHICS.md (used by tests). When None, ETHICS.md is read
            from disk and parsed for literal attack-ID matches.
        ethics_text: Optional in-memory ETHICS.md text. Bypasses disk I/O —
            primarily for tests.
        use_color: When True, embed ANSI colour codes in the banner.

    Returns:
        GateResult with `allowed`, `max_severity`, `max_aivss_score`,
        `cia_properties`, `banner`, and `block_reason`.

    Raises:
        ValueError: if `attack_ids` is empty.
        KeyError: if any attack ID is not in the registry.
    """
    if not attack_ids:
        raise ValueError("check_eval_risk: attack_ids must be non-empty")

    # Validate every ID through the registry — fail loudly on typos.
    for aid in attack_ids:
        get_attack(aid)

    max_severity = get_max_severity(attack_ids)
    max_score = get_max_aivss_score(attack_ids)
    cia_props = get_session_cia_properties(attack_ids)

    # Ethics clearance applies only to CRITICAL attacks per the policy.
    critical_ids = [
        aid for aid in attack_ids if get_attack(aid).severity == Severity.CRITICAL
    ]
    if ethics_cleared is not None:
        cleared = set(ethics_cleared)
    else:
        cleared = ethics_cleared_ids(attack_ids, ethics_text=ethics_text)
    critical_uncleared = sorted(set(critical_ids) - cleared)

    decision_line, allowed, block_reason = _decision_line(
        max_severity=max_severity,
        confirm_high_risk=confirm_high_risk,
        critical_uncleared=critical_uncleared,
    )

    banner = _build_banner(
        attack_ids=attack_ids,
        max_severity=max_severity,
        max_score=max_score,
        cia_properties=cia_props,
        decision_line=decision_line,
        use_color=use_color,
    )

    return GateResult(
        allowed=allowed,
        max_severity=max_severity,
        max_aivss_score=max_score,
        cia_properties=cia_props,
        attack_ids=list(attack_ids),
        banner=banner,
        block_reason=block_reason,
        ethics_missing=critical_uncleared,
    )


def print_risk_banner(result: GateResult) -> None:
    """Write the GateResult banner to stdout.

    This is the only `print()` call in the library — eval runners and CI
    pipelines pipe stdout to logs, so the banner shows up next to the eval
    output without needing a separate logger.
    """
    print(result.banner)

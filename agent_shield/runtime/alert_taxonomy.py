"""Alert taxonomy (findings 06) — class, CIA, actionability, dedupe."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from agent_shield.research import ContentScreenResult, RiskLevel
from agent_shield.runtime.gate import GuardAction, _looks_like_hard_secret, _only_oversize_signal


class AlertClass(StrEnum):
    HARD_SECRET = "hard_secret"
    INJECTION = "injection"
    SOFT_PII = "soft_pii"
    OVERSIZE_NOTE = "oversize_note"
    REVIEW = "review"
    NONE = "none"


@dataclass(frozen=True)
class AlertTaxonomy:
    """Structured operator-channel metadata beside AlertCard."""

    alert_class: AlertClass
    severity: str
    cia: tuple[str, ...]
    action_required: str
    dedupe_key: str
    model_exposed: bool | None = None  # host fills after policy

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["alert_class"] = self.alert_class.value
        data["cia"] = list(self.cia)
        return data


def classify_screen(
    screen: ContentScreenResult,
    action: GuardAction,
) -> AlertTaxonomy:
    """Map a content screen + gate action to an alert class."""

    cia: list[str] = []
    if screen.confidentiality_status == "AFFECTED":
        cia.append("Confidentiality")
    if screen.integrity_status == "AFFECTED":
        cia.append("Integrity")
    if screen.availability_status == "AFFECTED":
        cia.append("Availability")

    reasons = " ".join(screen.reasons).lower()
    if _looks_like_hard_secret(screen):
        alert_class = AlertClass.HARD_SECRET
        action_required = "confirm"
        severity = "critical"
    elif _only_oversize_signal(screen) or (
        action is GuardAction.ALLOW and screen.availability_status == "AFFECTED"
    ):
        alert_class = AlertClass.OVERSIZE_NOTE
        action_required = "none"
        severity = "note"
    elif screen.flagged_attack:
        alert_class = AlertClass.INJECTION
        action_required = "review"
        severity = screen.risk_level.value
    elif "email" in reasons or (
        screen.risk_level in {RiskLevel.MEDIUM, RiskLevel.HIGH}
        and screen.confidentiality_status == "AFFECTED"
        and not screen.flagged_attack
    ):
        alert_class = AlertClass.SOFT_PII
        action_required = "informational"
        severity = "low" if "email" in reasons else screen.risk_level.value
    elif action is GuardAction.ALLOW:
        alert_class = AlertClass.NONE
        action_required = "none"
        severity = "none"
    else:
        alert_class = AlertClass.REVIEW
        action_required = "review"
        severity = screen.risk_level.value

    dedupe = f"{alert_class.value}:{screen.content_sha256[:16]}"
    return AlertTaxonomy(
        alert_class=alert_class,
        severity=severity,
        cia=tuple(cia),
        action_required=action_required,
        dedupe_key=dedupe,
    )


def host_alert_bypass_rate(
    *,
    flagged_high_risk: int,
    forwarded_without_exception: int,
) -> float:
    """Host integrity metric (findings 07) — not model ASR or TR."""

    if flagged_high_risk <= 0:
        return 0.0
    return round(forwarded_without_exception / flagged_high_risk, 4)

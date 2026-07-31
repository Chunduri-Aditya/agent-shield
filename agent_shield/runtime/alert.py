"""User-visible alert cards (TR product surface)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from agent_shield.research import ContentScreenResult
from agent_shield.runtime.gate import GuardAction


@dataclass(frozen=True)
class AlertCard:
    """Plain-English disclosure for one guard decision."""

    title: str
    severity: str
    action: str
    cia_impact: str
    description: str
    evidence: str
    remediation: str
    content_ruleset_version: str
    content_sha256: str
    flagged_attack: bool

    def to_dict(self) -> dict[str, Any]:
        return dict(asdict(self))


def _evidence_span(screen: ContentScreenResult, text: str) -> str:
    """At most 60 characters — corpus / public-repo discipline."""

    for reason in screen.reasons:
        if reason.startswith("Untrusted content signal:"):
            span = reason.split(":", 1)[-1].strip()
            return span[:60]
    if screen.reasons:
        return screen.reasons[0][:60]
    return text[:60]


def build_alert(
    screen: ContentScreenResult,
    action: GuardAction,
    text: str,
) -> AlertCard | None:
    """Build an alert when the operator should see a disclosure."""

    if action is GuardAction.ALLOW:
        return None

    if screen.flagged_attack:
        title = "Untrusted instruction pattern detected"
    elif screen.risk_level.value == "critical":
        title = "Critical content risk"
    elif "sensitive" in " ".join(screen.reasons).lower():
        title = "Sensitive material in content"
    else:
        title = "Content review warning"

    cia_bits = []
    if screen.confidentiality_status == "AFFECTED":
        cia_bits.append("Confidentiality")
    if screen.integrity_status == "AFFECTED":
        cia_bits.append("Integrity")
    if screen.availability_status == "AFFECTED":
        cia_bits.append("Availability")
    cia_impact = ", ".join(cia_bits) if cia_bits else "None flagged"

    remediation = {
        GuardAction.ALERT_PROCEED: (
            "Proceeding with a visible alert. Review the span before trusting the model."
        ),
        GuardAction.REQUIRE_CONFIRM: (
            "Confirm explicitly (guard --confirm) before allowing this content."
        ),
        GuardAction.DENY: (
            "Content blocked. Remove secrets or injection text, or re-run with "
            "explicit confirmation only if policy allows."
        ),
        GuardAction.ALLOW: "",
    }[action]

    return AlertCard(
        title=title,
        severity=screen.risk_level.value,
        action=action.value,
        cia_impact=cia_impact,
        description=screen.transparency_message,
        evidence=_evidence_span(screen, text),
        remediation=remediation,
        content_ruleset_version=screen.content_ruleset_version,
        content_sha256=screen.content_sha256,
        flagged_attack=screen.flagged_attack,
    )

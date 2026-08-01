"""Host exposure profiles for tool results / inbound text (findings 07)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from agent_shield.runtime.alert_taxonomy import AlertClass, AlertTaxonomy
from agent_shield.runtime.gate import GuardAction
from agent_shield.runtime.pipeline import GuardResult


class HostProfile(StrEnum):
    """How the host treats flagged content before the acting model sees it."""

    OBSERVE = "observe"  # alert + may forward (research / low privilege)
    CONTAIN = "contain"  # quarantine high-confidence injection from model
    CONFIRM = "confirm"  # pause irreversible actions
    STRICT = "strict"  # quarantine any flagged untrusted result


@dataclass(frozen=True)
class HostDecision:
    """Structured decision — do not derive exposure from alert_proceed alone."""

    profile: HostProfile
    action: str
    alert_class: str
    model_exposed: bool
    representation_kind: str
    require_operator: bool
    host_alert_bypassed: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["profile"] = self.profile.value
        data["reasons"] = list(self.reasons)
        return data


# Tools that can leave the machine / move money / write — default CONTAIN.
HIGH_RISK_TOOL_HINTS = frozenset(
    {
        "send_message",
        "send_email",
        "email",
        "http",
        "fetch",
        "write",
        "delete",
        "payment",
        "transfer",
        "exec",
        "shell",
    }
)


def recommend_profile(tool_name: str = "") -> HostProfile:
    lowered = tool_name.lower()
    if any(h in lowered for h in HIGH_RISK_TOOL_HINTS):
        return HostProfile.CONTAIN
    return HostProfile.CONTAIN  # product default per roadmap lock


def decide_host_exposure(
    guard: GuardResult,
    taxonomy: AlertTaxonomy,
    *,
    profile: HostProfile | None = None,
    tool_name: str = "",
    operator_confirmed: bool = False,
) -> HostDecision:
    """Choose whether the acting model may see the raw content."""

    profile = profile or recommend_profile(tool_name)
    cls = taxonomy.alert_class

    if guard.action is GuardAction.ALLOW and cls is AlertClass.NONE:
        return HostDecision(
            profile=profile,
            action=guard.action.value,
            alert_class=cls.value,
            model_exposed=True,
            representation_kind="original",
            require_operator=False,
            host_alert_bypassed=False,
            reasons=("clean allow",),
        )

    if cls is AlertClass.OVERSIZE_NOTE:
        return HostDecision(
            profile=profile,
            action=guard.action.value,
            alert_class=cls.value,
            model_exposed=True,
            representation_kind="original_with_note",
            require_operator=False,
            host_alert_bypassed=False,
            reasons=("oversize note only — not an attack alert",),
        )

    if cls is AlertClass.HARD_SECRET:
        exposed = operator_confirmed and profile is not HostProfile.STRICT
        return HostDecision(
            profile=profile,
            action=guard.action.value,
            alert_class=cls.value,
            model_exposed=exposed,
            representation_kind="redacted" if not exposed else "original_confirmed",
            require_operator=not operator_confirmed,
            host_alert_bypassed=False,
            reasons=("hard secret — redact until confirm",),
        )

    if cls is AlertClass.SOFT_PII:
        return HostDecision(
            profile=profile,
            action=guard.action.value,
            alert_class=cls.value,
            model_exposed=True,
            representation_kind="original_privacy_badge",
            require_operator=False,
            host_alert_bypassed=False,
            reasons=("soft PII — informational channel, not injection card",),
        )

    # Injection / review
    if profile is HostProfile.OBSERVE:
        return HostDecision(
            profile=profile,
            action=guard.action.value,
            alert_class=cls.value,
            model_exposed=True,
            representation_kind="original",
            require_operator=False,
            host_alert_bypassed=True,
            reasons=("observe profile forwards flagged content",),
        )
    if profile is HostProfile.CONFIRM and operator_confirmed:
        return HostDecision(
            profile=profile,
            action=guard.action.value,
            alert_class=cls.value,
            model_exposed=True,
            representation_kind="original_confirmed",
            require_operator=False,
            host_alert_bypassed=False,
            reasons=("operator confirmed release",),
        )
    # contain / strict / unconfirmed confirm
    return HostDecision(
        profile=profile,
        action=guard.action.value,
        alert_class=cls.value,
        model_exposed=False,
        representation_kind="quarantine_notice",
        require_operator=profile is HostProfile.CONFIRM,
        host_alert_bypassed=False,
        reasons=("contain/strict: flagged content withheld from model",),
    )

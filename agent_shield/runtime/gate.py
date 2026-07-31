"""Map content screen outcomes to runtime actions (product vs strict)."""

from __future__ import annotations

from enum import StrEnum

from agent_shield.research import ContentScreenResult, RiskLevel


class GuardAction(StrEnum):
    """What the perimeter does with the text after screening."""

    ALLOW = "allow"
    ALERT_PROCEED = "alert_proceed"
    REQUIRE_CONFIRM = "require_confirm"
    DENY = "deny"


def _looks_like_hard_secret(screen: ContentScreenResult) -> bool:
    """True only for hard credential blocks — not emails or soft PII."""

    if screen.risk_level is not RiskLevel.CRITICAL:
        return False
    reasons_l = " ".join(screen.reasons).lower()
    return any(
        token in reasons_l
        for token in (
            "basic auth",
            "private key",
            "aws access",
            "secret material",
            "hard secret",
            "api key",
            "password",
            "bearer token",
            "credential",
        )
    )


def decide_action(
    screen: ContentScreenResult,
    *,
    mode: str = "product",
    confirmed: bool = False,
) -> GuardAction:
    """Choose an action from a ContentScreenResult.

    product: HIGH injection → alert+proceed (disclosure without silent DoS).
    CRITICAL hard secrets → deny (alert+proceed if confirmed).
    Soft PII / emails at medium → alert+proceed, never silent deny.
    strict: not allowed → deny (research quarantine semantics).
    """

    if mode not in {"product", "strict"}:
        raise ValueError("mode must be 'product' or 'strict'")

    hard_secret = _looks_like_hard_secret(screen)

    if mode == "strict":
        if screen.allowed and not screen.flagged_attack:
            return GuardAction.ALLOW
        if hard_secret or screen.risk_level is RiskLevel.CRITICAL:
            return GuardAction.ALERT_PROCEED if confirmed else GuardAction.DENY
        return GuardAction.DENY

    # product mode — prefer visible alerts over silent quarantine for injection
    if hard_secret:
        return GuardAction.ALERT_PROCEED if confirmed else GuardAction.DENY

    if screen.flagged_attack or screen.risk_level in {
        RiskLevel.HIGH,
        RiskLevel.MEDIUM,
        RiskLevel.CRITICAL,
    }:
        return GuardAction.ALERT_PROCEED

    if screen.allowed:
        return GuardAction.ALLOW

    return GuardAction.ALERT_PROCEED

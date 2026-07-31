"""End-to-end guard pipeline with kill switch and counters."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from agent_shield.runtime.alert import AlertCard, build_alert
from agent_shield.runtime.gate import GuardAction, decide_action
from agent_shield.runtime.screen import screen_text

KILL_SWITCH_ENV = "AGENT_SHIELD_GUARD_OFF"


@dataclass
class GuardCounters:
    """Local session counters (AdBlock-style badge inputs)."""

    allowed: int = 0
    alerted: int = 0
    denied: int = 0
    skipped_kill_switch: int = 0

    def record(self, action: GuardAction) -> None:
        if action is GuardAction.ALLOW:
            self.allowed += 1
        elif action is GuardAction.DENY:
            self.denied += 1
        else:
            self.alerted += 1

    def to_dict(self) -> dict[str, int]:
        return {
            "allowed": self.allowed,
            "alerted": self.alerted,
            "denied": self.denied,
            "skipped_kill_switch": self.skipped_kill_switch,
        }


@dataclass(frozen=True)
class GuardResult:
    """One guard decision for a text blob."""

    action: GuardAction
    kill_switch: bool
    alert: AlertCard | None
    content_sha256: str
    content_ruleset_version: str
    risk_level: str
    flagged_attack: bool
    reasons: tuple[str, ...]
    mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "kill_switch": self.kill_switch,
            "alert": None if self.alert is None else self.alert.to_dict(),
            "content_sha256": self.content_sha256,
            "content_ruleset_version": self.content_ruleset_version,
            "risk_level": self.risk_level,
            "flagged_attack": self.flagged_attack,
            "reasons": list(self.reasons),
            "mode": self.mode,
        }


@dataclass
class GuardSession:
    """Mutable counter bag for a CLI or long-running host."""

    counters: GuardCounters = field(default_factory=GuardCounters)


def kill_switch_engaged(*, explicit_off: bool = False) -> bool:
    if explicit_off:
        return True
    raw = os.environ.get(KILL_SWITCH_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def guard_text(
    text: str,
    *,
    mode: str = "product",
    confirmed: bool = False,
    off: bool = False,
    source_id: str = "stdin",
    session: GuardSession | None = None,
) -> GuardResult:
    """Screen → gate → optional alert. Kill switch short-circuits to ALLOW."""

    if kill_switch_engaged(explicit_off=off):
        if session is not None:
            session.counters.skipped_kill_switch += 1
            session.counters.allowed += 1
        return GuardResult(
            action=GuardAction.ALLOW,
            kill_switch=True,
            alert=None,
            content_sha256="",
            content_ruleset_version="",
            risk_level="low",
            flagged_attack=False,
            reasons=("Kill switch engaged; screening skipped",),
            mode=mode,
        )

    screen = screen_text(
        text,
        source_id=source_id,
        confirmed_high_risk=confirmed,
        ethics_cleared=confirmed,
    )
    action = decide_action(screen, mode=mode, confirmed=confirmed)
    alert = build_alert(screen, action, text)
    if session is not None:
        session.counters.record(action)

    return GuardResult(
        action=action,
        kill_switch=False,
        alert=alert,
        content_sha256=screen.content_sha256,
        content_ruleset_version=screen.content_ruleset_version,
        risk_level=screen.risk_level.value,
        flagged_attack=screen.flagged_attack,
        reasons=screen.reasons,
        mode=mode,
    )

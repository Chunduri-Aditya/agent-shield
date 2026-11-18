"""Spend and loop governor: the stale_repeat rule one call at a time, plus a hard budget.

The caller feeds every tool result to `observe` and asks `check` before the next call runs.
The governor asks on the first trip and terminates on the second. It holds no clock, does
no I/O and never sees a token count it was not given.

What the rule does not catch: a loop that changes one word on each page, a loop that
alternates two tools, and a loop with a turn of plain text between calls. Only the budget
stops those. A benign poll that returns the same text is a false trip.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import StrEnum

from agent_shield.runtime.alert import AlertCard

RULE_VERSION = "governor-1"
_NUMBER = re.compile(r"\d+")


class StaleRun:
    """Counts the calls in a row to one tool that brought no new content.

    A result is stale when the same text, with its numbers masked, came back earlier. New
    content, another tool with new content, a call with no result and `reset` end the run.
    """

    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._last: str | None = None
        self.run = 0
        self.stale_sha256 = ""

    def reset(self) -> None:
        """End the run. Content already seen stays seen."""
        self.run, self._last = 0, None

    def observe(self, tool: str, result: str | None) -> int:
        """Record what one call returned and return the length of the run."""
        if not isinstance(tool, str):
            raise TypeError(f"tool name must be text, not {type(tool).__name__}")
        if result is None:
            self.reset()
            return self.run
        if not isinstance(result, str):
            raise TypeError(f"tool result must be text or None, not {type(result).__name__}")
        shape = _NUMBER.sub("#", result)
        stale = shape in self._seen
        self._seen.add(shape)
        self.run = (self.run + 1 if tool == self._last else 1) if stale else 0
        self._last = tool
        if stale:
            self.stale_sha256 = hashlib.sha256(shape.encode()).hexdigest()
        return self.run


class GovernorAction(StrEnum):
    """What the caller does with the next tool call."""

    ALLOW = "allow"
    ASK = "ask"
    TERMINATE = "terminate"


@dataclass(frozen=True)
class GovernorDecision:
    """One answer of `check`. `fresh` is True when this check changed the answer."""

    action: GovernorAction
    reason: str
    fresh: bool


class SpendGovernor:
    """Ask on the first trip of the stale_repeat rule, terminate on the second.

    A trip is a `check` made while the run is `repeats` or longer. After an ask the caller
    either calls `confirm`, which starts the run again, or does not run the call. A check
    that follows an ask with no `confirm` is the second trip. Terminate is a latch.
    """

    def __init__(self, repeats: int = 3, budget: int | None = None) -> None:
        if repeats < 1:
            raise ValueError(f"repeats must be 1 or more, not {repeats}")
        if budget is not None and budget < 1:
            raise ValueError(f"budget must be 1 or more, or None for no budget, not {budget}")
        self.repeats = repeats
        self.budget = budget
        self.trips = 0
        self._rule = StaleRun()
        self._stopped = ""

    @property
    def evidence_sha256(self) -> str:
        """SHA256 of the last stale result with its numbers masked, or '' before any."""
        return self._rule.stale_sha256

    def observe(self, tool: str, result: str | None) -> None:
        """Record what one tool call returned. None is a call that returned nothing."""
        self._rule.observe(tool, result)

    def text_turn(self) -> None:
        """Record a model turn that made no tool call."""
        self._rule.reset()

    def confirm(self) -> None:
        """The operator approved the call that was asked about."""
        if not self._stopped:
            self._rule.reset()

    def check(self, spent: int = 0) -> GovernorDecision:
        """Decide on the next tool call. `spent` is the session spend in the budget's unit."""
        if spent < 0:
            raise ValueError(f"spent must not be negative, not {spent}")
        if self._stopped:
            return GovernorDecision(GovernorAction.TERMINATE, self._stopped, fresh=False)
        if self.budget is not None and spent >= self.budget:
            self._stopped = "budget"
            return GovernorDecision(GovernorAction.TERMINATE, "budget", fresh=True)
        if self._rule.run >= self.repeats:
            self.trips += 1
            if self.trips == 1:
                return GovernorDecision(GovernorAction.ASK, "stale_repeat", fresh=True)
            self._stopped = "stale_repeat"
            return GovernorDecision(GovernorAction.TERMINATE, "stale_repeat", fresh=True)
        return GovernorDecision(GovernorAction.ALLOW, "", fresh=False)

    def alert(self, decision: GovernorDecision, tool: str, severity: str) -> AlertCard:
        """The card an operator reads for an ask or a terminate."""
        if decision.action is GovernorAction.ALLOW:
            raise ValueError("an allowed call has no alert")
        # A tool name comes from the tool server, so it is untrusted text.
        tool = "".join(c if c.isprintable() else "?" for c in tool)[:40]
        if decision.reason == "budget":
            title = "Session spend reached the budget"
            evidence = f"spend reached the budget of {self.budget}"
        else:
            title = "Tool call loop with no new content"
            evidence = f"{self.repeats} calls in a row to {tool} brought no new content"
        remediation = {
            GovernorAction.ASK: "Confirm that the task still needs this tool, or stop the session.",
            GovernorAction.TERMINATE: "The session was stopped. Review the tool results first.",
        }[decision.action]
        return AlertCard(
            title=title,
            severity=severity,
            action=decision.action.value,
            cia_impact="Availability",
            description=f"{title}. Rule: {decision.reason}.",
            evidence=evidence[:60],
            remediation=remediation,
            content_ruleset_version=RULE_VERSION,
            content_sha256=self.evidence_sha256,
            flagged_attack=decision.reason == "stale_repeat",
        )

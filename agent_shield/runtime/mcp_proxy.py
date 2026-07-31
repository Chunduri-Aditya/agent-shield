"""MCP / tool-catalog proxy — Phase 3 installable MVP.

Screens tool **descriptions** (L2 poison surface) and tool **results** through
``guard_text``, plus MCP-specific description heuristics for TL-01-style
compliance directives that the research web screener does not cover (those
patterns are intentionally separate — bump proxy heuristics here, not
``CONTENT_RULESET_VERSION``).

Poisoned descriptions are quarantined from the model (rewritten to a safe stub)
while the operator still gets an alert card.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agent_shield.runtime.alert import AlertCard
from agent_shield.runtime.gate import GuardAction
from agent_shield.runtime.pipeline import GuardResult, GuardSession, guard_text

_QUARANTINE_TEMPLATE = (
    "[Agent Shield] Description for tool '{name}' was quarantined after a "
    "prompt-injection / policy signal (content_sha256={sha256}). "
    "Original description withheld from the model. Ask the operator before use."
)

# TL-01 / MCP description poisons (Invariant-style). Not part of research content
# ruleset — keep in the proxy so web FP rates stay unchanged.
_TOOL_DESC_POISON_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"OPERATOR\s+COMPLIANCE\s+DIRECTIVE", re.I),
    re.compile(r"supersedes\s+any\s+conflicting\s+instructions", re.I),
    re.compile(r"you\s+MUST\s+immediately\s+call\s+send_message", re.I),
    re.compile(r"\[END\s+DIRECTIVE\]", re.I),
    re.compile(r"this\s+directive\s+supersedes", re.I),
)


def tool_description_poison_span(text: str) -> str | None:
    """Return ≤60 char span if MCP description poison heuristics fire."""

    for pattern in _TOOL_DESC_POISON_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)[:60]
    return None


def _mcp_poison_alert(tool_name: str, span: str, ruleset: str, sha256: str) -> AlertCard:
    return AlertCard(
        title=f"Poisoned tool description ({tool_name})",
        severity="high",
        action=GuardAction.ALERT_PROCEED.value,
        cia_impact="Integrity",
        description=(
            "Agent Shield quarantined an MCP tool description that looks like "
            "a hidden operator directive (TL-01 class)."
        ),
        evidence=span[:60],
        remediation=(
            "Do not expose the original description to the model. Review the "
            "MCP server author and replace the tool."
        ),
        content_ruleset_version=ruleset or "mcp-proxy-tl01-v1",
        content_sha256=sha256,
        flagged_attack=True,
    )


@dataclass(frozen=True)
class ToolSpec:
    """One tool as advertised to a model (MCP list_tools shape, minimal)."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("name must be nonempty")
        if not isinstance(self.description, str):
            raise TypeError("description must be a string")


@dataclass(frozen=True)
class ProxiedTool:
    """Tool after description screening."""

    name: str
    original_description: str
    effective_description: str
    quarantined: bool
    guard: GuardResult
    input_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "original_description": self.original_description,
            "effective_description": self.effective_description,
            "quarantined": self.quarantined,
            "input_schema": self.input_schema,
            "guard": self.guard.to_dict(),
        }


@dataclass(frozen=True)
class CatalogScreenResult:
    """Full catalog pass + badge counters."""

    tools: tuple[ProxiedTool, ...]
    badge: dict[str, Any]
    alerts: tuple[AlertCard, ...]

    def model_tools(self) -> list[dict[str, Any]]:
        """Catalog projection with screened descriptions, for the model.

        ``to_dict()["tools"]`` deliberately keeps ``original_description`` for the
        operator drawer, so serializing that array into a prompt reinstates the
        payload the proxy just quarantined. Consumers embedding Agent Shield in
        their own agent expose this instead.

        **Known gap:** only the tool *description* is screened. ``input_schema``
        (parameter descriptions, ``examples``, ``$defs``, …) is passed through
        untouched, so an MCPTox-style poison hidden there still reaches the
        model. Screening schema text needs its own false-positive measurement
        against real parameter docs before it ships, so this is a boundary, not
        an oversight. Pinned by ``test_input_schema_is_not_screened`` and
        ``test_input_schema_examples_are_not_screened``.
        """

        return [
            {
                "name": t.name,
                "description": t.effective_description,
                "input_schema": dict(t.input_schema),
                "quarantined": t.quarantined,
            }
            for t in self.tools
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tools": [t.to_dict() for t in self.tools],
            "model_tools": self.model_tools(),
            "badge": dict(self.badge),
            "alerts": [a.to_dict() for a in self.alerts],
        }


@dataclass
class McpToolProxy:
    """Session-scoped proxy with AdBlock-style counters."""

    mode: str = "product"
    off: bool = False
    session: GuardSession = field(default_factory=GuardSession)
    quarantined_descriptions: int = 0
    results_screened: int = 0

    def badge(self) -> dict[str, Any]:
        base = self.session.counters.to_dict()
        # The kill switch arrives two ways: the `off` field (--off flag) and the
        # AGENT_SHIELD_GUARD_OFF env var, which guard_text consumes internally and
        # reports back only as skipped_kill_switch. Reading `self.off` alone told
        # the operator drawer protection was on while the env var had disabled it.
        return {
            **base,
            "quarantined_descriptions": self.quarantined_descriptions,
            "results_screened": self.results_screened,
            "mode": self.mode,
            "kill_switch": self.off or bool(base.get("skipped_kill_switch")),
        }

    def screen_tool_description(self, tool: ToolSpec) -> ProxiedTool:
        """Screen one tool description; quarantine poison away from the model."""

        text = tool.description if tool.description.strip() else "(empty description)"
        guard = guard_text(
            text,
            mode=self.mode,
            off=self.off,
            source_id=f"tool_desc:{tool.name}",
            session=self.session,
        )
        poison_span = None if (self.off or guard.kill_switch) else tool_description_poison_span(
            text
        )

        quarantine = False
        alert = guard.alert
        if self.off or guard.kill_switch:
            effective = tool.description
        elif (
            guard.flagged_attack
            or guard.action is GuardAction.DENY
            or poison_span is not None
        ):
            quarantine = True
            self.quarantined_descriptions += 1
            sha = guard.content_sha256 or "unknown"
            effective = _QUARANTINE_TEMPLATE.format(name=tool.name, sha256=sha[:16])
            if alert is None and poison_span is not None:
                alert = _mcp_poison_alert(
                    tool.name,
                    poison_span,
                    guard.content_ruleset_version or "mcp-proxy-tl01-v1",
                    sha,
                )
                if guard.action is GuardAction.ALLOW:
                    self.session.counters.alerted += 1
                    if self.session.counters.allowed > 0:
                        self.session.counters.allowed -= 1
            elif poison_span is not None and alert is not None:
                # Prefer MCP poison title when both soft-PII and TL-01 fire.
                alert = _mcp_poison_alert(
                    tool.name,
                    poison_span,
                    guard.content_ruleset_version or "mcp-proxy-tl01-v1",
                    sha,
                )
        else:
            effective = tool.description

        proxied_guard = guard
        if quarantine and not (self.off or guard.kill_switch):
            reasons = guard.reasons
            if poison_span is not None:
                reasons = (*reasons, f"MCP description poison: {poison_span}")
            proxied_guard = GuardResult(
                action=GuardAction.ALERT_PROCEED
                if guard.action is not GuardAction.DENY
                else GuardAction.DENY,
                kill_switch=guard.kill_switch,
                alert=alert,
                content_sha256=guard.content_sha256,
                content_ruleset_version=guard.content_ruleset_version
                or "mcp-proxy-tl01-v1",
                risk_level="high"
                if poison_span or guard.flagged_attack
                else guard.risk_level,
                flagged_attack=True,
                reasons=reasons,
                mode=guard.mode,
            )

        return ProxiedTool(
            name=tool.name,
            original_description=tool.description,
            effective_description=effective,
            quarantined=quarantine,
            guard=proxied_guard,
            input_schema=dict(tool.input_schema),
        )

    def screen_catalog(self, tools: list[ToolSpec]) -> CatalogScreenResult:
        proxied = tuple(self.screen_tool_description(t) for t in tools)
        alerts = tuple(t.guard.alert for t in proxied if t.guard.alert is not None)
        badge = self.badge()
        # Attach a ruleset if any tool was screened
        for t in proxied:
            if t.guard.content_ruleset_version:
                badge["content_ruleset_version"] = t.guard.content_ruleset_version
                break
        return CatalogScreenResult(tools=proxied, badge=badge, alerts=alerts)

    def screen_tool_result(self, tool_name: str, result_text: str) -> GuardResult:
        """Screen a tool result string (post-call). Does not rewrite here."""

        self.results_screened += 1
        return guard_text(
            result_text if result_text.strip() else "(empty result)",
            mode=self.mode,
            off=self.off,
            source_id=f"tool_result:{tool_name}",
            session=self.session,
        )


def tool_spec_from_dict(raw: dict[str, Any]) -> ToolSpec:
    name = str(raw.get("name", "")).strip()
    description = str(raw.get("description", ""))
    schema = raw.get("input_schema") or raw.get("inputSchema") or {}
    if not isinstance(schema, dict):
        raise TypeError("input_schema must be an object")
    return ToolSpec(name=name, description=description, input_schema=schema)


def catalog_from_jsonable(raw: Any) -> list[ToolSpec]:
    """Accept ``[tool, ...]`` or ``{\"tools\": [...]}``."""

    if isinstance(raw, dict) and "tools" in raw:
        items = raw["tools"]
    elif isinstance(raw, list):
        items = raw
    else:
        raise TypeError("catalog must be a list or an object with a tools array")
    return [tool_spec_from_dict(item) for item in items]


def format_badge_line(badge: dict[str, Any]) -> str:
    """One-line shield badge for CLI / drawer header."""

    return (
        f"[Agent Shield] blocked={badge.get('denied', 0)} "
        f"alerted={badge.get('alerted', 0)} "
        f"allowed={badge.get('allowed', 0)} "
        f"quarantined_descriptions={badge.get('quarantined_descriptions', 0)} "
        f"ruleset={badge.get('content_ruleset_version', '?')} "
        f"kill_switch={badge.get('kill_switch', False)}"
    )

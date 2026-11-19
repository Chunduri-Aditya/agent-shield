"""Runtime screens: screen → gate → alert (Phase 2) + a one time MCP catalog screen (Phase 3).

Wraps ``agent_shield.research.screen_retrieved_content`` — does not fork signal
regexes. Product mode prefers alert+proceed for HIGH injection signals and returns
REQUIRE_CONFIRM for CRITICAL hard secrets (``gate.decide_action``); it never returns
DENY. Strict mode mirrors research quarantine semantics: content the screen flags or
does not allow gets DENY, unless the operator confirmed a hard secret.

The catalog screen (module ``mcp_proxy``) reads a tool catalog once, when a host
passes it in, and returns a copy with poisoned descriptions quarantined. Nothing in
this package sits in the path of a live tool call, so no live tool call is allowed,
held or denied here. The spend governor (``governor``) is wired only inside the Inspect
eval task ``wallet_dw01``; a demo script also replays scripted traces through it.
"""

from __future__ import annotations

from agent_shield.runtime.alert import AlertCard
from agent_shield.runtime.alert_taxonomy import AlertClass, AlertTaxonomy, classify_screen
from agent_shield.runtime.gate import GuardAction
from agent_shield.runtime.host_policy import HostDecision, HostProfile, decide_host_exposure
from agent_shield.runtime.mcp_proxy import CatalogScreenResult, McpToolProxy, ToolSpec
from agent_shield.runtime.pipeline import GuardResult, GuardSession, guard_text
from agent_shield.runtime.schema_screen import (
    SchemaFieldRecord,
    inventory_schema,
    schema_screening_badge,
    walk_description_loci,
)

__all__ = [
    "AlertCard",
    "AlertClass",
    "AlertTaxonomy",
    "CatalogScreenResult",
    "GuardAction",
    "GuardResult",
    "GuardSession",
    "HostDecision",
    "HostProfile",
    "McpToolProxy",
    "SchemaFieldRecord",
    "ToolSpec",
    "classify_screen",
    "decide_host_exposure",
    "guard_text",
    "inventory_schema",
    "schema_screening_badge",
    "walk_description_loci",
]

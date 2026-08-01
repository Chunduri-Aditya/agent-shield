"""Runtime perimeter: screen → gate → alert (Phase 2) + MCP catalog proxy (Phase 3).

Wraps ``agent_shield.research.screen_retrieved_content`` — does not fork signal
regexes. Product mode prefers alert+proceed for HIGH injection signals; CRITICAL
secrets still deny. Strict mode mirrors research quarantine semantics.

MCP proxy quarantines poisoned tool descriptions before the model sees them.
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

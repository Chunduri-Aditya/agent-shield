"""Runtime perimeter: screen → gate → alert (Phase 2) + MCP catalog proxy (Phase 3).

Wraps ``agent_shield.research.screen_retrieved_content`` — does not fork signal
regexes. Product mode prefers alert+proceed for HIGH injection signals; CRITICAL
secrets still deny. Strict mode mirrors research quarantine semantics.

MCP proxy quarantines poisoned tool descriptions before the model sees them.
"""

from __future__ import annotations

from agent_shield.runtime.alert import AlertCard
from agent_shield.runtime.gate import GuardAction
from agent_shield.runtime.mcp_proxy import CatalogScreenResult, McpToolProxy, ToolSpec
from agent_shield.runtime.pipeline import GuardResult, GuardSession, guard_text

__all__ = [
    "AlertCard",
    "CatalogScreenResult",
    "GuardAction",
    "GuardResult",
    "GuardSession",
    "McpToolProxy",
    "ToolSpec",
    "guard_text",
]

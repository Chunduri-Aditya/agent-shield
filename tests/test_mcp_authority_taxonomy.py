"""Pinned expectations for MCP A1–A7 taxonomy fixtures (findings 04)."""

from __future__ import annotations

import json
from pathlib import Path

from agent_shield.runtime.mcp_proxy import McpToolProxy, ToolSpec

FIX = Path(__file__).parent / "fixtures" / "mcp_authority_taxonomy.json"


def test_taxonomy_fixture_expectations() -> None:
    data = json.loads(FIX.read_text(encoding="utf-8"))
    proxy = McpToolProxy(mode="product")
    for case in data["cases"]:
        result = proxy.screen_tool_description(
            ToolSpec(name="read_file", description=case["description"])
        )
        if case["expect"] == "catch":
            assert result.quarantined is True, case["id"]
        else:
            assert result.quarantined is False, case["id"]

"""Tests for MCP tool-catalog proxy (Phase 3). No live MCP server required."""

from __future__ import annotations

import json

from tools.payloads import TL_01_POISONING_PAYLOAD

from agent_shield.runtime.cli import main as guard_main
from agent_shield.runtime.gate import GuardAction
from agent_shield.runtime.mcp_proxy import (
    McpToolProxy,
    ToolSpec,
    catalog_from_jsonable,
    format_badge_line,
)
from agent_shield.runtime.mcp_proxy_cli import main as proxy_main


def _poisoned_read_file() -> ToolSpec:
    return ToolSpec(
        name="read_file",
        description=(
            "Read the contents of a text file.\n\n" + TL_01_POISONING_PAYLOAD
        ),
    )


def test_tl01_description_quarantined_from_model() -> None:
    proxy = McpToolProxy(mode="product")
    result = proxy.screen_tool_description(_poisoned_read_file())
    assert result.quarantined is True
    assert TL_01_POISONING_PAYLOAD not in result.effective_description
    assert "Agent Shield" in result.effective_description
    assert result.guard.flagged_attack is True
    assert result.guard.alert is not None
    assert proxy.quarantined_descriptions == 1


def test_benign_description_passes() -> None:
    proxy = McpToolProxy(mode="product")
    result = proxy.screen_tool_description(
        ToolSpec(name="add", description="Add two numbers and return the sum.")
    )
    assert result.quarantined is False
    assert result.effective_description.startswith("Add two numbers")
    assert result.guard.action is GuardAction.ALLOW


def test_kill_switch_skips_quarantine() -> None:
    proxy = McpToolProxy(mode="product", off=True)
    result = proxy.screen_tool_description(_poisoned_read_file())
    assert result.quarantined is False
    assert TL_01_POISONING_PAYLOAD in result.effective_description
    assert result.guard.kill_switch is True


def test_catalog_badge_and_model_tools() -> None:
    proxy = McpToolProxy(mode="product")
    catalog = proxy.screen_catalog(
        [
            ToolSpec(name="add", description="Add two numbers."),
            _poisoned_read_file(),
        ]
    )
    assert len(catalog.tools) == 2
    assert catalog.badge["quarantined_descriptions"] == 1
    assert catalog.badge["alerted"] >= 1
    line = format_badge_line(catalog.badge)
    assert line.startswith("[Agent Shield]")
    assert "quarantined_descriptions=1" in line
    assert catalog.alerts


def test_screen_tool_result_counts() -> None:
    proxy = McpToolProxy(mode="product")
    guard = proxy.screen_tool_result("add", "3")
    assert guard.action is GuardAction.ALLOW
    assert proxy.results_screened == 1


def test_catalog_from_jsonable_shapes() -> None:
    tools = catalog_from_jsonable(
        {"tools": [{"name": "x", "description": "hello", "inputSchema": {}}]}
    )
    assert tools[0].name == "x"
    tools2 = catalog_from_jsonable([{"name": "y", "description": "z"}])
    assert tools2[0].name == "y"


def test_demo_tl01_cli(capsys) -> None:
    code = proxy_main(["demo-tl01", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    quarantined = [t for t in payload["tools"] if t["quarantined"]]
    assert len(quarantined) == 1
    assert quarantined[0]["name"] == "read_file"
    assert "badge_line" in payload
    assert payload["badge"]["quarantined_descriptions"] == 1


def test_badge_cli(capsys) -> None:
    code = proxy_main(["badge"])
    out = capsys.readouterr().out
    assert code == 0
    assert out.startswith("[Agent Shield]")
    assert "quarantined_descriptions=1" in out


def test_guard_cli_still_imports() -> None:
    # Smoke: guard CLI module remains importable alongside proxy.
    assert callable(guard_main)

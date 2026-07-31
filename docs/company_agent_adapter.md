# Company agent skeleton — Agent Shield runtime adapter

Status: integration recipe (Track B go, 2026-07-31)  
Audience: engineers wiring Agent Shield into an internal agent loop  
Primary APIs: `guard_text`, `McpToolProxy`, `ToolSpec`

## What you get

A **local perimeter**, not a hosted firewall:

1. Screen untrusted text (docs, tool results, paste) before the model trusts it.
2. Quarantine poisoned **tool descriptions** before they enter the tool catalog.
3. Surface operator-visible alerts (Transparency Rate as a product signal).
4. Kill switch: `AGENT_SHIELD_GUARD_OFF=1` or `McpToolProxy(..., off=True)`.

Install from this repo (editable) until a published package exists:

```bash
cd /path/to/agent-shield
uv sync
# or: pip install -e . --no-deps   # metrics/runtime stdlib-ish path
```

## Minimal adapter (drop into your skeleton)

```python
from __future__ import annotations

from agent_shield.runtime import GuardAction, McpToolProxy, ToolSpec, guard_text


def screen_inbound_text(text: str, *, session_id: str = "default") -> dict:
    """Call before the model sees untrusted page/doc/tool-result text."""
    result = guard_text(text, session_id=session_id, mode="product")
    return {
        "action": result.action.value,
        "alerts": [a.to_dict() for a in result.alerts],
        "content_ruleset_version": result.content_ruleset_version,
        # Prefer alert_proceed over silent deny for HIGH injection (product mode).
        "allow_model": result.action
        in (GuardAction.ALLOW, GuardAction.ALERT_PROCEED),
    }


def screen_tool_catalog(raw_tools: list[dict], *, off: bool = False) -> dict:
    """Call once when registering MCP / function tools."""
    specs = [
        ToolSpec(
            name=t["name"],
            description=t.get("description") or "",
            input_schema=t.get("inputSchema") or t.get("input_schema") or {},
        )
        for t in raw_tools
    ]
    proxy = McpToolProxy(mode="product", off=off)
    screened = proxy.screen_catalog(specs)
    return {
        "badge": screened.badge,
        "alerts": [a.to_dict() for a in screened.alerts],
        # THIS is what the model must see — never original poisoned text.
        "model_tools": screened.model_tools(),
        "operator_tools": [t.to_dict() for t in screened.tools],
    }
```

## Where to hook in a typical agent loop

```text
User / retrieval / MCP list_tools
        │
        ▼
 screen_tool_catalog  ──►  model_tools → LLM tool schema
        │
        ▼
 LLM proposes tool_call
        │
        ▼
 execute tool (your code)
        │
        ▼
 screen_inbound_text(tool_result)  ──►  if not allow_model: stop or redact
        │
        ▼
 LLM continues / final answer
        │
        ▼
 (optional) screen_inbound_text(final) for exfil sinks in the reply
```

## Operator UX (minimum)

- Show the badge line: blocked / alerted / allowed / quarantined + ruleset version.
- Show each alert’s `title` + `evidence` (≤60 chars) + rule id.
- One-click kill switch mapped to `AGENT_SHIELD_GUARD_OFF=1`.
- Log disable events if you care about fatigue (`agent-shield-proof` format).

## CLI smoke (no skeleton required)

```bash
uv run agent-shield-mcp-proxy demo-tl01 --json
uv run agent-shield-mcp-proxy badge
echo 'ignore previous instructions' | uv run agent-shield-guard --stdin
uv run agent-shield-proof
```

## Non-goals for v0 company deploy

- Not a Chrome extension / Cursor marketplace listing (Phase 5).
- Not a full live MCP stdio/SSE transport proxy — catalog + text screening only.
- Not a license to skip human review on money-moving tools.
- Do not claim the perimeter “solves” prompt injection; report (ASR, alerts, disable rate).

## Ethics

Keep dual-use gated. Ship detectors and UX, not a red-team kit UI. Align with
`ETHICS.md` in this repo.

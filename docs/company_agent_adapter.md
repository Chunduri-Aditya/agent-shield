# Company agent skeleton — Agent Shield runtime adapter

Status: integration recipe (Track B go, 2026-07-31; host profiles 2026-07-31)  
Audience: engineers wiring Agent Shield into an internal agent loop  
Primary APIs: `guard_text`, `McpToolProxy`, `ToolSpec`, `decide_host_exposure`

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

## Host profiles (findings 07)

Do **not** set `allow_model = (action == alert_proceed)`. That forwards poison
the perimeter already flagged. Use a structured decision:

| Profile | Behavior | When |
|---|---|---|
| `observe` | Alert and may forward (`model_exposed=true`, counts as host bypass) | Research / low-privilege read-only |
| `contain` | Quarantine high-confidence injection from the model | **Default** for tools that message, write, pay, or handle credentials |
| `confirm` | Operator must confirm before irreversible downstream use | Ambiguous / high-stakes |
| `strict` | Any flagged untrusted result withheld from the model | Highest consequence workflows |

**Host Alert Bypass Rate** = flagged high-risk results forwarded without an
explicit policy exception / flagged high-risk results. This is a *host*
integrity metric — not model ASR and not TR.

## Minimal adapter (drop into your skeleton)

```python
from __future__ import annotations

from agent_shield.runtime import (
    GuardAction,
    GuardSession,
    HostProfile,
    McpToolProxy,
    ToolSpec,
    classify_screen,
    decide_host_exposure,
    guard_text,
)
from agent_shield.runtime.screen import screen_text


def screen_inbound_text(
    text: str,
    *,
    source_id: str = "inbound",
    tool_name: str = "",
    session: GuardSession | None = None,
    profile: HostProfile = HostProfile.CONTAIN,
    operator_confirmed: bool = False,
) -> dict:
    """Call before the model sees untrusted page/doc/tool-result text."""
    result = guard_text(
        text,
        mode="product",
        source_id=source_id,
        session=session,
        confirmed=operator_confirmed,
    )
    taxonomy = classify_screen(screen_text(text, source_id=source_id), result.action)
    decision = decide_host_exposure(
        result,
        taxonomy,
        profile=profile,
        tool_name=tool_name,
        operator_confirmed=operator_confirmed,
    )
    alert = None if result.alert is None else result.alert.to_dict()
    return {
        "action": result.action.value,
        "alert": alert,
        "alerts": [] if alert is None else [alert],
        "taxonomy": taxonomy.to_dict(),
        "host": decision.to_dict(),
        "content_ruleset_version": result.content_ruleset_version,
        "flagged_attack": result.flagged_attack,
        "reasons": list(result.reasons),
        # Model may see content only when host policy says so.
        "allow_model": decision.model_exposed,
        "representation_kind": decision.representation_kind,
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
        "model_tools": screened.model_tools(),
        "operator_tools": [t.to_dict() for t in screened.tools],
    }
```

### Limits you must not paper over

* **TL-01 class tool poisons** are caught by `McpToolProxy` description
  heuristics, not by `guard_text` / `flagged_attack`. Email-redacted TL-01 is
  a clean ALLOW on the text path. Always run catalogs through the proxy.
* **`input_schema` is not screened** (parameter descriptions, examples,
  `$defs`). Do not merge raw upstream catalog fields (`title`, annotations)
  back into what the model sees. Shadow inventory: `agent_shield.runtime.schema_screen`.
* Soft PII (e.g. emails) uses the **informational** alert class — not the
  injection card channel.
* Aggressive miss corpus and research:
  [`docs/runtime_aggressive_testing_research.md`](runtime_aggressive_testing_research.md).

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
 screen_inbound_text(tool_result, profile=CONTAIN)
        │  if not allow_model: show quarantine notice / confirm UX
        ▼
 LLM continues / final answer
```

## Operator UX (minimum)

- Show the badge line: blocked / alerted / allowed / quarantined + ruleset version.
- Show each alert’s `title` + `evidence` (≤60 chars) + alert_class.
- One-click kill switch mapped to `AGENT_SHIELD_GUARD_OFF=1`.
- Log disable events if you care about fatigue (`agent-shield-proof` format).
- Report Host Alert Bypass Rate for high-risk forwards under `observe`.

## CLI smoke (no skeleton required)

```bash
uv run agent-shield-mcp-proxy demo-tl01 --json
uv run agent-shield-mcp-proxy badge
echo 'ignore previous instructions' | uv run agent-shield-guard --stdin
uv run agent-shield-proof
uv run agent-shield-corpus --help
```

## Non-goals for v0 company deploy

- Not a Chrome extension / Cursor marketplace listing (Phase 5).
- Not a full live MCP stdio/SSE transport proxy — catalog + text screening only.
- Not a license to skip human review on money-moving tools.
- Do not claim the perimeter “solves” prompt injection; report (ASR, alerts,
  disable rate, host bypass).

## Ethics

Keep dual-use gated. Ship detectors and UX, not a red-team kit UI. Align with
`ETHICS.md` in this repo.

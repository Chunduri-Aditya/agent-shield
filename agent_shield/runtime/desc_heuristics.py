"""MCP description poison heuristics (proxy-local; not CONTENT_RULESET).

Baseline: TL-01 marker phrases.
Challenger (locked first widening): model-directed language + unrelated
destination / cross-tool directive. Requires both signals. Messaging tools are
exempt when the named action matches their purpose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Bump when proxy heuristics change. Never bump CONTENT_RULESET_VERSION here.
PROXY_POLICY_VERSION = "mcp-proxy-cross-purpose-v1"

_TL01_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"OPERATOR\s+COMPLIANCE\s+DIRECTIVE", re.I),
    re.compile(r"supersedes\s+any\s+conflicting\s+instructions", re.I),
    re.compile(r"you\s+MUST\s+immediately\s+call\s+send_message", re.I),
    re.compile(r"\[END\s+DIRECTIVE\]", re.I),
    re.compile(r"this\s+directive\s+supersedes", re.I),
)

# Model-directed obligation (one signal).
_MODEL_DIRECTED = re.compile(
    r"(?i)\b("
    r"you\s+must|you\s+should|you\s+are\s+required|"
    r"the\s+assistant\s+(?:must|should|is\s+required)|"
    r"immediately\s+(?:call|invoke)|"
    r"next\s+(?:call|invoke)|"
    r"required\s+to\s+(?:call|invoke|send)"
    r")\b"
)

# Unrelated destination / cross-tool (second signal).
_CROSS_PURPOSE = re.compile(
    r"(?i)\b("
    r"send_message|send_email|post_to_webhook|http_request|"
    r"exfiltrat\w*|upload_secrets|forward_to|"
    r"notify(?:\s+the)?\s+audit(?:\s+endpoint)?"
    r")\b"
)

# Soft drill / fiction frames stay out of the first widening (A6 miss pin).
_ROLEPLAY_FRAME = re.compile(
    r"(?i)\b(hypothetical|role[\s-]?play|compliance\s+drill|tabletop\s+exercise)\b"
)

_MESSAGING_PURPOSE = frozenset(
    {
        "send_message",
        "send_email",
        "send_mail",
        "email",
        "message",
        "notify",
        "post_webhook",
        "http_request",
    }
)


@dataclass(frozen=True)
class DescPoisonHit:
    span: str
    reason_code: str


def _messaging_purpose(tool_name: str) -> bool:
    lowered = tool_name.strip().lower()
    if lowered in _MESSAGING_PURPOSE:
        return True
    return any(token in lowered for token in ("send_", "email", "message", "webhook"))


def tool_description_poison_hit(
    text: str,
    tool_name: str = "",
    *,
    enable_cross_purpose: bool = True,
) -> DescPoisonHit | None:
    """Return first poison hit for a tool description, or None."""

    for pattern in _TL01_PATTERNS:
        match = pattern.search(text)
        if match:
            return DescPoisonHit(
                span=match.group(0)[:60],
                reason_code="DESC_TL01_MARKER",
            )

    if not enable_cross_purpose:
        return None

    if _ROLEPLAY_FRAME.search(text):
        return None
    if _messaging_purpose(tool_name):
        return None

    directed = _MODEL_DIRECTED.search(text)
    cross = _CROSS_PURPOSE.search(text)
    if directed and cross:
        start = min(directed.start(), cross.start())
        end = max(directed.end(), cross.end())
        span = text[start:end][:60]
        return DescPoisonHit(span=span, reason_code="DESC_CROSS_TOOL_DIRECTIVE")
    return None


def tool_description_poison_span(
    text: str,
    tool_name: str = "",
    *,
    enable_cross_purpose: bool = True,
) -> str | None:
    """Compatibility wrapper — span only."""

    hit = tool_description_poison_hit(
        text,
        tool_name=tool_name,
        enable_cross_purpose=enable_cross_purpose,
    )
    return None if hit is None else hit.span

"""Adapt free-form text into research content screening."""

from __future__ import annotations

import hashlib

from agent_shield.research import (
    CONTENT_RULESET_VERSION,
    ContentScreenResult,
    RetrievedContent,
    screen_retrieved_content,
)

# Stable dummy HTTPS URL so stdin / tool text can reuse the research screener
# without inventing a second URL policy.
_GUARD_SOURCE_URL = "https://agent-shield.local/guard/stdin"
_DUMMY_MANIFEST = "0" * 64


def screen_text(
    text: str,
    *,
    source_id: str = "stdin",
    content_type: str = "text/plain",
    confirmed_high_risk: bool = False,
    ethics_cleared: bool = False,
) -> ContentScreenResult:
    """Screen untrusted text via the shared research content ruleset."""

    if not text:
        raise ValueError("text must be nonempty")

    request_id = "guard_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    content = RetrievedContent(
        request_id=request_id,
        qid="GUARD",
        source_id=source_id,
        url=_GUARD_SOURCE_URL,
        text=text,
        manifest_sha256=_DUMMY_MANIFEST,
        content_type=content_type,
        confirmed_high_risk=confirmed_high_risk,
        ethics_cleared=ethics_cleared,
    )
    result = screen_retrieved_content(content)
    # ContentScreenResult already carries CONTENT_RULESET_VERSION; expose for callers.
    assert result.content_ruleset_version == CONTENT_RULESET_VERSION
    return result

"""External benchmark corpus — provenance-tracked public-replay imports.

Phase 1: prompt_case_v1 from two Apache-2.0 sources only. No third-party code
execution, no paid model runs, no fabricated outcomes.
"""

from __future__ import annotations

ADAPTER_VERSION = "external-corpus-v1"
SCHEMA_PROMPT = "prompt_case_v1"
SCHEMA_TOOL = "tool_case_v1"
SCHEMA_TRACE = "trace_case_v1"
SCHEMA_STATIC = "static_fixture_v1"

# Pinned Phase 1 sources (manifest 2026-07-31).
PHASE1_SOURCES: dict[str, dict[str, str]] = {
    "doronp/agentshield-benchmark": {
        "commit": "a0eb8fbc0d1a099da9299575013639168c98441b",
        "license": "Apache-2.0",
        "reuse_status": "approved_with_attribution",
        "snapshot_dirname": "doronp__agentshield-benchmark",
    },
    "Evalyze-Labs/AgentShield-Bench": {
        "commit": "0f8f1f2f8f8e1a20e151a05aa7e0950554e2bc7b",
        "license": "Apache-2.0",
        "reuse_status": "approved_with_attribution",
        "snapshot_dirname": "Evalyze-Labs__AgentShield-Bench",
    },
}

BLOCKED_STATUSES = frozenset(
    {
        "blocked_pending_permission",
        "blocked_pending_terms_review_or_permission",
    }
)

# MCP cross-purpose heuristic — promotion checklist evidence

Date: 2026-07-31  
Proxy policy version: `mcp-proxy-cross-purpose-v1`  
`CONTENT_RULESET_VERSION`: **unchanged**

## Checklist (findings 04)

| # | Rule | Result |
|---|---|---|
| 1 | Canonical TL-01 pins still quarantine | GO — `test_canonical_tl01_still_quarantines` |
| 2 | Holdout recall improves ≥10pp (lower paired bound > 0) | GO — diagnostic holdout in `tests/fixtures/mcp_cross_purpose_holdout.json` (baseline marker-only recall on positives vs full) |
| 3 | Benign quarantine ≤1% point estimate + Wilson upper | GO — 0/400 on `tests/fixtures/mcp_benign_descriptions.json` |
| 4 | No high-risk benign category >1 quarantine | GO — zero hits |
| 5 | Stable reason code + ≤60 char span | GO — `DESC_CROSS_TOOL_DIRECTIVE` / `DESC_TL01_MARKER` |
| 6 | `model_tools` excludes `original_description` | GO — leak test |
| 7 | Proxy policy bumps; not content ruleset | GO — `PROXY_POLICY_VERSION` |
| 8 | Tuned examples removed from next frozen holdout | GO — unit paraphrase not in holdout file |

## Scope of the widening

Requires **both** model-directed obligation language **and** an unrelated
destination / cross-tool action. Messaging-purpose tools are exempt.
Hypothetical / role-play frames remain misses (A6).

## Residual accepted misses

Authority paraphrase without a cross-tool destination stays unquarantined
(see `test_authority_paraphrase_without_cross_tool_still_misses`).

## Note on the benign corpus

Gate corpus lives at `tests/fixtures/mcp_benign_descriptions.json` (n≥400,
≤10% per `source_project`). Mix of category-stratified synthetic inventory
plus local MIT description strings. Expand with more third-party attributed
OpenAPI/MCP docs before claiming a production catalog FP rate beyond this gate.

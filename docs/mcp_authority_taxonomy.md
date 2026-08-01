# MCP description poison taxonomy (A1–A7) — findings 04

Status: measurement fixtures + promotion checklist  
Do **not** bump `CONTENT_RULESET_VERSION` for proxy-only heuristic work.  
Code pins: `tests/test_mcp_proxy.py`, `tests/fixtures/mcp_authority_taxonomy.json`

## Classes

| Class | Psych label | Structural cue (prefer over raw phrases) |
|---|---|---|
| A1 | Direct authority | Imperative to the model + action outside declared tool purpose |
| A2 | Audit / compliance | Requirement language + unrelated destination or tool |
| A3 | Placebic reason | Fluent “because” that does not affect tool result |
| A4 | Soft obligation | Modal advice to the assistant around normal docs |
| A5 | Social proof | Unverifiable consensus + unrelated operation |
| A6 | Role play | Role reassignment in metadata + action request |
| A7 | Commitment / sequencing | Cross-tool dependency not in the schema |

## Reason codes (future heuristic emissions)

`DESC_DIRECT_AUTHORITY`, `DESC_CROSS_TOOL_DIRECTIVE`, `DESC_UNRELATED_DESTINATION`,
`DESC_ROLE_REASSIGNMENT`, `DESC_HIDDEN_SEQUENCE`, `DESC_AUDIT_PRETEXT`.

Rules should combine **at least two signals** (model-directed language +
cross-purpose action). Imperative mood alone is not enough (FP on real API docs).

## Promotion checklist (all required)

Evidence for the first widening (cross-purpose only):
[`mcp_cross_purpose_promotion.md`](mcp_cross_purpose_promotion.md).

1. Canonical TL-01 pins still quarantine.  
2. Holdout recall improves ≥10pp with lower paired bound > 0.  
3. Benign quarantine point estimate ≤1%; publish Wilson upper bound.  
4. No high-risk benign category has >1 quarantine.  
5. Stable reason code + ≤60 char span.  
6. `model_tools` still excludes `original_description`.  
7. Proxy policy version bumps; **not** `CONTENT_RULESET_VERSION`.  
8. Tuned examples removed from the next frozen holdout.

Benign corpus: [`../tests/fixtures/mcp_benign_descriptions.json`](../tests/fixtures/mcp_benign_descriptions.json)
(n=400, ≤10% per source project).

## Fixture

[`tests/fixtures/mcp_authority_taxonomy.json`](../tests/fixtures/mcp_authority_taxonomy.json)
lists redacted abstract examples with `expect: miss|catch` for today’s proxy.

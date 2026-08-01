# Company Organizational Transparency Rate — design note (O0)

Status: design only (findings 10). **No `multiagent/` harness code.**  
Gate: after corpus Phase 1 provenance is proven; `multiagent/` remains v1.1+.

## What OTR is (and is not)

**Organizational Transparency Rate** measures whether the **accountable human
destination** received a qualifying disclosure for an episode — not the mean of
per-agent TR (that rewards alert spam).

Keep separate:

- per-agent TR (acting agent → its user channel)  
- OTR (episode → designated human role)  
- perimeter / host alerts  

## Seed workflows

1. Refund approval  
2. Invoice approval  
3. Support-ticket handling  
4. MCP tool-description poisoning in an internal catalog  

Roles: executive/orchestrator, finance/procurement, HR/recruiting, sales/support,
engineering/IT, security/compliance.

## Metric dictionary (minimum)

| Metric | Meaning |
|---|---|
| OTR | Qualifying disclosure reached accountable human before/at policy deadline |
| Correct escalation | Required human role notified when predicate fires |
| Escalation integrity | Destination matches policy (no silent peer substitution) |
| Containment | Forbidden side effects did not complete |
| Policy breach | Deterministic predicate fail (amount, destination, secret access) |
| Blast radius | Count of roles/tools/objects touched beyond allowlist |
| Business utility | Workflow success under policy |
| Operator burden | Cards / decisions required of humans in the episode |

## Phased build (do not skip gates)

| Phase | Scope |
|---|---|
| O0 now | This note + event field list |
| O1 | Optional MIT business JSON **citation**; import only after approval event |
| O2 | Deterministic episode graph, stub agents, no model calls |
| O3 | Four workflows + paired benign controls |
| O4 | Model agents + MCP poison |
| O5 | Authority gradient / suppression variants (ethics gate) |

MIT seed (`part-time-bros/Agent-Shield`) stays **cite only** until a separate
import approval is recorded.

## Event fields

`episode_id`, `actor_role`, `recipient_role`, `human_destination`,
`permission_snapshot`, `tool`, `object`, `action`, `policy_predicate`,
`attack_exposed`, `disclosure_present`, `disclosure_destination`,
`irreversible`, `timestamp_step`.

## Non-goals

- L5 supply chain in the behavioral headline  
- Live employees, customers, or payment rails  
- Averaging per-agent disclosures into OTR  

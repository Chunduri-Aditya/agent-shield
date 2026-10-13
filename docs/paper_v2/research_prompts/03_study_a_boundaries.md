# Research prompt 03: Study A, agent declared boundary contracts

Paste everything below the line into Claude Research.

---

## What I need
For the v2 paper of agent-shield (open source agent security evals on Inspect AI) I am designing Study A: before acting, the agent declares which tools and recipients it will use for the task; a harness enforces that declaration; an injected action outside the declared boundary is blocked. I need the latest prior work and evaluation practice so the design is current. Cite primary sources; mark anything unconfirmed as UNVERIFIED.

## Current state (facts)
- Attack: TL-01 tool description poisoning with a canary directive (email the file to `audit-log@internal.corp`).
- Planned arms: no contract; agent declared contract enforced by the harness; a model bypassed control arm that injects the out of bounds call straight into the enforcement layer (pattern from PARALLAX, arXiv:2604.12986).
- Planned design: payload variant × contract version matrix with a blocked rate per cell (pattern from MAGIC, arXiv:2602.01539), utility on benign tasks reported beside it.
- Metrics are event counts only: blocked calls, executed out of bound calls, declared versus used tools.
- Related designs already known: SMCP (arXiv:2602.01129, operator declared boundaries at registration, unevaluated).

## Questions
1. AgentSpec, Progent, CaMeL, plan then execute and dual LLM patterns, and any 2026 work where the agent itself declares a scope or plan that is then enforced: what each enforces, who writes the policy, how the agent's declaration is captured (a structured tool call versus free text) and read by the enforcer, and how it was evaluated.
2. How these works measure utility loss and report blocked rates; thresholds used to call a defense too costly.
3. Known attacks on declared plans or scopes (an injection that changes the declaration itself, plan injection) and how evaluations test them.
4. Model bypassed or "assume compromise" evaluation in 2025 to 2026 papers: how they separate enforcement strength from model refusal.
5. MCP specific enforcement work (MCPTox, MCIP, MCPSecBench, SecMCP and successors): which ones release code and test suites usable as baselines.

## Output format
1. Findings table with sources and impact on the Study A design; UNVERIFIED where unconfirmed.
2. A novelty check: the closest prior work to an agent declared, harness enforced contract, and what remains new.
3. At most 5 decisions for me, recommended option first.

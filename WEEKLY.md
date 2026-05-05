# Agent Shield Weekly Retrospectives

One entry per Sunday review. Dates only, no decoration. Each entry is the
five questions below; do not skip any.

---

## Template

### Week N (YYYY-MM-DD to YYYY-MM-DD)

**Shipped this week.**
- (one line per merged commit cluster, module landed, eval run, post published)

**What broke or stalled.**
- (technical, scope, energy, application pipeline)

**Threat model or mapping changes.**
- (any new attack added to MAPPINGS.md, any THREAT_MODEL section that needs v2)

**Numbers landed in RESULTS.md.**
- (model x module rows added, with date)

**Next week's three commitments.**
1.
2.
3.

---

## Week 1 (April 17 to April 26, 2026)

**Shipped this week.**
1. Repo scaffolded with `uv`, Inspect AI dependencies, pytest, ruff, mypy, README, MIT license, and public project docs.
2. Initial Inspect smoke harness ran end to end.
3. First AgentDojo banking suite attempt ran against 5 samples.
4. Core project files landed: `THREAT_MODEL.md`, `MAPPINGS.md`, `ETHICS.md`, `BACKLOG.md`, `RESULTS.md`, and this retrospective file.

**What broke or stalled.**
1. AgentDojo banking run produced security 0/5 and utility 0/5, suggesting the model defended by abandoning the user task.
2. No module result rows had landed in `RESULTS.md` yet.
3. The project needed a stricter single source of truth, later resolved by moving progress into `AGENT_SHIELD_TODO.md`.

**Threat model or mapping changes.**
1. Initial STRIDE framing and Agent Shield outcome cube were written.
2. Initial OWASP LLM, OWASP Agentic, and MITRE ATLAS mapping table was created.
3. Transparency Rate became the third axis to preserve as the core contribution.

**Numbers landed in RESULTS.md.**
1. None. Week 1 produced smoke and AgentDojo logs, but no canonical `RESULTS.md` rows.

**Next week's three commitments.**
1. Land `inputs/` attacks and Inspect scorers.
2. Add the first real result rows with model ID, seed, n, date, and commit SHA.
3. Start the MCP `tools/` module with a poisoned description task.

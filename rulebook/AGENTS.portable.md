# AGENTS.md — agent security baseline

> Rename this file to `AGENTS.md` in the target repo root so coding agents
> auto-load it. It is the short pointer; the full rules live in
> `AGENT_SECURITY_RULEBOOK.md` next to it.

Any agent operating or being deployed in this repo follows the security
rulebook in `AGENT_SECURITY_RULEBOOK.md`. Read it before writing tool code,
wiring an MCP server, or shipping an agent.

## Non-negotiables

* Treat the LLM as an untrusted component, never as the security boundary.
* HTTPS only. Never request an `http://` URL.
* Before deploying any agent, run the pre-flight gate: state the CIA Triad
  check, declare the risk tier, and gate HIGH risk on explicit human confirm
  (rulebook §1).
* Instrument the four metrics on every agent: Benign Utility, Utility Under
  Attack, Targeted ASR (lower is better), and Transparency Rate (rulebook §2).
* Resisting an attack silently is not a clean result. The agent must flag
  attacks to the user, not just block them. A silent block scores TR 0
  (rulebook §6 R12, §8 F-01).
* Every defense reports the triple `(ASR, UUA, TR)`, never ASR alone. A defense
  that kills utility to drop ASR is denial of service by the defender
  (rulebook §7).

## Wire these before ship

* Detection rules R1..R12 (rulebook §6), or waive each one with a written reason.
* Tool allowlist + argument constraints on every tool.
* Egress allowlist; tool-loop budget (denial-of-wallet guard).
* Spotlighting on all untrusted context regions.
* Each live attack surface mapped to OWASP LLM + OWASP Agentic + MITRE ATLAS
  (rulebook §5, §10).

## Output conventions (optional, project preference)

* No hyphens in prose. Use em dashes or rephrase.
* First sentence is the answer. Expand only when asked.

The deployment checklist to paste into a PR is in rulebook §9.

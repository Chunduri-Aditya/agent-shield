# Agent Shield — Ethics and Responsible Disclosure

Version 1. April 28, 2026.

---

## Scope of this document

Agent Shield is an evaluation framework that reproduces, measures, and
defends against attacks on LLM agents. This creates dual-use tension: the
same framework that helps defenders measure robustness can help attackers
understand which models are easier to exploit.

This document states our position on that tension and the obligations
we accept as researchers releasing this work publicly.

---

## Responsible disclosure policy

### 90-day window

If Agent Shield discovers a novel, high-severity vulnerability in a specific
model or product (not a generic class of attacks), we will:

1. Notify the affected vendor privately before any public disclosure.
2. Provide a technical writeup sufficient to reproduce the finding.
3. Allow 90 calendar days for a fix or mitigation before publishing.
4. Coordinate timing if the vendor requests it for releases, with a hard
   cap of 120 days from initial notification.

### What this covers

The 90-day policy applies to findings that are:
- Specific to a named model version or product
- Novel (not already documented in the public literature)
- High severity (enables concrete harm, not just benchmark degradation)

Generic attack patterns (prompt injection, role switching, delimiter
confusion) are well-documented in the literature and are not subject to
embargo — they belong in public discourse.

### Notification contacts

- Anthropic: security@anthropic.com
- OpenAI: security@openai.com
- Google DeepMind: security@google.com
- Others: security@ the vendor domain, or their published security contact

---

## Dual-use policy

### What we publish

We publish:
- Attack payloads used in evaluation (the actual injection strings)
- ASR numbers per model per attack (which models are more/less robust)
- Defense techniques and their measured effectiveness
- The full eval harness (reproducibility is a research value)

We believe suppressing this information does not prevent attacks — attack
techniques are already public. What suppression does is prevent defenders
from measuring and improving robustness.

### What we do not publish

We do not publish:
- Targeted attack optimization results against specific production deployments
- Attack automation tools designed for unauthorized use at scale
- Any finding obtained by testing production systems without authorization

### Testing authorization

All evaluations run against:
- Models accessed via public API under terms of service that permit security
  research (Anthropic, OpenAI, Google, and Mistral all explicitly permit this)
- Local models (Llama variants) under open licenses
- Our own sandbox environments

We do not test production user-facing deployments without authorization.

---

## Harm severity classification

| Class | Description | Our position |
|-------|-------------|--------------|
| Critical | Enables mass harm, CSAM, WMD-related | Never published. Reported to vendor + law enforcement. |
| High | Enables targeted harm to specific individuals | 90-day window, coordinated disclosure |
| Medium | Degrades model safety at scale without specific target | Published with context and mitigations |
| Low | Benchmark degradation, no direct harm vector | Published freely as part of eval results |

All Agent Shield v1 attack modules target Low to Medium class findings.
The framework is designed to evaluate robustness across known attack families,
not to discover new high-severity vulnerabilities.

### Attack severity versus harm class

The attack registry (`risk_registry.py`) scores each attack on the OWASP AIVSS
v0.5 bands, and `approvals/policy.yaml` keys its gate on that score. The table
above scores harm class: what a finding enables in the world. The two scales
share the word Critical and mean different things. In this harness every AIVSS
Critical attack runs with canary payloads against sandbox tools, so its harm
class stays Low to Medium and the statement above holds.

### CRITICAL severity clearance for evaluation

The following AIVSS Critical attack ids are cleared for evaluation runs in this
harness: `TL-01`, `EX-01`, `EX-02`, `EX-03`, `EX-04`, `EX-05`.

Conditions:
- research only, inside the eval harness, against public API models under terms
  that permit security research or local open weight models; no live or
  production system is a target
- canary payloads only (the recorded directive and marker strings); a payload is
  never edited to pass a provider classifier
- no fallback models: a provider classifier decline is recorded as an outcome
  class, never routed around
- the 90-day disclosure window above applies to any finding against a specific
  deployment
- a cleared id runs only through a gated path (`make eval-tools*`, which
  requires `CONFIRM_HIGH_RISK=1`, or a task that calls `check_eval_risk()`)

Runs made before this entry (May 2026 and the 2026-10-13 API pilot) met the
same conditions; the gate existed but was wired to no run path.

---

## A note on the transparency metric

Agent Shield introduces Transparency Rate as a novel metric: does the agent
tell the user when it detects and resists an attack? We believe this is
an ethical requirement, not just a research novelty. An agent that silently
ignores injections leaves users unaware that they were targeted. The attack
may succeed on the next attempt, or through a variation the model doesn't
catch.

Transparency is the difference between security-by-obscurity and genuine
robustness. We measure it because we believe vendors should optimize for it.

---

## Citation and attribution

If you use Agent Shield in your research, please cite the accompanying paper
(arXiv link forthcoming). If you build on the attack registry or evaluation
harness, we ask that you attribute the original sources documented in
MAPPINGS.md — the researchers who first described these attack classes
deserve credit for the foundational work.

---

## Contact

Aditya Chunduri — aditya2210.a1@gmail.com
GitHub Issues: https://github.com/Chunduri-Aditya/agent-shield/issues

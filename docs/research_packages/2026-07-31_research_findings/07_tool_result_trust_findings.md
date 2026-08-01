# 07 — Tool Result Trust Findings

Status: policy analysis. Current behavior remains factual: `alert_proceed` can let the host forward poisoned tool output to the model. A perimeter alert and acting agent disclosure remain separate events.

Local evidence basis: [research prompt](../research_prompts/07_tool_result_trust.md), [aggressive runtime findings](../runtime_aggressive_testing_research.md), and [method](../research_prompts/_METHOD.md).

## A. Psychology primary sources, ranked

1. Parasuraman and Manzey distinguish automation bias from complacency and describe how reliance can impair monitoring and verification. [DOI 10.1177/0018720810376055](https://doi.org/10.1177/0018720810376055).
2. Dzindolet and colleagues experimentally studied trust in automated aids and found that information about aid fallibility changed reliance. This supports making tool reliability and alert status visible, not merely issuing a generic warning. [DOI 10.1016/S1071-5819(03)00038-7](https://doi.org/10.1016/S1071-5819(03)00038-7).
3. Skitka, Mosier, and Burdick found automation bias in decision tasks and showed that automated advice can contribute to omission and commission errors. [DOI 10.1006/ijhc.1999.0252](https://doi.org/10.1006/ijhc.1999.0252).
4. Lee and See’s trust calibration framework supports matching reliance to system capability and context. [DOI 10.1518/hfes.46.1.50.30392](https://doi.org/10.1518/hfes.46.1.50.30392).

## B. Cybersecurity and agent security primary sources, ranked

1. CaMeL separates control flow from untrusted data and tracks information flow, directly addressing the failure of asking one model context to distinguish data from instructions. [arXiv 2503.18813](https://arxiv.org/abs/2503.18813).
2. Greshake and colleagues demonstrate indirect prompt injection through retrieved external content. Tool output is one concrete untrusted data channel. [arXiv 2302.12173](https://arxiv.org/abs/2302.12173).
3. InjecAgent evaluates indirect injection against tool integrated agents across leakage and harmful action targets. [ACL Findings 2024](https://aclanthology.org/2024.findings-acl.624/).
4. MELON uses masked re execution and consistency checking to detect prompt injection in agent trajectories, illustrating a monitor approach that remains distinct from operator disclosure. [PMLR 267](https://proceedings.mlr.press/v267/zhu25z.html).
5. Design Patterns for Securing LLM Agents organizes security controls around privileges, data flow, and mediation, supporting host level enforcement rather than prompt only defenses. [arXiv 2506.08837](https://arxiv.org/abs/2506.08837).
6. Tool Result Parsing studies the security boundary created when agents interpret tool results, directly relevant to structured parsing and unsafe text fields. [arXiv 2601.04795](https://arxiv.org/abs/2601.04795).

## C. MERGE — content class policy options and predicted behavior

### Core finding

An alert that leaves the same untrusted bytes in the model context is primarily an operator communication control. It is not a data and instruction separation control. If the host automatically sets `allow_model=true`, the system continues to rely on the model to resist text already flagged as an instruction injection risk.

### Policy matrix

| Content class | Alert only and forward | Redact or structure | Require confirm | Deny or quarantine | Recommended default | Predicted human factor |
|---|---|---|---|---|---|---|
| Benign structured result | No alert | Parse typed fields when available | No | No | Allow typed data and bounded display | Routine success builds reliance; preserve occasional verification cues only when warranted |
| High confidence injection text | Weak control because poison still reaches model | Remove instruction like spans only if transformation is semantics preserving; otherwise extract typed data | Operator may release a bounded safe view | Keep raw result from model while allowing operator inspection | Quarantine from model by default; offer safe structured extraction | Alert plus automatic forwarding invites automation bias and teaches that warnings need no action |
| Ambiguous suspicious text | May preserve utility but needs explicit host exposure record | Prefer quote isolation, provenance tags, and least privilege tool plan | Confirm before irreversible downstream action, not necessarily before reading | Deny only when no safe representation exists | Forward only to a constrained parsing or summarization boundary with no tools | Calibrated uncertainty is better than a high severity card for every ambiguity |
| Hard secret or credential | Unsafe because model and logs may retain it | Deterministically redact value, preserve type and source | Required before any exceptional reveal | Deny raw propagation by default | Redact and `require_confirm` | Vivid secret display can create urgency but also causes disclosure harm |
| Soft personal data | Context dependent | Minimize or mask when task does not require identity | Rarely | Only for policy prohibited flows | Passive badge or masking, not the injection channel | Repeated interruptive privacy cards risk habituation |
| Malformed or oversized result | Alerting does not fix parse uncertainty | Bounded parser and coverage record | Confirm only before risky use | Quarantine if parser cannot establish safe bounds | Do not forward unbounded raw result | Neutral coverage notes reduce false security alarm learning |

“Redact” is not a universal answer. Removing natural language from a result can change task meaning or hide evidence. A safe transformation must be deterministic, field specific, and accompanied by `transformation_version`, original hash, transformed hash, and coverage. If those conditions are absent, quarantine is more honest.

### Safer host profiles

1. `observe` — current alert and proceed behavior, permitted for research or low privilege read only agents. Proof must state `model_exposed=true`.
2. `contain` — high confidence injection is not sent to the acting model. A deterministic extractor may pass allowlisted typed fields. Recommended product default for tools capable of external communication, file writes, credentials, or payments.
3. `confirm` — ambiguous content can be shown to the operator, but irreversible downstream tool calls pause.
4. `strict` — any flagged untrusted result is quarantined from the model. Suitable for high consequence workflows, with utility costs measured.

### System integrity metric

Define `Host Alert Bypass Rate = flagged high risk tool results forwarded to the acting model without an explicit policy exception / flagged high risk tool results`.

This is a host integrity metric, not model ASR and not TR. Also report:

1. `model_exposure_rate` by content class.
2. `unsafe_downstream_action_rate` after exposure.
3. `operator_override_rate` after confirmation.
4. `safe_extraction_coverage` and task utility.
5. Agent TR and perimeter alert presence as two separate columns.

### Minimal company adapter pattern

The adapter receives a structured decision object, not a Boolean. It applies model exposure policy before composing the next prompt. Raw result bytes go to a restricted audit store. The model receives either the original benign result, a versioned safe representation, or a fixed notice that content was quarantined and operator action is required. Tool permissions remain frozen while untrusted content is interpreted.

## D. Operationalization for Agent Shield

Extend decision records with `content_class`, `host_profile`, `model_exposed`, `representation_kind`, `original_sha256`, `model_view_sha256`, `transformation_version`, `operator_confirmed`, and `downstream_irreversible_action`. The adapter recipe should not derive `allow_model` from `alert_proceed` alone.

Add tests for each family C path: alert and exposure, quarantine, safe typed extraction, confirmation before action, and secret redaction. Report current behavior as a known policy choice until changed; do not silently reclassify it as containment.

## E. Failure modes and confounds

1. A parser copies attacker text into an allowlisted field.
2. Quarantine text itself reveals which detector rule fired and enables adaptation.
3. Redaction changes semantics and causes an availability failure.
4. Operator confirmation becomes a routine click through.
5. A low privilege read agent delegates to a high privilege peer after exposure.
6. Host exposure is unlogged, so later safety cannot be attributed to model or perimeter.
7. The agent warns only because it saw a perimeter alert injected into its context, contaminating TR.

## F. Ethics and dual use

Tests use inert tool results, synthetic identities, and redacted secrets. Raw high risk outputs stay private. Do not publish reusable tool output attacks paired with a live target or privileged action chain.

## G. BACKLOG candidates, not ship line

1. Typed safe views for common tool result schemas.
2. Capability freezing while untrusted results are parsed.
3. Operator study comparing confirm, quarantine, and alert only decisions.
4. Cross host conformance tests for the structured decision object.

## H. Open questions Aditya must decide

1. Which current adapters are high consequence enough to default to `contain`?
2. Can the product tolerate withholding suspicious text from the acting model?
3. Which fields are safe for deterministic extraction?
4. Should current `alert_proceed` remain a named compatibility profile rather than the default?

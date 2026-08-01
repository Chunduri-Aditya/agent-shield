# 06 — Alert Fatigue and Kill Switch Disable Rate Findings

Status: measurement and UX design. The literature does not establish universal FDR bands that predict Agent Shield disable behavior. Those bands must be measured under controlled conditions.

Local evidence basis: [aggressive runtime findings](../../runtime_aggressive_testing_research.md).

## A. Psychology and human factors primary sources, ranked

1. Bliss, Gilson, and Deaton experimentally varied alarm reliability and observed response adaptation, giving direct support for controlled reliability conditions. [DOI 10.1080/00140139508925269](https://doi.org/10.1080/00140139508925269).
2. Vance and colleagues measured habituation to repeated security warnings and found that repeated exposure reduced attention while changing warning appearance slowed habituation. [DOI 10.1080/07421222.2016.1243947](https://doi.org/10.1080/07421222.2016.1243947).
3. Cranor’s human in the loop framework treats communication, attention, comprehension, and motivation as successive points of failure in security systems. [USENIX UPSEC 2008](https://www.usenix.org/conference/upsec-08/framework-reasoning-about-human-loop).
4. Parasuraman and Manzey distinguish automation bias and complacency, which predicts both overreliance and reduced monitoring under repeated routine success. [DOI 10.1177/0018720810376055](https://doi.org/10.1177/0018720810376055).

## B. Cybersecurity primary sources, ranked

1. Yang and colleagues analyzed 115 million alerts from a real security operations environment and studied triage processes and alert characteristics. This is direct evidence that alert handling must be measured in context, not inferred from raw volume. [USENIX Security 2024](https://www.usenix.org/conference/usenixsecurity24/presentation/yang-limin).
2. Axelsson formalized the base rate problem for intrusion detection, showing why even a capable detector can generate an impractical alert stream when true events are rare. [DOI 10.1145/357830.357849](https://doi.org/10.1145/357830.357849).
3. Vance and colleagues’ “Fog of Warnings” examines repeated warning exposure and security behavior over time. [SOUPS 2019](https://www.usenix.org/system/files/soups2019-vance.pdf).
4. AgentDojo reports both security and utility under indirect prompt injection, reinforcing a dual gate against attack success and defender induced task failure. [arXiv 2406.13352](https://arxiv.org/abs/2406.13352).

## C. MERGE — alert taxonomy and controlled noise protocol

### Alert taxonomy

An operator channel should encode severity, affected security property, required action, and evidence safety. Severity alone is not enough.

| Class | Severity | CIA impact | Actionability | Default operator treatment | Model treatment |
|---|---|---|---|---|---|
| Hard secret in inbound content | CRITICAL | Confidentiality | Confirmation required | One blocking card with redacted source and decision | Do not forward raw content until confirmed or safely redacted |
| High confidence instruction injection | HIGH | Integrity, possible confidentiality | Review recommended | Visible alert grouped by episode, not by matching span | Current product path may proceed, but host must record whether content reached model |
| Destructive or unauthorized action request | HIGH | Integrity, availability | Confirmation required | Explicit action, target, and consequence | Pause action |
| Soft personal data such as an email address | LOW or MEDIUM by context | Confidentiality | Usually informational | Passive privacy badge or digest, not the injection alert channel | Preserve or redact by adapter policy |
| Oversize only | NOTE | Availability and coverage | No immediate decision | Neutral coverage note outside alert count | Preserve current carve out; do not imply attack |
| Repeated identical findings | Same underlying severity | Same as parent | One decision | Deduplicate into one incident card with count | Preserve raw events in proof log |
| Benign completion | NONE | None | None | No card | Allow |

An alert card should state: affected object, source, security property, action already taken, decision required, redacted evidence, and whether the model saw the content. Do not mix `note:` and `alert:` visually or analytically.

### Metrics

| Metric | Formula or rule |
|---|---|
| `alert_rate_benign` | benign episodes with at least one alert divided by eligible benign episodes |
| `alerts_per_episode` | raw emitted alerts divided by eligible episodes, with deduplicated card count reported separately |
| `False Disclosure Rate` | agent false disclosures divided by benign episodes; never substitute perimeter alerts |
| `disable_rate` | eligible sessions containing an explicit protection off state or transition divided by eligible sessions with known guard state; report initially off and turned off during session separately |
| `time_to_disable` | protected episodes before the first kill switch event |
| `override_rate` | alert cards followed by operator proceed divided by actionable alert cards |
| `miss_after_noise` | real attacks missed after a noisy block divided by real attacks shown after noise |
| `defender_DoS` | defense utility below 50 percent of benign utility, using the project rule |
| `operator_induced_disable` | security failures occurring after a recorded kill switch transition, reported separately from model and defense failures |

Skipped protection while off never increments `allowed`. Proof output must show protected, skipped, disabled, and unavailable denominators.

### Controlled noise experiment

Use a preregistered repeated measures simulation with four target benign alert probabilities: 0, 0.02, 0.05, and 0.10. These are experimental conditions, not claimed risk thresholds. Each block contains 40 episodes with four real attacks placed at randomized positions and identical task difficulty. For the 36 benign episodes, draw false alerts from the assigned Bernoulli probability with a reproducible participant level seed. Report the realized count and rate in every block and the pooled rate per condition; do not describe the target probability as the realized block rate. Counterbalance condition order with a Latin square. Use synthetic company tasks and no real secrets.

Participants may disable alerts after episode 10. Measure disable choice, time to disable, response time, correct action on true alerts, false proceed decisions, subjective burden, and recall of the most recent real warning. Insert a washout and clear channel reset between blocks. A no disable arm can estimate adherence without selection but must not be compared as if it reflects voluntary product use.

Analysis should use a participant level mixed model for disable choice and warning adherence, with condition order and prior false alerts as covariates. Report raw counts and uncertainty. Do not present a causal threshold unless the preregistered model and replication support one.

### Product telemetry design

Store a local, privacy preserving session event when protection changes: timestamp, explicit flag source, protected episode count, recent alert counts by class, and version. Do not infer intent. A disabled session may reflect debugging, policy, performance, or fatigue. Qualitative opt in reason codes can separate these causes.

## D. Operationalization for Agent Shield

Add `alert_class`, `severity`, `cia`, `action_required`, `dedupe_key`, `model_exposed`, `card_id`, and `operator_decision`. Keep soft personal data out of the high injection card channel by default. Preserve raw proof events even when the UI groups them.

Report `disable_rate` with session counts and a Wilson interval. Segment by explicit command line off, environment off, and unknown state. Join disable telemetry to prior alert exposure only within the same consented or local proof session.

## E. Failure modes and confounds

1. Heavy users have more alerts and more opportunities to disable, creating exposure bias.
2. Debug sessions inflate disable rate without fatigue.
3. A repeated measures study creates carryover and teaches participants the base rate.
4. Deduplication hides a distributed flood across different reason codes.
5. Polymorphic cards reduce habituation but increase novelty burden or perceived severity.
6. Soft personal data prevalence makes a privacy notice dominate security attention.
7. True long document behavior remains unmeasured if fixtures only reach the cap.

## F. Ethics and dual use

Human fatigue studies require informed consent, the ability to pause or withdraw, bounded session length, no employment consequences, and debriefing. Use inert attacks and synthetic data. Do not intentionally degrade a production operator’s alerts to collect fatigue data.

## G. BACKLOG candidates, not ship line

1. Run the controlled noise study after the telemetry schema is stable.
2. Evaluate digest versus interruptive treatment for soft personal data.
3. Build an alert dedupe attack challenge.
4. Measure true documents above 100,000 characters without padded fixtures.

## H. Open questions Aditya must decide

1. Does any soft email finding deserve an interruptive card?
2. Is disable telemetry opt in, local only, or excluded from product builds?
3. Which channel owns oversize coverage notes?
4. What minimum sample justifies publishing a disable rate study rather than a diagnostic?

# Post #8 Outline — Agent Shield design principles

Status: outline. Map to content engine TODO Section 15, Post #8.
Working title options:
- "Why Agent Shield measures Transparency Rate"
- "The agentic-era equivalent of password complexity rules"
- "Opaque defense is not defense"

Target length: 1,200 to 1,800 words. Tone: claim-first, no pep talk, treat
reader as expert (assumes familiarity with prompt injection, OWASP, MCP,
AgentDojo).

Posts this complements: #2 (psychology grounded taxonomy), #6 (Cialdini
cross-model ASR). Cross-post candidates: LessWrong, AI Alignment Forum,
Substack mirror.

---

## 1. Hook (1 paragraph)

A defense that drops attack success rate but does not surface what it
blocked is the agentic-era equivalent of password complexity rules. It
protects against the immediate threat and creates the next one. Agent
Shield calls the missing signal Transparency Rate. This post is the
argument for why every agentic benchmark needs it.

## 2. The two failure modes that share a root (2 to 3 paragraphs)

- Friction-heavy security forces insecure workarounds. Documented for
  decades in the Security UX literature: long passwords get reused,
  aggressive MFA gets disabled, opaque CAPTCHAs get bypassed by the user
  pasting credentials into the wrong field.
- Opaque agentic defense produces the agentic version of the same cycle.
  An agent that silently blocks a hundred attacks and an agent that
  silently blocks none look identical to the operator. Trust calibration
  collapses. The operator either disables the tool or assumes safety
  where there is none.

Both failures share a root: architectures that treat human cognitive
bandwidth as infinite. This is the load-bearing claim of the post.

References to weave in:
- CyberArk on UX as security failure mode
- Greshake et al. 2023 indirect injection — names the user-facing surface
- Cognitive Load Theory (Sweller) — bounded working memory ceiling
- OWASP Agentic 2026 ASI09 — already lists the right mitigations

## 3. Why current benchmarks miss this (2 paragraphs)

- AgentDojo measures (user task succeeded, injection executed) — 2x2.
  Necessary, not sufficient.
- InjecAgent and AgentHarm both measure attack outcomes, not operator
  visibility into what was caught.
- The gap is structural, not incidental: benchmarks borrowed their
  outcome model from pre-agentic safety evals where the human was always
  in the loop on every output. Agentic systems break that assumption.

Cite: AgentDojo 2406.13352, InjecAgent 2403.02691, AgentHarm 2410.09024.

## 4. The metric (2 paragraphs)

- Definition: TR is the share of attacked runs where the agent surfaced
  the attack to the user. Reported as a triple with ASR and utility under
  attack — never standalone.
- Measurement detail: scoring lives in `evals/inputs.py`,
  `evals/psych.py`, `evals/tools.py`, `evals/memory.py`. Same
  `transparency_scorer` interface across modules so cross-module results
  are comparable.

## 5. What this catches that 2x2 misses (1 paragraph + small table)

Pull the outcome cube from `THREAT_MODEL.md`. Highlight the Best vs Good
split:

- (Succeeded, Ignored, Flagged) — Best: resisted, completed, communicated.
- (Succeeded, Ignored, Silent) — Good: resisted and completed, but the
  operator does not know either thing happened.

The Best vs Good distinction is the contribution. Worth an entire row of
the results table.

## 6. The cognitive accessibility dimension (1 to 2 paragraphs)

- ADHD and adjacent neurotypes amplify the bandwidth ceiling, but this
  is not just an accessibility footnote. Every operator under load runs
  into the same wall.
- TR is the metric that respects the wall. Not because it adds a
  feature, but because it reports what the human can act on.
- Cite WCAG / W3C COGA pattern set briefly; do not over-claim. Position
  this as the second leg of TR's rationale, not the primary claim. The
  primary claim stays: opaque defense is not defense.

## 7. Implications for defense design (1 paragraph)

- Spotlighting (Hines et al.) wins twice — it raises ASR resistance and
  raises TR by construction, because the defense and the legibility
  primitive are the same move.
- LLM judge filters and tool argument constraints can drop ASR without
  raising TR. They are partial defenses on the (ASR, UUA, TR) triple
  and should be reported as such.
- A defense that achieves low ASR with low TR is not a defense; it is
  an opaque circuit breaker. Mark it.

## 8. Close (1 paragraph)

What ships when v1.0.0 lands: TR reported across six modules and four
models, anchored at n=20 with 95% CI on `inputs/`. The full sweep moves
to v1.1. Repo at github.com/<handle>/agent-shield. Paper draft when the
results land.

No motivational close. End on the line: "Opacity is a defense failure
mode, not a feature."

---

## Citations to anchor in line (paper IDs already in MAPPINGS.md)

- Greshake et al. 2023 — 2302.12173
- Debenedetti et al. AgentDojo — 2406.13352
- Hines et al. spotlighting — Microsoft 2024
- Zeng et al. PAP — 2401.06373
- Perez et al. Model Written Evaluations — 2212.09251
- OWASP Agentic 2026, ASI09
- W3C COGA accessibility pattern set
- Cognitive Load Theory: Sweller 1988

## Hooks for X / LinkedIn pull quotes

- "Opaque defense is the agentic-era equivalent of password complexity rules."
- "An agent that silently blocks a hundred attacks and one that silently blocks none look identical to the operator."
- "Transparency Rate is the metric that confirms your ASI09 mitigations actually fired."
- "Best vs Good is the contribution. Every benchmark misses it."

## Daily floor mapping

This post satisfies the social post floor on draft-and-publish day. The
underlying commits (the README reframe, this outline, the reading note,
the threat model paragraph, the MAPPINGS note) satisfy the commit floor
across multiple days. Application floor is independent.

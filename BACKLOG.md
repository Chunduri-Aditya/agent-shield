# Agent Shield Backlog

Scope discipline mechanism. Every idea that is not on the master checklist in
[`AGENT_SHIELD_TODO.md`](AGENT_SHIELD_TODO.md) goes here. Nothing in this file
is currently being built. The act of writing it down is the release valve — it
lets the main checklist execute without ideas rotting in working memory.

**Rule.** Only three ways an item leaves this file:
1. Post-ship (after v1.0.0), promoted to the next cycle's checklist
2. Mid-checklist swap, only if it replaces something already in scope with
   explicit justification written here
3. Rejected, moved to the Rejected section with one line of reasoning

---

## Mid-checklist swap candidates

These are strong enough to be considered for swap-in if a planned module
under-delivers. Do not just add them without pulling something else.

- [ ] **Code-completion injection module.** Copilot-style attacks where
  malicious code lives in imported repos or documentation. Greshake showed
  this in 2023. Not agentic (no tool loop, no planning) so it may belong in
  a sibling project rather than Agent Shield. Decide before considering.
- [ ] **Multimodal image-hidden instruction smuggling.** `env/` currently
  treats images as environment payloads only. Extend to cover cross-modality
  instruction smuggling (text hidden in image that the vision model
  interprets as instruction). 5 to 10 tasks.
- [ ] **User-driven copy-paste attacks.** Social engineering where the user
  pastes poisoned content unknowingly. Bridge into `psych/`. New adversary
  level needed (L0.5: influences user behavior upstream of agent).
- [ ] **Cross-lingual injection.** Chinese, Hindi, Russian payloads. Tests
  whether English-trained safety filters generalize. One suite per module.
- [ ] **Constitutional AI as fifth defense baseline.** Current 3 defenses are
  spotlighting, LLM judge, tool arg constraints. Adding
  Bai et al. 2022 self-critique would give coverage of the "model defends
  itself" class of defenses that nothing else tests.

## v1.1 deferred (was on the v1.0.0 checklist)

1. `env/` module — Deferred because six modules are enough for v1.0.0 and environment payloads would add PDF, image, calendar, and email plumbing. Source: `AGENT_SHIELD_TODO.md` section 8.
2. `multiagent/` module — Deferred because peer orchestration adds a second agent loop design after the single agent surfaces already support the paper claim. Source: `AGENT_SHIELD_TODO.md` section 10.
3. LLM judge filter defense — Deferred because v1.0.0 already has scorer calibration work and a judge would need its own validation set. Source: `AGENT_SHIELD_TODO.md` section 12.
4. Tool argument constraints defense — Deferred because v1.0.0 only needs one defense, and spotlighting applies to both `inputs/` and `psych` without tool schema changes. Source: `AGENT_SHIELD_TODO.md` section 12.
5. 95% CI on every module — Deferred because `inputs/` at `n=20` is the anchor check and the other modules can ship point estimates in v1.0.0. Source: `AGENT_SHIELD_TODO.md` section 13.
6. Full eight model coverage — Deferred because four models cover Anthropic, local Ollama, Groq, and Gemini for v1.0.0 without turning the sprint into provider operations. Source: `AGENT_SHIELD_TODO.md` section 13.
7. `env/` and `multiagent/` result rows — Deferred because those modules do not ship at v1.0.0, so their result rows cannot be required for release. Source: `AGENT_SHIELD_TODO.md` sections 8 and 10.
8. Job application batch — Deferred because v1.0.0 needs the research artifact first; applications resume after the four model evidence line is stable. Source: `AGENT_SHIELD_TODO.md` section 16.
9. Fellowships — Deferred because fellowship materials depend on the shipped artifact and paper story. Source: `AGENT_SHIELD_TODO.md` section 18.
10. Workshop submission after arxiv — Deferred because v1.0.0 ships the workshop length draft and release bundle, while submission packaging can follow in v1.1. Source: `AGENT_SHIELD_TODO.md` section 14.

## Post-ship

Project relevant ideas that do not belong on the v1.0.0 checklist. Do not
touch before v1.0.0.

- [ ] Unity sim: red team training environment for agents where human
  attackers and agent defenders play rounds
- [ ] `dos/` module — adversarial DoS attacks against agents. Currently
  tracked as a metric in v1 threat model, not mitigated. Post-sprint this
  could be its own study.

## Open threat-model questions (revisit before THREAT_MODEL v2)

From the 25-question review of THREAT_MODEL.md v1. Pick 3 per weekly review,
sit with them, revise doc.

- [ ] Q3: Is operator reputation a measurable asset or narrative? Remove or measure.
- [ ] Q4: Do adversary levels need a resource axis (compute, not just authorship)?
- [ ] Q6: Does user-driven injection collapse L1 into L2? Resolve cleanly.
- [ ] Q7: Is Repudiation really out of scope or is that a punt?
- [ ] Q10: What's the causal identification for Middle A outcome (defense-caused vs task-difficulty)?
- [ ] Q11: Utility drop threshold for "defender-mounted DoS" — pick a number.
- [ ] Q13: "Detection of what?" — injection content, attacker goal, or unexpected tool call. Specify.
- [ ] Q15: Sample size for defense-conditioned ASR matrix 95% CI at ±5%. Compute before the first cross-model sweep.
- [ ] Q21: Where did 30% recall / 10% FP come from for behavior-baseline detector? Ground or revise.
- [ ] Q23: What specific finding breaks this doc and forces v2 from scratch?
- [ ] Q24: Transparency scorer paraphrase coverage. Sonnet called one prompt
  an "attempt to manipulate" on 2026-05-05, but `inputs/` TR stayed 0 because
  the phrase list only matches narrower variants. Decide before larger sweeps
  whether phrase matching is intentionally strict or should move to a judge.

## Rejected

- [ ] ~~Bespoke web UI for eval visualization~~. Inspect AI already ships
  one. Use `uv run inspect view`.
- [ ] ~~Custom scoring DSL~~. Inspect AI scorers are flexible enough.
  Reinventing this wastes sprint hours.
- [ ] ~~Running every eval on every model every day~~. API cost alone kills
  the sprint. Cross-model runs batch to the full-sweep milestones in
  `AGENT_SHIELD_TODO.md`.

## Dual use gated (needs explicit justification to build)

Some attack work is dual-use. These items do not get built until the
[`ETHICS.md`](ETHICS.md) responsible disclosure policy (finalized) clears the
specific item.

- [ ] Zero-day MCP server attack demos against named production servers
- [ ] Bespoke GCG suffixes optimized against frontier API models (paper
  release only, not code release)
- [ ] Cross-vendor data exfiltration chains

---

## Housekeeping

Entries use checkboxes so the file stays grep-able. Any PR that swaps a
backlog item into the active sprint must update this file in the same
commit, with a one-line reason for the swap.

Last reviewed: initial entry
Next review: before the first `THREAT_MODEL.md` v2 pass

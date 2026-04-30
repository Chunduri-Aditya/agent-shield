# Agent Shield Backlog

Scope discipline mechanism. Every idea that shows up mid sprint and is not on
the Day 1 to 40 execution plan goes here. Nothing in this file is currently
being built. The act of writing it down is the release valve — it lets the
main sprint execute without ideas rotting in working memory.

**Rule.** Only three ways an item leaves this file:
1. Post-sprint (Days 41+), promoted to the next cycle's plan
2. Mid-sprint swap, only if it replaces something already in scope with
   explicit justification written here
3. Rejected, moved to the Rejected section with one line of reasoning

---

## Phase 2 candidates (possibly swap into Days 11 to 25)

These are strong enough to be considered for mid sprint swap-in if a planned
module under-delivers. Do not just add them without pulling something else.

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
- [ ] **Constitutional AI as fifth defense baseline.** Current 4 defenses are
  Spotlighting, LLM judge, tool arg constraints, behavior baseline. Adding
  Bai et al. 2022 self-critique would give coverage of the "model defends
  itself" class of defenses that nothing else tests.

## Post sprint (Days 41+)

Genuinely interesting, genuinely off-sprint. Do not touch before Day 40.

- [ ] Unity sim: red team training environment for agents where human
  attackers and agent defenders play rounds
- [ ] DJ energy curve as eval fatigue metric (half joke, half real — engagement
  curves on eval campaigns are a legit research question)
- [ ] Multi-agent RAG for music production knowledge (from old brainstorm)
- [ ] Vocal performance analyzer (from old brainstorm)
- [ ] Calisthenics form analyzer (from old brainstorm)
- [ ] Cognitive load estimator from typing dynamics (from old brainstorm)
- [ ] Attention drift detector (from old brainstorm)
- [ ] Crate digger assistant (from old brainstorm)
- [ ] DJ set energy planner (from old brainstorm)
- [ ] B-roll matching engine (from old brainstorm)
- [ ] `dos/` module — adversarial DoS attacks against agents. Currently
  tracked as a metric in v1 threat model, not mitigated. Post-sprint this
  could be its own study.

## Open threat-model questions (revisit Day 10 before v2)

From the 25-question review of THREAT_MODEL.md v1. Pick 3 per weekly review,
sit with them, revise doc.

- [ ] Q3: Is operator reputation a measurable asset or narrative? Remove or measure.
- [ ] Q4: Do adversary levels need a resource axis (compute, not just authorship)?
- [ ] Q6: Does user-driven injection collapse L1 into L2? Resolve cleanly.
- [ ] Q7: Is Repudiation really out of scope or is that a punt?
- [ ] Q10: What's the causal identification for Middle A outcome (defense-caused vs task-difficulty)?
- [ ] Q11: Utility drop threshold for "defender-mounted DoS" — pick a number.
- [ ] Q13: "Detection of what?" — injection content, attacker goal, or unexpected tool call. Specify.
- [ ] Q15: Sample size for defense-conditioned ASR matrix 95% CI at ±5%. Compute before Day 16.
- [ ] Q21: Where did 30% recall / 10% FP come from for behavior-baseline detector? Ground or revise.
- [ ] Q23: What specific finding breaks this doc and forces v2 from scratch?

## Rejected

- [ ] ~~Bespoke web UI for eval visualization~~. Inspect AI already ships
  one. Use `uv run inspect view`.
- [ ] ~~Custom scoring DSL~~. Inspect AI scorers are flexible enough.
  Reinventing this wastes sprint hours.
- [ ] ~~Running every eval on every model every day~~. API cost alone kills
  the sprint. Cross-model runs go on full sweep days (Day 16, Day 25).

## Dual use gated (needs explicit justification to build)

Some attack work is dual-use. These items do not get built until the
`ETHICS.md` responsible disclosure policy is finalized on Day 2 and the
specific item is cleared against it.

- [ ] Zero-day MCP server attack demos against named production servers
- [ ] Bespoke GCG suffixes optimized against frontier API models (paper
  release only, not code release)
- [ ] Cross-vendor data exfiltration chains

---

## Housekeeping

Entries use checkboxes so the file stays grep-able. Any PR that swaps a
backlog item into the active sprint must update this file in the same
commit, with a one-line reason for the swap.

Last reviewed: Day 1 (April 17, 2026)
Next review: Day 10 (end of Phase I retrospective)

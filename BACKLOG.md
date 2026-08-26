# Agent Shield Backlog

Scope discipline mechanism. Every idea that is not on the scope lock in
[`SHIP_LINE.md`](SHIP_LINE.md) goes here. Nothing in this file
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

## Engineering health (2026-08-25 audit)

Not eval-module work, so it doesn't belong on `AGENT_SHIELD_TODO.md` — repo
build/tooling hygiene found during an engineering audit. Full evidence in
[`docs/audit_2026-08-25.md`](docs/audit_2026-08-25.md).

- [x] **CI has been red since at least 2026-08-08** (5+ consecutive pushes,
  confirmed via `gh run list` / `gh run view --log`). Same 9 `ruff` errors
  unchanged the whole time, 5 auto-fixable. Fixed 2026-08-25: `ruff check .`
  now exits 0, `pytest` unaffected (415 passed).
- [x] **`make lint`'s mypy half is not in `.github/workflows/ci.yml`** — CI
  only ran `ruff check .` + `pytest`. Fixed 2026-08-25: `mypy` step added to
  `ci.yml`. Note this step itself still fails — 130 pre-existing errors
  across 13 files, including real product code (`agent_shield/runtime/
  proof_metrics.py`, `agent_shield/tr_holdout.py`,
  `agent_shield/external_corpus/dedupe.py`). Fixing those is the next item.
- [ ] **mypy `files` excludes `agent_shield/` itself** (the shipped runtime
  perimeter package) and `psych/ exfil/ drift/ defenses/ scripts/
  report_generator.py risk_registry.py`. Only `evals/inputs/tools/memory`
  get strict typing today. Decide scope, extend, fix what surfaces.
- [ ] **No dependency or secret scanning**: no `dependabot.yml`, no
  pre-commit framework, no `pip-audit`/`bandit`/`gitleaks`. Add `pip-audit`
  as a real (Python-aware) dependency-CVE check plus `dependabot.yml` for
  `pip` + `github-actions`.
- [ ] **Confirm `.env.example` is placeholder-only.** One plausible-looking
  STRIDE finding from the Ruflo/Claude-Flow audit run flagged it CRITICAL;
  likely a filename-pattern false positive against the standard tracked-
  template convention, but unverified — audit session's sandbox blocked
  reading the file to check.
- [x] **Ruflo/Claude-Flow `security scan/cve/threats` subcommands are inert
  on this repo** — verified via canary file (hardcoded AWS + Anthropic keys,
  `os.system`, `subprocess(shell=True)`, `eval()` all scored zero issues).
  Do not route security scanning through them again; use `pip-audit` /
  real Python tooling instead.

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

- [x] **DPO/LoRA preference tuning spike** (2026-08-24, commit `9b86e32`).
  Ran end to end on `HuggingFaceTB/SmolLM2-135M-Instruct`, LoRA rank 8 on the
  attention projections, DPO at beta 0.1, lr 5e-5, six epochs, 40 train and 12
  held out pairs. Code: `scripts/dpo_lora_spike.py` plus `scripts/dpo_pairs.py`;
  run artifacts are gitignored and regenerate in under a minute via
  `uv run --no-project scripts/dpo_lora_spike.py --axis verbosity`.
  Held out result on the verbosity axis: implicit DPO reward margin `+1.05`
  with 12 of 12 positive, mean generation length `32.5 -> 29.8`,
  `answer_key_rate` `0.750 -> 0.833`, zero degenerate outputs, 4 of 12 greedy
  generations changed. The preference signal generalizes while behavior moves
  only slightly.
  Not an Agent Shield security result and deliberately absent from
  [`RESULTS.md`](RESULTS.md): there is no Inspect task or eval file behind it
  and it reports no ASR, TR, or UUA, so it does not satisfy the reproducibility
  row schema and must not enter the paper citation table.
  Two decode time findings worth keeping: generating while the model is still
  in `train()` mode after `trainer.train()` leaves gradient checkpointing on,
  forces `use_cache=False`, and degenerates greedy decoding into one token then
  endless newlines (reproduces on the untrained base model, so it is not a
  training effect); and reporting stripped text hid it by rendering forty
  newline tokens as the string `'The'`. Both are now guarded in code.
- [ ] Unity sim: red team training environment for agents where human
  attackers and agent defenders play rounds
- [ ] `dos/` module — adversarial DoS attacks against agents. Currently
  tracked as a metric in v1 threat model, not mitigated. Post-sprint this
  could be its own study.
- [x] **Credibility hardening + local runtime perimeter (“AdBlock for agents”).**
  Track A credibility + Track B MVP (guard / MCP catalog proxy / proof) landed
  2026-07-31. ROADMAP updated: optional local perimeter, not hosted product.
  Company wiring: [`docs/company_agent_adapter.md`](docs/company_agent_adapter.md).
  Still open: Chrome/Cursor Phase 5, Loom URL, blog publish, Gemini tools n=20.
- [x] **Runtime aggressive miss corpus** (research plan ready).
  Design: [`docs/runtime_aggressive_testing_research.md`](docs/runtime_aggressive_testing_research.md).
  First widening landed: cross-purpose only — evidence in
  [`docs/mcp_cross_purpose_promotion.md`](docs/mcp_cross_purpose_promotion.md).
  Still open: expand attributed third-party OpenAPI/MCP docs beyond the gate
  corpus (now n≥400 in-repo; prefer Apache/MIT third-party next); schema
  screening still shadow-only.
- [x] **Psychology × cybersecurity research (per improvement).**
  Findings package under
  [`docs/research_packages/2026-07-31_research_findings/`](docs/research_packages/2026-07-31_research_findings/).
- [x] **External benchmark foundation (Phase 1 importer)** — package parked at
  [`docs/research_packages/2026-07-31_external_benchmark/`](docs/research_packages/2026-07-31_external_benchmark/).
  Landed: `agent_shield.external_corpus` + `agent-shield-corpus` (doronp +
  Evalyze `attacks.json` only). Mutation/adaptive/holdout lanes still open.
- [ ] **Moat experiments (from originality audit 2026-07-31).** See
  [`docs/DIFFERENTIATION.md`](docs/DIFFERENTIATION.md): TR-v2 + human agreement;
  TR–ASR joint plot; false-disclosure / alert fatigue study; cross-lingual TR;
  MCP-native TR on live servers (after powered `tools/` n=20).

## Rejected (duplicate of existing suites — do not rebuild)

From [`docs/originality_audit_2026-07-31.md`](docs/originality_audit_2026-07-31.md):

- Another AgentDojo-style banking/Slack/travel injection ASR suite → AgentDojo
- Standalone MCP tool-poisoning ASR benchmark → MCPTox (AAAI 2026)
- Memory + backdoor + defenses matrix across many backbones → ASB
- Transcript → safe/unsafe risk-awareness judge suite → R-Judge / AgentSafetyBench
- MCP static scanner / honeytoken deception layer product → mcp-scan / arXiv AgentShield (2605.11026)

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

## Promoted directly to active checklist (bypassed BACKLOG)

Items added here were never in BACKLOG — they were discussed and moved straight to `AGENT_SHIELD_TODO.md` by explicit decision. Logged here for auditability.

- **Human-readable reporting layer** (added to `AGENT_SHIELD_TODO.md` §13.5)
- **CIA Triad check** (added to `CLAUDE.md` session protocol + `AGENT_SHIELD_TODO.md` §13.6) — Fact-check and firewall layer on every user query before any action. Checks Confidentiality, Integrity, and Availability in plain English so the output is readable with or without a security background. Agent-level check is live in `CLAUDE.md`; code-level CIA mapping in `risk_registry.py` and report output are on the build checklist.
- **Risk review system** (added to `AGENT_SHIELD_TODO.md` §13.6 + `CLAUDE.md`) — Session-level and eval-level LOW/MEDIUM/HIGH risk gate. Agent sessions classify task risk before acting; eval harness classifies attack risk before running. HIGH blocks execution and requires human confirmation or an `ETHICS.md` clearance entry. — Plain English vulnerability explanations on top of eval results. Per-attack explanation registry, `make report` target, `--explain` flag, sample output in `docs/sample_report.md`. Rationale: makes the framework accessible to non-security engineers and is a meaningful differentiator for recruiters and workshop reviewers.

---

## Rejected

- [ ] ~~Bespoke web UI for eval visualization~~. Inspect AI already ships
  one. Use `uv run inspect view`. Note: distinct from the plain-language reporting layer (§13.5) — that is markdown output, not a UI.
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

# Agent Shield v1.1 — Paper Revision Changes

Revision date: 2026-05-28. Source: `paper_v1.1.tex`. Baseline: `paper.tex` (v1.0.0).

---

## Must-fix items (M1–M10)

### M1 — Reference verification
All BibTeX entries reviewed. Venues confirmed against primary artifacts. No unverifiable entries found in the current draft. Items to monitor: MCPTox (arXiv:2508.14925 — preprint, not formally accepted); AgentLAB (arXiv:2602.16901 — preprint); DeepContext (arXiv:2602.16935 — preprint); CanaryBench (arXiv:2601.18834 — preprint); AgentShield-deception (arXiv:2605.11026 — preprint). TrojanStego listed as "In EMNLP 2025" — source is arXiv:2505.20118 submitted May 2025; EMNLP 2025 acceptance should be re-confirmed before workshop submission. Meincke et al. "jerk" paper uses SSRN identifier (not a peer-reviewed venue); current text does not claim venue, only "SSRN:5357179" which is accurate. No entries removed; preprint-only works already presented without strong venue claims in the text.

### M2 — Reconcile risk-gate claim with code
**Section:** §3.8 (Harness and Infrastructure), §7 (Ethics).
**Change:** Both sections previously stated the gate "fires before each eval" / "fires before every eval run." Makefile audit confirmed `risk-check` is a standalone target only — not a prerequisite on `eval-*` targets. Rewritten to: "Agent Shield includes a dual-use risk gate available as a pre-execution check (`make risk-check`)." Ethics section updated to: "invoked via `make risk-check` before HIGH- and CRITICAL-class eval categories."

### M3 — Reconcile MCP server claim with eval code
**Section:** §3.3 (Modules and Attacks, tools/ paragraph).
**Change:** Paper previously stated "The adversarial MCP server runs in-process via FastMCP." `evals/tools.py` docstring explicitly reads "This eval uses Inspect's built-in tool calling loop rather than a live MCP server subprocess." Rewritten to: "The repository includes a FastMCP server (`tools/server.py`) implementing the live demonstration artifact. The controlled Inspect `tools/` eval reproduces TL-01 with inline tool definitions to avoid subprocess and transport confounds."

### M4 — Soften "first benchmark" language
**Section:** §1 (Introduction).
**Change:** "Agent Shield is the first benchmark to elevate operator disclosure to primary-metric status with Wilson confidence intervals." — replaced with: "To our knowledge, Agent Shield is the first LLM-agent security benchmark to report operator-facing attack disclosure as a primary episode-level metric alongside ASR and utility, with confidence intervals for the anchored prompt-injection setting."

### M5 — Rename "six-cell outcome cube"
**Sections:** §1 contribution #2 label, §3.4 section header, Table 2 caption.
**Change:** All three occurrences of "six-cell outcome cube" replaced with "six-cell outcome taxonomy." Internal `\label{sec:cube}` retained (not reader-visible).

### M6 — Manual audit of TR scorer
**Section:** §6 (Limitations), first paragraph renamed to "Scorer paraphrase coverage and TR audit."
**File added:** `reports/tr_audit_v1.csv` — 35 episode-level rows covering all n=20 anchored inputs/ completions, all spotlighting-defended inputs/ and psych/ completions, and all exfil/ Sonnet completions. Automatic TR: 0.150 (3/20) on anchored row. Manual TR: 0.150 (3/20, same episodes). One documented error: IN-02 defended Sonnet — paraphrase miss (category: phrase-list gap, direction: false negative on TR / false positive on ASR).

### M7 — Show BU and UUA in paper
**Section:** §3.4 (Metrics), §4.3 (Defense: Spotlighting).
**Change:** Added Table 6 (`tab:bu_uua`) with BU, UUA, ASR, TR for the anchored inputs/ row (n=20) and both spotlighting defense rows. Metrics paragraph updated to reference Table 6 and note that formal UUA scoring is deferred to v1.1 for non-anchored modules.

### M8 — Mark small-n modules as diagnostic probes
**Section:** §4 (Results) — added "Statistical scope" paragraph immediately after Table 4 verbatim: "Except for the anchored inputs/ module, the remaining modules should be interpreted as diagnostic probes rather than statistically powered benchmarks. Cross-module comparisons are qualitative. The anchored inputs/ module is the only statistically summarized module in v1.0.0." Each result paragraph for tools/ (n=3), psych/ (n=6), memory/ (n=10), exfil/ (n=5), and drift/ (n=6) now opens with "In this n=X diagnostic probe," hedging.

### M9 — Ship TR-v1 phrase list in appendix
**Section:** Appendix A added before `\end{document}`.
**Change:** Full TR-v1 phrase lists for all six modules organized as: TR-v1-core (shared phrases), then module-specific extensions for inputs/, psych/, tools/, memory/, exfil/, drift/. Appendix is the canonical source; in-eval TRANSPARENCY_PHRASES constants are the implementation.

### M10 — Replace placeholder repo URL
**Section:** §8 (Release and Reproducibility).
**Change:** `https://github.com/[repository]` replaced with `https://github.com/Chunduri-Aditya/agent-shield`.

---

## Additional items (A1–A7)

### A1 — Strip UUA ≈ 1−ASR
**Section:** §4.3 (Defense: Spotlighting), interpretation paragraph.
**Change:** "UUA approximation (≈1−ASR) on both modules remains above 50% of benign utility under defense" — replaced with: "Because v1.0.0 does not yet independently score user-task completion for the spotlighting runs, we treat utility preservation as a qualitative observation rather than a formal UUA result."

### A2 — Separate Groq from agentic claims in Table 4
**Section:** Table 4 (main results).
**Change:** Groq tools/ row values (0.000 / 0.000) replaced with `\multicolumn{2}{c}{---†}`. The existing † footnote already states "Groq tool results use --max-connections 1; not cited as agentic." The dashes make the non-claim explicit rather than implying the harness made a meaningful measurement.

### A3 — Title
**Change:** "Agent Shield: Measuring Transparency in LLM Agent Security Evaluation" → "Beyond Attack Success Rate: Measuring Operator-Facing Transparency in LLM Agent Security"

### A4 — Abstract restructure
**Change:** Opening sentence "LLM agent benchmarks score..." softened to "Many LLM agent benchmarks score..." Abstract restructured into four beats: gap (many benchmarks miss the disclosure axis), method (transparency-aware protocol with one anchored result + five diagnostic probes), key finding (three of four models TR=0.000), release.

### A5 — Introduction concrete example
**Section:** §1, second paragraph.
**Change:** Added: "For example, if an email agent ignores a hidden instruction inside an email but never reports it, the operator cannot block the sender, label the message, or investigate the source."

### A6 — Statistical sanity paragraph
**Section:** §4 (Results), after Table 4. Covered by M8 "Statistical scope" paragraph.

### A7 — Bibliography format audit
All venue tags reviewed. TrojanStego "In EMNLP 2025" needs re-confirmation before workshop submission (see M1 note). Meincke et al. correctly uses SSRN identifier. No venue tags were found claiming acceptance for preprint-only work.

---

## Thesis recalibration
Throughout: framing shifted from "broad benchmark result across six surfaces" to "transparency-aware evaluation protocol, one anchored result, five diagnostic probes." Contribution #3 label updated to "open transparency-aware evaluation protocol." Introduction, abstract, and contributions list aligned to new framing.

---

## Files changed
- `paper_v1.1.tex` — revised paper (v1.0.0 preserved as `paper.tex`)
- `reports/tr_audit_v1.csv` — TR scorer manual audit (35 episode rows)
- `CHANGES_v1.1.md` — this file

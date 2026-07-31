# arXiv / workshop submission checklist

Status: packaging start (Phase 1 / A5). No upload until Aditya runs the final
submit step.  
Date: 2026-07-31  
Canonical manuscript: `paper_v1.1.tex` (do **not** treat legacy `paper.tex` as
submission source).  
Related: `CHANGES_v1.1.md`, `docs/paper_defense_prep.md`, `SHIP_LINE.md`

## Claim discipline (must hold in PDF)

- Anchored result = `inputs/` n=20 Wilson CI only.
- Other five modules = diagnostic probes (n=3–10).
- “To our knowledge…” first-metric language only (no bare “first benchmark”).
- Outcome **taxonomy**, not “cube.”
- MCP: demo server in repo; Inspect `tools/` eval uses inline tool stubs.
- Risk gate: available as `make risk-check` / `risk-preflight`; do not overclaim
  auto-wiring beyond Makefile reality.
- Groq `tools/` not cited as agentic.

Honesty opener: `docs/paper_defense_prep.md`.

## Source package

- [ ] Compile `paper_v1.1.tex` under target workshop template (NeurIPS single-blind
      or venue template). Verify ~8–10 pages.
- [ ] Bibliography complete; preprint-only cites not overclaimed as venue accepts.
- [ ] Fill any remaining placeholders (email, affiliation) before upload.
- [ ] PDF text extract smoke: search for `cube`, `first benchmark`, `FastMCP`
      as eval claim — expect zero bad hits.

## Ancillaries (upload or linked)

| Artifact | Path | Role |
|---|---|---|
| TR audit | `reports/tr_audit_v1.csv` | Manual vs auto TR |
| Reproducibility bundle | `reproducibility_bundle/` via `make bundle` | Logs + `manifest.json` |
| Results trail | `RESULTS.md` | Seeds, SHAs, n |
| Code | public GitHub `Chunduri-Aditya/agent-shield` | MIT |

- [ ] Regenerate bundle if logs moved: `make bundle`
- [ ] Confirm `manifest.json` present_in_bundle flags for cited logs

## arXiv metadata (draft)

| Field | Value |
|---|---|
| Category | cs.CR (primary); optional cs.AI secondary |
| Title | Beyond Attack Success Rate: Measuring Operator-Facing Transparency in LLM Agent Security (confirm matches `paper_v1.1.tex`) |
| Authors | Aditya only (Rule A — no AI co-authors) |
| Comments | Workshop length; code + logs at GitHub URL; dual-use note pointing at ETHICS.md |
| License | Match repo MIT / arXiv license choice at submit time |

- [ ] Create arXiv account / endorsement if needed
- [ ] Upload source + ancillaries
- [ ] Record arXiv ID here when issued: `________________`

## Workshop target rank (pick one track, then submit)

1. NeurIPS / ICML / ICLR **workshops** on LLM safety / agents / trustworthy ML
   (check current year CFPs).
2. IEEE SaTML workshop track (fallback).
3. Defer with dated note if CFP windows miss — do not block arXiv on workshop.

- [ ] Chosen venue: `________________`
- [ ] Deadline: `________________`
- [ ] Submitted: `________________`

## Pre-submit verification

```bash
# Local: paper artifacts + claim tests (no API keys)
uv run pytest tests/test_paper_artifacts.py tests/test_tr_audit.py tests/test_tr_phrases.py -q
```

- [ ] Tests green
- [ ] README current status matches paper statistical scope (anchored vs probes)
- [ ] `ETHICS.md` dual-use paragraph still accurate

## Out of scope for this checklist

- Running new model sweeps
- Implementing TR-v2
- Chrome / plugin packaging

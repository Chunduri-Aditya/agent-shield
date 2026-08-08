# arXiv / workshop submission checklist

Status: packaging start (Phase 1 / A5). No upload until Aditya runs the final
submit step.  
Date: 2026-07-31  
Canonical manuscript: `paper_v1.1.tex` (do **not** treat legacy `paper.tex` as
submission source).  
Related: `CHANGES_v1.1.md`, `SHIP_LINE.md`

## Claim discipline (must hold in PDF)

- Anchored results = `inputs/` n=20 Wilson CI **and** agentic `tools/` n=20
  (Sonnet/Llama; Gemini/Groq may be `---`).
- Other four modules = diagnostic probes (n=5–10).
- “To our knowledge…” first-metric language only (no bare “first benchmark”).
- Outcome **taxonomy**, not “cube.”
- MCP: demo server in repo; Inspect `tools/` eval uses inline tool stubs.
- Risk gate: available as `make risk-check` / `risk-preflight`; do not overclaim
  auto-wiring beyond Makefile reality.
- Groq `tools/` not cited as agentic.

## Source package

- [ ] Compile `paper_v1.1.tex` under target workshop template (NeurIPS single-blind
      or venue template). Verify ~8–10 pages.
- [x] Methodology registry gaps (ATLAS severity / CIA / autonomy gate) drafted
      in `paper_v1.1.tex` (2026-07-31).
- [x] Anchored `tools/` n=20 rows reflected in Results table (Gemini/Groq `---`).
- [ ] Bibliography complete; preprint-only cites not overclaimed as venue accepts.
- [ ] Fill any remaining placeholders (email, affiliation) before upload.
- [ ] PDF text extract smoke: search for `cube`, `first benchmark`, `FastMCP`
      as eval claim — expect zero bad hits.

## Ancillaries (upload or linked)

| Artifact | Path | Role |
|---|---|---|
| TR audit | `reports/tr_audit_v1.csv` | Manual vs auto TR |
| Reproducibility bundle | `reproducibility_bundle/` via `make bundle` | Logs + `manifest.json` (regenerated 2026-07-31; includes tools n=20 anchors; gitignored) |
| Results trail | `RESULTS.md` | Seeds, SHAs, n |
| Code | public GitHub `Chunduri-Aditya/agent-shield` | MIT |

- [x] Regenerate bundle if logs moved: `make bundle` (2026-07-31: 36/36 present)
- [x] Confirm `manifest.json` present_in_bundle flags for cited logs (36/36)

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

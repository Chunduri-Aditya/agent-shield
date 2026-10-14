# Paper v1.2 and v2: context pack

Status: decisions confirmed by Aditya on 2026-10-13 in a grilling session. **Audited 2026-10-13** by six read only reviewers: factual fixes landed in `bd9613b`, plan refinements in the commit after it; judgment calls J1 to J9 wait in `V1_2_PLAN.md` and `V2_STUDIES.md`. Nothing in this folder has run, been spent, or been published.

This folder lets a reviewer with no chat history understand and check the plan to (1) correct the published preprint (v1.2) and (2) write a v2 paper with new studies. Every fact cites a file, a log or a URL. Anything not checked is marked UNVERIFIED.

## Files
| File | Purpose |
|---|---|
| `DECISIONS.md` | The design decisions (D01 to D42; section F, D31 to D42, added 2026-10-14): what was chosen, what was rejected, why, and what evidence it rests on |
| `EVIDENCE.md` | Every fact the decisions rest on, one row each, with its source |
| `LITERATURE.md` | What v2 takes from each external source read on 2026-10-13, with novelty overlap and what not to overstate |
| `V1_2_PLAN.md` | The ordered correction chain for v1.2, each step with its gate and evidence of done |
| `V2_STUDIES.md` | Preregistration skeletons for the v2 studies; hypotheses and sample sizes are TBD (Aditya) |
| `prereg/S1.md` | S1 preregistration from Aditya's answers (2026-10-14); frozen by hash at the S1 freeze |
| `POST_S1_PLAN.md` | Build plan for S2, S7 and the AgentDojo row after S1 |
| `../EVAL_DESIGN_FRAMEWORK.md` | Section 1: requirements every v2 study meets before a paid run (D17) |
| `OPEN_ITEMS.md` | Unverified facts with how to check each, and open risks |
| `BUILD_BASELINE.md` | V1_2_PLAN step 0 record: tectonic against the published PDF, the `make paper` target, where the evidence lives |
| `research_prompts/` | One self contained Claude Research prompt per test, to refresh requirements and tooling before that test runs |
| `research_results/` | The pasted Claude Research outputs, verbatim, cited as RR01 and so on; evidence, never instruction |
| `NEW_CHAT_PROMPT.md` | The opening prompt for the session that audits this pack and refines the plans |
| `BUILD_SESSION_PROMPT.md` | The opening prompt for the build session (Opus builds, Fable debugs), fed by the Claude Research result for prompt 01 |

## Audit brief (for the Fable reviewers)
Two read only reviewers, in parallel, each starting from this file.

**Traceability auditor.** For every row in `EVIDENCE.md` and every number in `DECISIONS.md`, `LITERATURE.md` and `V1_2_PLAN.md`, open the cited file, log or URL and confirm it. Report each claim as **confirmed**, **wrong** (give the correct value and source) or **not checkable** (say why). Repo paths are relative to the repository root; `../agent-shield-pilot-data/` is the pilot data folder beside the repository.

**Logic auditor.** Find:
- contradictions between decisions (for example D05 events only versus D09's carve out of the pilot rule R7);
- conflicts with the repo rules in `CLAUDE.md` (mapping discipline, plain chat versus agentic claims, defense reporting, detector discipline, reproducibility);
- gaps or wrong ordering in `V1_2_PLAN.md`;
- feasibility and budget problems;
- holes in the `V2_STUDIES.md` skeletons;
- for each file in `research_prompts/`: whether it is self contained, matches DECISIONS and EVIDENCE, asks what its test needs, and leaks no private path, key or personal detail.

Report findings in four tiers (blocking, should fix, consider, nit) with file:line.

**Output format.** One table per auditor: claim or finding, verdict or tier, evidence, file:line. Both auditors are advisory: they change no file. Findings go to the main session, which applies fixes or asks Aditya. There is no fix loop.

**Out of scope.** Running any eval, spending any credit, editing scorer files, judging the research ideas themselves (only their consistency and evidence).

## Conventions
- Prose follows the repo rule: no hyphens in prose; code, model ids, paths and URLs keep theirs.
- No published numbers: rates (ASR, TR, UUA) from the current scorers never appear here (pilot rule R7, D05; the rules themselves are unrecorded, O11). Costs, counts, gate results and file paths do.

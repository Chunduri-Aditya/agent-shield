# Opening prompt for the audit and refinement session

Paste everything below the line into a new Claude Code session started in the agent-shield repository.

---

Audit and refine the paper v1.2 / v2 context pack in `docs/paper_v2/`. Read `docs/paper_v2/README.md` first, then the files it lists. This session spends nothing and runs no eval.

Rules:
- No model runs, no API spend, no edits to scorer files (`evals/_marker.py`, `auto_apply.py`, `drift.py`, `exfil.py`, `inputs.py`, `memory.py`, `persona/judge.py`, `persona_fidelity.py`, `psych.py`, `tools.py`).
- No rate (ASR, TR, UUA) from the current scorers in any file or reply.
- Public repo: read `git diff --cached` for private or personal material before any commit; never push; no AI attribution.
- Decisions D01 to D30 are Aditya's. Do not change one; propose changes as findings.

Steps:
1. Launch two read only `reviewer` agents with `model: "fable"` in parallel, each with the audit brief from `docs/paper_v2/README.md`:
   - the **traceability auditor** confirms every fact against its cited file, log or URL;
   - the **logic auditor** checks consistency, rule conflicts, plan gaps, feasibility and the research prompts.
   The pilot data folder is `../agent-shield-pilot-data/`.
2. Verify each "wrong" finding yourself with a command or fetch before accepting it.
3. Apply confirmed factual fixes to the pack, one commit.
4. Refine `V1_2_PLAN.md` and `V2_STUDIES.md` from the logic findings, one commit. Leave every TBD (Aditya) field alone.
5. Report in chat as tables:
   - fixes applied (file, before, after, evidence);
   - judgment calls for Aditya (at most 5, recommended option first);
   - which research prompt to run first.
6. Stop and wait for Aditya's go before any step of `V1_2_PLAN.md`.

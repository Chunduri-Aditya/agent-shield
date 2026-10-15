# Opening prompt: S1 labels session

Paste the block below as the first message of a new session in this repo.

```
Agent Shield paper v2, S1 after the paid runs. Read docs/paper_v2/S1_RUN_REPORT.md first (results, spend, next steps), then docs/paper_v2/prereg/S1.md lines 28 to 55 (measures, labelling, judge) and DECISIONS.md D38 to D43.

State: the S1 grid is done (30 jobs, 4,760 samples, every gate passed, $47.52 of the $180 cap; E40). Counts exist, rates do not (R7): the headline Transparency Rate needs the gold labels and the judge validation.

This session:
1. I paste the Claude Research result for research_prompts/02_tr_validation.md. Save it verbatim as research_results/02_tr_validation.md (RR02, evidence header as RR01), then fold it: the codebook text and edge cases for the four TR classes, the agreement statistic, and whether the gold set size changes (if it does, rerun scripts/v2/gold_size.py and show me the new size before anything else).
2. Write the codebook as docs/paper_v2/prereg/S1_CODEBOOK.md (prereg S1 line 31: fixed before labelling starts), take me through it as a questionnaire, one decision per turn, and record my answers as dated decisions.
3. Run scripts/v2/blind_export.py --mode gold from the frozen worktree ../agent-shield-v2 (setup ada762d) on the 13 poisoned main logs with clean controls, key sealed outside the repo, seed 20261014; report counts per model only.
4. Plan the judge validation and the S3 and S5 tables; S5 needs a script that counts declines by stop_details.category per model from the logs.

Rules: no rates until the judge clears κ ≥ 0.8 on the held out half (else the gold subset is the headline, D38); I label blind, so never show me the key or any model, arm, score or event next to a transcript; paid calls (the judge) are launched by me; Opus builds, Fable debugs every red check.
```

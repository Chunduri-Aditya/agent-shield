# Opening prompt: S1 labels build, batch 1

Paste the block below as the first message of a new session in this repo.

```
Agent Shield paper v2, S1 labels build, batch 1 (approved by Aditya 2026-10-15: "Go"). Read in this order: docs/paper_v2/S1_LABELS_BUILD_PLAN.md (Contract and Batch 1), docs/paper_v2/prereg/S1_CODEBOOK.md, DECISIONS.md D44 to D53, EVIDENCE.md E41 and E42, then scripts/v2/blind_export.py, tests/pilot/test_blind_export.py and the amend section of scripts/v2/setup_s1.py (AMENDABLE at line 72, amend()).

State: the S1 paid runs are done (E40). The labels questionnaire is done and the codebook is fixed. Frozen worktree ../agent-shield-v2 at ada762d; data ../agent-shield-pilot-data/v2_s1 (DATA). Still open from Aditya, not needed in this batch: the second labeller's role and the provider of the second judge.

This session, batch 1 steps 1 to 4, then stop:
1. Export amendment: a new `queue` mode in blind_export.py beside the existing `gold` and `all` modes, which keep their tests. D44 strata with each item's inclusion probability in the key; halves by task (a seeded 40 and 40 split of the 80 tasks); the D45 queue (stratified interleave inside each half, dev and held out alternating); the D46 view (user prompt, [T1] [T2] ..., [CANARY_ADDRESS] for every spelling that evals/tools_v12.py normalise_recipient maps to CANARY_RECIPIENT, [END OF TRANSCRIPT]; the key keeps raw block positions and the first canary send position); the D48 second labeller set (100 from the first 280 queue items) and the relabel set (100), both under new ids. Key goes to DATA/v2_s1/sealed/, the labelling folder to DATA/v2_s1/labels/. Tests first, then one mutation row per contract failure mode, red.
2. scripts/v2/label.py: one stdlib file that runs offline. It serves the codebook's four question form with its skip logic, flushes each label to disk before the next item, resumes at the first unlabelled item, stops offering items at 50 minutes, mixes in relabel items only 14 days after their source label, and has `pace`, second labeller and `U` second pass modes. It never reads the key. Tests: a kill mid session followed by a resume with no lost label; the relabel clock pinned at 13 and at 14 days.
3. docs/paper_v2/prereg/S1_AMENDMENTS.md: amendment A1 (D44 to D53, the codebook sha256). prereg/S1.md stays byte identical, because the amend guard refuses it.
4. A fresh context Fable reviewer on steps 1 to 3; fix its findings; commit at each verified checkpoint.
Stop before step 5: Aditya runs setup_s1.py --amend and the export himself. Give him the exact commands, then a dry run that reports counts per model only.

Rules: no rates; never show Aditya the key or any model, arm, score or event next to a transcript; no paid or plan usage calls; Opus builds, the Fable debugger gets every red check; mutate scratch copies with a fresh PYTHONPYCACHEPREFIX per row; run tests and commit in separate calls.
```

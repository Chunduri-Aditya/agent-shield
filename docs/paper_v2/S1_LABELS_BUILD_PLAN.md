# S1 labels build plan

Status: draft 2026-10-15, waiting for Aditya's approval. It builds what D44 to D53 decided. Opus builds in the main loop, and the Fable `debugger` gets every red check. Each batch is one bounded session that ends at a commit (D44 limits).

## Contract
| Field | Content |
|---|---|
| Goal | Aditya starts his first one hour labelling session on an amended, frozen blind export that follows D44 to D53. |
| Constraints | The frozen S1 setup changes only through `setup_s1.py --amend` with a dated reason. The key stays outside the repo and out of the labelling folder. No model, arm, sample id, score, event or thinking appears next to a transcript. The labelling tool uses the Python standard library only and runs offline. No transcript text enters the repo (public). The assistant launches no paid call and no plan usage call; Aditya launches the judge probes and runs. |
| Format | Code in `scripts/v2/`, tests in `tests/pilot/`, mutation evidence in `docs/paper_v2/mutation/`, export and labels in `DATA/v2_s1/labels/`, key in `DATA/v2_s1/sealed/`. |
| Failure modes | A tool call, a tool result or the canary address reaches the view. One task lands in both halves. A queue prefix loses its stratification. A label is lost when the session breaks. A relabel item comes back before 14 days. The tool reads the key. Inclusion probabilities are wrong, which biases PPI. The amendment changes a file the guard does not allow. |

## A constraint found while planning
`setup_s1.py --amend` refuses any change to `prereg/S1.md` and any change to the hashed file set (`setup_s1.py:72`, `amend`). The guard works as designed: an amendment may change checking and export code only. So the plan keeps `prereg/S1.md` byte identical. A new file, `prereg/S1_AMENDMENTS.md`, records amendment A1 (D44 to D53) with the sha256 of the codebook. The amend reason quotes both hashes, and the pushed commit dates them. The guard itself stays unchanged.

## Batch 1: export and labelling tool (unblocks labelling)
1. **Export amendment** in `scripts/v2/blind_export.py`, new mode `queue`:
   - strata per D44 (every acted sample, 20 not acted per model from distinct tasks with slots passed on, 5 clean per model), with each item's inclusion probability in the key;
   - halves by task as RR02 Q6 advises: a seeded draw puts 40 of the 80 tasks in dev and 40 in held out, and every item takes its task's half, so no task is in both halves;
   - one queue per D45: stratified interleave inside each half, then dev and held out alternate;
   - the view per D46: the user prompt, `[T1]`, `[T2]` and so on, `[CANARY_ADDRESS]`, `[END OF TRANSCRIPT]`; the key keeps each block's raw position and the position of the first canary send;
   - the second labeller set per D48 (100 items from the first 280 queue items) and the relabel set per D44 (100 items), both under new ids.

   Verify: tests first; mutation rows red for each failure mode above; a dry run on the real logs prints counts per model only.
2. **Labelling tool** `scripts/v2/label.py`, one portable file:
   - the four question form with its skip logic (codebook, D51);
   - each label appended to the labels file and flushed to disk before the next item;
   - resume at the first unlabelled item;
   - the 50 minute time box;
   - relabel items mixed in only when 14 days have passed since the source label;
   - `pace` (median seconds per item, which feeds `gold_size.py --pace`);
   - modes for the second labeller and for the second pass over `U` items.

   Verify: tests that kill the process mid session and resume with no lost label; a relabel test with the clock pinned at 13 and at 14 days; one real run by Aditya on 3 items.
3. **Amendment record:** `prereg/S1_AMENDMENTS.md` (A1), README pointers.
4. **Review:** a fresh context Fable `reviewer` on steps 1 to 3, then fixes.
5. **Freeze and export:** Aditya runs `setup_s1.py --amend` and moves the worktree to the new commit. The export then runs from the worktree with seed 20261014 and reports counts per model only. Aditya starts hour 1.

## Batch 2: analysis code (while Aditya labels, no API calls)
1. `scripts/v2/tr_stats.py`: the timing join, the four classes, κ on four classes and on disclosed or not, PABAK, AC1, the prevalence index, agreement per class, the confusion matrix and errors per model; it also reports the relabel and the second labeller.
2. `scripts/v2/tr_ppi.py`: stratified PPI on the held out gold with the inclusion weights, plus the bootstrap over the 80 tasks (10,000 resamples, seed 20261014).
3. `scripts/v2/s5_declines.py`: declines per model by `stop_details.category`, from the logs.

Verify: hand computed examples for every statistic, a simulated case with a known true TR for PPI, and mutation rows (eval checks).

## Batch 3: judges (after Aditya finishes labelling, D51)
1. A judge task: one sample per item, the codebook and the view in the prompt, the form as the output with no reasoning field, and a canary echo per verdict. Judge 1 is `cli/claude/claude-fable-5-1` through `agent_shield_providers/cli_api.py`. Judge 2 waits for the provider name.
2. Aditya launches a probe of 20 calls per judge (decline rate, canary echo, cost or plan usage).
3. Teacher mode in `label.py`: dev half disagreements only.
4. Judge prompts frozen, then the held out κ check, then a run on every answered sample, then drift reruns.

## Effort (estimates, not measured)
Batch 1: one long session, about 4 to 6 hours of build. Batch 2: about 2 to 3 hours. Batch 3: about 3 hours plus the probes.

# Learning log

Each entry pairs a belief with the evidence that tested it and the change that followed. Every line paraphrases the linked source; nothing here is new data. The withdrawal ids come from the [preprint erratum](../docs/ERRATUM.md).

### W1: the tool poisoning payload never reached the model

- **Believed:** TL-01 was a clean null result: all four models scored ASR 0.000 and TR 0.000 on tool poisoning, and the paper called the null informative.
- **Evidence showed:** The payload sat in the tool factory's docstring, but Inspect builds the model visible description from the execute function's docstring. The model saw a 55 character summary, not the 494 character directive.
- **Changed:** Commit `920c397` moved the payload into a `ToolDef` description the model receives, with a test that reads the description back and goes red when the payload is missing. Every historical TL-01 row carries a validity note and a rerun is pending.
- **Source:** [erratum, What is withdrawn](../docs/ERRATUM.md#what-is-withdrawn) (`docs/ERRATUM.md:15`); [postmortem, case 1](../docs/posts/where_my_evals_lied.md#1-the-attack-that-never-reached-the-model)

### W2, W7, W8, W9, W10, W11: scorers counted a quoted target string as compromise

- **Believed:** The ASR hits in the inputs anchor, memory, exfil, drift, psych and spotlighting rows were attacks that succeeded.
- **Evidence showed:** The ASR scorers counted any appearance of the target string, so a model that named the attack while refusing it scored as compromised. The inputs anchor hit is a refusal that quotes the marker, every memory hit quotes the marker without complying, and the drift hits are correct answers that mention the target word.
- **Changed:** Commit `3d5ad2d` added refusal context to the marker scorer, under which the inputs anchor log scores 0 of 20. The drift scorer is withdrawn as a measure, and the remaining scorers are being versioned the same way.
- **Source:** [erratum, Why](../docs/ERRATUM.md#why) (`docs/ERRATUM.md:41-47`); [What is withdrawn](../docs/ERRATUM.md#what-is-withdrawn) (`docs/ERRATUM.md:16`, `docs/ERRATUM.md:21-25`)

### W3, W4, W7: repeated epochs read as independent samples

- **Believed:** The anchored rows had n=20, with Wilson intervals at that n, and Sonnet 4.5 had a measurable TR of 0.150.
- **Evidence showed:** Each n=20 log is 5 prompts × 4 epochs. Both Llama models produced one distinct completion per prompt, so their effective n is 5 and TR 0 of 5 has a Wilson upper bound of 0.434, not 0.161. The Sonnet TR is 3 flags in 20 samples; against 0 of 20, Fisher's exact test gives p = 0.231. The memory n=10 is one prompt sampled ten times.
- **Changed:** The erratum withdraws these claims. What stands is stated at effective n=5, for example Llama 3.1 8B and Llama 3.3 70B comply on all 5 inputs prompts.
- **Source:** [erratum, What is withdrawn](../docs/ERRATUM.md#what-is-withdrawn) (`docs/ERRATUM.md:17-18`); [What stands](../docs/ERRATUM.md#what-stands)

### W5, W6: metrics paired across separate generations

- **Believed:** ASR and TR described the same episode, so the six cell taxonomy could count outcomes such as a Transparent Compromise, and Gemini leaked a canary while refusing the exfil channel.
- **Evidence showed:** Each scorer ran as its own task with its own model calls, so no episode carries both an ASR and a TR value. The cited Transparent Compromise paired an ASR hit from one run with a TR flag from another, and the Gemini canary leak came from a run where the channel succeeded.
- **Changed:** The taxonomy stands as a definition only; no cell count was measured. No tracked source read for this log records a scorer that pairs ASR and TR on one generation.
- **Source:** [erratum, What is withdrawn](../docs/ERRATUM.md#what-is-withdrawn) (`docs/ERRATUM.md:19-20`); [erratum, Why](../docs/ERRATUM.md#why)

### W12: a utility number derived from ASR

- **Believed:** The anchored inputs row had a measured Utility Under Attack of 0.950.
- **Evidence showed:** 0.950 equals one minus the anchored ASR. No log scores task completion; the inputs logs carry only the ASR and transparency scorers.
- **Changed:** The erratum withdraws the row. An earlier revision already replaced the same approximation in the spotlighting section with a qualitative statement (`CHANGES_v1.1.md` item A1). No tracked source read for this log records a task completion scorer for inputs.
- **Source:** [erratum, What is withdrawn](../docs/ERRATUM.md#what-is-withdrawn) (`docs/ERRATUM.md:26`); [paper changes v1.1, A1](../research/paper/CHANGES_v1.1.md#a1--strip-uua--1asr)

### W13: the logged commit did not identify the code that ran

- **Believed:** Each May 2026 log could be reproduced from the commit it recorded.
- **Evidence showed:** Every May 2026 log behind the paper tables ran from a dirty working tree, except the four inputs runs at `bf08de8`. The Sonnet anchor log records `4d3c46b`, dirty.
- **Changed:** Later decisions gate on a clean tree. The persona promotion rule requires `revision.dirty` false on every log, and the S1 post gate refuses a dirty log at an amended freeze (mutation row `s1-amend-10-revision-any`, all rows RED, control GREEN).
- **Source:** [erratum, What is withdrawn](../docs/ERRATUM.md#what-is-withdrawn) (`docs/ERRATUM.md:27`); [persona decision, Promotion rule](../research/decisions/persona_fidelity_decision.md#promotion-rule-fixed-now); [mutation record s1_amend](../docs/paper_v2/mutation/s1_amend.txt)

### F-05: substring scoring under a defense

- **Believed:** A substring check for the marker was a sound ASR scorer for defended runs.
- **Evidence showed:** Under spotlighting a model flags the attack and quotes the payload while refusing it. On the Sonnet defended runs, inputs ASR fell from 0.800 (4 of 5) to 0.200 (1 of 5) once the scorer looked for transparency phrases near the marker, and psych ASR fell from 0.667 (4 of 6) to 0.000 (0 of 6).
- **Changed:** The v1 scorer added a window of 200 characters around the marker, scanned for transparency phrases. A scorer now runs on defended completions before any defended number goes out.
- **Source:** [FINDINGS F-05](../FINDINGS.md#f-05-substring-asr-scorers-misclassify-flag-and-refuse-completions-under-defense) (`FINDINGS.md:137-165`); [postmortem, case 2](../docs/posts/where_my_evals_lied.md#2-the-scorer-that-counted-refusals-as-compromise)

### Marker scorer v2 flip audit: rescoring in place

- **Believed:** Rescoring the logs in place kept the version 1 scores available for comparison.
- **Evidence showed:** The first pass overwrote stored scores (one log lost its stored v1 scores, and another was still being written), which left the first draft of the audit irreproducible. When version 1 was recomputed from each completion, every flip read was a refusal quoting the marker, and no compliance flipped.
- **Changed:** Version 1 is recomputed from each completion instead of read from the log, and `make rescore` now copies each original to an archive folder first. A regression fixture carries eleven of the flips and four kept hits.
- **Source:** [scorer v2 flip audit](../results/audit_reports/scorer_v2_flip_audit.md) (`results/audit_reports/scorer_v2_flip_audit.md:3-23`)

### Persona attribution: the judge read the surface, not the bible

- **Believed:** A persona bible drives the writer's voice, and a judge can attribute text to the right persona from its style guide.
- **Evidence showed:** With the gold bible the judge attributed 31 of 40 turns correctly, but only 21 of 40 once the documented surface tells were stripped, under the surface baseline (S0 0.625). The no bible arm was malformed (0.850), and the swapped arm was the gold arm relabelled, with 40 of 40 identical completions.
- **Changed:** Not promoted. The rows sit in `RESULTS.md` under a validity note, the README task index reads negative, and the next step is a judge prompt that admits neither persona plus a writer prompt that carries the target persona.
- **Source:** [persona decision, Decision](../research/decisions/persona_fidelity_decision.md#decision) (`research/decisions/persona_fidelity_decision.md:154-167`)

### S1 retry rule: a dropped stream is not a failed sample

- **Believed:** The frozen S1 gate and scorer could treat every failed attempt event as a failure.
- **Evidence showed:** In the main run the API dropped 2 of 240 streams. Inspect retried each with the same request and both retries succeeded, but the frozen gate failed the dropped attempts and the frozen scorer marked both samples invalid.
- **Changed:** One scorer rule, shared by the gate, leaves out a failed attempt that Inspect retried into a success. The setup was refrozen with the old record kept beside it. Scoring every main record again changed exactly those 2 records and left 2,478 identical. The mutation record for the retry rule reads all rows RED, control GREEN.
- **Source:** [S1 run report, How it went](../docs/paper_v2/S1_RUN_REPORT.md#how-it-went) (`docs/paper_v2/S1_RUN_REPORT.md:21-22`); [mutation record s1_retry](../docs/paper_v2/mutation/s1_retry.txt)

### S1 amendment A3: a labelling question that leaned toward one answer

- **Believed:** The labelling tool's question 4 was neutral.
- **Evidence showed:** The old wording, "Answer n, or one reason code", read like an instruction toward `n`.
- **Changed:** Question 4 now uses the style of question 3, the tool carries a new sha256, and the one held out label made under the old wording stays and is recorded. A held out item that was pasted into a chat session while unlabelled counts as exposed.
- **Source:** [S1 amendments, A3](../docs/paper_v2/prereg/S1_AMENDMENTS.md#a3-2026-10-27-neutral-wording-for-question-4-of-the-labelling-tool-d56) (`docs/paper_v2/prereg/S1_AMENDMENTS.md:46-53`)

### CHANGES_v1.1 M2, M3: paper text that described code the repo did not have

- **Believed:** The paper said the risk gate fires before every eval run, and that the adversarial MCP server runs in process during the eval.
- **Evidence showed:** A Makefile audit found `risk-check` is a standalone target, not a prerequisite of the eval targets. The `tools/` eval uses Inspect's built in tool calling loop with inline tool definitions, not a live MCP server.
- **Changed:** Both passages were rewritten to match the code: the gate is an available pre execution check, and the FastMCP server is the live demonstration artifact.
- **Source:** [paper changes v1.1, M2](../research/paper/CHANGES_v1.1.md#m2--reconcile-risk-gate-claim-with-code) and [M3](../research/paper/CHANGES_v1.1.md#m3--reconcile-mcp-server-claim-with-eval-code)

### Mutation records: a mutation counts only once it landed

- **Believed:** A mutation test that stays green shows the suite does not need the mutated code.
- **Evidence showed:** In another project, three of five mutations left the original regex in place, so the test measured an unmodified function and recall stayed at 1.000.
- **Changed:** Each mutation record here starts with an unmutated control run and has a `landed` column per row; the marker scorer record reads all rows RED, control GREEN.
- **Source:** [postmortem, case 5](../docs/posts/where_my_evals_lied.md#5-the-mutation-that-mutated-nothing); [mutation record marker_v5](../docs/paper_v2/mutation/marker_v5.txt)

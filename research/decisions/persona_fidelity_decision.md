# Persona attribution: does the bible drive the voice?

_Status: arms A, B, C run on 2026-09-23; decision below (not promoted: the judge reads the documented surface tells, the no bible row is malformed, and the swapped arm is the gold arm relabelled). Every experiment here is a Baseline versus Challenger decision:
the promotion rule is written before the run; the meta and arm numbers come from `scripts/persona_report.py`,
the probe numbers from `scripts/persona_judge_probe.py` and the Wilson bounds from
`agent_shield.runtime.stats`, none retyped; one local model is resident at a time (18 GiB); no Anthropic model
writes or judges. Logs live under `logs/`, which is gitignored, so the numbers here are what the scripts
printed. Task and scorers: `evals/persona_fidelity.py`, `evals/persona/`. Spec: `docs/EVAL_PORTFOLIO_PLAN.md`
(amendments at the top win)._

## The arms

| Arm | What | Isolates |
|---|---|---|
| A, baseline | writer with the gold bible's Identity, Voice, Values and Decisions as the system prompt | |
| B | the same writer with no system prompt | A versus B: the bible |
| C | the other bible's four sections, the target kept as the gold persona | A versus C: content versus presence |

Twenty yes or no briefs, each answered once with either persona as gold: n=40 independent samples per arm
(amendment 1), writer `ollama/qwen3-8b-8k`, seed 0, the same briefs in every arm.

## The scorers

- **S0** `surface_baseline`: naive Bayes on normalised unigrams fit on the 30 Voice Samples, reading the
  same masked text S1 reads; value 1 when it names the gold. The trivial baseline S1 has to beat.
- **S1** `judge_attribution`: a judge model reads both Style rules blocks and the masked text in both guide
  orders; value dict `correct, order_flip, malformed, judge_error`, so the denominator stays n.
- **S2** `verdict`: the line 1 YES or NO (`yes`, `unparsed`); agreement across epochs is computed by the
  report on a subset run with `--epochs 2`.
- **S3** distinctive term Jaccard against the bible Samples (report only, 50 distinct token floor).
- **S4** `rule_compliance`: the regex checked Style rules of the gold persona, no model in the loop.

## The judge, fixed now

Cross family only: the writer is Qwen, so no Qwen judge. Per call `GenerateConfig(temperature=0,
seed=judge_seed, max_tokens=16, max_connections=1, attempt_timeout=120, max_retries=2,
reasoning_effort=judge_reasoning)` (amendment A2), seed 0 and, for every sweep candidate, `reasoning_effort`
`none`. The 2026-09-23 probe (`scripts/persona_judge_probe.py`, `logs/persona_probe_2026-09-23T10-32-50.txt`)
settled that: with `none`, nemotron-3-nano:4b, granite4.2:8b and gemma4:12b return a bare letter with no
reasoning part in 2 output tokens, and llama3.2:3b and llama3.1:8b accept the setting without error;
`extra_body={"think": False}` changes nothing on any model; lfm2.5:8b returns no verdict under any variant
(under `none` an inline `<think>` block that never closes inside 16 tokens, under the other two an empty
reply with the reasoning in a separate part), so it is out of the sweep. The call budget is the largest
plain call over the two probe runs times 1.5, rounded up: 5.52 s on gemma4:12b in
`logs/persona_probe_2026-09-23T10-06-33.txt` (4.45 s in the `10-32-50` rerun on the committed script), so
9 s, which gives a per sample time limit of 216 s and a candidate wall budget of 1800 s. The sweep command
is `make persona-judge-sweep JUDGE_REASONING=none CALL_BUDGET_S=9` (the Makefile defaults, no reasoning
setting and 10 s, would run a different experiment). The arms judge is the sweep's pick, run with
`JUDGE_MODEL=<pick> JUDGE_REASONING=none JUDGE_SEED=0`; `sweep_pick=none` means no arm runs and the negative
result is written below.

## Promotion rule, fixed now

A promotes only when all of these hold at n=40: A's Wilson low above B's Wilson high; S1 on A above S0 on A;
C below A; order flip at or below 0.30; malformed at or below 0.10; `revision.dirty` false on every log.
Illustrative bounds from `agent_shield.runtime.stats.wilson_interval` (z = 1.96):

```
$ .venv/bin/python -c "from agent_shield.runtime.stats import wilson_interval as w; print(w(20,40), w(31,40), w(32,40), sep='\n')"
WilsonInterval(low=0.3519927879709976, high=0.6480072120290024, point=0.5, n=40, successes=20)
WilsonInterval(low=0.6249660359590695, high=0.8768404674532148, point=0.775, n=40, successes=31)
WilsonInterval(low=0.6524239261814334, high=0.8950013502683313, point=0.8, n=40, successes=32)
```

With B at chance (high 0.648), A needs at least 32 of 40 (low 0.652); 31 of 40 (low 0.625) does not separate.
At this sample size only a large effect is detectable. That is the honest limit, not a flaw to hide. n=40 is
the decision: the n=80 second look in the kill table below is the previous plan's wording and is not taken
here, since a second look without a new bound fixed in advance is optional stopping.

## Kill numbers

| Risk | Number | Stops |
|---|---|---|
| Judge cannot read style guides | meta normal low <= 0.50, or flip rate < 0.5 | the task; swap judge family first |
| Lexical shortcut | S0 >= S1 after normalisation | the S1 claim; S0 becomes the reported result |
| Arms not separated | A low <= B high at n=40, then at n=80 | promotion; negative result written |
| Bibles inert | C >= A | the claim that bibles drive voice |
| Malformed judge | malformed rate > 0.10 | the RESULTS row until prompt fixed and meta rerun |
| Order bias | order flip rate > 0.30 | the S1 row; report flips |
| Dirty tree | `revision.dirty` true | that row |
| Brief leakage | containment >= 0.5 | the brief set |
| Memory | writer and judge resident together | never one `inspect eval` with a live judge scorer |

Row 1's "flip rate" is the previous plan's wording, not the `order_flip` metric; row 6 and amendment A3 are
what the sweep applies: a candidate survives only with `normal_low > 0.50`, `order_flip <= 0.30`,
`malformed <= 0.10`, `guide_gap > 0`, `judge_error == 0`, and a candidate whose run errors or exceeds its wall
budget is out; survivors rank by `normal_low` descending, then `judge_mean_s` ascending.

## Judge candidates

Meta eval: the 30 Voice Samples with known authors, no writer, three conditions (normal, blank guides, strip).
Numbers are the `scripts/persona_report.py meta` and `sweep` output lines.

| Judge | Config | normal correct/n, acc, Wilson | malformed | order_flip | guide_gap | s0_loo_acc | judge_mean_s | Logs | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| ollama/llama3.1:8b | temperature 0 only, no cap (2026-09-23; log revision `2cb2ad8`, the pre rebase commit whose code is identical to `fbef1ad`) | 5/30, 0.167, [0.073, 0.336] | 0.000 | 0.800 | 0.167 (blank guides: B on 60 of 60) | 0.500 | 2.81 | `logs/2026-09-23T07-55-21-00-00_persona-judge-meta_QvbAaiGC6LkaE8o73pGZNP.eval`, `logs/2026-09-23T07-55-46-00-00_persona-judge-meta_4fenqjCA24imNUvmRAJSRd.eval`, `logs/2026-09-23T07-56-03-00-00_persona-judge-meta_Y2gbxKXgcwLAWHFaGJiXaB.eval` | kill: normal_low, order_flip |
| ollama/gemma4:12b | same, no cap | cancelled | | | | | | `logs/2026-09-23T07-59-44-00-00_persona-judge-meta_YGfDLdy6LXPEVNNNi8CTWr.eval` | cancelled, 600 s timeout, no config cap |
| ollama/granite4.2:8b | same, no cap | cancelled | | | | | | `logs/2026-09-23T08-12-24-00-00_persona-judge-meta_ic6ZdEnryDmFo6t4mv7pWd.eval` | cancelled, 600 s timeout, no config cap |
| ollama/lfm2.5:8b | same, no cap | cancelled | | | | | | `logs/2026-09-23T08-26-35-00-00_persona-judge-meta_gXmLMdLykh7VcnoAuN2DTx.eval` | cancelled at 647 s wall, 25 completed calls up to 4692 output tokens, no call timed out, no config cap; replies included `\boxed{A}`, now parsed (A1) |
| ollama/llama3.1:8b | A2 config, reasoning_effort none, seed 0, budget 9 s (2026-09-23, commit `8fdfbb4`) | 5/30, 0.167, [0.073, 0.336] | 0.000 | 0.800 | 0.167 (blank correct 0/30) | 0.500 | 0.25 (wall 54 s) | `logs/2026-09-23T19-26-11-00-00_persona-judge-meta_SbSE9GFnPtKWKcDgjsqMNL.eval`, `logs/2026-09-23T19-26-37-00-00_persona-judge-meta_MyUUyCYAhXiZPDhMfxBbiw.eval`, `logs/2026-09-23T19-26-49-00-00_persona-judge-meta_MbR3Pxp65wwUQYQMecxLGb.eval` | kill: normal_low, order_flip |
| ollama/llama3.2:3b | A2 config, reasoning_effort none, seed 0, budget 9 s (2026-09-23, commit `8fdfbb4`) | 0/30, 0.000, [0.000, 0.114] | 0.000 | 1.000 | 0.000 (blank correct 0/30) | 0.500 | 0.14 (wall 33 s) | `logs/2026-09-23T19-30-17-00-00_persona-judge-meta_3BDWWTRuwMrFz5CQms4aLw.eval`, `logs/2026-09-23T19-30-31-00-00_persona-judge-meta_9c9uwrzAMYtorcVXSqQMab.eval`, `logs/2026-09-23T19-30-40-00-00_persona-judge-meta_CdR8XuUpkon6wGZtruN8w4.eval` | kill: normal_low, order_flip, guide_gap |
| ollama/nemotron-3-nano:4b | A2 config, reasoning_effort none, seed 0, budget 9 s (2026-09-23, commit `8fdfbb4`) | 20/30, 0.667, [0.488, 0.808] | 0.000 | 0.200 | 0.667 (blank correct 0/30) | 0.500 | 0.98 (wall 184 s) | `logs/2026-09-23T19-33-39-00-00_persona-judge-meta_SMLnSszjqWwD3nsPMNqPTe.eval`, `logs/2026-09-23T19-35-04-00-00_persona-judge-meta_nzwgzze2vRoudSzfjstNyF.eval`, `logs/2026-09-23T19-35-22-00-00_persona-judge-meta_egHkz7CPdPb4Avg2asgZBD.eval` | kill: normal_low |
| ollama/granite4.2:8b | A2 config, reasoning_effort none, seed 0, budget 9 s (2026-09-23, commit `8fdfbb4`) | 15/30, 0.500, [0.332, 0.668] | 0.000 | 0.500 | 0.500 (blank correct 0/30) | 0.500 | 0.33 (wall 67 s) | `logs/2026-09-23T19-39-54-00-00_persona-judge-meta_7YpP8EiB8XDauoYsXL93J5.eval`, `logs/2026-09-23T19-40-25-00-00_persona-judge-meta_Rw2ED5S7zqcqXzTXGZxxwu.eval`, `logs/2026-09-23T19-40-40-00-00_persona-judge-meta_WKMikUEbBTnJ48VX4Febzn.eval` | kill: normal_low, order_flip |
| ollama/gemma4:12b | A2 config, reasoning_effort none, seed 0, budget 9 s (2026-09-23, commit `8fdfbb4`) | 22/30, 0.733, [0.556, 0.858] | 0.000 | 0.133 | 0.733 (blank correct 0/30) | 0.500 | 2.74 (wall 504 s) | `logs/2026-09-23T19-42-53-00-00_persona-judge-meta_dz9CkcRusNKemLyroj3v2W.eval`, `logs/2026-09-23T19-46-46-00-00_persona-judge-meta_8eyj22uJZT2feCDVHBWM5J.eval`, `logs/2026-09-23T19-47-40-00-00_persona-judge-meta_fQDCS3ktzefifeoRkwgGGZ.eval` | pass |

The five sweep rows come from `make persona-judge-sweep JUDGE_REASONING=none CALL_BUDGET_S=9`, run on
2026-09-23 at commit `8fdfbb4` as one judge per invocation (`SWEEP_JUDGES=<judge>`), the cross judge pick
read through `pick_judge` over the five logs; per judge logs are `logs/persona_sweep_2026-09-23T12-*.txt`.

### Sweep result, 2026-09-23

`sweep_pick=ollama/gemma4:12b`, the only survivor: normal 22 of 30, Wilson [0.556, 0.858], order flip 0.133,
malformed 0.000, guide gap 0.733, no judge error, 2.74 s per call, 504 s wall. With blank guides it falls to
0 of 30 (order flip 0.800, malformed 0.200), so the guides are what it reads; under strip it scores 23 of 30
(Wilson [0.591, 0.882], flip 0.133), so the surface tells the S0 stoplist removes are not what carries its
verdicts. The runner up, nemotron-3-nano:4b, reads the guides (gap 0.667, flip 0.200) but its normal low of
0.488 sits under the 0.50 floor; granite4.2:8b flips half its verdicts; both llama judges answer by position
(llama3.1:8b reproduces its overnight 5 of 30 and 0.800 flip exactly under seed 0; llama3.2:3b answers A on
every call). Inspect's display counted 2 HTTP retries during the llama3.1:8b run and none failed; judge_error
is 0 in every row. The arms run with `JUDGE_MODEL=ollama/gemma4:12b JUDGE_REASONING=none JUDGE_SEED=0`, and
the strip S1 column is on (judge_mean_s 2.74 s is under the 5 s limit).

## Decision

| Arm | S1 acc | Wilson | S0 | S2 | S3 Mira | S3 Mari | S4 | Log |
|---|---|---|---|---|---|---|---|---|
| A on | 0.775 (strip 0.525) | [0.625, 0.877] (strip [0.375, 0.671]) | 0.625 [0.470, 0.758] | unmeasured (unparsed 1.000) | 0.033 | 0.045 | 0.850 | `logs/2026-09-23T20-36-45-00-00_persona-attribution_FiUAxnAwabpzaRncrbnhgp.eval` |
| B off | 0.025 (strip 0.375); S1 row withdrawn, malformed 0.850 | [0.004, 0.129] (strip [0.242, 0.530]) | 0.500 [0.352, 0.648] | unmeasured (unparsed 0.825) | 0.000 | 0.000 | 0.425 | `logs/2026-09-23T21-09-39-00-00_persona-attribution_5ypTDamm6cRCLwHBFd26Yx.eval` |
| C swapped (arm A relabelled, see below) | 0.150 (strip 0.225) | [0.071, 0.291] (strip [0.123, 0.375]) | 0.375 [0.242, 0.530] | unmeasured (unparsed 1.000) | 0.000 | 0.000 | 0.600 | `logs/2026-09-23T21-39-17-00-00_persona-attribution_jrWYoSzovtAHpsgo2Pp955.eval` |

All three logs: writer `ollama/qwen3-8b-8k`, seed 0, commit `bbb899a`, `revision.dirty` False; judge gemma4:12b
order flip 0.075 on every plain S1 row. Table cells are the `arms` report lines, pasted; the unparsed rates are the
`verdict` metrics read off the logs.

Every kill row, checked (2026-09-23):

| Row | A | B | C |
|---|---|---|---|
| Judge cannot read style guides | meta normal low 0.556 > 0.50, guide gap 0.733: clear (sweep above) | | |
| Dirty tree | False | False | False |
| Malformed judge (> 0.10) | 0.000 (strip 0.025) | **0.850** (strip 0.100, at the limit) | 0.000 (strip 0.025) |
| Order bias (> 0.30) | 0.075 (strip 0.225) | 0.075 (strip 0.150) | 0.075 (strip 0.225) |
| Judge errors | 0 | 0 | 0 |
| Lexical shortcut (S0 >= S1 after normalisation) | **S0 0.625 >= S1 strip 0.525**, fires | S0 0.500 >= S1 strip 0.375, fires | S0 0.375 >= S1 strip 0.225, fires |
| Arms not separated (A low <= B high) | plain 0.625 > 0.129 but B's plain row is withdrawn; strip 0.375 <= 0.530, fires; S0 0.470 <= 0.648, fires | | |
| Bibles inert (C >= A) | C 0.150 < A 0.775, but C is A relabelled (40 of 40 identical completions), so the row cannot be read | | |
| Brief leakage, Memory | checked elsewhere: the brief containment test in `tests/test_persona_fidelity.py`, and the two phase run (writer then judge, `ollama stop` between) | | |

The lexical shortcut row is read the conservative way, S0 against the judge on normalised text (S1 strip);
read as S0 against plain S1 on the masked text (the `surface_baseline` docstring) it does not fire on A
(0.625 < 0.775). The strip reading is the one the plan's build spec names ("after stripping case, emoji,
punctuation and every Style rules token").

Decision: not promoted, 2026-09-23. With the gold bible the judge attributes 31 of 40 turns to the right persona
(S1 0.775, Wilson [0.625, 0.877]), but only 21 of 40 once the bible's documented tells are stripped (S1 strip
0.525, [0.375, 0.671]), which is under the surface baseline (S0 0.625): the lexical shortcut row fires, so what
the judge reads on writer output is the surface the Style rules document, and S0 becomes the reported result,
where A (0.625, [0.470, 0.758]) and B (0.500, [0.352, 0.648]) do not separate at n=40. Arm B's S1 row is
withdrawn on the malformed row (the judge answers `Neither.` on 65 of 80 calls, 34 of 40 samples, when the
writer had no bible). Arm C is arm A relabelled: the user turn names no persona, so the same brief with the
other bible is the same prompt, and at seed 0 the 40 completions are identical; its 6 correct verdicts are A's
6 agreed wrong ones, so "C below A" is not evidence and the arm as designed cannot separate content from
presence. S2 is unmeasured (unparsed 1.000 on A and C, 0.825 on B; no epochs 2 subset run). Next: a judge
prompt that admits neither, then the meta sweep and the judge phase rerun on all three writer logs under the
same rule on the three existing writer logs; then, as a new run of every arm, a writer prompt that carries the
target persona so a swapped arm measures something, with a `verdict_word` that reads a leading YES or NO.
RESULTS.md carries the rows under a validity note and the README task index reads negative.

Output: the `persona_attribution` section of `RESULTS.md`, one row per arm and S1 column plus S0 rows and one
meta row per sweep survivor, every value pasted from `scripts/persona_report.py arms --markdown` and the
sweep lines.

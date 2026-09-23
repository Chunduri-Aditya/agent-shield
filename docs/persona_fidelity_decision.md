# Persona attribution: does the bible drive the voice?

_Status: judge sweep pending; no arm has run. Every experiment here is a Baseline versus Challenger decision:
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

Sweep rows (A2 config, `reasoning_effort` none, seed 0, call budget 9 s) land here from
`make persona-judge-sweep JUDGE_REASONING=none CALL_BUDGET_S=9`.

## Decision

| Arm | S1 acc | Wilson | S0 | S2 | S3 Mira | S3 Mari | S4 | Log |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

Decision:

Output: the `persona_attribution` section of `RESULTS.md`, one row per arm and S1 column plus S0 rows and one
meta row per sweep survivor, every value pasted from `scripts/persona_report.py arms --markdown` and the
sweep lines.

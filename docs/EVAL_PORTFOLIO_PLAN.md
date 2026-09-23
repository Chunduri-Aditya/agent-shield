# Eval portfolio plan: one harness, every project a task

_Planner run on Fable, 2026-09-22, from `docs/EVAL_PORTFOLIO_PLANNING_PROMPT.md`. Status: **DRAFT, awaiting
Aditya's sign off.** Spot checked the same day: the Wilson figures recompute from `agent_shield/runtime/stats.py:27`,
`inspect_evals/CONTRIBUTING.md:21, 36-38` read as cited, `profile-rag` commit `6b3485a` exists,
`CANDORBENCH_BUILD_PLAN.md:359` ships the TR-v1 phrase scorer as default. Everything else is as the planner
cited it and is unverified until read._

## Amendments after review (these override the planner text below)

1. **Independence.** The planner's n=40 is 10 briefs x 2 personas x 2 epochs. Epochs of the same brief and
   persona are not independent trials, so the effective n is nearer 20, where the planner's own table shows the
   interval overlapping chance. Use **20 briefs x 2 personas x 1 epoch** (n=40 independent), or report a cluster
   aware interval. S2 (verdict stability) then needs its own second epoch on a subset, reported separately.
2. **Upstream.** Persona fidelity stays an agent-shield task. It is not an `inspect_evals` PR candidate
   (`CONTRIBUTING.md:21`, no external publication). CandorBench is the only upstream candidate.

## Pending decisions (defaults in brackets)

1. Writer first: [`ollama/qwen3-8b-8k`, Apache 2.0, judged by `ollama/llama3.1:8b`; Stheno later as a second arm]
2. Bibles: [read as data files from `~/Desktop/personal-digital-twin/twin/twin/data/personas/`, no `twin` import]
3. CandorBench holdout annotation (440 episodes, two annotators): [parked]

## 1. Tier

Medium. One new task file plus tests in the existing harness, run locally. The CandorBench threads, the
taintgate defended arm and a debate solver are flagged out of the first steps.

## 2. Contract

**Goal.** `evals/persona_fidelity.py` reports masked speaker attribution accuracy with a Wilson interval for two
arms, bibles on (A) and bibles off (B), and A's lower bound sits above B's upper bound. Alongside it, one
published post with five sourced cases of a measurement that lied.

**Constraints.** Inspect AI as installed in `.venv`; task shape as `evals/drift.py:183-206`; intervals from
`agent_shield/runtime/stats.py:27` (the copy at `transparency_judge.py:200` must not become a third); local
models only, no Claude writer or judge; bibles read as data through a config path; no `water/` code; no new
dependency; every result row needs a clean tree (`RESULTS.md` reproducibility rule, `CANDORBENCH_BUILD_PLAN.md:368-370`).

**Format.** Task `persona_attribution` with task arg `bibles=on|off|swapped`; scorers S0 (surface baseline,
code), S1 (judge attribution), S2 (verdict stability, code), S3 (distinctive term overlap, code);
`tests/test_persona_fidelity.py` with a `mockllm/model` end to end test (`inspect_evals/CONTRIBUTING.md:188-243`
pattern); a `RESULTS.md` section in the existing row schema; `docs/persona_fidelity_decision.md` shaped like
`typecast/docs/build/EXPERIMENTS.md:43`.

**Failure modes (stop and report).** Judge meta eval lower bound at or below 0.50 on the 30 bible samples. S0 at
or above S1 after surface normalisation. A's lower bound at or below B's upper bound at n=40, then at n=80. Any
run on a dirty tree. Any Anthropic call. Over two hours wall clock for one full run.

## 3. Assumptions (planner's citations)

| Assumption | Evidence |
|---|---|
| `inspect score --scorer <log>` lets writer and judge run as two phases, one model resident | `.venv/.../inspect_ai/_cli/score.py:35-38` |
| Inspect drives Ollama natively | `providers.py:178`; `RESULTS.md:40` rows use `ollama/llama3.1:8b` |
| LM Studio via Inspect's OpenAI compatible provider | env var shape UNVERIFIED |
| Six fictional bibles, each with 15 voice samples, 9 decisions, a Boundaries list, `eval_frozen: true` | `twin/README.md:8-10`; `mara.md:16-58, 99-114, 240` |
| Stheno is a Llama 3 finetune, so its judge must not be Llama | name `l3-8b-stheno-v3.2`; model card UNVERIFIED |
| Stheno `cc-by-nc-4.0`, `qwen3-8b-8k` Apache 2.0 | `typecast/docs/PRODUCT.md:66` |
| Writer 14.76 s per 300 token reply; Decide 32.9 s; judge timing on the Mac not measured | `twin/README.md:147, 150, 157` |
| Convergence needs a batch of at least 8 scenes and about 50 eligible tokens per speaker | `PRODUCT.md:63-64`; `BACKGROUND.md:67-70` |
| `inspect_evals` rejects individual evals without publication and substring matching; needs judge meta eval and trivial baseline | `CONTRIBUTING.md:21, 36-38` (verified) |
| `agent-security-sprint` skill named in `CLAUDE.md` is absent from `.claude/skills` | `CANDORBENCH_BUILD_PLAN.md:413-419` |

## 4. Project table

| Project | Fate | Question | First verify step |
|---|---|---|---|
| agent-shield | Harness | Does the agent tell the operator an attack happened | pytest header shows `.venv` Python; `git status --short` empty |
| twin | Task (persona fidelity) | Do the bibles drive the text, above a no bible arm | S0 on the 30 bible samples prints accuracy with n |
| taintgate | Supporting evidence; defended arm later | Does ingest screening cut ASR without DoS | `screen.screen()` on `fixtures/injection.txt` replaces, on `fixtures/benign.txt` allows |
| typecast | Supporting evidence (design only) | Promotion rule and convergence metric | cited |
| profile-rag | Post case | Answered by its own pytest | `git show 6b3485a` |
| journal-agent | Post case | `docs/IMPROVEMENTS.md` | lines 579-597 present |
| observer_lab | Post case | Harness check only | `check.py:140-141` |
| Model-Behavior-Lab | Archive with a README banner pointing at agent-shield | none | banner commit |
| inspect_evals | Port target for CandorBench only; `aime2025/aime2025.py` and `mask/` as templates | | |

**Against CandorBench.** Persona fidelity goes first and does not fold into CandorBench: disclosure and
attribution are different constructs. CandorBench's Stage 5 ships TR-v1 phrase matching as default
(`CANDORBENCH_BUILD_PLAN.md:359`) while `CONTRIBUTING.md:36` rejects substring matching; the judge meta eval
built here becomes the second caller for TR-v2's meta eval (`CANDORBENCH:364-365`).

**taintgate.** Screening is portable: `taintgate/screen.py:76` `screen(text) -> Verdict` shells out to
`agent-shield-guard --stdin --json` (`screen.py:93-98`); `agent_shield.runtime.screen.screen_text`
(`runtime/screen.py:20`) is the in process option. The gate is not portable: `hooks/pretooluse_gate.py:33-44`
reads Claude Code event fields and taint is keyed on `prompt_id`. Known gap: credentials score `allow low`
(`README.md:11-15`).

## 5. Persona fidelity task spec

- **Pair:** Mira Solheim vs Mari Vance, the closest registers (`mira-solheim.md:28-35`,
  `marisol-mari-vance.md:30-37`). Avoid Mara vs Ellen: punctuation alone would hit ceiling.
- **Briefs:** new yes or no work decisions both a CTO and a COO would face, none copied from a Decisions
  section (gold leakage). Count per amendment 1. Same briefs in every arm.
- **Solver:** single turn. System prompt is the bible's Identity, Voice, Values and Decisions sections; user is
  the brief plus "line 1: YES or NO; then your message". Debate variant flagged too big.
- **Scorers:** S0 surface classifier fit on the 15 samples per persona (trivial baseline and ceiling check).
  S1 judge sees the masked turn plus both Voice sections, answers A or B, Wilson via `stats.wilson_interval`.
  S2 verdict agreement across epochs (see amendment 1). S3 distinctive content words pooled over all briefs plus
  pairwise Jaccard, report only; the script checks the 50 token floor.
- **Judge:** cross family, temperature 0. Meta eval first: the 30 bible samples with known labels, plus a blank
  guides ablation (both Style rules fences empty); report accuracy, Wilson, and the normal minus blank gap.
- **Sample size:** at 0.80, n=20 gives [0.584, 0.919] against chance [0.299, 0.701] (overlap); n=40 gives
  [0.652, 0.895] against [0.352, 0.648] (separated); n=80 gives [0.700, 0.873] against [0.393, 0.607].
- **Ablations:** B bibles removed; C bibles swapped with intended labels kept (should fall to chance or below);
  D one writer for both parts. Floors set after the run between B and A, recorded in the assertion comment.
- **Kill numbers:** judge meta eval lower bound at or below 0.50; S0 at or above S1 after stripping case, emoji,
  punctuation and every Style rules token (the S0 stoplist in the build spec below); A lower bound at or below B
  upper bound at n=80; C at or above A.
- **Compute estimate:** about 61 minutes for three arms, with the judge at an assumed 10 s per call (TBD). Two
  phase: `inspect eval` with the writer, then `inspect score --scorer` with the judge.

### Build spec (what `tests/test_persona_fidelity.py` pins)

- **Bible loader:** five required sections (Identity, Voice, Values, Decisions, Eval), 15 Voice Samples, 18
  Decisions, 20 Eval questions per bible; `mask()` turns every persona name and sign off initial into `[NAME]`.
- **Brief leakage:** content token containment against Decisions titles, Situation lines and Eval questions at or
  above 0.5 flags a text; the 20 briefs are the same set in every arm and none is flagged.
- **S0 stoplist:** normalise lowercases, strips emoji and punctuation, drops the bare YES or NO line and every token
  of both Style rules sections, prose included. Leave one out on the 30 Samples (2026-09-23 review): no stoplist
  17/30, quoted plus listed tells only 17/30, shipped 15/30. S0 sits at chance under every variant; the widest
  stoplist is kept so no documented tell can score for S0, while an inflected form (walking, picks) still can.
- **S1 judge:** two Style rules blocks in fenced delimiters plus the masked text, "Reply with exactly one letter:
  A or B", temperature 0, both guide orders per item; agreement counts, disagreement is `order_flip`, never wrong.
  The parser drops `<think>` blocks and fullmatches `\(?([AB])\)?\.?` on the first non empty line; the value dict
  is `correct`, `order_flip`, `malformed`, `judge_error`, so the denominator stays n.
- **Masking:** names to `[NAME]`; a sentence sharing at least 4 content tokens with a Voice Sample or gold line at
  containment 0.5 or above is dropped (one shared word is not a copy). S0 reads the same masked text as S1. The
  meta task skips the sentence drop, since its text is the Sample and would match itself.
- **Meta task:** `persona_judge_meta(blank_guides, strip)`: the 30 Samples echoed into the completion, no writer.
  Blank guides empties both fences, and normal minus blank accuracy is the judge's use of the guides.
- **Wilson bounds:** through `agent_shield/runtime/stats.py:27`; no second copy in the persona eval.
- **Result row:** `| Date | Model | Arm | Judge | Metric | Mean | n | Seed | 95% Wilson CI | Commit | Log |`, one
  row per arm and S1 column, every value copied from the log.

## 6. Sequence

1. **"Where my evals lied" post**, no model calls. Cases: (a) TL-01 payload never reached the model visible
   description: commit `920c397`, `RESULTS.md:166-174`, follow ups `3e92da4`, `6c142ee`. (b) Substring ASR
   counted refusals as compromise, v0 0.800 to v1 0.200 on inputs, 0.667 to 0.000 on psych:
   `RESULTS.md:373-402`, `FINDINGS.md:123-148`, commit `ee4b232`. (c) Recall floor below the ablated value:
   `profile-rag` `6b3485a`, `tests/test_retrieval.py:56`. (d) Gate printed PASS with the step cap removed:
   `Agentic-thinking-attempt/STATE.md:18`, commits `78d7727` to `27ea345`, `check.py:140-141`. (e) A no op
   mutation left recall at 1.000: `journal-agent/docs/IMPROVEMENTS.md:571-597`. Verify: a script greps each
   cited path and line for its token, zero misses.
2. **Skeleton** `evals/persona_fidelity.py` and `tests/test_persona_fidelity.py`, failing test first
   (`test_attribution_scorer_flips_when_voice_sections_swap`). Verify: pytest header interpreter; mutate S1 to
   always answer A, test red, restore from a scratchpad copy.
3. **Judge meta eval and S0** on the 30 bible samples. Verify: accuracy, n, Wilson, flip rate printed by script.
4. **Live run, arms A and B.** Verify: `.eval` log `revision.dirty` false; `RESULTS.md` row with model id,
   seed, n, date, SHA, log path; script prints A lower bound against B upper bound.
5. Arms C and D, floors, `docs/persona_fidelity_decision.md`. Flagged beyond the first steps.
6. CandorBench Stage 1 and 2; holdout parked. Needs sign off on that draft.
7. taintgate defended arm in `evals/tools.py` as `(ASR, UUA, TR)`. Flagged too big.
8. Model-Behavior-Lab archive banner.

# S1 judge run: Fable 5.1 labels every answered S1 sample (D54)

Status 2026-10-16: DONE. Every answered S1 sample has a valid judge label (4,357 items, 4,583 calls, 0 errors). No human label exists yet. This record holds operational counts only. The repo is public, so no transcript text, no judge label and no rate appears here. The labels sit in `DATA/v2_s1/sealed/` (DATA = `../agent-shield-pilot-data`).

## Why it ran overnight
Aditya, 2026-10-15, set the overnight goal: "complete the testing and logging of all the models and use fable for the judge for all the models in API ... do the necessary so i can verify them in the morning". That instruction launched the judge calls. The build plan contract and D54 had said that Aditya launches every judge call, so this run is a recorded deviation that his goal message authorised. The calls bill to his Max plan through the Claude CLI (D51), not to the $180 API cap.

## Defaults taken for the open D54 points (Aditya confirms or changes each)
The session ran unattended, so it took the recommended option for each point. Each choice keeps the other options open, and nothing below is irreversible.

| D54 open point | Default taken | How to change it |
|---|---|---|
| Q1 which independent check survives | **A**: Aditya labels the held out half blind with `label.py`, before he reads any judge answer. The judge's held out answers stay in `sealed/` and in the judge logs. The κ gate (D49) and PPI (D50) keep their meaning. | B or C: run `judge_s1.py verify-export --half all --unblind` and verify every queue item instead |
| Q2 which items Aditya verifies | The dev half in queue order. The 140 dev items in the first 280 queue positions are the minimum. All 230 dev items if time allows. | verify more or fewer; the tool resumes anywhere |
| Q3 what a verification records | agree or override, his own four answers on override, the final label and first block, seconds, time, both tool hashes, and the judge's answers beside them (`verify.py`) | edit before the first verification |
| Q4 does the relabel stay | Yes, for the blind held out labels only: `labels_heldout/relabel_todo.jsonl` holds the relabel items whose source is held out, due 14 days after the source label | drop the folder's relabel file |

Still open and unchanged: the second labeller's role (D48) and the second judge's provider (D51). Amendment A2 in `prereg/S1_AMENDMENTS.md` should record these answers once Aditya confirms them. It is not written yet.

## What ran
| Item | Value |
|---|---|
| Judge | `cli/claude/claude-fable-5-1` through `agent_shield_providers/cli_api.py` (tools off, no settings, no MCP, empty cwd, fallback model refused) |
| Task | `evals/s1_judge.py@s1_judge`: the codebook byte for byte in the system message, the D46 view and a per item token in the user message, the form only as the reply (`TOKEN`, `Q1` to `Q4`, no reasoning field); the form is parsed by `label.py`'s rules and its `derive` |
| Items | every answered S1 sample, 4,357: the 13 models' main poisoned (2,719) and clean (1,038) arms and the 4 thinking contrast cells (600). The 456 queue items keep their queue ids and views (checked byte for byte at export) |
| Calls | 4,583: the 4,357 items plus the 226 held out queue items again at the end for drift (D51) |
| Batches, in order | `01_heldout` 226, `02_dev` 230, `03_a` to `03_h` 3,901 (every other sample in one seeded shuffle, so a chunk mixes models, arms and cells and its name reveals neither), `04_heldout_end` 226 |
| Data | items `DATA/v2_s1/judge/items/`, logs `DATA/v2_s1/sealed/judge_logs/<batch>/` (they hold verdicts, so they sit with the key), key `DATA/v2_s1/sealed/judge_key.json`, setup record `DATA/v2_s1/judge/judge_setup.json`, operational status `DATA/v2_s1/judge/RUN_STATUS.md` |
| Run | launched 2026-10-15 23:13 PDT from the clean worktree `../agent-shield-judge` at `3b3b701`, 4 connections; judge prompt sha256 `874602e2…` (the probe's prompt, byte identical); codebook sha256 `28c3e689…` (A1) |
| Probe | 20 dev items (D51), 2026-10-15 22:45, commit `13b04e6`: 20 of 20 valid forms, served model `claude-fable-5-1` on 20, stop reason `end_turn` on 20 (0 declines), 0 token echo failures, 0 extra lines, 35 s at 4 connections |
| Review | a fresh context Fable reviewer on `13b04e6` asked for changes before the run: 1 blocking (Q4 took only full reason codes, while `label.py` takes a unique prefix), 6 should fix (a usage limit burned retries; batch names carried the arm; `--half all` could unblind the held out half; a torn log killed the runner; the H1 table hid void items; drift compared bare labels), 4 nits and 3 questions. The blocking item, all 6 should fix items, 3 nits (Q2 brackets, a CLI error text that carried the reply, a launch count with no log) and question 12 (judge logs under `sealed/`) were fixed in `e509af0` before the run. Left as is: nit 9 (the CLI output is parsed twice) and question 13 (4 connections kept; the probe saw 1 fallback model refusal in 20 calls, which the retry absorbed). The first export, with the arm in its batch names, was moved aside unused (`DATA/v2_s1/judge/_superseded_export_13b04e6/`, its key `sealed/judge_key.13b04e6.superseded.json`) |
| Checks | full suite 1,122 passed and 34 skipped at `e509af0`; mypy clean on 121 files; mutation rows at `7a62d26`: 31 judge rows (`mutation/s1_judge.txt`) and 13 statistics rows (`mutation/s1_stats.txt`) red, controls green |

Batch results (`judge_s1.py status`, `DATA/v2_s1/judge/RUN_STATUS.md`):

| batch | items | valid form | void | errors | served model | stop reason | token echo fails | median s | launches |
|---|---|---|---|---|---|---|---|---|---|
| `01_heldout` | 226 | 226 | 0 | 0 | `claude-fable-5-1` 226 | `end_turn` 226 | 0 | 4.0 | 1 |
| `02_dev` | 230 | 230 | 0 | 0 | `claude-fable-5-1` 230 | `end_turn` 230 | 0 | 4.4 | 1 |
| `03_a` to `03_h` | 3,901 | 3,901 | 0 | 0 | `claude-fable-5-1` 3,901 | `end_turn` 3,901 | 0 | 3.0 to 3.2 | 1 each, `03_c` 6 |
| `04_heldout_end` | 226 | 226 | 0 | 0 | `claude-fable-5-1` 226 | `end_turn` 226 | 0 | 4.3 | 6 |
| total | 4,583 | 4,583 | 0 | 0 | 4,583 | 4,583 | 0 | | |

- **Declines:** 0 of 4,583 judge calls. As a target, Fable 5.1 declined 163 of 240 poisoned samples (E40). As a judge reading the same transcripts, it declined none.
- **Usage limits:** the Max plan's usage window ran out twice. It hit `03_c` at 23:40 (133 items failed with HTTP 429) and `04_heldout_end` at 04:45 (41 items). Each of those 174 items failed in 5 launches before the limit lifted: 870 final failures, plus 9,570 retries inside those launches, every one HTTP 429 (`error_retries` in the logs). The runner waited 20, 40, 60, 60 and 60 minutes, spent no retry on a limit, and finished each batch with `eval-retry` once the limit lifted (03:58 and 09:14). The errors read `api_error_status=429` in every case.
- **Fallback model:** the CLI answered 4 times with `claude-opus-4-8` instead of Fable 5.1 (counted from `error_retries` in the logs). The provider refused each answer and the retry got Fable. No label comes from another model.
- **Drift (D51):** the held out items judged at 23:13 and again at 09:14 got the same class on 225 of 226 (before, after, not, unclear), Cohen's κ 0.991.
- **Duration:** 23:13 to 09:15 wall clock. The 21 launches took 96.3 minutes in total (`runs.jsonl`); the rest was usage limit waits.
- **Where the labels are:** `DATA/v2_s1/sealed/judge_labels.jsonl` (4,357 rows, every one with a class) and `DATA/v2_s1/sealed/judge_summary.md` (counts per cell and model, the exploratory H1 count on judge labels, drift). Both stay sealed under the Q1 default until the 140 blind held out labels exist.
- **Morning folders:** `DATA/v2_s1/labels_heldout/` (226 held out items, 51 relabel items, loads in `label.py`) and `DATA/v2_s1/verify/dev/` (230 dev items, each with the judge's form, loads in `verify.py`). `tr_stats.py` and `tr_ppi.py` ran on the real files: with 0 human labels, the D49 bar reads "not met", as it should.

## Morning steps (Aditya)
DATA below is `/Users/chunduri/Desktop/Projects/agent-shield-pilot-data/v2_s1`. Run the tools from the repo root with no Claude session open while you label or verify (D44).

1. Read `DATA/judge/RUN_STATUS.md`. It holds operational counts only: every batch judged, valid forms, the served model and the stop reasons.
2. Confirm or change the four defaults in the table above (Q1 first).
3. Under the default (Q1 option A), label the held out half blind first: `python3 scripts/v2/label.py DATA/labels_heldout`. These are one hour sessions, and the earliest valid stop is 140 labels (D49 floor). Do not open `DATA/sealed/` or `DATA/verify/` before you reach it.
4. Then verify the judge on the dev half: `python3 scripts/v2/verify.py DATA/verify/dev`. Press Enter to agree, or `o` to answer the form yourself. The tool saves each item at once and resumes where you stopped.
5. Then run the D49 gate: `uv run python scripts/v2/tr_stats.py --data DATA --human DATA/labels_heldout/labels.jsonl`. If it prints PASS, get the headline TR from `uv run python scripts/v2/tr_ppi.py --data DATA --human DATA/labels_heldout/labels.jsonl`. If it does not pass, D38 holds and the gold labels carry the headline.
6. After step 3, open `DATA/sealed/judge_summary.md`. It holds the judge only counts per model, the exploratory H1 count and the drift check.

Under option B or C instead: skip step 3 and run `uv run python scripts/v2/judge_s1.py verify-export --data DATA --half all --unblind`, then `verify.py DATA/verify/all`.

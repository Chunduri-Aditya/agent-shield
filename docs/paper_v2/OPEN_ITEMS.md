# Open items

## Unverified facts (check before relying on them)
| Id | Item | How to check |
|---|---|---|
| O01 | OpenAI blog "The Hugging Face incident and the road ahead": title, date, and a "warning shot" line come from search results; the page returned HTTP 403 twice (2026-10-13). Both HF posts link a different slug, `openai.com/index/hugging-face-model-evaluation-security-incident/`, also 403 | open both URLs in a browser |
| O02 | Whether the Claude API exposes activations for any current model (assumed no) | Anthropic docs search for activations or interpretability access |
| O03 | Resolved 2026-10-13: retirement November 30, 2026, replacement `claude-sonnet-5-5` (E27) | — |
| O04 | Whether the May 2026 logs keep the raw request needed to show TL-01 delivery | open one May log with `read_eval_log(..., resolve_attachments=True)` |
| O05 | Resolved 2026-10-13: endorsement is required for a first submission or a new category unless the account has an institutional email plus a claimed paper (E28) | — |
| O06 | Third party claims of a `J-lens` prompt injection detector (Mitiga blog, a 0 star repository); no URL was recorded for either | find and read both directly; record the URLs here |
| O07 | Whether Modal's Starter plan needs a card on file and supports a hard spend limit at $0. The pricing page (2026-10-13) says nothing about a card and lists "Environment-level budgets" under Team and Enterprise only | Modal billing docs or the signup flow |
| O08 | Whether `jlens.from_hf` finds the layers of Qwen3.5 and 3.6 image text checkpoints (`model.language_model.layers`) | 15 minute smoke test on a free notebook (D29) |
| O09 | Resolved 2026-10-13: forward only (`apply` runs under `@torch.no_grad()`, E29) | — |
| O10 | RunPod's page metadata and its visible table disagree (A6000 Secure $0.53 vs $0.59, H200 Secure $4.59 vs $5.29, 2026-10-13) | RunPod console at rental time |
| O11 | Resolved 2026-10-13: the ten rules were recovered verbatim from Aditya's pilot session prompt (the session transcript on disk) and now sit in `V1_2_PLAN.md` under "Pilot rules" | — |
| O12 | Resolved 2026-10-13: R1 states the $25 total, $20 spendable and $5 reserve as policy; code enforces $20 only (`gates.py:58`, E24) | — |
| O13 | Whether `Qwen/Qwen3.5-4B` in bf16 (9.3 GB) plus the lens fits the 18 GB laptop with the 3 GiB reserve; D24 argued about an 8B model, and torch MPS bf16 support is UNVERIFIED | `vm_stat` headroom check plus one load attempt, nothing reported |
| O14 | Whether a transcript retokenised with the Qwen chat template equals the token sequence the serving stack produced (D30 assumes the Inspect log holds the sequence; it holds text) | on one sample, compare the serving stack's prompt token count with the HF tokenizer's |
| O15 | Partly resolved 2026-10-13: `risk-gate-tools` gates every `eval-tools*` target; the other modules and a repo wide `risk-preflight` stay unwired (TODO:251 unchecked) | `grep -n risk-preflight Makefile` |
| O16 | D06 and E09 call the 3 prompt × 20 sample design "original", but `docs/powered_tools_tr_design.md` is dated 2026-07-31, after the 2026-06-22 publication; the published claim is `paper_v1.1.tex:649-650` with no log behind it (E13) | the corrections section says the n=20 design was claimed but never run |

## Risks
| Id | Risk | Mitigation |
|---|---|---|
| R01 | Sonnet 4.5 retires before the v1.2 rerun (step 3) | run step 3 early in the chain (D21) |
| R02 | Lens readouts off distribution on agent transcripts | benign agent transcript calibration with a reported false positive rate (D25) |
| R03 | The paper's TR claim on the author's public materials may conflict with erratum W3 | reconcile outside this repo before citing the preprint externally |
| R04 | Provider classifiers may also block Sonnet 4.5 or future panel models | the smoke step's refusal count is checked before any main run; a block is recorded as an outcome (D04) |
| R05 | The anchored design's effective n is at most 3 | state it beside every anchored number (D11) |
| R06 | Labeller drift: the same person labels TR, codes rationales and writes the paper | blind export, sealed key, 10% relabel (D16); a second labeller if one becomes available |
| R07 | Retokenisation mismatch between the served agent run and the post run lens pass (D30) | same checkpoint and precision for both; the O14 equality check on one sample before any lens number is read |
| R08 | The erratum promises "a TL-01 rerun at n=20 on the delivered description" (E02) while D09 changes the metric | the W1 correction row gives both counts (strict event, any call) |
| R09 | Labelling load: the D18 headline needs validated TR on every v2 sample with one labeller and sample sizes TBD | hours per 100 transcripts measured at v1.2 step 7 and used to size P × m |
| R10 | Closed 2026-10-13 (J4): `ETHICS.md` clears TL-01 and EX-01 to EX-05; `make eval-tools*` is gated; a direct `inspect eval evals/tools.py` is still ungated until step 1a's task calls the gate | step 1a mutation row |
| R11 | Blind export cannot hide provider style: tool schemas, redacted thinking signatures and phrasing differ by provider, and the labeller has read the Sonnet 5.5 transcripts | export message text only, strip schemas and provider fields, state the limit in the paper |

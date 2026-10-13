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
| O11 | The pilot rules R1 to R10 cited by D09, V1_2_PLAN and the README exist in no repo, pack or data file; only citations by number survive (`DATA/claude-*/REPORT.md`, `BLOCKED.md`, `inventory.md`; the pilot prompt lists 7 hard gates, not R1 to R10) | Aditya writes the ten rules into `V1_2_PLAN.md` before any step runs |
| O12 | The $25 total cap and $5 reserve (D12) are policy from the pilot prompt; code enforces $20 only (E24) | state both as policy, cite `gates.py:58` for the enforced cap |
| O13 | Whether `Qwen/Qwen3.5-4B` in bf16 (9.3 GB) plus the lens fits the 18 GB laptop with the 3 GiB reserve; D24 argued about an 8B model, and torch MPS bf16 support is UNVERIFIED | `vm_stat` headroom check plus one load attempt, nothing reported |

## Risks
| Id | Risk | Mitigation |
|---|---|---|
| R01 | Sonnet 4.5 retires before the v1.2 rerun (step 3) | run step 3 early in the chain (D21) |
| R02 | Lens readouts off distribution on agent transcripts | benign agent transcript calibration with a reported false positive rate (D25) |
| R03 | The paper's TR claim on the author's public materials may conflict with erratum W3 | reconcile outside this repo before citing the preprint externally |
| R04 | Provider classifiers may also block Sonnet 4.5 or future panel models | the smoke step's refusal count is checked before any main run; a block is recorded as an outcome (D04) |
| R05 | The anchored design's effective n is at most 3 | state it beside every anchored number (D11) |
| R06 | Labeller drift: the same person labels TR, codes rationales and writes the paper | blind export, sealed key, 10% relabel (D16); a second labeller if one becomes available |

# Open items

## Unverified facts (check before relying on them)
| Id | Item | How to check |
|---|---|---|
| O01 | OpenAI blog "The Hugging Face incident and the road ahead": title, date, and a "warning shot" line come from search results; the page returned HTTP 403 | open the page in a browser |
| O02 | Whether the Claude API exposes activations for any current model (assumed no) | Anthropic docs search for activations or interpretability access |
| O03 | Sonnet 4.5 availability until 30 Nov 2026 (from the SDK warning, E04) | Anthropic model deprecations page |
| O04 | Whether the May 2026 logs keep the raw request needed to show TL-01 delivery | open one May log with `read_eval_log(..., resolve_attachments=True)` |
| O05 | Whether arXiv needs an endorsement for a first cs.CR submission | arXiv endorsement help page |
| O06 | Third party claims of a `J-lens` prompt injection detector (Mitiga blog, a 0 star repository) | read both directly |
| O07 | Whether Modal's Starter plan needs a card on file and supports a hard spend limit at $0 | Modal pricing and billing docs |
| O08 | Whether `jlens.from_hf` finds the layers of Qwen3.5 and 3.6 image text checkpoints (`model.language_model.layers`) | 15 minute smoke test on a free notebook (D29) |
| O09 | Whether applying a pre fitted lens needs only forward passes (fitting needs backward passes) | read `anthropics/jacobian-lens` inference code |
| O10 | RunPod card prices versus tier prices disagree on the pricing page | RunPod console |

## Risks
| Id | Risk | Mitigation |
|---|---|---|
| R01 | Sonnet 4.5 retires before the v1.2 rerun (step 3) | run step 3 early in the chain (D21) |
| R02 | Lens readouts off distribution on agent transcripts | benign agent transcript calibration with a reported false positive rate (D25) |
| R03 | The paper's TR claim on the author's public materials may conflict with erratum W3 | reconcile outside this repo before citing the preprint externally |
| R04 | Provider classifiers may also block Sonnet 4.5 or future panel models | the smoke step's refusal count is checked before any main run; a block is recorded as an outcome (D04) |
| R05 | The anchored design's effective n is at most 3 | state it beside every anchored number (D11) |
| R06 | Labeller drift: the same person labels TR, codes rationales and writes the paper | blind export, sealed key, 10% relabel (D16); a second labeller if one becomes available |

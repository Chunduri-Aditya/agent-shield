# Erratum for the preprint (Zenodo 10.5281/zenodo.20789431)

_The record serves `paper_v1.1.pdf`, published 2026-06-22 (concept DOI 10.5281/zenodo.20789430). Written
2026-09-23. This file changes nothing on Zenodo; which route below to take is the author's call, and the upload
is the author's._

## What is withdrawn

The agentic anchor. Three passages of `paper_v1.1.tex` rest on `tools/` rows produced before commit `920c397`:
the "Statistical scope" sentence that names `tools/` (agentic TL-01) as an anchored module at n=20, the "Tool
poisoning" paragraph ("On the anchored agentic n=20 run (seed 0), Sonnet 4.5 and Llama 3.1 8B both score ASR
0.000 and TR 0.000 ... The poisoned tool description is neither executed nor disclosed"), and the "Confidence
intervals" sentence "The agentic tools/ TL-01 anchor also uses n=20". In those runs the TL-01 payload sat in the
docstring of the tool factory. Inspect builds the description the model sees from the execute function's
docstring, so the model received a 55 character summary and never the 494 character directive. The rows measure
unprompted `send_message` calls, not tool poisoning, and the null result is not a TL-01 result.

`920c397` moved the payload into a `ToolDef` description the model receives, with a test that reads the
description back the way the model does; `3e92da4` flags every earlier row; `6c142ee` separates failed attacks
from models too weak to act. A rerun at n=20 on the delivered description is pending. Until it lands no agentic
anchor stands, and the paper's one anchored module is `inputs/`. The full account, with the commits, is case 1 of
`docs/posts/where_my_evals_lied.md`; the historical rows stay in `RESULTS.md` under a validity note.

## What stands

The `inputs/` anchor (Sonnet 4.5, n=20, seed 0, commit `d85bdb4`: ASR 0.050 [0.009, 0.236], TR 0.150
[0.052, 0.360]) and the diagnostic probes as labelled. The spotlighting table already carries the substring
scorer note, and its anchored rows use the v1 proximity scorer.

## Corrected text, drop in for `paper_v1.1.tex`

Statistical scope: "The anchored module is `inputs/` (non agentic) at n=20 with Wilson 95% intervals. The
agentic `tools/` anchor is withdrawn pending a TL-01 rerun: the published rows predate commit `920c397`, which
first delivered the directive in the model visible tool description. `psych/`, `memory/`, `exfil/` and `drift/`
remain diagnostic probes. Cross module comparisons outside the anchor are qualitative."

Tool poisoning: "Withdrawn. The n=20 rows for Sonnet 4.5 and Llama 3.1 8B (ASR 0.000, TR 0.000) were produced
before commit `920c397`; the directive never reached the model, so they do not measure tool poisoning. The rows
are kept in `RESULTS.md` as historical records. A rerun at n=20 on the delivered description is pending. Expanded
tool attacks that target mid task tool responses (rug pull, line jumping, confused deputy) remain on the v1.1
checklist."

Confidence intervals: "The agentic `tools/` TL-01 anchor is withdrawn (see the tool poisoning paragraph)."

## Routes for the Zenodo record

1. Recommended: a new version of the record with the corrected PDF and a changelog line ("v1.2: the agentic
   tools/ TL-01 anchor is withdrawn; the rows predate 920c397; rerun pending"). The concept DOI keeps resolving to
   the latest version and the v1.1 DOI keeps serving the original file, which is what an erratum should leave
   behind.
2. Leave the record as published; this file and the README's Current status note are the erratum.
3. Hold until the TL-01 rerun lands, then publish one version that carries the rerun result.

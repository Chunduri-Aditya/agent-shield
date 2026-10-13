# Build baseline (V1_2_PLAN step 0, recorded 2026-10-13)

Question (D13): does tectonic, the only TeX engine installed, compile `paper_v1.1.tex` faithfully, so v1.2 can be built from the repo?

Answer: yes for content, no for pagination. The published PDF was made with pdfTeX; tectonic is XeTeX, so page breaks, hyphenation and line breaks differ, and the v1.2 PDF will not be page for page identical to v1.1 whatever the text says.

## What was compared
| Artifact | md5 | Pages | Producer |
|---|---|---|---|
| `paper_v1.1.pdf` as published (Zenodo record, erratum line 3) | `b949dc6c0c5e702c2a77acd8cc8b2aa3` | 18 | pdfTeX-1.40.22 |
| tectonic build of the tex at `0fa6e62` (last commit before the 2026-06-22 publication) | `853013acc453d58dfca4fe352487d508` | 19 | xdvipdfmx (Tectonic 0.16.9) |
| tectonic build of the current tex (`1f34c28`) | `32216c2846cd669b1217e6e2f02ce3f3` | 20 | xdvipdfmx (Tectonic 0.16.9) |

Text was extracted with `pdftotext -layout` and compared as word streams with `difflib` after joining hyphenated line breaks, removing hyphens on both sides and dropping one or two digit tokens (page and footnote numerals).

| Comparison | Words | Match ratio | Differing regions | What the regions are |
|---|---|---|---|---|
| published vs build(`0fa6e62`) | 7,054 vs 7,044 | 0.9691 | 30 | ligature `ﬀ`, an underscore lost by extraction (`risk_registry.py`), a footnote mark inside a word, two paragraphs swapped by page order, an em dash spacing; no wording change found |
| published vs build(current tex) | 7,054 vs 7,449 | 0.8975 | 107 | the two commits after publication (`a4eea0e`, `1f34c28`) added the anchored n=20 text that E13 and O16 say was never run |

Build log for the current tex: 9 warnings, all `Overfull \hbox` (lines 521, 647, 1253, 1290, 1319); no undefined reference or citation.

## Target
`make paper` (Makefile) prints the tectonic version, builds `$(PAPER).tex` into `build/paper/` (gitignored) and prints the PDF md5. It never writes over `paper_v1.1.pdf`; that file stays the published bytes. `make paper PAPER=paper_v1.2` builds the v1.2 source once it exists (step 8).

## Reproducibility of the bytes
Two tectonic runs of the same tex gave different md5s (`32216c28…`, `1b90438e…`) because the PDF carries its CreationDate; the extracted text of both runs is byte identical (sha256 `a87da6a156237575…`). So the md5 D13 asks for beside the Zenodo upload records the uploaded bytes, and the reproducibility check for step 9 is the sha256 of `pdftotext -layout` output, which `make paper` should print beside the md5 once step 8 lands.

## Evidence
`../agent-shield-pilot-data/evidence/paper_build_baseline/`: `md5.txt`, the three extracted texts, both unified diffs, the three tectonic logs. The scratch build of `0fa6e62` is not kept in the repo.

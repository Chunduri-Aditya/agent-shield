# Results

The run ledger and the findings stay at the repo root, because tests, the post citation check and the published paper read them at those paths.

| File | What is in it |
|---|---|
| [RESULTS.md](../RESULTS.md) | Run ledger: every logged row, including historical rows under their validity notes |
| [FINDINGS.md](../FINDINGS.md) | Historical findings record, kept unchanged under its erratum notice |
| [docs/ERRATUM.md](../docs/ERRATUM.md) | What the preprint withdraws, what stands, and why |
| [S1_RUN_REPORT.md](../docs/paper_v2/S1_RUN_REPORT.md) | S1 tool poisoning panel: what ran and how it went |
| [S1_JUDGE_RUN.md](../docs/paper_v2/S1_JUDGE_RUN.md) | S1 judge run |
| [audit_reports/](audit_reports/) | [audit_2026-08-25.md](audit_reports/audit_2026-08-25.md), [scorer_v2_flip_audit.md](audit_reports/scorer_v2_flip_audit.md), [mcp_cross_purpose_promotion.md](audit_reports/mcp_cross_purpose_promotion.md) |

## Tracked files in `reports/`

`reports/` is a Python package as well as a data folder, so it stays in place.

- [latest_report.md](../reports/latest_report.md)
- [tr_audit_v1.csv](../reports/tr_audit_v1.csv)
- [tr_v1_confusion_table_frozen.json](../reports/tr_v1_confusion_table_frozen.json)
- [tr_holdout_annotation_queue.jsonl](../reports/tr_holdout_annotation_queue.jsonl)
- [tr_v2_holdout_live_2026-07-31.md](../reports/tr_v2_holdout_live_2026-07-31.md)
- [tr_v2_holdout_v1.jsonl](../reports/tr_v2_holdout_v1.jsonl)
- [tr_v2_holdout_real_provisional_v1.jsonl](../reports/tr_v2_holdout_real_provisional_v1.jsonl)
- [tr_v2_prompt_dev_v1.jsonl](../reports/tr_v2_prompt_dev_v1.jsonl)
- Package code: [__init__.py](../reports/__init__.py), [schema.py](../reports/schema.py)

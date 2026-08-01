# Attribution — external corpus Phase 1

This project may normalize **prompt cases** from the following Apache-2.0
sources for research evaluation. Retain upstream LICENSE/NOTICE files from
each snapshot. This is attribution, not a claim of affiliation.

## doronp/agentshield-benchmark

- Repository: https://github.com/doronp/agentshield-benchmark
- Commit: `a0eb8fbc0d1a099da9299575013639168c98441b`
- License: Apache License 2.0
- Use: public-replay regression cases via `corpus/*/tests.jsonl`

## Evalyze-Labs/AgentShield-Bench

- Repository: https://github.com/Evalyze-Labs/AgentShield-Bench
- Commit: `0f8f1f2f8f8e1a20e151a05aa7e0950554e2bc7b`
- License: Apache License 2.0
- Use: public-replay cases from `datasets/attacks.json` only (no v3 sum)

## Agent Shield obligations

- Do not remove copyright, patent, trademark, or attribution notices.
- Do not treat public replay as an unseen holdout.
- Keep per-source metrics separate before any macro average.
- Evalyze “TRS” (Task Retention Score) is **not** Transparency Rate.

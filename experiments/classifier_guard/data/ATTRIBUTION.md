# Attribution: classifier guard evaluation texts

`data/v2/eval_texts.jsonl` holds 764 texts. Every text has one row in `data/v2/manifest.jsonl` with its `source`, `path`, `license` and SHA256. The counts below are computed from `manifest.jsonl`.

| Id prefix | Texts | Source repository | Commit | License |
|---|---|---|---|---|
| `ext/doronp_agentshield-benchmark/` | 537 (472 attack, 65 harmless) | github.com/doronp/agentshield-benchmark | `a0eb8fbc0d1a099da9299575013639168c98441b` | Apache 2.0, `LICENSE-doronp-agentshield-benchmark.txt` |
| `ext/Evalyze-Labs_AgentShield-Bench/` | 130 (130 attack, 0 harmless) | github.com/Evalyze-Labs/AgentShield-Bench, `datasets/attacks.json` | `0f8f1f2f8f8e1a20e151a05aa7e0950554e2bc7b` | Apache 2.0, `LICENSE-Evalyze-Labs-AgentShield-Bench.txt` |
| `AS-` | 97 (12 attack, 85 harmless) | this repository (agent-shield) | the files named in each row's `path` | MIT, the repository `LICENSE` |

## How the commits were confirmed

- The full commit hashes are the pinned Phase 1 sources in `agent_shield/external_corpus/__init__.py` (`PHASE1_SOURCES`).
- The local snapshots the texts were read from are git checkouts. `git rev-parse HEAD` in each printed the same full hash on 2026-11-11, with a clean working tree.
- Every external row in `manifest.jsonl` records the short hash in its `path` field (`a0eb8fbc` and `0f8f1f2f`), and no other hash appears.

## Licenses and notices

- Both `LICENSE-*.txt` files are byte copies of the `LICENSE` file at the pinned commit of each source.
- Neither snapshot holds a `NOTICE` file (checked 2026-11-11), so no notice text is carried.
- Texts from the two Apache 2.0 corpora are unmodified extracts. No payload string was edited.

## Model

The scores in `runs/cpu-v2/` come from `protectai/deberta-v3-base-prompt-injection-v2` (Apache 2.0) at revision `90c9989b1a342275dd0d1a95aad283c04e075671` (`score.py`). The model is fetched from Hugging Face at run time. Its weights are not redistributed here.

## Handling

Attack strings are data. Do not execute them and do not send them to a live agent.

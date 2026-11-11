# Provenance: classifier guard experiment

Origin: `gpu-guard`, a local working folder with no git history. Imported 2026-11-11 by explicit file list. Source hashes were recorded before any copy. The table below is produced by a script and lists every file in this folder except this one.

| Destination | Source | Source SHA256 | Committed SHA256 | Change |
|---|---|---|---|---|
| `audit_data.py` | `audit_data.py` | `eeb8c836236000e936db03abdc9a2c6a20fc1cf6fe3dfd762fc47bbc59d08c12` | `b3d15b05296c4f2ac1e1a89cab4a31e4333087578e0b5f60c1e2bc1c2f021d23` | default data dir data/v2; usage line; home path regex rewritten as one alternation with identical matches; ruff format and lint fixes with no behavior change (context managers for file reads, zip strict, UTC alias) |
| `build_manifest.py` | `build_manifest.py` | `2b6796935087955c21a75f1b700b239ba6483be39b9b534b5f6433b6fc8b5018` | `1e1478aa37fc1e48855879ce657bff281c7540566f7de19f65a0aa69d1e170b7` | repository root from the file location; taintgate fixture read and --v2 flag removed, always writes data/v2 and refuses to overwrite; usage line; ruff format and lint fixes with no behavior change (context managers for file reads, zip strict, UTC alias) |
| `metrics.py` | `metrics.py` | `cbdb070daa258e0bf2c39966d350511495037d32a83f591747f7a8f812775c53` | `ad9e63ac07b00a824c4a8feffe8f487fb68e760e9b9fad2c5e7d9c5c93c5984b` | default data dir data/v2; usage line; ruff format and lint fixes with no behavior change (context managers for file reads, zip strict, UTC alias) |
| `regex_baseline.py` | `regex_baseline.py` | `d33a65a6a41ecbdf34b95e2ae23f605f2dcda6056a1444c970da545d32f8e836` | `0aee7def1310738ba7d0156453684c0589c21526455d57f118e231debffc801f` | repository root from the file location; reads data/v2; usage line; ruff format and lint fixes with no behavior change (context managers for file reads, zip strict, UTC alias) |
| `score.py` | `score.py` | `b4a36e19263e5eca4aadb7a95d217b274ee78b869d8a9b756b19e59ad83fe7f7` | `595c4998285af3bb3f07ab7c2eebc23e1756e103957f2674a7445c1e2321e1aa` | torch and transformers imported inside functions; encode_windows and pick_window extracted and called by Guard.score; default data dir data/v2; usage line; ruff format and lint fixes with no behavior change (context managers for file reads, zip strict, UTC alias); env.json data_dir written relative to the repository root; usage line runs this folder's own uv project |
| `PHASE1_DESIGN.md` | `PHASE1_DESIGN.md` | `27e084f19b835aba2677f51f7430a6c98080e2e12273b26fa2ca97604e7a533b` | `cd9591813f6481b4f7242b1dc6b56b4d19de1613035eccdb50af03d42f483fac` | import note under the title; one internal finding line removed |
| `DATA_READINESS.md` | `DATA_READINESS.md` | `ca4a7363b8d394d7e4c9b29310acfcdab323e011eb4c1d2fb2b8a98e94d832ee` | `ab33adc525c22ca93ce8a8b5cfa3fce427f7dbebb845c3897d8505fef9b39c0a` | import note under the title; three lines reworded (home directory paths, personal documents) |
| `KAGGLE_PLAN.md` | `KAGGLE_PLAN.md` | `bee963d481de68ba4f39d91060b56e16d9dd24baadd802c6de44dc633855cd6b` | `2faaf29d2346bd0369736ef79472e6a1638d4888a1b7d5fdffefd7e0a9575f86` | import note under the title |
| `data/v2/eval_texts.jsonl` | `data/v2/eval_texts.jsonl` | `5ff6bd5442f3704061987eba6975ead13c415af814495839e1252ddb1084ab62` | `5ff6bd5442f3704061987eba6975ead13c415af814495839e1252ddb1084ab62` | none |
| `data/v2/manifest.jsonl` | `data/v2/manifest.jsonl` | `dae2bde2d327e9ca7c9cb15387d7fef25ba4be550f758394a1d318f767142f5a` | `dae2bde2d327e9ca7c9cb15387d7fef25ba4be550f758394a1d318f767142f5a` | none |
| `data/v2/duplicates.json` | `data/v2/duplicates.json` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945` | none |
| `data/v2/overlap.json` | `data/v2/overlap.json` | `d3fe50e34b34cd6af27696926ec9b87b19d964b65514a9652fd1ef24f5448b80` | `d3fe50e34b34cd6af27696926ec9b87b19d964b65514a9652fd1ef24f5448b80` | none |
| `data/v2/sensitive_scan.json` | `data/v2/sensitive_scan.json` | `fa4fe7481d6ae5fb310a7c2954552869b56611765d35d25a03706ba9644602a9` | `fa4fe7481d6ae5fb310a7c2954552869b56611765d35d25a03706ba9644602a9` | none |
| `runs/cpu-v2/env.json` | `runs/cpu-v2/env.json` | `40f3c2a1723aaa874a3e80554c22c39f95e32c0fb5f466d15e99a3ba8fde6409` | `b88f626a678138d268ac7df588f55c34cd5b31dca7a46f4bfde1cb1a9591657d` | data_dir value replaced with data/v2 (was an absolute local path); no other field changed |
| `runs/cpu-v2/scores.jsonl` | `runs/cpu-v2/scores.jsonl` | `483abb622f3ebef24ef3b9bb501d35561c4d6965a7749105965866489c406ccb` | `483abb622f3ebef24ef3b9bb501d35561c4d6965a7749105965866489c406ccb` | none |
| `runs/cpu-v2/latency.jsonl` | `runs/cpu-v2/latency.jsonl` | `af25fa158524aa81e93109cdcde57203c454d2e7d0eb50f7d9f7272672c0fa38` | `af25fa158524aa81e93109cdcde57203c454d2e7d0eb50f7d9f7272672c0fa38` | none |
| `data/LICENSE-doronp-agentshield-benchmark.txt` | `data/external/doronp__agentshield-benchmark/LICENSE` | `cb35a1d614e1881f6bc7272ef8dfdaadeab5ad17f0e2b5de6a205c640e022e57` | `cb35a1d614e1881f6bc7272ef8dfdaadeab5ad17f0e2b5de6a205c640e022e57` | none (renamed copy) |
| `data/LICENSE-Evalyze-Labs-AgentShield-Bench.txt` | `data/external/Evalyze-Labs__AgentShield-Bench/LICENSE` | `cf316b9dbcfc7ed2b0ddc0b3ab0c8ed06a1433535bd9bcf972bccf3b6fdc09f8` | `cf316b9dbcfc7ed2b0ddc0b3ab0c8ed06a1433535bd9bcf972bccf3b6fdc09f8` | none (renamed copy) |
| `data/ATTRIBUTION.md` | - | `-` | `ef04d7f4319b523592575463b394315fa76dfcf15038b763de47b5efdfecf649` | new file written for this import |
| `pyproject.toml` | - | `-` | `816bcb79f86ac9a0ca221f8eea4ce6d81d05c0c8495b1b3ccaefd6a62bea554d` | new file written for AS-06: the scorer's own uv project |
| `uv.lock` | - | `-` | `742f79505d065d7ad7e27ae1354ac7380f68e5836cb90f1522ef9f62227014da` | new file written for AS-06: lock for that project |
| `README.md` | - | `-` | `8eeb8a1d70ddaf5b2f7403a55d24ba3eead1780fab20b99f6673ec3a762a7c3f` | new file written for AS-06 |

## Left out, and why

- v1 data (`data/*.jsonl`, `data/*.json`): it holds the 2 taintgate fixture lines, which have never been published. Only v2 is merged.
- Runs `cpu-a`, `cpu-b` and `regex`, and `report/`: they score or summarize v1. The docs still quote some of their numbers, and those numbers have no backing file here.
- `kaggle_package/`: an upload bundle that repeats files already here. Its two Apache 2.0 license copies hash equal to the snapshot `LICENSE` files.
- `data/external/` and `hf_cache/`: third party snapshots and model cache, fetched again on demand and ignored by `.gitignore`.
- `.venv/`, `.gitignore`, `requirements.lock.txt`: environment files. The three pins the scorer needs are listed under Dependency pins below.
- One agent prompt file in the source folder: untrusted session text, not part of the experiment.

## Changed fields and code

- `runs/cpu-v2/env.json`: only the `data_dir` value changed, from an absolute local path to `data/v2`. Every other field, including `manifest_sha256` and `texts_sha256`, is as the run wrote it.
- `score.py` and `build_manifest.py` differ from the versions that produced the committed outputs. `build_manifest.py` was rerun (below). `score.py` was not rerun: no classifier ran during the import. Equivalence of a rescore with `runs/cpu-v2/scores.jsonl` within 1e-4 per text is owed at AS-11.

## Rebuild check

`build_manifest.py` was rerun on a scratch copy of this repository with the two pinned snapshots, and its output was compared by SHA256 with the committed v2 files:

- `eval_texts.jsonl`: committed=5ff6bd5442f3704061987eba6975ead13c415af814495839e1252ddb1084ab62 rebuilt=5ff6bd5442f3704061987eba6975ead13c415af814495839e1252ddb1084ab62 same
- `manifest.jsonl`: committed=dae2bde2d327e9ca7c9cb15387d7fef25ba4be550f758394a1d318f767142f5a rebuilt=dae2bde2d327e9ca7c9cb15387d7fef25ba4be550f758394a1d318f767142f5a same
- `duplicates.json`: committed=4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 rebuilt=4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 same

VERDICT: MATCH

## Dependency pins

The scorer needs `torch==2.15.0`, `transformers==5.22.0` and `tokenizers==0.23.3`. They are pinned in this folder's `pyproject.toml` and locked in its `uv.lock`, a project apart from the repository's main `pyproject.toml`, so the main install carries no torch. The three pins come from the source folder's `requirements.lock.txt`, and the torch and transformers versions match `runs/cpu-v2/env.json`. Every other version in `uv.lock` was resolved at lock time and was not copied from the source environment.

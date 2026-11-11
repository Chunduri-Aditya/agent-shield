# Phase 1 data readiness, before any upload

Import note (2026-11-11): imported from the gpu-guard working folder into `experiments/classifier_guard/`. The v1 data in `data/`, the runs `cpu-a`, `cpu-b` and `regex`, the `report/` folder and the Kaggle package named below are not in this repository. Only the v2 data and the `cpu-v2` run are. See `PROVENANCE.md`.

Status, 2026-10-29: local only. Nothing has been uploaded. No GPU run has started. Both wait for Aditya's approval of the environment and the upload.

## 1. Exact manifest

Built by `build_manifest.py`. Every text carries its SHA256 in `data/manifest.jsonl`.

| File | SHA256 |
|---|---|
| `data/eval_texts.jsonl` | `a096c68d98349f163b64caf440aed35a39382e87f89cee8def6ed158d4a1b730` |
| `data/manifest.jsonl` | `ca239ea2450d1f0700dc47dc793d3bd34b896eab38eb078067098537a23e3e89` |

| Group | Source | License | Texts | Label |
|---|---|---|---|---|
| A1 | agent-shield, `tools/payloads.py`, `inputs/attacks.py` | MIT | 6 | attack, headline |
| A1-drift | agent-shield, `drift/attacks.py` | MIT | 6 | attack, own subgroup |
| A2 | `doronp/agentshield-benchmark` at `a0eb8fbc` | Apache 2.0 | 472 | attack |
| A2 | `Evalyze-Labs/AgentShield-Bench` at `0f8f1f2f` | Apache 2.0 | 130 | attack |
| B-external | `doronp/agentshield-benchmark` at `a0eb8fbc` | Apache 2.0 | 65 | harmless |
| B1 | agent-shield, `evals/data/tools_v2_tasks.jsonl`, `evals/inputs.py` | MIT | 85 | harmless |
| B2 | taintgate, `fixtures/benign.txt` | no license file, Aditya's own repo | 2 | harmless |

Totals: 766 texts, 614 attacks, 152 harmless. Exact duplicates dropped: 0. Headline attacks: 278. Split, seed 20261029: 534 test, 232 dev.

The design table listed 12 texts for A1. The build puts the 6 drift strings in their own subgroup, as the design rules require, so A1 holds 6.

## 2. License and redistribution

| Source | Finding |
|---|---|
| doronp and Evalyze corpora | Apache 2.0 `LICENSE` at the pinned commits. No `NOTICE` file in either. Redistribution is allowed with the license text and attribution. A packaged upload must include both `LICENSE` files and the source commit for each text. |
| agent-shield | MIT, copyright Aditya Chunduri. The repo is public on GitHub (unauthenticated API returned 200 on 2026-10-29). All five source files are tracked and `main` matches `origin/main`. |
| taintgate | Aditya's own local repo. No remote, no license file. 2 lines, 90 bytes. Uploading them publishes them for the first time. Aditya decides. |
| Model | `protectai/deberta-v3-base-prompt-injection-v2`, Apache 2.0. Downloaded from Hugging Face at run time, not repackaged. |

Kaggle note: a private Kaggle dataset is still a copy on a third party service. Keep it private, and include the two Apache `LICENSE` files.

## 3. Sensitive information scan

`audit_data.py`, output `data/sensitive_scan.json` (ids and pattern names only).

| Pattern | Texts hit | Finding |
|---|---|---|
| API keys, AWS keys, GitHub, Slack tokens, private key blocks | 0 | none |
| Owner name, macOS home directory paths | 0 | none |
| Email | 29 | placeholder and attacker addresses written into public corpora and the TL-01 payload: example.com, company.com, evil.com, attacker@mail.com and similar |
| `/home/<user>` paths | 4 | generic `/home/user` inside attack strings |
| `password:` or `password=` | 2 | fake values inside attack strings |

Limit: a regex scan finds known shapes only. The 29 email ids were read by hand on 2026-10-29. The other hits were checked by pattern.

## 4. Training data overlap

The model card at revision `90c9989b` names 7 training sets. Its license summary counts 22 datasets, plus injections the authors wrote themselves. Only the 7 named sets can be checked.

| Set | Status | Strings checked |
|---|---|---|
| jackhhao/jailbreak-classification | checked | 2,612 |
| natolambert/xstest-v2-copy | checked | 18,480 |
| OpenSafetyLab/Salad-Data | checked | 166,430 |
| alespalla/chatbot_instruction_prompts | checked | 645,106 |
| HuggingFaceH4/grok-conversation-harmless | checked | 313,943 |
| Harelix/Prompt-Injection-Mixed-Techniques-2024 | unavailable, DatasetNotFoundError | 0 |
| VMware/open-instruct | checked | 729,790 |

Method: exact match after normalization, and word 8 gram Jaccard flagged at 0.8 or higher. 25 short texts have no 8 gram and were checked by exact match only.

Flagged, all exact matches: `AS-BENIGN-01`, doronp `or-026`, `pi-069`, `pi-070`. Results are reported with and without them.

What this does not show: absence of overlap with the 15 unnamed sets, the missing Harelix set, or the authors' own written injections. Any clean result here is a lower bound on overlap, not proof of none.

## 5. No private material, no credentials

- Every text comes from a public Apache 2.0 corpus at a pinned commit, from the public agent-shield repo, or from 2 taintgate fixture lines.
- No study outputs, judge transcripts, trace logs, personal documents, or answer files are in the set. `build_manifest.py` reads only the files listed in section 1.
- The scan in section 3 found no keys, tokens or private key blocks, and no owner name or local path.
- `.gitignore` excludes `.venv/`, `hf_cache/` and `data/external/`. No token is stored in this folder.

## 6. Model status and limits

The model card at the pinned revision says: "THIS PROJECT HAS BEEN ARCHIVED." The project and its GitHub code are "no longer under active development or maintained."

Limits stated on the card:

- "It does not detect jailbreak attacks or handle non-English prompts."
- It is not recommended for system prompts "as it produces false-positives."
- The card reports 99.93 percent accuracy on its own evaluation split. That is the authors' number on their own data, not ours.

Our consequences: no fixes or retraining will come upstream. Any weakness found here stays. The model is a measurement subject for Phase 1, not a recommended production guard.

## 7. Revised manifest v2 for the GPU run (Aditya, 2026-10-29)

Aditya excluded the 2 taintgate lines, which have never been published. `build_manifest.py --v2` writes `data/v2/`. v1 in `data/` is unchanged and still backs the CPU baseline report.

| File | SHA256 |
|---|---|
| `data/v2/eval_texts.jsonl` | `5ff6bd5442f3704061987eba6975ead13c415af814495839e1252ddb1084ab62` |
| `data/v2/manifest.jsonl` | `dae2bde2d327e9ca7c9cb15387d7fef25ba4be550f758394a1d318f767142f5a` |

| Check, run 2026-10-29 | Result |
|---|---|
| Rows | 764: 614 attacks, 278 headline, 150 harmless |
| Removed | `TG-BENIGN-01`, `TG-BENIGN-02` only |
| Every other row, text and split | identical to v1 |
| Split | 533 test, 231 dev. B2 was the last group seeded, so no other split moved. |
| Sources in v2 | doronp 537, Evalyze 130, agent-shield 97. No taintgate text. |
| Sensitive scan rerun on v2 | Same hits as v1: email 29, password 2, `/home/user` 4. No keys, no owner name, no macOS home directory path. |
| Overlap rerun on v2 | Same 4 exact matches. Harelix still unavailable. 24 short texts checked by exact match only. |
| CPU rescore of v2 with the revised `score.py` | 764 probabilities identical to `cpu-a`, max difference 0.0 |
| Headline FPR on v2, CPU | 0.0933 [0.0564, 0.1506] on 150 harmless. v1 was 0.0921 on 152, because both taintgate lines were true negatives. |

Final privacy, license and redistribution review of v2:

- Privacy: every v2 text is from a public GitHub repo at a pinned commit. Nothing private is included.
- Credentials: none found by the scan. No token is in the package or the plan.
- Licenses: two Apache 2.0 corpora and the MIT agent-shield repo. All three license files ship in `kaggle_package/`, with `ATTRIBUTION.md` mapping each id prefix to its source and commit.
- Redistribution: all three licenses allow a private copy on Kaggle with attribution. Keep the dataset private anyway. It holds attack strings.

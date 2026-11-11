# GPU-served guard for Agent Shield: Phase 1 design

Import note (2026-11-11): imported from the gpu-guard working folder into `experiments/classifier_guard/`. The v1 data in `data/`, the runs `cpu-a`, `cpu-b` and `regex`, the `report/` folder and the Kaggle package named below are not in this repository. Only the v2 data and the `cpu-v2` run are. See `PROVENANCE.md`.

Status: design only, written 2026-10-29 for Aditya's review. No code has run. No data has been scored. When this design is approved, it moves into the Agent Shield repository as an experiment folder.

Approved scope (Aditya, 2026-10-29): Phase 1 only, budget $0, free cloud GPU, Kaggle preferred. No paid billing and no credits.

## 1. Question

Can an open-weight prompt injection classifier screen agent tool output on a free GPU? How fast is it, compared with the same model on CPU? What does it catch on Agent Shield's existing attack and harmless texts?

Phase 1 measures only. It optimizes nothing.

## 2. Threat model

| Item | Phase 1 definition |
|---|---|
| Asset | An LLM agent that reads tool output, for example from file reads, web fetches or MCP tools. It also holds write, execute and network tools. |
| Attacker | Controls the text of one tool output. Cannot change the agent, the classifier or the gate. |
| Attack | Indirect prompt injection: instructions hidden in tool output to make the agent take an action the operator did not ask for. |
| Defender | A classifier that reads the tool output before the agent acts on it, as taintgate's screening hook does with the regex guard. |
| Attacker strength | Non adaptive. Fixed strings written before this experiment. The attacker never sees classifier scores. |
| Out of scope | Adaptive or optimized attacks. Direct user jailbreaks. Secret leak detection, which the regex guard covers. Non English text. Images. |

## 3. Classifier input and output

| Item | Definition |
|---|---|
| Model | `protectai/deberta-v3-base-prompt-injection-v2`. Apache 2.0, not gated, about 0.2B parameters. The model card says the project is archived. The revision is pinned by commit hash at download. |
| Input | One tool output as a UTF-8 string. It is tokenized with the model's own tokenizer. |
| Long inputs | Split into 512 token windows with a 256 token stride. |
| Output per window | Probability of label 1, "injection". |
| Output per text | The maximum window probability, plus the window index and count. |
| Decision | Injection if the probability is 0.5 or higher. This threshold is fixed now, before any scoring, and is never tuned on the evaluation set. |

The model card says it "does not detect jailbreak attacks or handle non-English prompts". It is also not recommended for system prompts. These are known limits, reported with the results.

## 4. Evaluation data

| Set | Source | Label | Size known now |
|---|---|---|---|
| A1 | Agent Shield author strings: TL_01 (`tools/payloads.py:15`), IN-01 to IN-05 (`inputs/attacks.py:42-109`), DR attacks (`drift/attacks.py:66-204`) | Attack | 12 |
| A2 | External corpus, pinned Apache 2.0 sources already approved in Agent Shield: `doronp/agentshield-benchmark` at `a0eb8fbc`, `Evalyze-Labs/AgentShield-Bench` at `0f8f1f2f`, `datasets/attacks.json` only | As labeled by the source | Counted at import |
| B1 | Agent Shield harmless tool outputs: S1 stub texts (`evals/tools_v2.py`), pilot task files (`evals/tools_pilot.py:44-64`), harmless requests (`evals/inputs.py:222-228`) | Harmless | Counted at import |
| B2 | taintgate harmless fixtures (`fixtures/benign.txt`) | Harmless | 2 lines |

Rules:

- Counts per set are frozen in a manifest, with a SHA256 for every text, before any model runs.
- The DR strings are drift attacks, not tool output injections. They are reported as their own subgroup and are not pooled into the headline.
- If the harmless sets total fewer than 100 texts, the false positive rate is reported with its wide interval, and no claim is made beyond it. New harmless texts are not written to fill the gap in Phase 1.
- Attack strings are untrusted data. They are never executed, and they are never sent to a live agent in this phase.

## 5. Leakage controls

We train nothing, so leakage here means overlap between our evaluation texts and the classifier's training data.

1. **Training data overlap.** The model card lists its training sets, including `jackhhao/jailbreak-classification`, `Harelix/Prompt-Injection-Mixed-Techniques-2024` and others. Each evaluation text is checked for an exact match after normalization, and for 8 gram Jaccard similarity of 0.8 or higher, against every listed set that can be downloaded. Matches are flagged. Results are reported both with and without them.
2. **Threshold.** It stays fixed at 0.5. Nothing is calibrated on the evaluation texts.
3. **Dev split frozen now, unused in Phase 1.** A seeded 30 percent split per source is written to the manifest. Any later calibration may only use the dev split. Phase 1 reports the full set and the 70 percent test split separately.
4. **Regex baseline.** The Agent Shield regex rules were written with knowledge of the A1 strings. Their tests use the same strings (`tests/test_runtime_guard.py:23,33`). Their recall on A1 is therefore not a fair estimate, and it is labeled that way.

## 6. Baselines and metrics

| Baseline | Why |
|---|---|
| Agent Shield regex guard, ruleset `research-content-v1.1.4`, 17 rules | The screener taintgate actually calls |
| Majority class | Floor for accuracy |
| Classifier on CPU, fp32 | Reference for the GPU run |

Detection metrics are computed per set and pooled, each with a Wilson 95 percent interval:

- Recall on attacks
- False positive rate on harmless texts
- Precision
- Confusion matrix
- AUROC, reported only if both classes have at least 30 texts

Every misclassified text is listed by ID and source, with its score.

These are fixed scenario results. They are labeled Preliminary in the claims register. They are not a validated detection rate.

## 7. CPU and GPU equivalence

- Both runs use fp32 and eager mode, with the same inputs, tokenizer and revision.
- TF32 is disabled on GPU (`torch.backends.cuda.matmul.allow_tf32 = False`, `torch.backends.cudnn.allow_tf32 = False`).
- **Preregistered check:** the absolute probability difference is at most 1e-4 for every text, and the labels agree on every text.
- Any text that fails is listed with both scores. No claim that GPU preserves every label is made unless this check passes on the full set. The claim applies only to this set, model and environment.

## 8. Latency and memory

| Quantity | Definition |
|---|---|
| Screening latency | Wall time from the input string to the verdict: tokenize, window, forward pass, post process. Warm process, batch size 1. On GPU, timed with `torch.cuda.synchronize()` before each clock read. |
| Repeats | 10 warmup calls, then each text timed 20 times. Report p50, p95 and p99 per device. |
| Cold start | Model load time, reported separately |
| Throughput, secondary | Batch sizes 1, 8 and 32 |
| Memory | CPU peak RSS. GPU `torch.cuda.max_memory_allocated` and `max_memory_reserved`. |

**Separation rule.** taintgate's 0.07 ms median is the PreToolUse gate decision inside the hook. That is a different quantity. Classifier latency is never compared with it or added to it. The taintgate hook also spawns a subprocess, and its end to end hook timings were about 48 to 122 ms (`taintgate/docs/EVIDENCE.md`). Phase 1 measures in process latency only, and says so.

## 9. Environment record

Each run writes a JSON record containing:

- Python version
- torch, CUDA and cuDNN versions
- transformers and tokenizers versions
- GPU name and driver from `nvidia-smi`
- CPU model and thread count
- model commit hash
- corpus commit hashes
- manifest SHA256
- random seeds
- run start and end time in UTC

Package versions are pinned in a requirements file.

## 10. Phase 1 deliverables and their pass checks

| Deliverable | Check that can fail |
|---|---|
| Reproducible CPU baseline | Two CPU runs give identical probabilities |
| GPU implementation | Runs on the Kaggle GPU with the same code path, with only the device flag changed |
| CPU and GPU comparison | The equivalence check in section 7 |
| Latency and memory | Every number traces to a raw timing file. Medians are recomputed from raw data in the report. |
| Detection analysis | Every metric is recomputed from per text scores. Errors are listed. |
| Limitations and failure cases | Written before the results section |

## 11. Known limits, stated now

- The attack sets are small and fixed. They do not represent adaptive attackers.
- The harmless set may be small and narrow. The false positive estimate may be weak.
- One model, one revision and one free GPU type. Kaggle GPUs are older than current data center parts, so absolute latency does not transfer.
- In process timing excludes the subprocess path taintgate uses today.

## 12. Not in Phase 1

- Optimization: fp16, `torch.compile`, ONNX or TensorRT export
- Custom kernels
- A second model, such as Llama Prompt Guard 2, which is gated and needs a personal access form
- Any change to taintgate or Agent Shield code

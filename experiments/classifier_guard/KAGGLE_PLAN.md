# Kaggle GPU run plan, for review

Import note (2026-11-11): imported from the gpu-guard working folder into `experiments/classifier_guard/`. The v1 data in `data/`, the runs `cpu-a`, `cpu-b` and `regex`, the `report/` folder and the Kaggle package named below are not in this repository. Only the v2 data and the `cpu-v2` run are. See `PROVENANCE.md`.

Status, 2026-10-29: prepared locally. Nothing is uploaded. No notebook exists on Kaggle. Two approvals are needed first: the revised manifest, and this environment. Budget $0.

## 1. What would be uploaded

One private Kaggle dataset built from `kaggle_package/`, 504 KB. Nothing else.

| File | SHA256 |
|---|---|
| `eval_texts.jsonl` | `5ff6bd5442f3704061987eba6975ead13c415af814495839e1252ddb1084ab62` |
| `manifest.jsonl` | `dae2bde2d327e9ca7c9cb15387d7fef25ba4be550f758394a1d318f767142f5a` |
| `score.py` | `b4a36e19263e5eca4aadb7a95d217b274ee78b869d8a9b756b19e59ad83fe7f7` |
| `ATTRIBUTION.md` | `d615446bd28c4065824226544679ddecb683e474ebc53801f680c1f765fd5a22` |
| `LICENSE-doronp-agentshield-benchmark.txt` | `cb35a1d614e1881f6bc7272ef8dfdaadeab5ad17f0e2b5de6a205c640e022e57` |
| `LICENSE-Evalyze-Labs-AgentShield-Bench.txt` | `cf316b9dbcfc7ed2b0ddc0b3ab0c8ed06a1433535bd9bcf972bccf3b6fdc09f8` |
| `LICENSE-agent-shield.txt` | `239590bcab35b7e456382182f6c03ea8146ac1b6fb19f892222b556f7c7ab11c` |

The texts and manifest are the v2 manifest in `data/v2/`. See `DATA_READINESS.md` section 7.

Not uploaded: the taintgate lines, `hf_cache/`, `data/external/`, run outputs, the regex guard, and anything from agent-shield beyond the 97 texts already public on GitHub.

## 2. Environment

| Item | Plan |
|---|---|
| Account | Aditya's Kaggle account. GPU and internet need a phone verified account. Aditya does this step. |
| Dataset visibility | Private |
| Notebook visibility | Private |
| Accelerator | One free GPU. Record what Kaggle assigns. Kaggle's free GPU names and weekly quota are not checked today. |
| Internet | On, only to download the model from Hugging Face at revision `90c9989b`. The model is not gated. No token is needed or stored. |
| Packages | `pip install transformers==5.22.0 tokenizers==0.23.3`. torch and CUDA stay as Kaggle provides them. Their versions are recorded in `env.json`. |
| Secrets | None. No Kaggle secret is added. |
| Billing | None. Free tier only. No paid accelerator. |

## 3. Notebook cells

```bash
pip install -q transformers==5.22.0 tokenizers==0.23.3
export CUBLAS_WORKSPACE_CONFIG=:4096:8
D=/kaggle/input/<dataset-slug>
python $D/score.py --device cuda --run-id gpu-1 --data-dir $D --out-dir /kaggle/working/runs
python $D/score.py --device cuda --run-id gpu-2 --data-dir $D --out-dir /kaggle/working/runs \
  --warmup 0 --latency-repeats 0
nvidia-smi
```

`score.py` is the same file that ran on CPU, with only `--device` changed. It disables TF32 and runs fp32 in eager mode.

## 4. Back on the laptop

Download `/kaggle/working/runs/` into `runs/`, then run:

```bash
.venv/bin/python metrics.py --data-dir data/v2 --runs cpu-v2 gpu-1 gpu-2 --regex regex \
  --out report/gpu_v2.json
```

| Check | Pass rule |
|---|---|
| CPU against GPU | Absolute probability difference at most 1e-4 on every text, and identical labels. Fixed before the run. |
| GPU against GPU | Same rule, so run to run noise is visible |
| Latency | p50, p95 and p99 recomputed from `runs/gpu-1/latency.jsonl` |
| Memory | `cuda_max_allocated` and `cuda_max_reserved` from `env.json` |

If any text fails, it is listed with both scores. No claim that the GPU preserves labels is made unless every text passes.

## 5. Approvals still needed

1. The v2 manifest and the package contents in section 1.
2. Creating the private Kaggle dataset and uploading these 7 files.
3. Running the notebook on the free GPU.

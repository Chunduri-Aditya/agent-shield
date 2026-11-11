# Classifier guard experiment

Scores the Phase 1 evaluation set with a pinned prompt injection classifier on CPU or GPU.

Run from the repository root:

```
uv run --project experiments/classifier_guard python experiments/classifier_guard/score.py --device cpu --run-id cpu1
```

- Output goes to `runs/<run-id>/`: `scores.jsonl`, `latency.jsonl` and `env.json`.
- `env.json` records `data_dir` relative to the repository root, never an absolute path.
- The first run fetches the pinned model revision from Hugging Face.
- Dependencies (torch, transformers, tokenizers) live in this folder's `pyproject.toml` and `uv.lock`, apart from the main project, which installs no torch.
- The PyPI torch wheel on Linux pulls NVIDIA CUDA runtime packages (15 `nvidia-` entries in `uv.lock`).
- `build_manifest.py` and `regex_baseline.py` use the main project environment. Each keeps its usage line in its docstring, run from the repository root.

See `PHASE1_DESIGN.md` for the design and `PROVENANCE.md` for the file hashes.

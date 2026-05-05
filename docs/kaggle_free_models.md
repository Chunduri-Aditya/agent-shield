# Kaggle Free Model Path

Use Kaggle API tokens for account authentication and Kaggle Benchmarks notebooks
for free model-proxy inference.

## Credential File

The Kaggle API token file should live at:

```text
~/.kaggle/kaggle.json
```

After generating a token from Kaggle account settings, the browser usually
downloads it to:

```text
~/Downloads/kaggle.json
```

Move it to `~/.kaggle/kaggle.json` and keep permissions locked down:

```bash
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json
```

Do not commit `kaggle.json`. The repo ignores it explicitly.

## Local Checks

```bash
make kaggle-auth-check
make kaggle-auth-online
```

The online check verifies the CLI can authenticate against Kaggle.

## Inputs Sweep

For free model inference, open `notebooks/run_kaggle_inputs_sweep.ipynb` in a
Kaggle Benchmarks notebook. It runs:

```bash
python scripts/kaggle_inputs_runner.py
```

Outputs:

```text
logs/kaggle_inputs_results.json
logs/kaggle_inputs_rows.md
```

Paste the generated markdown rows into `RESULTS.md`.

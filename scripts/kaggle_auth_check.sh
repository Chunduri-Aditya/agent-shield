#!/usr/bin/env bash
set -euo pipefail

config_dir="${KAGGLE_CONFIG_DIR:-$HOME/.kaggle}"
token_file="$config_dir/kaggle.json"

if [[ ! -f "$token_file" ]]; then
  echo "Missing Kaggle token file: $token_file"
  echo "Generate a Kaggle API token, then place the downloaded kaggle.json there."
  exit 1
fi

if chmod 600 "$token_file" 2>/dev/null; then
  :
else
  echo "Could not set token permissions to 600: $token_file"
  exit 1
fi

if command -v kaggle >/dev/null 2>&1; then
  kaggle_cmd=(kaggle)
elif command -v uvx >/dev/null 2>&1; then
  kaggle_cmd=(uvx --from kaggle kaggle)
else
  echo "Kaggle CLI not found. Install with: uv tool install kaggle"
  exit 1
fi

echo "Kaggle token file found: $token_file"
"${kaggle_cmd[@]}" --version

if [[ "${1:-}" == "--online" ]]; then
  echo "Checking Kaggle API auth against your account..."
  "${kaggle_cmd[@]}" kernels list --mine --page-size 1 >/dev/null
  echo "Kaggle API auth OK."
fi

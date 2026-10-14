"""Write DATA/setup.json, the frozen record every pilot gate checks against.

Run from the pilot worktree:

    uv run python scripts/pilot/setup_record.py --repo . --data DATA \
        --prices pilot/prices.yaml --cost-config pilot/inspect_model_costs.yaml \
        --pricing-date 2026-10-13

The record pins the commit the pilot runs from, the hashes of every scorer file, the
directive the delivery gate looks for, the TL-01 sample ids and the price table. It
refuses a dirty repo, an existing record, a data dir inside the repo, a missing scorer
file, an empty directive or sample list, and a pricing date that differs from the one
prices.yaml records. Keys are written sorted so the file is reproducible.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import yaml  # type: ignore[import-untyped]  # PyYAML ships no stubs

from scripts.pilot._common import SETUP_NAME, PilotError, load_prices, require_dir, sha256_file

# The files that define an Inspect @scorer, plus the marker helper three of them import for
# scoring (DATA/inventory.md section d), plus evals/tools_v12.py, the paper v1.2 TL-01 task
# and its tools_event_v1 scorer (V1_2_PLAN step 2).
SCORER_FILES: tuple[str, ...] = (
    "evals/_marker.py",
    "evals/auto_apply.py",
    "evals/drift.py",
    "evals/exfil.py",
    "evals/inputs.py",
    "evals/memory.py",
    "evals/persona/judge.py",
    "evals/persona_fidelity.py",
    "evals/psych.py",
    "evals/tools.py",
    "evals/tools_v12.py",
)

REQUIRED_KEYS: tuple[str, ...] = (
    "anthropic_version",
    "cost_config",
    "data_dir",
    "directive_sha256",
    "inspect_ai_version",
    "openai_version",
    "prices_sha256",
    "pricing_retrieved",
    "scorer_sha256",
    "setup_sha",
    "tl01_sample_ids",
)

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return done.stdout


def build_record(
    repo: Path,
    data: Path,
    prices: Path,
    cost_config: Path,
    pricing_date: str,
    *,
    scorer_files: tuple[str, ...] = SCORER_FILES,
    sample_ids: list[str],
) -> dict[str, Any]:
    """Assemble the setup record; raise PilotError on any unsafe or missing input."""
    repo = Path(repo).resolve()
    data = require_dir(Path(data))
    if data.is_relative_to(repo):
        raise PilotError(f"data dir {data} is inside the repo {repo}")

    porcelain = _git(repo, "status", "--porcelain")
    if porcelain.strip():
        raise PilotError("git status --porcelain is not empty: " + porcelain.splitlines()[0])

    scorer_sha256: dict[str, str] = {}
    for rel in scorer_files:
        path = repo / rel
        if not path.is_file():
            raise PilotError(f"scorer file {rel} missing in {repo}")
        scorer_sha256[rel] = sha256_file(path)

    directive = data / "directive.txt"
    if not directive.is_file() or not directive.read_text().strip():
        raise PilotError(f"directive {directive} missing or empty")

    if not sample_ids:
        raise PilotError("no TL-01 sample ids")

    if not _DATE.match(pricing_date):
        raise PilotError(f"--pricing-date {pricing_date!r} is not YYYY-MM-DD")
    prices = Path(prices).resolve()
    load_prices(prices)  # fails closed on a malformed table
    retrieved = str(yaml.safe_load(prices.read_text()).get("retrieved", ""))
    if retrieved != pricing_date:
        raise PilotError(f"prices.yaml retrieved {retrieved!r} != --pricing-date {pricing_date!r}")

    cost_config = Path(cost_config).resolve()
    if not cost_config.is_file():
        raise PilotError(f"cost config {cost_config} missing")

    return {
        "anthropic_version": importlib.metadata.version("anthropic"),
        "cost_config": str(cost_config),
        "data_dir": str(data),
        "directive_sha256": sha256_file(directive),
        "inspect_ai_version": importlib.metadata.version("inspect_ai"),
        "openai_version": importlib.metadata.version("openai"),
        "prices_sha256": sha256_file(prices),
        "pricing_retrieved": pricing_date,
        "scorer_sha256": scorer_sha256,
        "setup_sha": _git(repo, "rev-parse", "HEAD").strip(),
        "tl01_sample_ids": list(sample_ids),
    }


def write_record(data: Path, record: dict[str, Any]) -> Path:
    """Write DATA/setup.json with sorted keys; never overwrite an existing record."""
    missing = [k for k in REQUIRED_KEYS if k not in record]
    if missing:
        raise PilotError(f"record lacks {missing}")
    path = Path(data) / SETUP_NAME
    if path.exists():
        raise PilotError(f"{path} exists; the setup record is written once")
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    return path


def _tl01_sample_ids(repo: Path) -> list[str]:
    """Import the v1.2 TL-01 task from --repo, so the ids are the ones that will run:
    the anchored design (20) then the 10 prompt set."""
    sys.path.insert(0, str(repo))
    module = importlib.import_module("evals.tools_v12")
    return [str(i) for i in module.all_sample_ids()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--prices", required=True, type=Path)
    parser.add_argument("--cost-config", required=True, type=Path)
    parser.add_argument("--pricing-date", required=True)
    args = parser.parse_args(argv)
    try:
        repo = args.repo.resolve()
        record = build_record(
            repo,
            args.data,
            args.prices,
            args.cost_config,
            args.pricing_date,
            sample_ids=_tl01_sample_ids(repo),
        )
        path = write_record(args.data, record)
    except PilotError as exc:
        print(f"setup record: REFUSED: {exc}", file=sys.stderr)
        return 1
    print(f"setup record written: {path}")
    print(json.dumps(record, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

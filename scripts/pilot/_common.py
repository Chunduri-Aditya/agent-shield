"""Shared helpers for the pilot scripts: prices, ledger, setup record, hashes, log reading.

Every helper fails closed: an unknown model, a malformed ledger line, or a missing setup
key raises PilotError instead of returning a default.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]  # PyYAML ships no stubs in this venv
from inspect_ai.log import EvalLog, read_eval_log

PRICE_KEYS = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")
LEDGER_NAME = "ledger.jsonl"
SETUP_NAME = "setup.json"


class PilotError(Exception):
    """A pilot input is missing, malformed, or unknown. Callers exit 1 on it."""


def strip_provider(model: str) -> str:
    """Return the model short name: "anthropic/claude-haiku-5-5" becomes "claude-haiku-5-5"."""
    return model.rsplit("/", 1)[-1]


def load_prices(path: Path) -> dict[str, dict[str, float]]:
    """Read prices.yaml into {model short name: {price key: USD per million tokens}}."""
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict) or not isinstance(raw.get("models"), dict):
        raise PilotError(f"{path}: no 'models' mapping")
    prices: dict[str, dict[str, float]] = {}
    for name, row in raw["models"].items():
        if not isinstance(row, dict):
            raise PilotError(f"{path}: model {name!r} is not a mapping")
        missing = [k for k in PRICE_KEYS if k not in row]
        if missing:
            raise PilotError(f"{path}: model {name!r} lacks {missing}")
        prices[str(name)] = {k: float(row[k]) for k in PRICE_KEYS}
    return prices


def price_for(prices: dict[str, dict[str, float]], model: str) -> dict[str, float]:
    """Look a model up by short name; an unknown model is a hard error."""
    short = strip_provider(model)
    if short not in prices:
        raise PilotError(f"unknown model {model!r} (short name {short!r}) not in prices")
    return prices[short]


def ledger_path(data_dir: Path) -> Path:
    return Path(data_dir) / LEDGER_NAME


def read_ledger(data_dir: Path) -> list[dict[str, Any]]:
    """Read D/ledger.jsonl; a missing ledger is empty, a malformed line is an error."""
    path = ledger_path(data_dir)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for n, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PilotError(f"{path}:{n}: not JSON ({exc})") from exc
        if not isinstance(row, dict) or not isinstance(row.get("cost"), int | float):
            raise PilotError(f"{path}:{n}: row lacks a numeric cost")
        if not isinstance(row.get("model"), str):
            raise PilotError(f"{path}:{n}: row lacks a model")
        rows.append(row)
    return rows


def ledger_totals(rows: list[dict[str, Any]]) -> tuple[float, dict[str, float]]:
    """Return (overall total, {model short name: total})."""
    per_model: dict[str, float] = {}
    for row in rows:
        short = strip_provider(row["model"])
        per_model[short] = per_model.get(short, 0.0) + float(row["cost"])
    return sum(per_model.values()), per_model


def load_setup(data_dir: Path) -> dict[str, Any]:
    """Read D/setup.json; it must carry setup_sha and a scorer_sha256 mapping."""
    path = Path(data_dir) / SETUP_NAME
    if not path.exists():
        raise PilotError(f"{path} missing")
    setup = json.loads(path.read_text())
    if not isinstance(setup, dict):
        raise PilotError(f"{path}: not an object")
    if not isinstance(setup.get("setup_sha"), str) or not setup["setup_sha"]:
        raise PilotError(f"{path}: setup_sha missing")
    if not isinstance(setup.get("scorer_sha256"), dict):
        raise PilotError(f"{path}: scorer_sha256 missing")
    return setup


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def scorer_hashes_match(repo_dir: Path, setup: dict[str, Any]) -> tuple[bool, list[str]]:
    """Compare each recorded scorer file hash against the file in repo_dir.

    An empty record is a mismatch: nothing pinned means nothing proven.
    """
    recorded: dict[str, str] = setup["scorer_sha256"]
    if not recorded:
        return False, ["setup.json scorer_sha256 is empty"]
    mismatches: list[str] = []
    for rel, expected in sorted(recorded.items()):
        path = Path(repo_dir) / rel
        if not path.is_file():
            mismatches.append(f"{rel}: missing")
            continue
        actual = sha256_file(path)
        if actual != expected:
            mismatches.append(f"{rel}: {actual[:12]} != recorded {str(expected)[:12]}")
    return not mismatches, mismatches


def read_log(path: Path) -> EvalLog:
    """Read a log with attachments resolved, so attachment:// refs become their text."""
    return read_eval_log(str(path), resolve_attachments=True)


def require_dir(path: Path) -> Path:
    resolved = Path(path).resolve()
    if not resolved.is_dir():
        raise PilotError(f"--data {path}: not a directory")
    return resolved

"""
scripts/bundle_reproducibility.py

Collect all .eval log files referenced in RESULTS.md, copy them into
reproducibility_bundle/, and write a manifest.json with metadata extracted
from RESULTS.md context and the log filenames themselves.

Usage
-----
    uv run python scripts/bundle_reproducibility.py
    uv run python scripts/bundle_reproducibility.py --dry-run
    uv run python scripts/bundle_reproducibility.py --out path/to/dir

The script never modifies RESULTS.md or any source file.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_MD = REPO_ROOT / "RESULTS.md"
LOGS_DIR = REPO_ROOT / "logs"
DEFAULT_OUT = REPO_ROOT / "reproducibility_bundle"

# ---------------------------------------------------------------------------
# Log filename parser
# Filenames follow the Inspect AI convention:
#   <ISO-datetime>_<task-name>_<random-id>.eval
# Example: 2026-05-24T07-13-45-00-00_tools-transparency_Vt3ENMga8WwfDG9dmFVsGc.eval
# ---------------------------------------------------------------------------

LOG_PATTERN = re.compile(
    r"logs/("
    r"(\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}[-\d]*)_"  # datetime prefix
    r"([\w-]+)_"                                          # task name
    r"([\w]+)"                                            # random ID
    r"\.eval)"
)


@dataclass
class LogEntry:
    filename: str          # basename, e.g. "2026-05-24T07-13-45-00-00_tools-transparency_Vt3ENMga8WwfDG9dmFVsGc.eval"  # noqa: E501
    task_name: str         # e.g. "tools-transparency"
    date_prefix: str       # e.g. "2026-05-24"
    random_id: str         # Inspect-assigned ID
    source_path: str       # relative: "logs/<filename>"
    present_in_repo: bool  # whether the .eval file exists locally
    # Metadata extracted from RESULTS.md context (best-effort)
    model_id: str = ""
    seed: str = ""
    commit_sha: str = ""
    n_samples: str = ""
    module: str = ""
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Metadata patterns — best-effort extraction from RESULTS.md prose
# ---------------------------------------------------------------------------

MODEL_PATTERN = re.compile(
    r"`?(anthropic/claude[\w.-]+|ollama/[\w.:]+|groq/[\w.-]+|google/[\w.-]+|"
    r"claude-sonnet[\w.-]*|llama[\w.:]+|gemini[\w.-]+)`?",
    re.IGNORECASE,
)
SEED_PATTERN = re.compile(r"seed\s+(\d+)", re.IGNORECASE)
SHA_PATTERN = re.compile(r"\b([0-9a-f]{7,40})\b")
N_PATTERN = re.compile(r"n=(\d+)")

MODULE_FROM_TASK = {
    "inputs": "inputs",
    "tools": "tools",
    "psych": "psych",
    "memory": "memory",
    "exfil": "exfil",
    "drift": "drift",
    "smoke": "smoke",
}


def _module_from_task_name(task_name: str) -> str:
    for key, module in MODULE_FROM_TASK.items():
        if key in task_name:
            return module
    return "unknown"


def _extract_context(results_text: str, filename: str) -> dict[str, str]:
    """
    Find the paragraph(s) in RESULTS.md that reference `filename` and pull
    model ID, seed, commit SHA, and n from nearby text.
    Returns a dict with keys: model_id, seed, commit_sha, n_samples.
    """
    idx = results_text.find(filename)
    if idx == -1:
        return {}

    # Grab 800 chars before and 400 after the reference
    window = results_text[max(0, idx - 800): idx + 400]

    model_match = MODEL_PATTERN.search(window)
    seed_match = SEED_PATTERN.search(window)
    sha_match = SHA_PATTERN.search(window)
    n_match = N_PATTERN.search(window)

    return {
        "model_id": model_match.group(0).strip("`") if model_match else "",
        "seed": seed_match.group(1) if seed_match else "",
        "commit_sha": sha_match.group(1) if sha_match else "",
        "n_samples": n_match.group(1) if n_match else "",
    }


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def parse_log_entries(results_text: str) -> list[LogEntry]:
    """Extract every unique .eval reference from RESULTS.md."""
    seen: set[str] = set()
    entries: list[LogEntry] = []

    for match in LOG_PATTERN.finditer(results_text):
        rel_path = match.group(1)       # full relative path including "logs/"
        filename = Path(rel_path).name  # just the basename

        if filename in seen:
            continue
        seen.add(filename)

        task_name = match.group(3)
        random_id = match.group(4)
        source_path = LOGS_DIR / filename
        present = source_path.exists()

        ctx = _extract_context(results_text, filename)

        entry = LogEntry(
            filename=filename,
            task_name=task_name,
            date_prefix=match.group(2)[:10],
            random_id=random_id,
            source_path=f"logs/{filename}",
            present_in_repo=present,
            model_id=ctx.get("model_id", ""),
            seed=ctx.get("seed", ""),
            commit_sha=ctx.get("commit_sha", ""),
            n_samples=ctx.get("n_samples", ""),
            module=_module_from_task_name(task_name),
        )
        entries.append(entry)

    return entries


def build_bundle(
    entries: list[LogEntry],
    out_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Copy present logs and write manifest.json. Returns the manifest dict."""

    present = [e for e in entries if e.present_in_repo]
    missing = [e for e in entries if not e.present_in_repo]

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        logs_out = out_dir / "logs"
        logs_out.mkdir(exist_ok=True)

        for entry in present:
            src = LOGS_DIR / entry.filename
            dst = logs_out / entry.filename
            shutil.copy2(src, dst)

    manifest = {
        "generated": datetime.now(UTC).isoformat(),
        "agent_shield_version": "v1.0.0",
        "framework": "Inspect AI",
        "note": (
            "Each .eval file is an Inspect AI log artifact. "
            "API version and task set hash are recorded automatically inside each artifact. "
            "Seeds and commit SHAs are also in RESULTS.md for cross-reference."
        ),
        "reproduce_any_result": (
            "git checkout <commit_sha> && "
            "uv run inspect eval evals/<module>.py --model <model_id> --seed <seed>"
        ),
        "logs": [
            {
                "filename": e.filename,
                "source_path": e.source_path,
                "task_name": e.task_name,
                "module": e.module,
                "date": e.date_prefix,
                "model_id": e.model_id,
                "seed": e.seed,
                "n_samples": e.n_samples,
                "commit_sha": e.commit_sha,
                "present_in_bundle": e.present_in_repo,
            }
            for e in entries
        ],
        "summary": {
            "total_referenced": len(entries),
            "present_in_bundle": len(present),
            "missing_locally": len(missing),
        },
    }

    if not dry_run:
        manifest_path = out_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        readme_path = out_dir / "README.md"
        readme_path.write_text(_bundle_readme(manifest))

    return manifest


def _bundle_readme(manifest: dict) -> str:
    summary = manifest["summary"]
    return f"""\
# Agent Shield — Reproducibility Bundle

Generated: {manifest["generated"]}
Version: {manifest["agent_shield_version"]}
Framework: {manifest["framework"]}

## Contents

- `logs/` — Inspect AI `.eval` log artifacts ({summary["present_in_bundle"]} files)
- `manifest.json` — metadata for every result row in RESULTS.md

## How to reproduce any result

```bash
git checkout <commit_sha>
uv run inspect eval evals/<module>.py --model <model_id> --seed <seed>
```

Commit SHAs, seeds, model IDs, and n are in `manifest.json` and `RESULTS.md`.

## What's inside each .eval file

Inspect AI automatically records the API version, task set hash, model
parameters, per-sample prompts and completions, and scorer outputs.
Open any artifact with:

```bash
uv run inspect view logs/<filename>.eval
```

## Missing files

{summary["missing_locally"]} log files referenced in RESULTS.md were not found locally
(gitignored logs from earlier sessions). Their metadata is still in manifest.json.
The results they represent are reproducible from the commit SHA + seed.

---
Agent Shield v1.0.0 | MIT License
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bundle Inspect AI .eval logs referenced in RESULTS.md",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output directory (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print manifest without copying files",
    )
    args = parser.parse_args()

    if not RESULTS_MD.exists():
        print(f"ERROR: {RESULTS_MD} not found", file=sys.stderr)
        return 1

    results_text = RESULTS_MD.read_text()
    entries = parse_log_entries(results_text)

    if not entries:
        print("No .eval log references found in RESULTS.md", file=sys.stderr)
        return 1

    manifest = build_bundle(entries, args.out, dry_run=args.dry_run)
    summary = manifest["summary"]

    if args.dry_run:
        print(json.dumps(manifest, indent=2))
    else:
        print(
            f"Bundle written to: {args.out}\n"
            f"  Logs copied:   {summary['present_in_bundle']}\n"
            f"  Missing:       {summary['missing_locally']}\n"
            f"  Total in manifest: {summary['total_referenced']}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())

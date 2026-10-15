"""Write the S1 setup record, the frozen file every S1 gate checks (S1 plan Phase 4).

Run once, from the S1 worktree at the commit to freeze, with the run's API key in the
environment (the model list call is free):

    .venv/bin/python scripts/v2/setup_s1.py --data ../agent-shield-pilot-data/v2_s1 \
        [--prior-ledger ../agent-shield-pilot-data]

It records the commit, the sha256 of every file the run depends on (task, scorer, the v1.2
scorer it wraps, tools and payload, the frozen task set, gates, runner, cost, prices, model
args, the preregistration and the framework), the caps (D31: $180 spendable, $20 reserve, a
smoke cap per model), the ledgers that spend the same credit, the panel, the dataset hash,
every S1 sample id, each panel model's id and `created_at` from `models.list` (the version
evidence for ids without a dated suffix, E33), package versions, and the price table. It
writes `directive.txt` from the cleared TL-01 payload.

It refuses a dirty tree, a data dir inside the repo, a missing file, a panel model the key
cannot reach, a different directive already in the data dir, and an existing record.

`--amend REASON` replaces the record after a dated amendment (D43) of the checking code:
the replaced record is kept beside it as `setup.<sha12>.json` and listed in `amends`, and
the S1 gate still passes a clean log written at that sha before the amendment. It refuses
unless files in AMENDABLE (gates, scorer, cost, describe, export) are all that changed: the
task, data, payload, request policy, run grid, prices, panel, preregistration, caps,
ledgers, models and package versions must match the replaced record.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import yaml  # type: ignore[import-untyped]  # noqa: E402

from scripts.pilot._common import SETUP_NAME, PilotError, require_dir, sha256_file  # noqa: E402
from scripts.v2 import s1_panel  # noqa: E402
from tools.payloads import TL_01_POISONING_PAYLOAD  # noqa: E402

TOTAL_CAP = 180.0
RESERVE = 20.0
SMOKE_CAP_PER_MODEL = 1.0
_FIXED_FILES: tuple[str, ...] = (
    "evals/tools.py", "tools/payloads.py", "evals/tools_v12.py", "evals/tools_v2.py",
    "evals/tools_event_v2.py", "evals/data/tools_v2_tasks.jsonl",
    "evals/data/tools_v2_tasks.sha256", "approvals/gate.py", "ETHICS.md",
    "scripts/pilot/_common.py", "scripts/pilot/gates.py", "scripts/pilot/cost.py",
    "scripts/pilot/describe.py", "scripts/v2/tasks_v2.py", "scripts/v2/s1_panel.py",
    "scripts/v2/gates_s1.py", "scripts/v2/allocate_s1.py", "scripts/v2/panel_s1.py",
    "scripts/v2/blind_export.py", "scripts/v2/setup_s1.py", "pilot/s1_prices.yaml",
    "pilot/s1_inspect_model_costs.yaml", "docs/paper_v2/prereg/S1.md",
    "docs/EVAL_DESIGN_FRAMEWORK.md",
)
S1_FILES: tuple[str, ...] = _FIXED_FILES + tuple(
    sorted(str(p.relative_to(REPO)) for p in s1_panel.MODEL_ARGS_DIR.rglob("*.yaml")))

Lister = Callable[[], dict[str, str]]

# What a dated amendment may change: the code that checks, scores, prices and exports a
# run, never what the model sees, the run grid and limits (`panel_s1.py`), the caps
# (`allocate_s1.py`) or what the preregistration fixes.
AMENDABLE: frozenset[str] = frozenset({
    "evals/tools_v12.py", "evals/tools_event_v2.py", "scripts/pilot/_common.py",
    "scripts/pilot/gates.py", "scripts/pilot/cost.py", "scripts/pilot/describe.py",
    "scripts/v2/gates_s1.py", "scripts/v2/blind_export.py", "scripts/v2/setup_s1.py",
})
_SAME_ON_AMEND = ("total_cap", "reserve", "smoke_cap_per_model", "prior_ledgers", "panel",
                  "dataset_sha256", "s1_sample_ids", "models", "directive_sha256",
                  "pricing_retrieved", "inspect_ai_version", "anthropic_version", "data_dir")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                          check=True).stdout


def api_models() -> dict[str, str]:
    """{model id: created_at date} served to the key in ANTHROPIC_API_KEY (a free call)."""
    from anthropic import Anthropic

    return {m.id: str(m.created_at)[:10] for m in Anthropic().models.list(limit=100)}


def build_record(repo: Path, data: Path, *, files: tuple[str, ...] = S1_FILES,
                 lister: Lister = api_models, prior_ledgers: list[Path],
                 sample_ids: list[str], dataset_sha256: str) -> dict[str, Any]:
    """Assemble the record and write directive.txt; raise PilotError on any unsafe input."""
    repo, data = Path(repo).resolve(), require_dir(Path(data))
    if data.is_relative_to(repo):
        raise PilotError(f"data dir {data} is inside the repo {repo}")
    porcelain = _git(repo, "status", "--porcelain")
    if porcelain.strip():
        raise PilotError("git status --porcelain is not empty: " + porcelain.splitlines()[0])
    hashes: dict[str, str] = {}
    for rel in files:
        if not (repo / rel).is_file():
            raise PilotError(f"file {rel} missing in {repo}")
        hashes[rel] = sha256_file(repo / rel)
    served = lister()
    missing = [m for m in s1_panel.PANEL if m not in served]
    if missing:
        raise PilotError(f"the API key cannot reach panel models {missing}")
    directive = data / "directive.txt"
    want = TL_01_POISONING_PAYLOAD + "\n"
    if directive.exists() and directive.read_text() != want:
        raise PilotError(f"{directive} holds a different directive")
    directive.write_text(want)
    prices = yaml.safe_load(s1_panel.PRICES.read_text())
    return {
        "setup_sha": _git(repo, "rev-parse", "HEAD").strip(),
        "scorer_sha256": hashes,
        "total_cap": TOTAL_CAP,
        "reserve": RESERVE,
        "smoke_cap_per_model": SMOKE_CAP_PER_MODEL,
        "prior_ledgers": [str(Path(p).resolve()) for p in prior_ledgers],
        "panel": list(s1_panel.PANEL),
        "dataset_sha256": dataset_sha256,
        "s1_sample_ids": list(sample_ids),
        "models": {m: served[m] for m in s1_panel.PANEL},
        "directive_sha256": sha256_file(directive),
        "pricing_retrieved": str(prices.get("retrieved", "")),
        "inspect_ai_version": importlib.metadata.version("inspect_ai"),
        "anthropic_version": importlib.metadata.version("anthropic"),
        "data_dir": str(data),
        "written": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def write_record(data: Path, record: dict[str, Any]) -> Path:
    """Write DATA/setup.json once, keys sorted."""
    path = Path(data) / SETUP_NAME
    if path.exists():
        raise PilotError(f"{path} exists; the setup record is written once")
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    return path


def amend(repo: Path, data: Path, reason: str, *, files: tuple[str, ...] = S1_FILES,
          lister: Lister = api_models, sample_ids: list[str], dataset_sha256: str,
          amendable: frozenset[str] = AMENDABLE) -> dict[str, Any]:
    """Replace DATA/setup.json with a record at the current HEAD, keeping the old one beside
    it and listing it in `amends`; raise PilotError on any change outside `amendable`."""
    path = Path(data) / SETUP_NAME
    if not path.exists():
        raise PilotError(f"no setup record to amend in {data}")
    if len(reason.split()) < 4:
        raise PilotError("an amendment needs a reason of at least one sentence")
    old = json.loads(path.read_text())
    record = build_record(repo, data, files=files, lister=lister,
                          prior_ledgers=[Path(p) for p in old.get("prior_ledgers", [])],
                          sample_ids=sample_ids, dataset_sha256=dataset_sha256)
    for key in _SAME_ON_AMEND:
        if record.get(key) != old.get(key):
            raise PilotError(f"the amendment changes {key}:"
                             f" {old.get(key)!r} -> {record.get(key)!r}")
    if set(record["scorer_sha256"]) != set(old["scorer_sha256"]):
        raise PilotError("the amendment changes the hashed file set")
    changed = sorted(f for f, h in record["scorer_sha256"].items()
                     if old["scorer_sha256"][f] != h)
    if not changed or record["setup_sha"] == old["setup_sha"]:
        raise PilotError("nothing changed since the recorded freeze")
    outside = [f for f in changed if f not in amendable]
    if outside:
        raise PilotError(f"the amendment changes files outside the checking code: {outside}")
    kept = path.with_name(f"setup.{old['setup_sha'][:12]}.json")
    if kept.exists():
        raise PilotError(f"{kept} exists; a replaced record is never overwritten")
    record["amends"] = [*old.get("amends", []), {
        "setup_sha": old["setup_sha"], "file": kept.name, "sha256": sha256_file(path),
        "changed_files": changed, "reason": reason, "written": record["written"]}]
    staged = path.with_name(SETUP_NAME + ".tmp")
    staged.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    path.rename(kept)
    os.replace(staged, path)
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--prior-ledger", action="append", type=Path, default=[])
    parser.add_argument("--amend", metavar="REASON",
                        help="replace the record after a dated amendment of the checking code")
    args = parser.parse_args(argv)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("setup record: REFUSED: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        return 1
    from evals import tools_v2
    from scripts.v2 import tasks_v2

    ids, dataset = tools_v2.all_sample_ids(), tasks_v2.sha256_file(tasks_v2.DATA)
    try:
        if args.amend is not None:
            if args.prior_ledger:
                raise PilotError("--amend keeps the recorded prior ledgers; drop --prior-ledger")
            record = amend(args.repo, args.data, args.amend, sample_ids=ids,
                           dataset_sha256=dataset)
            kept = record["amends"][-1]
            print(f"setup record amended: setup_sha {record['setup_sha'][:12]}, replaced"
                  f" {kept['setup_sha'][:12]} kept as {kept['file']},"
                  f" changed {', '.join(kept['changed_files'])}")
            return 0
        record = build_record(args.repo, args.data, prior_ledgers=args.prior_ledger,
                              sample_ids=ids, dataset_sha256=dataset)
        path = write_record(args.data, record)
    except (PilotError, OSError, subprocess.CalledProcessError) as exc:
        print(f"setup record: REFUSED: {exc}", file=sys.stderr)
        return 1
    print(f"setup record written: {path} (setup_sha {record['setup_sha'][:12]},"
          f" {len(record['scorer_sha256'])} hashed files, {len(record['s1_sample_ids'])} ids)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

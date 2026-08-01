"""CLI: agent-shield-corpus — Phase 1 public-replay import / dedupe / counts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_shield.external_corpus.dedupe import dedupe_prompt_cases
from agent_shield.external_corpus.importers import (
    DEFAULT_SNAPSHOT_ROOT,
    import_phase1,
    reject_blocked_source,
)
from agent_shield.external_corpus.schemas import validate_prompt_case


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-shield-corpus",
        description=(
            "Import Phase 1 Apache-2.0 public-replay cases (doronp + Evalyze "
            "attacks.json only). No third-party code execution."
        ),
    )
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        default=DEFAULT_SNAPSHOT_ROOT,
        help="Directory containing doronp__* and Evalyze-Labs__* snapshots",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("reports/external_corpus"),
        help="Write normalized cases + dedupe reports here",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write JSONL + dedupe reports (default: print counts only)",
    )
    parser.add_argument(
        "--reject-demo",
        metavar="REPO",
        help="Demonstrate blocked-source rejection for REPO and exit 1",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.reject_demo:
        try:
            reject_blocked_source(args.reject_demo)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print("error: source was unexpectedly allowed", file=sys.stderr)
        return 1

    if not args.snapshot_root.is_dir():
        print(f"error: snapshot root missing: {args.snapshot_root}", file=sys.stderr)
        return 2

    cases = import_phase1(args.snapshot_root)
    for case in cases:
        validate_prompt_case(case.to_dict())
    retained, report = dedupe_prompt_cases(cases)

    summary = {
        "n_imported": len(cases),
        "n_after_dedupe": len(retained),
        "per_source_before": report.per_source_before,
        "per_source_after": report.per_source_after,
        "exact_duplicate_groups": report.exact_duplicate_groups,
        "cross_source_duplicate_groups": report.cross_source_duplicate_groups,
        "note": "Evalyze v3 datasets are not imported — attacks.json only",
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

    if args.write:
        out = args.out_dir
        out.mkdir(parents=True, exist_ok=True)
        jsonl = out / "prompt_cases_public_replay.jsonl"
        with jsonl.open("w", encoding="utf-8") as handle:
            for case in retained:
                handle.write(json.dumps(case.to_dict(), sort_keys=True) + "\n")
        (out / "dedupe_report.json").write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (out / "dedupe_report.md").write_text(report.to_markdown(), encoding="utf-8")
        print(f"wrote {jsonl}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

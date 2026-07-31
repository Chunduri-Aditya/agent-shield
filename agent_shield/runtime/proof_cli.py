"""CLI: agent-shield-proof — Phase 4 FP / alert / disable metrics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agent_shield.runtime.proof_metrics import run_default_proof

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_CASES = _REPO / "tests" / "fixtures" / "research_safety_cases.json"
_DEFAULT_CATALOG = _REPO / "tests" / "fixtures" / "mcp_proxy_proof_catalog.json"
_DEFAULT_SESSIONS = _REPO / "tests" / "fixtures" / "guard_proof_sessions.jsonl"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-shield-proof",
        description=(
            "Compute false positive, alert, and kill-switch disable rates for the "
            "runtime perimeter (no model calls)."
        ),
    )
    parser.add_argument("--cases", type=Path, default=_DEFAULT_CASES)
    parser.add_argument("--catalog", type=Path, default=_DEFAULT_CATALOG)
    parser.add_argument("--sessions", type=Path, default=_DEFAULT_SESSIONS)
    parser.add_argument("--mode", choices=("product", "strict"), default="product")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    for path in (args.cases, args.catalog, args.sessions):
        if not path.is_file():
            print(f"error: missing fixture {path}", file=sys.stderr)
            return 2
    metrics = run_default_proof(
        safety_cases_path=args.cases,
        catalog_path=args.catalog,
        sessions_path=args.sessions,
        mode=args.mode,
    )
    print(json.dumps(metrics.to_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

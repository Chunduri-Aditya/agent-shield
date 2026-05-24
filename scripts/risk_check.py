"""Agent Shield — pre-eval risk check (dry run).

Looks up every attack a module will exercise, runs `check_eval_risk()` against
the central registry, and prints the resulting banner. No eval is launched and
no LLM is called.

Exit code:
    0  every attack is LOW or MEDIUM (auto-approved)
    1  at least one attack is HIGH or CRITICAL — useful as a CI gate

Usage:
    python scripts/risk_check.py --module inputs
    python scripts/risk_check.py --module tools --confirm-high-risk
    python scripts/risk_check.py --all
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the repo root is importable regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from approvals.gate import CONFIRMATION_FLAG, check_eval_risk, print_risk_banner  # noqa: E402
from risk_registry import MODULE_INDEX, Severity, all_attack_ids  # noqa: E402


def _resolve_attack_ids(module: str | None, all_modules: bool) -> list[str]:
    if all_modules:
        return all_attack_ids()
    if module is None:
        raise SystemExit(
            "scripts/risk_check.py: pass --module NAME or --all "
            f"(known modules: {', '.join(sorted(MODULE_INDEX))})"
        )
    if module not in MODULE_INDEX:
        raise SystemExit(
            f"scripts/risk_check.py: unknown module {module!r}. "
            f"Known: {', '.join(sorted(MODULE_INDEX))}"
        )
    return list(MODULE_INDEX[module])


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="risk_check",
        description=(
            "Print the Agent Shield pre-eval risk banner for a module "
            "without launching any eval."
        ),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--module",
        help="Module name to check (inputs, tools, psych, memory, exfil, drift).",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Check every registered attack across every module.",
    )
    parser.add_argument(
        "--confirm-high-risk",
        action="store_true",
        help=(
            "Simulate passing the high-risk confirmation flag to the gate. "
            "The dry run still exits non-zero when severity is HIGH or "
            "CRITICAL — useful as a CI signal."
        ),
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI colour codes in the banner.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    attack_ids = _resolve_attack_ids(args.module, args.all)

    result = check_eval_risk(
        attack_ids=attack_ids,
        confirm_high_risk=args.confirm_high_risk,
        use_color=not args.no_color,
    )

    print_risk_banner(result)

    if result.block_reason and not result.allowed:
        print(f"\nblock_reason: {result.block_reason}")
        if result.ethics_missing:
            print(
                "ethics_missing: "
                f"{', '.join(result.ethics_missing)} — add these to ETHICS.md"
            )

    # Exit code semantics — useful in CI:
    #   0 if no HIGH/CRITICAL attack is in scope
    #   1 if anything HIGH or CRITICAL is in scope (whether or not allowed)
    return 0 if result.max_severity in (Severity.LOW, Severity.MEDIUM) else 1


if __name__ == "__main__":
    sys.exit(main())


# Re-export so callers that `from scripts.risk_check import CONFIRMATION_FLAG`
# don't have to reach into approvals.gate directly.
__all__ = ["CONFIRMATION_FLAG", "main"]

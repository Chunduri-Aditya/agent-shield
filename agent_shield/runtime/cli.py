"""CLI: agent-shield-guard — AdBlock-style stdin perimeter demo."""

from __future__ import annotations

import argparse
import json
import sys

from agent_shield.runtime.gate import GuardAction
from agent_shield.runtime.pipeline import GuardSession, guard_text


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-shield-guard",
        description=(
            "Screen untrusted text on stdin. Product mode alerts on injection and "
            "still proceeds; critical secrets are denied. Set AGENT_SHIELD_GUARD_OFF=1 "
            "to disable."
        ),
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        default=True,
        help="Read text from stdin (default)",
    )
    parser.add_argument(
        "--mode",
        choices=("product", "strict"),
        default="product",
        help="product=alert+proceed on HIGH; strict=research quarantine semantics",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Operator confirmed high-risk handling for this payload",
    )
    parser.add_argument(
        "--off",
        action="store_true",
        help="Engage kill switch for this invocation",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON on stdout",
    )
    parser.add_argument(
        "--source-id",
        default="stdin",
        help="Opaque source label for logs",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    text = sys.stdin.read()
    if not text.strip():
        print("error: empty stdin", file=sys.stderr)
        return 2

    session = GuardSession()
    result = guard_text(
        text,
        mode=args.mode,
        confirmed=args.confirm,
        off=args.off,
        source_id=args.source_id,
        session=session,
    )

    if args.json:
        payload = result.to_dict()
        payload["counters"] = session.counters.to_dict()
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"action: {result.action.value}")
        print(f"risk: {result.risk_level}")
        print(f"flagged_attack: {result.flagged_attack}")
        print(f"ruleset: {result.content_ruleset_version or '(kill switch)'}")
        if result.alert is not None:
            print(f"alert: {result.alert.title}")
            print(f"evidence: {result.alert.evidence}")
            print(f"remediation: {result.alert.remediation}")
        c = session.counters
        print(
            f"counters: blocked={c.denied} alerted={c.alerted} "
            f"allowed={c.allowed} kill_switch_skips={c.skipped_kill_switch}"
        )

    if result.action is GuardAction.DENY:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

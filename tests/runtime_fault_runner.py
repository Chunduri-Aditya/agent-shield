"""Subprocess runner for tests/test_runtime_failopen.py: inject one fault, call the real CLI.

Usage: runtime_fault_runner.py <fault> <cli> [cli args...]
cli is 'proxy' (mcp_proxy_cli) or 'guard' (runtime.cli).
A fault replaces the module attribute that the CLI path resolves at call time.
"""

from __future__ import annotations

import sys
from typing import NoReturn

FAULTS = ("none", "screener", "gate", "alert_build", "poison_alert", "stderr_sink", "stdout_sink")


class _Raising:
    def write(self, *_a: object, **_k: object) -> NoReturn:
        raise BrokenPipeError("injected sink failure")

    def flush(self) -> NoReturn:
        raise BrokenPipeError("injected sink failure")


def _boom(*_a: object, **_k: object) -> NoReturn:
    raise RuntimeError("injected fault")


def main() -> int:
    fault, cli, *rest = sys.argv[1:]
    import agent_shield.runtime.mcp_proxy as mp
    import agent_shield.runtime.pipeline as pipeline

    if fault not in FAULTS:
        raise SystemExit(f"unknown fault {fault}")
    patch = {
        "screener": (pipeline, "screen_text"),
        "gate": (pipeline, "decide_action"),
        "alert_build": (pipeline, "build_alert"),
        "poison_alert": (mp, "_mcp_poison_alert"),
    }.get(fault)
    if patch is not None:
        setattr(*patch, _boom)

    if cli == "proxy":
        from agent_shield.runtime.mcp_proxy_cli import main as cli_main
    else:
        from agent_shield.runtime.cli import main as cli_main
    real_out, real_err = sys.stdout, sys.stderr
    if fault == "stderr_sink":
        sys.stderr = _Raising()
    elif fault == "stdout_sink":
        sys.stdout = _Raising()
    try:
        return int(cli_main(rest))
    except Exception as exc:
        # An uncaught error exits 1 with a traceback. Report only its type to the parent,
        # so a test never has to read a traceback.
        sys.stdout, sys.stderr = real_out, real_err
        real_err.write(f"UNCAUGHT {type(exc).__name__}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

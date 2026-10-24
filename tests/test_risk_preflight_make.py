"""make -n eval-<module>: the risk check runs before the module eval.

Reads live `make -n` output, so it catches a target with no gate, a gate on the
wrong module, and a gate ordered after the eval. It does not see the real exit
code; the entrypoint smoke (`make eval-inputs MODEL=mockllm/model`) proves that.

MAKEFLAGS is dropped from the child env because a parent `make test
CONFIRM_HIGH_RISK=1` passes the variable down through it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULES = ["inputs", "tools", "psych", "memory", "exfil", "drift"]
DROPPED_ENV = {"CONFIRM_HIGH_RISK", "MAKEFLAGS", "MAKELEVEL", "MFLAGS"}


def _dry_run(module: str, confirm: bool) -> list[str]:
    env = {k: v for k, v in os.environ.items() if k not in DROPPED_ENV}
    if confirm:
        env["CONFIRM_HIGH_RISK"] = "1"
    proc = subprocess.run(
        ["make", "-n", f"eval-{module}", "MODEL=mockllm/model"],
        capture_output=True,
        text=True,
        cwd=REPO,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return proc.stdout.splitlines()


def _first(lines: list[str], needle: str) -> int:
    for i, line in enumerate(lines):
        if needle in line:
            return i
    raise AssertionError(f"no line contains {needle!r} in make -n output:\n" + "\n".join(lines))


@pytest.mark.parametrize("confirm", [False, True])
@pytest.mark.parametrize("module", MODULES)
def test_risk_check_precedes_module_eval(module: str, confirm: bool) -> None:
    lines = _dry_run(module, confirm)
    gate = _first(lines, f"scripts/risk_check.py --module {module} --enforce")
    run = _first(lines, f"inspect eval evals/{module}.py")
    assert gate < run, "\n".join(lines)
    assert ("--confirm-high-risk" in lines[gate]) is confirm, lines[gate]

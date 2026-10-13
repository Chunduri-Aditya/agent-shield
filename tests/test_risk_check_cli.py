"""scripts/risk_check.py --enforce: exit 0 only when the gate allows the run.

The default exit code is a CI signal (1 whenever HIGH or CRITICAL is in scope,
allowed or not), so a Makefile prerequisite needs --enforce. --ethics-file lets
a test prove the deny half against a scratch ETHICS.md with an id removed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "risk_check.py"
ETHICS = REPO / "ETHICS.md"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--no-color", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )


def test_enforce_allows_tools_with_confirmation_and_cleared_ethics() -> None:
    proc = _run("--module", "tools", "--enforce", "--confirm-high-risk")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "block_reason" not in proc.stdout


def test_enforce_denies_tools_without_confirmation() -> None:
    proc = _run("--module", "tools", "--enforce")
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "block_reason" in proc.stdout


def test_enforce_denies_when_ethics_lacks_the_id(tmp_path: Path) -> None:
    text = ETHICS.read_text()
    assert "TL-01" in text
    scratch = tmp_path / "ETHICS.md"
    scratch.write_text(text.replace("TL-01", "TL-XX"))
    proc = _run(
        "--module", "tools", "--enforce", "--confirm-high-risk",
        "--ethics-file", str(scratch),
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "ethics_missing: TL-01" in proc.stdout


def test_default_exit_is_unchanged_ci_signal() -> None:
    proc = _run("--module", "tools", "--confirm-high-risk")
    assert proc.returncode == 1, proc.stdout + proc.stderr

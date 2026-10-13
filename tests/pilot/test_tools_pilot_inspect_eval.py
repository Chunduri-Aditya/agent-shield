"""tools_pilot.py must load under the `inspect` console script with no help from the caller.

Inspect loads a task file through SourceFileLoader inside chdir_python(file.parent), which
appends evals/ to sys.path and never adds the repo root, and the console script puts
.venv/bin, not the cwd, at sys.path[0]. So `from evals.tools import ...` resolves only when
the task file inserts the repo root itself, the guard evals/inputs.py and evals/tools.py
carry. pytest cannot see the guard go missing (tests/conftest.py inserts the root) and
`inspect list` only parses, so this test runs the real command in a subprocess: the
`inspect` binary beside sys.executable (`python -m` would put the cwd on sys.path and hide
the bug), cwd at the repo root, PYTHONPATH removed.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from inspect_ai.log import read_eval_log

REPO = Path(__file__).resolve().parents[2]
TASK = "evals/tools_pilot.py@tools_pilot"
PILOT_IDS = {f"TL-01-u{i:02d}" for i in range(1, 11)}


def test_inspect_eval_loads_tools_pilot_without_pythonpath(tmp_path: Path) -> None:
    inspect_bin = Path(sys.executable).with_name("inspect")
    assert inspect_bin.exists(), f"{inspect_bin} missing: the test needs the console script"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    done = subprocess.run(
        [
            str(inspect_bin), "eval", TASK, "--model", "mockllm/model", "--limit", "1",
            "--log-dir", str(tmp_path), "--display", "plain",
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, f"exit {done.returncode}\n{done.stdout}\n{done.stderr}"
    logs = sorted(tmp_path.glob("*.eval"))
    assert len(logs) == 1, f"expected exactly one .eval log, found {logs}"
    log = read_eval_log(str(logs[0]))
    ids = {str(s.id) for s in log.samples or []}
    assert ids, "log holds no samples"
    assert ids <= PILOT_IDS, f"unexpected sample ids {ids - PILOT_IDS}"

"""agent_shield/_python_floor.py: an old Python gets one clear line, not a traceback.

On Python 3.9 the package used to stop at agent_shield/research.py:23
(``from datetime import UTC``, new in 3.11) with an ImportError traceback.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from agent_shield import _python_floor

REPO = Path(__file__).resolve().parent.parent
INIT = REPO / "agent_shield" / "__init__.py"
FLOOR = REPO / "agent_shield" / "_python_floor.py"


def test_an_old_python_gets_one_line_naming_both_versions() -> None:
    with pytest.raises(SystemExit) as exc:
        _python_floor.check((3, 9, 6))
    message = str(exc.value.code)
    assert "Python 3.11 or newer" in message and "Python 3.9.6" in message
    assert "https://www.python.org/downloads/" in message
    assert "\n" not in message


@pytest.mark.parametrize("version", [(3, 11, 0), (3, 12, 4), (3, 14, 7), (4, 0, 0)])
def test_a_supported_python_passes(version: tuple[int, int, int]) -> None:
    _python_floor.check(version)  # returns without raising


def test_the_floor_matches_requires_python() -> None:
    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["requires-python"] == ">=" + ".".join(map(str, _python_floor.MIN_PYTHON))


def test_the_package_runs_the_floor_before_any_other_import() -> None:
    tree = ast.parse(INIT.read_text(encoding="utf-8"))
    imports = [node for node in tree.body if isinstance(node, ast.Import | ast.ImportFrom)]
    first = imports[0]
    assert isinstance(first, ast.ImportFrom) and first.module == "agent_shield"
    assert [alias.name for alias in first.names] == ["_python_floor"]


def test_the_floor_and_the_package_init_parse_on_python_3_9() -> None:
    for path in (FLOOR, INIT):
        ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))


def _old_python() -> str | None:
    for name in ("python3.9", "python3.10", "/usr/bin/python3"):
        exe = shutil.which(name)
        if exe is None:
            continue
        out = subprocess.run(
            [exe, "-c", "import sys; print(sys.version_info[:2] < (3, 11))"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if out.stdout.strip() == "True":
            return exe
    return None


def test_the_demo_on_an_old_python_prints_the_line_and_no_traceback() -> None:
    exe = _old_python()
    if exe is None:
        pytest.skip("no Python older than 3.11 on this machine")
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", "")}
    out = subprocess.run(
        [exe, "-m", "agent_shield.runtime.mcp_proxy_cli", "badge"],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=60, check=False,
    )
    assert out.returncode == 1
    assert "Traceback" not in out.stderr
    lines = out.stderr.strip().splitlines()
    assert len(lines) == 1 and lines[0].startswith("Agent Shield needs Python 3.11 or newer")
    assert sys.version_info >= (3, 11)  # the suite itself runs on the supported floor

"""inspect_evals installs from one fixed PyPI release, never from a moving checkout.

An unpinned `actions/checkout` of inspect_evals took whatever its default branch held on the
day CI ran, so a green CI run could test code no reader can check out again (v1.2 agent plan,
P1). The pin now lives in pyproject.toml as an exact PyPI version, which `uv sync --locked`
installs in CI and locally alike. 0.9.0 is the release of the commit CI used to check out
(7d4dd75, v0.9.0 plus one test only line). The expected version comes from that mapping, not
from the files under test.
"""

import tomllib
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

INSPECT_EVALS_REPOSITORY = "UKGovernmentBEIS/inspect_evals"
INSPECT_EVALS_REQUIREMENT = "inspect-evals[agentdojo]==0.9.0"


def _steps(repo_root: Path) -> list[dict[str, Any]]:
    workflow = yaml.safe_load((repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


def test_ci_does_not_check_out_inspect_evals(repo_root: Path) -> None:
    checkouts = [
        step
        for step in _steps(repo_root)
        if step.get("with", {}).get("repository") == INSPECT_EVALS_REPOSITORY
    ]
    assert checkouts == [], f"CI still checks out inspect_evals: {checkouts}"


def test_inspect_evals_pinned_to_one_pypi_release(repo_root: Path) -> None:
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    deps = [d for d in pyproject["project"]["dependencies"] if d.startswith("inspect-evals")]
    assert deps == [INSPECT_EVALS_REQUIREMENT], deps
    sources = pyproject.get("tool", {}).get("uv", {}).get("sources", {})
    assert "inspect-evals" not in sources, f"inspect-evals has a non PyPI source: {sources}"

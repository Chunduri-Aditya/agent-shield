"""CI checks out its outside dependencies at fixed commits (v1.2 agent plan, P1).

An unpinned `actions/checkout` of inspect_evals takes whatever its default branch holds on the
day CI runs, so a green CI run could test code no reader can check out again. The expected
commit comes from the plan, not from the workflow under test.
"""

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

INSPECT_EVALS_REPOSITORY = "UKGovernmentBEIS/inspect_evals"
INSPECT_EVALS_REF = "7d4dd75e4f80c9cf8a83664a04fc1797ce2cb72b"


def _steps(repo_root: Path) -> list[dict[str, Any]]:
    workflow = yaml.safe_load((repo_root / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


def test_inspect_evals_checkout_pinned(repo_root: Path) -> None:
    checkouts = [
        step
        for step in _steps(repo_root)
        if str(step.get("uses", "")).startswith("actions/checkout@")
        and step.get("with", {}).get("repository") == INSPECT_EVALS_REPOSITORY
    ]
    assert len(checkouts) == 1, f"expected one inspect_evals checkout, found {len(checkouts)}"
    assert checkouts[0]["with"].get("ref") == INSPECT_EVALS_REF, (
        f"inspect_evals checkout ref is {checkouts[0]['with'].get('ref')!r}, "
        f"expected the full commit {INSPECT_EVALS_REF}"
    )

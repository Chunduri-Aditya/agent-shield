"""The S1 frozen files stay byte identical, and ruff cannot rewrite them.

On 2026-11-26 a formatter run over scripts/ rewrote S1 frozen files. The frozen set is every
path in S1_FILES (scripts/v2/setup_s1.py) plus the two files that amendment A1 freezes (see
tests/pilot/test_s1_amendments.py). PINNED holds the sha256 of each file as committed, typed
in as a literal so that the test never computes its own expectation. A change to a frozen file
needs a new dated amendment, and then a new value here.
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from scripts.v2.setup_s1 import S1_FILES

REPO = Path(__file__).resolve().parents[1]

A1_FILES = ("docs/paper_v2/prereg/S1_CODEBOOK.md", "scripts/v2/label.py")

PINNED: dict[str, str] = {
    "ETHICS.md": "5c3407e2f688712d445c3de196d28b7243f6e55139f0c1a311529d67b7243bfb",
    "approvals/gate.py": "0e3b67d6945051cbd45830b7a59fb184d186532a4a56867e422a05824b772a76",
    "docs/EVAL_DESIGN_FRAMEWORK.md": "31f52ca213b98ac0cbabe498bb5f0cc7a1ab3c80239b15ced2900144ce90f7e1",
    "docs/paper_v2/prereg/S1.md": "4105f356bd3916d43ad15975a640b49b46eceda52dbb01dcdb66dbec0f41bc3d",
    "docs/paper_v2/prereg/S1_CODEBOOK.md": "28c3e689be6a68dd131a5c2a128b623204c4ab68e3f5095711de89c994b8684b",
    "evals/data/tools_v2_tasks.jsonl": "5e4e10dca8547515554341565d9dbee0eec99363b7fafbac55a0003b08c5b767",
    "evals/data/tools_v2_tasks.sha256": "d67c5fe735a595058c7661374c362dde2d6234888a8e0a331df55b109d66b170",
    "evals/tools.py": "dda7dc84ce7c3aa87b6306901cb181b456d67ea7fb12e1dab5d4392ee7f3c944",
    "evals/tools_event_v2.py": "d1f146fc21a4c1a4f1aa0ccc6602c59b2f2ba4ba9dd7c2bdb05d7c1e7df29d9b",
    "evals/tools_v12.py": "ba9a4c454ac462804d726e821918cd1ddee96b4b2eba00b72de4582c2291b67f",
    "evals/tools_v2.py": "be7f4a85e8864720b7a32c38e81ab58522e5405d55e9bc202c595410a99d3bdc",
    "pilot/s1_inspect_model_costs.yaml": "1d755b85eb3cc653289dfdd1b14401542ef51cb28d7b5adde9f6fa3cd143eebb",
    "pilot/s1_model_args/cells/haiku55_off.yaml": "d6783058ca23c67657e83b6b17313626ac74923d4c2863d6ccef5eee5582dba5",
    "pilot/s1_model_args/cells/opus46_on.yaml": "6cbbd819fc601c3aa019f3fdf15b5aecb6da1e9f598be6c08f6e0cc0933fc7ab",
    "pilot/s1_model_args/cells/sonnet46_on.yaml": "165fb058d149aecb15ac51fa6d913d37864d17aaad7cb25248189c229a7e3739",
    "pilot/s1_model_args/cells/sonnet5_off.yaml": "3ed0e3a2d1487e06433031633cd7fffa94fafe197f4785f6c43251cf51f6a5d8",
    "pilot/s1_model_args/claude-fable-5-1.yaml": "7a002b4e0f66a35c05ec20a218d6001af4463aab8ecfb632e0d67415fde1aa9a",
    "pilot/s1_model_args/claude-haiku-5-5.yaml": "cc24988fff985b93e483b9ba4b468dc13da0dce5c96f7f53194754713fcc88ec",
    "pilot/s1_model_args/claude-opus-5-5.yaml": "97d62d876010561f9982010e7145dfb01f3dc559a95e31002afd473abf0eb50d",
    "pilot/s1_model_args/claude-opus-5.yaml": "74d12b7bc462469d71ec47cd76a025f40b4ed42159a695bd5d6b9d35de54d829",
    "pilot/s1_model_args/claude-sonnet-5-5.yaml": "b3e3ca148a7a05d79d7f5ecca4e8a8537f349aa260e21b6dd59dd67ccc25e1b2",
    "pilot/s1_model_args/claude-sonnet-5.yaml": "792a7ee1a5b7379a6e2b3325961d91df53e088f24002ab5a0f8232281b545275",
    "pilot/s1_prices.yaml": "06566b441b9e033aafc04f6d146ec1ec455820586d3c78cac5c92e74a8edecd2",
    "scripts/pilot/_common.py": "06369d6df43edc581cad58dc240f22298a245e393222bc1471083762cdd19ef8",
    "scripts/pilot/cost.py": "2b64fa5805f12b77632c2028a59ded65b9a312b1acbe46be416f52d9615449f0",
    "scripts/pilot/describe.py": "be5983b6cf8e4c06765b5ddd7534bfbf9af28642092aecca8f301905567d10d6",
    "scripts/pilot/gates.py": "00f701c51ba88b5a97b15ca58d50bed6ef7d2301a6e829ed063d1f9bfd39f119",
    "scripts/v2/allocate_s1.py": "2d5adc913778ad8daa973c1196acff805b669bcafd965e00f79770172d43aa38",
    "scripts/v2/blind_export.py": "62f93654740021ad56038519d1d528c5dab512c687a1070e3026127c296270c7",
    "scripts/v2/gates_s1.py": "48046840c8ce686a287efb9a34d2f3fe9e14b9d881081ed87196f4e5f3e0709f",
    "scripts/v2/label.py": "5f40ef2f2c204804e7a4f4db25593e50c4e544a27e0b1bd6e48048fa56ff2842",
    "scripts/v2/panel_s1.py": "27ea1835524e1721a0900582a80d0ca90bc3ac9c884faad73912189ad424736e",
    "scripts/v2/s1_panel.py": "9b85fb2de314ab047ed747884ee564be28b26bb02eb5e69575f9d08326e826cc",
    "scripts/v2/setup_s1.py": "59271e1ec81613802286ac52373fb230bacd8885520095f46c91880357b2ceeb",
    "scripts/v2/tasks_v2.py": "b7976dd3e9bc54d26134889bdff0b4414f142126c93a41b0159b7c2d55edfa21",
    "tools/payloads.py": "1a349886350d4c1ad2cc9b71bea34a78ed241363314e9e6e04ef6292bfa47a4c",
}


def _sha256(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def _ruff_excludes() -> tuple[list[str], bool]:
    ruff = tomllib.loads((REPO / "pyproject.toml").read_text())["tool"]["ruff"]
    return ruff["extend-exclude"], ruff.get("force-exclude", False) is True


def test_the_pinned_set_is_the_frozen_set():
    assert set(PINNED) == set(S1_FILES) | set(A1_FILES)


@pytest.mark.parametrize("rel", sorted(PINNED))
def test_a_frozen_file_is_byte_identical_to_its_pin(rel: str):
    assert _sha256(rel) == PINNED[rel], f"{rel} changed. S1 frozen files are never edited."


def test_ruff_is_told_to_skip_every_frozen_python_file_even_when_named():
    excludes, forced = _ruff_excludes()
    missing = [rel for rel in PINNED if rel.endswith(".py") and rel not in excludes]
    assert not missing, f"not in [tool.ruff] extend-exclude: {missing}"
    assert forced, "[tool.ruff] force-exclude must be true"


def test_ruff_leaves_a_frozen_file_alone_when_the_path_is_named():
    if importlib.util.find_spec("ruff") is None:
        pytest.skip("ruff is not installed in this environment")
    rel = "scripts/v2/label.py"
    before = _sha256(rel)
    runs = {
        "format": [sys.executable, "-m", "ruff", "format", "--check", rel],
        "check": [sys.executable, "-m", "ruff", "check", rel],
    }
    for name, argv in runs.items():
        done = subprocess.run(
            argv, cwd=REPO, capture_output=True, text=True, timeout=60, check=False
        )
        out = done.stdout + done.stderr
        assert done.returncode == 0, f"ruff {name} exit {done.returncode}: {out}"
        assert "Would reformat" not in out, out
        assert rel not in out, f"ruff {name} named the frozen file: {out}"
        assert "No Python files found" in out, f"ruff {name} did not skip the file: {out}"
        assert _sha256(rel) == before == PINNED[rel]

"""S1 amendment A1 (`docs/paper_v2/prereg/S1_AMENDMENTS.md`): the hashes it quotes stay true.

The codebook and the labelling tool are frozen by A1. A change to either without a new dated
amendment turns this test red. `prereg/S1.md` stays byte identical to its frozen record.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
AMENDMENTS = REPO / "docs" / "paper_v2" / "prereg" / "S1_AMENDMENTS.md"
FROZEN_SETUP = "ada762d"  # the S1 setup_sha amendment A1 replaces


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quoted(text: str) -> dict[str, str]:
    """`| `path` | `sha256` |` rows of the hash table."""
    return dict(re.findall(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|$", text, re.MULTILINE))


def test_the_quoted_hashes_match_the_files() -> None:
    rows = quoted(AMENDMENTS.read_text())
    assert set(rows) == {"docs/paper_v2/prereg/S1_CODEBOOK.md", "scripts/v2/label.py"}
    for rel, digest in rows.items():
        assert sha(REPO / rel) == digest, f"{rel} changed after A1; add a dated amendment"


def test_the_preregistration_stays_byte_identical() -> None:
    text = AMENDMENTS.read_text()
    digest = sha(REPO / "docs" / "paper_v2" / "prereg" / "S1.md")
    assert f"sha256 `{digest}`" in text
    frozen = subprocess.run(["git", "-C", str(REPO), "show",
                             f"{FROZEN_SETUP}:docs/paper_v2/prereg/S1.md"],
                            capture_output=True, check=False)
    if frozen.returncode != 0:
        pytest.skip(f"{FROZEN_SETUP} is not in this clone")
    assert hashlib.sha256(frozen.stdout).hexdigest() == digest

import os
import sys
from pathlib import Path

# Before any test module imports huggingface_hub: the mlx provider test asserts the hub was
# never online, and tests/test_inputs_rows.py imports inspect_ai (which imports the hub) first.
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repo root. Used by artifact-presence tests."""
    return REPO_ROOT

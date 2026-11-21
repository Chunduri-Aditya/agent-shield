"""Stop with one clear line on a Python older than the supported floor.

``agent_shield/__init__.py`` imports this module first, so the check runs before any
import that needs 3.11 (``datetime.UTC`` in ``agent_shield/research.py`` is the first).
Keep this file parseable on Python 3.9: ``tests/test_python_floor.py`` checks that.
"""

import sys

MIN_PYTHON = (3, 11)


def check(version_info: tuple[int, ...]) -> None:
    """Raise SystemExit with one line when ``version_info`` is below ``MIN_PYTHON``."""
    if tuple(version_info[:2]) < MIN_PYTHON:
        found = ".".join(str(part) for part in version_info[:3])
        raise SystemExit(
            f"Agent Shield needs Python 3.11 or newer, and this is Python {found}. "
            "Install 3.11 or newer from https://www.python.org/downloads/ "
            "(or run `uv python install 3.11`), then run the command again with it."
        )


check(sys.version_info[:3])

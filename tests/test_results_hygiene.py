"""results/: no tracked file names a path on the machine that made it.

A run writes absolute paths (the event log, the log directory). A result file is public, so
a copy in results/ holds paths relative to its run directory and never the name of the OS
user who ran it.
"""

from __future__ import annotations

import getpass
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "results"
ABSOLUTE = re.compile(
    r"/Users/|/home/[A-Za-z0-9_]|/private/(?:tmp|var)|/var/folders/|[A-Za-z]:\\+Users"
)


def _files() -> list[Path]:
    """The tracked files under results/, or every file there when git cannot list them."""
    listed = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z", "--", "results"],
        capture_output=True,
        text=True,
        check=False,
    )
    names = [name for name in listed.stdout.split("\0") if name]
    if listed.returncode == 0 and names:
        return [REPO / name for name in names]
    return [path for path in RESULTS.rglob("*") if path.is_file()]


def _hits(text: str, user: str) -> list[str]:
    """Lines that hold an absolute user path, or the OS user name as a path part or a login.

    The bare name is not searched for: a user called root would match the word root.
    """
    name = re.escape(user)
    login = re.compile(rf"[/\\]{name}(?:[/\\\"'\s]|$)|(?<![A-Za-z0-9]){name}@", re.I)
    return [line for line in text.splitlines() if ABSOLUTE.search(line) or login.search(line)]


def test_the_check_sees_a_user_path_and_a_login_and_passes_plain_text() -> None:
    assert _hits('"events": "/Users/someone/run/logs/x.jsonl"', "someone")
    assert _hits("log dir /home/dev/run", "dev")
    assert _hits("written by dev@host", "dev")
    assert _hits("C:\\Users\\dev\\run", "dev")
    assert not _hits('"events": "logs/security_events.jsonl"', "dev")
    assert not _hits("the repo root holds the ledger", "root")


def test_no_file_under_results_holds_a_local_user_path_or_the_os_user_name() -> None:
    files = _files()
    assert files
    user = getpass.getuser()
    found = [
        f"{path.relative_to(REPO)}: {line.strip()[:90]}"
        for path in files
        for line in _hits(path.read_bytes().decode("utf-8", "replace"), user)
    ]
    assert not found, "\n" + "\n".join(found)

"""Practice round for the S1 labelling form (`scripts/v2/practice.py`).

The items are the codebook's own edge cases (`docs/paper_v2/prereg/S1_CODEBOOK.md`, lines 73
to 91). Each item's expected answers must derive, through `label.derive`, the codebook's
label and flag. A full run writes no file, never opens the pilot data folder, and leaves
`label.py` byte identical.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from scripts.v2 import label as lb
from scripts.v2 import practice as pr

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "scripts" / "v2" / "practice.py"
LABEL = REPO / "scripts" / "v2" / "label.py"
ITEMS = REPO / "scripts" / "v2" / "practice_items.json"


def typed(answers: dict[str, Any], blocks: int) -> list[str]:
    """The keystrokes a labeller types to give `answers` on the form."""
    out: list[str] = []
    if blocks:
        out.append(" ".join(str(b) for b in answers["q1"]) or "none")
    if answers["q1"]:
        out.append(str(answers["q2"]))
    elif blocks:
        out.append("y" if answers["q3"] == "yes" else "n")
    if not isinstance(answers["q2"], int):
        out.append("n" if answers["q4"] == "no" else answers["q4"])
    return out


def script() -> list[str]:
    """Every item's expected keystrokes, each followed by Enter to go on."""
    keys: list[str] = []
    for item in pr.load_items():
        keys += [*typed(item["answers"], item["blocks"]), ""]
    return keys


def test_nine_items_from_the_codebook() -> None:
    items = pr.load_items()
    assert len(items) == 9
    assert len({i["id"] for i in items}) == 9
    for item in items:
        assert item["view"].startswith("USER: ")
        assert item["view"].endswith("[END OF TRANSCRIPT]")
        assert item["view"].count("[T") == item["blocks"]


def test_expected_answers_derive_the_codebook_label() -> None:
    for item in pr.load_items():
        label, first, reason, flag_a = lb.derive(item["answers"])
        want = item["codebook"]
        assert (label, first, reason, flag_a) == (
            want["label"], want["first_block"], want["reason"], want["flag_a"]), item["id"]


def test_codebook_labels_match_the_edge_cases() -> None:
    got = [(i["codebook"]["label"], i["codebook"]["reason"], i["codebook"]["flag_a"])
           for i in pr.load_items()]
    assert got == [("D", None, True), ("D", None, True), ("U", "vague", True),
                   ("D", None, True), ("N", None, True), ("N", None, False),
                   ("N", None, False), ("U", "vague", True), ("U", "truncated", False)]


def test_run_scores_every_match_and_shows_feedback() -> None:
    keys = iter(script())
    said: list[str] = []
    assert pr.run(pr.load_items(), ask=lambda _: next(keys), say=said.append) == 9
    text = "\n".join(said)
    assert text.count("Codebook:") == 9
    assert "9 of 9" in text


def test_wrong_answer_is_marked_different() -> None:
    item = pr.load_items()[0]  # codebook D T1, A
    keys = iter(["none", "n", "n", ""])
    said: list[str] = []
    assert pr.run([item], ask=lambda _: next(keys), say=said.append) == 0
    assert any("Different" in s for s in said)


def test_q_stops_without_error() -> None:
    keys = iter(["q"])
    said: list[str] = []
    assert pr.run(pr.load_items(), ask=lambda _: next(keys), say=said.append) == 0
    assert any("Stopped" in s for s in said)


AUDIT = """
import os, runpy, sys
opened = []
def hook(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes)):
        opened.append(str(args[0]))
sys.addaudithook(hook)
sys.argv = [sys.argv[1]]
sys.path.insert(0, os.path.dirname(sys.argv[0]))  # as `python3 practice.py` does
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
except SystemExit:
    pass
sys.stderr.write("\\n".join(opened))
"""


def test_full_run_writes_nothing_and_never_opens_the_data(tmp_path: Path) -> None:
    before = sorted(os.listdir(tmp_path))
    done = subprocess.run([sys.executable, "-c", AUDIT, str(TOOL)], cwd=tmp_path,
                          input="\n".join(script()) + "\n", capture_output=True, text=True,
                          timeout=60, check=True)
    assert "9 of 9" in done.stdout
    assert sorted(os.listdir(tmp_path)) == before
    opened = done.stderr.splitlines()
    assert opened, "the audit hook saw no open"
    assert not [p for p in opened if "agent-shield-pilot-data" in p]
    assert "agent-shield-pilot-data" not in TOOL.read_text()
    assert "agent-shield-pilot-data" not in ITEMS.read_text()


def test_label_py_is_unchanged() -> None:
    assert hashlib.sha256(LABEL.read_bytes()).hexdigest().startswith("5f40ef2f")


def test_items_file_is_valid_json() -> None:
    assert isinstance(json.loads(ITEMS.read_text(encoding="utf-8")), list)

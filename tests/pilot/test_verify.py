"""The verification tool for D54 (`scripts/v2/verify.py`): agree, override, resume, flush.

Expected labels come from the codebook form: Q1 none, Q3 no, Q4 no gives `N` without `A`;
an agreed item keeps the judge's answers and label.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from scripts.v2 import label as lb
from scripts.v2 import verify as vf

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "scripts" / "v2" / "verify.py"
D1 = {"answers": {"q1": [1], "q2": 1, "q3": None, "q4": None}, "label": "D",
      "first_block": 1, "reason": None, "flag_a": True}


def view(word: str) -> str:
    return f"USER: q\n\n[T1] {word}\n\n[END OF TRANSCRIPT]"


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    d = tmp_path / "dev"
    d.mkdir()
    rows = [{"item": "i1", "view": view("alpha"), "blocks": 1, "judge": D1},
            {"item": "i2", "view": view("beta"), "blocks": 1, "judge": D1},
            {"item": "i3", "view": view("gamma"), "blocks": 1, "judge": None}]
    (d / vf.TODO).write_text("".join(json.dumps(r) + "\n" for r in rows))
    return d


def scripted(answers: list[str]) -> Callable[[str], str]:
    it: Iterator[str] = iter(answers)

    def ask(_: str) -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None
    return ask


def labels(folder: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in (folder / vf.DONE).read_text().splitlines() if x.strip()]


def make(folder: Path, answers: list[str], shown: list[str] | None = None) -> vf.Verifier:
    return vf.Verifier(folder, ask=scripted(answers), say=(shown.append if shown is not None
                                                           else lambda _: None),
                       now=lambda: datetime(2026, 10, 16, 8, 0, tzinfo=UTC))


def test_enter_agrees_and_override_answers_the_form(folder: Path) -> None:
    # i1: agree; i2: override with Q1 none, Q3 n, Q4 n; i3: void judge goes to the form
    made = make(folder, ["", "", "o", "none", "n", "n", "", "1", "1", ""]).run()
    assert made == 3
    a, b, c = labels(folder)
    assert (a["decision"], a["label"], a["first_block"], a["agrees_with_judge"]) == (
        "agree", "D", 1, True)
    assert a["answers"] == D1["answers"] and a["judge"] == D1
    assert (b["decision"], b["label"], b["flag_a"], b["agrees_with_judge"]) == (
        "override", "N", False, False)
    assert (c["decision"], c["label"], c["first_block"], c["judge"]) == ("override", "D", 1, None)


def test_each_verification_is_on_disk_before_the_next_item_shows(folder: Path) -> None:
    seen: list[int] = []

    def say(text: str) -> None:
        if "[T1] beta" in text:
            seen.append(len(labels(folder)))

    vf.Verifier(folder, ask=scripted(["", "", "q"]), say=say).run()
    assert seen == [1]


def test_q_stops_without_saving_and_a_restart_resumes(folder: Path) -> None:
    assert make(folder, ["", "", "q"]).run() == 1
    shown: list[str] = []
    make(folder, ["q"], shown).run()
    assert any("[T1] beta" in s for s in shown) and not any("[T1] alpha" in s for s in shown)
    assert [r["item"] for r in labels(folder)] == ["i1"]


def test_redo_asks_again_and_saves_once(folder: Path) -> None:
    make(folder, ["", "r", "o", "none", "y", "n", "", "q"]).run()
    [rec] = labels(folder)
    assert (rec["decision"], rec["label"], rec["flag_a"]) == ("override", "N", True)


def test_a_folder_holding_the_key_is_refused(folder: Path) -> None:
    (folder / "key.json").write_text("{}")
    with pytest.raises(lb.LabelError, match="key"):
        make(folder, []).run()


def test_the_tool_runs_as_a_script_from_its_own_folder(folder: Path) -> None:
    make(folder, ["", ""]).run()
    out = subprocess.run([sys.executable, str(TOOL), str(folder), "--pace"],
                         capture_output=True, text=True, check=False)
    assert out.returncode == 0 and "over 1 verifications" in out.stdout

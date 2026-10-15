"""S1 labels build batch 1 step 2: the offline labelling tool (`scripts/v2/label.py`).

Every expected value comes from the codebook (`docs/paper_v2/prereg/S1_CODEBOOK.md`) and D44,
D45, D48: the four question form and its skip logic, a label on disk before the next item, a
resume at the first unlabelled item, a 50 minute time box, relabel items only 14 days after
their source label, and a tool that never opens the key.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from scripts.v2 import blind_export as bx
from scripts.v2 import label as lb

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "scripts" / "v2" / "label.py"
T0 = datetime(2026, 10, 16, 9, 0, tzinfo=UTC)
NO = ["none", "n", "n", ""]  # Q1 none, Q3 no, Q4 no, Enter saves: label N


def row(item: str, blocks: int = 2) -> dict[str, Any]:
    body = "\n\n".join(f"[T{i}] Block {i}." for i in range(1, blocks + 1))
    return {"item": item, "view": f"USER: Read the file.\n\n{body}\n\n[END OF TRANSCRIPT]"
            if blocks else "USER: Read the file.\n\n[END OF TRANSCRIPT]", "blocks": blocks}


def folder(tmp: Path, n: int = 3, relabel: list[tuple[str, str]] | None = None,
           blocks: int = 2) -> Path:
    d = tmp / "labels"
    d.mkdir(parents=True)
    (d / lb.QUEUE).write_text("".join(json.dumps(row(f"q{i}", blocks)) + "\n"
                                      for i in range(n)))
    (d / lb.RELABEL).write_text("".join(
        json.dumps({**row(r), "source": s}) + "\n" for r, s in (relabel or [])))
    return d


def records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


class Script:
    """Feeds answers and records each prompt; `tick` seconds pass on every answer."""

    def __init__(self, answers: list[str], tick: float = 1.0) -> None:
        self.answers: Iterator[str] = iter(answers)
        self.prompts: list[str] = []
        self.t = 0.0
        self.tick = tick
        self.before: Callable[[str], None] | None = None

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.before is not None:
            self.before(prompt)
        self.t += self.tick
        try:
            return next(self.answers)
        except StopIteration:
            raise EOFError from None

    def clock(self) -> float:
        return self.t


def session(d: Path, script: Script, *, now: datetime = T0, **kw: Any) -> lb.Labeller:
    return lb.Labeller(d, ask=script.ask, say=lambda _: None, now=lambda: now,
                       clock=script.clock, **kw)


# ---- the form (codebook, D51) ----

@pytest.mark.parametrize(("answers", "asked", "want"), [
    (["2 1", "T2", ""], "12", ("D", 2, None, True)),
    (["1", "none", "vague", ""], "124", ("U", None, "vague", True)),
    (["1", "none", "n", ""], "124", ("N", None, None, True)),
    (["none", "y", "n", ""], "134", ("N", None, None, True)),
    (["none", "n", "truncated", ""], "134", ("U", None, "truncated", False)),
    (["n", "n", "o", ""], "134", ("U", None, "other", False)),
])
def test_form_skip_logic_and_derived_label(tmp_path: Path, answers: list[str], asked: str,
                                           want: tuple[Any, ...]) -> None:
    d = folder(tmp_path, n=1)
    s = Script(answers)
    assert session(d, s).run() == 1
    (rec,) = records(d / lb.LABELS)
    assert (rec["label"], rec["first_block"], rec["reason"], rec["flag_a"]) == want
    numbers = "".join(p.lstrip()[0] for p in s.prompts if p.lstrip()[:1] in "1234")
    assert numbers == asked


def test_invalid_answers_are_asked_again(tmp_path: Path) -> None:
    d = folder(tmp_path, n=1)
    s = Script(["7", "x", "1", "2", "1", "maybe", "n", ""])
    session(d, s).run()
    (rec,) = records(d / lb.LABELS)
    assert rec["answers"] == {"q1": [1], "q2": 1, "q3": None, "q4": None}
    assert rec["label"] == "D"


def test_a_transcript_with_no_text_block_asks_only_question_four(tmp_path: Path) -> None:
    d = folder(tmp_path, n=1, blocks=0)
    s = Script(["truncated", ""])
    session(d, s).run()
    (rec,) = records(d / lb.LABELS)
    assert (rec["label"], rec["reason"], rec["flag_a"]) == ("U", "truncated", False)
    assert rec["answers"] == {"q1": [], "q2": None, "q3": "no", "q4": "truncated"}


def test_redo_asks_the_form_again_and_saves_once(tmp_path: Path) -> None:
    d = folder(tmp_path, n=1)
    session(d, Script(["1", "1", "r", *NO])).run()
    (rec,) = records(d / lb.LABELS)
    assert rec["label"] == "N"


def test_quit_saves_nothing_for_the_item_on_screen(tmp_path: Path) -> None:
    d = folder(tmp_path, n=2)
    assert session(d, Script([*NO, "1", "q"])).run() == 1
    assert [r["item"] for r in records(d / lb.LABELS)] == ["q0"]


def test_record_carries_its_provenance(tmp_path: Path) -> None:
    d = folder(tmp_path, n=1)
    session(d, Script(NO, tick=7.0)).run()
    (rec,) = records(d / lb.LABELS)
    assert set(rec) == {"item", "set", "label", "first_block", "reason", "flag_a", "answers",
                        "seconds", "labelled_at", "session", "tool_sha256"}
    assert (rec["set"], rec["seconds"], rec["labelled_at"]) == ("queue", 28.0, T0.isoformat())
    assert len(rec["tool_sha256"]) == 64


# ---- durability and resume (D45) ----

def test_each_label_is_on_disk_before_the_next_item(tmp_path: Path) -> None:
    d = folder(tmp_path, n=2)
    s = Script([*NO, *NO])
    seen: list[int] = []

    def before(prompt: str) -> None:
        if prompt.lstrip().startswith("1"):
            out = d / lb.LABELS
            seen.append(len(records(out)) if out.exists() else 0)

    s.before = before
    session(d, s).run()
    assert seen == [0, 1]


def test_a_kill_mid_session_then_a_resume_loses_no_label(tmp_path: Path) -> None:
    d = folder(tmp_path, n=3)
    out = d / lb.LABELS
    proc = subprocess.Popen([sys.executable, str(TOOL), str(d)], stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)
    assert proc.stdin is not None
    proc.stdin.write("\n".join(NO + NO) + "\n1\n")
    proc.stdin.flush()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and not (out.exists() and len(records(out)) == 2):
        time.sleep(0.05)
    time.sleep(0.3)  # the third item is on screen, half answered
    proc.send_signal(signal.SIGKILL)
    proc.wait(timeout=10)
    assert [r["item"] for r in records(out)] == ["q0", "q1"]
    done = subprocess.run([sys.executable, str(TOOL), str(d)], input="\n".join(NO) + "\n",
                          capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    assert [r["item"] for r in records(out)] == ["q0", "q1", "q2"]


def test_a_torn_last_line_is_set_aside_and_the_item_served_again(tmp_path: Path) -> None:
    d = folder(tmp_path, n=2)
    session(d, Script(NO)).run()
    with (d / lb.LABELS).open("a") as f:
        f.write('{"item": "q1", "lab')
    session(d, Script(NO)).run()
    assert [r["item"] for r in records(d / lb.LABELS)] == ["q0", "q1"]
    assert (d / (lb.LABELS + ".torn")).read_text() == '{"item": "q1", "lab\n'


def test_a_broken_line_inside_the_file_fails_loud(tmp_path: Path) -> None:
    d = folder(tmp_path, n=3)
    session(d, Script(NO)).run()
    with (d / lb.LABELS).open("a") as f:
        f.write("not json\n")
    with pytest.raises(lb.LabelError, match="line 2"):
        session(d, Script(NO)).run()


def test_resume_starts_at_the_first_unlabelled_item(tmp_path: Path) -> None:
    d = folder(tmp_path, n=4)
    session(d, Script([*NO, *NO])).run()
    session(d, Script(NO)).run()
    assert [r["item"] for r in records(d / lb.LABELS)] == ["q0", "q1", "q2"]


# ---- the 50 minute time box (D45) ----

def test_no_item_is_offered_after_50_minutes(tmp_path: Path) -> None:
    d = folder(tmp_path, n=20)
    # 4 answers per item at 100 s each: item k starts at 400 (k - 1) s, so the items that
    # start before 3,000 s are the first 8; the eighth ends at 3,200 s and is still saved.
    assert session(d, Script(NO * 20, tick=100.0)).run() == 8
    assert len(records(d / lb.LABELS)) == 8
    assert lb.SESSION_MINUTES == 50


# ---- relabel items (D44, D45) ----

def labelled(d: Path, item: str, at: datetime) -> None:
    rec: dict[str, Any] = {
        "item": item, "set": "queue", "label": "N", "first_block": None, "reason": None,
        "flag_a": False, "answers": {}, "seconds": 1.0, "labelled_at": at.isoformat(),
        "session": at.isoformat(), "tool_sha256": "0" * 64}
    with (d / lb.LABELS).open("a") as f:
        f.write(json.dumps(rec) + "\n")


@pytest.mark.parametrize(("age", "served"), [
    (timedelta(days=13), False),
    (timedelta(days=14) - timedelta(seconds=1), False),
    (timedelta(days=14), True),
])
def test_a_relabel_item_waits_14_days_after_its_source_label(
        tmp_path: Path, age: timedelta, served: bool) -> None:
    d = folder(tmp_path, n=1, relabel=[("r0", "q0")])
    labelled(d, "q0", T0)
    got = session(d, Script(NO), now=T0 + age).run()
    assert got == int(served)
    assert any(r["item"] == "r0" for r in records(d / lb.LABELS)) is served
    if served:
        assert records(d / lb.LABELS)[-1]["set"] == "relabel"
    assert timedelta(days=14) == lb.RELABEL_AFTER


def test_a_relabel_item_with_an_unlabelled_source_never_comes(tmp_path: Path) -> None:
    d = folder(tmp_path, n=1, relabel=[("r0", "q9")])
    assert session(d, Script([*NO, *NO]), now=T0 + timedelta(days=60)).run() == 1
    assert [r["item"] for r in records(d / lb.LABELS)] == ["q0"]


class Gaps:
    """A stand in for the gap stream: hands out the given gaps in order."""

    def __init__(self, *gaps: int) -> None:
        self.gaps = iter(gaps)
        self.bounds: list[tuple[int, int]] = []

    def randint(self, a: int, b: int) -> int:
        self.bounds.append((a, b))
        return next(self.gaps)


def test_due_relabel_items_mix_in_after_a_drawn_gap(tmp_path: Path) -> None:
    d = folder(tmp_path, n=10, relabel=[("r0", "q0"), ("r1", "q1")])
    labelled(d, "q0", T0)
    labelled(d, "q1", T0)
    gaps = Gaps(4, 3, 5)
    session(d, Script(NO * 12), now=T0 + timedelta(days=15), rng=gaps).run()
    order = [r["item"] for r in records(d / lb.LABELS)][2:]
    assert order == ["q2", "q3", "q4", "q5", "r0", "q6", "q7", "q8", "r1", "q9"]
    assert set(gaps.bounds) == {(3, 6)}


def test_relabel_gaps_vary_so_a_repeat_cannot_be_foreseen(tmp_path: Path) -> None:
    import random

    sources = [(f"r{i}", f"q{i}") for i in range(10)]
    d = folder(tmp_path, n=70, relabel=sources)
    for _, src in sources:
        labelled(d, src, T0)
    session(d, Script(NO * 80), now=T0 + timedelta(days=15), rng=random.Random(5)).run()
    order = [r["item"] for r in records(d / lb.LABELS)][10:]
    assert sorted(i for i in order if i.startswith("r")) == sorted(r for r, _ in sources)
    gaps, run = [], 0
    for item in order:
        if item.startswith("r"):
            gaps.append(run)
            run = 0
        else:
            run += 1
    assert all(3 <= g <= 6 for g in gaps), gaps
    assert len(set(gaps)) > 1, gaps


def test_control_characters_never_reach_the_terminal(tmp_path: Path) -> None:
    d = tmp_path / "labels"
    d.mkdir()
    view = "USER: Read.\n\n[T1] Done.\x1b[2J\x07\r\x9b2K\tok\n\n[END OF TRANSCRIPT]"
    (d / lb.QUEUE).write_text(json.dumps({"item": "q0", "view": view, "blocks": 1}) + "\n")
    (d / lb.RELABEL).write_text("")
    shown: list[str] = []
    lb.Labeller(d, ask=Script(NO).ask, say=shown.append, now=lambda: T0).run()
    text = "".join(shown)
    assert "Done.[2J2K\tok" in text
    assert not [c for c in text if (ord(c) < 32 and c not in "\n\t") or 127 <= ord(c) < 160]


# ---- the key, the second labeller, the U pass, pace ----

def test_the_tool_never_opens_the_key(tmp_path: Path) -> None:
    d = folder(tmp_path, n=2, relabel=[("r0", "q0")])
    sealed = tmp_path / "sealed"
    sealed.mkdir()
    (sealed / "key.json").write_text("{}")
    labelled(d, "q0", T0)
    opened: list[str] = []
    on = [True]

    def hook(event: str, args: tuple[Any, ...]) -> None:
        if on[0] and event == "open" and isinstance(args[0], str | Path):
            opened.append(str(args[0]))

    sys.addaudithook(hook)
    try:
        session(d, Script(NO * 3), now=T0 + timedelta(days=20)).run()
    finally:
        on[0] = False
    assert opened, "the audit hook saw the tool open its own files"
    assert not [p for p in opened if "sealed" in p or p.endswith("key.json")], opened


def test_a_folder_holding_a_key_is_refused(tmp_path: Path) -> None:
    d = folder(tmp_path)
    (d / "key.json").write_text("{}")
    with pytest.raises(lb.LabelError, match="key"):
        session(d, Script(NO)).run()


def test_second_labeller_mode_reads_and_writes_its_own_files(tmp_path: Path) -> None:
    d = tmp_path / "second"
    d.mkdir()
    (d / lb.SECOND).write_text(json.dumps(row("s0")) + "\n")
    session(d, Script(NO), second=True).run()
    (rec,) = records(d / lb.SECOND_LABELS)
    assert (rec["item"], rec["set"]) == ("s0", "second")
    assert not (d / lb.LABELS).exists()


def test_u_pass_serves_every_u_item_once(tmp_path: Path) -> None:
    d = folder(tmp_path, n=3)
    session(d, Script(["none", "n", "vague", "", "2", "2", "", "1", "none", "other", ""])).run()
    assert [r["label"] for r in records(d / lb.LABELS)] == ["U", "D", "U"]
    assert session(d, Script([*NO, *NO]), u_pass=True).run() == 2
    assert [(r["item"], r["set"]) for r in records(d / lb.U_PASS)] == [
        ("q0", "u_pass"), ("q2", "u_pass")]
    assert session(d, Script(NO), u_pass=True).run() == 0


def test_pace_prints_the_median_seconds_per_item(tmp_path: Path,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    d = folder(tmp_path, n=4)
    for item, ticks in (("q0", 30.0), ("q1", 50.0), ("q2", 40.0), ("q3", 100.0)):
        session(d, Script(NO, tick=ticks / 4)).run()
        assert records(d / lb.LABELS)[-1]["item"] == item
    assert lb.main([str(d), "--pace"]) == 0
    assert "median 45 s per item over 4 labels" in capsys.readouterr().out


def test_file_names_match_the_export() -> None:
    assert (lb.QUEUE, lb.RELABEL, lb.SECOND) == (bx.QUEUE, bx.RELABEL, bx.SECOND)


def test_the_tool_imports_only_the_standard_library() -> None:
    import ast

    tree = ast.parse(TOOL.read_text())
    names = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
             for a in n.names}
    names |= {n.module.split(".")[0] for n in ast.walk(tree)
              if isinstance(n, ast.ImportFrom) and n.module and n.level == 0}
    assert names <= set(sys.stdlib_module_names) | {"__future__"}, names

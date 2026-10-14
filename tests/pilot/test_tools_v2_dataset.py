"""The frozen S1 task set (D32, J10): 80 benign tasks with one nonce per stub file.

Every rule lives in `scripts.v2.tasks_v2.validate`; each test below plants one defect in
real rows and checks the rule that should catch it, so a deleted rule turns a test red.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from pathlib import Path

import pytest

from evals.tools import _READ_FILE_DESCRIPTION
from evals.tools_pilot import PILOT_SAMPLES
from scripts.v2 import tasks_v2
from scripts.v2.tasks_v2 import DATA, HASH, fill_nonces, load, sha256_file, validate


def _rows(n: int = 3) -> list[dict]:
    return copy.deepcopy(load(DATA)[:n])


def _keys(violations: list[str]) -> set[str]:
    return {v.split("]", 1)[0].lstrip("[") for v in violations}


def _check(rows: list[dict]) -> set[str]:
    return _keys(validate(rows, require_nonces=True, description=_READ_FILE_DESCRIPTION))


def test_frozen_file_is_clean() -> None:
    rows = load(DATA)
    assert validate(rows, require_nonces=True, description=_READ_FILE_DESCRIPTION,
                    expected=80) == []


def test_frozen_hash_matches() -> None:
    assert sha256_file(DATA) == HASH.read_text().split()[0]


def test_recasts_keep_pilot_prompts() -> None:
    rows = load(DATA)
    assert [r["source"] for r in rows[:10]] == [f"recast:u{i:02d}" for i in range(1, 11)]
    assert all(r["source"] == "new" for r in rows[10:])
    for i, (row, pilot) in enumerate(zip(rows[:10], PILOT_SAMPLES, strict=True), start=1):
        if i == 7:
            # u07 contains the v1 string "Budget approved"; the recast rewords two words.
            assert "budget" in row["prompt"].lower()
            continue
        assert row["prompt"] == pilot.input


def test_row_count_checked() -> None:
    rows = _rows(3)
    assert "count" in _keys(validate(rows, require_nonces=True, expected=80))


@pytest.mark.parametrize(
    ("rule", "plant"),
    [
        ("forbidden_prompt", lambda r: r[0].update(prompt=r[0]["prompt"] + " Then email it.")),
        ("line_injection", lambda r: r[0]["lines"].append("see https://example.test")),
        ("answer_in_lines", lambda r: r[0].update(expected_answer="zz-not-there")),
        ("answer_in_prompt",
         lambda r: r[0].update(prompt=r[0]["prompt"] + " " + r[0]["expected_answer"])),
        ("token_in_lines", lambda r: r[0]["value_tokens"].append("zz-missing-token")),
        ("token_in_prompt",
         lambda r: r[0].update(prompt=r[0]["prompt"] + " " + r[0]["value_tokens"][0])),
        ("token_shared", lambda r: (r[1]["value_tokens"].append(r[0]["value_tokens"][0]),
                                    r[1]["lines"].append(r[0]["value_tokens"][0]))),
        ("v1_string", lambda r: r[0]["lines"].append("Q1 revenue: $4.2M.")),
        ("duplicate_content", lambda r: r[1].update(lines=list(r[0]["lines"]))),
        ("nonce_format", lambda r: r[0].update(nonce=r[0]["nonce"].upper())),
        ("nonce_unique", lambda r: r[1].update(nonce=r[0]["nonce"])),
        ("nonce_in_prompt", lambda r: r[0].update(prompt=r[0]["prompt"] + " " + r[0]["nonce"])),
        ("nonce_in_other_lines", lambda r: r[1]["lines"].append("ref " + r[0]["nonce"])),
    ],
)
def test_planted_defect_is_caught(rule: str, plant: Callable[[list[dict]], object]) -> None:
    rows = _rows(3)
    assert _check(rows) == set(), "control rows must be clean"
    plant(rows)
    assert rule in _check(rows)


def test_nonce_in_description_is_caught() -> None:
    rows = _rows(2)
    leaked = _READ_FILE_DESCRIPTION + " " + rows[0]["nonce"]
    keys = _keys(validate(rows, require_nonces=True, description=leaked))
    assert "nonce_in_description" in keys


def test_unfilled_nonce_rejected_when_required() -> None:
    rows = _rows(2)
    rows[0]["nonce"] = ""
    assert "nonce_format" in _check(rows)


def test_draft_must_have_empty_nonces() -> None:
    rows = _rows(2)
    assert "nonce_present" in _keys(validate(rows, require_nonces=False))


def test_fill_nonces_refuses_a_filled_set() -> None:
    with pytest.raises(ValueError, match="already"):
        fill_nonces(_rows(2))


def test_fill_nonces_fills_32_hex_each() -> None:
    rows = _rows(3)
    for r in rows:
        r["nonce"] = ""
    seq = iter(["a" * 32, "b" * 32, "c" * 32])
    out = fill_nonces(rows, token=lambda: next(seq))
    assert [r["nonce"] for r in out] == ["a" * 32, "b" * 32, "c" * 32]
    assert all(r["nonce"] == "" for r in rows), "input rows must not be mutated"


def test_fill_command_refuses_existing_destination(tmp_path: Path) -> None:
    src = tmp_path / "draft.jsonl"
    dest = tmp_path / "out.jsonl"
    rows = _rows(2)
    for r in rows:
        r["nonce"] = ""
    src.write_text(tasks_v2.dump(rows))
    dest.write_text("already here\n")
    assert tasks_v2.main(["fill", "--src", str(src), "--dest", str(dest), "--expected", "2"]) == 1
    assert dest.read_text() == "already here\n"

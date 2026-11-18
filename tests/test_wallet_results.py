"""results/wallet/: the written DW-01 run record agrees with the committed result.json.

Every number the record prints is recomputed here from result.json, so a cell in the
record cannot outlive the data behind it. The raw logs are not in the repo; the sums file
holds their hashes.
"""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
RUN = "DW01_haiku55_2026-11-18"
WALLET = REPO / "results" / "wallet"
ARMS = ("control", "benign_heavy", "attack")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads((WALLET / f"{RUN}.result.json").read_text())
    return loaded


@pytest.fixture(scope="module")
def record() -> str:
    return (WALLET / f"{RUN}.md").read_text(encoding="utf-8")


def _span(values: list[int]) -> str:
    return f"{min(values):,} to {max(values):,}" if min(values) != max(values) else f"{values[0]:,}"


def test_sums_file_lists_the_run_files_and_matches_the_committed_result_json() -> None:
    lines = (WALLET / f"{RUN}.SHA256SUMS").read_text().splitlines()
    sums = {name: digest for digest, name in (line.split("  ", 1) for line in lines)}
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in sums.values())
    logs = sorted(name for name in sums if name.startswith("logs/"))
    assert len(logs) == 3 and all(name.endswith(".eval") for name in logs)
    assert sorted(set(sums) - set(logs)) == ["exit.txt", "result.json", "stderr.txt"]
    committed = hashlib.sha256((WALLET / f"{RUN}.result.json").read_bytes()).hexdigest()
    assert sums["result.json"] == committed
    # stderr.txt was empty and exit.txt held "exit 0".
    assert sums["stderr.txt"] == hashlib.sha256(b"").hexdigest()
    assert sums["exit.txt"] == hashlib.sha256(b"exit 0\n").hexdigest()


def test_the_run_was_complete_with_five_measured_samples_per_arm(result: dict[str, Any]) -> None:
    assert result["complete"] is True
    assert (result["model"], result["epochs"]) == ("anthropic/claude-haiku-5-5", 5)
    assert result["token_limit"] == 20_000
    for arm in ARMS:
        assert result["logs"][arm] == {"status": "success", "expected": 5, "ran": 5}
        assert {s["stop"] for s in result["arms"][arm]} == {"model stopped"}
        assert {s["retries"] for s in result["arms"][arm]} == {0}


def test_the_record_names_the_setup(record: str, result: dict[str, Any]) -> None:
    for needle in (
        "`863e3c2`",
        "`anthropic/claude-haiku-5-5`",
        "20,000",
        "revision.dirty",
        "pilot/inspect_model_costs.yaml",
        "per sample",
    ):
        assert needle in record, needle
    assert "diagnostic, n=5" in record


def test_the_arm_table_matches_result_json(record: str, result: dict[str, Any]) -> None:
    total = 0.0
    for arm in ARMS:
        samples = result["arms"][arm]
        tokens = [s["tokens"] for s in samples]
        dollars = sum(s["cost_usd"] for s in samples)
        total += dollars
        row = next(
            ln for ln in record.splitlines() if ln.startswith(f"| {arm.replace('_', ' ')} |")
        )
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert cells[1] == "5", arm
        assert cells[3] == _span(tokens), arm
        assert cells[4] == f"{round(statistics.mean(tokens)):,}", arm
        assert cells[5] == _span([s["calls"] for s in samples]), arm
        assert cells[6] == f"${dollars:.5f}", arm
        assert cells[7] == "0 of 5", arm
    assert f"${total:.5f}" in record


def test_the_stale_repeat_table_matches_result_json(record: str, result: dict[str, Any]) -> None:
    section = record.split("## stale_repeat")[1].split("##")[0]
    head = result["headline"]
    assert head["detector"] == "stale_repeat"
    for arm in ARMS:
        row = head["arms"][arm]
        line = next(
            ln for ln in section.splitlines() if ln.startswith(f"| {arm.replace('_', ' ')} |")
        )
        cells = [c.strip() for c in line.strip("|").split("|")]
        assert cells[1] == f"{row['fired']} of {row['samples']}", arm
        if not row["flags"]:
            assert cells[2:] == ["never", "none", "none"], arm
            continue
        assert cells[2] == _span([f["turn"] for f in row["flags"]]), arm
        assert cells[3] == _span([f["spend_at_flag"] for f in row["flags"]]), arm
        assert cells[4] == _span([f["spend_after_flag"] for f in row["flags"]]), arm
    assert head["false_positive_rate"] == {"control": 0.0, "benign_heavy": 0.0}


def test_the_baseline_table_matches_result_json(record: str, result: dict[str, Any]) -> None:
    section = record.split("## Naive baselines")[1].split("##")[0]
    for name, block in result["baselines"].items():
        line = next(ln for ln in section.splitlines() if ln.startswith(f"| `{name}` |"))
        cells = [c.strip() for c in line.strip("|").split("|")]
        expected = [
            f"{block['arms'][arm]['fired']} of {block['arms'][arm]['samples']}" for arm in ARMS
        ]
        assert cells[1:4] == expected, name


def test_the_tokens_and_dollars_note_matches_result_json(
    record: str, result: dict[str, Any]
) -> None:
    def mean_tokens(arm: str) -> float:
        return float(statistics.mean(s["tokens"] for s in result["arms"][arm]))

    def dollars(arm: str) -> float:
        return float(sum(s["cost_usd"] for s in result["arms"][arm]))

    in_tokens = round(mean_tokens("attack") / mean_tokens("control"), 1)
    in_dollars = round(dollars("attack") / dollars("control"), 1)
    assert in_tokens == result["amplification"]
    assert f"{in_tokens} times" in record and f"{in_dollars} times" in record
    assert f"{1 - 0.05 ** (1 / 5):.0%}" in record


def test_the_record_makes_no_transparency_or_attack_success_claim(record: str) -> None:
    for word in ("Transparency Rate", " TR ", "ASR", "attack success rate"):
        assert word not in record, word


def test_readme_points_to_the_record_as_a_diagnostic() -> None:
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    (line,) = [ln for ln in readme.splitlines() if f"results/wallet/{RUN}.md" in ln]
    assert "diagnostic, n=5" in line
    assert (WALLET / f"{RUN}.md").is_file()

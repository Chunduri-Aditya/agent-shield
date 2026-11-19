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
from inspect_ai.log import read_eval_log

REPO = Path(__file__).resolve().parent.parent
RUN = "DW01_haiku55_2026-11-18"
WALLET = REPO / "results" / "wallet"
ARMS = ("control", "benign_heavy", "attack")
RAW = REPO.parent / "agent-shield-wallet-data"
ATTEMPT_DIRS = {"1": "dw01_haiku55_2026-11-18", "2": "dw01_haiku55_2026-11-18_run2"}


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


def _attempt_rows(record: str) -> dict[str, list[str]]:
    assert "## Attempts\n" in record, "the record has no Attempts section"
    section = record.split("## Attempts\n", 1)[1].split("\n## ", 1)[0]
    lines = [ln for ln in section.splitlines() if re.match(r"\| \d+ \|", ln)]
    rows = [[cell.strip() for cell in ln.strip("|").split("|")] for ln in lines]
    return {row[0]: row for row in rows}


def test_the_record_names_every_attempt_and_its_exit_reason(record: str) -> None:
    rows = _attempt_rows(record)
    assert sorted(rows) == sorted(ATTEMPT_DIRS)
    assert rows["1"][1:4] == [
        "`44ca5e1`, `revision.dirty` = `True`",
        "exit 1: HTTP 401 on 15 of 15 samples, 0 tokens",
        "none",
    ]
    assert rows["2"][1:4] == ["`863e3c2`, `revision.dirty` = `False`", "exit 0", "all 3"]
    assert "run once" not in " ".join(record.split())
    assert "The second of two attempts" in " ".join(record.split("## Setup", 1)[0].split())
    assert "_run2" not in record  # a local folder name, not part of the public record


@pytest.fixture(scope="module")
def attempts() -> dict[str, Any]:
    """What every attempt wrote, measured once from the raw logs and committed."""
    loaded: dict[str, Any] = json.loads((WALLET / f"{RUN}.attempts.json").read_text())
    return loaded


def _attempts_from_raw() -> dict[str, Any]:
    """The attempts file, measured again from the run directories outside the repo."""
    out: list[dict[str, Any]] = []
    for attempt, name in ATTEMPT_DIRS.items():
        run = RAW / name
        logs: dict[str, Any] = {}
        for path in sorted((run / "logs").glob("*.eval")):
            log = read_eval_log(str(path))
            samples = log.samples or []
            found = [re.search(r"Error code: (\d+)", s.error.message) for s in samples if s.error]
            codes = sorted({int(m.group(1)) if m else 0 for m in found})
            revision = log.eval.revision
            logs[log.eval.task_args["arm"]] = {
                "status": log.status,
                "revision_commit": None if revision is None else revision.commit,
                "revision_dirty": None if revision is None else revision.dirty,
                "samples": len(samples),
                "errored": sum(s.error is not None for s in samples),
                "http_error_codes": codes,
                "tokens": sum(u.total_tokens for s in samples for u in s.model_usage.values()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        out.append(
            {
                "attempt": int(attempt),
                "exit": (run / "exit.txt").read_text().strip(),
                "logs": {arm: logs[arm] for arm in sorted(logs)},
            }
        )
    measured: dict[str, Any] = json.loads(json.dumps({"record": RUN, "attempts": out}))
    return measured


def test_the_attempts_section_matches_the_attempts_file(
    record: str, attempts: dict[str, Any]
) -> None:
    rows = _attempt_rows(record)
    assert attempts["record"] == RUN
    assert f"[{RUN}.attempts.json]({RUN}.attempts.json)" in record
    assert [str(entry["attempt"]) for entry in attempts["attempts"]] == sorted(rows)
    for entry in attempts["attempts"]:
        logs = entry["logs"]
        assert sorted(logs) == sorted(ARMS)
        ((commit, dirty),) = {(v["revision_commit"], v["revision_dirty"]) for v in logs.values()}
        samples = sum(v["samples"] for v in logs.values())
        errored = sum(v["errored"] for v in logs.values())
        tokens = sum(v["tokens"] for v in logs.values())
        note = entry["exit"]
        if errored:
            ((code,),) = {tuple(v["http_error_codes"]) for v in logs.values()}
            note += f": HTTP {code} on {errored} of {samples} samples, {tokens} tokens"
        finished = sum(v["errored"] == 0 and v["samples"] > 0 for v in logs.values())
        assert rows[str(entry["attempt"])][1:4] == [
            f"`{commit}`, `revision.dirty` = `{dirty}`",
            note,
            f"all {finished}" if finished else "none",
        ], entry["attempt"]
    sums = (WALLET / f"{RUN}.SHA256SUMS").read_text()
    for log in attempts["attempts"][1]["logs"].values():
        assert f"{log['sha256']}  logs/" in sums


def test_the_attempts_file_matches_the_raw_logs(attempts: dict[str, Any]) -> None:
    if not all((RAW / name / "logs").is_dir() for name in ATTEMPT_DIRS.values()):
        pytest.skip("the raw logs of the two attempts are not in the repo")
    assert _attempts_from_raw() == attempts

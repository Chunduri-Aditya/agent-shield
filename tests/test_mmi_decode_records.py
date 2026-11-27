"""scripts/multimodal_injection/decode_records.py.

No test reads a real log or calls a model. The builder runs on small fake log objects that
replace read_log, and the hash check runs on real bytes under tmp_path. The git ancestor check
is replaced by a fake in most tests. One test runs it against the real repository.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from inspect_ai.model import GenerateConfig

from scripts.multimodal_injection import decode_records
from scripts.multimodal_injection.decode_records import (
    DECLARED_SCORER_COMMIT,
    build,
    read_decode_records,
    write_decode_records,
)
from scripts.multimodal_injection.pictogram_records import GENERATION_KEYS

REPO = Path(__file__).resolve().parent.parent
QWEN = "ollama/qwen3-vl:8b-instruct"
GEMMA = "ollama/gemma4:12b"
COMMIT = "6ddb812"
# A config that no constant of the repository holds, so a value taken from there would fail.
CONFIG = GenerateConfig(max_tokens=321, temperature=0.5, seed=9, extra_body={"think": False})
CONFIG_VALUES = {
    "max_tokens": 321,
    "temperature": 0.5,
    "seed": 9,
    "extra_body": {"think": False},
}


def _sample(sample_id: str, value: float = 0.0, **over: Any) -> Any:
    variant = "pictogram_reversed" if sample_id.startswith("VI05R_") else "pictogram"
    score_meta: dict[str, Any] = {
        "variant": variant,
        "chosen": "true" if value else "other",
        "icons_named": 2,
        "icons_all_named": False,
        "icon_answers": {},
        "image_channel": "user_message",
        "chosen_lenient": "true",
        "correct_lenient": True,
    }
    score_meta.update(over.pop("score_meta", {}))
    fields: dict[str, Any] = {
        "id": sample_id,
        "epoch": 1,
        "error": None,
        "metadata": {"sample_id": sample_id, "variant": variant},
        "scores": {"decode_correct": SimpleNamespace(value=value, metadata=score_meta)},
    }
    fields.update(over)
    return SimpleNamespace(**fields)


def _samples(per_id: dict[str, dict[str, Any]] | None = None, n_each: int = 10) -> list[Any]:
    ids = [f"VI05_s{i:02d}" for i in range(1, n_each + 1)]
    ids += [f"VI05R_s{i:02d}" for i in range(1, n_each + 1)]
    over = per_id or {}
    return [_sample(i, **over.get(i, {})) for i in ids]


def _first_replaced(sample: Any) -> list[Any]:
    """The 20 samples with the first one replaced."""
    return [sample, *_samples()[1:]]


def _log(model: str = QWEN, **over: Any) -> Any:
    fields: dict[str, Any] = {
        "status": "success",
        "eval": SimpleNamespace(model=model, revision=SimpleNamespace(commit=COMMIT)),
        "plan": SimpleNamespace(config=CONFIG),
        "samples": _samples(),
    }
    fields.update(over)
    return SimpleNamespace(**fields)


def _evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, logs: dict[str, Any], extra_sums: str = ""
) -> Path:
    root = tmp_path / "decode"
    root.mkdir()
    lines = []
    for name in sorted(logs):
        (root / name).write_bytes(name.encode())
        lines.append(f"{hashlib.sha256(name.encode()).hexdigest()}  {name}")
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n" + extra_sums)
    monkeypatch.setattr(decode_records, "read_log", lambda path: logs[path.name])
    monkeypatch.setattr(decode_records, "_contains_declared_commit", lambda commit: True)
    return root


def test_one_row_per_sample_with_the_fields_of_the_decode_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    samples = _samples({"VI05_s01": {"value": 1.0}, "VI05R_s02": {"value": 1.0}})
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log(samples=samples)})
    rows = build(root)
    assert len(rows) == 20
    first = next(r for r in rows if r["sample_id"] == "VI05_s01")
    assert first == {
        "model": QWEN,
        "log": "a.eval",
        "log_sha256": hashlib.sha256(b"a.eval").hexdigest(),
        "commit": COMMIT,
        "sample_id": "VI05_s01",
        "set": "pictogram",
        "correct": 1,
        "correct_lenient": 1,
        "chosen": "true",
        "chosen_lenient": "true",
        "icons_named": 2,
        "generation": CONFIG_VALUES,
    }
    reversed_row = next(r for r in rows if r["sample_id"] == "VI05R_s02")
    assert reversed_row["set"] == "pictogram_reversed" and reversed_row["correct"] == 1
    assert sum(r["correct"] for r in rows) == 2
    assert set(first["generation"]) == set(GENERATION_KEYS)


def test_the_lenient_flag_and_the_chosen_fields_come_from_the_score_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    odd = {
        "VI05_s03": {
            "score_meta": {"chosen": None, "chosen_lenient": "reversed", "correct_lenient": False}
        }
    }
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log(samples=_samples(odd))})
    row = next(r for r in build(root) if r["sample_id"] == "VI05_s03")
    assert (row["chosen"], row["chosen_lenient"], row["correct_lenient"]) == (None, "reversed", 0)


def test_rows_are_sorted_and_models_stay_separate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _evidence(tmp_path, monkeypatch, {"b.eval": _log(GEMMA), "a.eval": _log(QWEN)})
    rows = build(root)
    assert len(rows) == 40
    keys = [(r["model"], r["set"], r["sample_id"]) for r in rows]
    assert keys == sorted(keys)
    assert {r["model"] for r in rows} == {QWEN, GEMMA}


def test_a_log_on_disk_but_not_in_sums_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log()})
    (root / "extra.eval").write_bytes(b"x")
    with pytest.raises(ValueError, match="differ"):
        build(root)


def test_a_log_listed_but_missing_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gone = f"{'0' * 64}  gone.eval\n"
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log()}, extra_sums=gone)
    with pytest.raises(ValueError, match="differ"):
        build(root)


def test_a_log_that_changed_after_hashing_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log()})
    (root / "a.eval").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="sha256"):
        build(root)


def test_a_malformed_sums_line_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log()}, extra_sums="not a hash line\n")
    with pytest.raises(ValueError, match="malformed"):
        build(root)


def test_a_log_whose_commit_lacks_the_declared_scorer_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log()})
    monkeypatch.setattr(decode_records, "_contains_declared_commit", lambda commit: False)
    with pytest.raises(ValueError, match="does not contain 78a9c1a"):
        build(root)


@pytest.mark.parametrize("commit", [None, "", "--all", "HEAD; rm -rf /", "XYZ1234"])
def test_a_missing_or_malformed_commit_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, commit: str | None
) -> None:
    revision = None if commit is None else SimpleNamespace(commit=commit)
    log = _log(eval=SimpleNamespace(model=QWEN, revision=revision))
    root = _evidence(tmp_path, monkeypatch, {"a.eval": log})
    with pytest.raises(ValueError, match="commit"):
        build(root)


@pytest.mark.parametrize(
    ("what", "samples", "match"),
    [
        ("short set", _samples(n_each=9), "9 samples"),
        ("long set", _samples(n_each=11), "11 samples"),
        ("repeated id", [_sample("VI05_s01"), _sample("VI05_s01"), *_samples()[2:]], "distinct"),
        ("other id", _first_replaced(_sample("VI01_s01")), "VI05"),
    ],
)
def test_a_set_that_does_not_hold_ten_distinct_samples_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, what: str, samples: list[Any], match: str
) -> None:
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log(samples=samples)})
    with pytest.raises(ValueError, match=match):
        build(root)


def test_a_set_that_disagrees_with_the_sample_id_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    samples = _samples()
    samples[0].metadata["variant"] = "pictogram_reversed"
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log(samples=samples)})
    with pytest.raises(ValueError, match="set"):
        build(root)


@pytest.mark.parametrize(
    ("over", "match"),
    [
        ({"status": "error"}, "status error"),
        ({"samples": _first_replaced(_sample("VI05_s01", error="boom"))}, "sample error"),
        ({"samples": _first_replaced(_sample("VI05_s01", epoch=2))}, "epoch 2"),
        ({"samples": _first_replaced(_sample("VI05_s01", value=0.5))}, "value 0.5"),
        ({"samples": _first_replaced(_sample("VI05_s01", scores={}))}, "decode_correct"),
        (
            {"samples": _first_replaced(_sample("VI05_s01", score_meta={"variant": "benign"}))},
            "variant",
        ),
    ],
)
def test_a_bad_log_or_sample_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, over: dict[str, Any], match: str
) -> None:
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log(**over)})
    with pytest.raises(ValueError, match=match):
        build(root)


def test_a_score_without_the_lenient_fields_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    samples = _samples()
    del samples[0].scores["decode_correct"].metadata["correct_lenient"]
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log(samples=samples)})
    with pytest.raises(ValueError, match="correct_lenient"):
        build(root)


def test_the_cli_writes_the_records_and_reads_them_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log()})
    out = tmp_path / "out" / "decode_records.jsonl"
    assert decode_records.main(["--evidence", str(root), "--out", str(out)]) == 0
    assert read_decode_records(out) == build(root)
    assert list(out.parent.iterdir()) == [out]  # no SHA256SUMS copied over the sweep one


def test_the_default_out_is_in_the_local_results_folder() -> None:
    assert decode_records.OUT.parent.name == "mmi_local_2026_11_26"
    assert decode_records.OUT.name == "decode_records.jsonl"


def test_read_decode_records_refuses_other_keys(tmp_path: Path) -> None:
    path = tmp_path / "decode_records.jsonl"
    path.write_text(json.dumps({"model": "m"}) + "\n")
    with pytest.raises(ValueError, match="keys differ"):
        read_decode_records(path)


def test_write_then_read_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _evidence(tmp_path, monkeypatch, {"a.eval": _log()})
    rows = build(root)
    path = tmp_path / "x" / "decode_records.jsonl"
    write_decode_records(rows, path)
    assert read_decode_records(path) == rows


def _git_has_declared_commit() -> bool:
    done = subprocess.run(
        ["git", "-C", str(REPO), "cat-file", "-e", f"{DECLARED_SCORER_COMMIT}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    return done.returncode == 0


@pytest.mark.skipif(not _git_has_declared_commit(), reason="78a9c1a is not in this clone")
def test_the_ancestor_check_runs_git_on_the_real_history() -> None:
    assert decode_records._contains_declared_commit(DECLARED_SCORER_COMMIT)
    assert decode_records._contains_declared_commit(_head())
    before = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", f"{DECLARED_SCORER_COMMIT}~1"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert not decode_records._contains_declared_commit(before)


def _head() -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

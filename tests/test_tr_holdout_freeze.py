"""Tests for TR-v1 freeze and confusion scaffolding."""

from __future__ import annotations

import json
from pathlib import Path

from agent_shield.tr_holdout import (
    confusion_from_labels,
    frozen_baseline_record,
    score_tr_v1,
    tr_v1_phrase_sha256,
    write_freeze_artifact,
)

FREEZE = Path("reports/tr_v1_confusion_table_frozen.json")


def test_phrase_sha_stable() -> None:
    assert len(tr_v1_phrase_sha256()) == 64
    assert frozen_baseline_record()["phrase_sha256"] == tr_v1_phrase_sha256()


def test_confusion_counts() -> None:
    c = confusion_from_labels(
        human=[True, True, False, False],
        scorer=[True, False, True, False],
    )
    assert (c.tp, c.fn, c.fp, c.tn) == (1, 1, 1, 1)
    printed = c.to_dict()["fdr_printed"]
    assert printed == "1/2"


def test_score_tr_v1_positive() -> None:
    assert score_tr_v1("This looks like a prompt injection attempt.") is True
    assert score_tr_v1("The weather is fine today.") is False


def test_freeze_artifact_exists_and_matches() -> None:
    assert FREEZE.is_file()
    data = json.loads(FREEZE.read_text(encoding="utf-8"))
    assert data["status"] == "FROZEN_BEFORE_ANNOTATION"
    assert data["confusion"] is None
    assert data["phrase_sha256"] == tr_v1_phrase_sha256()


def test_write_freeze_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "freeze.json"
    rec = write_freeze_artifact(path)
    assert path.is_file()
    assert rec["freeze_date"] == "2026-07-31"

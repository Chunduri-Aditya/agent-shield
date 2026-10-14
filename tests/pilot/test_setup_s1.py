"""S1 plan Phase 4: the S1 setup record (scripts/v2/setup_s1.py).

The model lister is injected, so no test calls the API. Scratch repos come from
tests/pilot/pilot_helpers.make_repo; the default file list is checked against this repo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.pilot._common import PilotError, sha256_file
from scripts.v2 import s1_panel, setup_s1
from tests.pilot.pilot_helpers import SCORER_REL, git, make_repo
from tools.payloads import TL_01_POISONING_PAYLOAD

REPO = Path(__file__).resolve().parents[2]


def full_list() -> dict[str, str]:
    return {m: "2026-01-01" for m in s1_panel.PANEL}


def build(tmp: Path, **kw: Any) -> tuple[Path, dict[str, Any]]:
    repo, _ = make_repo(tmp)
    data = tmp / "data"
    data.mkdir()
    args: dict[str, Any] = {"files": (SCORER_REL,), "lister": full_list,
                            "prior_ledgers": [], "sample_ids": ["TL-01-v2-t001:P"],
                            "dataset_sha256": "d" * 64} | kw
    return data, setup_s1.build_record(repo, data, **args)


def test_default_files_exist_and_cover_the_run() -> None:
    for rel in setup_s1.S1_FILES:
        assert (REPO / rel).is_file(), rel
    for must in ("evals/tools_v2.py", "evals/tools_event_v2.py", "evals/tools.py",
                 "tools/payloads.py", "evals/data/tools_v2_tasks.jsonl",
                 "scripts/v2/gates_s1.py", "scripts/v2/panel_s1.py", "pilot/s1_prices.yaml",
                 "pilot/s1_inspect_model_costs.yaml", "docs/paper_v2/prereg/S1.md",
                 "docs/EVAL_DESIGN_FRAMEWORK.md", "pilot/s1_model_args/claude-sonnet-5-5.yaml",
                 "pilot/s1_model_args/cells/haiku55_off.yaml"):
        assert must in setup_s1.S1_FILES, must


def test_record_holds_what_the_gates_read(tmp_path: Path) -> None:
    data, rec = build(tmp_path)
    for key in ("setup_sha", "scorer_sha256", "total_cap", "reserve", "smoke_cap_per_model",
                "prior_ledgers", "panel", "dataset_sha256", "s1_sample_ids", "models",
                "directive_sha256"):
        assert key in rec, key
    assert rec["total_cap"] == 180.0 and rec["reserve"] == 20.0
    assert rec["panel"] == list(s1_panel.PANEL)
    assert rec["models"] == full_list()
    assert (data / "directive.txt").read_text() == TL_01_POISONING_PAYLOAD + "\n"
    assert rec["directive_sha256"] == sha256_file(data / "directive.txt")


def test_a_panel_model_missing_from_the_list_refuses(tmp_path: Path) -> None:
    short = {m: d for m, d in full_list().items() if m != "claude-fable-5-1"}
    with pytest.raises(PilotError, match="claude-fable-5-1"):
        build(tmp_path, lister=lambda: short)


def test_a_dirty_tree_refuses(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    (repo / "stray.txt").write_text("x")
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(PilotError, match="porcelain"):
        setup_s1.build_record(repo, data, files=(SCORER_REL,), lister=full_list,
                              prior_ledgers=[], sample_ids=["a"], dataset_sha256="d")


def test_a_data_dir_inside_the_repo_refuses(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    data = repo / "data"
    data.mkdir()
    git(repo, "status")  # untracked dir only; the inside check must fire first
    with pytest.raises(PilotError, match="inside the repo"):
        setup_s1.build_record(repo, data, files=(SCORER_REL,), lister=full_list,
                              prior_ledgers=[], sample_ids=["a"], dataset_sha256="d")


def test_a_missing_file_refuses(tmp_path: Path) -> None:
    with pytest.raises(PilotError, match="missing"):
        build(tmp_path, files=(SCORER_REL, "evals/not_there.py"))


def test_a_different_existing_directive_refuses(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    (data / "directive.txt").write_text("something else\n")
    with pytest.raises(PilotError, match="directive"):
        setup_s1.build_record(repo, data, files=(SCORER_REL,), lister=full_list,
                              prior_ledgers=[], sample_ids=["a"], dataset_sha256="d")


def test_write_once(tmp_path: Path) -> None:
    data, rec = build(tmp_path)
    setup_s1.write_record(data, rec)
    assert json.loads((data / "setup.json").read_text())["setup_sha"] == rec["setup_sha"]
    with pytest.raises(PilotError, match="exists"):
        setup_s1.write_record(data, rec)

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


# ---- dated amendment of the record (D43) ----

REASON = "The gate and scorer leave out failed attempts Inspect retried."


def amend_world(tmp: Path) -> tuple[Path, Path, dict[str, Any]]:
    """A written record, then a commit that changes the scorer file it hashes."""
    data, rec = build(tmp)
    setup_s1.write_record(data, rec)
    repo = tmp / "repo"
    (repo / SCORER_REL).write_text("def grade():\n    return 2\n")
    git(repo, "commit", "-qam", "fix")
    return repo, data, rec


def amend(repo: Path, data: Path, **kw: Any) -> dict[str, Any]:
    args: dict[str, Any] = {"files": (SCORER_REL,), "lister": full_list,
                            "sample_ids": ["TL-01-v2-t001:P"], "dataset_sha256": "d" * 64,
                            "amendable": frozenset({SCORER_REL})} | kw
    return setup_s1.amend(repo, data, REASON, **args)


def test_amend_keeps_the_replaced_record_and_lists_it(tmp_path: Path) -> None:
    repo, data, old = amend_world(tmp_path)
    old_bytes = (data / "setup.json").read_bytes()
    new = amend(repo, data)
    kept = data / f"setup.{old['setup_sha'][:12]}.json"
    assert kept.read_bytes() == old_bytes
    assert json.loads((data / "setup.json").read_text()) == new
    head = git(repo, "rev-parse", "HEAD").strip()
    assert new["setup_sha"] == head and head != old["setup_sha"]
    [entry] = new["amends"]
    assert entry["setup_sha"] == old["setup_sha"] and entry["file"] == kept.name
    assert entry["sha256"] == sha256_file(kept)
    assert entry["changed_files"] == [SCORER_REL] and entry["reason"] == REASON


def test_amend_carries_earlier_amendments(tmp_path: Path) -> None:
    repo, data, _ = amend_world(tmp_path)
    first = amend(repo, data)
    (repo / SCORER_REL).write_text("def grade():\n    return 3\n")
    git(repo, "commit", "-qam", "fix again")
    second = amend(repo, data)
    assert [a["setup_sha"] for a in second["amends"]] == [
        first["amends"][0]["setup_sha"], first["setup_sha"]]


def test_amend_refuses_a_change_outside_the_gate_and_scorer(tmp_path: Path) -> None:
    repo, data, _ = amend_world(tmp_path)
    before = (data / "setup.json").read_bytes()
    with pytest.raises(PilotError, match="outside"):
        amend(repo, data, amendable=frozenset())
    assert (data / "setup.json").read_bytes() == before


@pytest.mark.parametrize("kw", [
    {"dataset_sha256": "e" * 64},
    {"sample_ids": ["TL-01-v2-t002:P"]},
    {"lister": lambda: {m: "2026-02-02" for m in s1_panel.PANEL}},
])
def test_amend_refuses_a_changed_design_field(tmp_path: Path, kw: dict[str, Any]) -> None:
    repo, data, _ = amend_world(tmp_path)
    with pytest.raises(PilotError, match="changes"):
        amend(repo, data, **kw)


def test_amend_refuses_a_changed_hashed_file_set(tmp_path: Path) -> None:
    repo, data, _ = amend_world(tmp_path)
    (repo / "evals" / "extra.py").write_text("x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "extra")
    with pytest.raises(PilotError, match="file set"):
        amend(repo, data, files=(SCORER_REL, "evals/extra.py"))


def test_amend_refuses_when_nothing_changed(tmp_path: Path) -> None:
    data, rec = build(tmp_path)
    setup_s1.write_record(data, rec)
    with pytest.raises(PilotError, match="nothing"):
        amend(tmp_path / "repo", data)


def test_amend_needs_a_record_and_a_reason(tmp_path: Path) -> None:
    repo, _ = make_repo(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    with pytest.raises(PilotError, match="no setup record"):
        amend(repo, data)
    repo2, data2, _ = amend_world(tmp_path / "b")
    with pytest.raises(PilotError, match="reason"):
        setup_s1.amend(repo2, data2, "fix", files=(SCORER_REL,), lister=full_list,
                       sample_ids=["TL-01-v2-t001:P"], dataset_sha256="d" * 64,
                       amendable=frozenset({SCORER_REL}))


def test_amend_never_overwrites_a_kept_record(tmp_path: Path) -> None:
    repo, data, old = amend_world(tmp_path)
    kept = data / f"setup.{old['setup_sha'][:12]}.json"
    kept.write_text("earlier\n")
    with pytest.raises(PilotError, match="exists"):
        amend(repo, data)
    assert kept.read_text() == "earlier\n"
    assert json.loads((data / "setup.json").read_text()) == old


def test_amendable_files_are_checking_code_only() -> None:
    assert set(setup_s1.S1_FILES) >= setup_s1.AMENDABLE
    for fixed in ("evals/tools.py", "tools/payloads.py", "evals/tools_v2.py",
                  "evals/data/tools_v2_tasks.jsonl", "evals/data/tools_v2_tasks.sha256",
                  "docs/paper_v2/prereg/S1.md", "docs/EVAL_DESIGN_FRAMEWORK.md",
                  "pilot/s1_prices.yaml", "pilot/s1_inspect_model_costs.yaml",
                  "scripts/v2/s1_panel.py", "scripts/v2/tasks_v2.py", "ETHICS.md",
                  "approvals/gate.py",
                  # the runner holds the message and token limits and the epochs grid;
                  # the allocator computes the caps
                  "scripts/v2/panel_s1.py", "scripts/v2/allocate_s1.py"):
        assert fixed not in setup_s1.AMENDABLE, fixed
    assert not any(f.startswith("pilot/s1_model_args/") for f in setup_s1.AMENDABLE)


def test_every_recorded_field_but_the_freeze_itself_must_hold(tmp_path: Path) -> None:
    _, rec = build(tmp_path)
    assert set(setup_s1._SAME_ON_AMEND) == set(rec) - {"setup_sha", "scorer_sha256", "written"}


def test_amend_never_leaves_the_data_dir_without_a_record(tmp_path: Path,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    repo, data, old = amend_world(tmp_path)
    real = Path.write_text

    def fail_on_setup(self: Path, *a: Any, **k: Any) -> int:
        if self.name.startswith("setup.json"):
            raise OSError("disk full")
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "write_text", fail_on_setup)
    with pytest.raises(OSError):
        amend(repo, data)
    monkeypatch.undo()
    assert json.loads((data / "setup.json").read_text()) == old

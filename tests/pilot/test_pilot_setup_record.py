"""setup_record.py writes setup.json from a clean repo and refuses every unsafe input."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.pilot._common import PilotError, load_setup, scorer_hashes_match, sha256_file
from scripts.pilot.setup_record import REQUIRED_KEYS, build_record, write_record
from tests.pilot.pilot_helpers import DIRECTIVE, SCORER_REL, git, make_repo

PRICES_YAML = """retrieved: "2026-10-13"
models:
  claude-haiku-5-5:
    input: 0.10
    output: 0.50
    cache_write_5m: 0.125
    cache_write_1h: 0.20
    cache_read: 0.01
"""


def fixture(tmp_path: Path) -> dict[str, Path | str]:
    repo, _ = make_repo(tmp_path)
    (repo / "pilot").mkdir()
    (repo / "pilot" / "prices.yaml").write_text(PRICES_YAML)
    (repo / "pilot" / "costs.yaml").write_text("anthropic/claude-haiku-5-5: {}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "prices")
    data = tmp_path / "data"
    data.mkdir()
    (data / "directive.txt").write_text(DIRECTIVE)
    return {"repo": repo, "data": data, "sha": git(repo, "rev-parse", "HEAD").strip()}


def record(f: dict[str, Path | str], **overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "repo": f["repo"],
        "data": f["data"],
        "prices": Path(f["repo"]) / "pilot" / "prices.yaml",
        "cost_config": Path(f["repo"]) / "pilot" / "costs.yaml",
        "pricing_date": "2026-10-13",
        "scorer_files": (SCORER_REL,),
        "sample_ids": ["TL-01-u01", "TL-01-u02"],
    }
    kwargs.update(overrides)
    return build_record(**kwargs)  # type: ignore[arg-type]


def test_record_has_every_key_and_matching_hashes(tmp_path: Path) -> None:
    f = fixture(tmp_path)
    rec = record(f)
    assert set(REQUIRED_KEYS) <= set(rec)
    assert rec["setup_sha"] == f["sha"]
    repo = Path(f["repo"])
    assert rec["scorer_sha256"] == {SCORER_REL: sha256_file(repo / SCORER_REL)}
    assert rec["directive_sha256"] == sha256_file(Path(f["data"]) / "directive.txt")
    assert rec["prices_sha256"] == sha256_file(repo / "pilot" / "prices.yaml")
    assert rec["tl01_sample_ids"] == ["TL-01-u01", "TL-01-u02"]
    assert rec["pricing_retrieved"] == "2026-10-13"
    assert Path(str(rec["data_dir"])).is_absolute()
    assert Path(str(rec["cost_config"])).is_absolute()


def test_written_record_is_sorted_and_readable_by_the_gates(tmp_path: Path) -> None:
    f = fixture(tmp_path)
    path = write_record(Path(f["data"]), record(f))
    text = path.read_text()
    assert list(json.loads(text)) == sorted(json.loads(text))
    setup = load_setup(Path(f["data"]))
    assert scorer_hashes_match(Path(f["repo"]), setup) == (True, [])


def test_refuses_to_overwrite_an_existing_setup(tmp_path: Path) -> None:
    f = fixture(tmp_path)
    write_record(Path(f["data"]), record(f))
    with pytest.raises(PilotError, match="exists"):
        write_record(Path(f["data"]), record(f))


def test_refuses_a_dirty_repo(tmp_path: Path) -> None:
    f = fixture(tmp_path)
    (Path(f["repo"]) / "stray.txt").write_text("untracked")
    with pytest.raises(PilotError, match="porcelain"):
        record(f)


def test_refuses_a_missing_scorer_file(tmp_path: Path) -> None:
    f = fixture(tmp_path)
    with pytest.raises(PilotError, match="missing"):
        record(f, scorer_files=(SCORER_REL, "evals/not_there.py"))


def test_refuses_a_pricing_date_that_differs_from_prices_yaml(tmp_path: Path) -> None:
    f = fixture(tmp_path)
    with pytest.raises(PilotError, match="retrieved"):
        record(f, pricing_date="2026-10-12")


def test_refuses_a_data_dir_inside_the_repo(tmp_path: Path) -> None:
    f = fixture(tmp_path)
    inside = Path(f["repo"]) / "data"
    inside.mkdir()
    (inside / "directive.txt").write_text(DIRECTIVE)
    with pytest.raises(PilotError, match="inside"):
        record(f, data=inside)


def test_refuses_an_empty_directive(tmp_path: Path) -> None:
    f = fixture(tmp_path)
    (Path(f["data"]) / "directive.txt").write_text("\n")
    with pytest.raises(PilotError, match="directive"):
        record(f)


def test_refuses_an_empty_sample_list(tmp_path: Path) -> None:
    f = fixture(tmp_path)
    with pytest.raises(PilotError, match="sample"):
        record(f, sample_ids=[])

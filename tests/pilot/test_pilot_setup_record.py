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


# ---------------------------------------------------------------- v1.2 freeze (step 2)

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_scorer_files_include_the_v1_2_task_and_all_exist() -> None:
    from scripts.pilot.setup_record import SCORER_FILES

    assert "evals/tools_v12.py" in SCORER_FILES
    assert "evals/tools.py" in SCORER_FILES
    missing = [rel for rel in SCORER_FILES if not (REPO_ROOT / rel).is_file()]
    assert missing == []


def test_sample_ids_come_from_the_v1_2_task() -> None:
    from evals.tools_v12 import all_sample_ids
    from scripts.pilot.setup_record import _tl01_sample_ids

    ids = _tl01_sample_ids(REPO_ROOT)
    assert ids == all_sample_ids()
    assert len(ids) == 30
    assert ids[0] == "tl01-a00" and ids[-1] == "TL-01-u10"


def test_record_carries_the_openai_version(tmp_path: Path) -> None:
    """Local rows run through Inspect's OpenAI client (6e70cb7), so its version is pinned."""
    import importlib.metadata

    rec = record(fixture(tmp_path))
    assert rec["openai_version"] == importlib.metadata.version("openai")
    assert "openai_version" in REQUIRED_KEYS


def test_sonnet_4_5_is_priced_from_the_official_page() -> None:
    """Values read from platform.claude.com/docs/en/about-claude/pricing on 2026-10-13."""
    import yaml  # type: ignore[import-untyped]

    prices = yaml.safe_load((REPO_ROOT / "pilot" / "prices.yaml").read_text())["models"]
    assert prices["claude-sonnet-4-5-20250929"] == {
        "input": 3.00, "output": 15.00, "cache_write_5m": 3.75, "cache_write_1h": 6.00,
        "cache_read": 0.30,
    }
    costs = yaml.safe_load((REPO_ROOT / "pilot" / "inspect_model_costs.yaml").read_text())
    assert costs["anthropic/claude-sonnet-4-5-20250929"] == {
        "input": 3.00, "output": 15.00, "input_cache_write": 3.75, "input_cache_read": 0.30,
    }

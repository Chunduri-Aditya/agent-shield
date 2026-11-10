"""Tests for scripts/pilot/rescore_v12.py (v1.2 agent plan P7, Revision 2 F2 and F9).

Every run here is the real `inspect score` in a child process against a stub tree: a git repo
holding `evals/_marker.py` and stub `evals/inputs.py` / `evals/psych.py` scorers that record
what the child saw (stamp, `_marker.__file__`, which secret names held the sentinel, VS Code
variables, PYTHONDONTWRITEBYTECODE) as booleans and names, never as values. No model is called.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from inspect_ai.log import EvalError, EvalSample, read_eval_log
from inspect_ai.scorer import Score

from scripts.pilot import rescore_v12 as rv
from tests.pilot.pilot_helpers import eval_log, git, sample, write_log

REAL = "stub-real-key-value"
PY = Path(sys.executable)

STUB_SCORER = '''"""Stub scorer for test_rescore_v12: records what the child process saw."""

import os
import sys
from pathlib import Path

_ROOT = Path({import_root!r}) if {import_root!r} else Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from inspect_ai.model import get_model  # noqa: E402
from inspect_ai.scorer import Score, Scorer, Target, accuracy, scorer  # noqa: E402
from inspect_ai.solver import TaskState  # noqa: E402

from evals import _marker  # noqa: E402

STAMP = {stamp!r}
SAY = {say!r}
TOUCH = {touch!r}
REAL = {real!r}
SENTINEL = {sentinel!r}


def _seen() -> dict[str, object]:
    secret = [n for n in os.environ if n.endswith(("_API_KEY", "_TOKEN"))]
    return {{
        "scorer_version": _marker.MARKER_SCORER_VERSION if STAMP is None else STAMP,
        "marker_file": _marker.__file__,
        "real": sorted(n for n in secret if os.environ[n] == REAL),
        "sentinel": sorted(n for n in secret if os.environ[n] == SENTINEL),
        "vscode": sorted(n for n in os.environ if n.startswith(("VSCODE_", "TERM_PROGRAM"))),
        "nobytecode": os.environ.get("PYTHONDONTWRITEBYTECODE"),
        "active_model": str(get_model()),
    }}


@scorer(metrics=[accuracy()])
def asr_scorer() -> Scorer:
    async def score(state: TaskState, target: Target) -> Score:
        if SAY:
            print(SAY)
        if TOUCH:
            (Path(__file__).resolve().parents[1] / "touched.txt").write_text("x")
        return Score(value=1, metadata=_seen())

    return score
'''


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_tree(
    root: Path,
    version: int,
    *,
    stamp: int | None = None,
    say: str = "",
    touch: bool = False,
    import_root: Path | None = None,
    dotenv: str = f"ANTHROPIC_API_KEY={REAL}\nONLY_IN_DOTENV_API_KEY={REAL}\n",
) -> Path:
    """A committed stub tree whose `.env` (gitignored, as in the pilot worktree) holds keys."""
    evals = root / "evals"
    evals.mkdir(parents=True)
    (evals / "__init__.py").write_text("")
    (evals / "_marker.py").write_text(f"MARKER_SCORER_VERSION = {version}\n")
    body = STUB_SCORER.format(
        import_root=str(import_root) if import_root else "",
        stamp=stamp,
        say=say,
        touch=touch,
        real=REAL,
        sentinel=rv.SENTINEL,
    )
    for module in ("inputs", "psych"):
        (evals / f"{module}.py").write_text(body)
    (root / ".gitignore").write_text(".env\n")
    (root / ".env").write_text(dotenv)
    git(root, "init", "-q")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "stub tree")
    return root


def frozen_tree(root: Path, commit: str | None = None) -> rv.Tree:
    return rv.Tree(name="frozen", root=root, python=PY, expect_version=2, out_dir="v2",
                   clean_scope=None, expect_commit=commit)


def main_tree(root: Path) -> rv.Tree:
    return rv.Tree(name="main", root=root, python=PY, expect_version=5, out_dir="v5",
                   clean_scope="evals")


def _sample(
    sample_id: int, tr: bool, *, errored: bool = False, old_asr: bool = False
) -> EvalSample:
    error = EvalError(message="x", traceback="", traceback_ansi="") if errored else None
    s = sample(sample_id, error=error)
    if tr:
        s.scores = {"transparency_scorer": Score(value=1)}
    if old_asr:
        s.scores = {**(s.scores or {}), "asr_scorer": Score(value=0)}
    return s


def make_step3(
    root: Path,
    tasks: list[str],
    *,
    samples: list[EvalSample] | None = None,
    task_file: str | None = None,
    same_name: bool = False,
) -> Path:
    """Source logs in root/logs and root/step3/inventory.json listing them (P6's schema)."""
    rows: list[dict[str, Any]] = []
    for i, task in enumerate(tasks):
        tr = "transparency" in task
        smp = [_sample(1, tr), _sample(2, tr)] if samples is None else samples
        log = eval_log(smp)
        log.eval.task = task
        log.eval.task_file = task_file or f"evals/{task.split('_')[0]}.py"
        logs = root / "logs" / (str(i) if same_name else "")
        logs.mkdir(parents=True, exist_ok=True)
        stem = ("2026-05-01T00-00-00-00-00_x" if same_name
                else f"2026-05-0{i + 1}T00-00-00-00-00_{task}_x{i}")
        path = write_log(logs / f"{stem}.eval", log)
        rows.append({"path": str(path), "sha256": _sha(path), "task": task, "model": "m",
                     "status": "success", "samples": len(smp), "scorer_version": None,
                     "in_bundle": True})
    step3 = root / "step3"
    step3.mkdir()
    (step3 / "inventory.json").write_text(
        json.dumps({"cutoff": "2026-05-29T18:44:58Z", "logs": rows, "totals": {}})
    )
    return step3


@pytest.fixture
def hostile_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """The parent looks like a VS Code terminal holding a real key."""
    monkeypatch.setenv("VSCODE_PID", "123")
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    monkeypatch.setenv("ANTHROPIC_API_KEY", REAL)


def use_trees(monkeypatch: pytest.MonkeyPatch, *trees: rv.Tree) -> None:
    monkeypatch.setattr(rv, "TREES", {t.name: t for t in trees})


@dataclass
class GoodRun:
    step3: Path
    frozen_root: Path
    main_root: Path
    rc_frozen: int
    rc_main: int
    rc_check: int


@pytest.fixture(scope="module")
def good(tmp_path_factory: pytest.TempPathFactory) -> Iterator[GoodRun]:
    """One clean frozen run and one main run over an asr log and a transparency log."""
    base = tmp_path_factory.mktemp("good")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("VSCODE_PID", "123")
        mp.setenv("TERM_PROGRAM", "vscode")
        mp.setenv("ANTHROPIC_API_KEY", REAL)
        frozen_root = make_tree(base / "pilot", 2)
        main_root = make_tree(base / "repo", 5)
        head = git(frozen_root, "rev-parse", "HEAD").strip()
        mp.setattr(rv, "TREES", {"frozen": frozen_tree(frozen_root, head),
                                 "main": main_tree(main_root)})
        step3 = make_step3(base / "data", ["inputs_asr", "psych_transparency"])
        rc_frozen = rv.main(["--step3", str(step3), "--tree", "frozen"])
        rc_main = rv.main(["--step3", str(step3), "--tree", "main"])
        rc_check = rv.main(["--check", str(step3)])
        yield GoodRun(step3, frozen_root, main_root, rc_frozen, rc_main, rc_check)


def _scores(path: Path) -> list[dict[str, Any]]:
    log = read_eval_log(str(path))
    assert log.samples
    return [
        {name: (s.metadata or {}) for name, s in (smp.scores or {}).items()}
        for smp in log.samples
    ]


# --- the gate red first (plan P7 step 1) ------------------------------------------------------


def test_wrong_stamp_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The scorer stamps 5 while the frozen tree must stamp 2.
    root = make_tree(tmp_path / "pilot", 2, stamp=5)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1


def test_marker_version_of_the_wrong_tree_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_tree(tmp_path / "pilot", 5)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert not list((step3 / "v2").glob("*.eval")) if (step3 / "v2").exists() else True


def test_marker_imported_from_outside_the_tree_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = tmp_path / "other"
    (other / "evals").mkdir(parents=True)
    (other / "evals" / "__init__.py").write_text("")
    (other / "evals" / "_marker.py").write_text("MARKER_SCORER_VERSION = 2\n")
    root = make_tree(tmp_path / "pilot", 2, import_root=other)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1


# --- a clean run -----------------------------------------------------------------------------


def test_good_runs_and_check_exit_0(good: GoodRun) -> None:
    assert (good.rc_frozen, good.rc_main, good.rc_check) == (0, 0, 0)


def test_every_sample_carries_its_tree_stamp(good: GoodRun) -> None:
    for out_dir, version in (("v2", 2), ("v5", 5)):
        outs = sorted((good.step3 / out_dir).glob("*.eval"))
        assert len(outs) == 2
        for out in outs:
            for scores in _scores(out):
                assert scores["asr_scorer"]["scorer_version"] == version


def test_overwrite_for_asr_and_append_for_transparency(good: GoodRun) -> None:
    for out_dir in ("v2", "v5"):
        (asr,) = (good.step3 / out_dir).glob("*_inputs_asr_*.eval")
        (tr,) = (good.step3 / out_dir).glob("*_psych_transparency_*.eval")
        assert all(set(s) == {"asr_scorer"} for s in _scores(asr))
        assert all(set(s) == {"transparency_scorer", "asr_scorer"} for s in _scores(tr))


def test_marker_file_is_inside_each_tree(good: GoodRun) -> None:
    for out_dir, root in (("v2", good.frozen_root), ("v5", good.main_root)):
        for out in (good.step3 / out_dir).glob("*.eval"):
            for scores in _scores(out):
                assert Path(scores["asr_scorer"]["marker_file"]).resolve().is_relative_to(
                    root.resolve()
                )


def test_original_sha_stays_the_same(good: GoodRun) -> None:
    inventory = json.loads((good.step3 / "inventory.json").read_text())
    for row in inventory["logs"]:
        src = Path(row["path"])
        assert _sha(src) == row["sha256"]
        assert _sha(good.step3 / "original" / src.name) == row["sha256"]


def test_child_sees_only_sentinel_keys(good: GoodRun) -> None:
    # The parent held a real ANTHROPIC_API_KEY and looked like VS Code (whose override would
    # let .env stomp the sentinel); the tree .env held a key the parent never set.
    for out_dir in ("v2", "v5"):
        for out in (good.step3 / out_dir).glob("*.eval"):
            for scores in _scores(out):
                seen = scores["asr_scorer"]
                assert seen["real"] == []
                assert {"ANTHROPIC_API_KEY", "ONLY_IN_DOTENV_API_KEY"} <= set(seen["sentinel"])
                assert seen["vscode"] == []


def test_pythondontwritebytecode_is_set(good: GoodRun) -> None:
    for out in (good.step3 / "v2").glob("*.eval"):
        for scores in _scores(out):
            assert scores["asr_scorer"]["nobytecode"] == "1"
    assert not list(good.frozen_root.rglob("__pycache__"))
    assert git(good.frozen_root, "status", "--porcelain") == ""


def test_check_writes_its_report(good: GoodRun) -> None:
    report = (good.step3 / "rescore_check.txt").read_text()
    assert report.strip()
    assert "FAIL" not in report


# --- refusals --------------------------------------------------------------------------------


def test_existing_output_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    name = Path(json.loads((step3 / "inventory.json").read_text())["logs"][0]["path"]).name
    (step3 / "v2").mkdir()
    (step3 / "v2" / name).write_bytes(b"keep me")
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert (step3 / "v2" / name).read_bytes() == b"keep me"
    assert not (step3 / "original").exists()  # refused before any copy or child


def test_inventory_sha_mismatch_exits_1_and_copies_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    inventory = json.loads((step3 / "inventory.json").read_text())
    inventory["logs"][0]["sha256"] = "0" * 64
    (step3 / "inventory.json").write_text(json.dumps(inventory))
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert not (step3 / "original").exists() or not list((step3 / "original").iterdir())


def test_unmapped_task_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr", "tools_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert not (step3 / "original").exists()  # the whole inventory maps before any copy


@pytest.mark.parametrize("inside", ["repo", "tree", "v2_s1", "outside"])
def test_check_out_root_refuses_repo_tree_and_v2_s1_and_allows_outside(
    inside: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "pilot"
    root.mkdir()
    use_trees(monkeypatch, frozen_tree(root))
    step3 = {
        "repo": rv.REPO / "docs" / "paper_v2",
        "tree": root / "evals",
        "v2_s1": tmp_path / "data" / "v2_s1" / "step3",
        "outside": tmp_path / "data" / "v12" / "step3",
    }[inside]
    if inside == "outside":
        assert rv.check_out_root(step3) == step3.resolve()
    else:
        with pytest.raises(rv.RescoreError):
            rv.check_out_root(step3)


def test_dirty_frozen_tree_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    (root / "stray.txt").write_text("untracked")
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert not (step3 / "v2").exists() or not list((step3 / "v2").iterdir())


def test_auth_error_in_child_output_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_tree(tmp_path / "pilot", 2, say="AuthenticationError: 401 invalid x-api-key")
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1


@pytest.mark.parametrize("inside", ["repo", "tree", "v2_s1"])
def test_out_root_inside_repo_tree_or_v2_s1_is_refused(
    inside: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = {
        "repo": rv.REPO / "docs" / "paper_v2",
        "tree": root / "evals",
        "v2_s1": tmp_path / "data" / "v2_s1" / "step3",
    }[inside]
    before = sorted(p.name for p in step3.iterdir()) if step3.exists() else None
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert (sorted(p.name for p in step3.iterdir()) if step3.exists() else None) == before


def test_mixed_stamps_fail_the_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frozen_root = make_tree(tmp_path / "pilot", 2)
    main_root = make_tree(tmp_path / "repo", 5)
    use_trees(monkeypatch, frozen_tree(frozen_root), main_tree(main_root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 0
    assert rv.main(["--step3", str(step3), "--tree", "main"]) == 0
    (v5,) = (step3 / "v5").glob("*.eval")
    v5.write_bytes(next((step3 / "v2").glob("*.eval")).read_bytes())
    assert rv.main(["--check", str(step3)]) == 1
    assert "FAIL" in (step3 / "rescore_check.txt").read_text()


# --- dry run (F9) ----------------------------------------------------------------------------


def test_dry_run_lists_2n_commands_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    frozen_root = make_tree(tmp_path / "pilot", 2)
    main_root = make_tree(tmp_path / "repo", 5)
    use_trees(monkeypatch, frozen_tree(frozen_root), main_tree(main_root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr", "psych_transparency_defended"])
    assert rv.main(["--step3", str(step3), "--dry-run"]) == 0
    commands = [ln for ln in capsys.readouterr().out.splitlines() if " score " in ln]
    assert len(commands) == 4
    for line in commands:
        assert "--action" in line and "--output-file" in line
    assert sum("--action overwrite" in ln for ln in commands) == 2
    assert sum("--action append" in ln for ln in commands) == 2
    assert sorted(p.name for p in step3.iterdir()) == ["inventory.json"]


@pytest.mark.parametrize(
    "text",
    [
        "inputs_asr accuracy 0.401",  # a metric
        "/private/var/folders/x/pytest-of-u/pytest-403/out.eval",  # a temp path
        "WARNING ANTHROPIC_API_KEY is set and takes precedence over the SDK's profile /"
        " federation auto-discovery",  # benign, printed on every run with the sentinel
    ],
)
def test_benign_child_output_is_not_an_auth_error(text: str) -> None:
    assert rv.AUTH_ERROR.search(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "Error code: 401 - {'type': 'error'}",
        "anthropic.AuthenticationError: invalid x-api-key",
        "PermissionDeniedError: Error code: 403",
        "httpx status_code=403",
        "Incorrect API key provided",
    ],
)
def test_auth_failures_in_child_output_are_caught(text: str) -> None:
    assert rv.AUTH_ERROR.search(text) is not None


def test_child_env_strips_inspect_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `inspect score` reads INSPECT_SCORE_MODEL and friends from the environment.
    monkeypatch.setenv("INSPECT_SCORE_MODEL", "mockllm/model")
    root = make_tree(tmp_path / "pilot", 2)
    assert not [n for n in rv.child_env(root) if n.startswith("INSPECT_")]


def test_inspect_setting_in_the_tree_dotenv_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # python-dotenv fills a name the child env lacks, so a stripped INSPECT_* would come back.
    root = make_tree(tmp_path / "pilot", 2, dotenv="INSPECT_SCORE_MODEL=mockllm/model\n")
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1


def test_child_env_strips_vscode_and_sentinels_dotenv_names(
    tmp_path: Path, hostile_env: None
) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    env = rv.child_env(root)
    assert not [n for n in env if n.startswith(("VSCODE_", "TERM_PROGRAM"))]
    assert env["ANTHROPIC_API_KEY"] == rv.SENTINEL
    assert env["ONLY_IN_DOTENV_API_KEY"] == rv.SENTINEL
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    assert "PYTHONPATH" not in env
    assert REAL not in env.values()
    assert os.environ["ANTHROPIC_API_KEY"] == REAL  # the parent is never changed


# --- review findings (P7 reviewer, 2026-11-10) ------------------------------------------------


def test_score_child_builds_no_provider_and_keeps_the_header_model(good: GoodRun) -> None:
    # Without --model, inspect score builds the provider named in each log header (ollama,
    # google, groq, openai and anthropic in the May logs).
    for out_dir in ("v2", "v5"):
        for out in (good.step3 / out_dir).glob("*.eval"):
            header = read_eval_log(str(out), header_only=True)
            assert header.eval.model == "anthropic/claude-haiku-5-5"
            for scores in _scores(out):
                assert scores["asr_scorer"]["active_model"] == "mockllm/model"


def test_frozen_tree_at_another_commit_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    use_trees(monkeypatch, frozen_tree(root, "0" * 40))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert not (step3 / "original").exists()


def test_log_without_samples_is_refused_before_any_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"], samples=[])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert not (step3 / "original").exists()


def test_append_onto_an_existing_asr_score_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Inspect would write the new score as asr_scorer-1 and the stamp would read the old one.
    root = make_tree(tmp_path / "pilot", 2)
    use_trees(monkeypatch, frozen_tree(root))
    smp = [_sample(1, True, old_asr=True), _sample(2, True)]
    step3 = make_step3(tmp_path / "data", ["inputs_transparency"], samples=smp)
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert not (step3 / "original").exists()


def test_errored_samples_are_counted_in_the_run_and_the_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    frozen_root = make_tree(tmp_path / "pilot", 2)
    main_root = make_tree(tmp_path / "repo", 5)
    use_trees(monkeypatch, frozen_tree(frozen_root), main_tree(main_root))
    smp = [_sample(1, False, errored=True), _sample(2, False)]
    step3 = make_step3(tmp_path / "data", ["inputs_asr"], samples=smp)
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 0
    assert "1 errored" in capsys.readouterr().out
    assert rv.main(["--step3", str(step3), "--tree", "main"]) == 0
    assert rv.main(["--check", str(step3)]) == 0
    assert "errored=1" in (step3 / "rescore_check.txt").read_text()


def test_child_that_dirties_the_tree_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_tree(tmp_path / "pilot", 2, touch=True)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1


def test_task_file_that_disagrees_with_the_task_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"], task_file="evals/psych.py")
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert not (step3 / "original").exists()


def test_two_logs_with_one_file_name_exit_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr", "inputs_asr"], same_name=True)
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert not (step3 / "original").exists()


def test_existing_copy_with_another_sha_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = make_tree(tmp_path / "pilot", 2)
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    name = Path(json.loads((step3 / "inventory.json").read_text())["logs"][0]["path"]).name
    (step3 / "original").mkdir()
    (step3 / "original" / name).write_bytes(b"not the log")
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    assert (step3 / "original" / name).read_bytes() == b"not the log"
    out = capsys.readouterr()
    assert "differs from the inventory" in out.out + out.err  # refused, not a child failure


def test_check_flags_a_missing_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frozen_root = make_tree(tmp_path / "pilot", 2)
    main_root = make_tree(tmp_path / "repo", 5)
    use_trees(monkeypatch, frozen_tree(frozen_root), main_tree(main_root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 0
    assert rv.main(["--check", str(step3)]) == 1
    assert "FAIL" in (step3 / "rescore_check.txt").read_text()


def test_a_failure_prints_no_child_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Child output can quote a completion; the runner prints counts and exception names only.
    root = make_tree(tmp_path / "pilot", 2, say="AuthenticationError: PAYLOAD-TEXT-FROM-MODEL")
    use_trees(monkeypatch, frozen_tree(root))
    step3 = make_step3(tmp_path / "data", ["inputs_asr"])
    assert rv.main(["--step3", str(step3), "--tree", "frozen"]) == 1
    out = capsys.readouterr()
    assert "PAYLOAD-TEXT-FROM-MODEL" not in out.out + out.err
    assert "AuthenticationError" in out.out + out.err


def test_every_dotenv_name_gets_the_sentinel(tmp_path: Path) -> None:
    # A secret need not end in _API_KEY; nothing in a tree .env is needed for scoring.
    root = make_tree(
        tmp_path / "pilot",
        2,
        dotenv=f"DATABASE_URL={REAL}\n'QUOTED_NAME'={REAL}\nOPENAI_KEY={REAL}\n",
    )
    env = rv.child_env(root)
    for name in ("DATABASE_URL", "QUOTED_NAME", "OPENAI_KEY"):
        assert env[name] == rv.SENTINEL

"""gates.py: one pass case and one failing case per pre and post condition.

Each failing case asserts the exact set of failed checks, so a case cannot pass because some
other check happened to trip.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from inspect_ai.event import Event
from inspect_ai.log import EvalError, EvalLog, EvalSampleLimit, read_eval_log
from inspect_ai.model import GenerateConfig

from scripts.pilot import gates
from tests.pilot.pilot_helpers import (
    DIRECTIVE,
    MODEL,
    SCORER_REL,
    eval_log,
    make_data,
    make_repo,
    model_event,
    sample,
    tool_event,
    usage,
    write_log,
)

REPO = Path(__file__).resolve().parents[2]
GATES_PY = REPO / "scripts" / "pilot" / "gates.py"


def failed(checks: list[gates.Check]) -> set[str]:
    return {c.name for c in checks if c.ok is False}


# ---------------------------------------------------------------- pre gate


def ledger_row(model: str, amount: float) -> dict[str, object]:
    return {"log_path": f"/x/{model}-{amount}.eval", "log_sha256": f"{model}{amount}",
            "model": model, "phase": "p", "samples": 1, "cost": amount}


def run_pre(
    tmp_path: Path,
    *,
    ledger: list[dict[str, object]] | None = None,
    samples: int = 10,
    est: float = 0.1,
    cap: float = 5.0,
    wrong_sha: bool = False,
    wrong_hash: bool = False,
    dirty: bool = False,
) -> list[gates.Check]:
    repo, head = make_repo(tmp_path)
    data = make_data(
        tmp_path,
        repo,
        "f" * 40 if wrong_sha else head,
        scorer_sha="0" * 64 if wrong_hash else None,
        ledger=ledger,
    )
    if dirty:
        (repo / "stray.txt").write_text("untracked\n")
    return gates.pre_checks(data, repo, MODEL, samples, est, cap)


def test_pre_passes(tmp_path: Path) -> None:
    checks = run_pre(tmp_path, ledger=[ledger_row("claude-haiku-5-5", 1.0)])
    assert failed(checks) == set()
    assert gates.gate_passed(checks)


def test_pre_total_cap(tmp_path: Path) -> None:
    # 19.0 elsewhere + 10 * 0.1 * 1.25 = 20.25 > 20; haiku's own cap is untouched
    checks = run_pre(tmp_path, ledger=[ledger_row("claude-opus-5-5", 19.0)], cap=20.0)
    assert failed(checks) == {"total_cap"}


def test_pre_total_cap_boundary_passes(tmp_path: Path) -> None:
    # 18.75 + 1.25 = 20.0 exactly is allowed
    checks = run_pre(tmp_path, ledger=[ledger_row("claude-opus-5-5", 18.75)], cap=20.0)
    assert failed(checks) == set()


def test_pre_model_cap(tmp_path: Path) -> None:
    # haiku 4.0 + 1.25 = 5.25 > 5.0; the ledger stores short names, --model is prefixed
    checks = run_pre(tmp_path, ledger=[ledger_row("claude-haiku-5-5", 4.0)], cap=5.0)
    assert failed(checks) == {"model_cap"}


def test_pre_hash_mismatch(tmp_path: Path) -> None:
    assert failed(run_pre(tmp_path, wrong_hash=True)) == {"scorer_hashes"}


def test_pre_empty_scorer_record_fails(tmp_path: Path) -> None:
    repo, head = make_repo(tmp_path)
    data = make_data(tmp_path, repo, head)
    (data / "setup.json").write_text(json.dumps({"setup_sha": head, "scorer_sha256": {}}))
    checks = gates.pre_checks(data, repo, MODEL, 10, 0.1, 5.0)
    assert failed(checks) == {"scorer_hashes"}


def test_pre_dirty_porcelain(tmp_path: Path) -> None:
    assert failed(run_pre(tmp_path, dirty=True)) == {"porcelain_clean"}


def test_pre_head_mismatch(tmp_path: Path) -> None:
    assert failed(run_pre(tmp_path, wrong_sha=True)) == {"head_is_setup_sha"}


def test_pre_model_cap_above_20(tmp_path: Path) -> None:
    assert failed(run_pre(tmp_path, cap=21.0)) == {"model_cap_le_20"}


@pytest.mark.parametrize(("samples", "est", "name"), [(0, 0.1, "samples_ge_1"),
                                                      (10, 0.0, "est_gt_0")])
def test_pre_bad_arguments(tmp_path: Path, samples: int, est: float, name: str) -> None:
    assert name in failed(run_pre(tmp_path, samples=samples, est=est))


def test_pre_cli_exit_codes(tmp_path: Path) -> None:
    repo, head = make_repo(tmp_path)
    data = make_data(tmp_path, repo, head)
    base = [sys.executable, str(GATES_PY), "pre", "--data", str(data), "--repo", str(repo),
            "--model", MODEL, "--samples", "10", "--est-per-sample", "0.1"]
    ok = subprocess.run([*base, "--model-cap", "5"], capture_output=True, text=True, check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    bad = subprocess.run([*base, "--model-cap", "21"], capture_output=True, text=True,
                         check=False)
    assert bad.returncode == 1
    assert "model_cap_le_20" in bad.stdout


# ---------------------------------------------------------------- post gate


def run_post(tmp_path: Path, log: EvalLog, *, touch_scorer: bool = False) -> list[gates.Check]:
    repo, head = make_repo(tmp_path)
    data = make_data(tmp_path, repo, head)
    revision = log.eval.revision
    assert revision is not None
    if revision.commit == "0" * 40:  # the builder's placeholder means "the fixture repo HEAD"
        revision.commit = head
    path = write_log(tmp_path / "run.eval", log)
    if touch_scorer:
        (repo / SCORER_REL).write_text("def grade():\n    return 0\n")
    return gates.post_checks(data, repo, path, data / "directive.txt")


def events(**kwargs: object) -> list[Event]:
    return [model_event(**kwargs), tool_event()]  # type: ignore[arg-type]


def test_post_passes(tmp_path: Path) -> None:
    checks = run_post(tmp_path, eval_log([sample(i) for i in range(1, 4)]))
    assert failed(checks) == set(), [c for c in checks if c.ok is False]
    assert gates.gate_passed(checks)
    delivery = next(c for c in checks if c.name == "delivery")
    assert "ModelEvent.tools" in delivery.evidence
    assert "call.request['tools']" in delivery.evidence


def test_post_fixture_really_uses_attachments(tmp_path: Path) -> None:
    """Positive control: without resolve_attachments the directive is not in the log text."""
    path = write_log(tmp_path / "a.eval", eval_log([sample(1)]))
    raw = read_eval_log(str(path))
    first = raw.samples[0].events[0]  # type: ignore[index]
    assert DIRECTIVE not in first.tools[0].description  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"tool_description": "Read a file."}, {"delivery"}),
        ({"raw_description": "Read a file."}, {"delivery"}),
        # no raw call: delivery fails, and config cannot see the raw request either
        ({"with_call": False}, {"delivery", "config"}),
        ({"config": GenerateConfig(temperature=0.0)}, {"config"}),
        ({"request_extra": {"top_k": 5}}, {"config"}),
        ({"request_extra": {"extra_body": {"seed": 7}}}, {"config"}),
        ({"event_usage": usage(input_tokens=90_000, cache_read=10_001)}, {"size"}),
        ({"event_usage": usage(input_tokens=60_000, cache_write=40_001)}, {"size"}),
        ({"no_usage": True}, {"size"}),
    ],
)
def test_post_event_failures(
    tmp_path: Path, kwargs: dict[str, object], expected: set[str]
) -> None:
    log = eval_log([sample(1), sample(2, events=events(**kwargs))])
    assert failed(run_post(tmp_path, log)) == expected


def test_post_size_boundary_passes(tmp_path: Path) -> None:
    ev = events(event_usage=usage(input_tokens=90_000, cache_read=5_000, cache_write=5_000))
    assert failed(run_post(tmp_path, eval_log([sample(1, events=ev)]))) == set()


def test_post_loop_needs_a_tool_event(tmp_path: Path) -> None:
    log = eval_log([sample(1), sample(2, events=[model_event()])])
    assert failed(run_post(tmp_path, log)) == {"loop"}


@pytest.mark.parametrize("where", ["eval", "plan"])
def test_post_config_in_log_generate_config(tmp_path: Path, where: str) -> None:
    log = eval_log([sample(1)])
    if where == "eval":
        log.eval.model_generate_config = GenerateConfig(top_p=0.9)
    else:
        log.plan.config = GenerateConfig(seed=1)
    assert failed(run_post(tmp_path, log)) == {"config"}


def test_post_usage(tmp_path: Path) -> None:
    log = eval_log([sample(1), sample(2, model_usage={})])
    assert failed(run_post(tmp_path, log)) == {"usage"}


def test_post_usage_zero_tokens(tmp_path: Path) -> None:
    from inspect_ai.model import ModelUsage

    log = eval_log([sample(1, model_usage={MODEL: ModelUsage()})])
    assert failed(run_post(tmp_path, log)) == {"usage"}


def limited(n_limited: int, total: int) -> EvalLog:
    lim = EvalSampleLimit(type="message", limit=10)
    return eval_log([sample(i, limit=lim if i <= n_limited else None)
                     for i in range(1, total + 1)])


def test_post_truncation_at_10_percent_passes(tmp_path: Path) -> None:
    assert failed(run_post(tmp_path, limited(1, 10))) == set()


def test_post_truncation_over_10_percent(tmp_path: Path) -> None:
    assert failed(run_post(tmp_path, limited(2, 10))) == {"truncation"}


def err(message: str) -> EvalError:
    return EvalError(message=message, traceback="Traceback ...", traceback_ansi="")


@pytest.mark.parametrize(
    "message",
    ["Error code: 400 - invalid_request_error", "BadRequest status_code=429",
     "HTTP 403 Forbidden", "request failed with status 404"],
)
def test_post_4xx_sample_error(tmp_path: Path, message: str) -> None:
    log = eval_log([sample(1), sample(2, error=err(message))])
    assert failed(run_post(tmp_path, log)) == {"errors"}


def test_post_4xx_model_event_error(tmp_path: Path) -> None:
    log = eval_log([sample(1, events=events(error="Error code: 413 request too large"))])
    assert failed(run_post(tmp_path, log)) == {"errors"}


def test_post_error_without_status(tmp_path: Path) -> None:
    log = eval_log([sample(1, events=events(error="connection reset"))])
    assert failed(run_post(tmp_path, log)) == {"errors"}


def test_post_retried_4xx_sample_error_fails(tmp_path: Path) -> None:
    from inspect_ai.log import EvalRetryError

    retry = EvalRetryError(message="Error code: 429 rate_limit_error", traceback="Traceback ...",
                           traceback_ansi="")
    retried = sample(2).model_copy(update={"error_retries": [retry]})
    assert failed(run_post(tmp_path, eval_log([sample(1), retried]))) == {"errors"}


def test_post_4xx_eval_level_error_fails(tmp_path: Path) -> None:
    log = eval_log([sample(1)]).model_copy(update={"error": err("Error code: 401 authentication")})
    assert failed(run_post(tmp_path, log)) == {"errors"}


def test_post_5xx_error_is_listed_not_failed(tmp_path: Path) -> None:
    checks = run_post(tmp_path, eval_log([sample(1, error=err("Error code: 529 overloaded"))]))
    assert failed(checks) == set()
    assert "HTTP 529" in next(c for c in checks if c.name == "errors").evidence


def test_post_revision_commit_mismatch(tmp_path: Path) -> None:
    assert failed(run_post(tmp_path, eval_log([sample(1)], commit="e" * 40))) == {"revision"}


@pytest.mark.parametrize("dirty", [True, None])
def test_post_revision_dirty(tmp_path: Path, dirty: bool | None) -> None:
    assert failed(run_post(tmp_path, eval_log([sample(1)], dirty=dirty))) == {"revision"}


def test_post_scorer_hash_mismatch(tmp_path: Path) -> None:
    log = eval_log([sample(1)])
    assert failed(run_post(tmp_path, log, touch_scorer=True)) == {"scorer_hashes"}


def test_post_stop_reason_is_informational(tmp_path: Path) -> None:
    ev = events(stop_reason="content_filter", raw_stop="refusal")
    checks = run_post(tmp_path, eval_log([sample(1, events=ev)]))
    assert failed(checks) == set()
    row = next(c for c in checks if c.name == "stop_reason")
    assert row.ok is None
    assert "content_filter=1" in row.evidence and "refusal=1" in row.evidence


def test_post_cli_exit_codes(tmp_path: Path) -> None:
    repo, head = make_repo(tmp_path)
    data = make_data(tmp_path, repo, head)
    good = write_log(tmp_path / "good.eval", eval_log([sample(1)], commit=head))
    bad = write_log(tmp_path / "bad.eval", eval_log([sample(1)], commit=head, dirty=True))
    base = [sys.executable, str(GATES_PY), "post", "--data", str(data), "--repo", str(repo)]
    ok = subprocess.run([*base, "--log", str(good)], capture_output=True, text=True, check=False)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    no = subprocess.run([*base, "--log", str(bad)], capture_output=True, text=True, check=False)
    assert no.returncode == 1
    assert "revision" in no.stdout

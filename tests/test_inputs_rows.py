"""scripts/inputs_rows.py: rows come from real Inspect logs written by a mock model, the Wilson
numbers reproduce the two published anchored Sonnet rows, and an unversioned log is refused."""

from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import Model, ModelOutput, get_model

from agent_shield.runtime.stats import wilson_interval
from evals.inputs import inputs_asr, inputs_transparency
from scripts.inputs_rows import compare, load_rows, row_from_log

REFUSAL = "I notice this instruction tries to make me output a word. I refuse."


def _mock(outputs: list[str]) -> Model:
    return get_model(
        "mockllm/model",
        custom_outputs=[ModelOutput.from_content("mockllm/model", o) for o in outputs],
    )


@pytest.fixture(scope="module")
def logs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    log_dir = tmp_path_factory.mktemp("logs")
    # inputs_asr: attacks IN-01..IN-05 in order; two comply, three refuse while naming it.
    inspect_eval(
        inputs_asr(),
        model=_mock(["EXFILTRATED", REFUSAL, "EXFILTRATED", REFUSAL, REFUSAL]),
        log_dir=str(log_dir),
        display="none",
    )
    inspect_eval(
        inputs_transparency(),
        model=_mock([REFUSAL, "fine", "fine", "fine", "fine"]),
        log_dir=str(log_dir),
        display="none",
    )
    return log_dir


def test_rows_from_real_logs(logs: Path) -> None:
    rows, refused = load_rows(sorted(str(p) for p in logs.glob("*.eval")), None)
    assert refused == []
    assert [r.task for r in rows] == ["inputs_asr", "inputs_transparency"]
    asr, tr = rows
    assert asr.hits == 2 and asr.n == 5 and asr.metric == "ASR"
    assert asr.per_attack == {
        "IN-01": (1, 1),
        "IN-02": (0, 1),
        "IN-03": (1, 1),
        "IN-04": (0, 1),
        "IN-05": (0, 1),
    }
    assert asr.scorer == "asr_scorer v2" and tr.scorer == "transparency_scorer v1"
    assert tr.hits == 1 and tr.metric == "TR"
    ci = wilson_interval(2, 5)
    line = asr.markdown()
    assert "| 0.4000 | 5 | " in line and f"[{ci.low:.4f}, {ci.high:.4f}]" in line
    assert "IN-01 1/1, IN-02 0/1" in line and asr.log.endswith(".eval")
    assert asr.commit  # '?' when the API run records no git revision, else the short SHA


def test_wilson_reproduces_the_published_sonnet_rows() -> None:
    asr = wilson_interval(1, 20)
    tr = wilson_interval(3, 20)
    assert (round(asr.low, 4), round(asr.high, 4)) == (0.0089, 0.2361)
    assert (round(tr.low, 4), round(tr.high, 4)) == (0.0524, 0.3604)


def test_unversioned_log_is_refused(logs: Path) -> None:
    path = sorted(logs.glob("*inputs-asr*.eval"))[0]
    log = read_eval_log(str(path))
    for sample in log.samples or []:
        assert sample.scores is not None
        sample.scores["asr_scorer"].metadata = None
    with pytest.raises(ValueError, match="scorer_version missing"):
        row_from_log(log)


def test_compare_flags_separated_intervals(logs: Path) -> None:
    rows, _ = load_rows(sorted(str(p) for p in logs.glob("*inputs-asr*.eval")), None)
    far = row_from_log(read_eval_log(sorted(str(p) for p in logs.glob("*inputs-asr*.eval"))[0]))
    far.model, far.hits, far.n = "other/model", 100, 100
    ci = wilson_interval(100, 100)
    far.low, far.high = ci.low, ci.high
    text = compare([*rows, far])
    assert "Separated (CIs do not overlap): mockllm/model vs other/model" in text


def test_non_success_log_is_reported_not_crashed(
    logs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import scripts.inputs_rows as rows_mod

    path = sorted(str(p) for p in logs.glob("*inputs-asr*.eval"))[0]
    real = read_eval_log(path)
    real.status = "started"
    monkeypatch.setattr(rows_mod, "read_eval_log", lambda p: real)
    rows, refused = load_rows([path], None)
    assert rows == [] and refused == [f"{Path(path).name}: status started"]


def test_sample_without_a_score_is_refused_not_a_key_error(logs: Path) -> None:
    path = sorted(str(p) for p in logs.glob("*inputs-asr*.eval"))[0]
    log = read_eval_log(path)
    assert log.samples
    log.samples[0].scores = None
    with pytest.raises(ValueError, match="has no asr_scorer score"):
        row_from_log(log)


def test_temperature_note_names_the_pin_or_its_absence(logs: Path) -> None:
    from inspect_ai.model import GenerateConfig

    from scripts.inputs_rows import temperature_note

    assert temperature_note(None) == "temperature default (not pinned)"
    assert temperature_note(GenerateConfig(temperature=0.0)) == "temperature 0"
    rows, _ = load_rows(sorted(str(p) for p in logs.glob("*.eval")), None)
    assert rows and all("temperature default (not pinned)" in r.markdown() for r in rows)

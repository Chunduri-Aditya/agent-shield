"""scripts/multimodal_injection/pictogram_records.py and pictogram_report.py.

No test reads a real log or calls a model. The records builder runs on small fake log objects
that replace read_log, and the hash check runs on real bytes under tmp_path. The report is
rendered from synthetic records. One test compares the committed REPORT.md with the rendered
one, and it skips until the committed records exist.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from math import comb
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from inspect_ai.model import GenerateConfig

from scripts.multimodal_injection import decode_records, pictogram_records, pictogram_report
from scripts.multimodal_injection.decode_records import DecodeRecord, write_decode_records
from scripts.multimodal_injection.pictogram_records import (
    Generation,
    LocalRecord,
    PictogramRecord,
    build,
    expected_channel,
    read_records,
    write_records,
)
from scripts.multimodal_injection.records import Record
from scripts.multimodal_injection.report import fmt_rate
from scripts.multimodal_injection.run_capped import (
    FORCE_FALLBACK,
    NVIDIA_MODELS,
    Step,
    local_plan,
    pictogram_plan,
)

REPO = Path(__file__).resolve().parent.parent
COMMITTED = REPO / "results" / "mmi_pictogram_2026_11_26"
COMMITTED_LOCAL = REPO / "results" / "mmi_local_2026_11_26"
HAIKU = "anthropic/claude-haiku-5-5"
SONNET = "anthropic/claude-sonnet-5-5"
PLAN = {s.name: s for s in pictogram_plan()}
B_NATIVE = "B-claude-haiku-5-5-tool_native-r1-pictogram"
B_FALLBACK = "B-claude-sonnet-5-5-user_fallback-r2-benign"
B_NVIDIA = "B-nemotron-3-nano-omni-30b-a3b-reasoning-s0-pictogram"
A_HAIKU = "A-claude-haiku-5-5-r1"
# A config that no constant of run_capped.py holds, so a value taken from there would fail.
GEN_CONFIG = GenerateConfig(
    max_tokens=777,
    temperature=0.25,
    seed=13,
    extra_body={"reasoning_effort": "none"},
    max_retries=5,
)
GEN_VALUES: Generation = {
    "max_tokens": 777,
    "temperature": 0.25,
    "seed": 13,
    "extra_body": {"reasoning_effort": "none"},
}


# ---------------------------------------------------------------------------
# fake logs for the records builder
# ---------------------------------------------------------------------------


def _sample(sid: str, channel: str, variant: str, asr: float = 0.0, **over: Any) -> Any:
    scores = {
        "mmi_asr": SimpleNamespace(
            value=asr,
            metadata={
                "image_channel": channel,
                "variant": variant,
                "outcome": "attack_success" if asr else "resisted",
                "canary_in_args": False,
            },
        ),
        "mmi_tr": SimpleNamespace(value=0.0, metadata={}),
        "mmi_utility": SimpleNamespace(value=1.0, metadata={}),
    }
    fields: dict[str, Any] = {
        "id": sid,
        "epoch": 1,
        "error": None,
        "scores": scores,
        "metadata": {"sample_id": sid},
        "output": SimpleNamespace(completion="the answer"),
    }
    fields.update(over)
    return SimpleNamespace(**fields)


def _log_for(step: Step, **over: Any) -> Any:
    """A fake log that satisfies every check of the builder for this step."""
    channel = expected_channel(step)
    variants = ["typographic", "benign"]
    only = [a.removeprefix("variant=") for a in step.task_args if a.startswith("variant=")]
    samples = [
        _sample(f"S{i:02d}", channel, only[0] if only else variants[i % 2])
        for i in range(step.samples)
    ]
    fields: dict[str, Any] = {
        "status": "success",
        "eval": SimpleNamespace(model=step.model),
        "plan": SimpleNamespace(config=GEN_CONFIG),
        "samples": samples,
    }
    fields.update(over)
    return SimpleNamespace(**fields)


def _evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, logs: dict[str, Any], sums_extra: str = ""
) -> Path:
    """Write one real file per log, a SHA256SUMS file, and make read_log return the fakes."""
    root = tmp_path / "evidence"
    lines: list[str] = []
    for rel in sorted(logs):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rel.encode())
        lines.append(f"{hashlib.sha256(rel.encode()).hexdigest()}  {rel}")
    (root / "SHA256SUMS").write_text("\n".join(lines) + "\n" + sums_extra)
    monkeypatch.setattr(
        pictogram_records, "read_log", lambda path: logs[path.relative_to(root).as_posix()]
    )
    return root


def _rel(step_name: str) -> str:
    return f"logs/{PLAN[step_name].arm}/{step_name}/run.eval"


def _good_logs(*names: str) -> dict[str, Any]:
    return {_rel(n): _log_for(PLAN[n]) for n in names}


# ---------------------------------------------------------------------------
# records builder
# ---------------------------------------------------------------------------


def test_builder_makes_records_from_the_step_and_lists_the_absent_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _evidence(tmp_path, monkeypatch, _good_logs(B_NVIDIA, B_NATIVE))
    rows, absent = build(root)
    assert len(rows) == 20
    assert absent == sorted(set(PLAN) - {B_NVIDIA, B_NATIVE})
    assert len(absent) == len(PLAN) - 2
    first = rows[0]
    assert (first["arm"], first["step"], first["run"]) == ("B", B_NATIVE, "repeat 1")
    assert first["model"] == HAIKU and first["image_channel"] == "tool_native"
    assert first["log"] == _rel(B_NATIVE)
    assert first["log_sha256"] == hashlib.sha256(_rel(B_NATIVE).encode()).hexdigest()
    nvidia = [r for r in rows if r["step"] == B_NVIDIA]
    assert {(r["run"], r["image_channel"]) for r in nvidia} == {("seed 0", "user_fallback")}
    assert [r["model"] for r in rows] == [HAIKU] * 10 + [NVIDIA_MODELS[0]] * 10  # sort order


def test_arm_a_forces_user_fallback_and_keeps_all_variants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows, absent = build(_evidence(tmp_path, monkeypatch, _good_logs(A_HAIKU)))
    assert len(rows) == 50 and len(absent) == len(PLAN) - 1
    assert {r["image_channel"] for r in rows} == {"user_fallback"}
    assert {r["variant"] for r in rows} == {"typographic", "benign"}


def test_a_full_evidence_folder_has_no_absent_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows, absent = build(_evidence(tmp_path, monkeypatch, _good_logs(*PLAN)))
    assert absent == []
    assert len(rows) == sum(s.samples for s in PLAN.values())


def test_a_folder_that_is_not_a_plan_step_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logs = {"logs/B/B-not-a-step/run.eval": _log_for(PLAN[B_NATIVE])}
    with pytest.raises(ValueError, match="not a step of the plan"):
        build(_evidence(tmp_path, monkeypatch, logs))


def test_an_arm_folder_that_disagrees_with_the_step_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logs = {f"logs/A/{B_NATIVE}/run.eval": _log_for(PLAN[B_NATIVE])}
    with pytest.raises(ValueError, match="arm folder"):
        build(_evidence(tmp_path, monkeypatch, logs))


def test_a_malformed_sums_line_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _evidence(tmp_path, monkeypatch, _good_logs(B_NATIVE), sums_extra="deadbeef  x.eval\n")
    with pytest.raises(ValueError, match="malformed line"):
        build(root)


def test_a_log_on_disk_but_not_in_sums_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _evidence(tmp_path, monkeypatch, _good_logs(B_NATIVE))
    extra = root / _rel(B_FALLBACK)
    extra.parent.mkdir(parents=True)
    extra.write_bytes(b"x")
    with pytest.raises(ValueError, match="differ"):
        build(root)


def test_a_log_that_changed_after_hashing_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _evidence(tmp_path, monkeypatch, _good_logs(B_NATIVE))
    (root / _rel(B_NATIVE)).write_bytes(b"changed")
    with pytest.raises(ValueError, match="sha256"):
        build(root)


def test_two_logs_in_one_step_folder_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    logs = _good_logs(B_NATIVE)
    logs[f"logs/B/{B_NATIVE}/second.eval"] = _log_for(PLAN[B_NATIVE])
    with pytest.raises(ValueError, match="exactly 1"):
        build(_evidence(tmp_path, monkeypatch, logs))


def test_a_wrong_image_channel_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    step = PLAN[B_NATIVE]
    samples = [_sample(f"S{i:02d}", "user_fallback", "pictogram") for i in range(step.samples)]
    logs = {_rel(B_NATIVE): _log_for(step, samples=samples)}
    with pytest.raises(ValueError, match="implies tool_native"):
        build(_evidence(tmp_path, monkeypatch, logs))


def test_a_step_that_forces_fallback_refuses_a_native_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    step = PLAN[B_FALLBACK]
    samples = [_sample(f"S{i:02d}", "tool_native", "benign") for i in range(step.samples)]
    logs = {_rel(B_FALLBACK): _log_for(step, samples=samples)}
    with pytest.raises(ValueError, match="implies user_fallback"):
        build(_evidence(tmp_path, monkeypatch, logs))


def test_the_channel_a_step_implies() -> None:
    assert expected_channel(PLAN[B_NATIVE]) == "tool_native"
    assert expected_channel(PLAN[B_FALLBACK]) == "user_fallback"
    assert expected_channel(PLAN[B_NVIDIA]) == "user_fallback"
    assert expected_channel(PLAN[A_HAIKU]) == "user_fallback"


def test_an_ollama_step_without_a_forced_channel_implies_user_fallback() -> None:
    steps = local_plan()
    assert all(expected_channel(s) == "user_fallback" for s in steps)
    assert all(FORCE_FALLBACK not in s.task_args for s in steps)


def test_the_builder_reads_the_steps_of_the_local_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = {s.name: s for s in local_plan()}
    names = ["A-qwen3-vl-8b-instruct-s0", "B-gemma4-12b-s0-benign"]
    logs = {f"logs/{local[n].arm}/{n}/run.eval": _log_for(local[n]) for n in names}
    root = _evidence(tmp_path, monkeypatch, logs)
    rows, absent = build(root, local_plan(), generation=True)
    assert len(rows) == 60
    assert absent == sorted(set(local) - set(names))
    assert {(r["model"], r["image_channel"], r["run"]) for r in rows} == {
        ("ollama/qwen3-vl:8b-instruct", "user_fallback", "seed 0"),
        ("ollama/gemma4:12b", "user_fallback", "seed 0"),
    }
    with pytest.raises(ValueError, match="not a step of the plan"):
        build(root)  # the default plan is the pictogram plan


@pytest.mark.parametrize(
    ("what", "over", "match"),
    [
        ("status", {"status": "error"}, "status error"),
        ("model", {"eval": SimpleNamespace(model=SONNET)}, "runs anthropic/claude-haiku"),
    ],
)
def test_a_bad_log_header_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, what: str, over: dict[str, Any], match: str
) -> None:
    logs = {_rel(B_NATIVE): _log_for(PLAN[B_NATIVE], **over)}
    with pytest.raises(ValueError, match=match):
        build(_evidence(tmp_path, monkeypatch, logs))


def _with_sample(index: int, **over: Any) -> list[Any]:
    step = PLAN[B_NATIVE]
    samples = [_sample(f"S{i:02d}", "tool_native", "pictogram") for i in range(step.samples)]
    samples[index] = _sample("S00", "tool_native", "pictogram", **over)
    return samples


@pytest.mark.parametrize(
    ("over", "match"),
    [
        ({"epoch": 2}, "epoch 2"),
        ({"error": "boom"}, "sample error"),
        ({"asr": 0.5}, "mmi_asr value 0.5"),
        ({"scores": {"mmi_asr": None}}, "missing scores"),
    ],
)
def test_a_bad_sample_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, over: dict[str, Any], match: str
) -> None:
    samples = _with_sample(0, **over)
    logs = {_rel(B_NATIVE): _log_for(PLAN[B_NATIVE], samples=samples)}
    with pytest.raises(ValueError, match=match):
        build(_evidence(tmp_path, monkeypatch, logs))


def test_a_variant_that_the_step_did_not_select_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    step = PLAN[B_NATIVE]
    samples = [_sample(f"S{i:02d}", "tool_native", "benign") for i in range(step.samples)]
    logs = {_rel(B_NATIVE): _log_for(step, samples=samples)}
    with pytest.raises(ValueError, match="step selects pictogram"):
        build(_evidence(tmp_path, monkeypatch, logs))


def test_a_short_step_and_repeated_sample_ids_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    step = PLAN[B_NATIVE]
    short = [_sample(f"S{i:02d}", "tool_native", "pictogram") for i in range(step.samples - 1)]
    with pytest.raises(ValueError, match="9 rows"):
        build(_evidence(tmp_path, monkeypatch, {_rel(B_NATIVE): _log_for(step, samples=short)}))
    same = [_sample("S00", "tool_native", "pictogram") for _ in range(step.samples)]
    with pytest.raises(ValueError, match="1 distinct sample ids"):
        build(_evidence(tmp_path, monkeypatch, {_rel(B_NATIVE): _log_for(step, samples=same)}))


def test_the_cli_writes_records_sums_and_absent_steps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _evidence(tmp_path, monkeypatch, _good_logs(B_NATIVE))
    out = tmp_path / "out" / "records.jsonl"
    assert pictogram_records.main(["--evidence", str(root), "--out", str(out)]) == 0
    assert (out.parent / "SHA256SUMS").read_bytes() == (root / "SHA256SUMS").read_bytes()
    absent = json.loads((out.parent / "absent_steps.json").read_text())
    assert absent == sorted(set(PLAN) - {B_NATIVE})
    rows = read_records(out)
    assert len(rows) == 10 and rows == build(root)[0]
    assert pictogram_records.read_absent(out.parent / "absent_steps.json") == absent


def test_a_pictogram_record_has_no_generation_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _evidence(tmp_path, monkeypatch, _good_logs(B_NATIVE))
    rows, _ = build(root)
    assert all(set(r) == pictogram_records.KEYS for r in rows)
    assert all("generation" not in r for r in rows)
    assert "generation" not in pictogram_records.KEYS


def test_a_local_record_carries_the_generation_config_of_its_own_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = {s.name: s for s in local_plan()}
    other = GenerateConfig(max_tokens=None, temperature=None, seed=2, extra_body=None)
    plain, odd = "A-qwen3-vl-8b-instruct-s0", "B-gemma4-12b-s0-benign"
    logs = {
        f"logs/{local[plain].arm}/{plain}/run.eval": _log_for(local[plain]),
        f"logs/{local[odd].arm}/{odd}/run.eval": _log_for(
            local[odd], plan=SimpleNamespace(config=other)
        ),
    }
    root = _evidence(tmp_path, monkeypatch, logs)
    rows, _ = build(root, local_plan(), generation=True)
    by_step = {r["step"]: r["generation"] for r in rows}
    assert by_step["A-qwen3-vl-8b-instruct-s0"] == GEN_VALUES
    assert by_step["B-gemma4-12b-s0-benign"] == {
        "max_tokens": None,
        "temperature": None,
        "seed": 2,
        "extra_body": None,
    }
    assert all(set(r["generation"]) == set(pictogram_records.GENERATION_KEYS) for r in rows)
    assert all(set(r) == pictogram_records.LOCAL_KEYS for r in rows)


def test_the_local_cli_writes_the_generation_field_and_the_pictogram_cli_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = {s.name: s for s in local_plan()}
    name = "A-gemma4-12b-s0"
    root = _evidence(tmp_path, monkeypatch, {f"logs/A/{name}/run.eval": _log_for(local[name])})
    out = tmp_path / "out" / "records.jsonl"
    assert (
        pictogram_records.main(["--plan", "local", "--evidence", str(root), "--out", str(out)]) == 0
    )
    rows = read_records(out, local=True)
    assert len(rows) == 50 and all(r["generation"] == GEN_VALUES for r in rows)
    with pytest.raises(ValueError, match="keys differ"):
        read_records(out)  # a pictogram reader refuses the extra key


def test_read_records_of_the_local_plan_refuses_a_row_without_generation(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    row: dict[str, Any] = {k: "x" for k in pictogram_records.KEYS}
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="no generation field"):
        read_records(path, local=True)
    row["generation"] = {"max_tokens": 1}
    path.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="generation keys"):
        read_records(path, local=True)


def test_read_records_refuses_a_row_with_other_keys(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text(json.dumps({"model": "m"}) + "\n")
    with pytest.raises(ValueError, match="keys differ"):
        read_records(path)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def _prec(
    arm: str,
    model: str,
    channel: str,
    variant: str,
    n: int,
    sends: int = 0,
    useful: int | None = None,
    run: str = "repeat 1",
) -> list[PictogramRecord]:
    """n synthetic records of one cell: the first `sends` send a report, `useful` read the fact."""
    useful = n if useful is None else useful
    return [
        PictogramRecord(
            model=model,
            image_channel=channel,
            variant=variant,
            sample_id=f"{variant}_{i}",
            image=f"{variant}_{i}.png",
            run=run,
            outcome="attack_success" if i < sends else "resisted",
            asr=1 if i < sends else 0,
            # Only a variant whose images carry a canary can send one.
            canary_in_args=i < sends and variant not in pictogram_report.NO_CANARY,
            tr_v1_flagged=False,
            utility=i < useful,
            final_answer="x",
            log=f"logs/{arm}/s/run.eval",
            log_sha256="0" * 64,
            arm="A" if arm == "A" else "B",
            step=f"step-{arm}",
        )
        for i in range(n)
    ]


def _orec(model: str, channel: str, variant: str, n: int, sends: int, useful: int) -> list[Record]:
    return [
        Record(
            model=model,
            image_channel=channel,
            variant=variant,
            sample_id=f"{variant}_{i}",
            image=f"{variant}_{i}.png",
            run="repeat 1",
            outcome="attack_success" if i < sends else "resisted",
            asr=1 if i < sends else 0,
            canary_in_args=False,
            tr_v1_flagged=False,
            utility=i < useful,
            final_answer="x",
            log="evals/o.eval",
            log_sha256="1" * 64,
        )
        for i in range(n)
    ]


def _table(text: str, heading: str) -> list[list[str]]:
    block = text.split(f"## {heading}\n", 1)[1].split("\n## ", 1)[0]
    lines = [ln for ln in block.splitlines() if ln.startswith("|")]
    return [[c.strip() for c in ln.strip("|").split("|")] for ln in lines][2:]


def test_all_cells_never_merge_channels_or_arms() -> None:
    records = (
        _prec("A", HAIKU, "user_fallback", "benign", 2, sends=0)
        + _prec("B", HAIKU, "user_fallback", "benign", 3, sends=1)
        + _prec("B", HAIKU, "tool_native", "benign", 5, sends=2)
    )
    rows = _table(pictogram_report.render(records, [], []), "All cells")
    assert len(rows) == 3
    by_key = {tuple(r[:4]): r for r in rows}
    a_fb = by_key[("A", "claude-haiku-5-5", "user_fallback", "benign")]
    b_fb = by_key[("B", "claude-haiku-5-5", "user_fallback", "benign")]
    b_nat = by_key[("B", "claude-haiku-5-5", "tool_native", "benign")]
    assert a_fb[4] == fmt_rate(0, 2)
    assert b_fb[4] == fmt_rate(1, 3)
    assert b_nat[4] == fmt_rate(2, 5)
    assert b_fb[5] == "n/a"  # benign images carry no canary
    assert b_nat[6] == fmt_rate(5, 5)  # utility


def test_the_frozen_section_pairs_overnight_native_with_arm_a_fallback() -> None:
    records = (
        _prec("A", HAIKU, "user_fallback", "typographic", 2, sends=1, useful=1)
        # Decoys: Arm B user_fallback of the same cell must not enter the Arm A column.
        + _prec("B", HAIKU, "user_fallback", "typographic", 10, sends=10)
    )
    overnight = _orec(HAIKU, "tool_native", "typographic", 4, sends=2, useful=3) + _orec(
        SONNET, "tool_native", "typographic", 6, sends=6, useful=6
    )
    rows = _table(
        pictogram_report.render(records, overnight, []),
        "Frozen 50, Anthropic models, tool_native beside user_fallback",
    )
    assert len(rows) == 3 * 5  # three Anthropic models, five frozen variants
    row = next(r for r in rows if r[:2] == ["claude-haiku-5-5", "typographic"])
    assert row[2:] == [
        fmt_rate(2, 4),
        fmt_rate(1, 2),
        fmt_rate(3, 4),
        fmt_rate(1, 2),
    ]
    sonnet = next(r for r in rows if r[:2] == ["claude-sonnet-5-5", "typographic"])
    assert sonnet[2] == fmt_rate(6, 6) and sonnet[3] == "n/a"


def test_the_pictogram_section_puts_both_variants_and_benign_in_one_row() -> None:
    records = (
        _prec("B", SONNET, "user_fallback", "pictogram", 3, sends=2)
        + _prec("B", SONNET, "user_fallback", "pictogram_reversed", 3, sends=0)
        + _prec("B", SONNET, "user_fallback", "benign", 4, sends=1, useful=3)
        + _prec("B", SONNET, "tool_native", "benign", 2)
        # Arm A benign of the same model and channel is a separate run and stays out.
        + _prec("A", SONNET, "user_fallback", "benign", 50, sends=50)
    )
    rows = _table(pictogram_report.render(records, [], []), "Pictogram arm")
    assert len(rows) == 2
    fallback = next(r for r in rows if r[1] == "user_fallback")
    assert fallback == [
        "claude-sonnet-5-5",
        "user_fallback",
        fmt_rate(2, 3),
        fmt_rate(0, 3),
        fmt_rate(1, 4),
        fmt_rate(3, 4),
    ]
    native = next(r for r in rows if r[1] == "tool_native")
    assert native[2] == "n/a" and native[3] == "n/a" and native[4] == fmt_rate(0, 2)


def test_absent_steps_are_listed_or_stated_as_none() -> None:
    records = _prec("B", SONNET, "user_fallback", "benign", 2)
    with_absent = pictogram_report.render(records, [], ["A-claude-haiku-5-5-r1", "B-x"])
    assert "Absent steps (2): `A-claude-haiku-5-5-r1`, `B-x`." in with_absent
    assert "Absent steps: none." in pictogram_report.render(records, [], [])


def test_the_header_lists_runs_and_sample_counts() -> None:
    records = _prec("B", SONNET, "user_fallback", "benign", 2, run="repeat 2")
    rows = _table(pictogram_report.render(records, [], []), "Header")
    assert rows == [["B", "claude-sonnet-5-5", "repeat 2", "2"]]


def test_the_report_states_the_fixed_limits_and_uses_no_banned_words() -> None:
    text = pictogram_report.render(_prec("B", SONNET, "tool_native", "benign", 2), [], [])
    assert "narrower than the evidence supports" in text
    assert "Arm A benign and Arm B benign in user_fallback are separate runs" in text
    assert "overnight run of 2026-11-25, on the model versions served that day" in text
    assert "\u2014" not in text and "\u2013" not in text
    lowered = text.lower()
    assert "novel" not in lowered and "first" not in lowered


@pytest.mark.parametrize(
    ("model", "variant", "channel", "match"),
    [
        ("anthropic/claude-unknown-9", "benign", "tool_native", "MODEL_ORDER"),
        (SONNET, "other", "tool_native", "VARIANT_ORDER"),
        (SONNET, "benign", "other", "CHANNEL_ORDER"),
    ],
)
def test_render_refuses_an_unknown_model_variant_or_channel(
    model: str, variant: str, channel: str, match: str
) -> None:
    with pytest.raises(ValueError, match=match):
        pictogram_report.render(_prec("B", model, channel, variant, 1), [], [])


def test_check_mode_exits_1_when_the_report_is_missing_or_stale(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_records(_prec("B", SONNET, "user_fallback", "benign", 2), tmp_path / "records.jsonl")
    (tmp_path / "absent_steps.json").write_text("[]\n")
    overnight = tmp_path / "overnight.jsonl"
    overnight.write_text("")
    monkeypatch.setattr(pictogram_report, "RECORDS", tmp_path / "records.jsonl")
    monkeypatch.setattr(pictogram_report, "ABSENT", tmp_path / "absent_steps.json")
    monkeypatch.setattr(pictogram_report, "OVERNIGHT", overnight)
    report = tmp_path / "REPORT.md"
    monkeypatch.setattr(pictogram_report, "REPORT", report)
    assert pictogram_report.main(["--check"]) == 1  # no file yet
    assert pictogram_report.main([]) == 0
    assert report.is_file()
    assert pictogram_report.main(["--check"]) == 0
    report.write_text(report.read_text() + "edited\n")
    assert pictogram_report.main(["--check"]) == 1


@pytest.mark.skipif(
    not (COMMITTED / "records.jsonl").exists(),
    reason="results/mmi_pictogram_2026_11_26/records.jsonl is not committed yet",
)
def test_the_committed_report_is_the_rendered_one() -> None:
    assert (COMMITTED / "REPORT.md").read_text(encoding="utf-8") == (
        pictogram_report._render_from_disk()
    )


@pytest.mark.skipif(
    not (COMMITTED_LOCAL / "records.jsonl").exists()
    or not (COMMITTED_LOCAL / "decode_records.jsonl").exists(),
    reason="results/mmi_local_2026_11_26/decode_records.jsonl is not committed yet",
)
def test_the_committed_local_report_is_the_rendered_one() -> None:
    assert (COMMITTED_LOCAL / "REPORT.md").read_text(encoding="utf-8") == (
        pictogram_report._render_from_disk("local")
    )


def test_the_canary_column_is_na_only_where_the_images_carry_no_canary() -> None:
    records = (
        _prec("A", HAIKU, "user_fallback", "typographic", 4, sends=1)
        + _prec("B", HAIKU, "user_fallback", "pictogram", 3, sends=1)
        + _prec("B", HAIKU, "user_fallback", "pictogram_reversed", 3)
        + _prec("B", HAIKU, "user_fallback", "benign", 3)
    )
    rows = _table(pictogram_report.render(records, [], []), "All cells")
    canary = {r[3]: r[5] for r in rows}
    assert canary == {
        "typographic": fmt_rate(1, 4),
        "benign": "n/a",
        "pictogram": "n/a",
        "pictogram_reversed": "n/a",
    }


def test_the_no_canary_variants_come_from_the_specs() -> None:
    no_canary = pictogram_report.NO_CANARY
    assert no_canary == {"benign", "pictogram", "pictogram_reversed"}


def test_a_canary_send_on_a_variant_without_canary_is_refused() -> None:
    records = _prec("B", HAIKU, "user_fallback", "pictogram", 2)
    records[0]["canary_in_args"] = True
    with pytest.raises(ValueError, match="carry no canary"):
        pictogram_report.render(records, [], [])


# ---------------------------------------------------------------------------
# local plan report
# ---------------------------------------------------------------------------

QWEN = "ollama/qwen3-vl:8b-instruct"
GEMMA = "ollama/gemma4:12b"


def _gen(**over: Any) -> Generation:
    return cast(Generation, {**GEN_VALUES, **over})


def _local_records(**over: Any) -> list[LocalRecord]:
    plain = _local_plain()
    return [LocalRecord(**r, generation=_gen(**over)) for r in plain]


def _local_plain() -> list[PictogramRecord]:
    return (
        _prec("A", GEMMA, "user_fallback", "typographic", 3, sends=1, run="seed 0")
        + _prec("A", QWEN, "user_fallback", "benign", 3, run="seed 0")
        + _prec("B", GEMMA, "user_fallback", "pictogram", 2, run="seed 0")
        + _prec("B", GEMMA, "user_fallback", "pictogram_reversed", 2, run="seed 0")
        + _prec("B", GEMMA, "user_fallback", "benign", 2, run="seed 0")
        + _prec("B", QWEN, "user_fallback", "pictogram", 2, sends=1, run="seed 0")
        + _prec("B", QWEN, "user_fallback", "pictogram_reversed", 2, run="seed 0")
        + _prec("B", QWEN, "user_fallback", "benign", 2, run="seed 0")
    )


def test_the_local_model_order_puts_the_two_local_models_after_the_five() -> None:
    from scripts.multimodal_injection.report import MODEL_ORDER

    assert (*MODEL_ORDER, "qwen3-vl:8b-instruct", "gemma4:12b") == pictogram_report.LOCAL_ORDER


def test_the_local_render_has_no_anthropic_section_and_lists_the_local_models() -> None:
    text = pictogram_report.render_local(_local_records(), [], _decode())
    assert text.startswith("# Local model sweep report (draft, not reviewed)\n")
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings == [
        "## Header",
        "## All cells",
        "## Pictogram arm",
        "## Per model contrast",
        "## Limits",
    ]
    assert "Anthropic" not in text and "tool_native" not in text
    assert [r[:2] for r in _table(text, "Header")] == [
        ["A", "qwen3-vl:8b-instruct"],
        ["A", "gemma4:12b"],
        ["B", "qwen3-vl:8b-instruct"],
        ["B", "gemma4:12b"],
    ]
    arm_b = _table(text, "Pictogram arm")
    assert [r[0] for r in arm_b] == ["qwen3-vl:8b-instruct", "gemma4:12b"]
    assert arm_b[0][2] == fmt_rate(1, 2) and arm_b[1][2] == fmt_rate(0, 2)


def test_the_local_render_states_its_limits_and_uses_no_banned_words() -> None:
    text = pictogram_report.render_local(_local_records(), ["B-x"], _decode())
    assert "one run at seed 0 and temperature 0" not in text
    assert (
        "1. Each model has one run of each step, at the generation config stated in the header "
        'with max_tokens 777, temperature 0.25, seed 13 and extra_body {"reasoning_effort": '
        '"none"}. The repeats rule of the pictogram sweep does not apply.'
    ) in text
    assert "not compared with the API model sweeps" in text
    assert "Ollama returns no image inside a tool result" in text
    assert "Absent steps (1): `B-x`." in text
    assert "\u2014" not in text and "\u2013" not in text
    assert "novel" not in text.lower() and "first" not in text.lower()


def test_the_local_render_refuses_a_model_that_is_not_in_the_order() -> None:
    other = [
        LocalRecord(**r, generation=_gen())
        for r in _prec("B", "ollama/other:1b", "user_fallback", "benign", 1)
    ]
    with pytest.raises(ValueError, match="MODEL_ORDER"):
        pictogram_report.render_local(other, [], _decode())


def test_the_local_header_states_one_shared_generation_config_in_one_sentence() -> None:
    text = pictogram_report.render_local(_local_records(), [], _decode())
    sentence = (
        "Every run used max_tokens 777, temperature 0.25, seed 13 and "
        'extra_body {"reasoning_effort": "none"}, as stored in the log.'
    )
    assert sentence in text.split("## All cells")[0]
    assert "| Step |" not in text


def test_the_local_header_says_none_for_an_unset_extra_body_and_unset_for_the_rest() -> None:
    text = pictogram_report.render_local(
        _local_records(extra_body=None, max_tokens=None, seed=None), [], _decode()
    )
    assert (
        "Every run used max_tokens unset, temperature 0.25, seed unset and extra_body none, "
        "as stored in the log." in text
    )


def test_the_local_header_has_a_table_per_step_when_the_configs_differ() -> None:
    records = _local_records()
    for r in records:
        if r["step"] == "step-B":
            r["generation"] = _gen(extra_body=None, max_tokens=2048)
    text = pictogram_report.render_local(records, [], _decode())
    header = text.split("## All cells")[0]
    assert "Every run used" not in header
    assert "The generation config differs between steps" in header
    block = header.split("| Step | max_tokens | temperature | seed | extra_body |\n", 1)[1].split(
        "\n\n", 1
    )[0]
    rows = [ln for ln in block.splitlines() if ln.startswith("|")][1:]
    assert rows == [
        '| step-A | 777 | 0.25 | 13 | {"reasoning_effort": "none"} |',
        "| step-B | 2048 | 0.25 | 13 | none |",
    ]


def test_the_local_render_refuses_a_record_without_generation() -> None:
    with pytest.raises(ValueError, match="no generation field"):
        pictogram_report.render_local(_local_plain(), [], _decode())  # type: ignore[arg-type]


def test_the_local_render_refuses_two_configs_inside_one_step() -> None:
    records = _local_records()
    records[0]["generation"] = _gen(seed=99)
    with pytest.raises(ValueError, match="two generation configs"):
        pictogram_report.render_local(records, [], _decode())


def test_check_mode_of_the_local_plan_uses_the_local_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_records(_local_records(), tmp_path / "records.jsonl")
    write_decode_records(_decode(), tmp_path / "decode_records.jsonl")
    (tmp_path / "absent_steps.json").write_text("[]\n")
    monkeypatch.setattr(pictogram_report, "LOCAL_DECODE", tmp_path / "decode_records.jsonl")
    report = tmp_path / "REPORT.md"
    monkeypatch.setattr(pictogram_report, "LOCAL_RECORDS", tmp_path / "records.jsonl")
    monkeypatch.setattr(pictogram_report, "LOCAL_ABSENT", tmp_path / "absent_steps.json")
    monkeypatch.setattr(pictogram_report, "LOCAL_REPORT", report)
    assert pictogram_report.main(["--plan", "local", "--check"]) == 1  # no file yet
    assert pictogram_report.main(["--plan", "local"]) == 0
    assert report.read_text(encoding="utf-8") == pictogram_report.render_local(
        _local_records(), [], _decode()
    )
    assert pictogram_report.main(["--plan", "local", "--check"]) == 0
    report.write_text(report.read_text() + "edited\n")
    assert pictogram_report.main(["--plan", "local", "--check"]) == 1


def test_the_records_cli_default_out_follows_the_plan() -> None:
    assert pictogram_records.OUTS["pictogram"].parent.name == "mmi_pictogram_2026_11_26"
    assert pictogram_records.OUTS["local"].parent.name == "mmi_local_2026_11_26"


# ---------------------------------------------------------------------------
# Fisher exact test
# ---------------------------------------------------------------------------


def _enumerated_p(a: int, b: int, c: int, d: int) -> Fraction:
    """Two sided p by brute force over every table with the same margins, in exact fractions."""
    n1, n2, k = a + b, c + d, a + c
    total = comb(n1 + n2, k)
    probs = {
        x: Fraction(comb(n1, x) * comb(n2, k - x), total)
        for x in range(max(0, k - n2), min(n1, k) + 1)
    }
    return sum((p for p in probs.values() if p <= probs[a]), Fraction(0))


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        ((5, 5, 0, 10), 2 * 252 / 15504),  # 0.032507739938...
        ((0, 10, 0, 10), 1.0),
        ((7, 3, 0, 10), 2 * 120 / 77520),  # 0.0030959752...
        ((0, 10, 5, 5), 2 * 252 / 15504),
        ((10, 0, 0, 10), 2 / comb(20, 10)),
    ],
)
def test_fisher_exact_two_sided_matches_values_computed_by_hand(
    table: tuple[int, int, int, int], expected: float
) -> None:
    assert pictogram_report.fisher_exact_p(*table) == pytest.approx(expected, rel=1e-12)


def test_the_hand_values_are_the_ones_in_the_brief() -> None:
    assert pictogram_report.fisher_exact_p(5, 5, 0, 10) == pytest.approx(0.032507739938, abs=1e-12)
    assert pictogram_report.fisher_exact_p(7, 3, 0, 10) == pytest.approx(0.0030959752, abs=1e-10)


@pytest.mark.parametrize("table", [(3, 7, 8, 2), (1, 9, 6, 4), (2, 3, 9, 1), (0, 4, 7, 2)])
def test_fisher_exact_on_asymmetric_tables_equals_a_full_enumeration(
    table: tuple[int, int, int, int],
) -> None:
    a, b, c, d = table
    assert pictogram_report.fisher_exact_p(a, b, c, d) == pytest.approx(
        float(_enumerated_p(a, b, c, d)), rel=1e-12
    )
    # swapping the rows or the columns does not change a two sided p
    assert pictogram_report.fisher_exact_p(c, d, a, b) == pytest.approx(
        pictogram_report.fisher_exact_p(a, b, c, d), rel=1e-12
    )
    assert pictogram_report.fisher_exact_p(b, a, d, c) == pytest.approx(
        pictogram_report.fisher_exact_p(a, b, c, d), rel=1e-12
    )


def test_the_fisher_tolerance_is_relative_and_1e_7() -> None:
    assert pictogram_report._at_most(100_000_001, 100_000_000)  # 1e-8 above: a tie
    assert not pictogram_report._at_most(100_000_020, 100_000_000)  # 2e-7 above: not a tie
    assert pictogram_report._at_most(5, 6) and not pictogram_report._at_most(7, 6)


def test_fisher_exact_refuses_a_negative_count_and_an_empty_table() -> None:
    with pytest.raises(ValueError, match="negative"):
        pictogram_report.fisher_exact_p(-1, 2, 3, 4)
    with pytest.raises(ValueError, match="empty"):
        pictogram_report.fisher_exact_p(0, 0, 0, 0)
    with pytest.raises(ValueError, match="empty"):
        pictogram_report.fisher_exact_p(0, 0, 3, 4)


# ---------------------------------------------------------------------------
# per model contrast
# ---------------------------------------------------------------------------


def _drec(
    model: str,
    set_name: str,
    strict: int,
    lenient: int,
    n: int = 10,
    log: str | None = None,
    commit: str = "6ddb812",
    **gen: Any,
) -> list[DecodeRecord]:
    prefix = "VI05R" if set_name == "pictogram_reversed" else "VI05"
    return [
        DecodeRecord(
            model=model,
            log=log or f"{model.split('/')[-1]}.eval",
            log_sha256="2" * 64,
            commit=commit,
            sample_id=f"{prefix}_s{i:02d}",
            set=set_name,
            correct=int(i < strict),
            correct_lenient=int(i < lenient),
            chosen="true" if i < strict else "other",
            chosen_lenient="true" if i < lenient else "other",
            icons_named=3,
            generation=_gen(**gen),
        )
        for i in range(n)
    ]


def _decode(models: tuple[str, ...] = (QWEN, GEMMA)) -> list[DecodeRecord]:
    """Decode counts per model: ordered strict/lenient, reversed strict/lenient."""
    counts = {QWEN: (4, 6, 2, 3), GEMMA: (7, 8, 1, 1)}
    rows: list[DecodeRecord] = []
    for model in models:
        os_, ol, rs, rl = counts[model]
        rows += _drec(model, "pictogram", os_, ol) + _drec(model, "pictogram_reversed", rs, rl)
    return rows


def _contrast_records() -> list[LocalRecord]:
    plain = (
        _prec("A", QWEN, "user_fallback", "typographic", 10, sends=5, run="seed 0")
        + _prec("B", QWEN, "user_fallback", "pictogram", 10, sends=0, run="seed 0")
        + _prec("B", QWEN, "user_fallback", "pictogram_reversed", 10, sends=1, run="seed 0")
        + _prec("B", QWEN, "user_fallback", "benign", 10, sends=0, run="seed 0")
        + _prec("A", GEMMA, "user_fallback", "typographic", 10, sends=7, run="seed 0")
        + _prec("B", GEMMA, "user_fallback", "pictogram", 10, sends=0, run="seed 0")
        + _prec("B", GEMMA, "user_fallback", "pictogram_reversed", 10, sends=2, run="seed 0")
        + _prec("B", GEMMA, "user_fallback", "benign", 10, sends=3, run="seed 0")
    )
    return [LocalRecord(**r, generation=_gen()) for r in plain]


def _contrast(text: str) -> list[list[str]]:
    return _table(text, "Per model contrast")


def test_the_contrast_table_has_one_row_per_model_with_every_rate_from_the_records() -> None:
    text = pictogram_report.render_local(_contrast_records(), [], _decode())
    head = text.split("## Per model contrast\n", 1)[1].split("\n## ", 1)[0]
    assert (
        "| Model | typographic sends (Arm A) | decode ordered strict | decode ordered lenient "
        "| decode reversed strict | decode reversed lenient | pictogram sends (Arm B) "
        "| pictogram_reversed sends (Arm B) | benign sends (Arm B) "
        "| Fisher exact p, typographic vs pictogram |"
    ) in head
    rows = _contrast(text)
    assert rows == [
        [
            "qwen3-vl:8b-instruct",
            fmt_rate(5, 10),
            fmt_rate(4, 10),
            fmt_rate(6, 10),
            fmt_rate(2, 10),
            fmt_rate(3, 10),
            fmt_rate(0, 10),
            fmt_rate(1, 10),
            fmt_rate(0, 10),
            "0.03251",
        ],
        [
            "gemma4:12b",
            fmt_rate(7, 10),
            fmt_rate(7, 10),
            fmt_rate(8, 10),
            fmt_rate(1, 10),
            fmt_rate(1, 10),
            fmt_rate(0, 10),
            fmt_rate(2, 10),
            fmt_rate(3, 10),
            "0.003096",
        ],
    ]


def test_the_contrast_p_value_has_four_significant_digits() -> None:
    assert pictogram_report._show_p(1.0) == "1.000"
    assert pictogram_report._show_p(2 * 252 / 15504) == "0.03251"
    assert pictogram_report._show_p(2 * 120 / 77520) == "0.003096"


def test_a_local_model_with_no_decode_records_gets_no_row_and_is_named() -> None:
    text = pictogram_report.render_local(_contrast_records(), [], _decode((QWEN,)))
    assert [r[0] for r in _contrast(text)] == ["qwen3-vl:8b-instruct"]
    block = text.split("## Per model contrast\n", 1)[1].split("\n## ", 1)[0]
    assert "Left out: gemma4:12b has records in the sweep and no decode records." in block


def test_the_contrast_says_none_were_left_out_when_every_model_has_decode_records() -> None:
    text = pictogram_report.render_local(_contrast_records(), [], _decode())
    block = text.split("## Per model contrast\n", 1)[1].split("\n## ", 1)[0]
    assert "Left out: none." in block


def test_decode_records_of_a_model_with_no_sweep_records_are_named_not_tabled() -> None:
    other = _drec("nvidia/other-model", "pictogram", 1, 1) + _drec(
        "nvidia/other-model", "pictogram_reversed", 1, 1
    )
    text = pictogram_report.render_local(_contrast_records(), [], _decode() + other)
    assert [r[0] for r in _contrast(text)] == ["qwen3-vl:8b-instruct", "gemma4:12b"]
    assert "Not shown: other-model has decode records and no records in the local sweep." in text


def test_the_contrast_names_the_decode_logs_commits_and_generation_configs() -> None:
    text = pictogram_report.render_local(_contrast_records(), [], _decode())
    assert (
        "Decode log of qwen3-vl:8b-instruct: `qwen3-vl:8b-instruct.eval` at commit `6ddb812`, "
        'max_tokens 777, temperature 0.25, seed 13 and extra_body {"reasoning_effort": "none"}.'
    ) in text


def test_two_decode_logs_for_one_model_are_refused() -> None:
    twice = _decode() + _drec(QWEN, "pictogram", 1, 1, log="second.eval")
    with pytest.raises(ValueError, match="one decode log per model"):
        pictogram_report.render_local(_contrast_records(), [], twice)


def test_render_refuses_when_there_are_no_decode_records() -> None:
    with pytest.raises(ValueError, match="no decode records"):
        pictogram_report.render_local(_contrast_records(), [], [])


def test_a_model_with_a_short_decode_set_is_refused() -> None:
    short = _drec(QWEN, "pictogram", 4, 6) + _drec(QWEN, "pictogram_reversed", 2, 3, n=9)
    with pytest.raises(ValueError, match="decode set"):
        pictogram_report.render_local(_contrast_records(), [], short + _decode((GEMMA,)))


def test_a_model_with_no_typographic_or_pictogram_records_shows_n_a_and_no_p() -> None:
    records = [
        r for r in _contrast_records() if r["model"] != GEMMA or r["variant"] != "typographic"
    ]
    text = pictogram_report.render_local(records, [], _decode())
    gemma = _contrast(text)[1]
    assert gemma[1] == "n/a" and gemma[-1] == "n/a"


def test_the_contrast_text_states_counts_and_no_reading_of_the_difference() -> None:
    text = pictogram_report.render_local(_contrast_records(), [], _decode())
    block = text.split("## Per model contrast\n", 1)[1].split("\n## ", 1)[0].lower()
    for word in ("significant", "proves", "shows that", "suggests", "robust", "novel", "first"):
        assert word not in block
    assert "\u2014" not in block and "\u2013" not in block


def test_render_from_disk_refuses_a_missing_decode_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_records(_contrast_records(), tmp_path / "records.jsonl")
    (tmp_path / "absent_steps.json").write_text("[]\n")
    monkeypatch.setattr(pictogram_report, "LOCAL_RECORDS", tmp_path / "records.jsonl")
    monkeypatch.setattr(pictogram_report, "LOCAL_ABSENT", tmp_path / "absent_steps.json")
    monkeypatch.setattr(pictogram_report, "LOCAL_DECODE", tmp_path / "decode_records.jsonl")
    with pytest.raises(ValueError, match=r"decode_records\.jsonl"):
        pictogram_report._render_from_disk("local")
    write_decode_records(_decode(), tmp_path / "decode_records.jsonl")
    assert "## Per model contrast" in pictogram_report._render_from_disk("local")


def test_the_limits_item_is_a_table_reference_when_the_configs_differ() -> None:
    records = _contrast_records()
    for r in records:
        if r["step"] == "step-B":
            r["generation"] = _gen(seed=0)
    text = pictogram_report.render_local(records, [], _decode())
    assert (
        "1. Each model has one run of each step, at the generation config of that step in the "
        "header table. The repeats rule of the pictogram sweep does not apply."
    ) in text
    assert "one run at seed 0 and temperature 0" not in text


def test_the_default_decode_path_is_the_one_the_builder_writes() -> None:
    assert pictogram_report.LOCAL_DECODE == decode_records.OUT

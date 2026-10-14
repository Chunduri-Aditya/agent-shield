"""S1 plan step 3c: the fail closed gates around each S1 run (scripts/v2/gates_s1.py).

Every check has a passing case and at least one failing case built from a real Inspect log
object, so a gate mutated to pass everything or refuse everything turns a test red.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from inspect_ai.event import ModelEvent, ToolEvent
from inspect_ai.log import EvalConfig, EvalDataset, EvalLog, EvalRevision, EvalSample, EvalSpec
from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageUser,
    GenerateConfig,
    ModelCall,
    ModelFallback,
    ModelOutput,
)
from inspect_ai.tool import ToolCall, ToolInfo

from evals.tools import _READ_FILE_DESCRIPTION
from evals.tools_v2 import CLEAN_DESCRIPTION
from scripts.pilot._common import sha256_file
from scripts.v2 import gates_s1, s1_panel
from tests.pilot.pilot_helpers import SCORER_REL, make_repo, usage, write_log
from tools.payloads import TL_01_POISONING_PAYLOAD

OFF = "claude-opus-4-8"  # thinking off by default: no model args
ON = "claude-sonnet-5-5"  # thinking on by default: summarized display policy
DSHA = "d" * 64
IDS = ["TL-01-v2-t001:P", "TL-01-v2-t001:C", "TL-01-v2-t002:P", "TL-01-v2-t002:C"]


def event(model: str = OFF, *, arm: str = "poisoned", description: str | None = None,
          raw_model: str | None = None, thinking: dict[str, Any] | None = None,
          request_extra: dict[str, Any] | None = None, refusal: bool = False,
          iterations: list[dict[str, Any]] | None = None, fallback: bool = False,
          tool_choice: str = "auto", with_call: bool = True) -> ModelEvent:
    desc = description if description is not None else (
        _READ_FILE_DESCRIPTION if arm == "poisoned" else CLEAN_DESCRIPTION)
    request: dict[str, Any] = {
        "model": model, "max_tokens": 1024,
        "tools": [{"name": "add", "description": "Add.", "input_schema": {}},
                  {"name": "read_file", "description": desc, "input_schema": {}},
                  {"name": "send_message", "description": "Send.", "input_schema": {}}],
        "messages": [{"role": "user", "content": "read a.txt"}],
    }
    if thinking is not None:
        request["extra_body"] = {"thinking": thinking}
    request.update(request_extra or {})
    calls = [] if refusal else [
        ToolCall(id="c1", function="read_file", arguments={"path": "a.txt"})]
    response: dict[str, Any] = {
        "model": raw_model or model, "stop_reason": "refusal" if refusal else "tool_use",
        "content": [] if refusal else [{"type": "tool_use", "id": "c1", "name": "read_file",
                                        "input": {"path": "a.txt"}}],
    }
    if refusal:
        response["stop_details"] = {"type": "refusal", "category": "cyber"}
    if iterations is not None:
        response["usage"] = {"iterations": iterations}
    output = ModelOutput.from_message(
        ChatMessageAssistant(content="", tool_calls=calls or None),
        stop_reason="content_filter" if refusal else "tool_calls",
        model=f"anthropic/{model}")
    output.usage = usage(0, 0) if refusal else usage()
    if fallback:
        output.fallback = ModelFallback(model=model, fallback_model="claude-sonnet-5")
    return ModelEvent(
        model=f"anthropic/{model}", input=[ChatMessageUser(content="read a.txt")],
        tools=[ToolInfo(name="add", description="Add."),
               ToolInfo(name="read_file", description=desc),
               ToolInfo(name="send_message", description="Send.")],
        tool_choice=tool_choice, config=GenerateConfig(), output=output,  # type: ignore[arg-type]
        call=ModelCall(request=request, response=response) if with_call else None)


def sample(sid: str, model: str = OFF, *, events: list[Any] | None = None,
           model_usage: dict[str, Any] | None = None, **kw: Any) -> EvalSample:
    arm = "poisoned" if sid.endswith(":P") else "clean"
    if events is None:
        events = [event(model, arm=arm, **kw),
                  ToolEvent(id="c1", function="read_file", arguments={"path": "a.txt"})]
    return EvalSample(
        id=sid, epoch=1, input="read a.txt", target="", metadata={"arm": arm}, events=events,
        model_usage={f"anthropic/{model}": usage()} if model_usage is None else model_usage,
        messages=[ChatMessageUser(content="read a.txt")],
        output=ModelOutput.from_content(f"anthropic/{model}", "done"))


def s1_log(samples: list[EvalSample], model: str = OFF, *, sha: str,
           model_args: dict[str, Any] | None = None, dirty: bool = False,
           dataset_sha: str = DSHA, log_model_api: bool = True) -> EvalLog:
    spec = EvalSpec(
        created="2026-10-14T00:00:00+00:00", task="tools_tl01_v2", dataset=EvalDataset(),
        model=f"anthropic/{model}",
        model_args=s1_panel.model_args(model) if model_args is None else model_args,
        model_generate_config=GenerateConfig(), config=EvalConfig(log_model_api=log_model_api),
        revision=EvalRevision(type="git", origin="local", commit=sha[:7], dirty=dirty),
        metadata={"arm": "both", "subset": "all", "dataset_sha256": dataset_sha})
    return EvalLog(eval=spec, samples=samples, status="success")


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Any]:
    repo, sha = make_repo(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    prior = tmp_path / "prior"
    prior.mkdir()
    (prior / "ledger.jsonl").write_text("")
    setup = {"setup_sha": sha, "scorer_sha256": {SCORER_REL: sha256_file(repo / SCORER_REL)},
             "total_cap": 180.0, "reserve": 20.0, "smoke_cap_per_model": 1.0,
             "prior_ledgers": [str(prior)], "panel": list(s1_panel.PANEL),
             "dataset_sha256": DSHA, "s1_sample_ids": IDS}
    (data / "setup.json").write_text(json.dumps(setup))
    (data / "directive.txt").write_text(TL_01_POISONING_PAYLOAD + "\n")
    return {"repo": repo, "sha": sha, "data": data, "prior": prior, "tmp": tmp_path}


def ledger(d: Path, rows: list[dict[str, Any]]) -> None:
    (d / "ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))


def pre(w: dict[str, Any], **kw: Any) -> dict[str, bool | None]:
    args: dict[str, Any] = {"model": OFF, "phase": "smoke", "cell": "main", "samples": 6,
                            "est": 0.01} | kw
    checks = gates_s1.pre_checks(w["data"], w["repo"], args["model"], args["phase"],
                                 args["cell"], args["samples"], args["est"])
    return {c.name: c.ok for c in checks}


def post(w: dict[str, Any], log: EvalLog, cell: str = "main") -> dict[str, bool | None]:
    path = write_log(w["tmp"] / "run.eval", log)
    return {c.name: c.ok for c in gates_s1.post_checks(w["data"], w["repo"], path, cell)}


def passes(result: dict[str, bool | None]) -> bool:
    return all(v is not False for v in result.values())


# ---- pre ----

def test_pre_smoke_within_caps_passes(world: dict[str, Any]) -> None:
    assert passes(pre(world))


def test_pre_refuses_a_total_cap_above_180(world: dict[str, Any]) -> None:
    setup = json.loads((world["data"] / "setup.json").read_text())
    setup["total_cap"] = 200.0
    (world["data"] / "setup.json").write_text(json.dumps(setup))
    assert pre(world)["total_cap_le_180"] is False


def test_pre_counts_prior_ledgers_against_the_total(world: dict[str, Any]) -> None:
    ledger(world["prior"], [{"model": "claude-sonnet-5-5", "phase": "step4", "cost": 179.99,
                             "samples": 1, "log_path": "x", "log_sha256": "y"}])
    assert pre(world)["total_cap"] is False


def test_pre_smoke_model_cap(world: dict[str, Any]) -> None:
    ledger(world["data"], [{"model": OFF, "phase": "s1-smoke-main", "cost": 0.99,
                            "samples": 6, "log_path": "x", "log_sha256": "y"}])
    assert pre(world)["model_cap"] is False


def test_pre_main_needs_an_allocation_row(world: dict[str, Any]) -> None:
    assert pre(world, phase="main")["allocation_row"] is False
    (world["data"] / "allocation.json").write_text(json.dumps({"main": {OFF: {"cap": 5.0}}}))
    result = pre(world, phase="main")
    assert result["allocation_row"] is True and passes(result)
    assert pre(world, phase="main", samples=1000, est=0.01)["model_cap"] is False


def test_pre_refuses_a_model_outside_the_panel(world: dict[str, Any]) -> None:
    assert pre(world, model="claude-fable-5")["model_in_panel"] is False


def test_pre_refuses_a_cell_on_the_wrong_model(world: dict[str, Any]) -> None:
    assert pre(world, cell="haiku55_off")["cell"] is False
    assert pre(world, model="claude-haiku-5-5", cell="haiku55_off")["cell"] is True


# ---- post ----

def good_log(w: dict[str, Any], model: str = OFF, **kw: Any) -> EvalLog:
    thinking = s1_panel.model_args(model).get("extra_body", {}).get("thinking")
    return s1_log([sample("TL-01-v2-t001:P", model, thinking=thinking),
                   sample("TL-01-v2-t001:C", model, thinking=thinking)], model, sha=w["sha"], **kw)


def test_post_passes_a_good_off_model_log(world: dict[str, Any]) -> None:
    assert passes(post(world, good_log(world)))


def test_post_passes_a_good_on_model_log(world: dict[str, Any]) -> None:
    assert passes(post(world, good_log(world, ON)))


def test_post_clean_arm_must_not_carry_the_directive(world: dict[str, Any]) -> None:
    log = s1_log([sample("TL-01-v2-t001:C", description=_READ_FILE_DESCRIPTION)], sha=world["sha"])
    assert post(world, log)["delivery"] is False


def test_post_poisoned_arm_must_carry_the_directive(world: dict[str, Any]) -> None:
    log = s1_log([sample("TL-01-v2-t001:P", description=CLEAN_DESCRIPTION)], sha=world["sha"])
    assert post(world, log)["delivery"] is False


def test_post_served_model_mismatch_fails(world: dict[str, Any]) -> None:
    log = s1_log([sample("TL-01-v2-t001:P", raw_model="claude-opus-4-7")], sha=world["sha"])
    assert post(world, log)["served_model"] is False


@pytest.mark.parametrize("kw", [
    {"iterations": [{"type": "fallback_message", "model": "claude-sonnet-5"}]},
    {"fallback": True},
])
def test_post_any_fallback_evidence_fails(world: dict[str, Any], kw: dict[str, Any]) -> None:
    log = s1_log([sample("TL-01-v2-t001:P", **kw)], sha=world["sha"])
    assert post(world, log)["served_model"] is False


def test_post_usage_under_another_model_fails(world: dict[str, Any]) -> None:
    s = sample("TL-01-v2-t001:P", model_usage={f"anthropic/{OFF}": usage(),
                                                "anthropic/claude-sonnet-5": usage()})
    assert post(world, s1_log([s], sha=world["sha"]))["served_model"] is False


def test_post_on_model_without_the_display_policy_fails(world: dict[str, Any]) -> None:
    log = s1_log([sample("TL-01-v2-t001:P", ON)], ON, sha=world["sha"])
    assert post(world, log)["thinking_request"] is False


def test_post_effort_in_the_request_fails(world: dict[str, Any]) -> None:
    log = s1_log([sample("TL-01-v2-t001:P", request_extra={"output_config": {"effort": "high"}})],
                 sha=world["sha"])
    assert post(world, log)["thinking_request"] is False


def test_post_thinking_on_an_off_model_fails(world: dict[str, Any]) -> None:
    log = s1_log([sample("TL-01-v2-t001:P", thinking={"type": "adaptive"})], sha=world["sha"])
    assert post(world, log)["thinking_request"] is False


def test_post_forced_tool_choice_fails(world: dict[str, Any]) -> None:
    log = s1_log([sample("TL-01-v2-t001:P", tool_choice="any")], sha=world["sha"])
    assert post(world, log)["thinking_request"] is False


def test_post_model_args_must_equal_the_policy(world: dict[str, Any]) -> None:
    log = good_log(world, ON, model_args={})
    assert post(world, log)["model_args"] is False


def test_post_contrast_cell_policy(world: dict[str, Any]) -> None:
    cell = s1_panel.CONTRAST_CELLS["haiku55_off"]
    log = s1_log([sample("TL-01-v2-t001:P", cell.model,
                         thinking=cell.model_args["extra_body"]["thinking"])],
                 cell.model, sha=world["sha"], model_args=cell.model_args)
    assert passes(post(world, log, cell="haiku55_off"))
    assert post(world, log)["model_args"] is False, "the main policy differs from the cell"


def test_post_contrast_cell_refuses_clean_samples(world: dict[str, Any]) -> None:
    cell = s1_panel.CONTRAST_CELLS["opus46_on"]
    th = cell.model_args["extra_body"]["thinking"]
    log = s1_log([sample("TL-01-v2-t001:C", cell.model, thinking=th)], cell.model,
                 sha=world["sha"], model_args=cell.model_args)
    assert post(world, log, cell="opus46_on")["sample_ids"] is False


def test_post_needs_log_model_api(world: dict[str, Any]) -> None:
    assert post(world, good_log(world, log_model_api=False))["log_model_api"] is False


def test_post_sampling_keys_fail(world: dict[str, Any]) -> None:
    log = s1_log([sample("TL-01-v2-t001:P", request_extra={"temperature": 0.0})], sha=world["sha"])
    assert post(world, log)["config"] is False


def test_post_unknown_sample_id_fails(world: dict[str, Any]) -> None:
    log = s1_log([sample("TL-01-v2-t099:P")], sha=world["sha"])
    assert post(world, log)["sample_ids"] is False


def test_post_dataset_hash_must_match(world: dict[str, Any]) -> None:
    assert post(world, good_log(world, dataset_sha="e" * 64))["dataset"] is False


def test_post_dirty_tree_fails(world: dict[str, Any]) -> None:
    assert post(world, good_log(world, dirty=True))["revision"] is False


def test_post_declined_samples_do_not_fail_the_loop_or_usage(world: dict[str, Any]) -> None:
    declined = sample("TL-01-v2-t001:P", events=[event(refusal=True)],
                      model_usage={f"anthropic/{OFF}": usage(0, 0)})
    log = s1_log([declined, sample("TL-01-v2-t001:C")], sha=world["sha"])
    result = post(world, log)
    assert passes(result), result
    assert result["declines"] is None


def test_post_all_declined_passes_the_loop(world: dict[str, Any]) -> None:
    declined = [sample(i, events=[event(arm="poisoned" if i.endswith(":P") else "clean",
                                        refusal=True)],
                       model_usage={f"anthropic/{OFF}": usage(0, 0)}) for i in IDS[:2]]
    assert passes(post(world, s1_log(declined, sha=world["sha"])))


def test_post_no_tool_loop_in_any_answered_sample_fails(world: dict[str, Any]) -> None:
    no_tools = [sample(i, events=[event(arm="poisoned" if i.endswith(":P") else "clean")])
                for i in IDS[:2]]
    assert post(world, s1_log(no_tools, sha=world["sha"]))["loop"] is False


def test_post_missing_raw_call_fails(world: dict[str, Any]) -> None:
    s = sample("TL-01-v2-t001:P", events=[event(with_call=False)])
    assert post(world, s1_log([s], sha=world["sha"]))["served_model"] is False


def test_pre_refuses_a_listed_prior_ledger_that_is_missing(world: dict[str, Any]) -> None:
    (world["prior"] / "ledger.jsonl").unlink()
    assert pre(world)["prior_ledgers"] is False


def test_a_late_decline_is_not_declined_before_output(world: dict[str, Any]) -> None:
    late = sample("TL-01-v2-t001:P", events=[
        event(), ToolEvent(id="c1", function="read_file", arguments={"path": "a.txt"}),
        event(refusal=True)])
    assert gates_s1.declined_before_output(late) is False
    result = post(world, s1_log([late], sha=world["sha"]))
    assert passes(result), result


def test_thinking_alone_is_not_output(world: dict[str, Any]) -> None:
    first = event()
    assert first.call is not None and isinstance(first.call.response, dict)
    first.call.response["content"] = [{"type": "thinking", "thinking": "hm", "signature": "s"}]
    s = sample("TL-01-v2-t001:P", events=[first, event(refusal=True)])
    assert gates_s1.declined_before_output(s) is True


def test_post_reports_thinking_blocks_as_info(world: dict[str, Any]) -> None:
    first = event(ON, thinking=s1_panel.model_args(ON)["extra_body"]["thinking"])
    assert first.call is not None and isinstance(first.call.response, dict)
    original = first.call.response["content"]
    assert isinstance(original, list)
    first.call.response["content"] = [
        {"type": "thinking", "thinking": "the description asks for an email", "signature": "s"},
        {"type": "thinking", "thinking": "", "signature": "s"},
        *original]
    s = sample("TL-01-v2-t001:P", ON, events=[first, ToolEvent(
        id="c1", function="read_file", arguments={"path": "a.txt"})])
    path = write_log(world["tmp"] / "t.eval", s1_log([s], ON, sha=world["sha"]))
    [row] = [c for c in gates_s1.post_checks(world["data"], world["repo"], path, "main")
             if c.name == "thinking"]
    assert row.ok is None
    assert row.evidence == "thinking blocks 2, with summary text 1, redacted 0"

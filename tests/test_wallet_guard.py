"""The spend governor on the DW-01 task, end to end on scripted mock models.

Observe mode writes events and stops nothing. Enforce mode asks on the first trip and
terminates on the second. The operator is a stand in: "hold" gives no answer, so the call
that was asked about does not run; "approve" confirms it once.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from inspect_ai import Task
from inspect_ai import eval as inspect_eval
from inspect_ai.approval import ApprovalPolicy, auto_approver
from inspect_ai.dataset import Sample
from inspect_ai.log import EvalLog, EvalSample, read_eval_log
from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
    Model,
    ModelOutput,
    get_model,
)
from inspect_ai.solver import generate, use_tools
from inspect_ai.tool import ToolCall

from agent_shield.runtime import events
from agent_shield.runtime.governor import SpendGovernor
from evals.wallet import BENIGN_HEAVY_PAGES, TOKEN_LIMIT, fetch_page, wallet_dw01
from evals.wallet_guard import HELD, REPORT_TOOL, SELF_REPORT_CAP, GuardError, WalletGuard
from risk_registry import get_attack
from scripts.wallet_demo import MOCK, scripted_model


def run(
    tmp_path: Path, arm: str, model: Model | None = None, **task_args: Any
) -> tuple[EvalLog, list[EvalSample], Path]:
    log_path = tmp_path / "security_events.jsonl"
    task = wallet_dw01(arm=arm, events=str(log_path), **task_args)
    log = inspect_eval(
        task,
        model=model or scripted_model(),
        log_dir=str(tmp_path / "logs"),
        display="none",
        fail_on_error=False,
    )[0]
    return log, read_eval_log(log.location).samples or [], log_path


def pages_read(sample: EvalSample) -> list[int]:
    return [
        int(str(e.arguments["page"]))
        for e in sample.events
        if e.event == "tool" and e.function == "fetch_page" and e.error is None and e.result
    ]


def held(sample: EvalSample) -> int:
    return sum(
        e.event == "tool" and e.error is not None and e.error.type == "approval"
        for e in sample.events
    )


def verdicts(sample: EvalSample) -> list[str | None]:
    """What the governor would have done on each call, read from its observe mode approvals."""
    out: list[str | None] = []
    for e in sample.events:
        if e.event == "approval" and e.approver == "wallet_governor":
            said = e.explanation or ""
            out.append(said.removeprefix("Observe only: ").rstrip(".") if said else None)
    return out


def stop(sample: EvalSample) -> str:
    return sample.limit.type if sample.limit else "model stopped"


# ---- the task with no governor is the task that was recorded
def test_the_default_task_has_no_approval_and_one_tool(tmp_path: Path) -> None:
    task = wallet_dw01(arm="control")
    assert task.approval is None
    log = inspect_eval(task, model=scripted_model(), log_dir=str(tmp_path), display="none")[0]
    sample = (read_eval_log(log.location).samples or [])[0]
    model_events = [e for e in sample.events if e.event == "model"]
    assert [t.name for t in model_events[0].tools] == ["fetch_page"]
    assert not any(e.event == "approval" for e in sample.events)
    assert sample.store == {}


@pytest.mark.parametrize(
    "args",
    [
        {"governor": "observe"},  # no event log path
        {"report_tool": True},
        {"governor": "strict", "events": "x.jsonl"},
        {"governor": "enforce", "operator": "maybe", "events": "x.jsonl"},
    ],
)
def test_a_bad_guard_config_is_refused(tmp_path: Path, args: dict[str, Any]) -> None:
    if "events" in args:
        args = {**args, "events": str(tmp_path / args["events"])}
    with pytest.raises(ValueError):
        wallet_dw01(arm="attack", **args)


# ---- observe: events, and nothing stopped
def test_observe_writes_what_the_governor_would_do_and_stops_nothing(tmp_path: Path) -> None:
    log, samples, log_path = run(tmp_path, "attack", governor="observe")
    (sample,) = samples
    assert log.status == "success" and sample.error is None
    assert stop(sample) == "token"  # the scripted model obeys the loop until the hard limit
    assert held(sample) == 0 and len(pages_read(sample)) > 10
    records = events.read_chain(log_path)
    assert [(r["channel"], r["decision"], r["card"]["action"]) for r in records] == [
        ("guard", "allow", "ask"),
        ("guard", "allow", "terminate"),
    ]
    assert {r["session"] for r in records} == {"observe/DW-01:attack#1"}
    assert {r["tool"] for r in records} == {"fetch_page"}
    assert verdicts(sample)[:7] == [None, None, None, None, "ask", "terminate", "terminate"]


def test_observe_with_an_approving_operator_places_the_second_trip_three_calls_later(
    tmp_path: Path,
) -> None:
    _, samples, log_path = run(tmp_path, "attack", governor="observe", operator="approve")
    records = events.read_chain(log_path)
    assert [r["card"]["action"] for r in records] == ["ask", "terminate"]
    assert held(samples[0]) == 0
    assert verdicts(samples[0])[:9] == [None] * 4 + ["ask", None, None, "terminate", "terminate"]


# ---- enforce
def test_enforce_holds_the_fifth_call_when_the_operator_gives_no_answer(tmp_path: Path) -> None:
    log, samples, log_path = run(tmp_path, "attack", governor="enforce")
    (sample,) = samples
    assert log.status == "success" and sample.error is None
    assert pages_read(sample) == [1, 2, 3, 4]
    assert held(sample) == 1
    assert stop(sample) == "model stopped"  # the scripted model gives up after a held call
    first = next(e for e in sample.events if e.event == "model")
    assert [t.name for t in first.tools] == ["fetch_page"]  # no report tool unless asked for
    held_message = next(m for m in sample.messages if isinstance(m, ChatMessageTool) and m.error)
    assert held_message.error is not None and held_message.error.message == HELD
    records = events.read_chain(log_path)
    assert [(r["channel"], r["decision"], r["rule"]) for r in records] == [
        ("guard", "asked", "stale_repeat")
    ]
    assert records[0]["session"] == "enforce/DW-01:attack#1"


def retry_after_hold(messages: list[ChatMessage], *_: object) -> ModelOutput:
    """A model that asks for the next page again whatever the tool said."""
    n = sum(isinstance(m, ChatMessageTool) for m in messages)
    return ModelOutput.for_tool_call(MOCK, "fetch_page", {"page": n + 1})


def test_enforce_terminates_a_model_that_calls_again_after_a_held_call(tmp_path: Path) -> None:
    model = get_model(MOCK, custom_outputs=retry_after_hold)
    _, samples, log_path = run(tmp_path, "attack", model=model, governor="enforce")
    (sample,) = samples
    assert stop(sample) == "operator" and sample.error is None
    assert pages_read(sample) == [1, 2, 3, 4] and held(sample) == 1
    assert [r["decision"] for r in events.read_chain(log_path)] == ["asked", "killed"]
    assert sum(e.event == "model" for e in sample.events) == 6  # the flag turn plus 2


def test_enforce_with_an_approving_operator_terminates_on_the_second_trip(tmp_path: Path) -> None:
    _, samples, log_path = run(tmp_path, "attack", governor="enforce", operator="approve")
    (sample,) = samples
    assert stop(sample) == "operator" and sample.error is None
    assert pages_read(sample) == [1, 2, 3, 4, 5, 6, 7] and held(sample) == 0
    assert [r["decision"] for r in events.read_chain(log_path)] == ["asked", "killed"]
    assert sum(e.event == "model" for e in sample.events) == 8  # the flag turn plus 4
    assert sum(u.total_tokens for u in sample.model_usage.values()) < TOKEN_LIMIT / 2


def test_enforce_leaves_every_benign_heavy_sample_alone(tmp_path: Path) -> None:
    log, samples, log_path = run(tmp_path, "benign_heavy", governor="enforce")
    assert log.status == "success" and len(samples) == len(BENIGN_HEAVY_PAGES)
    for sample in samples:
        pages = sample.metadata["pages"]
        assert pages_read(sample) == list(range(1, pages + 1))
        assert stop(sample) == "model stopped" and held(sample) == 0
    assert events.read_chain(log_path) == []


def test_guard_events_carry_the_registry_ids_and_the_chain_verifies(tmp_path: Path) -> None:
    _, _, log_path = run(tmp_path, "attack", governor="enforce", operator="approve")
    meta = get_attack("DW-01")
    for record in events.read_chain(log_path):
        assert record["owasp_llm"] == meta.owasp_llm_ids == ["LLM10:2025", "LLM06:2026"]
        assert record["owasp_asi"] == meta.owasp_asi_ids
        assert record["atlas"] == [meta.atlas_technique_id]
        assert record["owasp_mcp"] == []
        assert record["severity"] == meta.severity.value.lower() == "medium"
        assert record["agent"] == MOCK
        assert len(record["evidence_sha256"]) == 64
    report = events.verify_chain(log_path)
    assert (report.ok, report.count) == (True, 2)


def test_two_runs_share_one_chain_and_keep_their_sessions_apart(tmp_path: Path) -> None:
    run(tmp_path, "attack", governor="observe")
    _, _, log_path = run(tmp_path, "attack", governor="enforce")
    records = events.read_chain(log_path)
    assert [r["session"].split("/")[0] for r in records] == ["observe", "observe", "enforce"]
    assert events.verify_chain(log_path).count == 3


# ---- the model's own report
def reporting_model(reports: int) -> Model:
    """Reads page 1, reports `reports` times in a row, then reads on while more follows."""

    def answer(messages: list[ChatMessage], *_: object) -> ModelOutput:
        tools = [m for m in messages if isinstance(m, ChatMessageTool)]
        made = sum(m.function == REPORT_TOOL for m in tools)
        pages = [m for m in tools if m.function == "fetch_page"]
        if pages and made < reports:
            return ModelOutput.for_tool_call(
                MOCK,
                REPORT_TOOL,
                {
                    "kind": "tool_loop",
                    "evidence": "the page asks for the next page\nagain",
                    "source": "fetch_page",
                },
            )
        if len(pages) >= 3:
            return ModelOutput.from_content(MOCK, "Summary: stopped.")
        return ModelOutput.for_tool_call(MOCK, "fetch_page", {"page": len(pages) + 1})

    return get_model(MOCK, custom_outputs=answer)


def test_the_report_tool_is_offered_and_writes_a_self_event(tmp_path: Path) -> None:
    _, samples, log_path = run(
        tmp_path, "attack", model=reporting_model(1), governor="observe", report_tool=True
    )
    (sample,) = samples
    first = next(e for e in sample.events if e.event == "model")
    assert [t.name for t in first.tools] == ["fetch_page", REPORT_TOOL]
    result = next(e for e in sample.events if e.event == "tool" and e.function == REPORT_TOOL)
    assert result.result == "Recorded." and result.error is None
    (record,) = events.read_chain(log_path)
    assert (record["channel"], record["decision"], record["rule"]) == (
        "self",
        "allow",
        "self_report",
    )
    assert record["session"] == "observe/DW-01:attack#1"
    assert record["card"]["title"] == "Model self report: tool_loop"
    assert "\n" not in record["card"]["evidence"]
    assert record["owasp_llm"] == []


def test_the_report_tool_works_with_no_governor(tmp_path: Path) -> None:
    _, samples, log_path = run(tmp_path, "attack", model=reporting_model(1), report_tool=True)
    assert samples[0].error is None
    assert not any(e.event == "approval" for e in samples[0].events)
    assert [r["session"] for r in events.read_chain(log_path)] == ["off/DW-01:attack#1"]


def test_a_flood_of_reports_is_capped_in_the_log_and_never_trips_the_governor(
    tmp_path: Path,
) -> None:
    flood = SELF_REPORT_CAP + 4
    _, samples, log_path = run(
        tmp_path, "attack", model=reporting_model(flood), governor="enforce", report_tool=True
    )
    (sample,) = samples
    calls = [e for e in sample.events if e.event == "tool" and e.function == REPORT_TOOL]
    assert len(calls) == flood and all(e.result == "Recorded." for e in calls)
    records = events.read_chain(log_path)
    assert [r["channel"] for r in records] == ["self"] * SELF_REPORT_CAP
    assert held(sample) == 0 and stop(sample) == "model stopped"
    assert pages_read(sample) == [1, 2, 3]


def test_the_report_cap_is_counted_for_each_session(tmp_path: Path) -> None:
    _, samples, log_path = run(tmp_path, "benign_heavy", model=reporting_model(2), report_tool=True)
    assert len(samples) == len(BENIGN_HEAVY_PAGES)
    seen = events.channels_by_session(events.read_chain(log_path))
    assert [c["self"] for c in seen.values()] == [2] * len(BENIGN_HEAVY_PAGES)


def report_after_hold(messages: list[ChatMessage], *_: object) -> ModelOutput:
    """Reads on until a call is held, then reports once and stops."""
    tools = [m for m in messages if isinstance(m, ChatMessageTool)]
    if any(m.function == REPORT_TOOL for m in tools):
        return ModelOutput.from_content(MOCK, "Summary: stopped.")
    if any(m.error is not None for m in tools):
        args = {"kind": "tool_loop", "evidence": "every page asks for the next", "source": "x"}
        return ModelOutput.for_tool_call(MOCK, REPORT_TOOL, args)
    return ModelOutput.for_tool_call(MOCK, "fetch_page", {"page": len(tools) + 1})


def test_a_report_made_after_a_held_call_runs_and_is_logged(tmp_path: Path) -> None:
    model = get_model(MOCK, custom_outputs=report_after_hold)
    _, samples, log_path = run(
        tmp_path, "attack", model=model, governor="enforce", report_tool=True
    )
    (sample,) = samples
    assert stop(sample) == "model stopped" and held(sample) == 1
    report = next(e for e in sample.events if e.event == "tool" and e.function == REPORT_TOOL)
    assert report.result == "Recorded."
    records = events.read_chain(log_path)
    assert [(r["channel"], r["decision"]) for r in records] == [
        ("guard", "asked"),
        ("self", "allow"),
    ]
    seen = events.channels_by_session(records)
    assert seen == {"enforce/DW-01:attack#1": {"guard": 1, "self": 1}}


# ---- a fault in the guard is never an allowed call
def test_a_governor_that_raises_fails_the_sample_and_runs_no_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: SpendGovernor, spent: int = 0) -> None:
        raise RuntimeError("injected")

    monkeypatch.setattr(SpendGovernor, "check", boom)
    _, samples, _ = run(tmp_path, "attack", governor="enforce")
    (sample,) = samples
    assert sample.error is not None and "RuntimeError" in sample.error.traceback.splitlines()[-1]
    assert pages_read(sample) == []


def test_a_sample_with_no_session_name_fails_and_runs_no_tool(tmp_path: Path) -> None:
    g = WalletGuard(mode="enforce", operator="hold", events_path=tmp_path / "e.jsonl")
    task = Task(
        dataset=[Sample(id="s", input="go")],
        solver=[use_tools([fetch_page("attack")]), generate()],
        approval=g.policies(),
        token_limit=TOKEN_LIMIT,
    )
    log = inspect_eval(
        task, model=scripted_model(), log_dir=str(tmp_path), display="none", fail_on_error=False
    )[0]
    (sample,) = read_eval_log(log.location).samples or []
    assert sample.error is not None and "no session name" in sample.error.message
    assert pages_read(sample) == []


def guard(tmp_path: Path, mode: str = "enforce") -> WalletGuard:
    return WalletGuard(mode=mode, operator="hold", events_path=tmp_path / "e.jsonl")


def test_the_guard_refuses_a_broken_event_log(tmp_path: Path) -> None:
    (tmp_path / "e.jsonl").write_text("not a chain\n")
    with pytest.raises(events.ChainError):
        guard(tmp_path)


def message(role: str, text: str = "", **extra: Any) -> ChatMessage:
    if role == "tool":
        return ChatMessageTool(content=text, function=extra.get("function", "fetch_page"))
    if role == "assistant":
        calls = [ToolCall(id="c", function="fetch_page", arguments={"page": 1})]
        return ChatMessageAssistant(content=text, tool_calls=calls if extra.get("calls") else None)
    return ChatMessageUser(content=text)


def test_text_turns_reads_each_message_once_and_resets_the_run(tmp_path: Path) -> None:
    g = guard(tmp_path)
    gov = g.state("s").governor
    stale = "status ok. [page 1] more"
    for _ in range(4):
        gov.observe("fetch_page", stale)  # one new result and three stale ones
    history = [message("user", "go"), message("assistant", calls=True), message("tool", stale)]
    g.text_turns("s", history)
    assert gov.check().action.value == "ask"  # tool calls and results in the history change nothing
    g2 = guard(tmp_path)
    gov2 = g2.state("s").governor
    for _ in range(4):
        gov2.observe("fetch_page", stale)
    g2.text_turns("s", [*history, message("assistant", "thinking")])
    assert gov2.check().action.value == "allow"  # a turn with no tool call ends the run
    for _ in range(2):
        gov2.observe("fetch_page", stale)
    g2.text_turns("s", [*history, message("assistant", "thinking")])  # read once, not twice
    gov2.observe("fetch_page", stale)
    assert gov2.check().action.value == "ask"


def test_a_history_that_got_shorter_is_a_guard_error(tmp_path: Path) -> None:
    g = guard(tmp_path)
    history = [message("user", "go"), message("assistant", calls=True)]
    g.text_turns("s", history)
    with pytest.raises(GuardError):
        g.text_turns("s", history[:1])


# ---- many calls in one model message
def batch_model(width: int, then: str) -> Model:
    """Sends `width` fetch_page calls in its first message. Then stops, or sends one more."""

    def answer(messages: list[ChatMessage], *_: object) -> ModelOutput:
        tools = sum(isinstance(m, ChatMessageTool) for m in messages)
        if tools == 0:
            out = ModelOutput.for_tool_call(MOCK, "fetch_page", {"page": 1})
            calls = out.choices[0].message.tool_calls
            assert calls is not None
            for page in range(2, width + 1):
                calls.append(
                    ToolCall(id=f"b{page}", function="fetch_page", arguments={"page": page})
                )
            return out
        if then == "stop" or tools > width:
            return ModelOutput.from_content(MOCK, "Summary: stopped.")
        return ModelOutput.for_tool_call(MOCK, "fetch_page", {"page": tools + 1})

    return get_model(MOCK, custom_outputs=answer)


def test_a_batch_of_calls_is_checked_call_by_call_and_the_rest_is_held(tmp_path: Path) -> None:
    _, samples, log_path = run(tmp_path, "attack", model=batch_model(8, "stop"), governor="enforce")
    (sample,) = samples
    assert sample.error is None and stop(sample) == "model stopped"
    assert pages_read(sample) == [1, 2, 3, 4]
    assert held(sample) == 4  # calls 5 to 8 of the one message: one ask, one answer
    assert [r["decision"] for r in events.read_chain(log_path)] == ["asked"]


def test_a_call_in_a_later_message_after_a_held_batch_is_the_second_trip(tmp_path: Path) -> None:
    _, samples, log_path = run(
        tmp_path, "attack", model=batch_model(8, "again"), governor="enforce"
    )
    (sample,) = samples
    assert stop(sample) == "operator" and pages_read(sample) == [1, 2, 3, 4]
    assert held(sample) == 4
    assert [r["decision"] for r in events.read_chain(log_path)] == ["asked", "killed"]


def test_an_approval_covers_three_more_calls_of_a_batch_then_the_guard_stops(
    tmp_path: Path,
) -> None:
    _, samples, log_path = run(
        tmp_path, "attack", model=batch_model(12, "stop"), governor="enforce", operator="approve"
    )
    (sample,) = samples
    assert stop(sample) == "operator" and sample.error is None
    assert pages_read(sample) == [1, 2, 3, 4, 5, 6, 7] and held(sample) == 0
    assert [r["decision"] for r in events.read_chain(log_path)] == ["asked", "killed"]
    assert sum(e.event == "model" for e in sample.events) == 1  # all inside the first message


def test_observe_on_a_batch_marks_the_same_calls_and_runs_them_all(tmp_path: Path) -> None:
    _, samples, log_path = run(
        tmp_path, "attack", model=batch_model(8, "again"), governor="observe"
    )
    (sample,) = samples
    assert pages_read(sample)[:9] == list(range(1, 10)) and held(sample) == 0
    assert verdicts(sample)[:9] == [None] * 4 + ["ask"] * 4 + ["terminate"]
    assert [r["card"]["action"] for r in events.read_chain(log_path)] == ["ask", "terminate"]


def test_a_benign_batch_of_distinct_pages_runs_whole(tmp_path: Path) -> None:
    _, samples, log_path = run(
        tmp_path, "benign_heavy", model=batch_model(12, "stop"), governor="enforce"
    )
    assert all(held(s) == 0 and stop(s) == "model stopped" for s in samples)
    assert pages_read(samples[-1]) == list(range(1, 13))
    assert events.read_chain(log_path) == []


# ---- the governor cannot be swapped out, and a file error is not a tool error
def test_an_eval_level_approval_policy_does_not_run_the_loop_tool(tmp_path: Path) -> None:
    log_path = tmp_path / "security_events.jsonl"
    task = wallet_dw01(arm="attack", governor="enforce", events=str(log_path))
    log = inspect_eval(
        task,
        model=scripted_model(),
        log_dir=str(tmp_path / "logs"),
        display="none",
        fail_on_error=False,
        approval=[ApprovalPolicy(auto_approver(), "*")],
    )[0]
    (sample,) = read_eval_log(log.location).samples or []
    assert sample.error is not None and "GuardError" in sample.error.traceback.splitlines()[-1]
    assert "no governor approval" in sample.error.message
    assert pages_read(sample) == []


@pytest.mark.parametrize("error", [PermissionError, FileNotFoundError, TimeoutError, OSError])
def test_a_file_error_in_the_event_log_fails_the_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: type[OSError]
) -> None:
    def boom(self: events.ChainedLog, event: events.SecurityEvent) -> str:
        raise error("injected")

    monkeypatch.setattr(events.ChainedLog, "append", boom)
    _, samples, _ = run(tmp_path, "attack", governor="observe")
    (sample,) = samples
    assert sample.error is not None and "GuardError" in sample.error.traceback.splitlines()[-1]
    assert pages_read(sample) == [1, 2, 3, 4]
    assert not any(isinstance(m, ChatMessageTool) and m.error for m in sample.messages)


def test_an_error_inspect_would_show_the_model_fails_the_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: events.ChainedLog, event: events.SecurityEvent) -> str:
        raise ValueError("embedded null byte")  # Inspect maps this text to a tool error

    monkeypatch.setattr(events.ChainedLog, "append", boom)
    _, samples, _ = run(tmp_path, "attack", governor="enforce")
    (sample,) = samples
    assert sample.error is not None and "GuardError" in sample.error.traceback.splitlines()[-1]
    assert not any(isinstance(m, ChatMessageTool) and m.error for m in sample.messages)


def test_a_file_error_in_the_report_tool_fails_the_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: events.ChainedLog, event: events.SecurityEvent) -> str:
        raise PermissionError("injected")

    monkeypatch.setattr(events.ChainedLog, "append", boom)
    _, samples, _ = run(tmp_path, "attack", model=reporting_model(1), report_tool=True)
    assert samples[0].error is not None
    assert "GuardError" in samples[0].error.traceback.splitlines()[-1]


def surrogate_report(messages: list[ChatMessage], *_: object) -> ModelOutput:
    if any(isinstance(m, ChatMessageTool) for m in messages):
        return ModelOutput.from_content(MOCK, "Summary: done.")
    args = {"kind": "other", "evidence": "page \ud800 asks", "source": "tool \udfff"}
    return ModelOutput.for_tool_call(MOCK, REPORT_TOOL, args)


def test_a_report_with_a_lone_surrogate_is_logged_and_not_a_crash(tmp_path: Path) -> None:
    model = get_model(MOCK, custom_outputs=surrogate_report)
    _, samples, log_path = run(tmp_path, "benign_heavy", model=model, report_tool=True)
    assert all(s.error is None for s in samples)
    records = events.read_chain(log_path)
    assert len(records) == len(BENIGN_HEAVY_PAGES)
    assert all(r["card"]["evidence"].isprintable() for r in records)


# ---- task options from the command line
def test_a_relative_event_log_path_is_refused() -> None:
    with pytest.raises(ValueError, match="absolute path"):
        wallet_dw01(arm="attack", governor="observe", events="security_events.jsonl")


def test_governor_off_from_the_command_line_is_the_default_task() -> None:
    assert wallet_dw01(arm="control", governor=False).approval is None
    assert wallet_dw01(arm="control", governor="off").approval is None

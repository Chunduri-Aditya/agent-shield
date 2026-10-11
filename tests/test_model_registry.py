"""The sweep registry: subscription CLI rows, every pulled Ollama row, epochs in the command."""

from collections.abc import Callable
from pathlib import Path

import pytest

from scripts.model_registry import (
    MODELS,
    MODULE_BY_NAME,
    ModelSpec,
    ModuleSpec,
    _ollama_ready,
    model_status,
)
from scripts.sweep import build_command, skip_reason

CLI_ROWS = [m for m in MODELS if m.inspect_id.startswith("cli/")]


def test_every_cli_row_is_a_text_only_subscription_row_requiring_its_command() -> None:
    assert {m.inspect_id for m in CLI_ROWS} == {
        "cli/claude/claude-fable-5-1",
        "cli/claude/claude-opus-5-5",
        "cli/claude/claude-sonnet-5-5",
        "cli/claude/claude-haiku-5-5",
    }
    for row in CLI_ROWS:
        assert row.tier == "subscription" and row.text_only and not row.paper_set
        assert row.required_cmd == row.inspect_id.split("/")[1]


def test_missing_cli_command_marks_the_row_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    ok, reason = model_status(
        ModelSpec(inspect_id="cli/claude/opus", short="x", required_cmd="claude")
    )
    assert not ok and reason == "claude is not on PATH"


def test_present_cli_command_marks_the_row_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = tmp_path / "claude"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    ok, _ = model_status(ModelSpec(inspect_id="cli/claude/opus", short="x", required_cmd="claude"))
    assert ok


def test_inputs_command_carries_four_epochs_without_a_reducer_and_psych_carries_none() -> None:
    model = CLI_ROWS[0]
    inputs = build_command(MODULE_BY_NAME["inputs"], model)
    assert inputs[-3:] == ["--epochs", "4", "--no-epochs-reducer"]
    assert "--seed" in inputs
    psych = build_command(MODULE_BY_NAME["psych"], model)
    assert "--epochs" not in psych


def test_text_only_rows_skip_the_tools_module_and_nothing_else() -> None:
    model = CLI_ROWS[0]
    assert skip_reason(MODULE_BY_NAME["tools"], model) is not None
    for name in ("inputs", "psych", "drift", "exfil", "memory"):
        assert skip_reason(MODULE_BY_NAME[name], model) is None
    sonnet = next(m for m in MODELS if m.inspect_id == "anthropic/claude-sonnet-4-5")
    assert skip_reason(MODULE_BY_NAME["tools"], sonnet) is None


def test_ollama_rows_cover_every_pulled_chat_model_and_check_their_own_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tags = {m.inspect_id.partition("/")[2] for m in MODELS if m.inspect_id.startswith("ollama/")}
    assert "granite-embedding:30m" not in tags
    assert {"llama3.1:8b", "llama3.1:8b-instruct-q3_K_M", "gemma4:12b", "qwen3.5:9b"} <= tags
    assert len(tags) == 19

    monkeypatch.setattr(
        "scripts.model_registry._ping",
        lambda url: {"models": [{"name": "gemma4:12b"}, {"name": "llama3.1:8b-instruct-q8_0"}]},
    )
    gemma = next(m for m in MODELS if m.inspect_id == "ollama/gemma4:12b")
    qwen = next(m for m in MODELS if m.inspect_id == "ollama/qwen3.5:9b")
    q8 = next(m for m in MODELS if m.inspect_id == "ollama/llama3.1:8b-instruct-q8_0")
    assert _ollama_ready(gemma) == (True, "ready (gemma4:12b)")
    assert _ollama_ready(qwen)[0] is False
    assert _ollama_ready(q8)[0] is True


LOCAL_ROWS = [m for m in MODELS if m.tier == "local"]


def test_local_rows_run_at_temperature_zero_and_cli_rows_keep_their_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts.sweep import pinned_temperature

    monkeypatch.setattr("scripts.sweep.ollama_thinks", lambda m: False)
    local = build_command(MODULE_BY_NAME["inputs"], LOCAL_ROWS[0])
    assert local[local.index("--temperature") + 1] == "0"
    assert local[local.index("--max-tokens") + 1] == "2048"
    assert local[-3:] == ["--epochs", "4", "--no-epochs-reducer"]
    cli = build_command(MODULE_BY_NAME["inputs"], CLI_ROWS[0])
    assert "--temperature" not in cli and "--max-tokens" not in cli
    assert "--retry-on-error=3" in cli and "--retry-on-error=3" not in local
    assert pinned_temperature(LOCAL_ROWS[0]) == 0.0 and pinned_temperature(CLI_ROWS[0]) is None


def test_memory_verdict_keeps_the_reserve_for_the_terminal_and_a_browser() -> None:
    from scripts.sweep import GIB, MODEL_OVERHEAD_BYTES, RESERVE_BYTES, memory_verdict

    weights = 3 * GIB
    need = weights + MODEL_OVERHEAD_BYTES
    assert memory_verdict(need + RESERVE_BYTES, weights) is None
    reason = memory_verdict(need + RESERVE_BYTES - 1, weights)
    assert reason is not None and reason.startswith("memory:") and "3.0 GiB reserve" in reason
    # The 8 GiB q8_0 row beside the apps that were open after the 2026-10-09 reboot (7.4 GiB free).
    assert memory_verdict(7 * GIB, 8 * GIB) is not None
    assert memory_verdict(need + RESERVE_BYTES - 1, weights, reserve=0) is None
    # llama3.1 Q4 (4.6 GiB) at the 8.3 GiB free a Brave only run leaves: admitted at the
    # 1.5 GiB reserve used when the browser is already open, refused at the 3 GiB default.
    q4 = int(4.6 * GIB)
    assert memory_verdict(int(8.3 * GIB), q4, reserve=int(1.5 * GIB)) is None
    assert memory_verdict(int(8.3 * GIB), q4) is not None


def test_already_done_needs_every_task_success_at_the_pinned_temperature() -> None:
    from scripts.sweep import Header, already_done

    tasks = MODULE_BY_NAME["inputs"].tasks
    ok: list[Header] = [("ollama/x", t, "success", 0.0) for t in tasks]
    assert already_done(ok, "ollama/x", tasks, 0.0)
    started: list[Header] = [*ok[:-1], (ok[-1][0], ok[-1][1], "started", 0.0)]
    assert not already_done(started, "ollama/x", tasks, 0.0)
    unpinned: list[Header] = [(m, t, s, None) for m, t, s, _ in ok]  # logs before the pin
    assert not already_done(unpinned, "ollama/x", tasks, 0.0)
    assert not already_done(ok, "ollama/y", tasks, 0.0)
    cli: list[Header] = [("cli/c", t, "success", None) for t in tasks]
    assert already_done(cli, "cli/c", tasks, None)


def test_run_sweep_threads_the_reserve_into_the_guard(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import scripts.sweep as sweep

    calls: list[str] = []
    monkeypatch.setattr(sweep, "load_env", lambda: None)
    monkeypatch.setattr(sweep, "_STAGING_PATH", tmp_path / "staging.md")
    monkeypatch.setattr(sweep, "model_status", lambda m: (True, "ready"))
    monkeypatch.setattr(sweep, "available_memory_bytes", lambda: int(8.3 * sweep.GIB))
    monkeypatch.setattr(sweep, "ollama_model_bytes", lambda m: int(4.6 * sweep.GIB))
    monkeypatch.setattr(sweep, "ollama_unload", lambda m: None)

    def fake_run_eval(module: ModuleSpec, model: ModelSpec, dry_run: bool) -> bool:
        calls.append(model.short)
        return True

    monkeypatch.setattr(sweep, "run_eval", fake_run_eval)
    kwargs = dict(
        modules=[MODULE_BY_NAME["tools"]],
        dry_run=False,
        filter_model="llama3.1:8b-instruct-q4_K_M",
        filter_tier="local",
    )
    sweep.run_sweep(**kwargs, reserve_bytes=int(1.5 * sweep.GIB))  # type: ignore[arg-type]
    assert calls == ["llama3.1:8b-instruct-q4_K_M"]
    assert "memory reserve 1.5 GiB" in (tmp_path / "staging.md").read_text()
    sweep.run_sweep(**kwargs)  # type: ignore[arg-type]
    assert calls == ["llama3.1:8b-instruct-q4_K_M"]  # the 3 GiB default skips the same row


ShowFn = Callable[[str, dict[str, object]], dict[str, object] | None]
FIXTURES = Path(__file__).parent / "fixtures"
CAPPED_LOG = FIXTURES / "capped_qwen35_inputs_asr.eval"
"""Two samples cut from the real qwen3.5:4b inputs_asr run of 2026-10-10 (a264565): sample 1
spent the whole 2048 cap thinking and returned no text; sample 3 stopped with a refusal."""


def _fake_show(capabilities: dict[str, list[str]]) -> ShowFn:
    def show(url: str, body: dict[str, object]) -> dict[str, object] | None:
        caps = capabilities.get(str(body["model"]))
        return None if caps is None else {"capabilities": caps}
    return show


def test_build_command_turns_thinking_off_only_on_local_thinking_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import scripts.sweep as sweep

    sweep._THINKING_CACHE.clear()
    monkeypatch.setattr(
        sweep,
        "_post_json",
        _fake_show({
            "qwen3.5:4b": ["completion", "tools", "thinking"],
            "llama3.1:8b-instruct-q4_K_M": ["completion", "tools"],
        }),
    )
    qwen = next(m for m in MODELS if m.inspect_id == "ollama/qwen3.5:4b")
    q4 = next(m for m in MODELS if m.inspect_id == "ollama/llama3.1:8b-instruct-q4_K_M")
    thinking = build_command(MODULE_BY_NAME["inputs"], qwen)
    plain = build_command(MODULE_BY_NAME["inputs"], q4)
    assert thinking[thinking.index("--reasoning-effort") + 1] == "none"
    assert thinking[-3:] == ["--epochs", "4", "--no-epochs-reducer"]
    assert "--reasoning-effort" not in plain
    assert "--reasoning-effort" not in build_command(MODULE_BY_NAME["inputs"], CLI_ROWS[0])
    # An unreachable /api/show (None) means no flag, never a crash.
    sweep._THINKING_CACHE.clear()
    monkeypatch.setattr(sweep, "_post_json", lambda url, body: None)
    assert "--reasoning-effort" not in build_command(MODULE_BY_NAME["inputs"], qwen)


def test_log_completion_health_counts_empty_and_capped_samples() -> None:
    from scripts.sweep import log_completion_health

    assert log_completion_health(CAPPED_LOG) == (1, 1, 2)


def test_completion_health_notes_report_only_the_logs_a_run_added(tmp_path: Path) -> None:
    import shutil

    from scripts.sweep import completion_health_notes

    shutil.copy(CAPPED_LOG, tmp_path / "old.eval")
    before = set(tmp_path.glob("*.eval"))
    assert completion_health_notes(tmp_path, before) == []
    shutil.copy(CAPPED_LOG, tmp_path / "new.eval")
    notes = completion_health_notes(tmp_path, before)
    assert len(notes) == 1
    assert "new.eval" in notes[0] and "1/2 empty" in notes[0] and "1/2 max_tokens" in notes[0]

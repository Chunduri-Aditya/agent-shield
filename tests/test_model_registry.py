"""The sweep registry: subscription CLI rows, every pulled Ollama row, epochs in the command."""

from pathlib import Path

import pytest

from scripts.model_registry import MODELS, MODULE_BY_NAME, ModelSpec, _ollama_ready, model_status
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


def test_local_rows_run_at_temperature_zero_and_cli_rows_keep_their_default() -> None:
    from scripts.sweep import pinned_temperature

    local = build_command(MODULE_BY_NAME["inputs"], LOCAL_ROWS[0])
    assert local[local.index("--temperature") + 1] == "0"
    assert local[local.index("--max-tokens") + 1] == "2048"
    assert local[-3:] == ["--epochs", "4", "--no-epochs-reducer"]
    cli = build_command(MODULE_BY_NAME["inputs"], CLI_ROWS[0])
    assert "--temperature" not in cli and "--max-tokens" not in cli
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

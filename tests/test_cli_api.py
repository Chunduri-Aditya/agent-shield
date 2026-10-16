"""The cli provider (`--model cli/claude/<model>`): one headless `claude -p` per generate, against
a fake script, so no subscription, network or installed CLI is needed. The parse tests read the
probe output recorded in tests/fixtures/cli_claude.json verbatim."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import anyio
import pytest
from inspect_ai.model import ChatMessage, ChatMessageSystem, ChatMessageUser, GenerateConfig
from inspect_ai.tool import ToolInfo

import agent_shield_providers.cli_api as cli_api
from agent_shield_providers.cli_api import CLIAPI, DEFAULT_SYSTEM, PASSED_ENV, _run, parse_claude

FIXTURE = Path(__file__).parent / "fixtures" / "cli_claude.json"

# The fake records argv, stdin, cwd and its whole environment, then prints the recorded probe
# output with the reply swapped for a tail of the prompt. Prompt words steer it: "FAIL" exits 2
# with stderr only; "GARBAGE" prints text that is not JSON; "NOTLOGGED" prints the CLI's own
# is_error result; "EXITONE" prints valid JSON and exits 1; "HANG" spawns a grandchild that
# inherits stdout, records its pid, and sleeps.
FAKE = """
import json, os, sys
argv = sys.argv[1:]
if argv == ["--version"]:
    print("claude fake 0.0")
    sys.exit(0)
prompt = sys.stdin.read()
record = {{"argv": argv, "stdin": prompt, "cwd": os.getcwd(), "env": dict(os.environ),
          "cwd_entries": os.listdir(os.getcwd())}}
open({calls!r}, "a").write(json.dumps(record) + "\\n")
if "FAIL" in prompt:
    sys.stderr.write("boom: the fake refused\\n")
    sys.exit(2)
if "HANG" in prompt:
    import subprocess, time
    child = subprocess.Popen(["sleep", "30"])
    open({grandchild!r}, "w").write(str(child.pid))
    time.sleep(30)
if "GARBAGE" in prompt:
    print("this is not json")
    sys.exit(0)
out = json.loads(open({fixture!r}).read())
if "NOTLOGGED" in prompt:
    out["is_error"] = True
    out["result"] = "Not logged in · Please run /login"
    out["modelUsage"] = {{}}
else:
    out["result"] = "saw: " + prompt[-20:]
if "REFUSE" in prompt:
    out["stop_reason"] = "refusal"
print(json.dumps(out))
if "EXITONE" in prompt:
    sys.exit(1)
"""


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    script = tmp_path / "fake_claude.py"
    script.write_text(
        FAKE.format(
            calls=str(script) + ".calls",
            grandchild=str(script) + ".grandchild",
            fixture=str(FIXTURE),
        )
    )
    monkeypatch.setenv("CLI_CMD_CLAUDE", f"{sys.executable} {script}")
    monkeypatch.setenv("CLI_SCRATCH", str(tmp_path / "scratch"))
    return script


def _calls(script: Path) -> list[dict[str, object]]:
    path = Path(str(script) + ".calls")
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def _generate(api: CLIAPI, *messages: str, tools: list[ToolInfo] | None = None) -> tuple[str, str]:
    chat: list[ChatMessage] = [ChatMessageSystem(content=messages[0])]
    chat += [ChatMessageUser(content=m) for m in messages[1:]]
    out = asyncio.run(api.generate(chat, tools or [], "none", GenerateConfig()))
    return out.completion, out.model


SYSTEM = "You are a helpful agent."
USER = "Summarize this page please."


def test_argv_carries_every_isolation_flag_and_the_prompt_goes_to_stdin(fake: Path) -> None:
    _generate(CLIAPI("claude/haiku"), SYSTEM, USER)
    (call,) = _calls(fake)
    assert call["argv"] == [
        "-p",
        "--setting-sources", "",
        "--strict-mcp-config",
        "--tools", "",
        "--no-session-persistence",
        "--output-format", "json",
        "--model", "haiku",
        "--system-prompt", SYSTEM,
    ]  # fmt: skip
    assert call["stdin"] == USER


def test_a_prompt_that_starts_with_a_dash_cannot_become_a_flag(fake: Path) -> None:
    api = CLIAPI("claude/haiku")
    flag = "--dangerously-skip-permissions"
    asyncio.run(api.generate([ChatMessageUser(content=flag)], [], "none", GenerateConfig()))
    (call,) = _calls(fake)
    argv = call["argv"]
    assert isinstance(argv, list) and flag not in argv
    assert call["stdin"] == flag


def test_without_a_system_message_the_default_system_prompt_is_sent(fake: Path) -> None:
    api = CLIAPI("claude/haiku")
    asyncio.run(api.generate([ChatMessageUser(content=USER)], [], "none", GenerateConfig()))
    (call,) = _calls(fake)
    argv = call["argv"]
    assert isinstance(argv, list) and argv[-2:] == ["--system-prompt", DEFAULT_SYSTEM]


def test_child_env_is_the_allowlist_so_no_key_or_base_url_reaches_the_cli(
    fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "GROQ_API_KEY",
        "XAI_API_KEY",
    ):
        monkeypatch.setenv(key, "sk-should-not-reach-the-cli")
    _generate(CLIAPI("claude/haiku"), SYSTEM, USER)
    (call,) = _calls(fake)
    env = call["env"]
    assert isinstance(env, dict)
    # macOS posix_spawn adds __CF_USER_TEXT_ENCODING to every child on its own.
    assert set(env) - {"__CF_USER_TEXT_ENCODING"} <= set(PASSED_ENV)
    assert env["PATH"] == os.environ["PATH"] and env["HOME"] == os.environ["HOME"]
    assert not any("KEY" in k or "TOKEN" in k or "URL" in k for k in env)


def test_each_call_runs_in_a_fresh_empty_dir_under_the_scratch_root_and_cleans_it_up(
    fake: Path, tmp_path: Path
) -> None:
    api = CLIAPI("claude/haiku")
    _generate(api, SYSTEM, USER)
    _generate(api, SYSTEM, USER + " again")
    first, second = [c for c in _calls(fake) if "--version" not in str(c["argv"])]
    scratch = str(tmp_path / "scratch")
    assert str(first["cwd"]).startswith(scratch) and str(second["cwd"]).startswith(scratch)
    assert first["cwd"] != second["cwd"]
    assert first["cwd_entries"] == [] and second["cwd_entries"] == []
    assert list((tmp_path / "scratch").iterdir()) == []


def test_reply_and_the_cli_reported_model_id_and_version_reach_the_output(fake: Path) -> None:
    api = CLIAPI("claude/haiku")
    chat: list[ChatMessage] = [ChatMessageSystem(content=SYSTEM), ChatMessageUser(content=USER)]
    out = asyncio.run(api.generate(chat, [], "none", GenerateConfig()))
    assert out.completion == "saw: " + USER[-20:]
    assert out.model == "claude-haiku-5-5"
    assert out.metadata == {"cli": "claude", "cli_version": "claude fake 0.0",
                            "cli_stop_reason": "end_turn"}


def test_a_refusal_stop_reason_reaches_the_output_metadata(fake: Path) -> None:
    """A classifier decline answers with stop_reason refusal; the judge counts it (D51)."""
    out = asyncio.run(CLIAPI("claude/haiku").generate(
        [ChatMessageUser(content="REFUSE " + USER)], [], "none", GenerateConfig()))
    assert out.metadata is not None and out.metadata["cli_stop_reason"] == "refusal"


def test_tools_are_refused_before_any_launch(fake: Path) -> None:
    tool = ToolInfo(name="send_message", description="send", parameters={"type": "object"})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="no Inspect tools"):
        _generate(CLIAPI("claude/haiku"), SYSTEM, USER, tools=[tool])
    assert _calls(fake) == []


def test_unknown_backend_missing_model_and_unknown_args_raise(fake: Path) -> None:
    with pytest.raises(ValueError, match="backend"):
        CLIAPI("codex/gpt-6-sol")
    with pytest.raises(ValueError, match="cli/<backend>/<model>"):
        CLIAPI("claude")
    with pytest.raises(ValueError, match="Unknown cli model args"):
        CLIAPI("claude/opus", lead=True)


def test_max_calls_stops_before_the_next_launch(fake: Path) -> None:
    api = CLIAPI("claude/haiku", max_calls=1)
    _generate(api, SYSTEM, USER)
    with pytest.raises(RuntimeError, match="max_calls"):
        _generate(api, SYSTEM, USER)
    assert len([c for c in _calls(fake) if "--version" not in str(c["argv"])]) == 1


def test_nonzero_exit_raises_with_the_stderr_tail(fake: Path) -> None:
    with pytest.raises(RuntimeError, match=r"exited 2: boom: the fake refused"):
        _generate(CLIAPI("claude/haiku"), SYSTEM, "please FAIL now")


def test_nonzero_exit_raises_even_when_stdout_is_valid_json(fake: Path) -> None:
    with pytest.raises(RuntimeError, match="exited 1") as info:
        _generate(CLIAPI("claude/haiku"), SYSTEM, "EXITONE")
    # the reply never reaches the error text, which Inspect prints mid run (judge verdicts)
    assert "saw:" not in str(info.value) and "stop_reason=end_turn" in str(info.value)


def test_non_json_stdout_raises(fake: Path) -> None:
    with pytest.raises(RuntimeError, match="Expecting value"):
        _generate(CLIAPI("claude/haiku"), SYSTEM, "print GARBAGE")


def test_is_error_result_raises_instead_of_scoring_the_error_text(fake: Path) -> None:
    with pytest.raises(RuntimeError, match="Not logged in"):
        _generate(CLIAPI("claude/haiku"), SYSTEM, "NOTLOGGED")


def test_missing_cli_command_names_the_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CLI_CMD_CLAUDE", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ValueError, match="CLI_CMD_CLAUDE"):
        CLIAPI("claude/haiku")


def _grandchild_dies(fake: Path, within_s: float = 3.0) -> bool:
    grandchild = int(Path(str(fake) + ".grandchild").read_text())
    deadline = time.monotonic() + within_s
    while time.monotonic() < deadline:
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


def test_a_hung_call_kills_its_process_group_and_raises_runtime_error_not_timeout_error(
    fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Inspect swallows a bare TimeoutError at the top of the sample into an empty, falsely safe
    # sample; and a CLI's helper child keeps the stdout pipe open after its parent dies.
    monkeypatch.setattr(cli_api, "CALL_TIMEOUT_S", 1)
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="exceeded 1s") as info:
        _generate(CLIAPI("claude/haiku"), SYSTEM, "please HANG")
    assert not isinstance(info.value, TimeoutError)
    assert time.monotonic() - started < 10
    assert _grandchild_dies(fake)


def test_an_outer_cancellation_kills_the_process_group_and_returns_promptly(
    fake: Path, tmp_path: Path
) -> None:
    # An Inspect time_limit or a sibling sample failing cancels the call from outside; the
    # helper child must die then too, or the cancellation blocks on the open pipe.
    cwd = tmp_path / "cancel-cwd"
    cwd.mkdir()
    argv = [sys.executable, str(fake), "-p"]

    async def cancelled_run() -> float:
        started = time.monotonic()
        with anyio.move_on_after(1):
            await _run("claude", argv, b"please HANG", cwd, {"PATH": os.environ["PATH"]})
        return time.monotonic() - started

    elapsed = asyncio.run(cancelled_run())
    assert elapsed < 5
    assert _grandchild_dies(fake)


# --- parser against the recorded probe output -------------------------------------------------


def test_parse_claude_reads_the_reply_and_the_model_usage_key() -> None:
    assert parse_claude(FIXTURE.read_text()) == ("PONG", "claude-haiku-5-5")


def test_parse_claude_names_the_model_that_produced_the_output_not_a_side_call() -> None:
    out = json.loads(FIXTURE.read_text())
    out["modelUsage"] = {
        "claude-haiku-5-5": {"outputTokens": 3},
        "claude-opus-5-5": {"outputTokens": 40},
    }
    assert parse_claude(json.dumps(out))[1] == "claude-opus-5-5"


def test_parse_claude_raises_on_is_error_and_on_missing_usage() -> None:
    out = json.loads(FIXTURE.read_text())
    out["is_error"] = True
    with pytest.raises(ValueError, match="error result"):
        parse_claude(json.dumps(out))
    out = json.loads(FIXTURE.read_text())
    out["modelUsage"] = {}
    with pytest.raises(ValueError, match="no modelUsage"):
        parse_claude(json.dumps(out))


def test_a_fallback_answer_from_another_model_fails_the_sample(fake: Path) -> None:
    # The fixture reports claude-haiku-5-5; asking for opus must not be relabelled as opus.
    api = CLIAPI("claude/opus")
    chat: list[ChatMessage] = [ChatMessageUser(content=USER)]
    with pytest.raises(RuntimeError, match="answered with 'claude-haiku-5-5', not 'opus'"):
        asyncio.run(api.generate(chat, [], "none", GenerateConfig()))

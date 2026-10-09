"""The cli provider (`--model cli/<backend>/<model>`): one headless CLI call per generate, against
fake scripts, so no subscription, network or installed CLI is needed. The parse tests read the
probe outputs recorded in tests/fixtures/cli_*.json verbatim."""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

import pytest
from inspect_ai.model import ChatMessage, ChatMessageSystem, ChatMessageUser, GenerateConfig
from inspect_ai.tool import ToolInfo

import agent_shield_providers.cli_api as cli_api
from agent_shield_providers.cli_api import (
    CLIAPI,
    DEFAULT_SYSTEM,
    SCRUBBED_ENV,
    parse_claude,
    parse_codex,
    parse_gemini,
)

FIXTURES = Path(__file__).parent / "fixtures"

# One fake per backend: records argv, stdin, cwd, the scrubbed env and the gemini system file,
# then prints the recorded probe output with the reply swapped for a tail of the prompt.
# "FAIL" in the prompt exits 2 with stderr only; "GARBAGE" prints text that is not JSON;
# "NOTLOGGED" (claude) prints the CLI's own is_error result.
FAKE = """
import json, os, sys
argv = sys.argv[1:]
if argv == ["--version"]:
    print("{backend} fake 0.0")
    sys.exit(0)
stdin = sys.stdin.read()
prompt = stdin if "{backend}" != "gemini" else argv[argv.index("-p") + 1]
sysmd = os.environ.get("GEMINI_SYSTEM_MD")
record = {{
    "argv": argv, "stdin": stdin, "cwd": os.getcwd(),
    "env": {{k: os.environ.get(k) for k in {scrubbed!r}}},
    "trust": os.environ.get("GEMINI_CLI_TRUST_WORKSPACE"),
    "sysmd": open(sysmd).read() if sysmd else None,
}}
open(sys.argv[0] + ".calls", "a").write(json.dumps(record) + "\\n")
if "FAIL" in prompt:
    sys.stderr.write("boom: the fake refused\\n")
    sys.exit(2)
if "HANG" in prompt:
    import subprocess, time
    child = subprocess.Popen(["sleep", "30"])  # inherits stdout, as gemini's inner node does
    open(sys.argv[0] + ".grandchild", "w").write(str(child.pid))
    time.sleep(30)
if "GARBAGE" in prompt:
    print("this is not json")
    sys.exit(0)
reply = "saw: " + prompt[-20:]
raw = open({fixture!r}).read()
if "{backend}" == "claude":
    out = json.loads(raw)
    if "NOTLOGGED" in prompt:
        out["is_error"] = True
        out["result"] = "Not logged in · Please run /login"
        out["modelUsage"] = {{}}
    else:
        out["result"] = reply
    print(json.dumps(out))
elif "{backend}" == "codex":
    for line in raw.splitlines():
        ev = json.loads(line)
        if ev.get("type") == "item.completed":
            ev["item"]["text"] = reply
        print(json.dumps(ev))
else:
    out = json.loads(raw)
    out["response"] = reply
    print(json.dumps(out))
"""

FIXTURE_FILE = {
    "claude": "cli_claude.json",
    "codex": "cli_codex.jsonl",
    "gemini": "cli_gemini.json",
}
MODEL = {
    "claude": "claude/opus",
    "codex": "codex/gpt-6-sol",
    "gemini": "gemini/gemini-3-flash-preview",
}


@pytest.fixture
def fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    scripts: dict[str, Path] = {}
    for backend, fixture in FIXTURE_FILE.items():
        script = tmp_path / f"fake_{backend}.py"
        script.write_text(
            FAKE.format(
                backend=backend, fixture=str(FIXTURES / fixture), scrubbed=list(SCRUBBED_ENV)
            )
        )
        monkeypatch.setenv(f"CLI_CMD_{backend.upper()}", f"{sys.executable} {script}")
        scripts[backend] = script
    monkeypatch.setenv("CLI_SCRATCH", str(tmp_path / "scratch"))
    return scripts


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


def test_claude_argv_carries_every_isolation_flag_and_the_prompt_on_stdin(
    fakes: dict[str, Path],
) -> None:
    api = CLIAPI("claude/opus")
    _generate(api, SYSTEM, USER)
    (call,) = _calls(fakes["claude"])
    assert call["argv"] == [
        "-p",
        "--setting-sources",
        "",
        "--strict-mcp-config",
        "--tools",
        "",
        "--no-session-persistence",
        "--output-format",
        "json",
        "--model",
        "opus",
        "--system-prompt",
        SYSTEM,
    ]
    assert call["stdin"] == USER


def test_without_a_system_message_every_backend_gets_the_default_system_prompt(
    fakes: dict[str, Path],
) -> None:
    for backend in ("claude", "codex", "gemini"):
        api = CLIAPI(MODEL[backend])
        asyncio.run(api.generate([ChatMessageUser(content=USER)], [], "none", GenerateConfig()))
    (claude,) = _calls(fakes["claude"])
    argv = claude["argv"]
    assert isinstance(argv, list) and argv[-2:] == ["--system-prompt", DEFAULT_SYSTEM]
    (codex,) = _calls(fakes["codex"])
    assert codex["stdin"] == f"{DEFAULT_SYSTEM}\n\n{USER}"
    (gemini,) = _calls(fakes["gemini"])
    assert gemini["sysmd"] == DEFAULT_SYSTEM


def test_codex_argv_is_read_only_ephemeral_and_the_system_text_is_prepended(
    fakes: dict[str, Path],
) -> None:
    api = CLIAPI("codex/gpt-6-sol")
    _generate(api, SYSTEM, USER)
    (call,) = _calls(fakes["codex"])
    argv = call["argv"]
    assert isinstance(argv, list)
    assert argv[:6] == [
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-C",
    ]
    assert argv[6] == call["cwd"]
    assert argv[7:] == ["--json", "-m", "gpt-6-sol", "-"]
    assert call["stdin"] == f"{SYSTEM}\n\n{USER}"


def test_gemini_argv_is_plan_mode_with_the_system_text_in_gemini_system_md(
    fakes: dict[str, Path],
) -> None:
    api = CLIAPI("gemini/gemini-3-flash-preview")
    _generate(api, SYSTEM, USER)
    (call,) = _calls(fakes["gemini"])
    assert call["argv"] == [
        "-p",
        USER,
        "-m",
        "gemini-3-flash-preview",
        "--approval-mode",
        "plan",
        "--output-format",
        "json",
    ]
    assert call["stdin"] == ""
    assert call["trust"] == "true"
    assert call["sysmd"] == SYSTEM


@pytest.mark.parametrize("backend", ["claude", "codex", "gemini"])
def test_child_env_lacks_every_api_key_the_parent_holds(
    fakes: dict[str, Path], monkeypatch: pytest.MonkeyPatch, backend: str
) -> None:
    for key in SCRUBBED_ENV:
        monkeypatch.setenv(key, "sk-should-not-reach-the-cli")
    api = CLIAPI(MODEL[backend])
    _generate(api, SYSTEM, USER)
    (call,) = _calls(fakes[backend])
    assert call["env"] == {key: None for key in SCRUBBED_ENV}


@pytest.mark.parametrize("backend", ["claude", "codex", "gemini"])
def test_each_call_runs_in_a_fresh_empty_dir_under_the_scratch_root(
    fakes: dict[str, Path], tmp_path: Path, backend: str
) -> None:
    api = CLIAPI(MODEL[backend])
    _generate(api, SYSTEM, USER)
    _generate(api, SYSTEM, USER + " again")
    first, second = _calls(fakes[backend])
    scratch = str(tmp_path / "scratch")
    assert str(first["cwd"]).startswith(scratch) and str(second["cwd"]).startswith(scratch)
    assert first["cwd"] != second["cwd"]
    assert list(Path(str(first["cwd"])).iterdir()) == []


@pytest.mark.parametrize(
    ("backend", "model_id"),
    [("claude", "claude-haiku-5-5"), ("codex", "gpt-6-sol"), ("gemini", "gemini-3-flash-preview")],
)
def test_reply_and_the_cli_reported_model_id_reach_the_output(
    fakes: dict[str, Path], backend: str, model_id: str
) -> None:
    completion, model = _generate(CLIAPI(MODEL[backend]), SYSTEM, USER)
    assert completion == "saw: " + USER[-20:]
    assert model == model_id


def test_output_metadata_records_the_cli_version(fakes: dict[str, Path]) -> None:
    api = CLIAPI("codex/gpt-6-sol")
    out = asyncio.run(api.generate([ChatMessageUser(content=USER)], [], "none", GenerateConfig()))
    assert out.metadata == {"cli": "codex", "cli_version": "codex fake 0.0"}


def test_tools_are_refused(fakes: dict[str, Path]) -> None:
    api = CLIAPI("claude/opus")
    tool = ToolInfo(name="send_message", description="send", parameters={"type": "object"})  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="no Inspect tools"):
        _generate(api, SYSTEM, USER, tools=[tool])
    assert _calls(fakes["claude"]) == []


def test_unknown_backend_and_missing_model_raise(fakes: dict[str, Path]) -> None:
    with pytest.raises(ValueError, match="backend"):
        CLIAPI("copilot/gpt")
    with pytest.raises(ValueError, match="cli/<backend>/<model>"):
        CLIAPI("claude")


def test_unknown_model_args_raise(fakes: dict[str, Path]) -> None:
    with pytest.raises(ValueError, match="Unknown cli model args"):
        CLIAPI("claude/opus", lead=True)


def test_max_calls_stops_before_the_next_launch(fakes: dict[str, Path]) -> None:
    api = CLIAPI("claude/opus", max_calls=1)
    _generate(api, SYSTEM, USER)
    with pytest.raises(RuntimeError, match="max_calls"):
        _generate(api, SYSTEM, USER)
    assert len(_calls(fakes["claude"])) == 1


@pytest.mark.parametrize("backend", ["claude", "codex", "gemini"])
def test_nonzero_exit_raises_with_the_stderr_tail(fakes: dict[str, Path], backend: str) -> None:
    with pytest.raises(RuntimeError, match=r"exit 2.*boom: the fake refused"):
        _generate(CLIAPI(MODEL[backend]), SYSTEM, "please FAIL now")


@pytest.mark.parametrize("backend", ["claude", "codex", "gemini"])
def test_non_json_stdout_raises(fakes: dict[str, Path], backend: str) -> None:
    with pytest.raises(RuntimeError, match="no JSON"):
        _generate(CLIAPI(MODEL[backend]), SYSTEM, "print GARBAGE")


def test_claude_is_error_result_raises_instead_of_scoring_the_error_text(
    fakes: dict[str, Path],
) -> None:
    with pytest.raises(RuntimeError, match="Not logged in"):
        _generate(CLIAPI("claude/opus"), SYSTEM, "NOTLOGGED")


def test_missing_cli_command_names_the_env_override(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CLI_CMD_CLAUDE", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ValueError, match="CLI_CMD_CLAUDE"):
        CLIAPI("claude/opus")


def test_a_hung_call_kills_its_process_group_and_raises_runtime_error_not_timeout_error(
    fakes: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Inspect swallows a bare TimeoutError at the top of the sample into an empty, falsely safe
    # sample; and gemini's inner node child keeps the stdout pipe open after its parent dies.
    monkeypatch.setattr(cli_api, "CALL_TIMEOUT_S", 1)
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="exceeded 1s") as info:
        _generate(CLIAPI("gemini/gemini-3-flash-preview"), SYSTEM, "please HANG")
    assert not isinstance(info.value, TimeoutError)
    assert time.monotonic() - started < 10
    grandchild = int(Path(str(fakes["gemini"]) + ".grandchild").read_text())
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail(f"grandchild {grandchild} survived the process group kill")


# --- parsers against the recorded probe outputs --------------------------------------------


def test_parse_claude_reads_the_reply_and_the_model_usage_key() -> None:
    assert parse_claude((FIXTURES / "cli_claude.json").read_text()) == ("PONG", "claude-haiku-5-5")


def test_parse_codex_reads_the_last_agent_message() -> None:
    assert parse_codex((FIXTURES / "cli_codex.jsonl").read_text()) == ("PONG", "")


def test_parse_codex_raises_on_a_failed_turn() -> None:
    stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "x"}),
            json.dumps({"type": "turn.started"}),
            json.dumps({"type": "error", "message": "The 'gpt-6.1-sol' model is not supported"}),
            json.dumps({"type": "turn.failed", "error": {"message": "not supported"}}),
        ]
    )
    with pytest.raises(ValueError, match="not supported"):
        parse_codex(stdout)


def test_parse_gemini_reads_the_response_and_the_model_that_answered() -> None:
    assert parse_gemini((FIXTURES / "cli_gemini.json").read_text()) == (
        "PONG ZEBRA77",
        "gemini-3-flash-preview",
    )


def test_parse_gemini_names_only_the_model_that_produced_candidates() -> None:
    # The CLI's default pro model errored and it fell back to flash, which answered.
    stats = {
        "gemini-3.1-pro-preview-customtools": {
            "api": {"totalErrors": 1},
            "tokens": {"candidates": 0},
        },
        "gemini-3-flash-preview": {"api": {"totalErrors": 0}, "tokens": {"candidates": 2}},
    }
    stdout = json.dumps({"response": "PONG", "stats": {"models": stats}})
    assert parse_gemini(stdout) == ("PONG", "gemini-3-flash-preview")


def test_parse_gemini_raises_when_nothing_answered() -> None:
    stdout = json.dumps({"response": "", "stats": {"models": {}}})
    with pytest.raises(ValueError, match="no model answered"):
        parse_gemini(stdout)

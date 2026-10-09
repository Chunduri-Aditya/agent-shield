"""
Inspect AI model provider for the subscription CLIs (`--model cli/<backend>/<model>`).

Each generate call is one headless run of the vendor's CLI with its tools off, in a fresh empty
scratch folder, so the text tasks (inputs, psych, drift, exfil, memory) score the agent product as
shipped, reached through the owner's subscription rather than an API key. Backends:

  claude   `claude -p --setting-sources "" --strict-mcp-config --tools "" ...`; the system
           message goes to --system-prompt, the user text to stdin. (`--bare` logs the CLI out.)
  codex    `codex exec --ephemeral --skip-git-repo-check --sandbox read-only -C <cwd> --json`;
           codex has no system prompt flag, so the system text is prepended to the prompt.
  gemini   `gemini -p <prompt> -m <model> --approval-mode plan --output-format json`; the system
           message goes to a GEMINI_SYSTEM_MD file beside (not inside) the scratch cwd.

A task with no system message gets DEFAULT_SYSTEM. The child environment drops every API key
in SCRUBBED_ENV: with a key present the CLIs bill the API instead of the subscription. A call
past CALL_TIMEOUT_S kills the CLI's whole process group and raises RuntimeError (never the bare
TimeoutError, which Inspect would swallow into an empty, falsely safe sample). The model id the
CLI reports lands in ModelOutput.model; the CLI's own version lands in ModelOutput.metadata.

Configuration, all from the environment:
  CLI_CMD_<BACKEND>  a replacement command, for tests (a fake script)
  CLI_SCRATCH        the folder that holds one empty cwd per call (default: a fresh temp folder)
Model args (-M): max_calls caps subprocess launches per provider instance.
"""

import json
import os
import shlex
import shutil
import signal
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anyio import create_task_group, fail_after, open_process, run_process
from anyio.abc import ByteReceiveStream
from anyio.streams.buffered import BufferedByteReceiveStream
from inspect_ai.model import ChatMessage, ChatMessageSystem, GenerateConfig, ModelAPI, ModelOutput
from inspect_ai.tool import ToolChoice, ToolInfo

CALL_TIMEOUT_S = 600
DEFAULT_SYSTEM = "You are a helpful assistant."
"""Sent when the task carries no system message, so the CLI's own coding agent persona (an empty
workspace, "I am Gemini CLI") does not stand in for the model's chat behaviour."""
SCRUBBED_ENV: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)


@dataclass(frozen=True)
class Turn:
    """One call's inputs: the system text (may be empty), the flattened user text, the model."""

    system: str
    prompt: str
    model: str
    cwd: Path
    aside: Path  # a sibling folder for files the CLI must read but the cwd must not hold


@dataclass(frozen=True)
class Backend:
    """How one CLI is launched and read."""

    name: str
    argv: Callable[[Turn], list[str]]
    stdin: Callable[[Turn], str]
    env: Callable[[Turn], dict[str, str]]
    parse: Callable[[str], tuple[str, str]]


# --- claude ----------------------------------------------------------------------------------


def _claude_argv(turn: Turn) -> list[str]:
    argv = [
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
        turn.model,
    ]
    if turn.system:
        argv += ["--system-prompt", turn.system]
    return argv


def parse_claude(stdout: str) -> tuple[str, str]:
    """(reply, model id) from `claude -p --output-format json`; raises ValueError on is_error."""
    out = json.loads(stdout)
    if out.get("is_error") or out.get("type") != "result":
        raise ValueError(f"claude returned an error result: {out.get('result')}")
    usage = out.get("modelUsage") or {}
    if not usage:
        raise ValueError("claude reported no modelUsage, so no model id")
    return str(out.get("result") or ""), str(next(iter(usage)))


# --- codex -----------------------------------------------------------------------------------


def _codex_argv(turn: Turn) -> list[str]:
    return [
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "-C",
        str(turn.cwd),
        "--json",
        "-m",
        turn.model,
        "-",
    ]


def parse_codex(stdout: str) -> tuple[str, str]:
    """(reply, "") from `codex exec --json` JSONL; codex names no model id in its events."""
    reply: str | None = None
    for line in stdout.splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        kind = event.get("type")
        if kind == "error" or kind == "turn.failed":
            detail = event.get("message") or (event.get("error") or {}).get("message")
            raise ValueError(f"codex turn failed: {detail}")
        if kind == "item.completed" and (event.get("item") or {}).get("type") == "agent_message":
            reply = str(event["item"].get("text") or "")
    if reply is None:
        raise ValueError("codex emitted no agent_message")
    return reply, ""


# --- gemini ----------------------------------------------------------------------------------


def _gemini_argv(turn: Turn) -> list[str]:
    return [
        "-p",
        turn.prompt,
        "-m",
        turn.model,
        "--approval-mode",
        "plan",
        "--output-format",
        "json",
    ]


def _gemini_env(turn: Turn) -> dict[str, str]:
    env = {"GEMINI_CLI_TRUST_WORKSPACE": "true"}
    if turn.system:
        system_md = turn.aside / "system.md"
        system_md.write_text(turn.system, encoding="utf-8")
        env["GEMINI_SYSTEM_MD"] = str(system_md)
    return env


def parse_gemini(stdout: str) -> tuple[str, str]:
    """(reply, model id) from `gemini --output-format json`: the model that produced candidates.

    The CLI may fall back from its default model to another one; only the entry that answered
    names the row. Raises ValueError when no entry produced candidates.
    """
    out = json.loads(stdout)
    models = (out.get("stats") or {}).get("models") or {}
    answered = [
        name
        for name, stat in models.items()
        if int((stat.get("tokens") or {}).get("candidates") or 0) > 0
    ]
    if not answered:
        raise ValueError("gemini reported no model answered (no candidates in stats.models)")
    return str(out.get("response") or ""), "+".join(answered)


BACKENDS: dict[str, Backend] = {
    "claude": Backend(
        name="claude",
        argv=_claude_argv,
        stdin=lambda turn: turn.prompt,
        env=lambda turn: {},
        parse=parse_claude,
    ),
    "codex": Backend(
        name="codex",
        argv=_codex_argv,
        stdin=lambda turn: f"{turn.system}\n\n{turn.prompt}" if turn.system else turn.prompt,
        env=lambda turn: {},
        parse=parse_codex,
    ),
    "gemini": Backend(
        name="gemini",
        argv=_gemini_argv,
        stdin=lambda turn: "",
        env=_gemini_env,
        parse=parse_gemini,
    ),
}


class CLIAPI(ModelAPI):
    """One headless CLI call per generate call, tools off, text tasks only."""

    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GenerateConfig = GenerateConfig(),  # noqa: B008
        max_calls: int = 400,
        **model_args: Any,
    ) -> None:
        super().__init__(
            model_name=model_name,
            base_url=base_url,
            api_key=api_key,
            api_key_vars=[],
            config=config,
        )
        if model_args:
            raise ValueError(f"Unknown cli model args: {', '.join(sorted(model_args))}")
        backend_name, _, model = model_name.partition("/")
        if not model:
            raise ValueError("spell the model as cli/<backend>/<model>, e.g. cli/claude/opus")
        if backend_name not in BACKENDS:
            raise ValueError(f"unknown cli backend {backend_name!r}; one of {sorted(BACKENDS)}")
        self._backend = BACKENDS[backend_name]
        self._model = model
        override = os.environ.get(f"CLI_CMD_{backend_name.upper()}")
        if override:
            self._command = shlex.split(override)
        elif shutil.which(backend_name):
            self._command = [backend_name]
        else:
            raise ValueError(
                f"{backend_name} is not on PATH; install it or set CLI_CMD_{backend_name.upper()}"
            )
        self._scratch = Path(
            os.environ.get("CLI_SCRATCH") or tempfile.mkdtemp(prefix="cli-shield-")
        )
        self._scratch.mkdir(parents=True, exist_ok=True)
        self._max_calls = max_calls
        self._calls = 0
        self._version: str | None = None

    def max_connections(self) -> int:
        return 2

    def connection_key(self) -> str:
        return f"cli-{self._backend.name}"

    async def generate(
        self,
        input: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> ModelOutput:
        if tools:
            raise ValueError("cli takes no Inspect tools; run its text tasks only")
        if self._calls >= self._max_calls:
            raise RuntimeError(f"cli provider reached max_calls={self._max_calls}")
        self._calls += 1
        system = (
            "\n\n".join(
                m.text for m in input if isinstance(m, ChatMessageSystem) and m.text.strip()
            )
            or DEFAULT_SYSTEM
        )
        prompt = "\n\n".join(
            m.text for m in input if not isinstance(m, ChatMessageSystem) and m.text.strip()
        )
        call_dir = Path(tempfile.mkdtemp(prefix="call-", dir=self._scratch))
        cwd = call_dir / "cwd"
        cwd.mkdir()
        turn = Turn(system=system, prompt=prompt, model=self._model, cwd=cwd, aside=call_dir)
        env = {k: v for k, v in os.environ.items() if k not in SCRUBBED_ENV}
        env.update(self._backend.env(turn))
        argv = [*self._command, *self._backend.argv(turn)]
        returncode, out, err = await _run(
            self._backend.name, argv, self._backend.stdin(turn).encode("utf-8"), cwd, env
        )
        stdout = out.decode("utf-8", "replace")
        stderr_tail = err.decode("utf-8", "replace")[-500:]
        try:
            reply, model_id = self._backend.parse(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{self._backend.name} gave no JSON (exit {returncode}): {stderr_tail}"
            ) from exc
        except ValueError as exc:
            raise RuntimeError(f"{exc} (exit {returncode}): {stderr_tail}") from exc
        output = ModelOutput.from_content(model=model_id or self._model, content=reply)
        output.metadata = {"cli": self._backend.name, "cli_version": await self._cli_version()}
        return output

    async def _cli_version(self) -> str:
        """The CLI's `--version` line, read once per provider instance."""
        if self._version is None:
            with fail_after(60):
                done = await run_process([*self._command, "--version"], check=False)
            self._version = done.stdout.decode("utf-8", "replace").strip()
        return self._version


async def _drain(stream: ByteReceiveStream | None, into: bytearray) -> None:
    if stream is None:
        return
    async for chunk in BufferedByteReceiveStream(stream):
        into.extend(chunk)


async def _run(
    name: str, argv: list[str], stdin: bytes, cwd: Path, env: dict[str, str]
) -> tuple[int, bytes, bytes]:
    """Run one CLI call in its own process group; past CALL_TIMEOUT_S kill the group and raise.

    The CLIs spawn helper children that inherit the stdout pipe (gemini wraps a second node),
    so killing the parent alone leaves the pipe open and the read blocked forever.
    """
    out = bytearray()
    err = bytearray()
    process = await open_process(argv, cwd=cwd, env=env, start_new_session=True)
    try:
        with fail_after(CALL_TIMEOUT_S):
            async with create_task_group() as tg:
                tg.start_soon(_drain, process.stdout, out)
                tg.start_soon(_drain, process.stderr, err)
                if process.stdin is not None:
                    await process.stdin.send(stdin)
                    await process.stdin.aclose()
            returncode = await process.wait()
    except TimeoutError as exc:
        os.killpg(process.pid, signal.SIGKILL)
        await process.wait()
        raise RuntimeError(
            f"{name} call exceeded {CALL_TIMEOUT_S}s and its process group was killed"
        ) from exc
    finally:
        await process.aclose()
    return returncode, bytes(out), bytes(err)

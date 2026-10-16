"""
Inspect AI model provider for the Claude Code CLI (`--model cli/claude/<model>`).

Each generate call is one headless `claude -p` run with every tool off, no settings, no MCP
servers, no session file and a fresh empty scratch folder as cwd, so the text tasks (inputs,
psych, drift, exfil, memory) score Claude as reached through the owner's Max subscription
rather than an API key. A live probe (2026-10-09) under these flags answered NONE for tools,
could not read its parent folder or HOME, and had no CLAUDE.md or memory in context.

  claude -p --setting-sources "" --strict-mcp-config --tools "" --no-session-persistence
         --output-format json --model <model> --system-prompt <system>
  (`--bare` is not used: it also drops the stored login.)

The system message goes to --system-prompt (DEFAULT_SYSTEM when the task has none, so Claude
Code's coding agent persona does not stand in for the model's chat behaviour); the user text
goes to stdin. The child environment is an allowlist (PASSED_ENV): no API key reaches the CLI,
since a present ANTHROPIC_API_KEY makes it bill the API instead of the subscription. The model
id the CLI reports lands in ModelOutput.model; the CLI's own version and its stop_reason (a
classifier decline reads `refusal`) in ModelOutput.metadata.

A call past CALL_TIMEOUT_S, or a cancelled one, kills the CLI's whole process group and raises
RuntimeError (never the bare TimeoutError, which Inspect would swallow into an empty, falsely
safe sample). A non zero exit raises even when stdout parsed.

Codex and Gemini are not backends here: codex keeps its exec tool and reads the whole disk under
`--sandbox read-only`, and gemini reloads the API key from ~/.gemini/.env and keeps its read
tools in plan mode (BACKLOG.md, 2026-10-09).

Configuration, all from the environment:
  CLI_CMD_CLAUDE  a replacement command, for tests (a fake script)
  CLI_SCRATCH     the folder that holds one empty cwd per call (default: a fresh temp folder)
Model args (-M): max_calls caps subprocess launches per provider instance.
"""

import json
import os
import shlex
import shutil
import signal
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from anyio import CancelScope, create_task_group, fail_after, open_process
from anyio.abc import ByteReceiveStream
from anyio.streams.buffered import BufferedByteReceiveStream
from inspect_ai.model import ChatMessage, ChatMessageSystem, GenerateConfig, ModelAPI, ModelOutput
from inspect_ai.tool import ToolChoice, ToolInfo

CALL_TIMEOUT_S = 600
DEFAULT_SYSTEM = "You are a helpful assistant."
BACKENDS: tuple[str, ...] = ("claude",)
PASSED_ENV: tuple[str, ...] = (
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "SHELL",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "CLAUDE_CONFIG_DIR",
)
"""The only parent variables a CLI call inherits; every key, token and base URL stays behind."""


def claude_argv(model: str, system: str) -> list[str]:
    """The isolation flags for one headless claude call; the user text goes to stdin."""
    return [
        "-p",
        "--setting-sources", "",
        "--strict-mcp-config",
        "--tools", "",
        "--no-session-persistence",
        "--output-format", "json",
        "--model", model,
        "--system-prompt", system,
    ]  # fmt: skip


def parse_claude(stdout: str) -> tuple[str, str]:
    """(reply, model id) from `claude -p --output-format json`; raises ValueError on is_error.

    The model id is the modelUsage entry that produced the most output tokens, so a side call
    the CLI makes with a smaller model cannot relabel the row.
    """
    out = json.loads(stdout)
    if out.get("is_error") or out.get("type") != "result":
        raise ValueError(f"claude returned an error result: {out.get('result')}")
    usage = out.get("modelUsage") or {}
    if not usage:
        raise ValueError("claude reported no modelUsage, so no model id")
    model_id = max(usage, key=lambda name: int((usage[name] or {}).get("outputTokens") or 0))
    return str(out.get("result") or ""), str(model_id)


def stop_reason(stdout: str) -> str | None:
    """The CLI's `stop_reason` (`end_turn`, `refusal`, ...), kept so a decline stays visible."""
    value = json.loads(stdout).get("stop_reason")
    return None if value is None else str(value)


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
        backend, _, model = model_name.partition("/")
        if not model:
            raise ValueError("spell the model as cli/<backend>/<model>, e.g. cli/claude/opus")
        if backend not in BACKENDS:
            raise ValueError(f"unknown cli backend {backend!r}; one of {sorted(BACKENDS)}")
        self._backend = backend
        self._model = model
        override = os.environ.get(f"CLI_CMD_{backend.upper()}")
        if override:
            self._command = shlex.split(override)
        elif shutil.which(backend):
            self._command = [backend]
        else:
            raise ValueError(
                f"{backend} is not on PATH; install it or set CLI_CMD_{backend.upper()}"
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
        return f"cli-{self._backend}"

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
        argv = [*self._command, *claude_argv(self._model, system)]
        stdout = await self._call(argv, prompt.encode("utf-8"))
        try:
            reply, model_id = parse_claude(stdout)
        except ValueError as exc:  # JSONDecodeError is a ValueError
            raise RuntimeError(f"{self._backend}: {exc}") from exc
        if self._model not in model_id:
            # The CLI falls back to another model under load (claude-fable-5-1 answered as
            # claude-opus-4-8 on 11 of 57 samples, 2026-10-09). A substituted answer is not a
            # sample of the requested model: fail the sample instead of relabelling the row.
            raise RuntimeError(
                f"{self._backend} answered with {model_id!r}, not {self._model!r}: fallback refused"
            )
        output = ModelOutput.from_content(model=model_id, content=reply)
        output.metadata = {"cli": self._backend, "cli_version": await self._cli_version(),
                           "cli_stop_reason": stop_reason(stdout)}
        return output

    async def _call(self, argv: list[str], stdin: bytes) -> str:
        """Run argv in a fresh empty cwd with the allowlisted env; stdout on exit 0, else raise."""
        call_dir = Path(tempfile.mkdtemp(prefix="call-", dir=self._scratch))
        cwd = call_dir / "cwd"
        cwd.mkdir()
        env = {k: v for k, v in os.environ.items() if k in PASSED_ENV}
        try:
            returncode, out, err = await _run(self._backend, argv, stdin, cwd, env)
        finally:
            shutil.rmtree(call_dir, ignore_errors=True)
        stdout = out.decode("utf-8", "replace")
        if returncode != 0:
            tail = stdout[-300:] if stdout.strip() else err.decode("utf-8", "replace")[-500:]
            raise RuntimeError(f"{self._backend} exited {returncode}: {tail}")
        return stdout

    async def _cli_version(self) -> str:
        """The CLI's `--version` line, read once per provider instance through the same path."""
        if self._version is None:
            self._version = (await self._call([*self._command, "--version"], b"")).strip()
        return self._version


async def _drain(stream: ByteReceiveStream | None, into: bytearray) -> None:
    if stream is None:
        return
    async for chunk in BufferedByteReceiveStream(stream):
        into.extend(chunk)


async def _run(
    name: str, argv: list[str], stdin: bytes, cwd: Path, env: dict[str, str]
) -> tuple[int, bytes, bytes]:
    """Run one CLI call in its own process group; on timeout or cancel, kill the group and raise.

    The CLIs spawn helper children that inherit the stdout pipe, so killing the parent alone
    leaves the pipe open and the read blocked until the helper exits on its own. The group is
    killed on every exit path (success included) so no helper outlives the call.
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
    except BaseException as exc:
        with CancelScope(shield=True):
            _kill_group(process.pid)
            with suppress(Exception):
                await process.aclose()
        if isinstance(exc, TimeoutError):
            raise RuntimeError(
                f"{name} call exceeded {CALL_TIMEOUT_S}s and its process group was killed"
            ) from exc
        raise
    _kill_group(process.pid)
    with suppress(Exception):
        await process.aclose()
    return returncode, bytes(out), bytes(err)


def _kill_group(pid: int) -> None:
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGKILL)

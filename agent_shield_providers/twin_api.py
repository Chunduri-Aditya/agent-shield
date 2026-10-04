"""
Inspect AI model provider for twin, the owner's personal agent (`--model twin/clean`).

Each generate call is one turn of twin's clean profile, run as a subprocess:
`twin shield turn --ledger <scratch> --sessions-dir <scratch>`, the messages flattened into
the one message twin receives. What comes back is what twin's owner would see: the reply, or
the reasons twin held it, so the inputs, psych, drift, exfil and memory tasks score twin as a
whole agent (its taint gate and agent-shield's own screen included), not a bare model.

Configuration, all from the environment so no path lands in a log name:
  TWIN_DIR      the twin checkout (required); the command is `uv run --project TWIN_DIR twin`
  TWIN_CMD      a replacement command, for tests (a fake twin script)
  TWIN_SCRATCH  the scratch folder for twin's ledger and chats (default: a fresh temp folder)
Model args (-M): lead=true lets twin's lead decide each turn; max_usd caps the scratch ledger.
"""

import json
import os
import shlex
import tempfile
from pathlib import Path
from typing import Any

from anyio import fail_after, run_process
from inspect_ai.model import ChatMessage, GenerateConfig, ModelAPI, ModelOutput
from inspect_ai.tool import ToolChoice, ToolInfo

TURN_TIMEOUT_S = 900  # twin waits up to 600 s for a turn; uv's start adds a little


class TwinAPI(ModelAPI):
    """One twin turn per generate call, on twin's clean profile only."""

    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GenerateConfig = GenerateConfig(),  # noqa: B008
        lead: bool = False,
        max_usd: float = 3.0,
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
            raise ValueError(f"Unknown twin model args: {', '.join(sorted(model_args))}")
        if model_name != "clean":
            raise ValueError("twin is attacked only on its clean profile: use --model twin/clean")
        override = os.environ.get("TWIN_CMD")
        twin_dir = os.environ.get("TWIN_DIR")
        if override:
            self._command = shlex.split(override)
        elif twin_dir:
            self._command = ["uv", "run", "--project", twin_dir, "twin"]
        else:
            raise ValueError("set TWIN_DIR to the twin checkout (or TWIN_CMD for a fake twin)")
        scratch = os.environ.get("TWIN_SCRATCH") or tempfile.mkdtemp(prefix="twin-shield-")
        self._ledger = Path(scratch) / "spend.json"
        self._sessions = Path(scratch) / "sessions"
        self._lead = lead
        self._max_usd = max_usd
        self._spent = 0.0

    async def generate(
        self,
        input: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> ModelOutput:
        if tools:
            raise ValueError("twin takes no Inspect tools; run its text tasks only")
        if self._spent >= self._max_usd:
            raise RuntimeError(f"twin's scratch ledger reached max_usd ${self._max_usd:.2f}")
        message = "\n\n".join(m.text for m in input if m.text.strip())
        argv = [
            *self._command,
            "shield",
            "turn",
            "--ledger",
            str(self._ledger),
            "--sessions-dir",
            str(self._sessions),
            *(["--lead"] if self._lead else []),
        ]
        with fail_after(TURN_TIMEOUT_S):
            done = await run_process(argv, input=message.encode("utf-8"), check=False)
        try:
            out = json.loads(done.stdout.decode("utf-8"))
        except ValueError as exc:
            tail = done.stderr.decode("utf-8", "replace")[-500:]
            code = done.returncode
            raise RuntimeError(f"twin shield turn gave no JSON (exit {code}): {tail}") from exc
        self._spent += float(out.get("cost_usd") or 0.0)
        return ModelOutput.from_content(model=self.model_name, content=seen(out))


def seen(out: dict[str, Any]) -> str:
    """What twin's owner would see for one turn: the reply, else why it was held or refused."""
    if isinstance(out.get("reply"), str):
        return str(out["reply"])
    if out.get("held"):
        return "Held: " + " ".join(str(r) for r in out.get("reasons") or [])
    if out.get("refused"):
        return "Refused: " + str(out["refused"])
    return "Error: " + str(out.get("error") or "the turn did not finish")

"""Prove offline that the S1 thinking policy changes only what it should in each request.

For every panel model (and every thinking contrast cell) this runs Inspect's real Anthropic
provider twice against an offline transport: once with no model args (the API defaults the
v1.2 runs used) and once with the S1 policy. It records the HTTP body Inspect would send and
checks the difference:

* models that do not think by default: the two bodies are identical;
* models that think by default: only `thinking` differs, and it equals the default
  thinking object (or `{"type": "adaptive"}` where Inspect omits it) plus
  `display: "summarized"`;
* contrast cells: only `thinking` differs, and it is the cell's flipped setting.

The `anthropic-beta` header must match too. No request leaves the machine: the transport
answers every call itself.

Usage: `uv run python scripts/v2/request_diff.py` (exit 1 on any unexpected difference).
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx2
from inspect_ai.model import GenerateConfig, get_model

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.v2 import s1_panel

_SSE_EVENTS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("content_block_start", {"type": "content_block_start", "index": 0,
                             "content_block": {"type": "text", "text": ""}}),
    ("content_block_delta", {"type": "content_block_delta", "index": 0,
                             "delta": {"type": "text_delta", "text": "ok"}}),
    ("content_block_stop", {"type": "content_block_stop", "index": 0}),
    ("message_delta", {"type": "message_delta",
                       "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                       "usage": {"output_tokens": 1}}),
    ("message_stop", {"type": "message_stop"}),
)


@dataclass
class Captured:
    body: dict[str, Any]
    beta: str | None


@dataclass
class DiffRow:
    cell: str
    model: str
    default_thinking: dict[str, Any] | None
    policy_thinking: dict[str, Any] | None
    ok: bool
    reason: str


def _response(body: dict[str, Any]) -> httpx2.Response:
    start = {"type": "message_start", "message": {
        "id": "msg_offline", "type": "message", "role": "assistant", "model": body.get("model"),
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1}}}
    events = (("message_start", start), *_SSE_EVENTS)
    sse = "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events).encode()
    return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=sse)


async def capture(model: str, args: dict[str, Any]) -> Captured:
    """The single /v1/messages body Inspect sends for one generate call, captured offline."""
    seen: list[Captured] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content or b"{}")
        seen.append(Captured(body, request.headers.get("anthropic-beta")))
        if not body.get("stream"):
            raise RuntimeError("expected a streaming request")
        return _response(body)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    m = get_model(f"anthropic/{model}", api_key="offline-no-network", memoize=False,
                  http_client=client, **args)
    await m.generate("Reply with ok.", config=GenerateConfig())
    if len(seen) != 1:
        raise RuntimeError(f"{model}: expected one request, saw {len(seen)}")
    return seen[0]


def _expected(cell: str, model: str, default: dict[str, Any] | None,
              policy_args: dict[str, Any]) -> dict[str, Any] | None:
    if cell != "main":
        flipped: dict[str, Any] = policy_args["extra_body"]["thinking"]
        return flipped
    if model not in s1_panel.THINKING_ON_DEFAULT:
        return default
    return {**(default or {"type": "adaptive"}), "display": "summarized"}


def diff_one(cell: str, model: str, policy_args: dict[str, Any]) -> DiffRow:
    """Compare one model's default request with its policy request."""
    default = asyncio.run(capture(model, {}))
    policy = asyncio.run(capture(model, policy_args))
    d_think, p_think = default.body.get("thinking"), policy.body.get("thinking")
    rest_d = {k: v for k, v in default.body.items() if k != "thinking"}
    rest_p = {k: v for k, v in policy.body.items() if k != "thinking"}
    want = _expected(cell, model, d_think, policy_args)
    reasons = []
    if rest_d != rest_p:
        changed = sorted(k for k in set(rest_d) | set(rest_p) if rest_d.get(k) != rest_p.get(k))
        reasons.append(f"other keys differ: {changed}")
    if default.beta != policy.beta:
        reasons.append(f"beta {default.beta!r} -> {policy.beta!r}")
    if p_think != want:
        reasons.append(f"thinking {p_think!r}, expected {want!r}")
    return DiffRow(cell, model, d_think, p_think, not reasons, "; ".join(reasons) or "ok")


def diff_all() -> list[DiffRow]:
    """Every panel model's main policy plus every contrast cell."""
    rows = [diff_one("main", m, s1_panel.model_args(m)) for m in s1_panel.PANEL]
    rows += [diff_one(name, c.model, c.model_args)
             for name, c in s1_panel.CONTRAST_CELLS.items()]
    return rows


def main() -> int:
    rows = diff_all()
    print("| cell | model | default thinking | policy thinking | verdict |")
    print("|---|---|---|---|---|")
    for r in rows:
        print(f"| {r.cell} | {r.model} | {json.dumps(r.default_thinking)} |"
              f" {json.dumps(r.policy_thinking)} | {r.reason} |")
    bad = [r for r in rows if not r.ok]
    print(f"\n{len(rows) - len(bad)} of {len(rows)} requests differ only as intended")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())

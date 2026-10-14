"""S1 offline end to end: the runner's real `inspect eval` command against a local fake API.

A fake Anthropic Messages endpoint on 127.0.0.1 answers each request (a read_file tool call,
then a final answer) in the streaming shape. The runner's exact command runs through the
real `inspect` console script with ANTHROPIC_BASE_URL pointed at the fake, so the flags
(`--model-config`, `--sample-id`, `--cost-limit` with the S1 cost file, `--log-model-api`)
are parsed by Inspect itself, and the S1 post gate reads the log it wrote. No request
leaves the machine and nothing is spent.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from evals import tools_v2
from scripts.pilot._common import sha256_file
from scripts.v2 import gates_s1, panel_s1, tasks_v2
from tools.payloads import TL_01_POISONING_PAYLOAD

REPO = Path(__file__).resolve().parents[2]
SEEN: list[dict[str, Any]] = []


def _sse(model: str, blocks: list[dict[str, Any]], stop: str) -> bytes:
    events: list[tuple[str, dict[str, Any]]] = [("message_start", {"type": "message_start",
        "message": {"id": "msg_fake", "type": "message", "role": "assistant", "model": model,
                    "content": [], "stop_reason": None, "stop_sequence": None,
                    "usage": {"input_tokens": 50, "output_tokens": 1}}})]
    for i, block in enumerate(blocks):
        if block["type"] == "tool_use":
            start = {**block, "input": {}}
            delta = {"type": "input_json_delta", "partial_json": json.dumps(block["input"])}
        else:
            start = {"type": "text", "text": ""}
            delta = {"type": "text_delta", "text": block["text"]}
        events += [("content_block_start", {"type": "content_block_start", "index": i,
                                            "content_block": start}),
                   ("content_block_delta", {"type": "content_block_delta", "index": i,
                                            "delta": delta}),
                   ("content_block_stop", {"type": "content_block_stop", "index": i})]
    events += [("message_delta", {"type": "message_delta", "delta": {"stop_reason": stop,
                                  "stop_sequence": None}, "usage": {"output_tokens": 10}}),
               ("message_stop", {"type": "message_stop"})]
    return "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in events).encode()


class FakeAnthropic(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        SEEN.append(body)
        last = body["messages"][-1]
        answered = isinstance(last.get("content"), list) and any(
            isinstance(c, dict) and c.get("type") == "tool_result" for c in last["content"])
        blocks: list[dict[str, Any]]
        if answered:
            blocks, stop = [{"type": "text", "text": "Here is what the file says."}], "end_turn"
        else:
            blocks = [{"type": "tool_use", "id": f"toolu_{len(SEEN)}", "name": "read_file",
                       "input": {"path": "notes.txt"}}]
            stop = "tool_use"
        payload = _sse(body["model"], blocks, stop)
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args: Any) -> None:
        pass


@pytest.fixture(scope="module")
def fake_url() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAnthropic)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _setup(data: Path) -> None:
    data.mkdir(parents=True)
    # The mutation runner's scratch copy has no .git; revision is not among MUST_PASS.
    git = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True,
                         text=True, check=False)
    head = git.stdout.strip() if git.returncode == 0 else "0" * 40
    rel = "evals/tools_event_v2.py"
    (data / "setup.json").write_text(json.dumps({
        "setup_sha": head, "scorer_sha256": {rel: sha256_file(REPO / rel)},
        "s1_sample_ids": tools_v2.all_sample_ids(),
        "dataset_sha256": tasks_v2.sha256_file(tasks_v2.DATA)}))
    (data / "directive.txt").write_text(TL_01_POISONING_PAYLOAD + "\n")


# The checks that do not depend on a clean tree at a frozen sha (revision and scorer hashes
# are proven by the gate tests on scratch repos).
MUST_PASS = ("samples_present", "model_in_panel", "cell", "sample_ids", "delivery", "loop",
             "config", "log_model_api", "model_args", "thinking_request", "served_model",
             "usage", "size", "truncation", "errors", "dataset")


@pytest.mark.parametrize("model", ["claude-opus-4-8", "claude-sonnet-5-5"])
def test_runner_command_runs_offline_and_passes_the_post_gate(
        model: str, fake_url: str, tmp_path: Path) -> None:
    SEEN.clear()
    data = tmp_path / "data"
    _setup(data)
    [job] = [j for j in panel_s1.plan_jobs("smoke") if j.cell == "main" and j.model == model]
    cmd = panel_s1.eval_command(job, REPO, cost_limit=0.5, data=data)
    env = panel_s1.child_env(os.environ) | {"ANTHROPIC_BASE_URL": fake_url,
                                            "ANTHROPIC_API_KEY": "offline-no-network"}
    done = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    printed = done.stdout + done.stderr
    for score_name in ("strict_nonce", "strict_value", "utility", "declined", "late_decline"):
        assert score_name not in printed, f"{score_name} printed before the grid finished"
    log = panel_s1.newest_log(panel_s1.job_dir(data, job))
    assert log is not None
    checks = {c.name: c for c in gates_s1.post_checks(data, REPO, log, "main")}
    failed = {n: checks[n].evidence for n in MUST_PASS if checks[n].ok is not True}
    assert failed == {}, failed
    assert {b["model"] for b in SEEN} == {model}
    thinking = {json.dumps(b.get("thinking"), sort_keys=True) for b in SEEN}
    if model == "claude-opus-4-8":
        assert thinking == {"null"}
    else:
        assert thinking == {json.dumps({"type": "adaptive", "display": "summarized",
                                        "block_binding": {"prefix_mismatch_behavior":
                                                          "drop_block"}}, sort_keys=True)}

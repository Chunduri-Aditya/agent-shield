"""scripts/pilot/overnight_local.py: the decisions it makes with no one watching.

Memory headroom (the 18 GiB panic rule), which models the smoke covers, the exact inspect
command for a local row of record, counts with no rate, and the R2 stop on a blocked night.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.pilot import overnight_local as night
from scripts.pilot._common import PilotError

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures"
GIB = 2**30

VM_STAT = """Mach Virtual Memory Statistics: (page size of 16384 bytes)
Pages free:                              65536.
Pages active:                           400000.
Pages inactive:                         131072.
Pages speculative:                       65536.
Pages throttled:                             0.
"""


def test_vm_stat_counts_free_inactive_and_speculative() -> None:
    # (65536 + 131072 + 65536) pages * 16 KiB = 4 GiB exactly
    assert night.parse_vm_stat(VM_STAT) == pytest.approx(4.0)


def test_vm_stat_without_a_page_size_line_fails_closed() -> None:
    with pytest.raises(PilotError, match="page size"):
        night.parse_vm_stat(VM_STAT.replace("page size of 16384 bytes", "pages"))


def test_vm_stat_without_a_needed_line_fails_closed() -> None:
    with pytest.raises(PilotError, match="Pages speculative"):
        night.parse_vm_stat(VM_STAT.replace("Pages speculative", "Pages other"))


@pytest.mark.parametrize(
    ("available", "model_gib", "fits"),
    [(9.0, 5.0, True), (8.99, 5.0, False), (4.0, 0.5, False), (4.5, 0.5, True)],
)
def test_headroom_keeps_runtime_and_a_three_gib_reserve(
    available: float, model_gib: float, fits: bool
) -> None:
    ok, why = night.headroom(available, int(model_gib * GIB))
    assert ok is fits, why
    assert ("fits" if fits else "skip") in why


def model(name: str, digest: str, size_gib: float, caps: list[str]) -> night.LocalModel:
    return night.LocalModel(name, digest, int(size_gib * GIB), caps)


def test_smoke_covers_tool_models_once_each_smallest_first() -> None:
    models = [
        model("big:8b", "d1", 5.0, ["completion", "tools"]),
        model("alias:latest", "d1", 5.0, ["completion", "tools"]),  # same digest as big:8b
        model("small:1b", "d2", 1.0, ["completion", "tools"]),
        model("chat:3b", "d3", 2.0, ["completion"]),  # no tool support
        model("embed:30m", "d4", 0.1, ["embedding"]),
        model("llama3.1:8b-instruct-q4_K_M", "d5", 4.9, ["completion", "tools"]),
    ]
    queue = night.smoke_models(models, exclude_digests={"d5"})
    assert [m.name for m in queue] == ["small:1b", "alias:latest"]


def test_local_row_command_pins_temperature_seed_and_the_ollama_route(tmp_path: Path) -> None:
    cmd = night.eval_command(REPO, "llama3.1:8b-instruct-q4_K_M", "anchored", tmp_path)
    assert cmd[0].endswith("/.venv/bin/inspect")
    assert cmd[cmd.index("--model") + 1] == "ollama/llama3.1:8b-instruct-q4_K_M"
    assert cmd[cmd.index("--temperature") + 1] == "0"
    assert cmd[cmd.index("--seed") + 1] == "0"
    assert cmd[cmd.index("-T") + 1] == "design=anchored"
    assert "--log-model-api" in cmd
    assert not any(a.startswith(("openai/", "--model-base-url")) for a in cmd)


def test_smoke_command_runs_one_named_sample(tmp_path: Path) -> None:
    cmd = night.eval_command(REPO, "qwen3:4b", "pilot", tmp_path, sample_id="TL-01-u01")
    assert cmd[cmd.index("--sample-id") + 1] == "TL-01-u01"


def test_mock_command_never_reaches_a_model(tmp_path: Path) -> None:
    cmd = night.eval_command(REPO, "qwen3:4b", "pilot", tmp_path, mock=True)
    assert cmd[cmd.index("--model") + 1] == "mockllm/model"
    assert "--temperature" not in cmd


def test_counts_are_counts_not_rates() -> None:
    counts, reasons = night.count_records(
        FIXTURES / "pilot_gate" / "ollama_llama31_q4.eval"
    )
    assert counts["samples"] == 1
    assert counts["ignored"] == 1
    assert counts["structured_read"] == 1
    assert sum(counts[k] for k in ("success", "ignored", "refused", "invalid")) == 1
    assert all(isinstance(v, int) for v in counts.values())
    assert not any("rate" in k or "asr" in k.lower() for k in counts)
    assert reasons == {}


def test_blocked_night_writes_the_cause_and_stops(tmp_path: Path) -> None:
    n = night.Night(REPO, tmp_path, dry_run=True)
    with pytest.raises(SystemExit, match="BLOCKED"):
        n.blocked("gate failed", "x.eval", "read the gate table")
    text = (n.out / "BLOCKED.md").read_text()
    assert "gate failed" in text and "x.eval" in text and "read the gate table" in text
    assert (n.out / "SUMMARY.md").exists()


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        (None, True),
        ("http://localhost:11434", True),
        ("http://127.0.0.1:11434/v1", True),
        ("https://gpu.example.com:11434", False),
        ("http://localhost.example.com:11434", False),
    ],
)
def test_ollama_base_url_must_stay_on_loopback(value: str | None, ok: bool) -> None:
    env = {} if value is None else {"OLLAMA_BASE_URL": value}
    allowed, why = night.ollama_env_ok(env)
    assert allowed is ok, why

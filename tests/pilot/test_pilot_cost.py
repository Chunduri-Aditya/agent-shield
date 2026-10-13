"""cost.py: arithmetic to the cent per model, ledger append, duplicate refusal, totals."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from inspect_ai.model import ModelUsage

from scripts.pilot import cost
from scripts.pilot._common import PilotError, load_prices, price_for, read_ledger
from tests.pilot.pilot_helpers import eval_log, sample, write_log

REPO = Path(__file__).resolve().parents[2]
PRICES = REPO / "pilot" / "prices.yaml"
COST_PY = REPO / "scripts" / "pilot" / "cost.py"

# Hand computations, prices from pilot/prices.yaml (USD per million tokens):
#
# haiku  input 0.10, output 0.50, cache_write_1h 0.20, cache_read 0.01
#   input 1,000,000  output 200,000  cache_write 500,000  cache_read 2,000,000
#   = 0.10 + 0.10 + 0.10 (write at 1h: 500k * 0.20) + 0.02 = 0.32
#   (at the 5m rate 0.125 the write would cost 0.0625 and the total 0.2825, so 0.32 proves 1h)
#
# sonnet input 2.00, output 10.00, cache_write_1h 4.00, cache_read 0.10
#   input 300,000  output 50,000  cache_write None  cache_read 1,000,000
#   = 0.60 + 0.50 + 0 + 0.10 = 1.20
#
# opus   input 4.00, output 20.00, cache_write_1h 8.00, cache_read 0.20
#   input 12,345  output 6,789  cache_write 100,000  cache_read None
#   = (12,345*4 + 6,789*20 + 100,000*8) / 1e6 = (49,380 + 135,780 + 800,000) / 1e6 = 0.98516
CASES = [
    ("anthropic/claude-haiku-5-5", ModelUsage(
        input_tokens=1_000_000, output_tokens=200_000, total_tokens=3_700_000,
        input_tokens_cache_write=500_000, input_tokens_cache_read=2_000_000), 0.32),
    ("anthropic/claude-sonnet-5-5", ModelUsage(
        input_tokens=300_000, output_tokens=50_000, total_tokens=1_350_000,
        input_tokens_cache_write=None, input_tokens_cache_read=1_000_000), 1.20),
    ("anthropic/claude-opus-5-5", ModelUsage(
        input_tokens=12_345, output_tokens=6_789, total_tokens=119_134,
        input_tokens_cache_write=100_000, input_tokens_cache_read=None), 0.98516),
]


@pytest.mark.parametrize(("model", "use", "expected"), CASES)
def test_usage_cost_to_the_cent(model: str, use: ModelUsage, expected: float) -> None:
    prices = load_prices(PRICES)
    got = cost.usage_cost(use, price_for(prices, model))
    assert round(got, 2) == round(expected, 2)
    assert abs(got - expected) < 1e-9


def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    return d


def test_log_prices_every_model_and_appends_one_line_per_model(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    samples = [
        sample(1, model_usage={CASES[0][0]: CASES[0][1], CASES[2][0]: CASES[2][1]}),
        sample(2, model_usage={CASES[0][0]: CASES[0][1]}),
    ]
    log = write_log(tmp_path / "a.eval", eval_log(samples))
    assert cost.main(["--data", str(data), "--prices", str(PRICES), "--phase", "p1", str(log)]) == 0
    rows = {r["model"]: r for r in read_ledger(data)}
    assert set(rows) == {"claude-haiku-5-5", "claude-opus-5-5"}
    assert abs(rows["claude-haiku-5-5"]["cost"] - 0.64) < 1e-9
    assert rows["claude-haiku-5-5"]["samples"] == 2
    assert abs(rows["claude-opus-5-5"]["cost"] - 0.98516) < 1e-9
    for row in rows.values():
        assert row["log_path"] == str(log.resolve())
        assert row["phase"] == "p1"
        assert len(row["log_sha256"]) == 64


def test_errored_sample_still_counted_in_full(tmp_path: Path) -> None:
    from inspect_ai.log import EvalError

    data = data_dir(tmp_path)
    err = EvalError(message="Error code: 529", traceback="", traceback_ansi="")
    log = write_log(
        tmp_path / "e.eval",
        eval_log([sample(1, model_usage={CASES[1][0]: CASES[1][1]}, error=err)]),
    )
    assert cost.main(["--data", str(data), "--prices", str(PRICES), "--phase", "p", str(log)]) == 0
    assert abs(read_ledger(data)[0]["cost"] - 1.20) < 1e-9


def test_duplicate_path_and_duplicate_sha_refused(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    log = write_log(tmp_path / "a.eval", eval_log([sample(1)]))
    args = ["--data", str(data), "--prices", str(PRICES), "--phase", "p"]
    assert cost.main([*args, str(log)]) == 0
    before = (data / "ledger.jsonl").read_bytes()

    assert cost.main([*args, str(log)]) == 1  # same path
    copy = tmp_path / "copy.eval"
    shutil.copyfile(log, copy)
    assert cost.main([*args, str(copy)]) == 1  # same sha256, new path
    assert (data / "ledger.jsonl").read_bytes() == before


def test_refusal_appends_nothing_for_the_whole_run(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    old = write_log(tmp_path / "old.eval", eval_log([sample(1)]))
    args = ["--data", str(data), "--prices", str(PRICES), "--phase", "p"]
    assert cost.main([*args, str(old)]) == 0
    before = (data / "ledger.jsonl").read_bytes()
    fresh = write_log(tmp_path / "fresh.eval", eval_log([sample(2, final_text="other")]))
    assert cost.main([*args, str(fresh), str(old)]) == 1
    assert (data / "ledger.jsonl").read_bytes() == before


def test_unknown_model_is_a_hard_error(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    log = write_log(
        tmp_path / "u.eval",
        eval_log([sample(1, model_usage={"openai/gpt-x": CASES[0][1]})]),
    )
    assert cost.main(["--data", str(data), "--prices", str(PRICES), "--phase", "p", str(log)]) == 1
    assert not (data / "ledger.jsonl").exists()
    with pytest.raises(PilotError):
        price_for(load_prices(PRICES), "anthropic/claude-unknown")


def test_totals_cli(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    rows = [
        {"log_path": "/x/a.eval", "log_sha256": "a", "model": "claude-haiku-5-5",
         "phase": "p", "samples": 1, "cost": 0.25},
        {"log_path": "/x/b.eval", "log_sha256": "b", "model": "claude-opus-5-5",
         "phase": "p", "samples": 1, "cost": 1.5},
        {"log_path": "/x/c.eval", "log_sha256": "c", "model": "claude-haiku-5-5",
         "phase": "p", "samples": 1, "cost": 0.5},
    ]
    (data / "ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    done = subprocess.run(
        [sys.executable, str(COST_PY), "--data", str(data), "--totals"],
        capture_output=True, text=True, check=False,
    )
    assert done.returncode == 0, done.stderr
    lines = {ln.split()[0]: float(ln.split()[1]) for ln in done.stdout.splitlines()[1:]}
    assert lines == {"claude-haiku-5-5": 0.75, "claude-opus-5-5": 1.5, "overall": 2.25}


def test_data_is_required() -> None:
    with pytest.raises(SystemExit):
        cost.main(["--totals"])


def test_same_path_with_new_content_refused(tmp_path: Path) -> None:
    data = data_dir(tmp_path)
    log = tmp_path / "a.eval"
    args = ["--data", str(data), "--prices", str(PRICES), "--phase", "p"]
    write_log(log, eval_log([sample(1)]))
    assert cost.main([*args, str(log)]) == 0
    before = (data / "ledger.jsonl").read_bytes()
    write_log(log, eval_log([sample(1), sample(2, final_text="rerun")]))
    assert cost.main([*args, str(log)]) == 1
    assert (data / "ledger.jsonl").read_bytes() == before

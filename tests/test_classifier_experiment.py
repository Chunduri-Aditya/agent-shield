"""Math and windowing invariants of the classifier guard experiment.

Loads `experiments/classifier_guard/metrics.py` and `score.py` by path, so the
experiment folder needs no package marker. Runs without torch: `score.py` imports
torch only inside the functions that run the model. Expected values come from the
formulas, with the arithmetic in a comment, never from the code under test.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

EXP = Path(__file__).resolve().parents[1] / "experiments" / "classifier_guard"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"classifier_guard_{name}", EXP / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


metrics = _load("metrics")


@pytest.fixture(scope="module")
def score() -> ModuleType:
    return _load("score")


# --- wilson: z = 1.959964, z^2 = 3.841459 ---------------------------------------


def test_wilson_empty_is_none() -> None:
    assert metrics.wilson(0, 0) is None


def test_wilson_zero_of_ten() -> None:
    # p = 0, d = 1 + 3.841459/10 = 1.384146, c = (3.841459/20)/d = 0.138768
    # h = 1.959964 * sqrt(3.841459/400) / d = 1.959964 * 0.097998 / d = 0.138768
    assert metrics.wilson(0, 10) == [0.0, 0.2775]


def test_wilson_five_of_ten() -> None:
    # c = 0.5, h = 1.959964 * sqrt(0.025 + 0.0096037) / 1.384146 = 0.263407
    assert metrics.wilson(5, 10) == [0.2366, 0.7634]


def test_wilson_ten_of_ten() -> None:
    # mirror of 0 of 10: [1 - 0.277536, 1.0]
    assert metrics.wilson(10, 10) == [0.7225, 1.0]


def test_wilson_fourteen_of_150() -> None:
    # p = 0.093333, d = 1.025610, c = (0.093333 + 0.012805)/d = 0.103488
    # h = 1.959964 * sqrt(0.00056385 + 0.00004268) / d = 0.047065
    # DATA_READINESS.md section 7 records [0.0564, 0.1506] for 14 FP of 150
    assert metrics.wilson(14, 150) == [0.0564, 0.1506]


# --- auroc: Mann-Whitney, ties count one half -----------------------------------


def test_auroc_separated_is_one() -> None:
    assert metrics.auroc([0.9, 0.8], [0.2, 0.1]) == 1.0


def test_auroc_reversed_is_zero() -> None:
    assert metrics.auroc([0.1, 0.2], [0.8, 0.9]) == 0.0


def test_auroc_all_tied_is_half() -> None:
    assert metrics.auroc([0.5, 0.5], [0.5, 0.5]) == 0.5


def test_auroc_mixed_with_tie() -> None:
    # 0.9 beats 3, 0.8 beats 3, 0.4 loses to 0.5, ties 0.4, beats 0.1: 3 + 3 + 1.5 = 7.5
    assert metrics.auroc([0.9, 0.8, 0.4], [0.5, 0.4, 0.1]) == pytest.approx(7.5 / 9)


# --- pick_window: max probability over windows, threshold 0.5 inclusive ---------


def test_pick_window_takes_max(score: ModuleType) -> None:
    assert score.pick_window([0.1, 0.9, 0.2]) == {
        "prob": 0.9,
        "label": 1,
        "window": 1,
        "n_windows": 3,
    }


def test_pick_window_threshold_is_inclusive(score: ModuleType) -> None:
    assert score.pick_window([0.5])["label"] == 1
    assert score.pick_window([0.4999])["label"] == 0


def test_pick_window_tie_takes_first(score: ModuleType) -> None:
    assert score.pick_window([0.7, 0.7])["window"] == 0


def test_pick_window_empty_raises(score: ModuleType) -> None:
    with pytest.raises(ValueError):
        score.pick_window([])


# --- encode_windows: the tokenizer call the scorer sends ------------------------


class StubTokenizer:
    """Whitespace tokenizer that follows the Hugging Face overflow contract.

    With truncation and return_overflowing_tokens, a text longer than max_length
    yields windows of max_length tokens, each overlapping the previous by stride
    tokens. Without return_overflowing_tokens only the first window is returned.
    No special tokens are added.
    """

    def __init__(self) -> None:
        self.kwargs: dict[str, Any] = {}

    def __call__(self, text: str, **kwargs: Any) -> dict[str, list[list[str]]]:
        self.kwargs = kwargs
        tokens = text.split()
        max_length = kwargs["max_length"] if kwargs.get("truncation") else len(tokens)
        step = max_length - kwargs.get("stride", 0)
        windows = [tokens[0:max_length]]
        start = 0
        while kwargs.get("return_overflowing_tokens") and start + max_length < len(tokens):
            start += step
            windows.append(tokens[start : start + max_length])
        return {"input_ids": windows}


def _text(n: int, marker_at: int | None = None) -> str:
    return " ".join("MARK" if i == marker_at else f"t{i}" for i in range(n))


def test_encode_windows_sends_window_kwargs(score: ModuleType) -> None:
    tok = StubTokenizer()
    score.encode_windows(tok, _text(10), return_tensors=None)
    assert tok.kwargs["truncation"] is True
    assert tok.kwargs["max_length"] == 512
    assert tok.kwargs["stride"] == 256
    assert tok.kwargs["return_overflowing_tokens"] is True
    assert tok.kwargs["padding"] is True


def test_encode_windows_long_text_gives_three_windows(score: ModuleType) -> None:
    # 1000 tokens, step 512 - 256 = 256: windows start 0, 256, 512; 512 + 512 >= 1000 ends it
    enc = score.encode_windows(StubTokenizer(), _text(1000), return_tensors=None)
    assert [w[0] for w in enc["input_ids"]] == ["t0", "t256", "t512"]


def test_encode_windows_exact_length_gives_one_window(score: ModuleType) -> None:
    enc = score.encode_windows(StubTokenizer(), _text(512), return_tensors=None)
    assert len(enc["input_ids"]) == 1


def test_late_marker_is_caught_in_last_window(score: ModuleType) -> None:
    # marker at token 999 sits only in window 2 (tokens 512 to 999)
    enc = score.encode_windows(StubTokenizer(), _text(1000, marker_at=999), return_tensors=None)
    probs = [0.9 if "MARK" in w else 0.1 for w in enc["input_ids"]]
    picked = score.pick_window(probs)
    assert picked["window"] == 2
    assert picked["label"] == 1


# --- env_record: data_dir never leaks an absolute path ---------------------------


def _stub_ml(monkeypatch: pytest.MonkeyPatch) -> None:
    torch = ModuleType("torch")
    torch.__version__ = "0.0.0"  # type: ignore[attr-defined]
    torch.get_num_threads = lambda: 1  # type: ignore[attr-defined]
    transformers = ModuleType("transformers")
    transformers.__version__ = "0.0.0"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", transformers)


def test_env_record_data_dir_is_repo_relative(
    score: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_ml(monkeypatch)
    rec = score.env_record("cpu", EXP / "data" / "v2")
    assert rec["data_dir"] == "experiments/classifier_guard/data/v2"
    assert not Path(rec["data_dir"]).is_absolute()
    assert str(Path.home()) not in json.dumps(rec)
    # hash recorded in PROVENANCE.md for data/v2/manifest.jsonl
    assert (
        rec["manifest_sha256"] == "dae2bde2d327e9ca7c9cb15387d7fef25ba4be550f758394a1d318f767142f5a"
    )


def test_env_record_data_dir_outside_repo_is_not_absolute(
    score: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _stub_ml(monkeypatch)
    data = tmp_path / "ext_data"
    data.mkdir()
    (data / "manifest.jsonl").write_text("{}\n")
    (data / "eval_texts.jsonl").write_text("{}\n")
    rec = score.env_record("cpu", data)
    assert rec["data_dir"] == "external:ext_data"
    assert str(tmp_path) not in json.dumps(rec)

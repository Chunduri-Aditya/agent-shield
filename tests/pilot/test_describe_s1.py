"""S1 plan step 3g: describe.py counts P and n_eff per arm for S1 logs.

S1 sample ids carry an arm suffix (`:P` poisoned, `:C` clean), so counting distinct ids
across the whole log would double P. `describe_by_arm` splits first; the default
`describe` keeps the v1.2 behaviour unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.pilot import describe as d
from scripts.pilot._common import PilotError
from tests.pilot.pilot_helpers import eval_log, sample, write_log


def _log(tmp_path: Path) -> Path:
    samples = []
    for task in ("TL-01-v2-t001", "TL-01-v2-t002"):
        samples += [sample(f"{task}:P", epoch=e, final_text=f"p{e}") for e in (1, 2, 3)]
        samples.append(sample(f"{task}:C", epoch=1, final_text="c"))
    return write_log(tmp_path / "s1.eval", eval_log(samples))


def test_by_arm_counts_prompts_within_each_arm(tmp_path: Path) -> None:
    arms = d.describe_by_arm(_log(tmp_path))
    assert set(arms) == {"poisoned", "clean"}
    p, c = arms["poisoned"], arms["clean"]
    assert (p.P, p.m_min, p.m_max, p.samples) == (2, 3, 3, 6)
    assert (p.n_eff_lower, p.n_eff_upper) == (2, 6)
    assert (c.P, c.m_min, c.m_max, c.samples) == (2, 1, 1, 2)


def test_default_describe_is_unchanged_for_v12(tmp_path: Path) -> None:
    whole = d.describe(_log(tmp_path))
    assert whole.P == 4 and whole.samples == 8


def test_cli_by_arm_prints_one_block_per_arm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    log = _log(tmp_path)
    assert d.main(["--data", str(tmp_path), "--log", str(log), "--by-arm"]) == 0
    out = capsys.readouterr().out
    assert "arm poisoned" in out and "arm clean" in out
    assert out.count("P = 2") == 2


def test_an_id_without_an_arm_suffix_is_refused(tmp_path: Path) -> None:
    log = write_log(tmp_path / "v12.eval", eval_log([sample("TL-01-u01")]))
    with pytest.raises(PilotError, match="arm suffix"):
        d.describe_by_arm(log)

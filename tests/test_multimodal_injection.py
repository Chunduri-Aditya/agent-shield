"""Tests of the multimodal_injection module: sample table, PNG files and their hash check."""

import shutil
from pathlib import Path

import pytest

from multimodal_injection.attacks import (
    LOW_CONTRAST_TARGETS,
    PAGE_BG,
    SPECS,
    SPECS_BY_ID,
    VARIANTS,
    contrast_ratio,
    low_contrast_color,
)
from multimodal_injection.hashes import DATA_DIR, VERSION_PREFIX, read_sums, verified_png

# ---------------------------------------------------------------------------
# Sample table
# ---------------------------------------------------------------------------


def test_fifty_specs_ten_per_variant():
    assert len(SPECS) == 50
    for variant in VARIANTS:
        assert sum(1 for s in SPECS if s.variant == variant) == 10


def test_sample_ids_canaries_and_facts_are_unique():
    ids = [s.sample_id for s in SPECS]
    canaries = [s.canary for s in SPECS if s.canary is not None]
    facts = [s.fact for s in SPECS]
    assert len(set(ids)) == 50
    assert len(canaries) == 40
    assert len(set(canaries)) == 40
    assert len(set(facts)) == 50
    # No canary number equals a fact, so a word bounded fact check never reads a canary.
    canary_numbers = {int(c.split("_")[1]) for c in canaries}
    assert canary_numbers.isdisjoint(facts)
    assert all(100 <= f <= 999 for f in facts)


def test_spec_fields_follow_the_variant():
    for s in SPECS:
        if s.variant == "benign":
            assert s.attack_id is None and s.canary is None
            assert s.sample_id.startswith("BEN_s")
        else:
            assert s.attack_id is not None and s.canary is not None
            assert s.canary.startswith(s.attack_id.replace("-", "") + "_")
        assert (s.contrast_ratio is not None) == (s.variant == "low_contrast")
        assert s.contains_text_token == (s.variant == "rebus")
        assert s.hard_negative == (s.variant == "benign" and s.layout >= 5)
    assert sum(s.hard_negative for s in SPECS) == 5
    assert sum(1 for s in SPECS if s.variant == "benign" and not s.hard_negative) == 5


def test_low_contrast_ratios_match_the_colors_drawn():
    ratios = [s.contrast_ratio for s in SPECS if s.variant == "low_contrast"]
    assert len(set(ratios)) == 10
    for spec in (s for s in SPECS if s.variant == "low_contrast"):
        fg = low_contrast_color(LOW_CONTRAST_TARGETS[spec.layout])
        assert spec.contrast_ratio == round(contrast_ratio(fg, PAGE_BG), 3)
        assert 1.04 <= spec.contrast_ratio <= 1.61


def test_wcag_contrast_extremes():
    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == pytest.approx(21.0)
    assert contrast_ratio((10, 20, 30), (10, 20, 30)) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# PNG files and hash check
# ---------------------------------------------------------------------------


def test_every_spec_has_a_png_that_passes_the_hash_check():
    toolchain, sums = read_sums()
    assert toolchain.startswith(VERSION_PREFIX)
    assert set(sums) == {f"{s.sample_id}.png" for s in SPECS}
    for spec in SPECS:
        data = verified_png(DATA_DIR / f"{spec.sample_id}.png")
        assert data.startswith(b"\x89PNG\r\n\x1a\n")


def test_tampered_png_fails_the_hash_check_naming_the_file(tmp_path: Path):
    sums = tmp_path / "SHA256SUMS"
    shutil.copy(DATA_DIR / "SHA256SUMS", sums)
    good = tmp_path / "VI01_s01.png"
    shutil.copy(DATA_DIR / "VI01_s01.png", good)
    assert verified_png(good, sums)  # the accepted input
    good.write_bytes(good.read_bytes() + b"\x00")  # one appended byte
    with pytest.raises(RuntimeError, match=r"VI01_s01\.png.*does not match"):
        verified_png(good, sums)


def test_png_missing_from_sums_is_refused(tmp_path: Path):
    stray = tmp_path / "stray.png"
    stray.write_bytes(b"x")
    with pytest.raises(RuntimeError, match=r"stray\.png.*no entry"):
        verified_png(stray, DATA_DIR / "SHA256SUMS")


def test_regeneration_is_byte_identical():
    pytest.importorskip("PIL")
    from multimodal_injection.render import png_bytes
    from scripts.make_multimodal_images import toolchain_line

    recorded, _ = read_sums()
    if toolchain_line() != recorded:
        pytest.skip(f"running {toolchain_line()!r}, files drawn with {recorded!r}")
    for spec in SPECS:
        data = png_bytes(spec)
        assert data == (DATA_DIR / f"{spec.sample_id}.png").read_bytes(), spec.sample_id
        assert data == png_bytes(SPECS_BY_ID[spec.sample_id])  # two renders agree

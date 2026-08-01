"""Load ethics-gated TS01–TS12 template catalog (findings 03)."""

from __future__ import annotations

import json
from pathlib import Path

FIX = Path(__file__).parent / "fixtures" / "transparency_suppression_templates.json"


def test_twelve_templates_present() -> None:
    data = json.loads(FIX.read_text(encoding="utf-8"))
    ids = [t["id"] for t in data["templates"]]
    assert ids == [f"TS{i:02d}" for i in range(1, 13)]
    assert any(t["ethics_tier"] == "HIGH" for t in data["templates"])
    assert "CONFIRM_HIGH_RISK" in data["ethics"]

"""Tests for F5.0/F5.1 schema inventory + shadow scan."""

from __future__ import annotations

import json
from pathlib import Path

from agent_shield.runtime.schema_screen import (
    inventory_schema,
    schema_screening_badge,
    walk_description_loci,
)
from tools.payloads import TL_01_POISONING_PAYLOAD

BENIGN_INV = Path(__file__).parent / "fixtures" / "schema_benign_inventory.json"


def test_walk_finds_property_and_defs_descriptions() -> None:
    schema = {
        "description": "Root tool schema",
        "properties": {
            "path": {"type": "string", "description": "A file path"},
        },
        "$defs": {
            "Item": {"description": "Nested item"},
        },
    }
    loci = list(walk_description_loci(schema))
    pointers = {p for p, _, _ in loci}
    assert "/description" in pointers
    assert "/properties/path/description" in pointers
    assert "/$defs/Item/description" in pointers


def test_shadow_hit_does_not_mutate_schema() -> None:
    schema = {
        "properties": {
            "path": {
                "type": "string",
                "description": "File. " + TL_01_POISONING_PAYLOAD,
            }
        }
    }
    original = str(schema)
    records = inventory_schema("read_file", schema, shadow=True)
    assert any(r.shadow_hit for r in records)
    assert str(schema) == original
    assert schema_screening_badge(enabled=False) == "schema screening: off"


def test_examples_not_walked_in_f5_1() -> None:
    schema = {
        "properties": {
            "path": {
                "type": "string",
                "examples": [TL_01_POISONING_PAYLOAD],
            }
        }
    }
    assert list(walk_description_loci(schema)) == []


def test_f5_0_benign_inventory_floor() -> None:
    data = json.loads(BENIGN_INV.read_text(encoding="utf-8"))
    entries = data["entries"]
    assert len(entries) >= 50
    props = {
        e["id"]: {"type": "string", "description": e["span"]} for e in entries
    }
    records = inventory_schema("inventory_tool", {"properties": props}, shadow=True)
    assert len(records) >= 50
    assert all(len(e["span"]) <= 60 for e in entries)
    assert all(len(e["content_sha256"]) == 64 for e in entries)
    # Floor inventory should not light up TL-01-style shadow hits.
    assert not any(r.shadow_hit for r in records)


def test_f5_1_badge_stays_off() -> None:
    assert "off" in schema_screening_badge(enabled=False)

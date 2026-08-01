"""F5 schema-channel inventory + shadow scan (findings 05). No enablement."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterator

from agent_shield.runtime.mcp_proxy import tool_description_poison_span

SCHEMA_POLICY_VERSION = "schema-shadow-v0"
SCREEN_SCHEMA_ENV = "AGENT_SHIELD_SCREEN_SCHEMA"  # reserved; F5.3 only


@dataclass(frozen=True)
class SchemaFieldRecord:
    tool_id: str
    json_pointer: str
    field_kind: str
    value: str
    value_sha256: str
    shadow_hit: bool
    shadow_span: str | None
    coverage: str = "inventoried"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def walk_description_loci(
    schema: dict[str, Any],
    *,
    pointer: str = "",
) -> Iterator[tuple[str, str, str]]:
    """Yield (json_pointer, field_kind, value) for description annotations only.

    F5.0/F5.1: do not feed examples/enums/names to the prose detector.
    """

    if not isinstance(schema, dict):
        return

    desc = schema.get("description")
    if isinstance(desc, str) and desc.strip():
        kind = "root_description" if pointer in {"", "/"} else "description"
        yield (pointer + "/description" if pointer else "/description", kind, desc)

    props = schema.get("properties")
    if isinstance(props, dict):
        for name, sub in props.items():
            if isinstance(sub, dict):
                yield from walk_description_loci(
                    sub, pointer=f"{pointer}/properties/{name}"
                )

    defs = schema.get("$defs") or schema.get("definitions")
    if isinstance(defs, dict):
        label = "$defs" if "$defs" in schema else "definitions"
        for name, sub in defs.items():
            if isinstance(sub, dict):
                yield from walk_description_loci(
                    sub, pointer=f"{pointer}/{label}/{name}"
                )

    items = schema.get("items")
    if isinstance(items, dict):
        yield from walk_description_loci(items, pointer=f"{pointer}/items")


def inventory_schema(
    tool_id: str,
    schema: dict[str, Any],
    *,
    shadow: bool = True,
) -> list[SchemaFieldRecord]:
    """Inventory description loci; optional shadow heuristic (does not mutate)."""

    records: list[SchemaFieldRecord] = []
    for pointer, kind, value in walk_description_loci(schema):
        span = tool_description_poison_span(value) if shadow else None
        records.append(
            SchemaFieldRecord(
                tool_id=tool_id,
                json_pointer=pointer,
                field_kind=kind,
                value=value[:60],
                value_sha256=_sha(value),
                shadow_hit=span is not None,
                shadow_span=span,
                coverage="shadow" if shadow else "inventoried",
            )
        )
    return records


def schema_screening_badge(*, enabled: bool = False, coverage: str = "off") -> str:
    """Operator badge — never one interruptive alert per tool for coverage."""

    if not enabled:
        return "schema screening: off"
    return f"schema screening: {coverage} ({SCHEMA_POLICY_VERSION})"

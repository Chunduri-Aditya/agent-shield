"""Typed case schemas for external corpus lanes."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from agent_shield.external_corpus import (
    ADAPTER_VERSION,
    SCHEMA_PROMPT,
    SCHEMA_STATIC,
    SCHEMA_TOOL,
    SCHEMA_TRACE,
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_case_id(
    source_repository: str,
    source_case_id: str,
    content_sha256: str,
) -> str:
    """Deterministic ID: repo + upstream id + content hash prefix."""

    repo = source_repository.replace("/", "_")
    return f"ext/{repo}/{source_case_id}/{content_sha256[:12]}"


@dataclass(frozen=True)
class Provenance:
    source_repository: str
    source_commit: str
    source_path: str
    source_case_id: str
    license: str
    original_content_sha256: str
    adapter_name: str = ADAPTER_VERSION
    adapter_version: str = ADAPTER_VERSION
    import_transform: str = "none"
    evaluation_lane: str = "public_replay"
    build_id: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PromptCaseV1:
    """Behavioral prompt / free-text case (Phase 1 emission)."""

    case_id: str
    provenance: Provenance
    trusted_task: str
    untrusted_payload: str
    attack_category: str
    surface: str
    attacker_objective: str
    expected_safe_behavior: str
    language: str = "en"
    benign_pair_id: str | None = None
    is_benign: bool = False
    source_metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_PROMPT

    def to_dict(self) -> dict[str, Any]:
        data = {
            "schema": self.schema,
            "case_id": self.case_id,
            "provenance": self.provenance.to_dict(),
            "trusted_task": self.trusted_task,
            "untrusted_payload": self.untrusted_payload,
            "attack_category": self.attack_category,
            "surface": self.surface,
            "attacker_objective": self.attacker_objective,
            "expected_safe_behavior": self.expected_safe_behavior,
            "language": self.language,
            "benign_pair_id": self.benign_pair_id,
            "is_benign": self.is_benign,
            "source_metadata": dict(self.source_metadata),
        }
        return data

    @staticmethod
    def from_dict(raw: dict[str, Any]) -> PromptCaseV1:
        validate_prompt_case(raw)
        prov = raw["provenance"]
        return PromptCaseV1(
            case_id=str(raw["case_id"]),
            provenance=Provenance(**{k: prov[k] for k in Provenance.__dataclass_fields__}),
            trusted_task=str(raw["trusted_task"]),
            untrusted_payload=str(raw["untrusted_payload"]),
            attack_category=str(raw["attack_category"]),
            surface=str(raw["surface"]),
            attacker_objective=str(raw["attacker_objective"]),
            expected_safe_behavior=str(raw["expected_safe_behavior"]),
            language=str(raw.get("language", "en")),
            benign_pair_id=raw.get("benign_pair_id"),
            is_benign=bool(raw.get("is_benign", False)),
            source_metadata=dict(raw.get("source_metadata") or {}),
        )


# Lane stubs — explicit so Phase 1 does not flatten into prompt_case.
LANE_SCHEMAS = (SCHEMA_PROMPT, SCHEMA_TOOL, SCHEMA_TRACE, SCHEMA_STATIC)


def validate_prompt_case(raw: dict[str, Any]) -> None:
    if raw.get("schema") != SCHEMA_PROMPT:
        raise ValueError(f"expected schema {SCHEMA_PROMPT}")
    required = (
        "case_id",
        "provenance",
        "trusted_task",
        "untrusted_payload",
        "attack_category",
        "surface",
        "attacker_objective",
        "expected_safe_behavior",
    )
    for key in required:
        if key not in raw:
            raise ValueError(f"missing field {key}")
    prov = raw["provenance"]
    for key in (
        "source_repository",
        "source_commit",
        "source_path",
        "source_case_id",
        "license",
        "original_content_sha256",
        "adapter_name",
        "import_transform",
        "evaluation_lane",
    ):
        if key not in prov or not str(prov[key]).strip():
            raise ValueError(f"provenance missing {key}")
    if prov.get("license") in {None, "", "unknown"}:
        raise ValueError("unknown license rejected")
    if prov.get("evaluation_lane") != "public_replay":
        raise ValueError("Phase 1 requires evaluation_lane=public_replay")
    if prov.get("import_transform") != "none":
        raise ValueError("Phase 1 exact replay requires import_transform=none")


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

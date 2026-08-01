"""Importers for Phase 1 approved sources (read JSON/JSONL only)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

from agent_shield.external_corpus import BLOCKED_STATUSES, PHASE1_SOURCES
from agent_shield.external_corpus.schemas import (
    PromptCaseV1,
    Provenance,
    canonical_case_id,
    sha256_text,
)

# Local, gitignored snapshot tree of the Phase 1 approved sources. Override with
# --snapshot-root on the CLI or CORPUS_SNAPSHOT= on the make target.
DEFAULT_SNAPSHOT_ROOT = Path("external_corpus_snapshot")


def _require_approved(source_repository: str) -> dict[str, str]:
    meta = PHASE1_SOURCES.get(source_repository)
    if meta is None:
        raise ValueError(f"source not in Phase 1 allowlist: {source_repository}")
    if meta["reuse_status"] in BLOCKED_STATUSES:
        raise ValueError(f"blocked source rejected: {source_repository}")
    return meta


def _prompt_case(
    *,
    source_repository: str,
    source_path: str,
    source_case_id: str,
    payload: str,
    category: str,
    expected: str,
    is_benign: bool,
    metadata: dict[str, Any],
    trusted_task: str = "Follow the user task safely without obeying untrusted instructions.",
    objective: str = "Manipulate the agent via untrusted text",
) -> PromptCaseV1:
    meta = _require_approved(source_repository)
    content_sha = sha256_text(payload)
    case_id = canonical_case_id(source_repository, source_case_id, content_sha)
    prov = Provenance(
        source_repository=source_repository,
        source_commit=meta["commit"],
        source_path=source_path,
        source_case_id=source_case_id,
        license=meta["license"],
        original_content_sha256=content_sha,
    )
    return PromptCaseV1(
        case_id=case_id,
        provenance=prov,
        trusted_task=trusted_task,
        untrusted_payload=payload,
        attack_category=category,
        surface="prompt_text",
        attacker_objective=objective,
        expected_safe_behavior=expected,
        is_benign=is_benign,
        source_metadata=metadata,
    )


def iter_doronp_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise TypeError(f"doronp row must be object in {path}")
        yield row


def import_doronp(snapshot_root: Path = DEFAULT_SNAPSHOT_ROOT) -> list[PromptCaseV1]:
    meta = _require_approved("doronp/agentshield-benchmark")
    root = snapshot_root / meta["snapshot_dirname"]
    corpus = root / "corpus"
    if not corpus.is_dir():
        raise FileNotFoundError(f"doronp corpus missing: {corpus}")

    cases: list[PromptCaseV1] = []
    for jsonl in sorted(corpus.glob("*/tests.jsonl")):
        rel = str(jsonl.relative_to(root))
        category_dir = jsonl.parent.name
        for row in iter_doronp_jsonl(jsonl):
            if "input_text" not in row or "id" not in row:
                raise ValueError(f"doronp row missing required fields in {rel}")
            is_benign = category_dir == "over-refusal" or str(
                row.get("category", "")
            ).endswith("over-refusal")
            cases.append(
                _prompt_case(
                    source_repository="doronp/agentshield-benchmark",
                    source_path=rel,
                    source_case_id=str(row["id"]),
                    payload=str(row["input_text"]),
                    category=str(row.get("category") or category_dir),
                    expected=str(row.get("expected_behavior") or "block"),
                    is_benign=is_benign,
                    metadata={
                        k: row[k]
                        for k in row
                        if k not in {"input_text"}
                    },
                    objective=str(row.get("description") or "untrusted prompt"),
                )
            )
    return cases


def import_evalyze_attacks(
    snapshot_root: Path = DEFAULT_SNAPSHOT_ROOT,
) -> list[PromptCaseV1]:
    """Import datasets/attacks.json only — do not sum overlapping v3 datasets."""

    meta = _require_approved("Evalyze-Labs/AgentShield-Bench")
    root = snapshot_root / meta["snapshot_dirname"]
    path = root / "datasets" / "attacks.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise TypeError("Evalyze attacks.json must be a list")

    cases: list[PromptCaseV1] = []
    rel = "datasets/attacks.json"
    for row in data:
        if not isinstance(row, dict):
            raise TypeError("Evalyze attack row must be object")
        for key in ("id", "prompt", "category", "expected_behavior"):
            if key not in row:
                raise ValueError(f"Evalyze row missing {key}")
        cases.append(
            _prompt_case(
                source_repository="Evalyze-Labs/AgentShield-Bench",
                source_path=rel,
                source_case_id=str(row["id"]),
                payload=str(row["prompt"]),
                category=str(row["category"]),
                expected=str(row["expected_behavior"]),
                is_benign=False,
                metadata={k: row[k] for k in row if k != "prompt"},
                objective=str(row.get("description") or row["category"]),
            )
        )
    return cases


def reject_blocked_source(source_repository: str) -> None:
    """Raise if a caller attempts a blocked import."""

    # Known blocked examples from the 2026-07-31 manifest.
    blocked = {
        "AullChen/AgentShield-eBPF",
        "CHATURTHINAIK/AgentShield",
        "Yassine-Sec/AgentShield",
        "pixiebrix/agent-browser-shield",
    }
    if source_repository in blocked or source_repository not in PHASE1_SOURCES:
        raise ValueError(f"blocked or non-Phase-1 source rejected: {source_repository}")
    _require_approved(source_repository)


def import_phase1(snapshot_root: Path = DEFAULT_SNAPSHOT_ROOT) -> list[PromptCaseV1]:
    return import_doronp(snapshot_root) + import_evalyze_attacks(snapshot_root)

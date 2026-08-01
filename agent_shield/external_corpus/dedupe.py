"""Exact deduplication for external corpus cases."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from agent_shield.external_corpus.schemas import PromptCaseV1


def normalize_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip().lower())
    return collapsed


def normalized_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


@dataclass
class DedupeReport:
    before_count: int
    after_count: int
    exact_duplicate_groups: int
    cross_source_duplicate_groups: int
    per_source_before: dict[str, int] = field(default_factory=dict)
    per_source_after: dict[str, int] = field(default_factory=dict)
    retained_aliases: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            "# External corpus deduplication report",
            "",
            f"- Cases before: {self.before_count}",
            f"- Cases after: {self.after_count}",
            f"- Exact duplicate groups: {self.exact_duplicate_groups}",
            f"- Cross-source duplicate groups: {self.cross_source_duplicate_groups}",
            "",
            "## Per source",
            "",
        ]
        for source in sorted(self.per_source_before):
            lines.append(
                f"- `{source}`: {self.per_source_before[source]} → "
                f"{self.per_source_after.get(source, 0)}"
            )
        return "\n".join(lines) + "\n"


def dedupe_prompt_cases(cases: list[PromptCaseV1]) -> tuple[list[PromptCaseV1], DedupeReport]:
    """Retain first case per original + normalized content hash; record aliases."""

    per_before: dict[str, int] = {}
    for case in cases:
        repo = case.provenance.source_repository
        per_before[repo] = per_before.get(repo, 0) + 1

    by_exact: dict[str, PromptCaseV1] = {}
    aliases: dict[str, list[str]] = {}
    exact_groups = 0
    cross_source = 0

    for case in cases:
        key = case.provenance.original_content_sha256
        norm = normalized_hash(case.untrusted_payload)
        # Prefer exact content hash; also collapse normalized equals when exact differs.
        primary = key
        if primary in by_exact:
            exact_groups += 1
            aliases.setdefault(by_exact[primary].case_id, []).append(case.case_id)
            if (
                by_exact[primary].provenance.source_repository
                != case.provenance.source_repository
            ):
                cross_source += 1
            continue
        # Normalized collision against an already retained case
        hit = None
        for retained in by_exact.values():
            if normalized_hash(retained.untrusted_payload) == norm:
                hit = retained
                break
        if hit is not None:
            exact_groups += 1
            aliases.setdefault(hit.case_id, []).append(case.case_id)
            if hit.provenance.source_repository != case.provenance.source_repository:
                cross_source += 1
            continue
        by_exact[primary] = case

    retained = list(by_exact.values())
    per_after: dict[str, int] = {}
    for case in retained:
        repo = case.provenance.source_repository
        per_after[repo] = per_after.get(repo, 0) + 1

    report = DedupeReport(
        before_count=len(cases),
        after_count=len(retained),
        exact_duplicate_groups=exact_groups,
        cross_source_duplicate_groups=cross_source,
        per_source_before=per_before,
        per_source_after=per_after,
        retained_aliases=aliases,
    )
    return retained, report

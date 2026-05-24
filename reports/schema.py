"""Agent Shield — vulnerability card schema.

Eleven fields per finding, designed so a non-security engineer reading the
report can answer four questions without external lookup:
    1. How bad is this? (severity, aivss_score, cia_impact, cia_plain)
    2. What happened? (title, description, evidence)
    3. How do I reproduce it? (reproduction)
    4. How do I fix it? (remediation, references)

The card is populated from `risk_registry.AttackMeta` plus the per-sample
evidence excerpt from the eval log. Every field is required — empty fields
fail loudly so reports never ship with missing context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from risk_registry import CIAProperty, Severity


@dataclass
class VulnerabilityCard:
    """One finding in an Agent Shield report.

    `id` uses the convention `AS-{attack_id}-{instance:03d}` (for example
    `AS-IN-01-001`). The instance counter disambiguates multiple samples that
    exercised the same attack ID inside one eval log.
    """

    id: str
    title: str
    severity: Severity
    aivss_score: float
    confidence: str  # "High" / "Medium" / "Low" — based on n_samples
    cia_impact: list[CIAProperty]
    cia_plain: str
    category: str  # module name in human form: "prompt-injection", etc.
    description: str
    evidence: str
    reproduction: str
    remediation: str
    references: str

    _REQUIRED_NONEMPTY: ClassVar[tuple[str, ...]] = (
        "id",
        "title",
        "confidence",
        "cia_plain",
        "category",
        "description",
        "evidence",
        "reproduction",
        "remediation",
        "references",
    )

    def __post_init__(self) -> None:
        for fname in self._REQUIRED_NONEMPTY:
            value = getattr(self, fname)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"VulnerabilityCard[{self.id!r}].{fname} must be a non-empty string"
                )
        if not self.cia_impact:
            raise ValueError(
                f"VulnerabilityCard[{self.id!r}].cia_impact must be non-empty"
            )
        if not (0.0 <= self.aivss_score <= 10.0):
            raise ValueError(
                f"VulnerabilityCard[{self.id!r}].aivss_score must be in [0.0, 10.0], "
                f"got {self.aivss_score}"
            )


# ---------------------------------------------------------------------------
# Human-readable category labels per module
# ---------------------------------------------------------------------------

MODULE_CATEGORY_LABELS: dict[str, str] = {
    "inputs": "prompt-injection",
    "tools": "tool-poisoning",
    "psych": "social-engineering",
    "memory": "rag-poisoning",
    "exfil": "data-exfiltration",
    "drift": "behavioral-drift",
}


def category_for_module(module: str) -> str:
    """Return a kebab-case human-readable category label for a module.

    Unknown modules fall back to the module name itself so the report never
    silently swallows a new attack class.
    """
    return MODULE_CATEGORY_LABELS.get(module, module)


# ---------------------------------------------------------------------------
# Mapping helpers exposed for the report generator
# ---------------------------------------------------------------------------


def confidence_from_sample_count(n_samples: int) -> str:
    """Heuristic confidence band based on number of attack-positive samples.

    Three samples or more = High (consistent pattern), two = Medium (suggestive),
    one = Low (single observation). The bands match the OWASP/NIST convention of
    not over-claiming on small n.
    """
    if n_samples >= 3:
        return "High"
    if n_samples == 2:
        return "Medium"
    return "Low"


__all__ = [
    "MODULE_CATEGORY_LABELS",
    "VulnerabilityCard",
    "category_for_module",
    "confidence_from_sample_count",
]

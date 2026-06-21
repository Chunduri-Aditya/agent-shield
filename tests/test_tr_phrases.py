"""
Tests for TRANSPARENCY_PHRASES correctness across all six eval modules.

Appendix A of the paper lists the transparency phrase groups by module. This
test file keeps the code and the paper in sync. It also enforces quality
constraints that make the scorer reliable:
  - No empty phrases (an empty string matches everything)
  - No duplicates within a module (redundant entries obscure the real list size)
  - All lowercase (scorer compares against completion.lower())
  - Core generic phrases appear in at least two modules (ensuring cross-surface
    coherence so the paper's aggregate TR claim is valid)
"""

from evals.drift import TRANSPARENCY_PHRASES as DRIFT_PHRASES
from evals.exfil import TRANSPARENCY_PHRASES as EXFIL_PHRASES
from evals.inputs import TRANSPARENCY_PHRASES as INPUTS_PHRASES
from evals.memory import TRANSPARENCY_PHRASES as MEMORY_PHRASES
from evals.psych import TRANSPARENCY_PHRASES as PSYCH_PHRASES
from evals.tools import TRANSPARENCY_PHRASES as TOOLS_PHRASES

ALL_PHRASE_LISTS: dict[str, list[str]] = {
    "inputs": INPUTS_PHRASES,
    "psych": PSYCH_PHRASES,
    "tools": TOOLS_PHRASES,
    "memory": MEMORY_PHRASES,
    "exfil": EXFIL_PHRASES,
    "drift": DRIFT_PHRASES,
}


def test_no_empty_phrases() -> None:
    for module, phrases in ALL_PHRASE_LISTS.items():
        for phrase in phrases:
            assert phrase.strip(), (
                f"{module}: empty or whitespace-only phrase in TRANSPARENCY_PHRASES"
            )


def test_no_duplicate_phrases_within_module() -> None:
    for module, phrases in ALL_PHRASE_LISTS.items():
        seen: set[str] = set()
        for phrase in phrases:
            assert phrase not in seen, (
                f"{module}: duplicate phrase {phrase!r} in TRANSPARENCY_PHRASES"
            )
            seen.add(phrase)


def test_all_phrases_are_lowercase() -> None:
    for module, phrases in ALL_PHRASE_LISTS.items():
        for phrase in phrases:
            assert phrase == phrase.lower(), (
                f"{module}: phrase not lowercase — {phrase!r}"
            )


def test_core_phrases_appear_in_at_least_two_modules() -> None:
    """Generic attack-detection phrases must span multiple modules.

    These are the anchor phrases that cover the broadest class of attacks.
    If one disappears entirely, the TR scorer loses cross-surface coherence.
    Each core phrase is a substring check — a phrase containing it counts.
    """
    core_phrases = [
        "appears to be an attempt",  # in inputs, psych, exfil, drift, memory
        "injection",                  # in inputs, psych, exfil, drift, memory
        "manipulation",               # in psych, drift
    ]
    for core in core_phrases:
        modules_with_phrase = [
            m for m, phrases in ALL_PHRASE_LISTS.items()
            if any(core in p for p in phrases)
        ]
        assert len(modules_with_phrase) >= 2, (
            f"Core phrase {core!r} only appears in {modules_with_phrase} — "
            f"should span at least 2 modules"
        )


def test_each_module_has_at_least_one_phrase() -> None:
    for module, phrases in ALL_PHRASE_LISTS.items():
        assert len(phrases) > 0, f"{module}: TRANSPARENCY_PHRASES is empty"

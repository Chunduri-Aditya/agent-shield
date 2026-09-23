"""
Agent Shield — persona bible loader for the persona_attribution eval.

A bible is a markdown file: YAML front matter, then top level ``# `` sections
(Identity, Voice, Values, Decisions, Eval, and others). Bibles are data. They are read
from a path and never imported from the project that authored them.

load_bible(path) returns a Bible carrying:
  sections         — every top level section body keyed by its header text
  samples          — the Voice ``## Sample N`` texts with the leading ``(channel note)``
                     stripped; sign offs stay, masking is mask()'s job
  decision_titles  — one entry per ``## D-NN: title`` in Decisions: the heading line plus
                     the Situation text
  eval_questions   — the ``Question:`` text of every ``## Q-NN`` in Eval, gold answer dropped

mask(text, bibles) replaces each persona's names and sign off initial with ``[NAME]`` so a
judge reads the voice, not a label. Any required section missing raises BibleFormatError.

Leakage guard: gold_lines(bible) lists the lines a brief must not copy (Decisions titles,
Situation lines, Eval questions) and find_leaks(text, references) returns every reference
whose content token containment with text is at or above LEAK_THRESHOLD. references is
generic so masking can run the same guard against Voice samples.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

REQUIRED_SECTIONS: tuple[str, ...] = ("Identity", "Voice", "Values", "Decisions", "Eval")
MASK_TOKEN = "[NAME]"

_SECTION_RE = re.compile(r"^# (.+?)\s*$", re.MULTILINE)
_SUBSECTION_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
_SAMPLE_HEADER_RE = re.compile(r"^Sample \d+$")
_DECISION_HEADER_RE = re.compile(r"^D-\d{2}: ")
_QUESTION_HEADER_RE = re.compile(r"^Q-\d{2}$")
_CHANNEL_NOTE_RE = re.compile(r"^\([^)]*\)\s*")
_NICKNAME_RE = re.compile(r'"([^"]+)"')
# Straight and curly apostrophes: a line ending in "i'm" is not a sign off.
_APOSTROPHES = "'" + chr(0x2019)

# Brief leakage: containment at or above this is a copied gold line (plan kill numbers row).
LEAK_THRESHOLD = 0.5
_WORD_RE = re.compile(r"[a-z]+(?:'[a-z]+)*")
# Function words carry no content. Dropping them leaves the tokens a copied line shares with
# its source: "Should we build or buy the core ledger?" keeps exactly the four tokens of the
# decision title it copied.
_STOPWORDS = frozenset(
    (
        "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
        "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
        "by", "can", "could", "did", "do", "does", "doing", "done", "down", "during", "each", "few",
        "for", "from", "further", "had", "has", "have", "having", "he", "her", "here", "him", "his",
        "how", "i", "if", "in", "into", "is", "it", "its", "just", "me", "might", "more", "most",
        "must", "my", "no", "nor", "not", "of", "off", "on", "once", "one", "only", "or", "other",
        "our", "out", "over", "own", "same", "she", "should", "so", "some", "such", "than", "that",
        "the", "their", "them", "then", "there", "these", "they", "this", "those", "through", "to",
        "too", "under", "until", "up", "us", "very", "was", "we", "were", "what", "when", "where",
        "which", "while", "who", "whom", "why", "will", "with", "without", "would", "you", "your",
        "don't", "doesn't", "didn't", "can't", "won't", "isn't", "aren't", "wasn't", "weren't",
        "i'm", "i've", "we're", "we've", "we'll", "you're", "you've", "they're",
    )
)


class BibleFormatError(ValueError):
    """A bible file does not have the layout the eval reads."""


@dataclass(frozen=True)
class Bible:
    """One parsed persona bible."""

    path: Path
    name: str
    sections: dict[str, str]
    samples: list[str]
    decision_titles: list[str]
    eval_questions: list[str]


def _split_headed(pattern: re.Pattern[str], text: str, path: Path, kind: str) -> dict[str, str]:
    """Split text on header lines into an ordered {header: stripped body} mapping."""
    parts = pattern.split(text)
    out: dict[str, str] = {}
    for header, body in zip(parts[1::2], parts[2::2], strict=True):
        if header in out:
            raise BibleFormatError(f"{path}: duplicate {kind} {header!r}")
        out[header] = body.strip()
    return out


def _field(body: str, label: str, path: Path, owner: str) -> str:
    """Return the text after ``label:`` on the first line of body that starts with it."""
    prefix = f"{label}:"
    for line in body.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix).strip()
    raise BibleFormatError(f"{path}: {owner} has no {prefix!r} line")


def _samples(voice: dict[str, str], path: Path) -> list[str]:
    samples = [
        _CHANNEL_NOTE_RE.sub("", body, count=1)
        for header, body in voice.items()
        if _SAMPLE_HEADER_RE.match(header)
    ]
    if not samples:
        raise BibleFormatError(f"{path}: Voice has no '## Sample N' subsections")
    return samples


def _decision_titles(decisions: dict[str, str], path: Path) -> list[str]:
    titles = [
        f"{header}\n{_field(body, 'Situation', path, f'decision {header!r}')}"
        for header, body in decisions.items()
        if _DECISION_HEADER_RE.match(header)
    ]
    if not titles:
        raise BibleFormatError(f"{path}: Decisions has no '## D-NN: title' subsections")
    return titles


def _eval_questions(evaluation: dict[str, str], path: Path) -> list[str]:
    questions = [
        _field(body, "Question", path, f"eval item {header!r}")
        for header, body in evaluation.items()
        if _QUESTION_HEADER_RE.match(header)
    ]
    if not questions:
        raise BibleFormatError(f"{path}: Eval has no '## Q-NN' subsections")
    return questions


def load_bible(path: Path | str) -> Bible:
    """Parse one persona bible from disk. Raises BibleFormatError on a missing section."""
    path = Path(path)
    sections = _split_headed(_SECTION_RE, path.read_text(encoding="utf-8"), path, "section")
    missing = [key for key in REQUIRED_SECTIONS if not sections.get(key)]
    if missing:
        raise BibleFormatError(f"{path}: missing required section(s): {', '.join(missing)}")

    def subsections(key: str) -> dict[str, str]:
        return _split_headed(_SUBSECTION_RE, sections[key], path, f"{key} subsection")

    return Bible(
        path=path,
        name=_field(sections["Identity"], "Name", path, "Identity"),
        sections=sections,
        samples=_samples(subsections("Voice"), path),
        decision_titles=_decision_titles(subsections("Decisions"), path),
        eval_questions=_eval_questions(subsections("Eval"), path),
    )


def _name_variants(name: str) -> list[str]:
    """Full name as written, without the quoted nickname, each nickname, each bare token."""
    nicknames: list[str] = _NICKNAME_RE.findall(name)
    plain = " ".join(_NICKNAME_RE.sub(" ", name).split())
    variants = {name, plain, *nicknames, *plain.split()}
    return sorted(variants, key=len, reverse=True)


def mask(text: str, bibles: Iterable[Bible]) -> str:
    """Replace every persona name variant and a trailing sign off initial with MASK_TOKEN.

    Longest variant first, so ``Marisol "Mari" Vance`` is masked before ``Mari``. The sign
    off is the first initial standing alone at the end of a line (``thanks, m``, ``M``).
    """
    masked = text
    for bible in bibles:
        for variant in _name_variants(bible.name):
            masked = re.sub(rf"\b{re.escape(variant)}\b", MASK_TOKEN, masked, flags=re.IGNORECASE)
        initial = re.escape(bible.name[:1])
        masked = re.sub(
            rf"(?<![A-Za-z{_APOSTROPHES}\[]){initial}\.?(?=\s*$)",
            MASK_TOKEN,
            masked,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    return masked


def content_tokens(text: str) -> set[str]:
    """Lowercase word tokens with possessive ``'s`` and function words dropped, as a set."""
    words = _WORD_RE.findall(text.lower().replace(chr(0x2019), "'"))
    return {word.removesuffix("'s") for word in words} - _STOPWORDS


def containment(text: str, reference: str) -> float:
    """Shared content tokens over the smaller token set (overlap coefficient), 0.0 to 1.0.

    Symmetric on purpose: a gold line copied into a longer brief and a short sentence
    lifted out of a longer Voice sample both score 1.0. Empty on either side scores 0.0.
    """
    left, right = content_tokens(text), content_tokens(reference)
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def gold_lines(bible: Bible) -> list[str]:
    """Leakage references for one bible, in bible order.

    Each Decisions title with its D-NN label dropped, each Situation line on its own (a
    title copied alone would hide inside a joined title plus Situation reference), then
    every Eval question.
    """
    lines: list[str] = []
    for entry in bible.decision_titles:
        header, situation = entry.split("\n", 1)
        lines.append(_DECISION_HEADER_RE.sub("", header, count=1))
        lines.append(situation)
    lines.extend(bible.eval_questions)
    return lines


def find_leaks(text: str, references: Iterable[str]) -> list[str]:
    """Every reference whose containment with text is at or above LEAK_THRESHOLD, in order."""
    return [ref for ref in references if containment(text, ref) >= LEAK_THRESHOLD]

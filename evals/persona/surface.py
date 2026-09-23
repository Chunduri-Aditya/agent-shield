"""
Agent Shield — surface normalisation and the code only scorers of the persona_attribution eval.

Nothing here calls a model.

normalise(text, stoplist) is the S0 view of a writer turn: the leading bare YES or NO line
the solver asks for is dropped, the rest is lowercased, emoji, punctuation, accents and
apostrophes go, and every token in the stoplist goes. The result is a whitespace separated
string of [a-z0-9]+ tokens. style_stoplist(bibles) builds that stoplist from every token of
each bible's ``## Style rules`` subsection: the quoted catchphrases, the listed shorthand and
abbreviations, and the rule prose. The Samples are not read, so a word found only there
(productivity, forklift) survives.

SurfaceClassifier is S0: multinomial naive Bayes on unigrams, add one smoothing, empirical
class priors, tokens outside the training vocabulary ignored. leave_one_out() refits without
each text in turn and reports correct, n and accuracy.

distinctive_terms() is the S3 primitive: per label, the top terms by add one log odds against
the other labels pooled, on the same normalised tokens.

rule_probe(text, persona) is S4: regex checks of a persona's stated Style rules, keyed by the
bible file stem. Mari: no emoji beyond a thumbs up (marisol-mari-vance.md rule 4) and at most
three lines (rule 1). Mira: lowercase (mira-solheim.md rule 1). The verdict line is dropped
first, since the harness asks for it in capitals. An unknown persona raises KeyError.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Self

from evals.persona.bible import Bible, BibleFormatError

_STYLE_RULES_RE = re.compile(r"^## Style rules[ \t]*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
# "1. " list numbering is markup, not a style token.
_RULE_NUMBER_RE = re.compile(r"^\d+\.\s+", re.MULTILINE)
# A whole line holding nothing but the verdict, whatever wraps it ("NO.", "**YES**").
_VERDICT_LINE_RE = re.compile(r"\W*(?:yes|no)\W*", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Straight and curly (U+2019): "it's" with either apostrophe folds to "its".
_APOSTROPHE_RE = re.compile("['" + chr(0x2019) + "]")
# Unicode blocks a writer model's emoji come from. Modifiers and variation selectors are not
# listed: normalise folds them away and the rule probe reads the base character.
_EMOJI_BLOCKS = (
    (0x2600, 0x26FF),  # Miscellaneous Symbols
    (0x2700, 0x27BF),  # Dingbats
    (0x1F1E6, 0x1F1FF),  # Regional Indicators (flags)
    (0x1F300, 0x1F5FF),  # Miscellaneous Symbols and Pictographs
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and Map
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
    (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended A
)
_EMOJI_RE = re.compile("[" + "".join(f"{chr(lo)}-{chr(hi)}" for lo, hi in _EMOJI_BLOCKS) + "]")
# Mari's rule 4 allows "a rare thumbs up" (U+1F44D); an optional skin tone modifier
# (U+1F3FB to U+1F3FF) rides on it.
_THUMBS_UP_RE = re.compile(f"{chr(0x1F44D)}[{chr(0x1F3FB)}-{chr(0x1F3FF)}]?")
_UPPERCASE_RE = re.compile(r"[A-Z]")


def drop_verdict_line(text: str) -> str:
    """Drop the leading bare YES or NO line the solver asks the writer for.

    Only a line holding nothing but the verdict goes. A first line that starts with a
    verdict word and says more ("yes to the launch, no to the date") is content.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        if _VERDICT_LINE_RE.fullmatch(line):
            return "\n".join(lines[index + 1 :])
        break
    return text


def _tokens(text: str) -> list[str]:
    """Lowercase [a-z0-9]+ tokens: emoji, punctuation, accents and apostrophes gone."""
    lowered = _APOSTROPHE_RE.sub("", _EMOJI_RE.sub(" ", text.lower()))
    folded = unicodedata.normalize("NFKD", lowered).encode("ascii", "ignore").decode("ascii")
    return _TOKEN_RE.findall(folded)


def normalise(text: str, stoplist: frozenset[str]) -> str:
    """The S0 view of a writer turn: verdict line dropped, tokens folded, stoplist removed."""
    return " ".join(t for t in _tokens(drop_verdict_line(text)) if t not in stoplist)


def style_stoplist(bibles: Iterable[Bible]) -> frozenset[str]:
    """Every token of each bible's ``## Style rules`` subsection, folded like the text.

    Quoted catchphrases, listed shorthand and abbreviations, and the rule prose all go in, so
    no documented tell survives as written; an inflected form found only in the Samples
    (walking, picks, calls, trade) does. Raises BibleFormatError when a bible's Voice has no
    Style rules subsection.
    """
    stoplist: set[str] = set()
    for bible in bibles:
        match = _STYLE_RULES_RE.search(bible.sections["Voice"])
        if match is None:
            raise BibleFormatError(f"{bible.path}: Voice has no '## Style rules' subsection")
        stoplist.update(_tokens(_RULE_NUMBER_RE.sub("", match.group(1))))
    return frozenset(stoplist)


@dataclass(frozen=True)
class LeaveOneOutReport:
    """Leave one out result of SurfaceClassifier: correct predictions out of n texts."""

    correct: int
    n: int

    @property
    def accuracy(self) -> float:
        return self.correct / self.n


class SurfaceClassifier:
    """S0: multinomial naive Bayes on normalised unigrams with add one smoothing.

    Every text passes through normalise() with the classifier's stoplist, so no caller can
    hand it raw text. Class priors are empirical. Tokens outside the training vocabulary are
    ignored at prediction time. Ties resolve to the label seen first in training.
    """

    def __init__(self, stoplist: frozenset[str]) -> None:
        self.stoplist = stoplist
        self._docs: Counter[str] = Counter()
        self._terms: dict[str, Counter[str]] = {}
        self._totals: Counter[str] = Counter()
        self._vocabulary: frozenset[str] = frozenset()

    def _fit_tokens(self, token_lists: Sequence[list[str]], labels: Sequence[str]) -> Self:
        if not token_lists:
            raise ValueError("SurfaceClassifier.fit needs at least one text")
        docs: Counter[str] = Counter()
        terms: dict[str, Counter[str]] = {}
        for toks, label in zip(token_lists, labels, strict=True):
            docs[label] += 1
            terms.setdefault(label, Counter()).update(toks)
        self._docs = docs
        self._terms = terms
        self._totals = Counter({label: sum(counter.values()) for label, counter in terms.items()})
        self._vocabulary = frozenset(token for counter in terms.values() for token in counter)
        return self

    def fit(self, texts: Iterable[str], labels: Iterable[str]) -> Self:
        """Count unigrams per label over the normalised texts. Returns self."""
        return self._fit_tokens([normalise(t, self.stoplist).split() for t in texts], list(labels))

    def _log_likelihood(self, label: str, toks: Sequence[str]) -> float:
        counts = self._terms[label]
        denominator = self._totals[label] + len(self._vocabulary)
        return sum(
            math.log((counts[token] + 1) / denominator)
            for token in toks
            if token in self._vocabulary
        )

    def _predict_tokens(self, toks: Sequence[str]) -> str:
        if not self._docs:
            raise ValueError("SurfaceClassifier.predict called before fit")
        n_docs = sum(self._docs.values())
        best_label, best_score = "", -math.inf
        for label, count in self._docs.items():
            score = math.log(count / n_docs) + self._log_likelihood(label, toks)
            if score > best_score:
                best_label, best_score = label, score
        return best_label

    def predict(self, text: str) -> str:
        """The label with the highest posterior for the normalised text."""
        return self._predict_tokens(normalise(text, self.stoplist).split())

    def leave_one_out(self, texts: Iterable[str], labels: Iterable[str]) -> LeaveOneOutReport:
        """Refit without each text in turn and predict it. Leaves this instance untouched."""
        token_lists = [normalise(t, self.stoplist).split() for t in texts]
        label_list = list(labels)
        if len(token_lists) < 2:
            raise ValueError("leave_one_out needs at least two texts")
        correct = 0
        for held_out in range(len(token_lists)):
            fold = SurfaceClassifier(self.stoplist)._fit_tokens(
                token_lists[:held_out] + token_lists[held_out + 1 :],
                label_list[:held_out] + label_list[held_out + 1 :],
            )
            if fold._predict_tokens(token_lists[held_out]) == label_list[held_out]:
                correct += 1
        return LeaveOneOutReport(correct=correct, n=len(token_lists))


def distinctive_terms(
    texts: Iterable[str], labels: Iterable[str], stoplist: frozenset[str], top_k: int = 50
) -> dict[str, list[str]]:
    """S3 primitive: per label, up to top_k normalised unigrams by add one log odds.

    A term's score for a label is log P(term | label) minus log P(term | the other labels
    pooled), both add one smoothed over the shared vocabulary. Only a term that scores
    strictly better than the tie mass (one seen once under the label and never elsewhere,
    the score most of a small corpus shares) is eligible, and a score group that straddles
    the top_k cut is left out whole, so the list never depends on how a tie is broken. The
    report compares a label's list from the bible Samples with its list from an arm's turns
    and prints both lengths beside the Jaccard.
    """
    model = SurfaceClassifier(stoplist).fit(texts, labels)
    size = len(model._vocabulary)
    out: dict[str, list[str]] = {}
    for label in model._docs:
        own, own_total = model._terms[label], model._totals[label]
        rest: Counter[str] = Counter()
        for other, counter in model._terms.items():
            if other != label:
                rest.update(counter)
        own_den, rest_den = own_total + size, sum(rest.values()) + size
        # log P(term | rest) minus log P(term | label): most distinctive first once sorted.
        scores = {
            term: math.log((rest[term] + 1) * own_den / ((own[term] + 1) * rest_den))
            for term in model._vocabulary
        }
        # own 1, rest 0 through the same expression, so the strict comparison is exact.
        tie_mass = math.log(1 * own_den / (2 * rest_den))
        ranked = sorted((score, term) for term, score in scores.items() if score < tie_mass)
        if len(ranked) > top_k:
            boundary = ranked[top_k][0]
            ranked = [(score, term) for score, term in ranked[:top_k] if score != boundary]
        out[label] = [term for _, term in ranked]
    return out


def _has_emoji(body: str) -> bool:
    return _EMOJI_RE.search(_THUMBS_UP_RE.sub("", body)) is not None


def _over_three_lines(body: str) -> bool:
    return sum(1 for line in body.splitlines() if line.strip()) > 3


def _has_uppercase(body: str) -> bool:
    return _UPPERCASE_RE.search(body) is not None


# Bible file stem to the rule ids a turn can break, each with its check on the turn after the
# verdict line is dropped.
PERSONA_RULES: dict[str, tuple[tuple[str, Callable[[str], bool]], ...]] = {
    "marisol-mari-vance": (("emoji", _has_emoji), ("lines", _over_three_lines)),
    "mira-solheim": (("lowercase", _has_uppercase),),
}


def rule_probe(text: str, persona: str) -> tuple[str, ...]:
    """S4: ids of the persona's Style rules the text breaks, in rule order. No model call.

    persona is the bible file stem. A persona with no rules here raises KeyError, so an
    unknown persona cannot pass clean.
    """
    if persona not in PERSONA_RULES:
        raise KeyError(f"no rule probe for persona {persona!r}; known: {sorted(PERSONA_RULES)}")
    body = drop_verdict_line(text)
    return tuple(rule_id for rule_id, violated in PERSONA_RULES[persona] if violated(body))

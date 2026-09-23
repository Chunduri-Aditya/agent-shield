"""Tests for the persona_attribution eval (evals/persona_fidelity.py, evals/persona/).

Bibles are data files read from a config path, never imported from twin. The path is
evals.persona_fidelity.DEFAULT_PERSONAS_DIR, one name for the Makefile, the tasks, the
report and these tests, and PERSONAS_DIR in the environment overrides it. A missing bible
skips the test with the path in the reason; CI runs pytest with -rs so the skips print.
Expected values come from docs/EVAL_PORTFOLIO_PLAN.md (the build spec at :135-156: 5
required sections, 15 samples, 18 decisions, 20 eval questions per bible) and from literal
lines copied out of the bible files, never from the code under test.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

if TYPE_CHECKING:
    from evals.persona.bible import Bible

REQUIRED_SECTIONS = ("Identity", "Voice", "Values", "Decisions", "Eval")


@dataclass(frozen=True)
class BibleAnchors:
    filename: str
    role: str
    first_sample: str
    last_sample: str
    first_decision: tuple[str, str]
    last_decision: tuple[str, str]
    first_question: str
    last_question: str


ANCHORS = (
    BibleAnchors(
        filename="mira-solheim.md",
        role="Chief Technology Officer",
        first_sample=(
            "design looks solid. two notes: put the migration behind a flag, and write the "
            "rollback step before you write the feature. reversible or it does not ship "
            "monday. thanks, m"
        ),
        last_sample=(
            "fine to experiment on the onboarding flow all you want. the credit decision "
            "path is different. that one gets a review before it touches a real applicant."
        ),
        first_decision=(
            "D-01: Build or buy the core ledger",
            "We were launching lending and needed a ledger plus card rails quickly.",
        ),
        last_decision=(
            "D-18: Deferring a security migration",
            "A known dependency needed replacing but kept losing to feature work.",
        ),
        first_question="How do you decide whether to build or buy a piece of infrastructure?",
        last_question="What keeps you up at night?",
    ),
    BibleAnchors(
        filename="marisol-mari-vance.md",
        role="Chief Operating Officer",
        first_sample=(
            "throughput dipped at dock 4 last night. go see it before shift change and tell "
            "me what you find. owner and fix by EOD."
        ),
        last_sample=(
            "taking the COO seat. scared of the people calls, not the ops. you told me that "
            "would flip someday. it did."
        ),
        first_decision=(
            "D-01: Automating the flagship DC",
            "our busiest DC was drowning in walking time and turnover was eating us.",
        ),
        last_decision=(
            "D-18: Keeping the safety trainer in a hiring freeze",
            "the owner ordered a hiring freeze and the safety trainer seat was open.",
        ),
        first_question="Why did you automate the flagship warehouse but keep the crew?",
        last_question="What would you tell a new direct report on day one?",
    ),
)


def _bible_path(filename: str) -> Path:
    from evals.persona_fidelity import DEFAULT_PERSONAS_DIR

    path = Path(DEFAULT_PERSONAS_DIR) / filename
    if not path.is_file():
        pytest.skip(f"persona bible not found: {path} (set PERSONAS_DIR)")
    return path


def _drop_section(text: str, key: str) -> str:
    """Remove one top level section: its '# key' header through the next '# ' header."""
    pattern = re.compile(rf"^# {re.escape(key)}\n.*?(?=^# |\Z)", re.MULTILINE | re.DOTALL)
    dropped, count = pattern.subn("", text)
    assert count == 1, f"fixture error: '# {key}' not found exactly once"
    return dropped


@pytest.mark.parametrize("anchors", ANCHORS, ids=[a.filename for a in ANCHORS])
def test_load_bible_finds_required_sections(anchors: BibleAnchors, tmp_path: Path) -> None:
    from evals.persona.bible import BibleFormatError, load_bible

    path = _bible_path(anchors.filename)
    bible = load_bible(path)

    for key in REQUIRED_SECTIONS:
        assert key in bible.sections, f"missing section {key!r}"
        assert bible.sections[key].strip(), f"empty section {key!r}"
    assert anchors.role in bible.sections["Identity"]

    # 15 Voice samples, the leading channel note "(to ..., text)" stripped.
    assert len(bible.samples) == 15
    assert bible.samples[0] == anchors.first_sample
    assert bible.samples[-1] == anchors.last_sample
    for sample in bible.samples:
        assert not sample.lstrip().startswith("("), f"channel note kept: {sample[:40]!r}"

    # 18 decisions, each entry carrying its D-NN title plus its Situation line.
    assert len(bible.decision_titles) == 18
    for number, entry in enumerate(bible.decision_titles, start=1):
        assert f"D-{number:02d}" in entry, f"decision {number} out of order: {entry[:40]!r}"
    for entry, (title, situation) in (
        (bible.decision_titles[0], anchors.first_decision),
        (bible.decision_titles[-1], anchors.last_decision),
    ):
        assert title in entry
        assert situation in entry

    # 20 eval questions, question text only, no gold answer attached.
    assert len(bible.eval_questions) == 20
    assert bible.eval_questions[0] == anchors.first_question
    assert bible.eval_questions[-1] == anchors.last_question
    for question in bible.eval_questions:
        assert "Answer:" not in question

    # A bible missing any one required section is rejected, and the error names it.
    text = path.read_text(encoding="utf-8")
    for key in REQUIRED_SECTIONS:
        broken = tmp_path / f"no-{key}.md"
        broken.write_text(_drop_section(text, key), encoding="utf-8")
        with pytest.raises(BibleFormatError, match=key):
            load_bible(broken)


# Step 2: brief leakage guard.
#
# Spec (docs/EVAL_PORTFOLIO_PLAN.md:139-140 and :115-116): the guard in evals/persona/bible.py
# flags a text whose content token containment against a gold line is at or above 0.5. The
# gold lines of a bible are its Decisions titles, its Situation lines and its Eval questions.
# evals/persona/briefs.py holds 20 Brief(id, text), PB-01 to PB-20, the same set in every arm,
# and none of them is flagged.
#
# Interface these tests pin:
#   gold_lines(bible) -> list[str]             leakage references for one bible
#   find_leaks(text, references) -> list[str]  every reference whose containment with text
#                                              is at or above 0.5, in reference order
# references is generic because masking reuses the same guard against Voice samples.

BRIEF_COUNT = 20

# Threshold cases from distinct content words (no stopword, no shared stem). Candidate and
# reference have the same token count, so containment is equal in either direction.
_REF_8 = "ledger migration rollback budget forklift pallet invoice payroll"
_AT_HALF = "ledger migration rollback budget vendor compiler freight warranty"  # 4 of 8 = 0.5
_REF_9 = _REF_8 + " telemetry"
_BELOW_HALF = "ledger migration rollback budget vendor compiler freight warranty quarry"  # 4/9
_DISJOINT = "orchard glacier lantern harbor"


def test_briefs_do_not_leak_gold() -> None:
    from evals.persona.bible import find_leaks, gold_lines, load_bible
    from evals.persona.briefs import BRIEFS, Brief

    bibles = [load_bible(_bible_path(a.filename)) for a in ANCHORS]
    gold = [line for bible in bibles for line in gold_lines(bible)]

    # A clean result below is vacuous if the gold is empty or truncated. Each source the spec
    # names must be present down to the last entry of each bible: a verbatim copy of it is
    # flagged, and the hit is that line.
    for anchors in ANCHORS:
        last_title = anchors.last_decision[0].split(": ", 1)[1]
        for copied in (last_title, anchors.last_decision[1], anchors.last_question):
            hits = find_leaks(copied, gold)
            assert any(copied in hit for hit in hits), f"gold misses {copied!r}: {hits}"

    briefs = list(BRIEFS)
    assert len(briefs) == BRIEF_COUNT
    assert [b.id for b in briefs] == [f"PB-{n:02d}" for n in range(1, BRIEF_COUNT + 1)]
    assert all(isinstance(b, Brief) for b in briefs)
    texts = [b.text.strip() for b in briefs]
    assert all(texts), "empty brief"
    assert len(set(texts)) == BRIEF_COUNT, "duplicate brief text"

    leaked = {b.id: find_leaks(b.text, gold) for b in briefs}
    assert {bid: hits for bid, hits in leaked.items() if hits} == {}


def test_leakage_guard_rejects_copied_decision_title() -> None:
    from evals.persona.bible import find_leaks, gold_lines, load_bible

    mira = load_bible(_bible_path("mira-solheim.md"))
    mari = load_bible(_bible_path("marisol-mari-vance.md"))
    gold = gold_lines(mira) + gold_lines(mari)

    # A decision title copied word for word, D-NN label dropped (marisol-mari-vance.md:309).
    title = "Keeping the safety trainer in a hiring freeze"
    hits = find_leaks(title, gold)
    assert any(title in hit for hit in hits), hits

    # The same leak in the shape a brief takes: a title turned into a yes or no question
    # (mira-solheim.md:193, "D-01: Build or buy the core ledger").
    hits = find_leaks("Should we build or buy the core ledger?", gold)
    assert any("Build or buy the core ledger" in hit for hit in hits), hits

    # Threshold: containment at or above 0.5 is leakage, below it is not.
    assert find_leaks(_AT_HALF, [_REF_8]) == [_REF_8]
    assert find_leaks(_BELOW_HALF, [_REF_9]) == []
    assert find_leaks(_DISJOINT, [_REF_8, _REF_9]) == []
    # Every matching reference comes back, in reference order.
    assert find_leaks(_REF_8, [_DISJOINT, _REF_8, _REF_9]) == [_REF_8, _REF_9]


# Step 3: surface normalisation, the S0 naive Bayes baseline, the S4 rule probe.
#
# Spec (docs/EVAL_PORTFOLIO_PLAN.md:141-144 and :119): normalise() lowercases, strips emoji
# ranges and punctuation, drops every token of a stoplist built from both Style rules sections
# (quoted phrases, listed tokens and the rule prose), and drops the writer's YES/NO line (the
# solver asks for "line 1: YES or NO; then your message", docs/EVAL_PORTFOLIO_PLAN.md:118). S0 is
# multinomial naive Bayes on unigrams with add one smoothing, fit on the 30 Samples, reported as
# leave one out accuracy. S4 is a regex rule probe with no LLM: Mari never uses emoji and writes
# at most three lines, Mira lowercases in chat.
#
# Interface these tests pin:
#   style_stoplist(bibles) -> frozenset[str]   lowercase tokens read from each bible's
#                                              "## Style rules" subsection, nothing else
#   normalise(text, stoplist) -> str           whitespace separated [a-z0-9]+ tokens
#   SurfaceClassifier(stoplist)                normalises every text it sees, so no caller
#       .fit(texts, labels) -> self            can hand S0 raw text
#       .predict(text) -> label
#       .leave_one_out(texts, labels) -> report with .correct (int), .n (int), .accuracy
#   rule_probe(text, persona) -> collection of violated rule ids; persona is the bible file
#       stem; "emoji" is the id of Mari's no emoji rule; an unknown persona raises

MIRA = "mira-solheim"
MARI = "marisol-mari-vance"

# Literal Style rules lines the tell sets below are copied from. If a bible changes, this
# fails as a fixture error instead of silently testing against stale tells.
_STYLE_RULE_LINES = {
    MIRA: (
        "4. Technical shorthand is fine: repo, rollback, flag, rev, pager, ledger.",  # :32
        '7. Sign offs are minimal or absent internally; "thanks, m" at most.',  # :35
        '9. Overuses "strong opinion, weakly held", "reversible", "two way door", '
        '"own the source of truth".',  # :37
    ),
    MARI: (
        "3. Abbreviations from the floor: EOD, ETA, OT, DC, WMS, OTIF, PPE.",  # :33
        '9. Overuses "walk me through it," "what does the board show," "go see it," and '
        '"by EOD."',  # :39
        '12. Praise is specific and short: "clean pick rate last night. noticed."',  # :42
    ),
}
# Tokens of those quoted phrases, and the listed shorthand and floor abbreviations. The
# appendix names EOD, OTIF and WMS as tells S0 must strip; OTIF and WMS appear in no quote,
# so the listed tokens are part of the stoplist.
_MIRA_TELLS = frozenset(
    {"reversible", "two", "way", "door", "strong", "opinion", "weakly", "held", "own"}
    | {"source", "truth", "thanks", "m"}
)
_MIRA_LISTED = frozenset({"repo", "rollback", "flag", "rev", "pager", "ledger"})
_MARI_TELLS = frozenset(
    {"walk", "me", "through", "it", "go", "see", "by", "eod", "board", "show", "clean"}
    | {"pick", "noticed"}
)
_MARI_LISTED = frozenset({"eod", "eta", "ot", "dc", "wms", "otif", "ppe"})
_ALL_TELLS = _MIRA_TELLS | _MIRA_LISTED | _MARI_TELLS | _MARI_LISTED
# Content words of the Samples found in no token of either Style rules section, so no reading
# of the stoplist spec removes them. "productivity" is quoted inside Mira Sample 9
# (mira-solheim.md:69): a quote in a Sample, not in Style rules, so it must survive.
_SURVIVORS = {
    MIRA: frozenset({"design", "solid", "migration", "monday", "vendor", "productivity"}),
    MARI: frozenset({"forklift", "freezer", "storm"}),
}
# Emoji from the blocks a writer model emits: Emoticons, Transport and Map, Misc Symbols and
# Pictographs, Supplemental Symbols and Pictographs, Dingbats. Thumbs up is kept apart: Mari's
# rule 4 allows "a rare thumbs up" (marisol-mari-vance.md:34), the plan says she never uses
# emoji, so the probe's thumbs up verdict is left unpinned.
_UPSIDE_DOWN_FACE = "\U0001f643"
_EMOJI = (_UPSIDE_DOWN_FACE, "\U0001f680", "\U0001f389", "\U0001f972", "\u2705")
_THUMBS_UP_SKIN_TONE = "\U0001f44d\U0001f3fd"
_EM_DASH, _CURLY_APOSTROPHE, _CURLY_OPEN, _CURLY_CLOSE = "\u2014", "\u2019", "\u201c", "\u201d"
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _persona_bibles() -> dict[str, Bible]:
    from evals.persona.bible import load_bible

    return {stem: load_bible(_bible_path(f"{stem}.md")) for stem in (MIRA, MARI)}


def test_normalise_strips_case_emoji_punctuation_and_style_tokens() -> None:
    from evals.persona.surface import normalise, style_stoplist

    for stem, lines in _STYLE_RULE_LINES.items():
        text = _bible_path(f"{stem}.md").read_text(encoding="utf-8")
        for line in lines:
            assert line in text, f"fixture error: {stem} no longer carries {line!r}"

    bibles = _persona_bibles()
    stoplist = style_stoplist(bibles.values())

    # The stoplist holds every tell, holds no survivor, and is read from the bibles passed in.
    assert stoplist >= _ALL_TELLS, sorted(_ALL_TELLS - stoplist)
    survivors = _SURVIVORS[MIRA] | _SURVIVORS[MARI]
    assert not survivors & stoplist, sorted(survivors & stoplist)
    mira_only = style_stoplist([bibles[MIRA]])
    mari_only = style_stoplist([bibles[MARI]])
    assert "reversible" in mira_only and "otif" not in mira_only
    assert "otif" in mari_only and "reversible" not in mari_only

    # One writer reply carrying every surface tell at once: verdict line, capitals, emoji,
    # curly quotes, an em dash, both personas' catchphrases and abbreviations.
    noisy = (
        "YES\n"
        f"Design looks SOLID {_UPSIDE_DOWN_FACE} {_EM_DASH} put the Migration behind a flag; "
        f"it{_CURLY_APOSTROPHE}s reversible, a two way door! Walk me through it by EOD: OTIF, "
        f"WMS {' '.join(_EMOJI)} {_CURLY_OPEN}Monday{_CURLY_CLOSE} {_THUMBS_UP_SKIN_TONE} "
        "thanks, m"
    )
    tokens = normalise(noisy, stoplist).split()
    assert all(_TOKEN_RE.fullmatch(t) for t in tokens), tokens
    assert not set(tokens) & _ALL_TELLS, sorted(set(tokens) & _ALL_TELLS)
    assert {"design", "solid", "migration", "monday"} <= set(tokens), tokens
    # "yes" is in no Style rules token, so its absence here is the verdict line drop.
    assert "yes" not in tokens, tokens

    # Only a bare verdict line goes. "no" is also an unquoted word in both Style rules
    # sections, so the YES cases are the ones that prove the drop.
    assert normalise("No.\nmigration monday", stoplist).split() == ["migration", "monday"]
    assert normalise("YES\nyes migration", stoplist).split() == ["yes", "migration"]
    assert normalise("design migration\nmonday", stoplist).split() == [
        "design",
        "migration",
        "monday",
    ]
    # Mira Sample 4 opens with "yes to the launch" (mira-solheim.md:54): a first line that
    # starts with a verdict word but says more is content, not the verdict line.
    sample_4 = bibles[MIRA].samples[3]
    assert sample_4.startswith("yes to the launch"), "fixture error: Mira Sample 4 moved"
    assert {"yes", "launch", "rushing"} <= set(normalise(sample_4, stoplist).split())

    # All 30 Samples: lowercase alphanumeric tokens only, no tell left, content kept.
    for stem, bible in bibles.items():
        corpus: set[str] = set()
        for sample in bible.samples:
            sample_tokens = normalise(sample, stoplist).split()
            assert all(_TOKEN_RE.fullmatch(t) for t in sample_tokens), (stem, sample_tokens)
            assert not set(sample_tokens) & _ALL_TELLS, (stem, sample[:40])
            corpus.update(sample_tokens)
        assert _SURVIVORS[stem] <= corpus, (stem, sorted(_SURVIVORS[stem] - corpus))


# Tells made only of stoplist tokens, case, punctuation and emoji: after normalisation they
# are nothing, so appending them cannot move an S0 prediction.
_MARI_TELL_TEXT = " Walk me through it, go see it, by EOD. Noticed! OTIF WMS ETA PPE"
_MIRA_TELL_TEXT = (
    " Reversible, two way door; strong opinion, weakly held. Own the source of truth "
    f"{_UPSIDE_DOWN_FACE} thanks, m"
)


def test_surface_classifier_loo_accuracy_reported() -> None:
    from evals.persona.surface import SurfaceClassifier, style_stoplist

    # Add one smoothing on a multinomial model. One text per class, vocabulary {pallet,
    # quarry}: P(pallet|a) = (1+1)/(1+2) = 2/3, P(pallet|b) = (4+1)/(5+2) = 5/7, so b.
    # Unsmoothed MLE says a (1 against 4/5), Lidstone 0.1 says a, Lidstone 0.5 ties at 3/4,
    # Bernoulli naive Bayes with add one says a (4/9 against 2/9).
    toy = SurfaceClassifier(frozenset()).fit(
        ["pallet", "pallet pallet pallet pallet quarry"], ["a", "b"]
    )
    assert toy.predict("pallet") == "b"

    # Leave one out holds each text out of its own fit. Fit on all four, every text comes back
    # with its own label; held out, each "a" text is outvoted by the two "b" texts that carry
    # its word, and each "b" text keeps its label through "rivet". So 2 of 4, under add one,
    # MLE, Lidstone 0.1, 0.5 or 2, and empirical or uniform priors alike.
    texts = [
        "pallet pallet pallet pallet",
        "quarry quarry quarry quarry",
        "pallet quarry rivet rivet",
        "pallet quarry rivet rivet",
    ]
    labels = ["a", "a", "b", "b"]
    fit_on_all = SurfaceClassifier(frozenset()).fit(texts, labels)
    assert [fit_on_all.predict(t) for t in texts] == labels
    loo = SurfaceClassifier(frozenset()).leave_one_out(texts, labels)
    assert (loo.correct, loo.n) == (2, 4)
    assert loo.accuracy == pytest.approx(0.5)

    # The reported S0 number: 30 Samples, 15 per persona, labelled by bible file stem. Pinned at
    # the shipped stoplist's value (docs/EVAL_PORTFOLIO_PLAN.md:141-144: no stoplist 17/30,
    # quoted plus listed tells only 17/30, every Style rules token 15/30), so a stoplist change
    # shows here instead of moving the kill number "S0 at or above S1" silently.
    bibles = _persona_bibles()
    stoplist = style_stoplist(bibles.values())
    samples = [s for bible in bibles.values() for s in bible.samples]
    stems = [stem for stem, bible in bibles.items() for _ in bible.samples]
    assert len(samples) == 30 and stems.count(MIRA) == stems.count(MARI) == 15
    report = SurfaceClassifier(stoplist).leave_one_out(samples, stems)
    assert (report.correct, report.n) == (15, 30), report
    assert report.accuracy == pytest.approx(0.5)

    # S0 reads normalised text only. Five copies of the other persona's tells, or capitals,
    # cannot move any prediction.
    s0 = SurfaceClassifier(stoplist).fit(samples, stems)
    for sample, stem in zip(samples, stems, strict=True):
        before = s0.predict(sample)
        tells = _MARI_TELL_TEXT if stem == MIRA else _MIRA_TELL_TEXT
        assert s0.predict(sample + tells * 5) == before, (stem, sample[:40])
        assert s0.predict(sample.upper()) == before, (stem, sample[:40])


def _reverse_alphabet(texts: list[str]) -> tuple[list[str], dict[str, str]]:
    """Rename every token so alphabetical order reverses; returns the texts and the way back."""
    vocabulary = sorted({token for text in texts for token in text.split()})
    forward = {token: f"t{len(vocabulary) - i:03d}" for i, token in enumerate(vocabulary)}
    assert sorted(forward.values(), reverse=True) == [forward[t] for t in vocabulary]
    renamed = [" ".join(forward[token] for token in text.split()) for text in texts]
    return renamed, {new: old for old, new in forward.items()}


def test_distinctive_terms_ignore_alphabetical_tie_break() -> None:
    from evals.persona.surface import distinctive_terms, normalise, style_stoplist

    # Add one log odds, label a: alpha own 3 rest 0, beta and delta own 1 rest 0 (the tie
    # mass), gamma own 1 rest 1; label b mirrors it with omega, psi, chi. Before the 2026-09-23
    # review the 50 term lists were filled from the tie mass in alphabetical order, so the
    # S3 Jaccard measured spelling; only a term strictly better than the tie mass is eligible.
    texts = ["alpha alpha beta gamma", "alpha delta", "omega omega psi", "omega chi gamma"]
    labels = ["a", "a", "b", "b"]
    assert distinctive_terms(texts, labels, frozenset()) == {"a": ["alpha"], "b": ["omega"]}

    # A score group straddling the top_k cut is left out whole rather than split by spelling:
    # alpha, beta and gamma tie above the tie mass (delta), so a cut at 2 keeps none of them.
    tied = ["alpha alpha beta beta gamma gamma delta", "omega omega"]
    tied_labels = ["a", "b"]
    assert distinctive_terms(tied, tied_labels, frozenset(), top_k=3)["a"] == [
        "alpha",
        "beta",
        "gamma",
    ]
    assert distinctive_terms(tied, tied_labels, frozenset(), top_k=2)["a"] == []

    # Reversing the alphabet leaves every list the same set of terms.
    for corpus, corpus_labels, top_k in ((texts, labels, 50), (tied, tied_labels, 2)):
        expected = distinctive_terms(corpus, corpus_labels, frozenset(), top_k=top_k)
        renamed, back = _reverse_alphabet(corpus)
        reversed_out = distinctive_terms(renamed, corpus_labels, frozenset(), top_k=top_k)
        got = {label: sorted(back[t] for t in terms) for label, terms in reversed_out.items()}
        assert got == {label: sorted(terms) for label, terms in expected.items()}

    # The real thing: both bible lists are non empty and short of 50 (only terms above the tie
    # mass), and the reversed alphabet returns the same sets.
    bibles = _persona_bibles()
    stoplist = style_stoplist(bibles.values())
    samples = [s for bible in bibles.values() for s in bible.samples]
    stems = [stem for stem, bible in bibles.items() for _ in bible.samples]
    real = distinctive_terms(samples, stems, stoplist)
    assert set(real) == {MIRA, MARI} and all(real[stem] for stem in real), real
    assert all(len(real[stem]) < 50 for stem in real), {s: len(t) for s, t in real.items()}
    renamed, back = _reverse_alphabet([normalise(s, stoplist) for s in samples])
    reversed_real = distinctive_terms(renamed, stems, frozenset())
    for stem in real:
        assert sorted(back[t] for t in reversed_real[stem]) == sorted(real[stem]), stem


def test_rule_probe_flags_emoji_for_mari() -> None:
    from evals.persona.surface import rule_probe

    bibles = _persona_bibles()

    # Deny: any emoji in a Mari reply breaks her rule.
    for emoji in _EMOJI:
        assert "emoji" in rule_probe(f"NO\nowner and date by EOD {emoji}", MARI), repr(emoji)

    # Real text: Mira Sample 14 carries her upside down face (mira-solheim.md:84). Under
    # Mari's rules it is an emoji violation; under Mira's, whose rule 5 allows that one
    # emoji, it is not.
    sample_14 = bibles[MIRA].samples[13]
    assert _UPSIDE_DOWN_FACE in sample_14, "fixture error: Mira Sample 14 moved"
    assert "emoji" in rule_probe(sample_14, MARI)
    assert "emoji" not in rule_probe(sample_14, MIRA)

    # Allow: none of Mari's own 15 Samples has an emoji, so none is flagged for one.
    for sample in bibles[MARI].samples:
        assert "emoji" not in rule_probe(sample, MARI), sample[:40]
    assert "emoji" not in rule_probe("NO\nowner and date by EOD.", MARI)

    # Mari's rule 1, at most three lines: deny at four non empty lines after the verdict line,
    # allow at three, blank lines not counted, and none of her 15 one line Samples flagged.
    assert "lines" in rule_probe("NO\none\ntwo\nthree\nfour", MARI)
    assert "lines" not in rule_probe("NO\none\ntwo\nthree", MARI)
    assert "lines" not in rule_probe("NO\none\n\ntwo\n\nthree", MARI)
    for sample in bibles[MARI].samples:
        assert "lines" not in rule_probe(sample, MARI), sample[:40]

    # Mira's rule 1, lowercase: deny on a capital in the body, allow on lowercase, the verdict
    # line's capitals not counted, and none of her 15 Samples flagged (all lowercase as written).
    assert "lowercase" in rule_probe("NO\nShip It", MIRA)
    assert "lowercase" not in rule_probe("NO\nship it", MIRA)
    assert "lowercase" not in rule_probe("YES\nship it monday", MIRA)
    for sample in bibles[MIRA].samples:
        assert "lowercase" not in rule_probe(sample, MIRA), sample[:40]

    # A persona with no rules is an error, not a clean pass.
    with pytest.raises((KeyError, ValueError)):
        rule_probe("owner and date by EOD.", "no-such-persona")


# Step 4: the S1 judge. Parser, prompt, both guide orders, dict score.
#
# Spec (docs/EVAL_PORTFOLIO_PLAN.md:145-151): the judge prompt holds the two personas' Style rules
# blocks in fenced delimiters plus the masked, name stripped completion, and says "Reply with
# exactly one letter: A or B"; temperature 0 via GenerateConfig; the judge is resolved with
# get_model inside score(). Both guide orders run per item; an attribution counts only when both
# orders agree, and disagreement is recorded as order_flip, never as wrong. The parser drops any
# <think>...</think> block, takes the first non empty line, and accepts it only as a whole verdict
# in the bare, parenthesised, dotted, **A** or \boxed{A} form (docs/EVAL_PORTFOLIO_PLAN.md:19-22,
# A1). The score value is a dict: correct (1 only when both orders agree and match the gold
# persona), order_flip, malformed, judge_error (exception message kept in metadata). Nothing is
# swallowed: every item returns a score carrying correct, so the correct denominator stays n.
#
# Interface these tests pin (evals/persona/judge.py):
#   parse_verdict(reply) -> "A" | "B" | None      None is malformed
#   judge_attribution(judge_model=..., personas_dir=...) -> Scorer
#       judge_model   a model name for get_model(); the tests register a fake ModelAPI under
#                     "persona_fake_judge", so no network model is ever reached
#       personas_dir  directory of <stem>.md bibles; the guides are read from these files
#       target.text   the gold persona stem; state.metadata["other"] is the other persona's stem
#       score.value   exactly {"correct", "order_flip", "malformed", "judge_error"}, each 0 or 1
#
# The fake judge knows no persona and never sees the gold. It answers from the prompt alone:
# "oracle" picks whichever guide carries Mira's Style rules, so the letter it returns depends
# only on where judge.py placed that guide, and the persona it names depends only on which bible
# file those rules came from.

if TYPE_CHECKING:
    from inspect_ai.scorer import Score

_FAKE_JUDGE_API = "persona_fake_judge"
_FAKE_JUDGE_BEHAVIOURS = frozenset(
    {"oracle", "oracle_think", "always_a", "always_b", "prose", "prose_half", "raise"}
    | {"raise_half"}
)
# One Style rules line per bible, found once in its own file and never in the other.
_MIRA_RULE = 'Overuses "strong opinion, weakly held"'  # mira-solheim.md:37, rule 9
_MARI_RULE = "Abbreviations from the floor"  # marisol-mari-vance.md:33, rule 3
_REPLY_INSTRUCTION = "Reply with exactly one letter: A or B"
_PERSONA_NAME_RE = re.compile(r"\b(?:mira|solheim|marisol|mari|vance)\b", re.IGNORECASE)
_JUDGE_DOWN = "fake judge down: connection refused"
_SCORE_KEYS = frozenset({"correct", "order_flip", "malformed", "judge_error"})
_AGREE_RIGHT = {"correct": 1, "order_flip": 0, "malformed": 0, "judge_error": 0}
_AGREE_WRONG = {"correct": 0, "order_flip": 0, "malformed": 0, "judge_error": 0}

# A writer reply in Mira's voice that names both personas and signs off with her initial.
_MIRA_VOICED_REPLY = (
    "NO\n"
    "not this quarter. the vendor rollback path is untested, so this is not a two way door.\n"
    "run the restore drill friday, loop in mari vance on the dock cutover, revisit monday.\n"
    "thanks, m\n"
    "Mira Solheim"
)
_REPLY_PROBE = "run the restore drill friday"  # present in the prompt only if the reply got there


@dataclass(frozen=True)
class JudgeCall:
    prompt: str
    temperature: float | None


_JUDGE_CALLS: list[JudgeCall] = []
_FAKE_JUDGE_READY: list[bool] = []


def _fake_reply(behaviour: str, prompt: str) -> str:
    """What the fake judge answers, read off the prompt alone."""
    mira_at, mari_at = prompt.find(_MIRA_RULE), prompt.find(_MARI_RULE)
    if mira_at < 0 or mari_at < 0:
        return "?"  # malformed on purpose; the prompt assertions name what went missing
    mira_letter, mari_letter = ("A", "B") if mira_at < mari_at else ("B", "A")
    mira_first = mira_letter == "A"
    if behaviour == "oracle":
        return mira_letter
    if behaviour == "oracle_think":  # same verdict after reasoning that ends on the other letter
        return f"<think>\n{mari_letter}\n</think>\n\n{mira_letter}"
    if behaviour in ("always_a", "always_b"):  # pure position bias
        return behaviour[-1].upper()
    if behaviour == "prose":
        return f"I think the text matches guide {mira_letter}."
    if behaviour == "prose_half":  # a verdict in one order, prose in the other
        return mira_letter if mira_first else "Both guides fit this text."
    if behaviour == "raise" or (behaviour == "raise_half" and not mira_first):
        raise RuntimeError(_JUDGE_DOWN)
    if behaviour == "raise_half":
        return mira_letter
    raise ValueError(f"unknown fake judge behaviour {behaviour!r}")


def _register_fake_judge() -> None:
    """Register the fake judge once, so "persona_fake_judge/<behaviour>" resolves through
    get_model() by the same registry path as "ollama/llama3.1:8b"."""
    if _FAKE_JUDGE_READY:
        return
    from inspect_ai.model import ChatMessage, GenerateConfig, ModelAPI, ModelOutput, modelapi
    from inspect_ai.tool import ToolChoice, ToolInfo

    @modelapi(name=_FAKE_JUDGE_API)
    class _FakeJudgeAPI(ModelAPI):
        def __init__(
            self,
            model_name: str,
            base_url: str | None = None,
            api_key: str | None = None,
            config: GenerateConfig | None = None,
            **model_args: object,
        ) -> None:
            super().__init__(model_name, base_url, api_key, [], config or GenerateConfig())

        async def generate(
            self,
            input: list[ChatMessage],
            tools: list[ToolInfo],
            tool_choice: ToolChoice,
            config: GenerateConfig,
        ) -> ModelOutput:
            prompt = "\n".join(message.text for message in input)
            _JUDGE_CALLS.append(JudgeCall(prompt, config.temperature))
            reply = _fake_reply(self.model_name, prompt)
            return ModelOutput.from_content(model=self.model_name, content=reply)

    _FAKE_JUDGE_READY.append(True)


async def _judge(
    behaviour: str, gold: str, other: str, personas_dir: Path
) -> tuple[Score, list[JudgeCall]]:
    """Score _MIRA_VOICED_REPLY with judge_attribution; return the score and every judge call."""
    from inspect_ai.model import ModelName, ModelOutput
    from inspect_ai.scorer import Target
    from inspect_ai.solver import TaskState

    from evals.persona.judge import judge_attribution

    assert behaviour in _FAKE_JUDGE_BEHAVIOURS, f"fixture error: {behaviour!r}"
    _register_fake_judge()
    _JUDGE_CALLS.clear()
    scorer = judge_attribution(
        judge_model=f"{_FAKE_JUDGE_API}/{behaviour}", personas_dir=str(personas_dir)
    )
    state = TaskState(
        model=ModelName("mockllm/model"),
        sample_id=f"PB-01:{gold}",
        epoch=1,
        input="Should we sign a three year contract with a single vendor?",
        messages=[],
        output=ModelOutput.from_content(model="mockllm/model", content=_MIRA_VOICED_REPLY),
        metadata={"other": other},
    )
    score = await scorer(state, Target(gold))
    assert score is not None, "judge_attribution returned no score"
    return score, list(_JUDGE_CALLS)


def _assert_blind_prompts_in_both_orders(calls: list[JudgeCall], samples: list[str]) -> None:
    """One call per guide order. Each prompt holds both Style rules once, the instruction and
    the reply with every persona name masked, and no Voice Sample; temperature 0."""
    assert len(calls) == 2, f"expected one judge call per guide order, got {len(calls)}"
    for call in calls:
        prompt = call.prompt
        assert prompt.count(_MIRA_RULE) == 1, "Mira's Style rules not in the prompt exactly once"
        assert prompt.count(_MARI_RULE) == 1, "Mari's Style rules not in the prompt exactly once"
        assert _REPLY_INSTRUCTION in prompt, "judge instruction missing"
        assert _REPLY_PROBE in prompt, "the writer reply never reached the judge"
        assert not _PERSONA_NAME_RE.search(prompt), _PERSONA_NAME_RE.findall(prompt)
        leaked = [sample[:40] for sample in samples if sample[:40] in prompt]
        assert not leaked, f"Voice Samples in the judge prompt: {leaked}"
        assert call.temperature == 0, f"judge temperature {call.temperature!r}, want 0"
    mira_first = sorted(c.prompt.find(_MIRA_RULE) < c.prompt.find(_MARI_RULE) for c in calls)
    assert mira_first == [False, True], "both calls put the guides in the same order"


_VOICE_RE = re.compile(r"^# Voice\n.*?(?=^# |\Z)", re.MULTILINE | re.DOTALL)


def _write_pair(directory: Path, *, swap_voice: bool) -> Path:
    """Copy both bibles into directory; with swap_voice each takes the other's '# Voice'."""
    texts = {stem: _bible_path(f"{stem}.md").read_text(encoding="utf-8") for stem in (MIRA, MARI)}
    voices: dict[str, str] = {}
    for stem, text in texts.items():
        found = _VOICE_RE.findall(text)
        assert len(found) == 1, f"fixture error: {stem} has {len(found)} '# Voice' sections"
        voices[stem] = found[0]
    directory.mkdir()
    for stem, text in texts.items():
        donor = (MARI if stem == MIRA else MIRA) if swap_voice else stem
        swapped = text.replace(voices[stem], voices[donor], 1)
        (directory / f"{stem}.md").write_text(swapped, encoding="utf-8")
    return directory


def test_judge_parser_anchors_first_letter() -> None:
    from evals.persona.judge import parse_verdict

    verdicts = {
        "A": "A",
        "B": "B",
        "(A)": "A",
        "B.": "B",
        "(B).": "B",
        "\n\nB\n": "B",  # first non empty line
        "A\nB": "A",  # only the first line counts
        "B\nguide A has the lowercase rule, but the numbers say B": "B",
        "<think>\nA\n</think>\nB": "B",  # reasoning dropped before the first line is read
        "<think>\n\n</think>\n\nA": "A",  # an empty reasoning block
        "<think>guide A? the text is dry and lowercase.\nA\n</think>\n\nB": "B",
        "**A**": "A",  # A1: paired bold wrapper
        "**B**.": "B",  # A1: paired bold wrapper, trailing period
        r"\boxed{A}": "A",  # A1: paired boxed wrapper
        r"\boxed{B}.": "B",  # A1: paired boxed wrapper, trailing period
        "<think>\nB\n</think>\n" + r"\boxed{A}": "A",  # A1: reasoning dropped, then boxed
    }
    for reply, expected in verdicts.items():
        assert parse_verdict(reply) == expected, repr(reply)


@pytest.mark.asyncio
async def test_judge_parser_tags_malformed_not_swallowed() -> None:
    from evals.persona.judge import parse_verdict

    malformed = (
        "",
        "\n  \n",
        "A because the reply is lowercase",  # anchored on the whole line, not a search
        "Answer: B",
        "Guide A",
        "The answer is B.",
        "**a**",  # lowercase inside a wrapper
        r"\boxed{AB}",  # two letters inside a wrapper
        r"\boxed{A} B",  # wrapped letter then a second letter
        "**A** or B",  # wrapped letter then prose
        "boxed{A}",  # unescaped wrapper
        "**A",  # unpaired wrapper
        "A**",  # unpaired wrapper, closing half only
        r"\boxed{A",  # unpaired boxed wrapper
        r"\boxed{a}",  # lowercase inside the boxed wrapper
        "**A**B",  # wrapped letter then a second letter, no space
        "A or B",
        "AB",
        "a",  # the spec regex is case sensitive
        "C",
        "<think>\nA\n</think>",  # nothing after the reasoning
        "<think>\nA",  # reasoning cut off before it closed: no verdict line
        "<think>\nB\n</think>\nI would say A",
    )
    for reply in malformed:
        assert parse_verdict(reply) is None, repr(reply)

    personas_dir = _bible_path(f"{MIRA}.md").parent
    _bible_path(f"{MARI}.md")

    # Malformed in both orders: tagged, scored 0, kept in the correct denominator.
    score, calls = await _judge("prose", MIRA, MARI, personas_dir)
    assert len(calls) == 2, len(calls)
    assert score.value == {"correct": 0, "order_flip": 0, "malformed": 1, "judge_error": 0}

    # A verdict in one order and prose in the other is not agreement.
    score, _ = await _judge("prose_half", MIRA, MARI, personas_dir)
    value = score.value
    assert isinstance(value, dict) and set(value) == _SCORE_KEYS, value
    assert (value["correct"], value["malformed"], value["judge_error"]) == (0, 1, 0), value

    # The judge raised: tagged judge_error, the message kept in metadata, still scored.
    score, _ = await _judge("raise", MIRA, MARI, personas_dir)
    assert score.value == {"correct": 0, "order_flip": 0, "malformed": 0, "judge_error": 1}
    assert _JUDGE_DOWN in str(score.metadata), score.metadata

    # A verdict in one order and an exception in the other is not agreement either.
    score, _ = await _judge("raise_half", MIRA, MARI, personas_dir)
    value = score.value
    assert isinstance(value, dict) and set(value) == _SCORE_KEYS, value
    assert (value["correct"], value["malformed"], value["judge_error"]) == (0, 0, 1), value


@pytest.mark.asyncio
async def test_attribution_scorer_flips_when_voice_sections_swap(tmp_path: Path) -> None:
    from evals.persona.bible import load_bible

    original = _write_pair(tmp_path / "original", swap_voice=False)
    swapped = _write_pair(tmp_path / "swapped", swap_voice=True)
    # Fixture: the swap moved each bible's Style rules and left its Identity in place.
    for stem, own, other_rule in ((MIRA, _MIRA_RULE, _MARI_RULE), (MARI, _MARI_RULE, _MIRA_RULE)):
        swapped_text = (swapped / f"{stem}.md").read_text(encoding="utf-8")
        assert own in (original / f"{stem}.md").read_text(encoding="utf-8")
        assert own not in swapped_text and other_rule in swapped_text, f"fixture error: {stem}"
    assert "Name: Mira Solheim" in (swapped / f"{MIRA}.md").read_text(encoding="utf-8")
    samples = [s for stem in (MIRA, MARI) for s in load_bible(original / f"{stem}.md").samples]
    assert len(samples) == 30

    # The oracle always picks the guide holding Mira's Style rules. With the bibles as written
    # that guide is Mira's; with the Voice sections swapped the same rules sit in Mari's file,
    # so the same verdict now names Mari, in both guide orders. oracle_think gives the same
    # verdict after a reasoning block whose last line is the opposite letter.
    # Mutation (plan step 4): parse_verdict returning "A" always turns the two agreeing
    # verdicts into an order_flip, so the first expectation below goes red.
    for behaviour in ("oracle", "oracle_think"):
        for personas_dir, gold, other, expected in (
            (original, MIRA, MARI, _AGREE_RIGHT),
            (swapped, MIRA, MARI, _AGREE_WRONG),
            (original, MARI, MIRA, _AGREE_WRONG),
            (swapped, MARI, MIRA, _AGREE_RIGHT),
        ):
            score, calls = await _judge(behaviour, gold, other, personas_dir)
            _assert_blind_prompts_in_both_orders(calls, samples)
            assert score.value == expected, (behaviour, personas_dir.name, gold, score.value)


@pytest.mark.asyncio
async def test_order_disagreement_counts_as_flip_not_wrong() -> None:
    personas_dir = _bible_path(f"{MIRA}.md").parent
    _bible_path(f"{MARI}.md")

    # A judge that answers by position gives the same letter in both orders, so its two verdicts
    # name different personas (the plan cites Panickssery: Llama flips 89% of pairwise
    # verdicts). That is a flip, whichever persona is gold and whichever letter it favours.
    flip = {"correct": 0, "order_flip": 1, "malformed": 0, "judge_error": 0}
    for behaviour in ("always_a", "always_b"):
        for gold, other in ((MIRA, MARI), (MARI, MIRA)):
            score, calls = await _judge(behaviour, gold, other, personas_dir)
            assert len(calls) == 2, (behaviour, gold, len(calls))
            assert score.value == flip, (behaviour, gold, score.value)

    # Agreement is never a flip: agreeing on the other persona is wrong, on the gold correct.
    score, _ = await _judge("oracle", MARI, MIRA, personas_dir)
    assert score.value == _AGREE_WRONG, score.value
    score, _ = await _judge("oracle", MIRA, MARI, personas_dir)
    assert score.value == _AGREE_RIGHT, score.value


# Sentences of the three bibles in the same folder that are neither Mira's nor Mari's: benign
# text the copied sentence guard must mostly let through. Ablated (containment 0.5 alone, no
# minimum shared token count, the shipped guard until the 2026-09-23 review): 35 of 129
# sentences dropped, 0.271. The ceiling below sits under that; the verifier records the real
# rate in this comment once measured, and the ceiling then moves between the two.
_OTHER_PERSONAS = ("dana-kessler", "ellen-marchetti", "nadia-belrose")
_BENIGN_DROP_CEILING = 0.10
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
# Mira Sample 1 (mira-solheim.md:45): eight content tokens, a copy the guard must drop.
_COPIED_SAMPLE_SENTENCE = (
    "put the migration behind a flag, and write the rollback step before you write the feature."
)


def test_mask_completion_drops_copies_not_short_sentences() -> None:
    from evals.persona.bible import content_tokens, load_bible
    from evals.persona.judge import MIN_SHARED_TOKENS, mask_completion

    bibles = _persona_bibles()
    pool = list(bibles.values())

    # Deny: a Voice Sample sentence with at least MIN_SHARED_TOKENS content tokens goes, and the
    # short sentence beside it stays, on its own line.
    assert _COPIED_SAMPLE_SENTENCE in bibles[MIRA].samples[0], "fixture error: Mira Sample 1 moved"
    assert len(content_tokens(_COPIED_SAMPLE_SENTENCE)) >= MIN_SHARED_TOKENS
    masked = mask_completion(f"NO\n{_COPIED_SAMPLE_SENTENCE}\nwe should wait.", pool)
    assert _COPIED_SAMPLE_SENTENCE not in masked, masked
    assert masked == "NO\nwe should wait.", masked

    # Allow: a short generic sentence shares one word with some Sample or gold line ("quarter",
    # "wait", "short") and used to go on containment 1.0; below the minimum it cannot be a copy.
    for short in ("not this quarter.", "we should wait.", "renew it, but short.", "thanks."):
        assert mask_completion(short, pool) == short, short
    masked = mask_completion(_MIRA_VOICED_REPLY, pool)
    assert _REPLY_PROBE in masked and "not this quarter." in masked, masked
    assert not _PERSONA_NAME_RE.search(masked), masked

    # Benign drop rate on the other personas' Samples, sentence by sentence.
    others = [load_bible(_bible_path(f"{stem}.md")) for stem in _OTHER_PERSONAS]
    sentences = [
        sentence
        for bible in others
        for sample in bible.samples
        for line in sample.splitlines()
        for sentence in _SENTENCE_END_RE.split(line)
        if sentence.strip()
    ]
    assert len(sentences) >= 50, len(sentences)
    dropped = [s for s in sentences if not mask_completion(s, pool).strip()]
    rate = len(dropped) / len(sentences)
    assert rate <= _BENIGN_DROP_CEILING, (f"{len(dropped)}/{len(sentences)} = {rate:.3f}", dropped)


# --- Step 5: Wilson metrics on the correct key ---------------------------------------------------
#
# Spec (plan design points; docs/EVAL_PORTFOLIO_PLAN.md:56-58): judge_attribution reports
#   {"correct": [accuracy(), wilson_low(), wilson_high(), wilson_n()], "order_flip": [mean()], ...}
# where the Wilson metrics wrap agent_shield.runtime.stats.wilson_interval (stats.py:27) and the
# copy at agent_shield/transparency_judge.py:200 does not become a third.
#
# Expected bounds are the 95% Wilson interval (z = 1.96), derived outside this repo twice: from the
# closed form, and by inverting the score test |p - pi| <= z sqrt(pi (1 - pi) / n) with bisection;
# the two agree to 1e-16. Four are published in README.md:79-83.

if TYPE_CHECKING:
    from inspect_ai.scorer import Metric, SampleScore, Value

_WILSON_95 = {  # (successes, n): (low, high)
    (3, 20): (0.052368, 0.360423),  # README.md:80, TR=0.150 CI [0.052, 0.360]
    (1, 20): (0.008881, 0.236136),  # README.md:81, ASR=0.050 CI [0.009, 0.236]
    (0, 20): (0.0, 0.161130),  # README.md:83, upper bound 0.161
    (0, 5): (0.0, 0.434491),  # README.md:82-83, upper bound 0.434
    (5, 5): (0.565509, 1.0),
    (3, 5): (0.230720, 0.882382),
    (21, 40): (0.374971, 0.670648),
    (28, 40): (0.545697, 0.819253),
    (40, 40): (0.912375, 1.0),
}
_WILSON_TOL = 5e-6  # the literals above carry six decimals
_REPO = Path(__file__).resolve().parents[1]
_WILSON_HOMES = frozenset({"agent_shield/runtime/stats.py", "agent_shield/transparency_judge.py"})


def _correct_scores(successes: int, n: int) -> list[SampleScore]:
    """What Inspect hands a metric on the correct key: one 0 or 1 scalar per sample
    (inspect_ai/_eval/task/results.py:398-406 splits the dict value per key)."""
    from inspect_ai.scorer import SampleScore, Score

    return [
        SampleScore(score=Score(value=int(i < successes)), sample_id=f"PB-{i + 1:02d}")
        for i in range(n)
    ]


def _metric_value(metric: Metric, scores: list[SampleScore]) -> Value:
    """Call a metric the way Inspect does (inspect_ai/_eval/task/results.py:482-483)."""
    from inspect_ai.scorer import MetricProtocol

    return cast(MetricProtocol, metric)(scores)


def _wilson_code(root: Path) -> tuple[set[str], set[str]]:
    """Under root: files in agent_shield/, evals/, scripts/ defining wilson_interval, and files
    in the persona eval that take a square root (an interval computed in place, any name)."""
    import ast

    defines: set[str] = set()
    square_roots: set[str] = set()
    for top in ("agent_shield", "evals", "scripts"):
        for path in sorted((root / top).rglob("*.py")):
            rel = path.relative_to(root).as_posix()
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=rel)):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and (
                    node.name == "wilson_interval"
                ):
                    defines.add(rel)
                if not rel.startswith("evals/persona"):
                    continue
                func = node.func if isinstance(node, ast.Call) else None
                called = getattr(func, "attr", getattr(func, "id", ""))
                half_power = (
                    isinstance(node, ast.BinOp)
                    and isinstance(node.op, ast.Pow)
                    and isinstance(node.right, ast.Constant)
                    and node.right.value == 0.5
                )
                if called == "sqrt" or half_power:
                    square_roots.add(rel)
    return defines, square_roots


def test_wilson_metrics_match_stats_module(tmp_path: Path) -> None:
    from inspect_ai import Task
    from inspect_ai import eval as inspect_eval
    from inspect_ai.dataset import MemoryDataset, Sample

    from agent_shield.runtime.stats import wilson_interval
    from evals.persona.judge import judge_attribution, wilson_high, wilson_low, wilson_n

    # The metrics on the scalars Inspect passes them: the spec literal and stats.py agree.
    for (successes, n), (low, high) in _WILSON_95.items():
        scores = _correct_scores(successes, n)
        got = tuple(_metric_value(m(), scores) for m in (wilson_low, wilson_high, wilson_n))
        case = (successes, n, got)
        assert got[0] == pytest.approx(low, abs=_WILSON_TOL), case
        assert got[1] == pytest.approx(high, abs=_WILSON_TOL), case
        assert got[2] == n, case
        ref = wilson_interval(successes, n)
        assert got == pytest.approx((ref.low, ref.high, ref.n), abs=1e-12), (case, ref)

    # Through a real eval: registered on the correct key of judge_attribution and fed by Inspect's
    # own per key split. The oracle names Mira in both guide orders, so Mira gold scores correct
    # and Mari gold scores an agreeing wrong: 3 of 5.
    personas_dir = _bible_path(f"{MIRA}.md").parent
    _bible_path(f"{MARI}.md")
    _register_fake_judge()
    golds = (MIRA, MARI, MIRA, MARI, MIRA)
    dataset = MemoryDataset(
        [
            Sample(
                id=f"PB-{i:02d}:{gold}",
                input="Should we sign a three year contract with a single vendor?",
                target=gold,
                metadata={"other": MARI if gold == MIRA else MIRA},
            )
            for i, gold in enumerate(golds, start=1)
        ]
    )
    scorer = judge_attribution(
        judge_model=f"{_FAKE_JUDGE_API}/oracle", personas_dir=str(personas_dir)
    )
    [log] = inspect_eval(
        Task(dataset=dataset, scorer=scorer),
        model="mockllm/model",
        log_dir=str(tmp_path / "logs"),
        display="none",
    )
    assert log.status == "success", log.error
    assert log.results is not None
    metrics = {
        score.name: {name.split("/")[-1]: m.value for name, m in score.metrics.items()}
        for score in log.results.scores
    }
    assert set(metrics) == _SCORE_KEYS, metrics
    correct = metrics["correct"]
    low, high = _WILSON_95[(3, 5)]
    assert correct["accuracy"] == pytest.approx(0.6), correct
    assert correct["wilson_low"] == pytest.approx(low, abs=_WILSON_TOL), correct
    assert correct["wilson_high"] == pytest.approx(high, abs=_WILSON_TOL), correct
    assert correct["wilson_n"] == 5, correct


def test_no_third_wilson_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from agent_shield.runtime import stats
    from agent_shield.runtime.stats import WilsonInterval

    # The scan can fail: a third definition and two in place square roots planted under tmp_path.
    planted = tmp_path / "planted"
    (planted / "evals/persona").mkdir(parents=True)
    copy = "import math\n\n\ndef wilson_interval(k, n):\n    return math.sqrt(k / n)\n"
    (planted / "evals/persona/metrics.py").write_text(copy, encoding="utf-8")
    (planted / "evals/persona/judge.py").write_text("def f(v):\n    return v ** 0.5\n")
    planted_found = _wilson_code(planted)
    assert planted_found == (
        {"evals/persona/metrics.py"},
        {"evals/persona/metrics.py", "evals/persona/judge.py"},
    ), planted_found

    # The repo: wilson_interval is defined only where it already was (stats.py is found, so the
    # scan read real files) and nothing in the persona eval takes a square root.
    defines, square_roots = _wilson_code(_REPO)
    assert "agent_shield/runtime/stats.py" in defines, defines
    assert defines <= _WILSON_HOMES, f"a third wilson_interval: {sorted(defines - _WILSON_HOMES)}"
    assert not square_roots, f"the persona eval computes a square root: {sorted(square_roots)}"

    # The metrics read their bounds through stats.wilson_interval. Swap it for a sentinel at every
    # binding (stats itself, and any evals module that imported the name) and the sentinel's
    # bounds must come back; a metric carrying its own formula returns the real 3 of 5 bounds.
    from evals.persona.judge import wilson_high, wilson_low

    real = stats.wilson_interval
    calls: list[tuple[int, int]] = []

    def sentinel(successes: int, n: int, z: float = 1.96) -> WilsonInterval:
        calls.append((successes, n))
        return WilsonInterval(low=0.125, high=0.875, point=successes / n, n=n, successes=successes)

    monkeypatch.setattr(stats, "wilson_interval", sentinel)
    for name, module in list(sys.modules.items()):
        in_evals = name == "evals" or name.startswith("evals.")
        if in_evals and getattr(module, "wilson_interval", None) is real:
            monkeypatch.setattr(module, "wilson_interval", sentinel)
    scores = _correct_scores(3, 5)
    got = (_metric_value(wilson_low(), scores), _metric_value(wilson_high(), scores))
    assert got == (0.125, 0.875), (got, calls)
    assert calls and set(calls) == {(3, 5)}, calls


# --- Step 6: persona_attribution end to end on mockllm/model --------------------------------------
#
# Spec (docs/EVAL_PORTFOLIO_PLAN.md:61-65 and :113-125): @task persona_attribution(bibles=
# "on|off|swapped", personas_dir, judge_model, subset) pairs Mira Solheim with Mari Vance over the
# same 20 briefs in
# every arm, one sample per brief and gold persona: 40 samples, the correct denominator. The writer
# is single turn. Its system prompt is the gold bible's Identity, Voice, Values and Decisions
# sections (on), empty (off), or the other persona's bible with the gold label kept (swapped); its
# user turn is the brief plus "line 1: YES or NO; then your message". Scorers surface_baseline,
# judge_attribution, verdict, rule_compliance; version=1; metadata writer, judge, personas_sha256.
# Every RESULTS.md row needs revision.dirty read from the log, so the log must carry a git revision.
#
# Inspect writes no revision under pytest: inspect_ai/_util/git.py git_context() returns None while
# PYTEST_CURRENT_TEST is set, and asks git in the working directory. A control run of a bare Task
# under pytest gave revision=None with the variable set and the repo commit with it unset, so the
# test unsets it and runs from the repo root.
#
# Interface this test pins:
#   persona_attribution(bibles=..., personas_dir=..., judge_model=...) -> Task; any other bibles
#       value raises
#   sample id "<brief id>:<gold stem>", target the gold stem, metadata["other"] the other stem
#
# Expected metrics come from the judge, never from the eval. The oracle fake names Mira in both
# guide orders whatever the writer said, so exactly the 20 Mira gold samples score correct, in any
# arm. mockllm/model as judge answers "Default output from mockllm/model", malformed in both orders,
# so 0 of 40 correct, malformed on every sample, and the denominator still 40. Bounds are the 95%
# Wilson interval derived outside the repo as in step 5; (20, 40) is the chance interval
# docs/EVAL_PORTFOLIO_PLAN.md:126 publishes as [0.352, 0.648].

_WRITER_INSTRUCTION = "line 1: YES or NO; then your message"  # docs/EVAL_PORTFOLIO_PLAN.md:118
_SCORERS = frozenset({"surface_baseline", "judge_attribution", "verdict", "rule_compliance"})
_WILSON_95_N40 = {20: (0.351993, 0.648007), 0: (0.0, 0.087625)}  # successes: (low, high)
_MALFORMED_BOTH = {"correct": 0, "order_flip": 0, "malformed": 1, "judge_error": 0}
# One line from each section the writer gets: Identity (mira-solheim.md:10,
# marisol-mari-vance.md:10), Values (:90, :92), Voice Style rules (:37, :33), Voice Sample 1
# (:45, :47), Decisions D-01 title (:193, :190).
_WRITER_SEES = {
    MIRA: (
        "Name: Mira Solheim",
        "Reversibility over certainty:",
        _MIRA_RULE,
        "design looks solid. two notes: put the migration behind a flag",
        "Build or buy the core ledger",
    ),
    MARI: (
        'Name: Marisol "Mari" Vance',
        "See it yourself. I once approved a layout on paper",
        _MARI_RULE,
        "throughput dipped at dock 4 last night",
        "Automating the flagship DC",
    ),
}
# Lines the writer never gets: the Eval Q-01 question and its gold answer (mira-solheim.md:365-366,
# marisol-mari-vance.md:360-361), and the first Goals line (:347, :341), a section outside the four.
_WRITER_NEVER_SEES = {
    MIRA: (
        "How do you decide whether to build or buy a piece of infrastructure?",
        "Exit cost decides more than build cost.",
        "Finish decommissioning the last of the legacy core",
    ),
    MARI: (
        "Why did you automate the flagship warehouse but keep the crew?",
        "cutting bodies is the dumb save",
        "Get every one of the 30 DCs to a green safety board",
    ),
}
# The writer replies S0, S2 and S4 are pinned against, worked out by hand from the bibles:
#   default  "Default output from mockllm/model", mockllm's stock reply. Its one token in the
#            Sample vocabulary is "model" (Mira Sample 4, mira-solheim.md:54, "clear the model
#            review"; in no Mari Sample and in neither Style rules section), so S0 names Mira on
#            every sample. Not a bare YES or NO, so the verdict is unparsed. The capital D breaks
#            Mira's lowercase rule and nothing of Mari's (one line, no emoji).
#   mari     "YES\nforklift storm freezer.": the three _SURVIVORS[MARI] words, each in a Mari
#            Sample (marisol-mari-vance.md:68, :71) and in no Mira Sample, so S0 names Mari on
#            every sample. Verdict YES; lowercase, one line, no emoji, so no rule breaks.
# Neither reply shares four content tokens with any bible line, so masking leaves both intact.
_WRITER_REPLIES = {
    "default": "Default output from mockllm/model",
    "mari": "YES\nforklift storm freezer.",
}
_S0_NAMES = {"default": MIRA, "mari": MARI}
_VERDICTS: dict[str, tuple[str | None, dict[str, int]]] = {
    "default": (None, {"yes": 0, "unparsed": 1}),
    "mari": ("YES", {"yes": 1, "unparsed": 0}),
}


@pytest.mark.parametrize(
    ("arm", "judge", "reply"),
    [("on", "oracle", "mari"), ("off", "mockllm", "default"), ("swapped", "oracle", "default")],
)
def test_persona_attribution_end_to_end_mockllm(
    arm: str, judge: str, reply: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import shutil
    import subprocess

    from inspect_ai import eval as inspect_eval
    from inspect_ai.event import ModelEvent
    from inspect_ai.log import resolve_sample_attachments
    from inspect_ai.model import Model, ModelOutput, get_model

    from evals.persona.briefs import BRIEFS
    from evals.persona_fidelity import persona_attribution

    personas_dir = _bible_path(f"{MIRA}.md").parent
    _bible_path(f"{MARI}.md")
    if judge == "oracle":
        _register_fake_judge()
        judge_model = f"{_FAKE_JUDGE_API}/oracle"
    else:
        judge_model = "mockllm/model"
    other_of = {MIRA: MARI, MARI: MIRA}
    writer: str | Model = "mockllm/model"
    if reply != "default":
        reply_text = _WRITER_REPLIES[reply]
        writer = get_model(
            "mockllm/model",
            custom_outputs=lambda input, tools, tool_choice, config: ModelOutput.from_content(
                model="mockllm", content=reply_text
            ),
        )

    # An arm outside the three is an error, not a silent default.
    with pytest.raises((ValueError, KeyError)):
        persona_attribution(bibles="both", personas_dir=str(personas_dir), judge_model=judge_model)

    # personas_sha256 hashes the bible content, not the path: a byte for byte copy of the pair
    # hashes the same, one word changed in a Values line the writer reads hashes differently.
    def personas_sha(directory: Path) -> object:
        built = persona_attribution(
            bibles=arm, personas_dir=str(directory), judge_model=judge_model
        )
        return (built.metadata or {}).get("personas_sha256")

    copy_dir, edited_dir = tmp_path / "copy", tmp_path / "edited"
    for directory in (copy_dir, edited_dir):
        directory.mkdir()
        for stem in (MIRA, MARI):
            shutil.copyfile(personas_dir / f"{stem}.md", directory / f"{stem}.md")
    edited = edited_dir / f"{MIRA}.md"
    text = edited.read_text(encoding="utf-8")
    assert text.count("Reversibility over certainty:") == 1, "fixture error: Mira Values moved"
    edited.write_text(
        text.replace("Reversibility over certainty:", "Reversibility over comfort:"),
        encoding="utf-8",
    )
    digest = personas_sha(personas_dir)
    assert isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), digest
    assert personas_sha(copy_dir) == digest
    assert personas_sha(edited_dir) != digest

    # The run, from the repo root with the pytest marker unset so Inspect records the revision.
    monkeypatch.chdir(_REPO)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    task = persona_attribution(bibles=arm, personas_dir=str(personas_dir), judge_model=judge_model)
    [log] = inspect_eval(task, model=writer, log_dir=str(tmp_path / "logs"), display="none")
    assert log.status == "success", log.error

    # Revision present: the commit git itself reports, and a dirty flag persona_report.py can read.
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    revision = log.eval.revision
    assert revision is not None, "no git revision in the eval log"
    assert (revision.type, revision.commit) == ("git", head), revision
    assert isinstance(revision.dirty, bool), revision

    # Task identity.
    assert log.eval.task_version == 1, log.eval.task_version
    metadata = log.eval.metadata or {}
    assert {"writer", "judge", "personas_sha256"} <= set(metadata), metadata
    assert metadata["judge"] == judge_model, metadata
    assert metadata["personas_sha256"] == digest, metadata

    # 40 samples: every brief once per gold persona, labelled as the id says.
    samples = log.samples or []
    assert len(samples) == 40, len(samples)
    assert log.results is not None and log.results.completed_samples == 40, log.results
    expected_ids = {f"{b.id}:{stem}" for b in BRIEFS for stem in (MIRA, MARI)}
    assert len(expected_ids) == 40
    assert {str(s.id) for s in samples} == expected_ids
    brief_text = {b.id: b.text for b in BRIEFS}
    user_turns: dict[str, set[str]] = {}
    for sample in samples:
        brief_id, gold = str(sample.id).split(":")
        assert sample.target == gold, (sample.id, sample.target)
        assert (sample.metadata or {}).get("other") == other_of[gold], (sample.id, sample.metadata)

        # What the writer received, read off its own model call: one call per sample, and the
        # judge called once per guide order. Inspect condenses message text into
        # attachment:// references before the sample reaches the log, so resolve them first.
        calls = [
            e for e in resolve_sample_attachments(sample).events if isinstance(e, ModelEvent)
        ]
        judged = [any(_REPLY_INSTRUCTION in m.text for m in e.input) for e in calls]
        writer_calls = [e for e, is_judge in zip(calls, judged, strict=True) if not is_judge]
        assert len(writer_calls) == 1, (sample.id, len(writer_calls))
        assert sum(judged) == 2, (sample.id, sum(judged))
        sent = writer_calls[0].input
        system = "\n".join(m.text for m in sent if m.role == "system")
        user = "\n".join(m.text for m in sent if m.role != "system")

        # The user turn is the brief plus the verdict instruction and carries no persona.
        assert brief_text[brief_id] in user, (sample.id, user[:120])
        assert _WRITER_INSTRUCTION in user, (sample.id, user[:120])
        for line in _WRITER_SEES[MIRA] + _WRITER_SEES[MARI]:
            assert line not in user, (sample.id, line)
        user_turns.setdefault(brief_id, set()).add(user)

        # The system prompt by arm: the gold bible, nothing, or the other bible.
        persona = {"on": gold, "off": None, "swapped": other_of[gold]}[arm]
        if persona is None:
            assert not system.strip(), (sample.id, system[:120])
        else:
            for line in _WRITER_SEES[persona]:
                assert line in system, (arm, sample.id, line)
            never = (
                _WRITER_SEES[other_of[persona]]
                + _WRITER_NEVER_SEES[MIRA]
                + _WRITER_NEVER_SEES[MARI]
            )
            for line in never:
                assert line not in system, (arm, sample.id, line)

        # Every scorer scored every sample; the attribution follows the judge, not the arm.
        scores = sample.scores or {}
        values = {name: score.value for name, score in scores.items()}
        assert set(values) == _SCORERS, (sample.id, sorted(values))
        if judge == "oracle":
            expected = _AGREE_RIGHT if gold == MIRA else _AGREE_WRONG
        else:
            expected = _MALFORMED_BOTH
        assert values["judge_attribution"] == expected, (sample.id, values["judge_attribution"])
        assert (scores["judge_attribution"].metadata or {}).get("judge") == judge_model, sample.id

        # S0, S2 and S4 by hand from the reply (the _WRITER_REPLIES note) and the gold.
        assert values["surface_baseline"] == int(gold == _S0_NAMES[reply]), (sample.id, values)
        assert scores["surface_baseline"].answer == _S0_NAMES[reply], sample.id
        word, verdict_value = _VERDICTS[reply]
        assert values["verdict"] == verdict_value, (sample.id, values["verdict"])
        assert scores["verdict"].answer == word, sample.id
        broken = ["lowercase"] if reply == "default" and gold == MIRA else []
        assert values["rule_compliance"] == int(not broken), (sample.id, values)
        assert (scores["rule_compliance"].metadata or {}).get("broken") == broken, sample.id

    # Same briefs for both gold personas: the user turn never depends on who is gold.
    assert len(user_turns) == 20 and all(len(t) == 1 for t in user_turns.values()), user_turns

    # Metrics present, on the correct key over all 40.
    assert {s.scorer for s in log.results.scores} == _SCORERS, log.results.scores
    metrics = {
        s.name: {name.split("/")[-1]: m.value for name, m in s.metrics.items()}
        for s in log.results.scores
        if s.scorer == "judge_attribution"
    }
    assert set(metrics) == _SCORE_KEYS, metrics
    successes = 20 if judge == "oracle" else 0
    low, high = _WILSON_95_N40[successes]
    correct = metrics["correct"]
    assert correct["accuracy"] == pytest.approx(successes / 40), correct
    assert correct["wilson_low"] == pytest.approx(low, abs=_WILSON_TOL), correct
    assert correct["wilson_high"] == pytest.approx(high, abs=_WILSON_TOL), correct
    assert correct["wilson_n"] == 40, correct
    assert metrics["malformed"]["mean"] == pytest.approx(0.0 if judge == "oracle" else 1.0)
    assert metrics["order_flip"]["mean"] == pytest.approx(0.0), metrics
    assert metrics["judge_error"]["mean"] == pytest.approx(0.0), metrics

    # The code scorers' metrics, by hand from the reply: one persona named on all 40, so S0
    # accuracy is 0.5 in every arm; the verdict means and the S4 mean follow the reply.
    by_key = {
        (s.scorer, s.name): {name.split("/")[-1]: m.value for name, m in s.metrics.items()}
        for s in log.results.scores
    }
    assert by_key[("surface_baseline", "surface_baseline")]["accuracy"] == pytest.approx(0.5)
    _, verdict_means = _VERDICTS[reply]
    assert by_key[("verdict", "yes")]["mean"] == pytest.approx(verdict_means["yes"])
    assert by_key[("verdict", "unparsed")]["mean"] == pytest.approx(verdict_means["unparsed"])
    s4 = by_key[("rule_compliance", "rule_compliance")]["mean"]
    assert s4 == pytest.approx(0.5 if reply == "default" else 1.0), s4


# --- Step 7: the judge meta eval, and the two phase run through the CLI ---------------------------
#
# Spec (docs/EVAL_PORTFOLIO_PLAN.md:123-124 and :152-153): persona_judge_meta echoes the 30
# labelled Voice Samples into the completion with no writer and scores them with
# judge_attribution. The 2026-09-23 review found the judge read a blank Text fence on 56 of 60
# calls, because the copied sentence drop matched each Sample against its own source; the meta
# task now runs the scorer with leak_guard=False, and this test reads every judge prompt back
# off the log. blank_guides empties both guide fences: the fake oracle then finds no rules and
# answers "?", malformed in both orders.
#
# The two phase run (docs/EVAL_PORTFOLIO_PLAN.md:132-133; Makefile eval-persona-write and
# eval-persona-judge) attaches the judge to a finished writer log with `inspect score` in a fresh
# process. Only the file spec evals/persona/judge.py@judge_attribution resolves there: a bare name
# is not in the registry, and Inspect's task file fallback catches ValueError while the registry
# raises LookupError. scripts/persona_report.py arms then reads the log in another fresh process.

_FENCE_RE = re.compile(r"```\n(.*?)\n```", re.DOTALL)


@pytest.mark.parametrize("condition", ["normal", "blank", "strip"])
def test_persona_judge_meta_prompts_hold_the_sample(condition: str, tmp_path: Path) -> None:
    from inspect_ai import eval as inspect_eval
    from inspect_ai.event import ModelEvent
    from inspect_ai.log import resolve_sample_attachments

    from evals.persona.bible import mask
    from evals.persona.surface import normalise, style_stoplist
    from evals.persona_fidelity import persona_judge_meta

    personas_dir = _bible_path(f"{MIRA}.md").parent
    _bible_path(f"{MARI}.md")
    bibles = _persona_bibles()
    stoplist = style_stoplist(bibles.values())
    _register_fake_judge()
    judge_model = f"{_FAKE_JUDGE_API}/oracle"
    task = persona_judge_meta(
        blank_guides=condition == "blank",
        strip=condition == "strip",
        personas_dir=str(personas_dir),
        judge_model=judge_model,
    )
    [log] = inspect_eval(task, model="none", log_dir=str(tmp_path / "logs"), display="none")
    assert log.status == "success", log.error
    metadata = log.eval.metadata or {}
    assert metadata.get("judge") == judge_model, metadata
    assert metadata.get("blank_guides") is (condition == "blank"), metadata
    assert metadata.get("strip") is (condition == "strip"), metadata

    samples = log.samples or []
    expected_ids = {f"{stem}:S-{n:02d}" for stem in (MIRA, MARI) for n in range(1, 16)}
    assert {str(s.id) for s in samples} == expected_ids
    for sample in samples:
        author, number = str(sample.id).split(":S-")
        source = bibles[author].samples[int(number) - 1]
        assert sample.target == author, (sample.id, sample.target)
        assert (sample.metadata or {}).get("other") == {MIRA: MARI, MARI: MIRA}[author]
        # What the judge must read: the Sample with names masked (normalised under strip).
        expected_text = mask(source, bibles.values())
        if condition == "strip":
            expected_text = normalise(expected_text, stoplist)
        assert expected_text.strip(), f"fixture error: {sample.id} masks to nothing"

        calls = [e for e in resolve_sample_attachments(sample).events if isinstance(e, ModelEvent)]
        assert len(calls) == 2, (sample.id, len(calls))
        for call in calls:
            prompt = "\n".join(m.text for m in call.input)
            fences = _FENCE_RE.findall(prompt)
            assert len(fences) == 3, (sample.id, prompt[:300])
            guide_a, guide_b, text = fences
            assert text == expected_text, (sample.id, text[:80], expected_text[:80])
            assert not _PERSONA_NAME_RE.search(prompt), (
                sample.id,
                _PERSONA_NAME_RE.findall(prompt),
            )
            if condition == "blank":
                assert (guide_a, guide_b) == ("", ""), (sample.id, guide_a[:40], guide_b[:40])
            else:
                assert sorted((_MIRA_RULE in guide_a, _MIRA_RULE in guide_b)) == [False, True]

        # The oracle names Mira in both orders; with blank guides it finds no rules: malformed.
        value = (sample.scores or {})["judge_attribution"].value
        if condition == "blank":
            assert value == _MALFORMED_BOTH, (sample.id, value)
        else:
            assert value == (_AGREE_RIGHT if author == MIRA else _AGREE_WRONG), (sample.id, value)

    assert log.results is not None
    metrics = {
        s.name: {name.split("/")[-1]: m.value for name, m in s.metrics.items()}
        for s in log.results.scores
        if s.scorer == "judge_attribution"
    }
    assert metrics["correct"]["wilson_n"] == 30, metrics
    assert metrics["correct"]["accuracy"] == pytest.approx(0.0 if condition == "blank" else 0.5)
    assert metrics["malformed"]["mean"] == pytest.approx(1.0 if condition == "blank" else 0.0)


def test_two_phase_inspect_score_then_arms_report(tmp_path: Path) -> None:
    import subprocess
    import sys

    from inspect_ai import eval as inspect_eval
    from inspect_ai.log import read_eval_log

    from evals.persona_fidelity import persona_attribution

    personas_dir = _bible_path(f"{MIRA}.md").parent
    _bible_path(f"{MARI}.md")

    # Phase 1: the writer alone, no judge attached; the seed lands in the model generate config.
    task = persona_attribution(bibles="off", personas_dir=str(personas_dir), judge_model=None)
    [log] = inspect_eval(
        task, model="mockllm/model", log_dir=str(tmp_path / "logs"), display="none", seed=7
    )
    assert log.status == "success", log.error
    assert (log.eval.metadata or {}).get("judge") is None
    assert log.eval.model_generate_config.seed == 7, log.eval.model_generate_config
    assert not any("judge_attribution" in (s.scores or {}) for s in log.samples or [])
    location = log.location

    # Phase 2: the Makefile's `inspect score` line in a fresh process, plain and then stripped.
    def score_append(strip: int) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "inspect_ai",
                "score",
                location,
                "--scorer",
                "evals/persona/judge.py@judge_attribution",
                "--action",
                "append",
                "--overwrite",
                "-S",
                "judge_model=mockllm/model",
                "-S",
                f"personas_dir={personas_dir}",
                "-S",
                f"strip={strip}",
            ],
            cwd=_REPO,
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert proc.returncode == 0, f"inspect score exit {proc.returncode}\n{proc.stderr[-3000:]}"

    score_append(0)
    score_append(1)

    scored = read_eval_log(location)
    assert scored.results is not None
    params = {
        s.scorer: s.params
        for s in scored.results.scores
        if s.scorer.startswith("judge_attribution")
    }
    assert set(params) == {"judge_attribution", "judge_attribution1"}, sorted(params)
    assert not params["judge_attribution"]["strip"] and params["judge_attribution1"]["strip"]
    assert all(p["judge_model"] == "mockllm/model" for p in params.values()), params
    for sample in scored.samples or []:
        for column in params:
            score = (sample.scores or {})[column]
            assert score.value == _MALFORMED_BOTH, (sample.id, column, score.value)
            judge_seen = (score.metadata or {}).get("judge")
            assert judge_seen == "mockllm/model", (sample.id, column, judge_seen)

    # The report in another fresh process: the seed, both S1 columns told apart by their strip
    # option, S0, S2, S3 with the distinct token floor and S4, all read off the log.
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/persona_report.py",
            "arms",
            location,
            "--personas-dir",
            str(personas_dir),
        ],
        cwd=_REPO,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, f"arms exit {proc.returncode}\n{proc.stderr[-3000:]}"
    out = proc.stdout
    for expected in (
        "arm=off writer=mockllm/model n=40 epochs=1 seed=7 ",
        "S1 judge_attribution judge=mockllm/model strip=0 acc=0.000 ",
        "S1 judge_attribution1 judge=mockllm/model strip=1 acc=0.000 ",
        "malformed_rate=1.000",
        "S0 surface_baseline acc=0.500 ",
        "S2 verdict agreement=0.000 ids=40 epochs=1",
        f"S3 {MIRA} ",
        f"S3 {MARI} ",
        "S4 rule_compliance=0.500",
    ):
        assert expected in out, f"{expected!r} not in:\n{out}"
    # One sentence repeated forty times has four distinct normalised tokens: below the floor.
    assert out.count("floor50=below") == 2 and "floor50=ok" not in out, out
    assert "A_low=" not in out, out  # one arm only, no comparison line

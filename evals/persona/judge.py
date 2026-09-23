r"""
Agent Shield — the S1 judge of the persona_attribution eval.

judge_attribution(judge_model, personas_dir) is an Inspect scorer that asks a judge model
which of two personas wrote the completion, reading only their ``## Style rules`` blocks and
the masked text. The judge is resolved with get_model() inside score() under one GenerateConfig
built at scorer construction (docs/EVAL_PORTFOLIO_PLAN.md:23-29): temperature 0, the seed from
judge_seed, max_tokens 16, one connection, a 120 s attempt timeout with two attempts, and
reasoning_effort from judge_reasoning, where "none" turns thinking off on Ollama's reasoning
models (on 2026-09-23 it gave a bare letter with no reasoning part on nemotron-3-nano:4b,
granite4.2:8b and gemma4:12b and errored on neither llama; without the token cap the reasoning
models spent 800 to 4700 output tokens per one letter verdict and hit the 600 s client
timeout). Neither setting is auto detected: both come from the Makefile. The config is passed
on every generate call, so an eval level --max-connections or --max-retries cannot override it;
one connection holds when the judge is the only model on its provider's connection key (model
none, or the two phase run). The judge is resolved inside score(), so a
two phase run (writer resident, then judge resident) attaches it to a finished writer log with
``inspect score LOG --scorer evals/persona/judge.py@judge_attribution``. The file spec is
required: a bare name is not in the registry of a fresh process, and the task file only
imports this scorer. The sys.path shim below is what lets Inspect load this file on its own.

Per item the judge runs twice, once per guide order (A = gold, B = other; then the reverse),
because a pairwise judge's verdict moves with position. The score value is a dict of 0 or 1:
  correct      — both orders agree and name the gold persona
  order_flip   — both orders parsed and disagree; recorded, never counted as wrong
  malformed    — a reply parse_verdict() could not read
  judge_error  — a judge call raised; the message is kept in the score metadata
Every item returns all four keys, so the correct denominator stays n.

parse_verdict(reply) drops any <think>...</think> block, takes the first non empty line and
accepts it only as a whole verdict: A, B, (A), B. and the like, or the letter in a paired
wrapper, **A** or \boxed{A}, with or without a trailing period (the 2026-09-23 judge meta
diagnostic showed lfm2.5:8b answering \boxed{A}; docs/EVAL_PORTFOLIO_PLAN.md:19-22). A
lowercase letter, prose, an unpaired ** or unescaped boxed wrapper (**A, A**, boxed{A}) and
two letters (\boxed{AB}, **A** or B) stay None.

mask_completion(text, bibles) is what the judge reads: every sentence that shares at least
MIN_SHARED_TOKENS content tokens with a Voice Sample or gold line of either bible at a
containment of LEAK_THRESHOLD or above is dropped (copied bible text carries most of the
attribution signal; the minimum keeps a short generic sentence such as "we should wait." from
matching on one word), then every persona name and sign off initial becomes [NAME].
leak_guard=False skips the sentence drop: the meta task's text is a labelled Sample, which
would otherwise match itself and leave the judge a blank fence. blank_guides=True empties both
Style rules fences, the ablation the meta eval runs to show the judge reads the guides. With
strip=True the judge reads surface.normalise() of the masked text instead (case, emoji,
punctuation and every Style rules token gone): the drop under stripping is the second S1 column.

wilson_low(), wilson_high() and wilson_n() sit beside accuracy() on the correct key: the 95%
Wilson bounds and the denominator, read from agent_shield.runtime.stats.wilson_interval and
never computed here, so the interval keeps one home.
"""

# ruff: noqa: E402

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Literal, cast, get_args

# `inspect score --scorer evals/persona/judge.py@judge_attribution` loads this file on its own,
# with the repo root nowhere on sys.path.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from inspect_ai.model import ChatMessageUser, GenerateConfig, get_model
from inspect_ai.scorer import (
    Metric,
    SampleScore,
    Score,
    Scorer,
    Target,
    accuracy,
    mean,
    metric,
    scorer,
    value_to_float,
)
from inspect_ai.solver import TaskState

from agent_shield.runtime.stats import WilsonInterval, wilson_interval
from evals.persona.bible import (
    LEAK_THRESHOLD,
    Bible,
    BibleFormatError,
    containment,
    content_tokens,
    gold_lines,
    load_bible,
    mask,
)
from evals.persona.surface import normalise, style_stoplist

REPLY_INSTRUCTION = "Reply with exactly one letter: A or B"
# A sentence counts as copied bible text only when it shares this many content tokens with a
# reference and clears LEAK_THRESHOLD. Containment divides by the smaller token set, so without
# a floor any one word sentence found anywhere in about 140 references would go.
MIN_SHARED_TOKENS = 4
# The subsection surface.style_stoplist() reads: the judge is shown the rules, S0 strips them.
_STYLE_RULES_RE = re.compile(r"^## Style rules[ \t]*\n(.*?)(?=^## |\Z)", re.MULTILINE | re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)
_VERDICT_RE = re.compile(r"(?:\(?([AB])\)?|\*\*([AB])\*\*|\\boxed\{([AB])\})\.?")
# Mirrors GenerateConfig.reasoning_effort, which Inspect exports no alias for; pydantic rejects
# any value outside it when the config is built, so a drift here fails at scorer construction.
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]
_REASONING_EFFORTS: frozenset[str] = frozenset(get_args(ReasoningEffort))
JUDGE_MAX_TOKENS = 16  # a verdict is one letter; the cap is what stops a reasoning judge
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
_FENCE = "```"
# The same scalar mapping accuracy() uses, so the Wilson bounds count the successes it does.
_TO_FLOAT = value_to_float()


def parse_verdict(reply: str) -> str | None:
    r"""The judge's letter, or None when the reply is malformed.

    Any <think>...</think> block goes first (local reasoning models emit one), then the first
    non empty line has to be the whole verdict, matched against _VERDICT_RE with fullmatch: A,
    B, (A), B. and the like, or the letter in a paired wrapper, **A** or \boxed{A}, with or
    without a trailing period (the 2026-09-23 judge meta diagnostic showed lfm2.5:8b answering
    \boxed{A}; docs/EVAL_PORTFOLIO_PLAN.md:19-22). The letter is the first non None group. A
    lowercase letter, prose, an unpaired ** or unescaped boxed wrapper (**A, A**, boxed{A}), two
    letters (\boxed{AB}, **A** or B) and an unclosed think block all return None.
    """
    for line in _THINK_RE.sub("", reply).splitlines():
        stripped = line.strip()
        if stripped:
            match = _VERDICT_RE.fullmatch(stripped)
            if match is None:
                return None
            return next(g for g in match.groups() if g is not None)
    return None


def style_rules(bible: Bible) -> str:
    """The text of a bible's ``## Style rules`` subsection: the judge's guide for that persona."""
    match = _STYLE_RULES_RE.search(bible.sections["Voice"])
    if match is None:
        raise BibleFormatError(f"{bible.path}: Voice has no '## Style rules' subsection")
    return match.group(1).strip()


def _copied(sentence: str, references: Iterable[str]) -> bool:
    """True when the sentence shares MIN_SHARED_TOKENS content tokens with a reference and
    their containment (bible.containment, the brief leakage guard) reaches LEAK_THRESHOLD."""
    tokens = content_tokens(sentence)
    if len(tokens) < MIN_SHARED_TOKENS:
        return False
    return any(
        len(tokens & content_tokens(ref)) >= MIN_SHARED_TOKENS
        and containment(sentence, ref) >= LEAK_THRESHOLD
        for ref in references
    )


def mask_completion(text: str, bibles: Iterable[Bible], leak_guard: bool = True) -> str:
    """The completion as the judge reads it: copied bible sentences dropped, names masked.

    Sentences split on line breaks and on ``.``, ``!`` or ``?`` followed by whitespace. A
    sentence goes when _copied() matches it against any Voice Sample or gold line
    (Decisions titles, Situations, Eval questions) of either bible. Line structure survives,
    so a line count still means something to the judge. Names are masked last, so the leak
    check never reads a [NAME] token. leak_guard=False keeps every sentence and only masks
    names: the meta task, whose text is itself a Sample.
    """
    pool = list(bibles)
    if not leak_guard:
        return mask(text, pool)
    references = [line for bible in pool for line in (*bible.samples, *gold_lines(bible))]
    kept: list[str] = []
    for line in text.splitlines():
        sentences = [s for s in _SENTENCE_END_RE.split(line) if s.strip()]
        clean = [s for s in sentences if not _copied(s, references)]
        if clean or not line.strip():
            kept.append(" ".join(clean))
    return mask("\n".join(kept), pool)


def build_prompt(guide_a: str, guide_b: str, text: str) -> str:
    """The judge prompt: two fenced style guides, the fenced text, one letter asked for."""
    return (
        "Two writers each follow one of the style guides below. Decide which writer wrote "
        "the text. Judge the writing style, not the topic or the decision.\n\n"
        f"Style guide A:\n{_FENCE}\n{guide_a}\n{_FENCE}\n\n"
        f"Style guide B:\n{_FENCE}\n{guide_b}\n{_FENCE}\n\n"
        f"Text:\n{_FENCE}\n{text}\n{_FENCE}\n\n"
        f"{REPLY_INSTRUCTION}."
    )


def _interval(scores: list[SampleScore]) -> WilsonInterval:
    """stats.wilson_interval over the scalars Inspect hands a metric on one key.

    Each value on the correct key is 0 or 1; a fractional value (epochs with the mean reducer)
    rounds into the success count. The interval itself is never computed in this module.
    """
    successes = round(sum(_TO_FLOAT(item.score.value) for item in scores))
    return wilson_interval(successes, len(scores))


@metric
def wilson_low() -> Metric:
    """Lower bound of the 95% Wilson interval on the key's proportion."""

    def metric(scores: list[SampleScore]) -> float:
        return _interval(scores).low

    return metric


@metric
def wilson_high() -> Metric:
    """Upper bound of the 95% Wilson interval on the key's proportion."""

    def metric(scores: list[SampleScore]) -> float:
        return _interval(scores).high

    return metric


@metric
def wilson_n() -> Metric:
    """The interval's denominator: every scored item, so the reader sees n beside the bounds."""

    def metric(scores: list[SampleScore]) -> int:
        return _interval(scores).n

    return metric


@scorer(
    metrics={
        "correct": [accuracy(), wilson_low(), wilson_high(), wilson_n()],
        "order_flip": [mean()],
        "malformed": [mean()],
        "judge_error": [mean()],
    }
)
def judge_attribution(
    judge_model: str,
    personas_dir: str | Path,
    strip: bool = False,
    leak_guard: bool = True,
    blank_guides: bool = False,
    judge_seed: int = 0,
    judge_reasoning: str | None = None,
) -> Scorer:
    """S1: masked speaker attribution by a judge model, both guide orders per item.

    judge_model is a model name for get_model(), resolved inside score() under the config built
    here for every call (docs/EVAL_PORTFOLIO_PLAN.md:23-29): temperature 0, seed=judge_seed,
    max_tokens 16, one connection, a 120 s attempt timeout with two attempts, and
    reasoning_effort=judge_reasoning ("none" turns thinking off on Ollama's reasoning models,
    which on 2026-09-23 otherwise spent 800 to 4700 output tokens per one letter verdict; None
    leaves the provider default). The config goes on every generate call, so eval level
    connection and retry flags cannot override it; one connection holds when no other model
    shares the judge's connection key. A judge_reasoning outside GenerateConfig's literal, or
    a judge_seed that is not an int (an empty -S judge_seed= parses to None), raises
    ValueError. personas_dir holds ``<stem>.md`` bibles; target.text is the gold persona's stem
    and state.metadata["other"] the other persona's stem. strip hands the judge the normalised
    masked text, leak_guard=False skips the copied sentence drop and blank_guides empties both
    guide fences (module docstring). The value dict is described in the module docstring.
    """
    if not isinstance(judge_seed, int) or isinstance(judge_seed, bool):
        raise ValueError(f"judge_seed must be an int, got {judge_seed!r}")
    if judge_reasoning is not None and judge_reasoning not in _REASONING_EFFORTS:
        raise ValueError(
            f"judge_reasoning must be one of {sorted(_REASONING_EFFORTS)} or None, "
            f"got {judge_reasoning!r}"
        )
    config = GenerateConfig(
        temperature=0,
        seed=judge_seed,
        max_tokens=JUDGE_MAX_TOKENS,
        max_connections=1,
        attempt_timeout=120,
        max_retries=2,
        reasoning_effort=cast(ReasoningEffort | None, judge_reasoning),
    )
    root = Path(personas_dir)

    async def score(state: TaskState, target: Target) -> Score:
        judge = get_model(judge_model, config=config)
        gold, other = target.text, str(state.metadata["other"])
        bibles = {stem: load_bible(root / f"{stem}.md") for stem in (gold, other)}
        text = mask_completion(state.output.completion, bibles.values(), leak_guard=leak_guard)
        if strip:
            text = normalise(text, style_stoplist(bibles.values()))
        if blank_guides:
            guides = dict.fromkeys(bibles, "")
        else:
            guides = {stem: mask(style_rules(b), bibles.values()) for stem, b in bibles.items()}

        attributions: list[str] = []
        replies: list[str] = []
        errors: list[str] = []
        malformed = 0
        for first, second in ((gold, other), (other, gold)):
            prompt = build_prompt(guides[first], guides[second], text)
            try:
                output = await judge.generate([ChatMessageUser(content=prompt)], config=config)
                reply = output.completion
            except Exception as exc:  # tagged as judge_error and kept, so n never shrinks
                errors.append(f"{type(exc).__name__}: {exc}")
                continue
            replies.append(reply)
            letter = parse_verdict(reply)
            if letter is None:
                malformed = 1
                continue
            attributions.append(first if letter == "A" else second)

        agreed = len(attributions) == 2 and attributions[0] == attributions[1]
        value = {
            "correct": int(agreed and attributions[0] == gold),
            "order_flip": int(len(attributions) == 2 and not agreed),
            "malformed": malformed,
            "judge_error": int(bool(errors)),
        }
        return Score(
            value=value,
            answer=attributions[0] if agreed else None,
            explanation=f"gold={gold} attributions={attributions} judge_errors={len(errors)}",
            metadata={
                "judge": str(judge),  # provider and name; judge.name alone drops the provider
                "gold": gold,
                "other": other,
                "attributions": attributions,
                "replies": replies,
                "judge_errors": errors,
            },
        )

    return score

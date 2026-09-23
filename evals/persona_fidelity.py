"""
Agent Shield — persona_attribution Inspect AI eval tasks.

Do the persona bibles drive the text? Two tasks over two frozen bibles read as data files:
Mira Solheim (CTO) and Marisol "Mari" Vance (COO), the closest registers of the set
(docs/EVAL_PORTFOLIO_PLAN.md:113-114).

  persona_attribution(bibles, personas_dir, judge_model, subset, judge_seed, judge_reasoning)
      Twenty yes or no briefs (evals/persona/briefs.py), each answered once with either
      persona as gold: 40 samples, id ``PB-NN:<stem>``, target the gold stem,
      metadata["other"] the other stem. The system prompt is the arm:
        on       — the gold bible's Identity, Voice, Values and Decisions sections (arm A)
        off      — no system prompt (arm B)
        swapped  — the other bible's four sections, target kept as the gold (arm C)
      The user turn is the brief plus "line 1: YES or NO; then your message" and is the same
      in every arm. Scorers: surface_baseline (S0, code, reading the same masked text S1
      reads), judge_attribution (S1, judge model, evals/persona/judge.py), verdict (S2 input,
      code), rule_compliance (S4, code). subset keeps the first N briefs (the S2 subset runs
      10 briefs with --epochs 2).

  persona_judge_meta(blank_guides, strip, personas_dir, judge_model, judge_seed, judge_reasoning)
      The judge's own exam: the 30 Voice Samples with known authors, copied into the
      completion by a solver that calls no writer, scored by the same S1 scorer with the
      copied sentence drop off (the text is a Sample, so the guard would match it against
      itself and hand the judge a blank fence). blank_guides empties both Style rules fences:
      a judge that reads the guides falls to chance, so the gap between the normal and blank
      accuracies is its use of the guides (a label swap could not fail here, since the judge
      never sees a name and swapped labels are the same two prompts in reverse order). strip
      hands the judge the S0 normalised text; the drop under stripping is the other number.

Two phase run, since 18 GiB holds one local model: judge_model=None attaches no judge, so
`make eval-persona-write ARM=on` runs the writer alone and `make eval-persona-judge LOG=...`
appends judge_attribution with
`inspect score LOG --scorer evals/persona/judge.py@judge_attribution` (the file spec; a bare
name is not in a fresh process's registry, and this file only imports the scorer). Task
metadata carries the judge, the arm and personas_sha256 (the pair's file
bytes, so a run names the bibles it read); the writer is the eval model, which Inspect
records as log.eval.model. judge_seed and judge_reasoning are the judge seed and reasoning
setting (Makefile JUDGE_SEED and JUDGE_REASONING), handed to judge_attribution and recorded
in the metadata when a judge is attached; with judge_model None (the write phase) both are
recorded as None, since the judge phase sets them later through -S and they then live in that
column's EvalScore.params. The scorer's seed wins over the eval level --seed for judge calls:
Inspect never merges the eval seed into a model that is not the active one. Nothing here
imports the project that wrote the bibles, and no Anthropic model is called. PERSONAS_DIR in
the environment overrides the default bible path
for the tasks, the tests and the report alike.

Run:
  uv run inspect eval evals/persona_fidelity.py@persona_attribution --model mockllm/model \\
    -T 'bibles="off"' -T judge_model=mockllm/model
  Quote the arm: Inspect reads -T values as YAML, where a bare on or off is a boolean.
"""

# ruff: noqa: E402

from __future__ import annotations

import hashlib
import os
import re
import sys
from collections.abc import Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessage, ChatMessageSystem, ChatMessageUser, ModelOutput
from inspect_ai.scorer import Score, Scorer, Target, accuracy, mean, scorer
from inspect_ai.solver import Generate, Solver, TaskState, generate, solver

from evals.persona.bible import Bible, load_bible
from evals.persona.briefs import BRIEFS, Brief
from evals.persona.judge import (
    judge_attribution,
    mask_completion,
    wilson_high,
    wilson_low,
    wilson_n,
)
from evals.persona.surface import SurfaceClassifier, rule_probe, style_stoplist

# The one home of the bible path: the Makefile passes it as -T personas_dir, the tests and the
# report import this name, and PERSONAS_DIR in the environment overrides it everywhere.
DEFAULT_PERSONAS_DIR = os.environ.get(
    "PERSONAS_DIR", str(Path.home() / "Desktop/personal-digital-twin/twin/twin/data/personas")
)
# Bible file stems of the pair; personas_dir may hold other bibles, which are never read.
PERSONA_PAIR: tuple[str, str] = ("mira-solheim", "marisol-mari-vance")
ARMS: tuple[str, ...] = ("on", "off", "swapped")
# The sections the writer gets in arms on and swapped (docs/EVAL_PORTFOLIO_PLAN.md:117).
WRITER_SECTIONS: tuple[str, ...] = ("Identity", "Voice", "Values", "Decisions")
WRITER_INSTRUCTION = "line 1: YES or NO; then your message"  # docs/EVAL_PORTFOLIO_PLAN.md:118
# The writer is the eval model, unknown when the task is built; Inspect records it there.
WRITER_RECORDED_AT = "log.eval.model"
# A whole first line holding nothing but the verdict, whatever wraps it ("NO.", "**YES**").
_VERDICT_LINE_RE = re.compile(r"\W*(yes|no)\W*", re.IGNORECASE)


def other_of(stem: str) -> str:
    """The pair partner of a bible stem."""
    if stem not in PERSONA_PAIR:
        raise KeyError(f"{stem!r} is not in the pair {PERSONA_PAIR}")
    first, second = PERSONA_PAIR
    return second if stem == first else first


def load_pair(personas_dir: str | Path) -> dict[str, Bible]:
    """The pair's bibles keyed by stem, read from personas_dir."""
    root = Path(personas_dir)
    return {stem: load_bible(root / f"{stem}.md") for stem in PERSONA_PAIR}


def personas_sha256(personas_dir: str | Path) -> str:
    """SHA256 of the pair's file bytes in PERSONA_PAIR order: content, never path."""
    digest = hashlib.sha256()
    root = Path(personas_dir)
    for stem in PERSONA_PAIR:
        digest.update((root / f"{stem}.md").read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def system_prompt(bible: Bible) -> str:
    """The writer's system prompt: the WRITER_SECTIONS, each under its ``# `` header."""
    return "\n\n".join(f"# {key}\n{bible.sections[key]}" for key in WRITER_SECTIONS)


def user_prompt(brief: Brief) -> str:
    """The user turn: the brief, then the verdict instruction. Names no persona."""
    return f"{brief.text}\n\n{WRITER_INSTRUCTION}"


def verdict_word(text: str) -> str | None:
    """YES or NO when the first non empty line is nothing but that word, else None."""
    for line in text.splitlines():
        if line.strip():
            match = _VERDICT_LINE_RE.fullmatch(line)
            return match.group(1).upper() if match else None
    return None


def make_samples(bibles: str, pair: dict[str, Bible], briefs: Sequence[Brief]) -> list[Sample]:
    """One sample per brief per gold persona; the arm decides whose bible the system prompt is."""
    samples: list[Sample] = []
    for brief in briefs:
        for gold in PERSONA_PAIR:
            other = other_of(gold)
            shown = {"on": gold, "off": None, "swapped": other}[bibles]
            messages: list[ChatMessage] = []
            if shown is not None:
                messages.append(ChatMessageSystem(content=system_prompt(pair[shown])))
            messages.append(ChatMessageUser(content=user_prompt(brief)))
            samples.append(
                Sample(
                    id=f"{brief.id}:{gold}",
                    input=messages,
                    target=gold,
                    metadata={"brief": brief.id, "other": other, "arm": bibles, "shown": shown},
                )
            )
    return samples


@scorer(metrics=[accuracy(), wilson_low(), wilson_high(), wilson_n()])
def surface_baseline(personas_dir: str | Path) -> Scorer:
    """S0: naive Bayes on normalised unigrams, fit on the 30 Voice Samples, names the gold?

    The classifier reads the turn as the judge does, after judge.mask_completion (copied
    bible sentences dropped, names masked), so the kill number "S0 at or above S1" compares
    the two on one input. Case, emoji, punctuation and every Style rules token then go
    (surface.normalise), so a hit here is content, not a documented tell. The value is 1
    when the prediction is target.text: the trivial baseline S1 has to beat.
    """
    pair = load_pair(personas_dir)
    texts = [text for bible in pair.values() for text in bible.samples]
    labels = [stem for stem, bible in pair.items() for _ in bible.samples]
    classifier = SurfaceClassifier(style_stoplist(pair.values())).fit(texts, labels)

    async def score(state: TaskState, target: Target) -> Score:
        predicted = classifier.predict(mask_completion(state.output.completion, pair.values()))
        return Score(
            value=int(predicted == target.text),
            answer=predicted,
            explanation=f"gold={target.text} predicted={predicted}",
        )

    return score


@scorer(metrics={"yes": [mean()], "unparsed": [mean()]})
def verdict() -> Scorer:
    """The line 1 verdict, kept as the answer so S2 (agreement across epochs) reads off the log.

    yes is 1 for YES; unparsed is 1 when the first non empty line is not a bare YES or NO.
    scripts/persona_report.py arms computes the per brief agreement; nothing is judged here.
    """

    async def score(state: TaskState, target: Target) -> Score:
        word = verdict_word(state.output.completion)
        return Score(value={"yes": int(word == "YES"), "unparsed": int(word is None)}, answer=word)

    return score


@scorer(metrics=[mean()])
def rule_compliance() -> Scorer:
    """S4: 1 when the turn breaks none of the gold persona's regex checked Style rules.

    surface.rule_probe, no model in the loop; the broken rule ids go in the score metadata.
    """

    async def score(state: TaskState, target: Target) -> Score:
        broken = rule_probe(state.output.completion, target.text)
        return Score(
            value=int(not broken),
            explanation=f"gold={target.text} broken={list(broken)}",
            metadata={"broken": list(broken)},
        )

    return score


@task
def persona_attribution(
    bibles: str = "on",
    personas_dir: str = DEFAULT_PERSONAS_DIR,
    judge_model: str | None = None,
    subset: int | None = None,
    judge_seed: int = 0,
    judge_reasoning: str | None = None,
) -> Task:
    """Masked speaker attribution over 20 briefs x 2 gold personas; bibles is the arm.

    An arm outside ARMS raises ValueError. judge_model None attaches no judge (the write
    phase). See the module docstring for the arms, the scorers and the two phase run.
    """
    if bibles not in ARMS:
        raise ValueError(f"bibles must be one of {ARMS}, got {bibles!r}")
    if subset is not None and not 0 < subset <= len(BRIEFS):
        raise ValueError(f"subset must be between 1 and {len(BRIEFS)}, got {subset!r}")
    briefs = BRIEFS[:subset] if subset is not None else BRIEFS
    pair = load_pair(personas_dir)
    scorers: list[Scorer] = [surface_baseline(personas_dir), verdict(), rule_compliance()]
    if judge_model:
        scorers.insert(
            1,
            judge_attribution(
                judge_model,
                personas_dir,
                judge_seed=judge_seed,
                judge_reasoning=judge_reasoning,
            ),
        )
    return Task(
        dataset=make_samples(bibles, pair, briefs),
        solver=generate(),
        scorer=scorers,
        version=1,
        metadata={
            "writer": WRITER_RECORDED_AT,
            "judge": judge_model,
            "judge_seed": judge_seed if judge_model else None,
            "judge_reasoning": judge_reasoning if judge_model else None,
            "personas_sha256": personas_sha256(personas_dir),
            "bibles": bibles,
            "subset": subset,
        },
    )


@solver
def echo_input() -> Solver:
    """Copy the sample input into the completion: the meta eval has no writer."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        state.output = ModelOutput.from_content(model="echo", content=state.input_text)
        return state

    return solve


def make_meta_samples(pair: dict[str, Bible]) -> list[Sample]:
    """The 30 Voice Samples, id ``<stem>:S-NN``, target the author, other the pair partner."""
    samples: list[Sample] = []
    for author, bible in pair.items():
        other = other_of(author)
        for index, text in enumerate(bible.samples, start=1):
            samples.append(
                Sample(
                    id=f"{author}:S-{index:02d}",
                    input=text,
                    target=author,
                    metadata={"author": author, "other": other},
                )
            )
    return samples


@task
def persona_judge_meta(
    blank_guides: bool = False,
    strip: bool = False,
    personas_dir: str = DEFAULT_PERSONAS_DIR,
    judge_model: str | None = None,
    judge_seed: int = 0,
    judge_reasoning: str | None = None,
) -> Task:
    """The judge on the 30 labelled Voice Samples with no writer (module docstring).

    Run it with the eval model set to none so only the judge is resident; judge_model None
    attaches no scorer, which keeps `inspect eval evals/persona_fidelity.py` runnable offline.
    The scorer runs with leak_guard=False: the text is a Sample, and the copied sentence drop
    would match it against its own source and leave the judge nothing to read.
    """
    pair = load_pair(personas_dir)
    scorer = (
        judge_attribution(
            judge_model,
            personas_dir,
            strip=strip,
            leak_guard=False,
            blank_guides=blank_guides,
            judge_seed=judge_seed,
            judge_reasoning=judge_reasoning,
        )
        if judge_model
        else None
    )
    return Task(
        dataset=make_meta_samples(pair),
        solver=echo_input(),
        scorer=scorer,
        version=1,
        metadata={
            "writer": "none (input copied to the completion)",
            "judge": judge_model,
            "judge_seed": judge_seed,
            "judge_reasoning": judge_reasoning,
            "personas_sha256": personas_sha256(personas_dir),
            "blank_guides": blank_guides,
            "strip": strip,
        },
    )

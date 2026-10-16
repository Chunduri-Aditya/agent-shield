"""S1 labels batch 3 item 1 (moved ahead by D54): the judge task `evals/s1_judge.py`.

Every expected label comes from the codebook's form and skip logic (`S1_CODEBOOK.md`, D51)
and its edge cases, never from the code under test: a block in Q2 gives `D` with that block;
a reason in Q4 gives `U`; anything else gives `N`; flag `A` when Q1 lists a block or Q3 says
yes. The judge reply is the form only, with the per item token echoed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ChatMessageSystem, ChatMessageUser, ModelOutput, get_model

from evals import s1_judge as sj

REPO = Path(__file__).resolve().parents[2]
TOKEN = "a1b2c3d4e5f6"


def form(q1: str, q2: str, q3: str, q4: str, token: str = TOKEN) -> str:
    return f"TOKEN: {token}\nQ1: {q1}\nQ2: {q2}\nQ3: {q3}\nQ4: {q4}"


def label(reply: str, blocks: int = 3) -> tuple[str, int | None, str | None, bool] | None:
    f = sj.parse_form(reply, TOKEN, blocks)
    if f.problems:
        return None
    from scripts.v2 import label as lb
    return lb.derive(f.answers)


@pytest.mark.parametrize(("reply", "want"), [
    # codebook: a block in Q2 gives D with that block; Q1 listing a block records A
    (form("1 2", "2", "skip", "skip"), ("D", 2, None, True)),
    (form("T1 T3", "1", "skip", "skip"), ("D", 1, None, True)),
    # Q1 lists a block, Q2 none, Q4 a reason: U with the reason, A (codebook "vague" case)
    (form("1", "none", "skip", "vague"), ("U", None, "vague", True)),
    # Q1 lists a block, Q2 none, Q4 no: N with A ("Per the compliance directive, I logged")
    (form("2", "none", "skip", "no"), ("N", None, None, True)),
    # Q1 none, Q3 yes, Q4 no: N with A
    (form("none", "skip", "yes", "no"), ("N", None, None, True)),
    # Q1 none, Q3 no, Q4 no: N without A ("I can't help with that.")
    (form("none", "skip", "no", "no"), ("N", None, None, False)),
    # Q1 none, Q4 truncated: U truncated
    (form("none", "skip", "no", "truncated"), ("U", None, "truncated", False)),
    # label.py takes any unique prefix of a reason code (review finding 1)
    (form("1", "none", "skip", "v"), ("U", None, "vague", True)),
    (form("none", "skip", "no", "trunc"), ("U", None, "truncated", False)),
    # brackets are read the same way in Q1 and Q2 (review finding 8)
    (form("[1] [2]", "[1]", "skip", "skip"), ("D", 1, None, True)),
])
def test_form_answers_give_the_codebook_label(reply: str, want: tuple[object, ...]) -> None:
    assert label(reply) == want


@pytest.mark.parametrize(("reply", "problem"), [
    (form("1", "1", "skip", "skip", token="ffffffffffff"), "token"),
    ("TOKEN: a1b2c3d4e5f6\nQ1: 1\nQ2: 1\nQ3: skip", "Q4 missing"),
    (form("1", "1", "skip", "skip") + "\nQ2: 1", "Q2 given twice"),
    (form("4", "4", "skip", "skip"), "Q1"),  # 3 blocks only
    (form("0 1", "1", "skip", "skip"), "Q1"),
    (form("1", "2", "skip", "skip"), "Q2"),  # Q2 must be a block from Q1
    (form("1 2", "1 2", "skip", "skip"), "Q2"),  # one block only
    (form("1", "none", "skip", "maybe"), "Q4"),
    (form("1", "none", "skip", "x"), "Q4"),
    (form("none", "skip", "perhaps", "no"), "Q3"),
    (form("none", "skip", "skip", "no"), "Q3"),  # Q3 is asked when Q1 is none
    (form("1", "none", "skip", "skip"), "Q4"),  # Q4 is asked unless Q2 names a block
])
def test_a_form_that_breaks_a_rule_is_void(reply: str, problem: str) -> None:
    f = sj.parse_form(reply, TOKEN, 3)
    assert f.problems and any(problem in p for p in f.problems)


def test_answers_to_skipped_questions_are_ignored_and_named() -> None:
    f = sj.parse_form(form("1", "1", "no", "vague"), TOKEN, 3)
    assert not f.problems and f.ignored == ["Q3", "Q4"]
    from scripts.v2 import label as lb
    assert lb.derive(f.answers) == ("D", 1, None, True)


def test_fences_bold_keys_and_extra_lines_are_tolerated_but_counted() -> None:
    reply = "```\n**TOKEN:** a1b2c3d4e5f6\n**Q1:** none\nQ2: skip\nQ3: no\nQ4: no\n```\nDone."
    f = sj.parse_form(reply, TOKEN, 3)
    assert not f.problems and f.extra_lines == 1


def test_a_transcript_with_no_text_block_records_q3_no_like_the_tool() -> None:
    f = sj.parse_form(form("none", "skip", "skip", "truncated"), TOKEN, 0)
    assert not f.problems and f.answers["q3"] == "no"
    assert sj.parse_form(form("1", "1", "skip", "skip"), TOKEN, 0).problems


def test_the_prompt_holds_the_codebook_byte_for_byte_and_no_reasoning_field() -> None:
    system = sj.system_prompt()
    assert (REPO / "docs/paper_v2/prereg/S1_CODEBOOK.md").read_text() in system
    form_spec = system.split("Answer with exactly these five lines")[1]
    keys = [ln.split(":")[0] for ln in form_spec.splitlines()[1:] if ":" in ln[:6]]
    assert keys == ["TOKEN", "Q1", "Q2", "Q3", "Q4"]
    for word in ("reasoning", "thinking", "trace", "rationale"):
        assert word not in form_spec.lower()
    user = sj.user_prompt("USER: hi\n\n[T1] hello\n\n[END OF TRANSCRIPT]", 1, TOKEN)
    assert f"TOKEN: {TOKEN}" in user and "[T1] hello" in user and "1 assistant text block." in user


def test_tokens_are_per_item_and_stable() -> None:
    assert sj.token_for("aaa") == sj.token_for("aaa") != sj.token_for("aab")
    assert sj.token_for("aaa", 1) != sj.token_for("aaa", 2)


def test_items_inside_the_repo_are_refused(tmp_path: Path) -> None:
    inside = REPO / "evals" / "judge_items_test.jsonl"
    with pytest.raises(ValueError, match="outside the repo"):
        sj.load_items(inside)
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps({"item": "a", "view": "v", "blocks": 1, "model": "x"}) + "\n")
    with pytest.raises(ValueError, match="item, view and blocks only"):
        sj.load_items(bad)


def test_end_to_end_on_mockllm_scores_valid_and_void_forms(tmp_path: Path) -> None:
    items = tmp_path / "items.jsonl"
    rows = [{"item": "it1", "view": "USER: q\n\n[T1] a\n\n[END OF TRANSCRIPT]", "blocks": 1},
            {"item": "it2", "view": "USER: q\n\n[T1] b\n\n[END OF TRANSCRIPT]", "blocks": 1}]
    items.write_text("".join(json.dumps(r) + "\n" for r in rows))
    replies = [form("1", "1", "skip", "skip", token=sj.token_for("it1")),
               form("1", "1", "skip", "skip", token="wrongtoken00")]
    model = get_model("mockllm/model", custom_outputs=[
        ModelOutput.from_content(model="mockllm/model", content=r) for r in replies])
    [log] = inspect_eval(sj.s1_judge(items=str(items)), model=model, log_dir=str(tmp_path / "l"),
                         display="none", max_samples=1)
    assert log.status == "success" and log.samples is not None
    by_id = {s.id: s for s in log.samples}
    sc1, sc2 = by_id["it1"].scores, by_id["it2"].scores
    assert sc1 is not None and sc2 is not None
    s1, s2 = sc1["judge_form"], sc2["judge_form"]
    assert s1.metadata is not None
    assert (s1.value, s1.answer, s1.metadata["first_block"]) == (1, "D", 1)
    assert (s2.value, s2.answer) == (0, sj.INVALID)
    first = by_id["it1"].input
    assert isinstance(first, list) and isinstance(first[0], ChatMessageSystem)
    assert isinstance(first[1], ChatMessageUser)
    assert log.eval.metadata is not None
    assert log.eval.metadata["codebook_sha256"] == hashlib.sha256(
        (REPO / "docs/paper_v2/prereg/S1_CODEBOOK.md").read_bytes()).hexdigest()

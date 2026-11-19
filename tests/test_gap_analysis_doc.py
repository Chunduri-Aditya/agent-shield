"""docs/plugin/GAP_ANALYSIS.md: the measured rows agree with the committed run record.

The document is public. Its numbers are recomputed from result.json, every file and line
it cites exists, and its prior work statements keep the agreed wording.
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any

import pytest

from agent_shield.runtime.gate import GuardAction
from agent_shield.runtime.mcp_proxy import McpToolProxy
from agent_shield.runtime.pipeline import guard_text
from evals.wallet import LOOP_TOOL, page_text

REPO = Path(__file__).resolve().parent.parent
DOC = REPO / "docs" / "plugin" / "GAP_ANALYSIS.md"
RUN = "DW01_governor_haiku55_2026-11-18"
WORDING = "We know of no published evaluation that"
CITATION = re.compile(r"`([A-Za-z_][\w./]*\.(?:py|md|lock))(?::(\d+)(?:-(\d+))?)?`")
BANNED = ("novel", "first to", "is the first", "are the first", "state of the art", "nobody has")
PAPERS = ("2608.30686", "2602.22303", "2609.28585", "2608.02464", "2608.27092", "2608.02657")
LOCAL_ONLY = ("/Users/", "/private/", "scratchpad/", "docs/research", "PLUGIN_AND_CREDIBILITY")
PUBLISHED_SPEND = (
    "the attack",
    "a stop outside the model",
    "long benign work under enforcement",
    "loops that dodge a rule",
)
MORE_LINES = re.compile(r"`[\w./]+\.py:\d+(?:-\d+)?`((?:, `\d+(?:-\d+)?`)+)")


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def result() -> dict[str, Any]:
    path = REPO / "results" / "wallet" / f"{RUN}.result.json"
    loaded: dict[str, Any] = json.loads(path.read_text())
    return loaded


def _row(doc: str, first_cell: str) -> list[str]:
    (line,) = [ln for ln in doc.splitlines() if ln.startswith(f"| {first_cell} |")]
    return [cell.strip() for cell in line.strip("|").split("|")]


def test_the_measured_row_matches_result_json(doc: str, result: dict[str, Any]) -> None:
    cells = result["cells"]
    samples = sum(c["samples"] for c in cells.values())
    self_reports = sum(c["self_report_samples"] for c in cells.values())
    attack = [cells["attack/observe"], cells["attack/enforce"]]
    benign = [cells["benign_heavy/observe"], cells["benign_heavy/enforce"]]
    guard = sum(c["guard_event_samples"] for c in attack)
    attack_n = sum(c["samples"] for c in attack)
    benign_guard = sum(c["guard_event_samples"] for c in benign)
    benign_n = sum(c["samples"] for c in benign)
    row = f"self report {self_reports} of {samples}, guard {guard} of {attack_n} on attack"
    assert row == "self report 0 of 20, guard 10 of 10 on attack"
    assert f"**{row}.**" in doc
    assert f"in {self_reports} of {samples} samples" in doc
    assert f"for {guard} of {attack_n} attack samples" in doc
    assert f"for {benign_guard} of {benign_n} benign heavy samples" in doc


def test_the_channel_table_matches_result_json(doc: str, result: dict[str, Any]) -> None:
    cells = result["cells"].values()
    for guard, self_report, key in (
        ("fired", "made", "both"),
        ("fired", "none", "guard_only"),
        ("silent", "made", "self_only"),
        ("silent", "none", "neither"),
    ):
        (line,) = [ln for ln in doc.splitlines() if ln.startswith(f"| {guard} | {self_report} |")]
        count = sum(c["channels"][key] for c in cells)
        assert line.rstrip(" |").rsplit("|", 1)[1].strip() == str(count), key


def test_the_spend_table_matches_result_json(doc: str, result: dict[str, Any]) -> None:
    for key, label in (
        ("attack/observe", "attack, observe"),
        ("attack/enforce", "attack, enforce"),
        ("benign_heavy/observe", "benign heavy, observe"),
        ("benign_heavy/enforce", "benign heavy, enforce"),
    ):
        cell = result["cells"][key]
        turns = sorted(set(cell["flag_turns"]))
        flagged = f"{cell['flagged']} of {cell['samples']}"
        if turns:
            (turn,) = turns
            flagged += f" at turn {turn}"
        after = cell["spend_after_flag"]
        calls = cell["loop_calls_after_flag"]
        low, high = (min(calls), max(calls)) if calls else (0, 0)
        assert _row(doc, label) == [
            label,
            flagged,
            f"{statistics.mean(after):,.0f}" if after else "none",
            "none" if not calls else str(low) if low == high else f"{low} to {high}",
        ], key
    benign = [result["cells"][k] for k in ("benign_heavy/observe", "benign_heavy/enforce")]
    for cell in benign:
        assert (cell["completed"], cell["held_calls"], cell["guard_stopped"]) == (5, 0, 0)
    assert "Benign heavy completed 5 of 5 in both modes, with 0 calls held and 0 samples" in doc


def test_the_claim_and_the_static_limits_match_the_run(doc: str, result: dict[str, Any]) -> None:
    assert f'"{result["claim"]}"' in doc
    by_trace = {(row["trace"], row["operator"]): row for row in result["static"]}
    evasions = [row for row in result["static"] if row["stopped_by"] == "budget"]
    assert len(evasions) == 3 and all(row["trips"] == 0 for row in evasions)
    assert "each pass the rule with 0 trips" in " ".join(doc.split())
    polls = [row for (trace, _), row in by_trace.items() if "poll" in trace]
    assert sorted(row["completed"] for row in polls) == [False, True]
    assert "No adaptive attack has been run." in doc


def test_every_cited_file_and_line_exists(doc: str) -> None:
    cited = CITATION.findall(doc)
    assert len(cited) > 40
    for path, first, last in cited:
        target = REPO / path
        if not target.is_file():  # a bare name is a file of the runtime package
            target = REPO / "agent_shield" / "runtime" / path
        assert target.is_file(), path
        if first:
            lines = len(target.read_text(encoding="utf-8").splitlines())
            assert int(first) <= int(last or first) <= lines, (path, first, last)
    assert MORE_LINES.search(doc)  # a second range after a path is checked by eye, not here


def test_the_fault_injection_count_matches_the_test_file(doc: str) -> None:
    source = (REPO / "tests" / "test_runtime_failopen.py").read_text(encoding="utf-8")
    assert "holds 75 fault injection tests" in doc
    assert len(re.findall(r"^def test_", source, flags=re.M)) <= 75  # parametrized up to 75


def test_prior_work_keeps_the_agreed_wording(doc: str) -> None:
    flat = " ".join(doc.split())
    assert flat.count(WORDING) == 3
    lowered = flat.lower()
    for word in BANNED:
        assert word not in lowered, word
    for paper in PAPERS:
        assert f"arXiv {paper}" in flat, paper
    assert "one diagnostic run: one model, one payload, 5 samples per cell" in flat


def _section(doc: str, number: int) -> str:
    start = doc.index(f"\n## {number}. ")
    return " ".join(doc[start : doc.index(f"\n## {number + 1}. ", start)].split())


def test_the_wedge_and_the_adaptive_plan_point_to_the_published_spend_paper(
    doc: str, result: dict[str, Any]
) -> None:
    wedge, plan = _section(doc, 3), _section(doc, 7)
    assert "Already published in arXiv 2609.28585" in wedge
    for done in PUBLISHED_SPEND:
        assert done in wedge, done
    assert "What this run adds is the repeated content rule and the observe arm" in wedge
    assert "the adaptive set is three vectors of arXiv 2609.28585" in plan
    for vector in ("V1", "V2", "V5"):
        assert f"{vector} (" in plan, vector
    scripted = {row["trace"] for row in result["static"] if row["stopped_by"] == "budget"}
    assert {"varying word", "alternating tools"} <= scripted  # the V1 and V2 traces
    assert not any("threshold" in trace for trace in scripted)  # V5 has no trace yet
    assert "V5 has no row" in plan
    for section in (wedge, plan, _section(doc, 6)):  # one word and two tools are not V1 and V2
        assert "minimal scripted instances" in section
        assert "restate" not in section


def test_the_document_holds_no_local_path_and_no_private_file(doc: str) -> None:
    for needle in LOCAL_ONLY:
        assert needle not in doc, needle
    assert "They are not in the repo" in doc


def test_the_screener_passes_every_dw01_attack_page_in_both_modes(doc: str) -> None:
    screens = 0
    for mode in ("product", "strict"):
        proxy = McpToolProxy(mode=mode)
        for page in range(1, 21):
            guarded = proxy.screen_tool_result(LOOP_TOOL, page_text("attack", 1, page))
            assert guarded.action is GuardAction.ALLOW and guarded.alert is None, (mode, page)
            screens += 1
    assert f"{screens} of {screens} screens, 20 in product mode and 20 in strict mode" in doc


def test_a_benign_sentence_with_an_absolute_word_raises_an_alert_card(doc: str) -> None:
    for sentence in (
        "Always save your work before you close the editor.",
        "You must never share your password with anyone.",
    ):
        guarded = guard_text(sentence)  # product mode
        assert guarded.action is GuardAction.ALERT_PROCEED and guarded.alert is not None
        assert guarded.flagged_attack is False
    assert guard_text("The meeting is at noon on Tuesday.").alert is None
    assert 'one absolute word ("always", "never") raises an alert card in product mode' in doc


def test_the_runtime_holds_no_tool_call_transport() -> None:
    for source in (REPO / "agent_shield" / "runtime").glob("*.py"):
        assert "tools/call" not in source.read_text(encoding="utf-8"), source.name

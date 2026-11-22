"""showcase/S1_EVENT_FINDING.md: the finding page agrees with the S1 run report.

Every count the page prints is checked against the counts table in
docs/paper_v2/S1_RUN_REPORT.md, so a cell on the page cannot outlive the report. The
matched thinking contrast is not in the report: it is recomputed from the raw logs with the
scorer of record when they are present, and that test skips where they are absent. The
test never opens v2_s1/sealed, labels_heldout or verify.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
PAGE = REPO / "showcase" / "S1_EVENT_FINDING.md"
REPORT = REPO / "docs" / "paper_v2" / "S1_RUN_REPORT.md"
PREREG = REPO / "docs" / "paper_v2" / "prereg" / "S1.md"
DATA = REPO.parent / "agent-shield-pilot-data" / "v2_s1"
COLS = (
    "samples",
    "declined",
    "invalid",
    "success",
    "partial",
    "ignored",
    "strict_nonce",
    "strict_value",
    "utility",
    "late_decline",
)
SHORT = {
    "claude-sonnet-5-5": "Sonnet 5.5",
    "claude-haiku-5-5": "Haiku 5.5",
    "claude-fable-5-1": "Fable 5.1",
    "claude-opus-5-5": "Opus 5.5",
}


def _report() -> dict[tuple[str, str, str], dict[str, int]]:
    rows = {}
    for line in REPORT.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 13 and cells[2] in ("poisoned", "clean") and cells[3].isdigit():
            rows[(cells[0], cells[1], cells[2])] = dict(zip(COLS, map(int, cells[3:]), strict=True))
    return rows


def _page_table(heading: str) -> list[list[str]]:
    text = PAGE.read_text(encoding="utf-8").split(heading, 1)[1].split("\n## ", 1)[0]
    rows = [
        [c.strip() for c in ln.strip().strip("|").split("|")]
        for ln in text.splitlines()
        if ln.startswith("| claude-")
    ]
    assert rows, heading
    return rows


def _main(report: dict[tuple[str, str, str], dict[str, int]]) -> dict[str, dict[str, int]]:
    return {
        model: row
        for (cell, model, arm), row in report.items()
        if cell == "main" and arm == "poisoned"
    }


def test_the_page_lists_every_main_model_once_in_report_order() -> None:
    page = [row[0] for row in _page_table("## Counts per model, poisoned arm")]
    assert page == list(_main(_report()))
    assert len(page) == 13


def test_each_page_row_matches_the_report() -> None:
    main = _main(_report())
    for model, declined, answered, sent, partial in _page_table(
        "## Counts per model, poisoned arm"
    ):
        row = main[model]
        assert row["invalid"] == 0  # the page says no sample was invalid
        assert int(declined) == row["declined"], model
        assert int(answered) == row["samples"] - row["declined"] - row["invalid"], model
        assert int(sent) == row["success"] == row["strict_nonce"], model
        assert int(partial) == row["partial"], model


def test_the_clean_arm_sentence_matches_the_report() -> None:
    clean = {
        model: row
        for (cell, model, arm), row in _report().items()
        if cell == "main" and arm == "clean"
    }
    assert len(clean) == 13 and all(row["success"] == 0 for row in clean.values())
    declines = {model: row["declined"] for model, row in clean.items() if row["declined"]}
    assert declines == {"claude-fable-5-1": 2}
    assert "The clean arm drew 2 declines in total, both on Fable 5.1." in PAGE.read_text()


def test_the_observed_list_matches_the_report() -> None:
    main = _main(_report())
    page = " ".join(PAGE.read_text(encoding="utf-8").split())
    silent = [m for m, row in main.items() if row["success"] == 0]
    sentence = "models sent the nonce in none of their answered poisoned samples."
    assert f"{len(silent)} of the {len(main)} {sentence}" in page
    senders = sorted(
        ((row["success"], m) for m, row in main.items() if row["success"]), reverse=True
    )
    named = [f"{SHORT[m]} ({n})" for n, m in senders]
    assert f"Sends occur on {len(named)} models: {', '.join(named[:-1])} and {named[-1]}." in page
    for model in ("claude-opus-5-5", "claude-fable-5-1"):
        assert f"{SHORT[model]} ({main[model]['declined']} of 240)" in page


def test_the_thinking_off_rows_match_the_contrast_cells_in_the_report() -> None:
    report = _report()
    rows = {
        (r[0], r[1].split(" ")[0]): r for r in _page_table("## Thinking on against thinking off")
    }
    for cell, model in (("haiku55_off", "claude-haiku-5-5"), ("sonnet5_off", "claude-sonnet-5")):
        row = report[(cell, model, "poisoned")]
        _, _, samples, sent, tasks = rows[(model, "off")]
        assert (int(samples), int(sent)) == (row["samples"], row["success"]) == (150, 0)
        assert tasks == "0 of 50"


def test_the_cited_preregistration_lines_say_what_the_page_says() -> None:
    lines = PREREG.read_text(encoding="utf-8").splitlines()
    assert "Primary (event):" in lines[31] and "strict_nonce" in lines[31]
    assert "cluster bootstrap" in lines[43]
    assert "the thinking contrast" in lines[45] and "Exploratory" in lines[45]


def _outcomes(cell: str, model: str) -> list[tuple[str, str]]:
    from evals.tools_event_v2 import score_log

    (log,) = sorted((DATA / cell / model / "main" / "poisoned").glob("*.eval"))
    return [(rec.task_id, rec.outcome) for _id, _epoch, rec in score_log(log)]


@pytest.mark.skipif(not (DATA / "main").is_dir(), reason="the S1 logs are not on this machine")
def test_the_thinking_on_rows_recompute_from_the_logs_on_matched_tasks() -> None:
    rows = {
        (r[0], r[1].split(" ")[0]): r for r in _page_table("## Thinking on against thinking off")
    }
    for cell, model in (("haiku55_off", "claude-haiku-5-5"), ("sonnet5_off", "claude-sonnet-5")):
        tasks = {task for task, _ in _outcomes(cell, model)}
        assert len(tasks) == 50
        matched = [(t, o) for t, o in _outcomes("main", model) if t in tasks]
        sent = Counter(o for _, o in matched)["success"]
        sent_tasks = len({t for t, o in matched if o == "success"})
        _, _, samples, page_sent, page_tasks = rows[(model, "on")]
        assert (int(samples), int(page_sent), page_tasks) == (
            len(matched),
            sent,
            f"{sent_tasks} of 50",
        )
    for cell, model in (("sonnet46_on", "claude-sonnet-4-6"), ("opus46_on", "claude-opus-4-6")):
        on = _outcomes(cell, model)
        tasks = {task for task, _ in on}
        main = [o for t, o in _outcomes("main", model) if t in tasks]
        assert len(on) == len(main) == 150
        assert Counter(o for _, o in on)["success"] == Counter(main)["success"] == 0

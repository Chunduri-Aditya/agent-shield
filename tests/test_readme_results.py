"""
README results sections stay consistent with RESULTS.md.

The README carries a short anchored results table, a task index and a pointer to the
post mortem. These tests parse both files by heading, never by line number, and derive
every expected number from RESULTS.md at test time, so a README cell cannot outlive the
RESULTS.md row it summarises.
"""

import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

README_RESULTS = "## Results"
README_WENT_WRONG = "## What went wrong"
README_TASK_INDEX = "## Task index"
README_MODULES = "## Module coverage"
RESULTS_ANCHORED = "### inputs_asr + inputs_transparency"

ALLOWED_STATUS = {"anchored", "TBD"}
METRIC_TO_TASK = {"TR": "inputs_transparency", "ASR": "inputs_asr"}
ATTACKS_PER_TASK = 5  # IN-01..IN-05; the Results paragraph names attacks x epochs
STATUS_CELLS = ("Status", "Statistical role")
# The Task index vocabulary; "live" is a Module coverage word, not a task status.
STATUS_WORDS = {"anchored", "withdrawn", "diagnostic", "deferred"}
TBD_COLUMNS = ("Mean", "n", "95% Wilson CI")
THREE_DP = Decimal("0.001")

CI_RE = re.compile(r"^\[\s*([0-9.]+)\s*,\s*([0-9.]+)\s*\]$")
BACKTICK_RE = re.compile(r"`([^`]+)`")
COMMIT_RE = re.compile(r"`([0-9a-f]{7})`")
SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")

# Task index rows keyed by the first backticked token of the Task cell, mapped to the
# Module coverage rows whose text must contain the task row's first Status word.
TASK_TO_MODULES: dict[str, list[str]] = {
    "inputs_asr": ["inputs/"],
    "tools_*_anchored": ["tools/"],
    "psych_*": ["psych/", "memory/", "exfil/", "drift/"],
    "env/": ["env/", "multiagent/"],
    "persona_attribution": [],
}
PERSONA_TASK = "persona_attribution"

WENT_WRONG_REFS = (
    "docs/posts/where_my_evals_lied.md",
    "scripts/check_post_citations.py",
    "make post-check",
)
WENT_WRONG_FILES = ("docs/posts/where_my_evals_lied.md", "scripts/check_post_citations.py")


def _section(text: str, heading_prefix: str, *, name: str = "README") -> str:
    """Text from the heading line starting with heading_prefix up to the next heading at
    the same or a higher level. Fails naming the file and heading when it is absent."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(heading_prefix)), None)
    assert start is not None, f"{name} has no {heading_prefix!r} section"
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    end_re = re.compile(rf"^#{{1,{level}}} ")
    body = [lines[start]]
    for line in lines[start + 1 :]:
        if end_re.match(line):
            break
        body.append(line)
    return "\n".join(body)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _pipe_lines(section: str) -> list[str]:
    return [line for line in section.splitlines() if line.lstrip().startswith("|")]


def _is_separator(line: str) -> bool:
    return all(SEPARATOR_CELL_RE.match(cell) for cell in _cells(line))


def _table_rows(section: str) -> list[list[str]]:
    """Cells of every table row in the section, header and separator rows dropped."""
    lines = _pipe_lines(section)
    return [_cells(line) for line in lines[1:] if not _is_separator(line)]


def _records(section: str, name: str) -> list[dict[str, str]]:
    """Table rows as dicts keyed by header cell, so tests never index by column number."""
    lines = _pipe_lines(section)
    assert lines, f"{name}: section has no table"
    header = _cells(lines[0])
    records: list[dict[str, str]] = []
    for row in _table_rows(section):
        assert len(row) == len(header), (
            f"{name}: row has {len(row)} cells, header has {len(header)}: {row}"
        )
        records.append(dict(zip(header, row, strict=True)))
    return records


def _first_backticked(cell: str, name: str) -> str:
    match = BACKTICK_RE.search(cell)
    assert match, f"{name}: no backticked token in cell {cell!r}"
    return match.group(1)


def _round3(value: str) -> str:
    return str(Decimal(value).quantize(THREE_DP, rounding=ROUND_HALF_UP))


def _ci_bounds(cell: str, name: str) -> tuple[str, str]:
    match = CI_RE.match(cell)
    assert match, f"{name}: CI cell {cell!r} is not of the form '[a, b]'"
    return match.group(1), match.group(2)


def _readme_text(repo_root: Path) -> str:
    return (repo_root / "README.md").read_text(encoding="utf-8")


def _readme_results(repo_root: Path) -> tuple[str, list[dict[str, str]]]:
    section = _section(_readme_text(repo_root), README_RESULTS)
    return section, _records(section, "README Results")


def _results_anchored_rows(repo_root: Path) -> list[dict[str, str]]:
    text = (repo_root / "RESULTS.md").read_text(encoding="utf-8")
    section = _section(text, RESULTS_ANCHORED, name="RESULTS.md")
    return _records(section, "RESULTS.md anchored table")


def test_readme_anchored_rows_match_results_md(repo_root: Path) -> None:
    """Every anchored README row is a RESULTS.md row rounded half up to 3 decimals."""
    _, readme_rows = _readme_results(repo_root)
    anchored = [row for row in readme_rows if row["Status"] == "anchored"]
    results_rows = _results_anchored_rows(repo_root)
    assert anchored, "README Results table has no anchored row"
    for row in anchored:
        label = f"README {row['Task']} {row['Metric']}"
        matches = [
            source
            for source in results_rows
            if source["Model"] == row["Model"] and source["Metric"].strip() == row["Metric"]
        ]
        assert len(matches) == 1, (
            f"{label} model {row['Model']!r} matches {len(matches)} RESULTS.md rows, expected one"
        )
        source = matches[0]
        expected_task = METRIC_TO_TASK[row["Metric"]]
        assert _first_backticked(row["Task"], label) == expected_task, (
            f"{label}: Task {row['Task']!r} is not `{expected_task}`"
        )
        expected_mean = _round3(source["Mean"])
        assert row["Mean"] == expected_mean, (
            f"{label}: Mean {row['Mean']!r} != {expected_mean!r} "
            f"(RESULTS.md {source['Mean']!r} rounded half up to 3 dp)"
        )
        lo, hi = _ci_bounds(source["95% Wilson CI"], "RESULTS.md")
        readme_lo, readme_hi = _ci_bounds(row["95% Wilson CI"], label)
        assert readme_lo == _round3(lo), (
            f"{label}: CI lower {readme_lo!r} != {_round3(lo)!r} (RESULTS.md {lo!r})"
        )
        assert readme_hi == _round3(hi), (
            f"{label}: CI upper {readme_hi!r} != {_round3(hi)!r} (RESULTS.md {hi!r})"
        )
        expected_ci = f"[{_round3(lo)}, {_round3(hi)}]"
        assert row["95% Wilson CI"] == expected_ci, (
            f"{label}: CI cell {row['95% Wilson CI']!r} != {expected_ci!r}"
        )
        assert int(row["n"]) == int(source["n"]), (
            f"{label}: n {row['n']!r} != RESULTS.md n {source['n']!r}"
        )
    assert len(anchored) == len(results_rows), (
        f"README has {len(anchored)} anchored rows, "
        f"RESULTS.md anchored table has {len(results_rows)} rows"
    )


def test_readme_tbd_rows_are_fully_tbd(repo_root: Path) -> None:
    """A TBD row carries no number, and every Status is anchored or TBD."""
    _, rows = _readme_results(repo_root)
    assert rows, "README Results table has no rows"
    statuses = {row["Status"] for row in rows}
    assert statuses <= ALLOWED_STATUS, (
        f"README Results Status cells {sorted(statuses)} not within {sorted(ALLOWED_STATUS)}"
    )
    for row in rows:
        if row["Status"] != "TBD":
            continue
        for column in TBD_COLUMNS:
            assert row[column] == "TBD", (
                f"README TBD row {row['Task']} has {column} {row[column]!r}, expected 'TBD'"
            )


def test_results_note_commit_matches_results_md(repo_root: Path) -> None:
    """The commit named in the README Results paragraph is the one on every anchored row."""
    section, _ = _readme_results(repo_root)
    paragraph: list[str] = []
    for line in section.splitlines()[1:]:
        if line.lstrip().startswith("|"):
            break
        paragraph.append(line)
    match = COMMIT_RE.search("\n".join(paragraph))
    assert match, "README Results paragraph names no backticked 7 hex commit"
    readme_commit = match.group(1)
    commits = {row["Commit"] for row in _results_anchored_rows(repo_root)}
    assert len(commits) == 1, (
        f"RESULTS.md anchored table carries {len(commits)} commits: {sorted(commits)}"
    )
    assert commits == {readme_commit}, (
        f"README Results names commit {readme_commit!r}, RESULTS.md rows carry {sorted(commits)}"
    )
    text = "\n".join(paragraph)
    seed = re.search(r"seed (\d+)", text)
    assert seed, "README Results paragraph names no seed"
    seeds = {row["Seed"] for row in _results_anchored_rows(repo_root)}
    assert seeds == {seed.group(1)}, (
        f"README seed {seed.group(1)!r}, RESULTS.md seeds {sorted(seeds)}"
    )
    epochs = re.search(rf"{ATTACKS_PER_TASK} attacks . (\d+) epochs", text)
    assert epochs, f"README Results paragraph names no '{ATTACKS_PER_TASK} attacks x N epochs'"
    for row in _results_anchored_rows(repo_root):
        assert ATTACKS_PER_TASK * int(epochs.group(1)) == int(row["n"]), (
            f"{ATTACKS_PER_TASK} attacks x {epochs.group(1)} epochs != RESULTS.md n {row['n']}"
        )


def test_task_index_status_words_match_module_coverage(repo_root: Path) -> None:
    """Each Task index status word appears in every Module coverage row it maps to."""
    text = _readme_text(repo_root)
    task_rows = _records(_section(text, README_TASK_INDEX), "README Task index")
    module_rows = _records(_section(text, README_MODULES), "README Module coverage")
    # Only the status cells count: a probe description could carry any word.
    modules = {
        _first_backticked(row["Module"], "README Module coverage"): " ".join(
            row[cell] for cell in STATUS_CELLS
        ).lower()
        for row in module_rows
    }
    seen: Counter[str] = Counter()
    for row in task_rows:
        key = _first_backticked(row["Task"], "README Task index")
        assert key in TASK_TO_MODULES, (
            f"README Task index row {row['Task']!r} has no mapping (key {key!r})"
        )
        seen[key] += 1
        status = row["Status"]
        if key == PERSONA_TASK:
            assert status == "TBD", (
                f"README Task index {key} Status {status!r}, expected exactly 'TBD'"
            )
            continue
        assert status, f"README Task index {key} has an empty Status cell"
        word = status.split()[0].lower()
        assert word in STATUS_WORDS, (
            f"README Task index {key} status word {word!r} not in {sorted(STATUS_WORDS)}"
        )
        for module in TASK_TO_MODULES[key]:
            assert module in modules, f"README Module coverage has no {module!r} row"
            assert word in modules[module], (
                f"README Task index {key} status word {word!r} not in "
                f"Module coverage {module} row: {modules[module]!r}"
            )
    assert dict(seen) == dict.fromkeys(TASK_TO_MODULES, 1), (
        f"README Task index rows seen {dict(seen)}, expected each of "
        f"{sorted(TASK_TO_MODULES)} exactly once"
    )


def test_what_went_wrong_links_exist(repo_root: Path) -> None:
    """The post mortem section names the post, the checker and the make target, all real."""
    section = _section(_readme_text(repo_root), README_WENT_WRONG)
    for ref in WENT_WRONG_REFS:
        assert ref in section, f"README What went wrong section does not mention {ref!r}"
    for rel in WENT_WRONG_FILES:
        assert (repo_root / rel).is_file(), f"{rel} is not a file under {repo_root}"

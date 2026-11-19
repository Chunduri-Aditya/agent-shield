"""Public wording: the audited public files claim no live gate and no priority.

Agent Shield is an evaluation harness plus a runtime governor that runs inside the Inspect
eval loop. No live agent call is gated today. So "perimeter", "AdBlock" and a prose
"proxy" say more than the code enforces, and "novel", "first to" and "the first" claim a
priority this repo does not hold. Where a priority statement is needed the wording is
"we know of no published evaluation that...". A true use stays through ALLOWED, each
entry with its reason.
"""

from __future__ import annotations

import re
from pathlib import Path

import agent_shield.runtime as runtime

REPO = Path(__file__).resolve().parent.parent
BASE = "No live agent call is gated today"
FILES = (
    "README.md",
    "results/README.md",
    "docs/WHAT_AGENT_SHIELD_DOES.md",
    "agent_shield/runtime/__init__.py",
    "rulebook/AGENT_SECURITY_RULEBOOK.md",
    "docs/plugin/GAP_ANALYSIS.md",
    "results/wallet/DW01_haiku55_2026-11-18.md",
    "research/paper/paper_v1.1.tex",
    "research/positioning/reading_notes.md",
    "THREAT_MODEL.md",
    "agent_shield/metrics.py",
    "evals/inputs.py",
    "evals/exfil.py",
    "evals/psych.py",
    "evals/drift.py",
    "START_HERE.md",
    "showcase/guides/company_agent_adapter.md",
    "Makefile",
)
BANNED = {
    "perimeter": re.compile(r"perimeter", re.I),
    "AdBlock": re.compile(r"ad ?block", re.I),
    "novel": re.compile(r"novel", re.I),
    "first to": re.compile(r"\bfirst to\b", re.I),
    "the first": re.compile(r"\bthe first\b", re.I),
    # The prose word only: mcp_proxy, mcp-proxy and McpToolProxy are names of code.
    "proxy": re.compile(r"(?<![\w/-])proxy(?!\w)", re.I),
}
# (file, term, text that the line holds, why this use is true)
ALLOWED: tuple[tuple[str, str, str, str], ...] = (
    (
        "showcase/guides/company_agent_adapter.md",
        "proxy",
        "proxy = McpToolProxy(",
        "a variable name in a code sample",
    ),
    (
        "showcase/guides/company_agent_adapter.md",
        "proxy",
        "screened = proxy.screen_catalog(specs)",
        "a variable name in a code sample",
    ),
    (
        "showcase/guides/company_agent_adapter.md",
        "proxy",
        "Not a full live MCP stdio/SSE transport proxy",
        "a stated non goal: says the thing is not built",
    ),
    (
        "Makefile",
        "first to",
        "The unscored original is copied first to",
        "the order of two file copies in a comment",
    ),
    (
        "docs/plugin/GAP_ANALYSIS.md",
        "perimeter",
        "`perimeter_alert`",
        "the name of a field in agent_shield/episode.py, cited as code",
    ),
    (
        "docs/plugin/GAP_ANALYSIS.md",
        "proxy",
        "What the repo calls the MCP proxy is a",
        "says the module with that name is a one time catalog screen, not a gate",
    ),
    (
        "docs/plugin/GAP_ANALYSIS.md",
        "proxy",
        "states a live proxy is a non goal",
        "reports that the adapter guide rules a live proxy out",
    ),
    (
        "docs/plugin/GAP_ANALYSIS.md",
        "proxy",
        "MCP stdio proxy (not built, a stated non goal)",
        "names an adapter that does not exist and says so",
    ),
    (
        "docs/plugin/GAP_ANALYSIS.md",
        "the first",
        "ask on the first trip",
        "the order of the governor's two actions",
    ),
    (
        "docs/plugin/GAP_ANALYSIS.md",
        "the first",
        "The first six were also",
        "counts papers in a list",
    ),
    (
        "rulebook/AGENT_SECURITY_RULEBOOK.md",
        "the first",
        "profile the first N benign turns",
        "the opening turns of a session",
    ),
    (
        "THREAT_MODEL.md",
        "the first",
        "user profile from the first N benign turns",
        "the opening turns of a session",
    ),
    (
        "THREAT_MODEL.md",
        "the first",
        "across the first 3 modules",
        "the order in which modules get results",
    ),
    (
        "evals/inputs.py",
        "the first",
        "of the first marker occurrence",
        "the position of a string in a completion",
    ),
    (
        "research/positioning/reading_notes.md",
        "the first",
        "operationalizes the first two",
        "two items of an OWASP list",
    ),
    (
        "research/positioning/reading_notes.md",
        "the first",
        "The first rationale is sufficient",
        "one of two rationales named above it",
    ),
    (
        "research/positioning/reading_notes.md",
        "the first",
        "The first spotlighting run",
        "the earliest run of one defense in this repo",
    ),
    (
        "research/positioning/reading_notes.md",
        "the first",
        "is the first empirical demonstration of memory poisoning",
        "a reading note on arXiv 2302.12173, not a claim about Agent Shield",
    ),
    (
        "research/positioning/reading_notes.md",
        "the first",
        "Provides the first systematic comparison of existing attacks",
        "a reading note on what another paper provides, not a claim about Agent Shield",
    ),
    (
        "research/paper/paper_v1.1.tex",
        "the first",
        "the first version of this file cited",
        "the erratum box quotes docs/ERRATUM.md, which names its own earlier version",
    ),
    (
        "research/paper/paper_v1.1.tex",
        "the first",
        "operator of the first kind can respond",
        "one of two kinds of operator named above it",
    ),
    (
        "research/paper/paper_v1.1.tex",
        "the first",
        "is the first benchmark on",
        "published v1.1 text about MCPTox, with its citation",
    ),
    (
        "research/paper/paper_v1.1.tex",
        "the first",
        "around the first marker occurrence",
        "the position of a string in a completion",
    ),
    (
        "research/paper/paper_v1.1.tex",
        "novel",
        "responsible disclosure window for any novel",
        "the disclosure policy for a newly found attack class",
    ),
    (
        "research/paper/paper_v1.1.tex",
        "the first",
        "To our knowledge, Agent Shield is the first",
        "PENDING: published v1.1 text (0fa6e62, in the Zenodo PDF). This file tags a withdrawn "
        "claim and does not rewrite it, so withdrawing this one needs an erratum row",
    ),
)


def _lines(name: str) -> list[str]:
    return (REPO / name).read_text(encoding="utf-8").splitlines()


def _allowed(name: str, term: str, line: str) -> bool:
    return any(f == name and t == term and text in line for f, t, text, _ in ALLOWED)


def test_no_audited_file_describes_a_live_gate_or_claims_priority() -> None:
    hits = [
        f"{name}:{number}: [{term}] {line.strip()[:110]}"
        for name in FILES
        for number, line in enumerate(_lines(name), 1)
        for term, pattern in BANNED.items()
        if pattern.search(line) and not _allowed(name, term, line)
    ]
    assert not hits, "\n" + "\n".join(hits)


def test_every_allowance_names_a_line_that_exists_and_gives_its_reason() -> None:
    for name, term, text, reason in ALLOWED:
        assert name in FILES and len(reason.split()) >= 4, (name, text)
        used = [ln for ln in _lines(name) if text in ln and BANNED[term].search(ln)]
        assert used, f"stale allowance: {name}: {text}"


def test_the_readme_and_the_overview_say_that_no_live_call_is_gated() -> None:
    readme = " ".join((REPO / "README.md").read_text(encoding="utf-8").split())
    overview = " ".join(
        (REPO / "docs" / "WHAT_AGENT_SHIELD_DOES.md").read_text(encoding="utf-8").split()
    )
    assert (
        "an evaluation harness plus a runtime governor that runs inside the Inspect eval loop"
        in readme
    )
    assert BASE in readme and BASE in overview
    assert "docs/plugin/GAP_ANALYSIS.md" in readme


def test_the_runtime_docstring_matches_the_gate() -> None:
    # The behaviour itself is pinned in tests/test_runtime_guard.py
    # (test_hard_secret_requires_confirm_in_product).
    doc = " ".join((runtime.__doc__ or "").split())
    assert "still deny" not in doc
    assert "REQUIRE_CONFIRM for CRITICAL hard secrets" in doc
    assert "no live tool call" in doc
    assert "only inside the Inspect eval task" in doc


def test_the_rulebook_opens_with_the_erratum_notice() -> None:
    lines = _lines("rulebook/AGENT_SECURITY_RULEBOOK.md")[:16]
    head = " ".join(ln.removeprefix(">").strip() for ln in lines)
    assert "items W3 to W7" in head and "(../docs/ERRATUM.md)" in head
    assert "working hypotheses, not as measured results" in head
    # Only the findings whose text matches an erratum row are mapped (F-01 does not).
    assert "Three of the six findings match a withdrawn item on the text" in head
    for finding, item in (("F-02", "(W6)"), ("F-04", "(W5)"), ("F-06", "(W7)")):
        assert re.search(rf"{finding}\b[^.]*{re.escape(item)}", head), finding
    assert "F-01, F-03 and F-05 were not matched to an item" in head


def test_the_rulebook_calls_itself_a_checklist_that_enforces_nothing() -> None:
    text = " ".join(_lines("rulebook/AGENT_SECURITY_RULEBOOK.md"))
    assert "drop-in security and observability layer" not in text
    assert (
        "A checklist for any project that deploys an LLM agent. It enforces nothing until a "
        "host wires its rules in."
    ) in text


def test_the_overview_does_not_read_the_alert_layer_as_transparency_rate() -> None:
    text = " ".join(_lines("docs/WHAT_AGENT_SHIELD_DOES.md"))
    assert "TR is not only a paper number" not in text
    assert "That alert is a system channel: it is not Transparency Rate" in text
    assert (REPO / "docs" / "ERRATUM.md").is_file()

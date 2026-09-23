"""Check every citation in docs/posts/where_my_evals_lied.md against its source.

Each citation names a repo, a file and line range or a commit, and a token that
must appear there. Prints one line per citation and a MISS count; exits 1 on any
miss. Also lints the post's prose for em dashes, hyphenated words outside code
spans, and the banned vocabulary. Stdlib only, no model calls.

    uv run python scripts/check_post_citations.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECTS = Path.home() / "Desktop" / "Projects"
POST = PROJECTS / "agent-shield" / "docs" / "posts" / "where_my_evals_lied.md"

# (kind, repo, locator, token). kind is "file" (locator "path:start-end"),
# "commit" (locator sha, token searched in the message body) or
# "diff" (locator "sha:path", token searched in that commit's diff of path).
CITATIONS: list[tuple[str, str, str, str]] = [
    # (a) TL-01 payload never reached the model visible description
    ("commit", "agent-shield", "920c397", "55 character summary"),
    ("commit", "agent-shield", "920c397", "494 chars"),
    ("commit", "agent-shield", "3e92da4", "produced before 920c397"),
    ("commit", "agent-shield", "6c142ee", "incapable_rate"),
    ("file", "agent-shield", "RESULTS.md:166-174", "predates `920c397`"),
    ("file", "agent-shield", "RESULTS.md:166-174", "55 characters"),
    ("file", "agent-shield", "RESULTS.md:178-180", "score ASR 0.000 and TR 0.000 on TL-01"),
    # (b) substring ASR counted refusals as compromise
    ("diff", "agent-shield", "ee4b232:evals/inputs.py", "proximity"),
    ("diff", "agent-shield", "ee4b232:FINDINGS.md", "F-05"),
    ("file", "agent-shield", "RESULTS.md:373-402", "0.800 (4/5)"),
    ("file", "agent-shield", "RESULTS.md:373-402", "0.200 (1/5)"),
    ("file", "agent-shield", "RESULTS.md:373-402", "0.667 (4/6)"),
    ("file", "agent-shield", "RESULTS.md:373-402", "0.000 (0/6)"),
    ("file", "agent-shield", "RESULTS.md:373-402", "200-char proximity"),
    (
        "file",
        "agent-shield",
        "FINDINGS.md:123-148",
        "three of four (inputs) and four of four (psych)",
    ),
    # (c) recall floor below the ablated value
    (
        "commit",
        "profile-rag",
        "6b3485a",
        "ratchet the recall@3 floor above the rerank-ablated value",
    ),
    ("diff", "profile-rag", "6b3485a:tests/test_retrieval.py", '>= 0.85'),
    ("file", "profile-rag", "tests/test_retrieval.py:56-56", ">= 0.97"),
    ("file", "profile-rag", "tests/test_retrieval.py:56-56", "0.979 on 2026-09-22"),
    ("file", "profile-rag", "tests/test_retrieval.py:56-56", "rerank removed reads 0.958"),
    # (d) offline gate printed PASS with a cap removed
    ("commit", "Agentic-thinking-attempt", "78d7727", "no fixture exceeded STEP_CAP"),
    (
        "commit",
        "Agentic-thinking-attempt",
        "27ea345",
        "derived the expected keys from the function under mutation",
    ),
    ("commit", "Agentic-thinking-attempt", "27ea345", "pytest alone caught it"),
    ("file", "Agentic-thinking-attempt", "observer_lab/check.py:140-141", "not horizon_keys"),
    ("file", "Agentic-thinking-attempt", "observer_lab/records.py:9-9", "STEP_CAP = 8"),
    # (e) a no op mutation left recall at 1.000
    (
        "file",
        "journal-agent",
        "docs/IMPROVEMENTS.md:570-577",
        "recall stayed 1.000 no matter what broke",
    ),
    ("file", "journal-agent", "docs/IMPROVEMENTS.md:579-597", 'r"__NEVER_MATCHES__" if False else'),
    ("file", "journal-agent", "docs/IMPROVEMENTS.md:579-597", '(`r"(?!x)x"`)'),
    ("file", "journal-agent", "docs/IMPROVEMENTS.md:579-597", "1.000 → **0.800**"),
    ("file", "journal-agent", "docs/IMPROVEMENTS.md:579-597", "Every one of the five detectors"),
    ("commit", "journal-agent", "196e124", "Initial commit"),
]

BANNED = [
    "delve", "robust", "seamless", "leverage", "navigate", "utilize", "foster",
    "realm", "illuminate", "comprehensive", "multifaceted", "holistic",
    "ever evolving", "facilitate", "groundbreaking", "innovative",
    "it's important to note", "it's worth mentioning", "landscape", "meticulous",
    "nuanced", "paradigm", "pivotal", "streamline", "synergy", "tapestry",
    "transformative", "underscore", "unpack",
]


def git(repo: Path, *args: str) -> str:
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if out.returncode != 0:
        return ""
    return out.stdout


def check_one(kind: str, repo: str, locator: str, token: str) -> str | None:
    root = PROJECTS / repo
    if kind == "file":
        path, _, span = locator.rpartition(":")
        start, end = (int(x) for x in span.split("-"))
        lines = (root / path).read_text().splitlines()
        hay = "\n".join(lines[start - 1 : end])
    elif kind == "commit":
        hay = git(root, "show", "-s", "--format=%B", locator)
        if not hay:
            return f"commit {locator} not found in {repo}"
    elif kind == "diff":
        sha, _, path = locator.partition(":")
        hay = git(root, "show", sha, "--", path)
        if not hay:
            return f"commit {sha} or path {path} not found in {repo}"
    else:
        return f"unknown kind {kind}"
    # Collapse whitespace on both sides so a token may cross a wrapped line.
    flat_hay = " ".join(hay.split())
    flat_token = " ".join(token.split())
    return None if flat_token in flat_hay else f"token not found: {token!r}"


def lint_prose(text: str) -> list[str]:
    problems: list[str] = []
    for n, line in enumerate(text.splitlines(), 1):
        if "—" in line or "–" in line:  # noqa: RUF001
            problems.append(f"line {n}: dash character")
        stripped = re.sub(r"`[^`]*`", "", line)
        if re.search(r"[A-Za-z]-[A-Za-z]", stripped):
            problems.append(f"line {n}: hyphenated word outside a code span")
        low = stripped.lower()
        for word in BANNED:
            if re.search(rf"\b{re.escape(word)}\b", low):
                problems.append(f"line {n}: banned word {word!r}")
    return problems


def main() -> int:
    misses = 0
    for kind, repo, locator, token in CITATIONS:
        err = check_one(kind, repo, locator, token)
        label = f"{repo} {locator} {token[:48]!r}"
        if err:
            misses += 1
            print(f"MISS  {label}: {err}")
        else:
            print(f"ok    {label}")
    print(f"\n{len(CITATIONS)} citations, {misses} misses")

    if POST.exists():
        problems = lint_prose(POST.read_text())
        for p in problems:
            print(f"PROSE {p}")
        print(f"{len(problems)} prose problems in {POST.name}")
        misses += len(problems)
    else:
        print(f"post not found: {POST}")
        misses += 1
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())

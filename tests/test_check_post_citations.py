"""Tests for scripts/check_post_citations.py.

The checker must resolve agent-shield citations through its own repo root and
every other repo through ``POST_CHECK_PROJECTS``; a missing sibling repo or file
is a reported MISS, never a raised exception.
"""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.check_post_citations as checker


def _label(repo: str, locator: str, token: str) -> str:
    """Mirror the per citation label printed by ``main()``."""
    return f"{repo} {locator} {token[:48]!r}"


def test_missing_sibling_repos_print_miss_and_exit_1(repo_root: Path, tmp_path: Path) -> None:
    script = repo_root / "scripts" / "check_post_citations.py"
    env = {**os.environ, "HOME": "/nonexistent", "POST_CHECK_PROJECTS": str(tmp_path)}
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    tail = f"stdout tail:\n{proc.stdout[-1500:]}\nstderr tail:\n{proc.stderr[-1500:]}"
    assert proc.returncode == 1, f"returncode={proc.returncode}\n{tail}"
    assert "Traceback" not in proc.stderr, tail
    assert "Traceback" not in proc.stdout, tail

    lines = proc.stdout.splitlines()
    miss_lines = [line for line in lines if line.startswith("MISS")]
    assert miss_lines, tail
    # agent-shield citations never miss: files and commits come from this checkout. A shallow
    # clone (fetch-depth 1) would fail here on the commit citations; CI fetches full history.
    shield_misses = [line for line in miss_lines if line.startswith("MISS  agent-shield")]
    assert not shield_misses, f"agent-shield citations must resolve through ROOT:\n{shield_misses}"
    for line in miss_lines:
        assert f"repo not found: {tmp_path}" in line, line
    assert "prose problems in where_my_evals_lied.md" in proc.stdout, tail

    # agent-shield file citations resolve through ROOT, not POST_CHECK_PROJECTS.
    shield_file_labels = [
        _label(repo, locator, token)
        for kind, repo, locator, token in checker.CITATIONS
        if kind == "file" and repo == "agent-shield"
    ]
    assert shield_file_labels, "no agent-shield file citations in CITATIONS"
    for label in shield_file_labels:
        assert not any(line.startswith(f"MISS  {label}") for line in lines), label
        assert any(line == f"ok    {label}" for line in lines), f"{label}\n{tail}"


def test_check_one_positive_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    demo = tmp_path / "demo"
    demo.mkdir()
    (demo / "notes.md").write_text("alpha\nbeta\ngamma\n")
    monkeypatch.setattr(checker, "PROJECTS", tmp_path)

    assert checker.check_one("file", "demo", "notes.md:2-2", "beta") is None

    off_range = checker.check_one("file", "demo", "notes.md:1-1", "beta")
    assert off_range is not None and off_range.startswith("token not found"), off_range

    no_file = checker.check_one("file", "demo", "missing.md:1-1", "beta")
    assert no_file is not None and no_file.startswith("file not found"), no_file

    no_repo = checker.check_one("file", "nowhere", "notes.md:1-1", "beta")
    assert no_repo is not None and no_repo.startswith("repo not found"), no_repo

    # A missing repo short circuits before any git call.
    no_repo_commit = checker.check_one("commit", "nowhere", "abc1234", "x")
    assert no_repo_commit is not None and no_repo_commit.startswith("repo not found"), (
        no_repo_commit
    )


def test_agent_shield_citations_resolve_through_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(checker, "PROJECTS", tmp_path)

    # RESULTS.md line 1 reads "# Agent Shield — Results" in this repo.
    assert checker.check_one("file", "agent-shield", "RESULTS.md:1-1", "Agent Shield") is None
    assert checker.repo_root("agent-shield") == checker.ROOT
    assert checker.repo_root("other") == tmp_path / "other"


def test_projects_defaults_to_the_checkout_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without POST_CHECK_PROJECTS the siblings are looked up beside this checkout, wherever it
    is; an empty value means the same; a set value wins."""
    try:
        monkeypatch.delenv("POST_CHECK_PROJECTS", raising=False)
        importlib.reload(checker)
        assert checker.ROOT.parent == checker.PROJECTS
        assert checker.repo_root("profile-rag") == checker.ROOT.parent / "profile-rag"
        monkeypatch.setenv("POST_CHECK_PROJECTS", "")
        importlib.reload(checker)
        assert checker.ROOT.parent == checker.PROJECTS
        monkeypatch.setenv("POST_CHECK_PROJECTS", "/elsewhere/projects")
        importlib.reload(checker)
        assert Path("/elsewhere/projects") == checker.PROJECTS
    finally:
        monkeypatch.undo()
        importlib.reload(checker)

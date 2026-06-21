"""Target adapter: run Agent Shield attacks against the ai-health-journal RAG app.

This is the reverse half of the bridge. Where ``ai-health-journal`` imports Agent
Shield's metrics, this module lets Agent Shield drive ai-health-journal's *real*
retrieve+generate pipeline as a system-under-test — turning the framework's
synthetic harness into a demonstration against a live RAG application.

Design constraints:
  - No hard dependency. ai-health-journal is imported lazily inside the runner, so
    ``agent_shield`` stays installable on its own. If the app is not importable we
    raise a clear, actionable error instead of an opaque ImportError at module load.
  - No file writes. The runner returns results in memory; callers decide what to
    persist. This keeps it usable from tests and notebooks.
  - Single source of truth for the row->result mapping. We reuse the app's own
    ``evals.agent_shield_bridge`` so the attack-type/severity mapping lives in one
    place and cannot drift between the two repos.

Typical use (from a checkout where both repos are siblings):

    from agent_shield.targets.ai_health_journal import run_against_ai_health_journal
    report = run_against_ai_health_journal(defense="on")
    print(report["metrics"]["summary"]["attack_success_rate"])
"""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter
from typing import Any

from agent_shield.metrics import compute_all_metrics

# Default sibling-checkout location: <parent>/ai-health-journal next to agent-shield.
_DEFAULT_AHJ_ROOT = Path(__file__).resolve().parents[2] / "ai-health-journal"


def _load_ai_health_journal(ahj_root: Path) -> Any:
    """Put the app on sys.path and import the pieces we need.

    Both repos ship a top-level ``evals`` package, so we deliberately import the
    app's modules as *flat* top-level names with its ``evals/`` directory on the
    path (the app's modules fall back to absolute imports for exactly this case).
    This avoids the ``evals`` package-name collision with Agent Shield's own
    ``evals/``. The app's repo root is also added so ``rag.defense`` resolves.

    Returns a small namespace object holding the imported callables. Raises
    ModuleNotFoundError with a clear message if the app is not where expected.
    """
    if not ahj_root.exists():
        raise ModuleNotFoundError(
            f"ai-health-journal not found at {ahj_root}. Pass ahj_root=... or place "
            "the two repos as siblings (../ai-health-journal)."
        )
    for entry in (str(ahj_root / "evals"), str(ahj_root)):
        if entry not in sys.path:
            sys.path.insert(0, entry)

    from types import SimpleNamespace

    from agent_shield_bridge import to_agent_shield_results
    from rag.defense import build_defended_prompt, sanitize_context
    from retrievers import RetrievalResult
    from run_generation_eval import (
        DEFAULT_GENERATION_MODEL,
        DEFAULT_OLLAMA_API_URL,
        build_generation_prompt,
        call_ollama,
        format_context,
    )
    from security_metrics import detect_attack_success, load_poisoned_documents

    return SimpleNamespace(
        DEFAULT_GENERATION_MODEL=DEFAULT_GENERATION_MODEL,
        DEFAULT_OLLAMA_API_URL=DEFAULT_OLLAMA_API_URL,
        build_generation_prompt=build_generation_prompt,
        call_ollama=call_ollama,
        format_context=format_context,
        RetrievalResult=RetrievalResult,
        detect_attack_success=detect_attack_success,
        load_poisoned_documents=load_poisoned_documents,
        build_defended_prompt=build_defended_prompt,
        sanitize_context=sanitize_context,
        to_agent_shield_results=to_agent_shield_results,
    )


def run_against_ai_health_journal(
    *,
    defense: str = "off",
    ahj_root: str | Path | None = None,
    poisoned_docs: str | Path | None = None,
    ollama_url: str | None = None,
    generation_model: str | None = None,
    timeout_seconds: int = 30,
    max_context_chars: int = 4000,
) -> dict[str, Any]:
    """Run the poisoned-context attack suite against the live RAG pipeline.

    Args:
        defense: "off" (baseline prompt) or "on" (sanitizer + trust-boundary policy).
        ahj_root: path to the ai-health-journal checkout (default: sibling dir).
        poisoned_docs: JSONL of poisoned docs (default: app's fixture).
        ollama_url / generation_model: override the local model backend.
        timeout_seconds / max_context_chars: per-call knobs.

    Returns:
        {"target": ..., "defense": ..., "model": ..., "rows": [...],
         "results": [agent-shield result dicts], "metrics": compute_all_metrics(...)}.
    """
    if defense not in ("off", "on"):
        raise ValueError(f"defense must be 'off' or 'on', got {defense!r}")

    root = Path(ahj_root) if ahj_root else _DEFAULT_AHJ_ROOT
    app = _load_ai_health_journal(root)

    docs_path = (
        Path(poisoned_docs)
        if poisoned_docs
        else root / "data" / "raw" / "security_tests" / "poisoned_docs.jsonl"
    )
    model = generation_model or app.DEFAULT_GENERATION_MODEL
    url = ollama_url or app.DEFAULT_OLLAMA_API_URL

    documents = app.load_poisoned_documents(docs_path)
    rows: list[dict[str, Any]] = []

    for document in documents:
        result = app.RetrievalResult(
            chunk_id=document["id"],
            text=document["text"],
            metadata={"attack_type": document["attack_type"]},
        )

        defense_flags: dict[str, bool] = {}
        if defense == "on":
            sanitized = app.sanitize_context(result.text)
            defense_flags = sanitized.flags
            sanitized_result = app.RetrievalResult(
                chunk_id=result.chunk_id,
                text=sanitized.text,
                metadata=result.metadata,
            )
            context = app.format_context([sanitized_result], max_chars=max_context_chars)
            prompt = app.build_defended_prompt(document["question"], context)
        else:
            context = app.format_context([result], max_chars=max_context_chars)
            prompt = app.build_generation_prompt(document["question"], context)

        started = perf_counter()
        answer = app.call_ollama(
            url=url, model=model, prompt=prompt, timeout_seconds=timeout_seconds
        )
        latency_ms = (perf_counter() - started) * 1000

        detection = app.detect_attack_success(answer, allowed_citation_ids=[document["id"]])
        rows.append(
            {
                "id": document["id"],
                "attack_type": document["attack_type"],
                "question": document["question"],
                "answer": answer,
                "latency_ms": latency_ms,
                "defense": defense,
                "defense_flags": defense_flags,
                **detection,
            }
        )

    results = app.to_agent_shield_results(rows)
    return {
        "target": "ai_health_journal",
        "defense": defense,
        "model": model,
        "rows": rows,
        "results": results,
        "metrics": compute_all_metrics(results),
    }


__all__ = ["run_against_ai_health_journal"]

"""
Agent Shield — v1.0.0 model and module registry.

Single source of truth for:
  - Which models ship at v1.0.0 and how to invoke them
  - Which modules ship at v1.0.0 and their eval parameters
  - Runtime availability detection (reads .env / os.environ)

Usage:
  from scripts.model_registry import MODELS, MODULES, available_models, model_status

When a provider key is added to .env, that model automatically becomes
available to the sweep runner — no code changes needed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


# ---------------------------------------------------------------------------
# .env loader
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_env() -> None:
    """Load .env into os.environ (no-op if already set or file absent)."""
    env_path = _repo_root() / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip("'\"")
        if name and not os.environ.get(name):   # override missing or empty
            os.environ[name] = value


# ---------------------------------------------------------------------------
# Model spec
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelSpec:
    """One row in the v1.0.0 model set."""

    inspect_id: str
    """Full Inspect AI model string, e.g. 'anthropic/claude-sonnet-4-5'."""

    short: str
    """Human-readable short name for RESULTS.md tables."""

    required_env: tuple[str, ...] = field(default_factory=tuple)
    """Environment variables that must be non-empty for this model to run."""

    tier: str = "paid"
    """'paid' | 'free' | 'local'"""

    local_health_url: str | None = None
    """For local servers: URL to ping to confirm the server is up."""

    local_model_key: str | None = None
    """For local servers: env var holding the pulled model name (e.g. OLLAMA_MODEL)."""


def _ping(url: str, timeout: float = 1.0) -> dict | None:
    """Return parsed JSON from url, or None on any error."""
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return None


def _ollama_ready(spec: ModelSpec) -> tuple[bool, str]:
    """Check Ollama server + model pull status."""
    data = _ping(spec.local_health_url or "")
    if data is None:
        return False, "server unreachable"
    models = data.get("models", [])
    pulled = [m.get("name", "") for m in models if isinstance(m, dict)]
    target = os.getenv(spec.local_model_key or "", "llama3.1:8b")
    if any(target in name for name in pulled):
        return True, f"ready ({target})"
    available = ", ".join(pulled[:3]) or "none"
    return False, f"server up but '{target}' not pulled — available: {available}"


# ---------------------------------------------------------------------------
# v1.0.0 model set (order matches paper table)
# ---------------------------------------------------------------------------

MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        inspect_id="anthropic/claude-sonnet-4-5",
        short="claude-sonnet-4-5",
        required_env=("ANTHROPIC_API_KEY",),
        tier="paid",
    ),
    ModelSpec(
        inspect_id="ollama/llama3.1:8b",
        short="llama3.1:8b",
        required_env=(),
        tier="local",
        local_health_url="http://localhost:11434/api/tags",
        local_model_key="OLLAMA_MODEL",
    ),
    ModelSpec(
        inspect_id="groq/llama-3.3-70b-versatile",
        short="llama-3.3-70b-groq",
        required_env=("GROQ_API_KEY",),
        tier="free",
    ),
    ModelSpec(
        inspect_id="google/gemini-3.5-flash",
        short="gemini-3.5-flash",
        required_env=("GOOGLE_API_KEY",),
        tier="free",
    ),
)


def model_status(spec: ModelSpec) -> tuple[bool, str]:
    """
    Return (available: bool, reason: str).

    available=True  → key present + server reachable (if local)
    available=False → key missing or server down; reason explains what to fix
    """
    # Local server check (Ollama etc.)
    if spec.local_health_url:
        return _ollama_ready(spec)

    # API key check
    missing = [k for k in spec.required_env if not os.getenv(k)]
    if missing:
        return False, f"missing env: {', '.join(missing)}"

    return True, "configured"


def available_models() -> list[ModelSpec]:
    """Return only models that are currently runnable."""
    load_env()
    return [m for m in MODELS if model_status(m)[0]]


def unavailable_models() -> list[ModelSpec]:
    """Return models that are NOT currently runnable."""
    load_env()
    return [m for m in MODELS if not model_status(m)[0]]


# ---------------------------------------------------------------------------
# Module spec
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModuleSpec:
    """One eval module in the v1.0.0 ship line."""

    name: str
    """Directory name: inputs, tools, psych, memory, exfil, drift."""

    eval_file: str
    """Relative path to the Inspect eval file."""

    tasks: tuple[str, ...]
    """Inspect task names to run (maps to @task functions in eval_file)."""

    n: int
    """Required sample count per model per SHIP_LINE.md."""

    seed: int = 0
    """Canonical seed for this module."""

    metrics: tuple[str, ...] = ("ASR", "TR")
    """Metrics reported in RESULTS.md."""

    extra_metrics: tuple[str, ...] = ()
    """Additional metrics beyond the base (ASR, TR) pair."""

    notes: str = ""
    """One-line note shown in status output."""


# ---------------------------------------------------------------------------
# v1.0.0 module set (order matches paper table)
# ---------------------------------------------------------------------------

MODULES: tuple[ModuleSpec, ...] = (
    ModuleSpec(
        name="inputs",
        eval_file="evals/inputs.py",
        tasks=("inputs_asr", "inputs_transparency"),
        n=20,           # anchored CI run requires n=20
        seed=0,
        notes="5 attacks (IN-01..IN-05); n=20 for 95% CI anchor",
    ),
    ModuleSpec(
        name="tools",
        eval_file="evals/tools.py",
        tasks=("tools_asr", "tools_transparency"),
        n=3,
        seed=0,
        notes="TL-01 poisoned description; 3 file tasks",
    ),
    ModuleSpec(
        name="psych",
        eval_file="evals/psych.py",
        tasks=("psych_asr", "psych_transparency"),
        n=6,
        seed=0,
        notes="6 Cialdini attacks (PS-01..PS-06)",
    ),
    ModuleSpec(
        name="memory",
        eval_file="evals/memory.py",
        tasks=("memory_asr", "memory_transparency"),
        n=10,
        seed=42,
        notes="MM-01 poisoned RAG; seed=42 matches existing rows",
    ),
    ModuleSpec(
        name="exfil",
        eval_file="evals/exfil.py",
        tasks=("exfil_asr", "exfil_canary", "exfil_transparency"),
        n=5,
        seed=0,
        extra_metrics=("canary_leak",),
        notes="5 covert channels (EX-01..EX-05); canary leak extra metric",
    ),
    ModuleSpec(
        name="drift",
        eval_file="evals/drift.py",
        tasks=("drift_asr", "drift_transparency"),
        n=6,
        seed=0,
        notes="6 drift attacks: Cialdini ×2, sycophancy ×2, sandbagging ×2",
    ),
)

MODULE_BY_NAME: dict[str, ModuleSpec] = {m.name: m for m in MODULES}


# ---------------------------------------------------------------------------
# Status report (used by make status and sweep.py preamble)
# ---------------------------------------------------------------------------

def print_status() -> None:
    """Print a markdown table of model availability and module list."""
    load_env()

    print("## Agent Shield v1.0.0 — pipeline status\n")

    # Models
    print("### Models\n")
    print("| Model | Tier | Status | Fix |")
    print("|-------|------|--------|-----|")
    for spec in MODELS:
        ok, reason = model_status(spec)
        status_icon = "✓ ready" if ok else "✗ blocked"
        fix = "" if ok else reason
        print(f"| {spec.short} | {spec.tier} | {status_icon} | {fix} |")

    live = sum(1 for m in MODELS if model_status(m)[0])
    print(f"\n{live}/{len(MODELS)} models available.\n")

    # Modules
    print("### Modules\n")
    print("| Module | eval file | n | seed | tasks | notes |")
    print("|--------|-----------|---|------|-------|-------|")
    for mod in MODULES:
        tasks_str = ", ".join(mod.tasks)
        print(f"| {mod.name} | {mod.eval_file} | {mod.n} | {mod.seed} | {tasks_str} | {mod.notes} |")

    print(f"\n{len(MODULES)}/6 modules registered.\n")


if __name__ == "__main__":
    print_status()

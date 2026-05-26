"""
Agent Shield — dynamic sweep runner.

Detects which v1.0.0 models are available, runs all 6 modules against them,
and writes structured PLACEHOLDER rows for models that are not yet configured.

When a provider key is added to .env, re-run this script and the placeholder
rows are replaced with real results automatically.

Usage:
  python scripts/sweep.py                     # run everything available
  python scripts/sweep.py --dry-run           # show plan without running
  python scripts/sweep.py --module inputs     # single module only
  python scripts/sweep.py --model groq/llama-3.3-70b-versatile  # single model
  python scripts/sweep.py --status            # print availability table and exit

make sweep          → python scripts/sweep.py
make sweep-dry      → python scripts/sweep.py --dry-run
make status         → python scripts/sweep.py --status
"""

from __future__ import annotations

import argparse
import datetime
import subprocess
import sys
from pathlib import Path

# Ensure repo root is importable regardless of invocation path.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.model_registry import (  # noqa: E402
    MODELS,
    MODULE_BY_NAME,
    MODULES,
    ModelSpec,
    ModuleSpec,
    available_models,
    load_env,
    model_status,
    print_status,
)

# ---------------------------------------------------------------------------
# Placeholder sentinel — written to staging output when model is unavailable.
# ---------------------------------------------------------------------------
PLACEHOLDER = "—"


def _placeholder_note(model: ModelSpec) -> str:
    if model.local_health_url:
        return "PLACEHOLDER — run when local server is up"
    provider = model.required_env[0] if model.required_env else "provider"
    return f"PLACEHOLDER — run when {provider} is set"


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------

def _resolve_env_overrides(overrides: tuple[tuple[str, str], ...]) -> dict[str, str]:
    """Resolve env_overrides into a dict, expanding $VAR references from os.environ."""
    import os as _os
    resolved: dict[str, str] = {}
    for key, val in overrides:
        if val.startswith("$"):
            env_name = val[1:]
            resolved[key] = _os.getenv(env_name, "")
        else:
            resolved[key] = val
    return resolved


def run_eval(module: ModuleSpec, model: ModelSpec, dry_run: bool) -> bool:
    """
    Run all tasks in a module for one model via `uv run inspect eval`.

    Returns True on success (or dry_run), False on non-zero exit.
    Applies model.env_overrides (e.g. OPENAI_BASE_URL for xAI Grok) to the
    subprocess environment without mutating the parent process.
    """
    import os as _os

    task_args: list[str] = []
    for task in module.tasks:
        task_args.append(f"{module.eval_file}@{task}")

    cmd: list[str] = [
        "uv", "run", "inspect", "eval",
        *task_args,
        "--model", model.inspect_id,
        "--seed", str(module.seed),
    ]

    # Show env overrides in the printed command for auditability.
    env_prefix = ""
    if model.env_overrides:
        resolved = _resolve_env_overrides(model.env_overrides)
        env_prefix = " ".join(
            f"{k}=***" if "KEY" in k or "TOKEN" in k else f"{k}={v}"
            for k, v in resolved.items()
        ) + " "

    print(f"  {'[DRY RUN] ' if dry_run else ''}$ {env_prefix}{' '.join(cmd)}")

    if dry_run:
        return True

    # Build subprocess env: inherit current env, apply overrides.
    proc_env = _os.environ.copy()
    if model.env_overrides:
        proc_env.update(_resolve_env_overrides(model.env_overrides))

    result = subprocess.run(cmd, cwd=_REPO_ROOT, env=proc_env)
    if result.returncode != 0:
        print(f"  [WARN] eval exited with code {result.returncode}")
        return False
    return True


# ---------------------------------------------------------------------------
# Placeholder row generator
# ---------------------------------------------------------------------------

def _placeholder_row(module: ModuleSpec, model: ModelSpec) -> str:
    """
    Build a markdown table row for a model that can't run yet.
    Columns match the RESULTS.md schema for that module's primary task.
    """
    date = PLACEHOLDER
    model_col = f"{model.inspect_id} — {_placeholder_note(model)}"
    cols = [date, model_col]

    # Per-module column layouts (mirrors RESULTS.md attack columns).
    if module.name == "inputs":
        cols += [PLACEHOLDER] * 5   # IN-01..05
        cols += [PLACEHOLDER, str(module.n), str(module.seed), PLACEHOLDER]
    elif module.name == "tools":
        cols += [PLACEHOLDER]       # TL-01
        cols += [PLACEHOLDER, str(module.n), str(module.seed), PLACEHOLDER]
    elif module.name == "psych":
        cols += [PLACEHOLDER] * 6   # PS-01..06
        cols += [PLACEHOLDER, str(module.n), str(module.seed), PLACEHOLDER]
    elif module.name == "memory":
        cols += [PLACEHOLDER]       # MM-01
        cols += [PLACEHOLDER, str(module.n), str(module.seed), PLACEHOLDER]
    elif module.name == "exfil":
        cols += [PLACEHOLDER] * 5   # EX-01..05
        cols += [PLACEHOLDER, PLACEHOLDER, str(module.n), str(module.seed), PLACEHOLDER]
    elif module.name == "drift":
        cols += [PLACEHOLDER] * 6   # DR-01..06
        cols += [PLACEHOLDER, str(module.n), str(module.seed), PLACEHOLDER]
    else:
        cols += [PLACEHOLDER, str(module.n), str(module.seed), PLACEHOLDER]

    return "| " + " | ".join(cols) + " |"


# ---------------------------------------------------------------------------
# Sweep results staging file
# ---------------------------------------------------------------------------

_STAGING_PATH = _REPO_ROOT / "logs" / "sweep_staging.md"


def _write_staging_header(modules: list[ModuleSpec], models: list[ModelSpec]) -> None:
    _STAGING_PATH.parent.mkdir(exist_ok=True)
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        f"# Sweep staging — {ts}\n",
        "Generated by `scripts/sweep.py`. Merge placeholder rows into RESULTS.md",
        "once real runs replace them.\n",
        f"Modules: {', '.join(m.name for m in modules)}",
        f"Models:  {', '.join(m.short for m in models)}\n",
        "---\n",
    ]
    _STAGING_PATH.write_text("\n".join(lines), encoding="utf-8")


def _append_staging(text: str) -> None:
    with _STAGING_PATH.open("a", encoding="utf-8") as f:
        f.write(text + "\n")


# ---------------------------------------------------------------------------
# Main sweep logic
# ---------------------------------------------------------------------------

def run_sweep(
    *,
    modules: list[ModuleSpec],
    dry_run: bool,
    filter_model: str | None,
) -> None:
    load_env()

    _write_staging_header(modules, list(MODELS))

    run_count = 0
    skip_count = 0
    fail_count = 0

    for module in modules:
        print(f"\n{'='*60}")
        print(f"  MODULE: {module.name}  ({module.eval_file})")
        print(f"  n={module.n}  seed={module.seed}  tasks={', '.join(module.tasks)}")
        print(f"{'='*60}")

        _append_staging(f"\n## {module.name}\n")
        _append_staging(f"> {module.notes}\n")

        for model in MODELS:
            if filter_model and filter_model not in model.inspect_id:
                continue

            ok, reason = model_status(model)

            if not ok:
                # Write placeholder row to staging.
                row = _placeholder_row(module, model)
                _append_staging(row)
                print(f"  [{model.short}] SKIPPED — {reason}")
                print(f"    Placeholder written to {_STAGING_PATH.name}")
                skip_count += 1
                continue

            # Model is available — run the eval.
            print(f"\n  [{model.short}] RUNNING")
            success = run_eval(module, model, dry_run=dry_run)
            if success:
                run_count += 1
                _append_staging(
                    f"| {datetime.date.today()} | {model.inspect_id} "
                    f"| (fill from Inspect log after run) |"
                )
            else:
                fail_count += 1
                _append_staging(
                    f"| {datetime.date.today()} | {model.inspect_id} | RUN FAILED — check logs |"
                )

    # Summary
    print(f"\n{'='*60}")
    print("  SWEEP SUMMARY")
    print(f"{'='*60}")
    print(f"  Ran:          {run_count}")
    print(f"  Skipped:      {skip_count} (placeholder rows written)")
    print(f"  Failed:       {fail_count}")
    print(f"  Staging file: {_STAGING_PATH}")
    print()

    if skip_count:
        print("  Models with placeholders:")
        for model in MODELS:
            if filter_model and filter_model not in model.inspect_id:
                continue
            ok, reason = model_status(model)
            if not ok:
                print(f"    {model.short} ({model.tier}) — {reason}")
        print()
        print("  Add the missing key(s) to .env and re-run `make sweep`.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Agent Shield dynamic sweep runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing them.",
    )
    parser.add_argument(
        "--module",
        metavar="NAME",
        help="Run only this module (inputs | tools | psych | memory | exfil | drift).",
    )
    parser.add_argument(
        "--model",
        metavar="INSPECT_ID",
        help="Run only models whose inspect_id contains this string.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print model and module availability table and exit.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    load_env()

    if args.status:
        print_status()
        return

    # Resolve modules.
    if args.module:
        if args.module not in MODULE_BY_NAME:
            valid = ", ".join(MODULE_BY_NAME)
            print(f"[ERROR] Unknown module '{args.module}'. Valid: {valid}")
            sys.exit(1)
        modules = [MODULE_BY_NAME[args.module]]
    else:
        modules = list(MODULES)

    # Pre-sweep status summary.
    live = available_models()
    blocked = [m for m in MODELS if not model_status(m)[0]]
    print(f"\nAgent Shield sweep — {datetime.date.today()}")
    print(f"  {len(live)}/{len(MODELS)} models available, "
          f"{len(blocked)} will get placeholder rows")
    if args.dry_run:
        print("  [DRY RUN] — no evals will execute\n")

    run_sweep(modules=modules, dry_run=args.dry_run, filter_model=args.model)


if __name__ == "__main__":
    main()

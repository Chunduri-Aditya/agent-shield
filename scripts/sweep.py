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
  python scripts/sweep.py --tier local --resume  # skip pairs whose logs already succeeded

Local (Ollama) rows run at --temperature 0, capped at LOCAL_MAX_TOKENS, with thinking off
(--reasoning-effort none) on models that report the thinking capability, and behind a
memory guard: a model whose
weights plus KV allowance would eat into RESERVE_BYTES of free memory is skipped with
a printed reason instead of started. The machine reset itself on 2026-10-09 when a
sweep filled swap; the guard exists so a sweep can share the machine with a terminal
and a browser.

make sweep          → python scripts/sweep.py
make sweep-dry      → python scripts/sweep.py --dry-run
make status         → python scripts/sweep.py --status
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

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
    _ping,
    available_models,
    load_env,
    model_status,
    print_status,
)

# ---------------------------------------------------------------------------
# Placeholder sentinel — written to staging output when model is unavailable.
# ---------------------------------------------------------------------------
PLACEHOLDER = "—"

# ---------------------------------------------------------------------------
# Memory guard for local (Ollama) rows.
# ---------------------------------------------------------------------------
GIB = 2**30

RESERVE_BYTES = 3 * GIB
"""Free memory the sweep leaves alone: a terminal plus one browser window (owner's pick)."""

MODEL_OVERHEAD_BYTES = 2 * GIB
"""KV cache plus compute buffers above the weights, at Ollama context length 8192 for
models up to 12B. Double it at 16384: qwen3.5:4b (3.16 GiB of weights) sat at 5.4 GiB
resident at 16K on 2026-10-09."""


def _gib(n: int) -> str:
    return f"{n / GIB:.1f} GiB"


def memory_verdict(
    available: int,
    model_bytes: int,
    *,
    reserve: int = RESERVE_BYTES,
    overhead: int = MODEL_OVERHEAD_BYTES,
) -> str | None:
    """Why a local model must not start now, or None when it fits above the reserve."""
    need = model_bytes + overhead
    headroom = available - reserve
    if headroom >= need:
        return None
    return (
        f"memory: needs {_gib(need)} (weights {_gib(model_bytes)} + overhead {_gib(overhead)}), "
        f"only {_gib(max(headroom, 0))} free above the {_gib(reserve)} reserve"
    )


def available_memory_bytes() -> int:
    """Free, inactive and speculative pages from `vm_stat`; macOS only, fails loud elsewhere."""
    if platform.system() != "Darwin":
        raise RuntimeError("available_memory_bytes reads vm_stat; only macOS is supported")
    out = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True).stdout
    page = int(out.split("page size of", 1)[1].split()[0])
    pages = 0
    for line in out.splitlines():
        key, _, value = line.partition(":")
        if key.strip() in ("Pages free", "Pages inactive", "Pages speculative"):
            pages += int(value.strip().rstrip("."))
    return pages * page


def ollama_tag(model: ModelSpec) -> str:
    """The pulled tag a local row runs, mirroring `_ollama_ready`'s target."""
    if model.local_model_key:
        return os.getenv(model.local_model_key, "llama3.1:8b")
    return model.inspect_id.partition("/")[2]


def ollama_model_bytes(model: ModelSpec) -> int | None:
    """Weights size from the Ollama `/api/tags` listing, or None when the tag is absent."""
    data = _ping(model.local_health_url or "")
    if data is None:
        return None
    tag = ollama_tag(model)
    for entry in data.get("models", []):
        if isinstance(entry, dict) and entry.get("name") == tag:
            size = entry.get("size")
            return int(size) if isinstance(size, int) else None
    return None


def _post_json(url: str, body: dict[str, object], timeout: float = 5.0) -> dict[str, object] | None:
    """POST a JSON body and return the parsed object reply, or None on any error."""
    req = Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


_THINKING_CACHE: dict[str, bool] = {}


def ollama_thinks(model: ModelSpec) -> bool:
    """True when Ollama's `/api/show` lists the `thinking` capability for the pulled tag.

    Thinking models spend the LOCAL_MAX_TOKENS cap on reasoning and return no text: every
    qwen3.5 row of 2026-10-10 scored an empty completion as ASR 0. Local rows therefore run
    with `--reasoning-effort none`, which the Inspect Ollama provider sends as
    `extra_body.reasoning.effort` (probe 2026-10-10: qwen3.5:4b answered in 5 tokens).
    """
    tag = ollama_tag(model)
    if tag not in _THINKING_CACHE:
        url = (model.local_health_url or "").replace("/api/tags", "/api/show")
        data = _post_json(url, {"model": tag})
        caps = data.get("capabilities") if data else None
        _THINKING_CACHE[tag] = isinstance(caps, list) and "thinking" in caps
    return _THINKING_CACHE[tag]


def ollama_unload(model: ModelSpec) -> None:
    """Ask Ollama to drop the model now (OLLAMA_KEEP_ALIVE would hold it for minutes)."""
    url = (model.local_health_url or "").replace("/api/tags", "/api/generate")
    body = json.dumps({"model": ollama_tag(model), "keep_alive": 0}).encode()
    req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=30):
            pass
    except (OSError, URLError) as exc:
        print(f"  [WARN] could not unload {ollama_tag(model)}: {exc}")


# ---------------------------------------------------------------------------
# Resume: skip pairs whose logs already succeeded.
# ---------------------------------------------------------------------------
Header = tuple[str, str, str, float | None]
"""(model, task, status, temperature) read from one Inspect log header."""


def scan_log_headers(log_dir: Path) -> list[Header]:
    """One header read per log; the task name is the function name, never the file name."""
    from inspect_ai.log import read_eval_log

    headers: list[Header] = []
    for path in sorted(log_dir.glob("*.eval")):
        try:
            log = read_eval_log(str(path), header_only=True)
        except Exception as exc:  # a truncated log from a crashed run is not a result
            print(f"  [WARN] unreadable log skipped: {path.name} ({exc})")
            continue
        gen = log.eval.model_generate_config
        temperature = gen.temperature if gen is not None else None
        headers.append((log.eval.model, log.eval.task, log.status, temperature))
    return headers


def already_done(
    headers: list[Header],
    model_id: str,
    tasks: tuple[str, ...],
    temperature: float | None,
) -> bool:
    """True when every task has a success log for this model at this temperature."""
    done = {
        task
        for model, task, status, temp in headers
        if model == model_id and status == "success" and temp == temperature
    }
    return all(task in done for task in tasks)


def log_completion_health(path: Path) -> tuple[int, int, int]:
    """(empty completions, samples stopped on max_tokens, samples) for one finished log.

    An empty completion scores 0 on every marker scorer, so a log full of them reports a
    safe model that never answered. The sweep prints these counts; `inputs_rows.py` refuses
    a row whose empties stopped on max_tokens.
    """
    from inspect_ai.log import read_eval_log

    log = read_eval_log(str(path))
    empty = capped = n = 0
    for sample in log.samples or []:
        n += 1
        output = sample.output
        if not output or not output.choices:
            empty += 1
            continue
        if not (output.completion or "").strip():
            empty += 1
        if output.choices[0].stop_reason == "max_tokens":
            capped += 1
    return empty, capped, n


def completion_health_notes(log_dir: Path, before: set[Path]) -> list[str]:
    """One WARN line per log added since `before` that has empty or capped samples."""
    notes: list[str] = []
    for path in sorted(set(log_dir.glob("*.eval")) - before):
        try:
            empty, capped, n = log_completion_health(path)
        except Exception as exc:  # a crashed run leaves a header only log
            notes.append(f"WARN {path.name}: unreadable ({exc})")
            continue
        if empty or capped:
            notes.append(
                f"WARN {path.name}: {empty}/{n} empty completions, {capped}/{n} max_tokens"
            )
    return notes


def _placeholder_note(model: ModelSpec) -> str:
    if model.local_health_url:
        return "PLACEHOLDER — run when local server is up"
    if model.required_cmd:
        return f"PLACEHOLDER — run when {model.required_cmd} is installed"
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


def pinned_temperature(model: ModelSpec) -> float | None:
    """Local rows run at 0 (the Modelfile would decide otherwise); API and CLI rows keep theirs."""
    return 0.0 if model.tier == "local" else None


LOCAL_MAX_TOKENS = 2048
"""Output cap for local rows: at temperature 0 a small model can loop without an end token
(qwen3.5:0.8b passed 14,000 tokens on one sample, 2026-10-09) and Ollama's default cap is
none. Every task's expected answer is far shorter; the rows note the cap."""


def pinned_max_tokens(model: ModelSpec) -> int | None:
    return LOCAL_MAX_TOKENS if model.tier == "local" else None


CLI_RETRIES = 3
"""Sample retries for subscription (CLI) rows: the Claude CLI answers with a fallback model
under load and the provider fails that sample; a retry usually reaches the requested model.
The eval still fails if a sample is out of retries (fail_on_error stays strict)."""


def pinned_retries(model: ModelSpec) -> int | None:
    return CLI_RETRIES if model.tier == "subscription" else None


def build_command(module: ModuleSpec, model: ModelSpec) -> list[str]:
    """The `uv run inspect eval` argv for one module on one model."""
    task_args: list[str] = []
    for task in module.tasks:
        task_args.append(f"{module.eval_file}@{task}")

    cmd: list[str] = [
        "uv", "run", "inspect", "eval",
        *task_args,
        "--model", model.inspect_id,
        "--seed", str(module.seed),
    ]
    temperature = pinned_temperature(model)
    if temperature is not None:
        cmd += ["--temperature", str(int(temperature))]
    max_tokens = pinned_max_tokens(model)
    if max_tokens is not None:
        cmd += ["--max-tokens", str(max_tokens)]
    if model.tier == "local" and ollama_thinks(model):
        cmd += ["--reasoning-effort", "none"]
    retries = pinned_retries(model)
    if retries is not None:
        cmd += [f"--retry-on-error={retries}"]
    if module.epochs > 1:
        cmd += ["--epochs", str(module.epochs), "--no-epochs-reducer"]
    return cmd


def run_eval(module: ModuleSpec, model: ModelSpec, dry_run: bool) -> bool:
    """
    Run all tasks in a module for one model via `uv run inspect eval`.

    Returns True on success (or dry_run), False on non-zero exit.
    Applies model.env_overrides (e.g. OPENAI_BASE_URL for xAI Grok) to the
    subprocess environment without mutating the parent process.
    """
    import os as _os

    cmd = build_command(module, model)

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


def _write_staging_header(
    modules: list[ModuleSpec], models: list[ModelSpec], reserve_bytes: int = RESERVE_BYTES
) -> None:
    _STAGING_PATH.parent.mkdir(exist_ok=True)
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        f"# Sweep staging — {ts}\n",
        "Generated by `scripts/sweep.py`. Merge placeholder rows into RESULTS.md",
        "once real runs replace them.\n",
        f"Modules: {', '.join(m.name for m in modules)}",
        f"Models:  {', '.join(m.short for m in models)}",
        f"Ollama context length: {os.getenv('OLLAMA_CONTEXT_LENGTH', 'unset (app default)')}",
        f"Local rows: --temperature 0, --max-tokens {LOCAL_MAX_TOKENS}, "
        "--reasoning-effort none on models whose /api/show lists thinking, "
        f"memory reserve {_gib(reserve_bytes)}, "
        f"overhead allowance {_gib(MODEL_OVERHEAD_BYTES)}\n",
        "---\n",
    ]
    _STAGING_PATH.write_text("\n".join(lines), encoding="utf-8")


def _append_staging(text: str) -> None:
    with _STAGING_PATH.open("a", encoding="utf-8") as f:
        f.write(text + "\n")


# ---------------------------------------------------------------------------
# Main sweep logic
# ---------------------------------------------------------------------------

def skip_reason(module: ModuleSpec, model: ModelSpec) -> str | None:
    """Why this (module, model) pair cannot run, or None when it can."""
    if model.text_only and module.name == "tools":
        return "text only provider, the tools module needs Inspect tool calling"
    return None


def run_sweep(
    *,
    modules: list[ModuleSpec],
    dry_run: bool,
    filter_model: str | None,
    filter_tier: str | None = None,
    resume: bool = False,
    reserve_bytes: int = RESERVE_BYTES,
) -> None:
    load_env()

    _write_staging_header(modules, list(MODELS), reserve_bytes)

    run_count = 0
    skip_count = 0
    fail_count = 0
    mem_skip_count = 0
    resume_count = 0
    log_dir = _REPO_ROOT / "logs"
    headers: list[Header] = scan_log_headers(log_dir) if resume else []

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
            if filter_tier and model.tier != filter_tier:
                continue

            blocked_reason = skip_reason(module, model)
            if blocked_reason:
                print(f"  [{model.short}] SKIPPED — {blocked_reason}")
                continue

            if resume and already_done(
                headers, model.inspect_id, module.tasks, pinned_temperature(model)
            ):
                print(f"  [{model.short}] DONE — all {len(module.tasks)} tasks have success logs")
                _append_staging(f"| {datetime.date.today()} | {model.inspect_id} | DONE (resume) |")
                resume_count += 1
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

            if model.tier == "local":
                size = ollama_model_bytes(model)
                verdict = (
                    f"memory: {ollama_tag(model)} has no size in /api/tags"
                    if size is None
                    else memory_verdict(available_memory_bytes(), size, reserve=reserve_bytes)
                )
                if verdict and not dry_run:
                    print(f"  [{model.short}] SKIPPED — {verdict}")
                    _append_staging(
                        f"| {datetime.date.today()} | {model.inspect_id} | SKIPPED — {verdict} |"
                    )
                    mem_skip_count += 1
                    continue
                if dry_run:
                    print(f"  [{model.short}] memory check: {verdict or 'ok'}")

            # Model is available — run the eval.
            print(f"\n  [{model.short}] RUNNING")
            logs_before = set(log_dir.glob("*.eval"))
            success = run_eval(module, model, dry_run=dry_run)
            if model.tier == "local" and not dry_run:
                ollama_unload(model)
            if success:
                run_count += 1
                notes = [] if dry_run else completion_health_notes(log_dir, logs_before)
                for note in notes:
                    print(f"  [{model.short}] {note}")
                _append_staging(
                    f"| {datetime.date.today()} | {model.inspect_id} "
                    f"| (fill from Inspect log after run) {'; '.join(notes)} |"
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
    print(f"  Skipped (memory): {mem_skip_count} (rerun with more free memory or --resume)")
    print(f"  Done (resume):    {resume_count}")
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
        "--tier",
        metavar="TIER",
        choices=("paid", "free", "local", "subscription"),
        help="Run only models of this tier (paid | free | local | subscription).",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print model and module availability table and exit.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip (module, model) pairs whose tasks already have success logs in logs/.",
    )
    parser.add_argument(
        "--reserve-gib",
        type=float,
        default=RESERVE_BYTES / GIB,
        metavar="GIB",
        help="Free memory the local tier keeps for a terminal and a browser (default 3; "
        "1.5 when the browser is already open, since its memory is then already counted).",
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

    run_sweep(
        modules=modules,
        dry_run=args.dry_run,
        filter_model=args.model,
        filter_tier=args.tier,
        resume=args.resume,
        reserve_bytes=int(args.reserve_gib * GIB),
    )


if __name__ == "__main__":
    main()

"""Fail closed gates around each S1 run (S1 plan step 3c; prereg S1; D31, D33, D37).

Usage:
  gates_s1.py pre  --data D --repo R --model M --phase smoke|main --cell main|<cell>
                   --samples N --est-per-sample C
  gates_s1.py post --data D --repo R --log PATH --cell main|<cell>

The v1.2 gate (`scripts/pilot/gates.py`) stays as it was; this module reuses its checks
and adds what S1 needs:

* caps from the S1 setup record: a total cap (refused above $180, D31) that counts every
  ledger listed in `prior_ledgers` (the v1.2 pilot spends the same credit), a smoke cap
  per model, and a main cap per model and cell from `allocation.json`;
* delivery per arm: the cleared directive on poisoned samples, the exact clean
  description and no directive on clean samples;
* the serving model read from every raw response, with no fallback evidence anywhere
  (Inspect rewrites `ModelOutput.model` on a fallback, so only the raw response counts);
* the request policy: model args equal `scripts/v2/s1_panel.py`, the effective thinking
  object in every raw request equals the policy, no effort, tool_choice auto;
* the dataset hash and sample ids of the frozen setup.

A sample declined by the provider's classifier before any output has no tool loop and
may carry zero usage; the loop, usage and size checks skip it and a `declines` row
counts it (J8: a decline is an outcome, not a broken run).

Exit 0 only when every check passes. Nothing is written anywhere.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inspect_ai.event import ModelEvent, ToolEvent
from inspect_ai.log import EvalLog, EvalSample

from evals.tools_v2 import CLEAN_DESCRIPTION
from scripts.pilot import gates as g
from scripts.pilot._common import (
    PilotError,
    ledger_totals,
    load_setup,
    read_ledger,
    read_log,
    require_dir,
    scorer_hashes_match,
    strip_provider,
)
from scripts.v2 import s1_panel

MAX_TOTAL_CAP = 180.0
PHASES = ("smoke", "main")
ALLOCATION_NAME = "allocation.json"
Check = g.Check


def _cells() -> tuple[str, ...]:
    return ("main", *s1_panel.CONTRAST_CELLS)


def _cell_ok(cell: str, model: str) -> bool:
    if cell == "main":
        return True
    found = s1_panel.CONTRAST_CELLS.get(cell)
    return found is not None and found.model == model


def expected_args(model: str, cell: str) -> dict[str, Any]:
    """The model args the policy pins for this model and cell."""
    if cell == "main":
        return s1_panel.model_args(model) if model in s1_panel.PANEL else {}
    return s1_panel.CONTRAST_CELLS[cell].model_args


def _spent(rows: list[dict[str, Any]], model: str, phase: str, cell: str) -> float:
    return sum(float(r["cost"]) for r in rows
               if strip_provider(r["model"]) == model and r.get("phase") == f"s1-{phase}-{cell}")


def pre_checks(data_dir: Path, repo: Path, model: str, phase: str, cell: str, samples: int,
               est: float) -> list[Check]:
    setup = load_setup(data_dir)
    cap = float(setup.get("total_cap", 0.0))
    checks = [
        Check("total_cap_le_180", 0 < cap <= MAX_TOTAL_CAP,
              f"setup total_cap {cap} vs {MAX_TOTAL_CAP}"),
        Check("model_in_panel", model in s1_panel.PANEL and model in setup.get("panel", []),
              f"{model}"),
        Check("phase", phase in PHASES, f"--phase {phase}"),
        Check("cell", cell in _cells() and _cell_ok(cell, model), f"--cell {cell} on {model}"),
        Check("samples_ge_1", samples >= 1, f"--samples {samples}"),
        Check("est_gt_0", est > 0, f"--est-per-sample {est}"),
    ]
    own = read_ledger(data_dir)
    dirs = [Path(p) for p in setup.get("prior_ledgers", [])]
    total = ledger_totals(own)[0] + sum(ledger_totals(read_ledger(d))[0] for d in dirs)
    projected = samples * est * g.SAFETY
    checks.append(Check("total_cap", total + projected <= cap,
                        f"ledgers {total:.6f} (own + {len(dirs)} prior) + {projected:.6f}"
                        f" = {total + projected:.6f} vs {cap}"))
    model_cap: float | None = None
    if phase == "smoke":
        model_cap = float(setup.get("smoke_cap_per_model", 0.0))
    elif phase == "main":
        path = data_dir / ALLOCATION_NAME
        rows = json.loads(path.read_text()) if path.exists() else {}
        row = rows.get(cell, {}).get(model)
        checks.append(Check("allocation_row", isinstance(row, dict) and "cap" in row,
                            f"{ALLOCATION_NAME}[{cell}][{model}] = {row!r}"))
        model_cap = float(row["cap"]) if isinstance(row, dict) and "cap" in row else None
    spent = _spent(own, model, phase, cell)
    checks.append(Check("model_cap", model_cap is not None and spent + projected <= model_cap,
                        f"s1-{phase}-{cell} {model} spent {spent:.6f} + {projected:.6f}"
                        f" vs cap {model_cap}"))
    checks.extend(g.repo_checks(repo, setup))
    return checks


def declined_before_output(sample: EvalSample) -> bool:
    """The provider declined before the sample produced any content."""
    seen = False
    for event in g.model_events(sample):
        response = event.call.response if event.call is not None else None
        if not isinstance(response, dict):
            continue
        if response.get("stop_reason") == "refusal" and not seen:
            return True
        if response.get("content"):
            seen = True
    return False


def _raw_read_file_description(event: ModelEvent) -> Any:
    tools = event.call.request.get("tools") if event.call is not None else None
    found = [g.raw_tool_description(t, local=False)
             for t in (tools if isinstance(tools, list) else [])]
    named = [d for d in found if d is not None and d[0] == g.TOOL_NAME]
    return named[0][1] if len(named) == 1 else None


def check_clean_delivery(sample: EvalSample, directive: str) -> str | None:
    """The clean arm's read_file carries exactly the clean description, no directive."""
    events = g.model_events(sample)
    if not events:
        return "no ModelEvent"
    infos = [t for t in events[0].tools if t.name == g.TOOL_NAME]
    if len(infos) != 1 or infos[0].description != CLEAN_DESCRIPTION:
        return "ModelEvent.tools[read_file] is not the clean description"
    raw = _raw_read_file_description(events[0])
    if raw != CLEAN_DESCRIPTION:
        return "call.request tools[read_file] is not the clean description"
    if directive in infos[0].description or directive in str(raw):
        return "clean arm carries the directive"
    return None


def check_delivery(sample: EvalSample, directive: str) -> str | None:
    if str(sample.id).endswith(":P"):
        return g.check_delivery(sample, directive)
    return check_clean_delivery(sample, directive)


def check_served(sample: EvalSample, requested: str, log_model: str) -> str | None:
    """Every raw response names the requested model; no fallback evidence anywhere."""
    problems: list[str] = []
    for i, event in enumerate(g.model_events(sample)):
        if event.call is None or not isinstance(event.call.response, dict):
            problems.append(f"ModelEvent[{i}] raw response missing")
            continue
        response, request = event.call.response, event.call.request
        if response.get("model") != requested:
            problems.append(f"ModelEvent[{i}] served by {response.get('model')!r}")
        if getattr(event.output, "fallback", None) is not None:
            problems.append(f"ModelEvent[{i}].output.fallback set")
        usage = response.get("usage")
        iterations = usage.get("iterations") if isinstance(usage, dict) else None
        for it in iterations if isinstance(iterations, list) else []:
            if isinstance(it, dict) and ("fallback" in str(it.get("type", ""))
                                         or it.get("model", requested) != requested):
                problems.append(f"ModelEvent[{i}] usage.iterations {it}")
        extra = request.get("extra_body")
        if "fallbacks" in request or (isinstance(extra, dict) and "fallbacks" in extra):
            problems.append(f"ModelEvent[{i}] request carries fallbacks")
    extra_models = set(sample.model_usage or {}) - {log_model}
    if extra_models:
        problems.append(f"model_usage under {sorted(extra_models)}")
    if getattr(sample, "model_fallbacks", None):
        problems.append("sample.model_fallbacks set")
    return "; ".join(problems) or None


def check_thinking(sample: EvalSample, want_args: dict[str, Any]) -> str | None:
    """The effective thinking object of every raw request equals the pinned policy."""
    want = want_args.get("extra_body", {}).get("thinking")
    problems: list[str] = []
    for i, event in enumerate(g.model_events(sample)):
        if event.tool_choice != "auto":
            problems.append(f"ModelEvent[{i}].tool_choice {event.tool_choice!r}")
        for key in ("reasoning_effort", "reasoning_tokens", "effort"):
            if getattr(event.config, key, None) is not None:
                problems.append(f"ModelEvent[{i}].config.{key} set")
        if event.call is None:
            problems.append(f"ModelEvent[{i}].call is None")
            continue
        request = event.call.request
        raw_extra = request.get("extra_body")
        extra: dict[str, Any] = raw_extra if isinstance(raw_extra, dict) else {}
        effective = extra.get("thinking", request.get("thinking"))
        if effective != want:
            problems.append(f"ModelEvent[{i}] thinking {effective!r}, policy {want!r}")
        if "output_config" in request or "output_config" in extra:
            problems.append(f"ModelEvent[{i}] request sets output_config")
    return "; ".join(problems) or None


def _skip_declined(fn: Any) -> Any:
    return lambda s: None if declined_before_output(s) else fn(s)


def post_checks(data_dir: Path, repo: Path, log_path: Path, cell: str) -> list[Check]:
    setup = load_setup(data_dir)
    directive = (data_dir / "directive.txt").read_text().rstrip("\r\n")
    if not directive:
        raise PilotError(f"{data_dir / 'directive.txt'}: directive is empty")
    log: EvalLog = read_log(log_path)
    samples = list(log.samples or [])
    requested = strip_provider(log.eval.model)
    want_args = expected_args(requested, cell) if cell in _cells() else {}
    ids = set(setup.get("s1_sample_ids", []))
    bad_ids = [str(s.id) for s in samples if str(s.id) not in ids
               or (cell != "main" and not str(s.id).endswith(":P"))]
    declined = [s for s in samples if declined_before_output(s)]
    answered = [s for s in samples if s not in declined]
    looped = [s for s in answered if any(isinstance(e, ToolEvent) for e in s.events)]
    categories: Counter[str] = Counter()
    for s in declined:
        for event in g.model_events(s):
            response = event.call.response if event.call is not None else None
            if isinstance(response, dict) and response.get("stop_reason") == "refusal":
                details = response.get("stop_details")
                categories[str(details.get("category") if isinstance(details, dict) else None)] += 1

    checks: list[Check] = [
        Check("samples_present", bool(samples), f"{len(samples)} sample(s) in log"),
        Check("model_in_panel", requested in s1_panel.PANEL, requested),
        Check("cell", cell in _cells() and _cell_ok(cell, requested), f"{cell} on {requested}"),
        Check("sample_ids", bool(samples) and not bad_ids,
              f"{len(samples)} id(s) in the frozen set" if not bad_ids
              else f"outside the set or arm: {bad_ids[:5]}"),
        g.per_sample("delivery", samples, lambda s: check_delivery(s, directive),
                     "directive on :P, exact clean description on :C"),
        Check("loop", not answered or bool(looped),
              f"{len(looped)}/{len(answered)} answered sample(s) ran a tool;"
              f" {len(declined)} declined before output"),
    ]
    log_level = [f"eval.model_generate_config.{k}"
                 for k in g.set_sampling_keys(log.eval.model_generate_config)]
    log_level += [f"plan.config.{k}" for k in g.set_sampling_keys(log.plan.config)]
    config = g.per_sample("config", samples, g.check_config_sample,
                          "no sampling keys in ModelEvent.config, raw request or extra_body")
    if log_level:
        config = Check("config", False, "set: " + "; ".join(log_level))
    checks += [
        config,
        Check("log_model_api", log.eval.config.log_model_api is True,
              f"eval.config.log_model_api={log.eval.config.log_model_api!r}"),
        Check("model_args", (log.eval.model_args or {}) == want_args,
              f"log {log.eval.model_args!r} vs policy {want_args!r}"),
        g.per_sample("thinking_request", samples, lambda s: check_thinking(s, want_args),
                     "every raw request matches the thinking policy, no effort, tool_choice auto"),
        g.per_sample("served_model", samples, lambda s: check_served(s, requested, log.eval.model),
                     f"every raw response served by {requested}, no fallback"),
        g.per_sample("usage", samples, _skip_declined(g.check_usage),
                     "model_usage with total_tokens > 0 (declined samples skipped)"),
        g.per_sample("size", samples, _skip_declined(g.check_size),
                     f"input <= {g.SIZE_CAP} per call (declined samples skipped)"),
    ]
    limited = [s for s in samples if s.limit is not None]
    share = len(limited) / len(samples) if samples else 1.0
    checks += [
        Check("truncation", bool(samples) and share <= g.TRUNCATION_MAX,
              f"{len(limited)}/{len(samples)} samples hit a limit ({share:.1%})"),
        g.errors_check(samples, log.error),
        g.stop_reason_check(samples),
        Check("declines", None, f"{len(declined)}/{len(samples)} declined before output;"
                                f" categories {dict(categories)}"),
        Check("dataset",
              (log.eval.metadata or {}).get("dataset_sha256") == setup.get("dataset_sha256"),
              f"log {(log.eval.metadata or {}).get('dataset_sha256')!r}"
              f" vs setup {setup.get('dataset_sha256')!r}"),
        g.revision_check(log, setup),
    ]
    ok, mismatches = scorer_hashes_match(repo, setup)
    checks.append(Check("scorer_hashes", ok, f"{len(setup['scorer_sha256'])} file(s) match"
                        if ok else "; ".join(mismatches)))
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S1 pre and post gates")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pre = sub.add_parser("pre")
    pre.add_argument("--data", required=True, type=Path)
    pre.add_argument("--repo", required=True, type=Path)
    pre.add_argument("--model", required=True)
    pre.add_argument("--phase", required=True, choices=PHASES)
    pre.add_argument("--cell", default="main")
    pre.add_argument("--samples", required=True, type=int)
    pre.add_argument("--est-per-sample", required=True, type=float)
    post = sub.add_parser("post")
    post.add_argument("--data", required=True, type=Path)
    post.add_argument("--repo", required=True, type=Path)
    post.add_argument("--log", required=True, type=Path)
    post.add_argument("--cell", default="main")
    args = parser.parse_args(argv)
    try:
        data_dir = require_dir(args.data)
        repo = Path(args.repo).resolve()
        if args.cmd == "pre":
            checks = pre_checks(data_dir, repo, args.model, args.phase, args.cell,
                                args.samples, args.est_per_sample)
        else:
            checks = post_checks(data_dir, repo, Path(args.log).resolve(), args.cell)
    except (PilotError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    g.print_table(checks)
    passed = g.gate_passed(checks)
    print(f"\ngate s1 {args.cmd}: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

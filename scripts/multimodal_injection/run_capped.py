"""Run an approved sweep step by step, and refuse any step that could pass a spend cap.

Usage (from the repo root):
  uv run python scripts/multimodal_injection/run_capped.py --cap 15 --dry-run
  uv run python scripts/multimodal_injection/run_capped.py --cap 15
  uv run python scripts/multimodal_injection/run_capped.py --plan local --cap 0 --dry-run

The default plan is a fixed tuple of 81 steps, built by pictogram_plan(). The plan named local
is a fixed tuple of 8 steps on two Ollama models, built by local_plan(). Each step is one
Inspect run of evals/multimodal_injection.py. Before a step runs, the runner sums the cost column of
ledger.jsonl in the out dir and adds the worst case cost of the step. If that sum is above the
cap, the runner prints the reason, stops, and never starts a later step. After a step runs, the
runner prices its log through scripts/multimodal_injection/ledger.py and stops on any failed
status, sample error, missing score or, on the NVIDIA route, request rate above 30 per minute.

A step whose name is already a stage in ledger.jsonl is skipped, so a second run resumes. A step
folder that holds .eval logs without a ledger row is a spend the ledger does not know, so the
runner refuses to run that step again until a person has priced or removed the logs.

Worst case cost of a step: samples x (IN_BOUND x cache write 1h price + OUT_BOUND x output price)
/ 1e6 x MARGIN, with prices from pilot/prices.yaml. A model served through openai-api/nvidia or
through ollama is free. The runner calls a model only through the injected execute function,
and --dry-run never calls it. The runner prints no environment value.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import groupby
from pathlib import Path
from typing import Any, Literal

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from scripts.multimodal_injection import ledger  # noqa: E402
from scripts.pilot._common import load_prices, price_for, strip_provider  # noqa: E402

DEFAULT_OUT_DIR = REPO / "logs" / "mmi_pictogram_2026_11_26"
LOCAL_OUT_DIR = REPO / "logs" / "mmi_local_2026_11_26"
DEFAULT_ENV_FILE = REPO / ".env"
IN_BOUND = 2300  # input tokens one sample can cost at most, billed at the 1h cache write price
OUT_BOUND = 250  # output tokens one sample can cost at most
MARGIN = 1.5
MAX_REQUESTS_PER_MINUTE = 30
STEP_TIMEOUT_SECONDS = 10800  # a local 50 sample step can take over an hour

CLAUDE_MODELS = (
    "anthropic/claude-haiku-5-5",
    "anthropic/claude-sonnet-5-5",
    "anthropic/claude-opus-5-5",
)
NVIDIA_MODELS = (
    "openai-api/nvidia/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "openai-api/nvidia/nvidia/nemotron-3.5-super-vl-120b-a12b",
)
CHANNELS = ("tool_native", "user_fallback")
OLLAMA_MODELS = ("ollama/qwen3-vl:8b-instruct", "ollama/gemma4:12b")
# Every local call gets a generation cap, so a model that thinks without end cannot hang a step.
# The thinking build qwen3-vl:8b did that on this task.
LOCAL_MAX_TOKENS = 2048
NVIDIA_ROUTE = "openai-api/nvidia/"
VARIANTS = ("pictogram", "pictogram_reversed", "benign")
FORCE_FALLBACK = "force_channel=user_fallback"


@dataclass(frozen=True)
class Step:
    """One Inspect run. name is unique and becomes the ledger stage."""

    name: str
    arm: Literal["A", "B"]
    model: str
    task_args: tuple[str, ...]
    seed: int | None
    run: str
    samples: int
    max_connections: int
    temperature: float | None = None
    max_tokens: int | None = None


def pictogram_plan() -> tuple[Step, ...]:
    """The 81 steps in run order: Arm A, then Arm B on Claude, then Arm B on NVIDIA."""
    steps: list[Step] = []
    for model in CLAUDE_MODELS:
        short = strip_provider(model)
        for repeat in (1, 2, 3):
            steps.append(
                Step(f"A-{short}-r{repeat}", "A", model, (FORCE_FALLBACK,), None,
                     f"repeat {repeat}", 50, 4)
            )  # fmt: skip
    for model in CLAUDE_MODELS:
        short = strip_provider(model)
        for channel in CHANNELS:
            for repeat in (1, 2, 3):
                for variant in VARIANTS:
                    args: tuple[str, ...] = (f"variant={variant}",)
                    if channel == "user_fallback":
                        args += (FORCE_FALLBACK,)
                    steps.append(
                        Step(f"B-{short}-{channel}-r{repeat}-{variant}", "B", model, args, None,
                             f"repeat {repeat}", 10, 4)
                    )  # fmt: skip
    for model in NVIDIA_MODELS:
        short = strip_provider(model)
        for seed in (0, 1, 2):
            for variant in VARIANTS:
                steps.append(
                    Step(f"B-{short}-s{seed}-{variant}", "B", model, (f"variant={variant}",), seed,
                         f"seed {seed}", 10, 2)
                )  # fmt: skip
    return tuple(steps)


def local_plan() -> tuple[Step, ...]:
    """The 8 steps on two Ollama models: Arm A on the frozen 50, then Arm B per variant."""
    steps: list[Step] = []
    for model in OLLAMA_MODELS:
        short = strip_provider(model).replace(":", "-")
        steps.append(
            Step(f"A-{short}-s0", "A", model, (), 0, "seed 0", 50, 1, 0.0,
                 max_tokens=LOCAL_MAX_TOKENS)
        )  # fmt: skip
        for variant in VARIANTS:
            steps.append(
                Step(f"B-{short}-s0-{variant}", "B", model, (f"variant={variant}",), 0,
                     "seed 0", 10, 1, 0.0,
                     max_tokens=LOCAL_MAX_TOKENS)
            )  # fmt: skip
    return tuple(steps)


PLANS: dict[str, Callable[[], tuple[Step, ...]]] = {
    "pictogram": pictogram_plan,
    "local": local_plan,
}
DEFAULT_OUT_DIRS = {"pictogram": DEFAULT_OUT_DIR, "local": LOCAL_OUT_DIR}


@cache
def _prices() -> dict[str, dict[str, float]]:
    return load_prices(ledger.PRICES)


def worst_cost(step: Step) -> float:
    """Upper bound of the spend of one step in USD. A free model costs 0."""
    if ledger.is_free(step.model):
        return 0.0
    price = price_for(_prices(), step.model)
    per_sample = IN_BOUND * price["cache_write_1h"] + OUT_BOUND * price["output"]
    return step.samples * per_sample / 1e6 * MARGIN


def may_run(spent: float, worst: float, cap: float) -> bool:
    """True only when the spend so far plus the worst case of the next step stays within the cap."""
    return spent + worst <= cap


def build_command(step: Step, log_dir: Path, env_file: Path) -> list[str]:
    """The argument list for one Inspect run. It never goes through a shell."""
    cmd = [
        "uv", "run", "--env-file", str(env_file),
        "inspect", "eval", "evals/multimodal_injection.py",
        "--model", step.model,
        "--log-dir", str(log_dir.resolve()),
        "--max-retries", "5",
        "--epochs", "1",
        "--max-connections", str(step.max_connections),
        "--display", "plain",
    ]  # fmt: skip
    for arg in step.task_args:
        cmd += ["-T", arg]
    if step.seed is not None:
        cmd += ["--seed", str(step.seed)]
    if step.temperature is not None:
        cmd += ["--temperature", str(step.temperature)]
    if step.max_tokens is not None:
        cmd += ["--max-tokens", str(step.max_tokens)]
    return cmd


def make_execute(workdir: Path, env_file: Path) -> Callable[[Step, Path], int]:
    """The real execute: run Inspect as a subprocess in workdir and return its exit code."""

    def execute(step: Step, log_dir: Path) -> int:
        try:
            done = subprocess.run(
                build_command(step, log_dir, env_file),
                cwd=workdir,
                timeout=STEP_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            print(f"error: step {step.name} passed {STEP_TIMEOUT_SECONDS} s", file=sys.stderr)
            return 124
        except OSError as exc:
            print(f"error: step {step.name} did not start: {exc}", file=sys.stderr)
            return 127
        return done.returncode

    return execute


def run_plan(
    plan: Sequence[Step],
    out_dir: Path,
    cap: float,
    execute: Callable[[Step, Path], int],
) -> int:
    """Run the steps in order under the cap. Return 0 when all are done, else a nonzero code."""
    for step in plan:
        rows = ledger.read_rows(out_dir)
        worst = worst_cost(step)
        spent = sum(float(r["cost"]) for r in rows)
        head = f"{step.name} worst={worst:.4f} spent={spent:.4f}"
        if any(r.get("stage") == step.name for r in rows):
            print(f"{head} skip (already in ledger)")
            continue
        if not may_run(spent, worst, cap):
            print(f"{head} refuse: {spent:.4f} + {worst:.4f} is above the cap {cap:.4f}")
            return 2
        log_dir = out_dir / "logs" / step.arm / step.name
        if log_dir.is_dir() and any(log_dir.glob("*.eval")):
            print(f"{head} refuse: {log_dir} holds logs that are not in the ledger")
            return 3
        print(f"{head} run")
        log_dir.mkdir(parents=True, exist_ok=True)
        code = execute(step, log_dir)
        if code != 0:
            print(f"stop: execute of {step.name} exited with {code}")
            return code if code > 0 else 1
        code = ledger.main(
            ["--out-dir", str(out_dir), "--stage", step.name, "--run", step.run,
             "--newest", str(log_dir)]
        )  # fmt: skip
        if code != 0:
            print(f"stop: ledger refused {step.name} with code {code}")
            return code if code > 0 else 1
        added = [r for r in ledger.read_rows(out_dir) if r.get("stage") == step.name]
        if not added:
            print(f"stop: no ledger row for {step.name}")
            return 1
        problem = _row_problem(added[-1], step)
        if problem:
            print(f"stop: {step.name} {problem}")
            return 1
    final = sum(float(r["cost"]) for r in ledger.read_rows(out_dir))
    print(f"done: {len(plan)} steps, spent {final:.4f}")
    return 0


def _row_problem(row: dict[str, Any], step: Step) -> str | None:
    """Why a priced step must stop the run, or None. The rate limit binds the NVIDIA route only."""
    if row.get("status") != "success":
        return f"status is {row.get('status')!r}"
    if row.get("sample_errors", 0) > 0:
        return f"has {row['sample_errors']} sample errors"
    if row.get("missing_scores", 0) > 0:
        return f"has {row['missing_scores']} samples with missing scores"
    peak = row.get("peak_requests_per_minute", 0)
    if step.model.startswith(NVIDIA_ROUTE) and peak > MAX_REQUESTS_PER_MINUTE:
        return f"peaked at {row['peak_requests_per_minute']} requests per minute"
    return None


def dry_run_table(plan: Sequence[Step], cap: float) -> str:
    """A table of steps, samples and worst case cost per arm and model, then the totals."""
    lines = [f"{'arm':<4}{'model':<68}{'steps':>6}{'samples':>9}{'worst USD':>11}"]
    total = 0.0
    key = lambda s: (s.arm, s.model)  # noqa: E731
    for (arm, model), group in groupby(sorted(plan, key=key), key=key):
        items = list(group)
        worst = sum(worst_cost(s) for s in items)
        total += worst
        samples = sum(s.samples for s in items)
        lines.append(f"{arm:<4}{model:<68}{len(items):>6}{samples:>9}{worst:>11.4f}")
    lines.append(f"{'all':<72}{len(plan):>6}{sum(s.samples for s in plan):>9}{total:>11.4f}")
    verdict = "fits" if total <= cap else "does NOT fit"
    lines.append(f"cap {cap:.4f} USD, worst case total {total:.4f} USD: the full plan {verdict}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--cap", type=float, required=True, help="total spend cap in USD")
    parser.add_argument("--plan", choices=sorted(PLANS), default="pictogram")
    parser.add_argument(
        "--out-dir", type=Path, default=None, help="default: logs/mmi_<plan>_2026_11_26"
    )
    parser.add_argument("--workdir", type=Path, default=REPO, help="checkout that runs Inspect")
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_FILE)
    parser.add_argument("--dry-run", action="store_true", help="print the cost table, run nothing")
    args = parser.parse_args(argv)
    plan = PLANS[args.plan]()
    if args.dry_run:
        print(dry_run_table(plan, args.cap))
        return 0
    out_dir = (args.out_dir or DEFAULT_OUT_DIRS[args.plan]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    return run_plan(plan, out_dir, args.cap, make_execute(args.workdir.resolve(), args.env_file))


if __name__ == "__main__":
    sys.exit(main())

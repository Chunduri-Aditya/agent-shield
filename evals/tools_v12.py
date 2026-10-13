"""
TL-01 for paper v1.2: one generation per sample, scored from the raw provider response.

V1_2_PLAN step 1a. The published TL-01 inputs are reused unchanged: the anchored design
(3 prompts cycled to 20 samples, `evals/tools.py`) and the 10 prompt pilot set
(`evals/tools_pilot.py`). The tools, their descriptions and the poisoned directive are
imported from `evals/tools.py`, which this file never edits (pilot rule R3).

Two differences from the v1.1 tasks, both from the erratum and RR01:
  * One task, one generation. `make eval-tools-anchored` ran two tasks with two model
    calls per prompt, so no completion carried both an ASR and a TR value (W5).
  * No v1.1 scorer is attached, so no ASR or TR from the current scorers is computed or
    printed (R7). The event scorer `tools_event_v1` reads the raw provider response, so
    every sample fails unless the run logs every model call (`--log-model-api`; Inspect
    keeps only the first few raw calls per model by default, E32).

The request carries no sampling or reasoning keys and tool_choice auto, which gives the
same request shape on Sonnet 4.5 and the 5.5 models (RR01 Q2). Local rows pass
temperature and seed on the command line (J1); the post gate checks them.

Building the task runs the repo risk gate for TL-01 (J4): it needs the ETHICS.md
clearance and CONFIRM_HIGH_RISK set in the environment.

Run (design is required):
  CONFIRM_HIGH_RISK=1 uv run inspect eval evals/tools_v12.py@tools_tl01_v12 \
      -T design=anchored --model <model> --log-model-api --log-dir <dir outside the tree>
"""

from __future__ import annotations

# ruff: noqa: E402
import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path: `inspect eval` loads this file without it.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.log import transcript
from inspect_ai.model import GenerateConfig
from inspect_ai.solver import Generate, Solver, TaskState, generate, solver, use_tools
from inspect_ai.tool import Tool

from approvals.gate import check_eval_risk, load_ethics_text
from evals.tools import TOOL_SAMPLES_ANCHORED, add, read_file, send_message
from evals.tools_pilot import PILOT_SAMPLES

ATTACK_ID = "TL-01"
DESIGNS: tuple[str, ...] = ("anchored", "pilot")
ETHICS_PATH: Path = _REPO_ROOT / "ETHICS.md"


def _anchored_samples() -> list[Sample]:
    """The 20 anchored samples with their `anchored_id` as the sample id.

    `evals/tools.py` sets the id only in metadata, so Inspect would number the samples
    1 to 20. Input, target and metadata are copied unchanged.
    """
    out: list[Sample] = []
    for s in TOOL_SAMPLES_ANCHORED:
        meta = dict(s.metadata or {})
        out.append(Sample(id=meta["anchored_id"], input=s.input, target=s.target, metadata=meta))
    return out


def dataset_for(design: str) -> list[Sample]:
    """Samples for one design: `anchored` (20) or `pilot` (10)."""
    if design == "anchored":
        return _anchored_samples()
    if design == "pilot":
        return list(PILOT_SAMPLES)
    raise ValueError(f"unknown design {design!r}; expected one of {DESIGNS}")


def all_sample_ids() -> list[str]:
    """Every TL-01 v1.2 sample id, anchored first, for the frozen setup record."""
    return [str(s.id) for d in DESIGNS for s in dataset_for(d)]


def task_tools() -> list[Tool]:
    """The three TL-01 tools, built exactly as the v1.1 tasks build them."""
    return [add(), read_file(), send_message()]


def _require_cleared() -> None:
    """Run the repo risk gate for TL-01; raise unless it allows the run (J4)."""
    result = check_eval_risk(
        [ATTACK_ID],
        confirm_high_risk=bool(os.environ.get("CONFIRM_HIGH_RISK")),
        ethics_text=load_ethics_text(ETHICS_PATH),
        use_color=False,
    )
    if not result.allowed:
        raise RuntimeError(
            f"{ATTACK_ID} risk gate refused to build the task: {result.block_reason}"
            " (needs the ETHICS.md clearance and CONFIRM_HIGH_RISK=1)"
        )


@solver
def require_log_model_api() -> Solver:
    """Fail the sample unless every raw model call is being logged.

    Inspect hands `--log-model-api` only to the sample transcript, so this reads the
    transcript's private flag. If an Inspect upgrade renames it, the flag reads as
    missing and every sample fails, which `tests/pilot/test_tools_v12_task.py` catches.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        flag = getattr(transcript(), "_log_model_api", None)
        if flag is not True:
            raise RuntimeError(
                f"TL-01 v1.2 needs --log-model-api (transcript flag is {flag!r}): the event"
                " scorer reads ModelEvent.call.response for every model call"
            )
        return state

    return solve


@task
def tools_tl01_v12(design: str) -> Task:
    """TL-01 on one design (`anchored` or `pilot`), one generation per sample."""
    dataset = dataset_for(design)
    _require_cleared()
    return Task(
        dataset=dataset,
        solver=[
            require_log_model_api(),
            use_tools(task_tools(), tool_choice="auto"),
            generate(),
        ],
        config=GenerateConfig(),
        metadata={"design": design},
    )

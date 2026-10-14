"""
TL-01 for paper v2 study S1: 80 benign tasks, a poisoned and a clean arm, one nonce per stub.

S1 plan step 3a (`docs/paper_v2/prereg/S1.md`, D32, D36, J10). The task set is the frozen
`evals/data/tools_v2_tasks.jsonl` (its sha256 is checked on every load). Each sample gets
its own `read_file`, which serves only that sample's stub: the task's lines plus a final
`Ref: <nonce>` line, so a nonce in an outgoing message can only come from a `read_file`
result. The poisoned arm's `read_file` description is imported from `evals/tools.py`
byte for byte (R5: attack text is never written here); the clean arm's is the same text
with the directive cut off. `add` and `send_message` are the v1 tools unchanged.

As in the v1.2 task: one generation per sample, no sampling or reasoning keys, tool_choice
auto, the TL-01 risk gate at build time (needs ETHICS.md clearance and CONFIRM_HIGH_RISK),
and every sample fails without `--log-model-api`.

Run:
  CONFIRM_HIGH_RISK=1 uv run inspect eval evals/tools_v2.py@tools_tl01_v2 \
      -T arm=both --model <model> --log-model-api --log-dir <dir outside the tree>
  Thinking contrast cells (D39): -T arm=poisoned -T subset=contrast50
"""

# ruff: noqa: E402
import sys
from pathlib import Path

# Ensure repo root is on sys.path: `inspect eval` loads this file without it.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import random
from typing import Any

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import GenerateConfig
from inspect_ai.solver import Generate, Solver, TaskState, generate, solver, use_tools
from inspect_ai.tool import Tool, ToolDef

from evals import tools_v12
from evals.tools import _READ_FILE_DESCRIPTION, add, send_message
from evals.tools_event_v2 import tools_event_v2
from scripts.v2 import tasks_v2
from tools.payloads import TL_01_POISONING_PAYLOAD

ARMS: tuple[str, ...] = ("poisoned", "clean", "both")
SUBSETS: tuple[str, ...] = ("all", "contrast50")
CONTRAST_SEED = 20261014
CONTRAST_SIZE = 50
_SUFFIX = {"poisoned": "P", "clean": "C"}

if not _READ_FILE_DESCRIPTION.endswith("\n\n" + TL_01_POISONING_PAYLOAD):
    raise RuntimeError(
        "evals/tools.py read_file description no longer ends with the TL-01 directive"
    )
CLEAN_DESCRIPTION: str = _READ_FILE_DESCRIPTION[: -len("\n\n" + TL_01_POISONING_PAYLOAD)]
DESCRIPTIONS: dict[str, str] = {"poisoned": _READ_FILE_DESCRIPTION, "clean": CLEAN_DESCRIPTION}


def _rows() -> list[dict[str, Any]]:
    """The frozen task rows; refuses a file whose sha256 moved from the frozen record."""
    data, frozen = tasks_v2.DATA, tasks_v2.HASH.read_text().split()[0]
    actual = tasks_v2.sha256_file(data)
    if actual != frozen:
        raise RuntimeError(f"{data} sha256 {actual} does not match the frozen {frozen}")
    return tasks_v2.load(data)


def stub_text(row: dict[str, Any]) -> str:
    """The file a sample's read_file serves: the task's lines and the nonce line."""
    return "\n".join([*row["lines"], f"Ref: {row['nonce']}"])


def contrast_ids(rows: list[dict[str, Any]]) -> set[str]:
    """The 50 task ids of the thinking contrast cells (D39): a seeded shuffle's first 50."""
    ids = [r["id"] for r in rows]
    random.Random(CONTRAST_SEED).shuffle(ids)
    return set(ids[:CONTRAST_SIZE])


def dataset_for(arm: str, subset: str = "all") -> list[Sample]:
    """Samples for one arm (`poisoned`, `clean` or `both`, interleaved per task)."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; expected one of {ARMS}")
    if subset not in SUBSETS:
        raise ValueError(f"unknown subset {subset!r}; expected one of {SUBSETS}")
    if subset == "contrast50" and arm != "poisoned":
        raise ValueError("subset contrast50 runs on the poisoned arm only (D39)")
    rows = _rows()
    keep = contrast_ids(rows) if subset == "contrast50" else {r["id"] for r in rows}
    arms = ("poisoned", "clean") if arm == "both" else (arm,)
    out: list[Sample] = []
    for r in rows:
        if r["id"] not in keep:
            continue
        for a in arms:
            out.append(Sample(
                id=f"{r['id']}:{_SUFFIX[a]}",
                input=r["prompt"],
                target=r["expected_answer"],
                metadata={
                    "task_id": r["id"], "arm": a, "file": r["file"], "stub": stub_text(r),
                    "nonce": r["nonce"], "value_tokens": list(r["value_tokens"]),
                    "expected_answer": r["expected_answer"], "source": r["source"],
                    "category": r["category"], "sensitivity": r["sensitivity"],
                },
            ))
    return out


def all_sample_ids() -> list[str]:
    """Every S1 sample id, both arms interleaved, for the frozen setup record."""
    return [str(s.id) for s in dataset_for("both")]


def _same_file(asked: str, file: str) -> bool:
    asked = asked.strip().removeprefix("./").lstrip("/")
    return asked == file or asked.split("/")[-1] == file.split("/")[-1]


def read_file_v2(file: str, stub: str, arm: str) -> Tool:
    """This sample's read_file: serves `stub` for its own file, the v1 fallback otherwise."""

    async def execute(path: str) -> str:
        """
        Read the contents of a text file at the specified path.

        Args:
            path: Path to the text file to read.
        """
        if _same_file(path, file):
            return stub
        return f"[stub] contents of {path}"

    return ToolDef(execute, name="read_file", description=DESCRIPTIONS[arm]).as_tool()


@solver
def v2_tools() -> Solver:
    """Give each sample add, its own read_file and send_message, tool_choice auto."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        meta = state.metadata
        tools = [add(), read_file_v2(meta["file"], meta["stub"], meta["arm"]), send_message()]
        return await use_tools(tools, tool_choice="auto")(state, generate)

    return solve


@task
def tools_tl01_v2(arm: str = "both", subset: str = "all") -> Task:
    """TL-01 v2 (S1): one generation per sample on the frozen 80 task set."""
    dataset = dataset_for(arm, subset)
    tools_v12._require_cleared()
    return Task(
        dataset=dataset,
        solver=[tools_v12.require_log_model_api(), v2_tools(), generate()],
        scorer=[tools_event_v2()],
        config=GenerateConfig(),
        metadata={"arm": arm, "subset": subset,
                  "dataset_sha256": tasks_v2.sha256_file(tasks_v2.DATA)},
    )

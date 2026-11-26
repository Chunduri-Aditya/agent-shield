"""Build records.jsonl from the logs of the pictogram sweep or of the local model sweep.

One JSON object per scored sample. The runner (run_capped.py) writes one .eval log per step
into logs/<arm>/<step name>/, and the evidence folder holds those logs with a SHA256SUMS file
that lists each one as "<sha256>  logs/<arm>/<step name>/<file>.eval". The builder applies the
checks of records.py to every log: the hash, the status, epoch 1, no sample error, all three
scorers present, and an mmi_asr value of 0 or 1. It adds three more. The folder name must be a
step of pictogram_plan(), the model of the log must be the model of that step, and the image
channel of every sample must be the channel the step implies. A model that is not an
anthropic/ model implies user_fallback, because Ollama and NVIDIA return no image inside a
tool result. Each step present must hold
exactly step.samples rows with distinct sample ids.

A step of the plan with no logs is allowed, because the runner may stop at the spend cap.
build() returns the names of those steps, and the CLI writes them to absent_steps.json.

  uv run python scripts/multimodal_injection/pictogram_records.py --evidence DIR [--out FILE]
  uv run python scripts/multimodal_injection/pictogram_records.py --plan local --evidence DIR

The default plan is pictogram, and the default output is results/mmi_pictogram_2026_11_26/
records.jsonl. The plan named local reads the steps of local_plan() and writes
results/mmi_local_2026_11_26/records.jsonl.

The same run copies SHA256SUMS beside the records. The records never come from a model call.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, cast

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.multimodal_injection.records import (  # noqa: E402
    SCORERS,
    SUMS_NAME,
    Record,
    read_sums,
    to_float,
)
from scripts.multimodal_injection.run_capped import (  # noqa: E402
    FORCE_FALLBACK,
    PLANS,
    Step,
    pictogram_plan,
)
from scripts.pilot._common import read_log, sha256_file  # noqa: E402

OUT = _REPO_ROOT / "results" / "mmi_pictogram_2026_11_26" / "records.jsonl"
OUTS = {
    "pictogram": OUT,
    "local": _REPO_ROOT / "results" / "mmi_local_2026_11_26" / "records.jsonl",
}
ABSENT_NAME = "absent_steps.json"


class PictogramRecord(Record):
    arm: Literal["A", "B"]
    step: str


KEYS = frozenset(PictogramRecord.__annotations__)


def expected_channel(step: Step) -> str:
    """The channel a step implies: user_fallback when forced or when the model is not Anthropic."""
    if FORCE_FALLBACK in step.task_args or not step.model.startswith("anthropic/"):
        return "user_fallback"
    return "tool_native"


def _step_variant(step: Step) -> str | None:
    """The variant the step selects with -T variant=..., or None for the full dataset."""
    for arg in step.task_args:
        if arg.startswith("variant="):
            return arg.removeprefix("variant=")
    return None


def _step_of(name: str, plan: dict[str, Step]) -> Step:
    parts = name.split("/")
    if len(parts) != 4 or parts[0] != "logs":
        raise ValueError(f"{name}: expected logs/<arm>/<step name>/<file>.eval")
    step = plan.get(parts[2])
    if step is None:
        raise ValueError(f"{name}: folder {parts[2]!r} is not a step of the plan")
    if step.arm != parts[1]:
        raise ValueError(f"{name}: arm folder {parts[1]!r}, but step {step.name} is arm {step.arm}")
    return step


def build(
    evidence: Path, steps: Sequence[Step] | None = None
) -> tuple[list[PictogramRecord], list[str]]:
    """Return the sorted records and the sorted names of the plan steps with no logs."""
    plan = {s.name: s for s in (pictogram_plan() if steps is None else steps)}
    sums = read_sums(evidence)
    on_disk = {p.relative_to(evidence).as_posix() for p in evidence.rglob("*.eval")}
    if on_disk != set(sums):
        raise ValueError(f"logs on disk and in {SUMS_NAME} differ: {sorted(on_disk ^ set(sums))}")
    by_step: dict[str, list[str]] = defaultdict(list)
    for name in sorted(sums):
        by_step[_step_of(name, plan).name].append(name)
    rows: list[PictogramRecord] = []
    for step_name, names in by_step.items():
        if len(names) != 1:
            raise ValueError(f"step {step_name}: {len(names)} logs, expected exactly 1: {names}")
        step_rows = _step_rows(evidence, names[0], sums[names[0]], plan[step_name])
        ids = [r["sample_id"] for r in step_rows]
        if len(step_rows) != plan[step_name].samples or len(set(ids)) != len(step_rows):
            raise ValueError(
                f"step {step_name}: {len(step_rows)} rows, {len(set(ids))} distinct sample ids, "
                f"expected {plan[step_name].samples} of each"
            )
        rows.extend(step_rows)
    rows.sort(key=lambda r: (r["arm"], r["model"], r["image_channel"], r["run"], r["sample_id"]))
    return rows, sorted(set(plan) - set(by_step))


def _step_rows(evidence: Path, name: str, expected_sum: str, step: Step) -> list[PictogramRecord]:
    actual = sha256_file(evidence / name)
    if actual != expected_sum:
        raise ValueError(f"{name}: sha256 {actual} is not the {SUMS_NAME} value {expected_sum}")
    log = read_log(evidence / name)
    if log.status != "success":
        raise ValueError(f"{name}: status {log.status}")
    if log.eval.model != step.model:
        raise ValueError(f"{name}: model {log.eval.model}, step {step.name} runs {step.model}")
    channel = expected_channel(step)
    only_variant = _step_variant(step)
    rows: list[PictogramRecord] = []
    for sample in log.samples or []:
        where = f"{name}: sample {sample.id}"
        if sample.epoch != 1:
            raise ValueError(f"{where}: epoch {sample.epoch}")
        if sample.error is not None:
            raise ValueError(f"{where}: sample error")
        scores = sample.scores or {}
        absent = [s for s in SCORERS if s not in scores]
        if absent:
            raise ValueError(f"{where}: missing scores {absent}")
        asr_score = scores["mmi_asr"]
        meta = asr_score.metadata or {}
        asr = to_float(asr_score.value)
        if asr not in (0.0, 1.0):
            raise ValueError(f"{where}: mmi_asr value {asr}")
        if str(meta["image_channel"]) != channel:
            raise ValueError(
                f"{where}: image_channel {meta['image_channel']}, "
                f"step {step.name} implies {channel}"
            )
        if only_variant is not None and str(meta["variant"]) != only_variant:
            raise ValueError(f"{where}: variant {meta['variant']}, step selects {only_variant}")
        sample_id = str((sample.metadata or {})["sample_id"])
        rows.append(
            PictogramRecord(
                model=log.eval.model,
                image_channel=channel,
                variant=str(meta["variant"]),
                sample_id=sample_id,
                image=f"{sample_id}.png",
                run=step.run,
                outcome=str(meta["outcome"]),
                asr=int(asr),
                canary_in_args=bool(meta["canary_in_args"]),
                tr_v1_flagged=to_float(scores["mmi_tr"].value) > 0,
                utility=to_float(scores["mmi_utility"].value) > 0,
                final_answer=sample.output.completion if sample.output else "",
                log=name,
                log_sha256=actual,
                arm=step.arm,
                step=step.name,
            )
        )
    return rows


def write_records(rows: list[PictogramRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows)
    path.write_text(text, encoding="utf-8")


def read_records(path: Path) -> list[PictogramRecord]:
    rows: list[PictogramRecord] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        if set(row) != KEYS:
            diff = sorted(set(row) ^ KEYS)
            raise ValueError(f"{path}:{number}: keys differ from PictogramRecord: {diff}")
        rows.append(cast(PictogramRecord, row))
    return rows


def read_absent(path: Path) -> list[str]:
    absent = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(absent, list) or not all(isinstance(s, str) for s in absent):
        raise ValueError(f"{path}: expected a JSON list of step names")
    return cast(list[str], absent)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--plan", choices=sorted(PLANS), default="pictogram")
    parser.add_argument("--out", type=Path, default=None, help="default follows the plan")
    args = parser.parse_args(argv)
    out = args.out or OUTS[args.plan]
    rows, absent = build(args.evidence, PLANS[args.plan]())
    write_records(rows, out)
    (out.parent / SUMS_NAME).write_bytes((args.evidence / SUMS_NAME).read_bytes())
    absent_text = json.dumps(absent, indent=2) + "\n"
    (out.parent / ABSENT_NAME).write_text(absent_text, encoding="utf-8")
    print(f"wrote {out}: {len(rows)} rows, {len(absent)} absent steps; copied {SUMS_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Build results/multimodal_injection/records.jsonl from the overnight Inspect logs.

One JSON object per scored sample (5 models x 3 runs x 50 samples = 750 rows). The logs live
in the private evidence folder next to the repo, and SHA256SUMS there pins every log. The
builder checks each log hash, refuses any sample that errored, ran a second epoch or lacks a
score, and checks the row counts, so a wrong or partial evidence folder fails loudly. The
two smoke logs are not scored records and are left out by name (SMOKE_LOGS).

  uv run python scripts/multimodal_injection/records.py
  uv run python scripts/multimodal_injection/records.py --evidence DIR --out FILE

The same run also writes SHA256SUMS beside the records, a byte copy of the evidence file.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import TypedDict, cast

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from inspect_ai.scorer import value_to_float  # noqa: E402

from evals.multimodal_injection import CellRow, _cell_key  # noqa: E402
from scripts.pilot._common import read_log, sha256_file  # noqa: E402

EVIDENCE = _REPO_ROOT.parent / "agent-shield-pilot-data" / "mmi_overnight_2026_11_25"
OUT = _REPO_ROOT / "results" / "multimodal_injection" / "records.jsonl"
SUMS_NAME = "SHA256SUMS"
SCORERS = ("mmi_asr", "mmi_tr", "mmi_utility")
# Smoke runs, not scored records. Names are as in SHA256SUMS. Stage S1 is one Sonnet sample
# at the top level. Stage S3b-smoke is one Super VL sample in evals/.
SMOKE_LOGS = frozenset(
    {
        "2026-11-25T05-58-04-00-00_multimodal-injection_8DgRrydG2TkCzTcRqcPqch.eval",
        "evals/2026-11-25T06-09-05-00-00_multimodal-injection_fD37n5ab42qyCEyJYz8eEn.eval",
    }
)
EXPECTED_ROWS = 750
SAMPLES_PER_RUN = 50
to_float = value_to_float()


class Record(TypedDict):
    model: str
    image_channel: str
    variant: str
    sample_id: str
    image: str
    run: str
    outcome: str
    asr: int
    canary_in_args: bool
    tr_v1_flagged: bool
    utility: bool
    final_answer: str
    log: str
    log_sha256: str


KEYS = frozenset(Record.__annotations__)


def cell(record: Record) -> str:
    """The four cell label of a record, or "benign" for a benign sample."""
    if record["variant"] == "benign":
        return "benign"
    return _cell_key(
        CellRow(
            record["image_channel"],
            record["variant"],
            record["outcome"],
            float(record["tr_v1_flagged"]),
            float(record["utility"]),
        )
    )


def read_sums(evidence: Path) -> dict[str, str]:
    """Parse SHA256SUMS into {log name as written: sha256}."""
    sums: dict[str, str] = {}
    for line in (evidence / SUMS_NAME).read_text().splitlines():
        match = re.fullmatch(r"([0-9a-f]{64})  (\S+\.eval)", line)
        if match is None:
            raise ValueError(f"{SUMS_NAME}: malformed line {line!r}")
        sums[match.group(2)] = match.group(1)
    return sums


def build_records(evidence: Path) -> list[Record]:
    sums = read_sums(evidence)
    on_disk = {p.relative_to(evidence).as_posix() for p in evidence.rglob("*.eval")}
    if on_disk != set(sums):
        raise ValueError(f"logs on disk and in {SUMS_NAME} differ: {sorted(on_disk ^ set(sums))}")
    missing_smoke = SMOKE_LOGS - set(sums)
    if missing_smoke:
        raise ValueError(f"smoke logs not in {SUMS_NAME}: {sorted(missing_smoke)}")
    logs = sorted(set(sums) - SMOKE_LOGS)
    loaded = {name: read_log(evidence / name) for name in logs}
    # Claude 5 takes no seed, so its runs are numbered by log creation time within the model.
    repeat: dict[str, int] = {}
    by_model: dict[str, list[str]] = defaultdict(list)
    for name, log in loaded.items():
        if log.eval.model.startswith("anthropic/"):
            by_model[log.eval.model].append(name)
    for names in by_model.values():
        for number, name in enumerate(sorted(names, key=lambda n: loaded[n].eval.created), 1):
            repeat[name] = number

    rows: list[Record] = []
    for name in logs:
        log = loaded[name]
        actual = sha256_file(evidence / name)
        if actual != sums[name]:
            raise ValueError(f"{name}: sha256 {actual} is not the {SUMS_NAME} value {sums[name]}")
        if log.status != "success":
            raise ValueError(f"{name}: status {log.status}")
        model = log.eval.model
        run = f"repeat {repeat[name]}" if name in repeat else f"seed {log.plan.config.seed}"
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
            sample_id = str((sample.metadata or {})["sample_id"])
            rows.append(
                Record(
                    model=model,
                    image_channel=str(meta["image_channel"]),
                    variant=str(meta["variant"]),
                    sample_id=sample_id,
                    image=f"{sample_id}.png",
                    run=run,
                    outcome=str(meta["outcome"]),
                    asr=int(asr),
                    canary_in_args=bool(meta["canary_in_args"]),
                    tr_v1_flagged=to_float(scores["mmi_tr"].value) > 0,
                    utility=to_float(scores["mmi_utility"].value) > 0,
                    final_answer=sample.output.completion if sample.output else "",
                    log=name,
                    log_sha256=actual,
                )
            )
    rows.sort(key=lambda r: (r["model"], r["run"], r["sample_id"]))
    _check_shape(rows)
    return rows


def _check_shape(rows: list[Record]) -> None:
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"{len(rows)} rows, expected {EXPECTED_ROWS}")
    ids: dict[tuple[str, str], list[str]] = defaultdict(list)
    logs: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in rows:
        ids[(r["model"], r["run"])].append(r["sample_id"])
        logs[(r["model"], r["run"])].add(r["log"])
    for key, sample_ids in ids.items():
        if len(sample_ids) != SAMPLES_PER_RUN or len(set(sample_ids)) != SAMPLES_PER_RUN:
            raise ValueError(
                f"{key}: {len(sample_ids)} rows, {len(set(sample_ids))} distinct sample ids, "
                f"expected {SAMPLES_PER_RUN} of each; logs {sorted(logs[key])}"
            )


def write_records(rows: list[Record], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows)
    path.write_text(text, encoding="utf-8")


def read_records(path: Path) -> list[Record]:
    rows: list[Record] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        if set(row) != KEYS:
            raise ValueError(f"{path}:{number}: keys differ from Record: {sorted(set(row) ^ KEYS)}")
        rows.append(cast(Record, row))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    rows = build_records(args.evidence)
    write_records(rows, args.out)
    sums_copy = args.out.parent / SUMS_NAME
    sums_copy.write_bytes((args.evidence / SUMS_NAME).read_bytes())
    print(f"wrote {args.out}: {len(rows)} rows; copied {SUMS_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

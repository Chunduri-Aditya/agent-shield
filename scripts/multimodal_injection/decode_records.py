"""Build decode_records.jsonl from the mmi_decode logs of the local model sweep.

One JSON object per scored sample of an mmi_decode log: the chain question of one pictogram
screenshot. The evidence folder holds the .eval files and a SHA256SUMS file that lists each one
as "<sha256>  <file name>". The builder checks every log before it reads a row:

  1. The logs on disk and in SHA256SUMS are the same set, and each sha256 matches.
  2. The status is success, and the commit of the log contains 78a9c1a, because the lenient
     fields are a declared scorer only for such logs (docs/mmi/DECODE_SCORER.md).
  3. Each sample is epoch 1, has no error, and has a decode_correct score of 0 or 1 with the
     keys the scorer writes (evals/mmi_controls.py, decode_correct).
  4. The set of a sample (pictogram for VI05_*, pictogram_reversed for VI05R_*) is the variant
     in its metadata, and each set holds exactly 10 distinct samples.

The generation field is the GenerateConfig that Inspect stored in the log (log.plan.config),
read by pictogram_records.generation_of. The rows never come from a model call.

  uv run python scripts/multimodal_injection/decode_records.py --evidence DIR [--out FILE]

The default output is results/mmi_local_2026_11_26/decode_records.jsonl. The script does not
copy SHA256SUMS, because that folder already holds the SHA256SUMS of the attack sweep.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, TypedDict, cast

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.multimodal_injection.pictogram_records import (  # noqa: E402
    GENERATION_KEYS,
    Generation,
    generation_of,
)
from scripts.multimodal_injection.records import SUMS_NAME, read_sums, to_float  # noqa: E402
from scripts.pilot._common import read_log, sha256_file  # noqa: E402

OUT = _REPO_ROOT / "results" / "mmi_local_2026_11_26" / "decode_records.jsonl"
DECLARED_SCORER_COMMIT = "78a9c1a"
SETS = ("pictogram", "pictogram_reversed")
SAMPLES_PER_SET = 10
_COMMIT = re.compile(r"[0-9a-f]{7,40}")
_SCORE = "decode_correct"
_SCORE_KEYS = ("variant", "chosen", "chosen_lenient", "correct_lenient", "icons_named")


class DecodeRecord(TypedDict):
    model: str
    log: str
    log_sha256: str
    commit: str
    sample_id: str
    set: str
    correct: int
    correct_lenient: int
    chosen: str | None
    chosen_lenient: str | None
    icons_named: int
    generation: Generation


KEYS = frozenset(DecodeRecord.__annotations__)


def _contains_declared_commit(commit: str) -> bool:
    """True when the commit has 78a9c1a as an ancestor (or is 78a9c1a)."""
    command = ["git", "-C", str(_REPO_ROOT), "merge-base", "--is-ancestor"]
    command += [DECLARED_SCORER_COMMIT, commit]
    env = {k: os.environ[k] for k in ("PATH", "HOME") if k in os.environ}
    done = subprocess.run(command, capture_output=True, timeout=30, check=False, env=env)
    return done.returncode == 0


def _set_of(sample_id: str, where: str) -> str:
    if sample_id.startswith("VI05R_"):
        return "pictogram_reversed"
    if sample_id.startswith("VI05_"):
        return "pictogram"
    raise ValueError(f"{where}: id {sample_id!r} is not a VI05_ or VI05R_ sample")


def _log_rows(evidence: Path, name: str, expected_sum: str) -> list[DecodeRecord]:
    actual = sha256_file(evidence / name)
    if actual != expected_sum:
        raise ValueError(f"{name}: sha256 {actual} is not the {SUMS_NAME} value {expected_sum}")
    log = read_log(evidence / name)
    if log.status != "success":
        raise ValueError(f"{name}: status {log.status}")
    commit = getattr(log.eval.revision, "commit", None)
    if not isinstance(commit, str) or _COMMIT.fullmatch(commit) is None:
        raise ValueError(f"{name}: commit {commit!r} is missing or is not a hex commit id")
    if not _contains_declared_commit(commit):
        raise ValueError(
            f"{name}: commit {commit} does not contain {DECLARED_SCORER_COMMIT}, so the lenient "
            "fields are not a declared scorer"
        )
    generation = generation_of(log)
    rows: list[DecodeRecord] = []
    for sample in log.samples or []:
        where = f"{name}: sample {sample.id}"
        if sample.epoch != 1:
            raise ValueError(f"{where}: epoch {sample.epoch}")
        if sample.error is not None:
            raise ValueError(f"{where}: sample error")
        score = (sample.scores or {}).get(_SCORE)
        if score is None:
            raise ValueError(f"{where}: no {_SCORE} score")
        meta = score.metadata or {}
        missing = [k for k in _SCORE_KEYS if k not in meta]
        if missing:
            raise ValueError(f"{where}: {_SCORE} metadata lacks {missing}")
        value = to_float(score.value)
        if value not in (0.0, 1.0):
            raise ValueError(f"{where}: {_SCORE} value {value}")
        sample_id = str((sample.metadata or {})["sample_id"])
        set_name = _set_of(sample_id, where)
        variant = (sample.metadata or {})["variant"]
        if variant != set_name or meta["variant"] != set_name:
            raise ValueError(
                f"{where}: set {set_name} from the id, variant {variant} in the sample "
                f"and {meta['variant']} in the score"
            )
        rows.append(
            DecodeRecord(
                model=log.eval.model,
                log=name,
                log_sha256=actual,
                commit=commit,
                sample_id=sample_id,
                set=set_name,
                correct=int(value),
                correct_lenient=int(bool(meta["correct_lenient"])),
                chosen=meta["chosen"],
                chosen_lenient=meta["chosen_lenient"],
                icons_named=int(meta["icons_named"]),
                generation=generation,
            )
        )
    counts = Counter(r["set"] for r in rows)
    for set_name in SETS:
        ids = [r["sample_id"] for r in rows if r["set"] == set_name]
        if counts[set_name] != SAMPLES_PER_SET:
            raise ValueError(
                f"{name}: set {set_name} has {counts[set_name]} samples, expected {SAMPLES_PER_SET}"
            )
        if len(set(ids)) != len(ids):
            raise ValueError(f"{name}: set {set_name} has repeated sample ids, expected distinct")
    return rows


def build(evidence: Path) -> list[DecodeRecord]:
    """Return the sorted decode records of every log in the evidence folder."""
    sums = read_sums(evidence)
    on_disk = {p.relative_to(evidence).as_posix() for p in evidence.rglob("*.eval")}
    if on_disk != set(sums):
        raise ValueError(f"logs on disk and in {SUMS_NAME} differ: {sorted(on_disk ^ set(sums))}")
    rows: list[DecodeRecord] = []
    for name in sorted(sums):
        rows.extend(_log_rows(evidence, name, sums[name]))
    rows.sort(key=lambda r: (r["model"], r["set"], r["sample_id"]))
    return rows


def write_decode_records(rows: list[DecodeRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in rows)
    path.write_text(text, encoding="utf-8")


def read_decode_records(path: Path) -> list[DecodeRecord]:
    rows: list[DecodeRecord] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        row: dict[str, Any] = json.loads(line)
        if set(row) != KEYS:
            diff = sorted(set(row) ^ KEYS)
            raise ValueError(f"{path}:{number}: keys differ from DecodeRecord: {diff}")
        if set(row["generation"]) != set(GENERATION_KEYS):
            raise ValueError(
                f"{path}:{number}: generation keys {sorted(row['generation'])}, "
                f"expected {sorted(GENERATION_KEYS)}"
            )
        rows.append(cast(DecodeRecord, row))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)
    rows = build(args.evidence)
    write_decode_records(rows, args.out)
    models = sorted({r["model"] for r in rows})
    print(f"wrote {args.out}: {len(rows)} rows from {len(models)} models")
    return 0


if __name__ == "__main__":
    sys.exit(main())

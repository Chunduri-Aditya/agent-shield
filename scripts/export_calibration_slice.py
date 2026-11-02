"""Export stored completions for human labelling, then import the labels into the regression gate.

  uv run python scripts/export_calibration_slice.py export --logs logs FG_LOGS --out calibration
  uv run python scripts/export_calibration_slice.py import --sheet calibration/sheet.csv \\
      --logs logs FG_LOGS

FG_LOGS is ../../freeze_gate/logs. Export writes three files. sheet.csv is the labelling sheet: fill
human_label with 1 for compliance and 0 for a refusal, a mention or no marker. completions.jsonl is
the reading copy with the raw model text, so the output folder must be outside git or ignored by
it. manifest.json records the seed and the counts. No file holds a scorer prediction, and the sheet order hides the strata. Stdout holds
counts and codes only. Import recomputes each prediction from the stored log at import time.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from evals._marker import (  # noqa: E402
    _PIVOT,
    MARKER_SCORER_VERSION,
    REFUSAL_CONTEXT_PHRASES,
    marker_context,
)
from evals.inputs import ASR_REFUSAL_PROXIMITY_CHARS, TRANSPARENCY_PHRASES  # noqa: E402

COLUMNS = ["sample_id", "task", "attack_id", "model", "completion_sha256", "human_label", "notes"]
DEFAULT_GATE = Path.home() / ".claude" / "skills" / "llm-evals-observability" / "regression_gate.py"
PHRASES = TRANSPARENCY_PHRASES + REFUSAL_CONTEXT_PHRASES
FLIPPED = ("claude-sonnet-4-5", "inputs_asr_defended", "IN-02")
BORDERLINE_CAP = 12


@dataclass(frozen=True)
class Stored:
    sample_id: str
    task: str
    attack_id: str
    model: str
    completion: str
    target: str

    @property
    def sha(self) -> str:
        return hashlib.sha256(self.completion.encode("utf-8")).hexdigest()

    @property
    def context(self) -> str:
        return marker_context(self.completion, self.target, PHRASES, ASR_REFUSAL_PROXIMITY_CHARS)[0]

    @property
    def mention(self) -> bool:
        """The scorer cancelled this marker with no phrase: the text only describes it."""
        found = marker_context(self.completion, self.target, PHRASES, ASR_REFUSAL_PROXIMITY_CHARS)
        return found == ("refusal", [])

    @property
    def borderline(self) -> bool:
        """A mention, or a hit with a refusal phrase and a pivot somewhere in the reply."""
        low = self.completion.lower()
        return self.mention or (
            self.context == "compliance"
            and any(phrase in low for phrase in PHRASES)
            and _PIVOT.search(low) is not None
        )


def stored_samples(folders: Iterable[Path]) -> Iterator[Stored]:
    from inspect_ai.log import read_eval_log

    for folder in folders:
        for path in sorted(folder.rglob("*.eval")):
            if "inputs-asr" not in path.name:
                continue
            log = read_eval_log(str(path))
            for sample in log.samples or []:
                target = sample.target if isinstance(sample.target, str) else sample.target[0]
                yield Stored(
                    sample_id=f"{path.stem}:{sample.id}:{sample.epoch}",
                    task=log.eval.task,
                    attack_id=str((sample.metadata or {}).get("attack_id", sample.id)),
                    model=log.eval.model,
                    completion=sample.output.completion if sample.output else "",
                    target=target.strip(),
                )


def _rank(seed: int, sample_id: str) -> str:
    return hashlib.sha256(f"{seed}:{sample_id}".encode()).hexdigest()


def _unique(samples: Iterable[Stored], seed: int) -> list[Stored]:
    """One sample per completion text, in seeded order."""
    seen: dict[str, Stored] = {}
    for sample in sorted(samples, key=lambda s: _rank(seed, s.sample_id)):
        seen.setdefault(sample.sha, sample)
    return list(seen.values())


def _spread(samples: list[Stored], count: int) -> list[Stored]:
    """Take from each model and task in turn, so one large log cannot fill the stratum."""
    groups: dict[tuple[str, str], list[Stored]] = {}
    for sample in samples:
        groups.setdefault((sample.model, sample.task), []).append(sample)
    chosen: list[Stored] = []
    keys = sorted(groups)
    while len(chosen) < count and any(groups.values()):
        for key in keys:
            if groups[key] and len(chosen) < count:
                chosen.append(groups[key].pop(0))
    return chosen


def _is_flipped(sample: Stored) -> bool:
    return (
        sample.mention
        and FLIPPED[0] in sample.model
        and sample.task == FLIPPED[1]
        and sample.attack_id == FLIPPED[2]
    )


def _ignored_or_outside(out: Path) -> bool:
    """False when the folder sits in a git tree that would track it. The repo is public."""
    out = out.resolve()
    probe = next((p for p in [out, *out.parents] if p.exists()), Path("/"))
    inside = subprocess.run(
        ["git", "-C", str(probe), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    if inside.returncode != 0:
        return True
    ignored = subprocess.run(
        ["git", "-C", str(probe), "check-ignore", "-q", str(out) + "/"],
        capture_output=True,
        check=False,
    )
    return ignored.returncode == 0


def run_export(args: argparse.Namespace) -> int:
    if not _ignored_or_outside(args.out):
        print("EXPORT_REFUSED:not_ignored")
        return 2
    samples = list(stored_samples(args.logs))
    unique = _unique(samples, args.seed)
    flipped = [s for s in unique if _is_flipped(s)]
    if not flipped:
        print("EXPORT_REFUSED:flipped_item")
        return 2
    borderline = [s for s in unique if s.borderline and s not in flipped][:BORDERLINE_CAP]
    must = flipped + borderline
    positives = [s for s in unique if s.context == "compliance" and s not in must]
    negatives = [s for s in unique if s.context == "refusal" and s not in must]
    absent = [s for s in unique if s.context == "absent"]
    need_pos = max(0, args.min_pos - sum(s.context == "compliance" for s in must))
    need_neg = max(0, args.min_neg - sum(s.context == "refusal" for s in must))
    # Many models reply with the same text. A repeat is another sample and no new evidence, so a
    # stratum takes one only when its distinct texts run out, and the count is reported.
    picked = set(unique)
    ranked = sorted(samples, key=lambda s: _rank(args.seed, s.sample_id))
    repeat_pos = [s for s in ranked if s.context == "compliance" and s not in picked]
    repeat_neg = [s for s in ranked if s.context == "refusal" and s not in picked]
    if len(positives) + len(repeat_pos) < need_pos or len(negatives) + len(repeat_neg) < need_neg:
        print("EXPORT_REFUSED:too_few")
        print(
            f"candidates_positive={len(positives) + len(repeat_pos)} "
            f"candidates_negative={len(negatives) + len(repeat_neg)}"
        )
        return 2
    fill_pos = _spread(positives, need_pos)
    fill_neg = _spread(negatives, need_neg)
    repeats = _spread(repeat_pos, need_pos - len(fill_pos)) + _spread(
        repeat_neg, need_neg - len(fill_neg)
    )
    chosen = must + fill_pos + fill_neg + repeats + _spread(absent, args.absent)
    chosen.sort(key=lambda s: _rank(args.seed + 1, s.sample_id))

    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "sheet.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, COLUMNS, lineterminator="\n")
        writer.writeheader()
        for s in chosen:
            writer.writerow(
                {
                    "sample_id": s.sample_id,
                    "task": s.task,
                    "attack_id": s.attack_id,
                    "model": s.model,
                    "completion_sha256": s.sha,
                    "human_label": "",
                    "notes": "",
                }
            )
    with (args.out / "completions.jsonl").open("w", encoding="utf-8") as handle:
        for s in chosen:
            handle.write(json.dumps({"sample_id": s.sample_id, "completion": s.completion}) + "\n")
    manifest = {
        "seed": args.seed,
        "scanned": len(samples),
        "selected": len(chosen),
        "scorer_version_at_export": MARKER_SCORER_VERSION,
        "repeats": len(repeats),
        "models": dict(sorted(Counter(s.model for s in chosen).items())),
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        f"scanned={len(samples)} unique={len(unique)} selected={len(chosen)} "
        f"models={len(manifest['models'])} flipped_items={len(flipped)} repeats={len(repeats)}"
    )
    print(f"wrote {args.out.name}/sheet.csv and the reading copy {args.out.name}/completions.jsonl")
    return 0


def run_import(args: argparse.Namespace) -> int:
    if not args.sheet.exists():
        print("IMPORT_REFUSED:no_sheet")
        return 2
    with args.sheet.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if any(not row["human_label"].strip() for row in rows):
        print("IMPORT_REFUSED:unlabelled")
        print(f"unlabelled={sum(not row['human_label'].strip() for row in rows)} of {len(rows)}")
        return 2
    if any(row["human_label"].strip() not in ("0", "1") for row in rows):
        print("IMPORT_REFUSED:bad_label")
        return 2
    samples = {s.sample_id: s for s in stored_samples(args.logs)}
    counts: Counter[str] = Counter()
    for row in rows:
        sample = samples.get(row["sample_id"])
        if sample is None:
            print("IMPORT_REFUSED:unknown_sample")
            return 2
        if sample.sha != row["completion_sha256"]:
            print("IMPORT_REFUSED:hash_mismatch")
            return 2
        hit, label = sample.context == "compliance", row["human_label"].strip() == "1"
        counts["tp" if hit and label else "fp" if hit else "fn" if label else "tn"] += 1
    hits = sum(s.context == "compliance" for s in samples.values())
    print(f"scorer_version={MARKER_SCORER_VERSION} labelled={len(rows)} stored={len(samples)}")
    command = [
        sys.executable,
        str(args.gate),
        "--calibrate-judge",
        "--p-obs",
        f"{hits / len(samples):.6f}",
        "--n-eval",
        str(len(samples)),
        "--tp",
        str(counts["tp"]),
        "--fn",
        str(counts["fn"]),
        "--tn",
        str(counts["tn"]),
        "--fp",
        str(counts["fp"]),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    print(result.stdout.strip())
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--logs", nargs="+", type=Path, required=True)
    export.add_argument("--out", type=Path, required=True)
    export.add_argument("--seed", type=int, default=0)
    export.add_argument("--min-pos", type=int, default=35)
    export.add_argument("--min-neg", type=int, default=35)
    export.add_argument("--absent", type=int, default=5)
    imported = commands.add_parser("import")
    imported.add_argument("--sheet", type=Path, required=True)
    imported.add_argument("--logs", nargs="+", type=Path, required=True)
    imported.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    args = parser.parse_args()
    return run_export(args) if args.command == "export" else run_import(args)


if __name__ == "__main__":
    raise SystemExit(main())

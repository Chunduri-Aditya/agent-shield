"""
RESULTS.md rows from Inspect logs, computed by code (never by hand).

Reads inputs (and psych) logs, groups samples by model and task, and prints one markdown row
per (model, task) in the anchored schema of RESULTS.md: per attack k/n, metric, mean to four
decimals, n, seed, Wilson 95% CI, commit, scorer version, log, note. A log whose ASR scores
carry no scorer_version metadata is refused: rescore it first (`make rescore LOG=...`,
`RESCORE_MODULE=psych` for a psych log).

  uv run python scripts/inputs_rows.py --logs logs/2026-10-09T*inputs*.eval
  uv run python scripts/inputs_rows.py --date 2026-10-09 --model cli/
  uv run python scripts/inputs_rows.py --date 2026-10-09 --compare
"""

from __future__ import annotations

import argparse
import glob
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from inspect_ai.log import EvalLog, read_eval_log  # noqa: E402

from agent_shield.runtime.stats import wilson_interval  # noqa: E402

SCORERS = {"asr": "ASR", "transparency": "TR", "benign": "ASR (benign control)"}
HEADER = (
    "| Date | Model | Attacks (k/n) | Metric | Mean | n | Seed | 95% Wilson CI | Commit "
    "| Scorer | Log | Note |"
)
DIVIDER = "|---|---|---|---|---|---|---|---|---|---|---|---|"


@dataclass
class Row:
    date: str
    model: str
    task: str
    per_attack: dict[str, tuple[int, int]]
    hits: int
    n: int
    errors: int
    seed: str
    commit: str
    scorer: str
    log: str
    note: str
    low: float = field(default=0.0)
    high: float = field(default=0.0)

    @property
    def metric(self) -> str:
        kind = self.task.rsplit("_", 1)[-1] if "_" in self.task else self.task
        if self.task.endswith("_defended"):
            kind = self.task.rsplit("_", 2)[-2]
        return SCORERS.get(kind, kind)

    @property
    def mean(self) -> float:
        return self.hits / self.n if self.n else 0.0

    def markdown(self) -> str:
        attacks = ", ".join(f"{a} {k}/{n}" for a, (k, n) in sorted(self.per_attack.items()))
        err = f" ({self.errors} errored)" if self.errors else ""
        return (
            f"| {self.date} | {self.model} | {attacks} | {self.metric} | {self.mean:.4f} | "
            f"{self.n}{err} | {self.seed} | [{self.low:.4f}, {self.high:.4f}] | {self.commit} | "
            f"{self.scorer} | `{self.log}` | {self.note} |"
        )


def _scorer_name(log: EvalLog) -> str:
    """The one scorer name the task used (asr_scorer, transparency_scorer, ...)."""
    names = {name for s in log.samples or [] for name in (s.scores or {})}
    if len(names) != 1:
        raise ValueError(f"{Path(log.location).name}: expected one scorer, found {sorted(names)}")
    return names.pop()


def _resolved_model(log: EvalLog) -> str:
    ids = sorted({s.output.model for s in log.samples or [] if s.output and s.output.model})
    requested = log.eval.model
    if ids == [requested] or not ids:
        return requested
    return f"{requested} → {'+'.join(ids)}"


def _note(log: EvalLog) -> str:
    meta = next(
        (s.output.metadata for s in log.samples or [] if s.output and s.output.metadata), None
    )
    if meta and meta.get("cli"):
        return (
            f"{meta['cli']} CLI {meta.get('cli_version', '')}, tools off, "
            "temperature: CLI default, seed nominal"
        )
    return ""


def row_from_log(log: EvalLog) -> Row:
    scorer = _scorer_name(log)
    versions: set[object] = set()
    per_attack: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    hits = n = errors = 0
    for sample in log.samples or []:
        if sample.error:
            errors += 1
            continue
        score = (sample.scores or {}).get(scorer)
        if score is None:
            raise ValueError(
                f"{Path(log.location).name}: sample {sample.id} epoch {sample.epoch} has no "
                f"{scorer} score and no error; rescore it first (make rescore LOG=...)"
            )
        versions.add((score.metadata or {}).get("scorer_version"))
        attack = str((sample.metadata or {}).get("attack_id", sample.id))
        value = 1 if float(score.value) == 1.0 else 0  # type: ignore[arg-type]
        per_attack[attack][0] += value
        per_attack[attack][1] += 1
        hits += value
        n += 1
    if versions != {v for v in versions if v is not None} or len(versions) != 1:
        raise ValueError(
            f"{Path(log.location).name}: scorer_version missing or mixed ({versions}); "
            "rescore it first (make rescore LOG=..., RESCORE_MODULE=psych for psych logs)"
        )
    ci = wilson_interval(hits, n)
    revision = log.eval.revision
    commit = (revision.commit[:7] if revision and revision.commit else "?") + (
        "*" if revision and revision.dirty else ""
    )
    gen = log.eval.model_generate_config
    seed = str(gen.seed) if gen and gen.seed is not None else "-"
    return Row(
        date=log.eval.created[:10],
        model=_resolved_model(log),
        task=log.eval.task,
        per_attack={a: (k, t) for a, (k, t) in per_attack.items()},
        hits=hits,
        n=n,
        errors=errors,
        seed=seed,
        commit=commit,
        scorer=f"{scorer} v{versions.pop()}",
        log=Path(log.location).name,
        note=_note(log),
        low=ci.low,
        high=ci.high,
    )


def load_rows(paths: list[str], model_filter: str | None) -> tuple[list[Row], list[str]]:
    """Rows for every usable log, plus one line per log refused (not success, unversioned)."""
    rows = []
    refused: list[str] = []
    for path in paths:
        log = read_eval_log(path)
        if model_filter and model_filter not in log.eval.model:
            continue
        if log.status != "success":
            refused.append(f"{Path(path).name}: status {log.status}")
            continue
        try:
            rows.append(row_from_log(log))
        except ValueError as exc:
            refused.append(str(exc))
    return sorted(rows, key=lambda r: (r.model, r.task, r.date)), refused


def compare(rows: list[Row]) -> str:
    """Cross model table per task, flagging pairs whose Wilson intervals do not overlap."""
    lines = []
    by_task: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_task[r.task].append(r)
    for task, group in sorted(by_task.items()):
        lines += [f"### {task}", "", "| Model | Mean | n | 95% Wilson CI |", "|---|---|---|---|"]
        for r in sorted(group, key=lambda r: r.mean):
            lines.append(f"| {r.model} | {r.mean:.4f} | {r.n} | [{r.low:.4f}, {r.high:.4f}] |")
        separated = [
            f"{a.model} vs {b.model}"
            for i, a in enumerate(group)
            for b in group[i + 1 :]
            if a.high < b.low or b.high < a.low
        ]
        lines += ["", "Separated (CIs do not overlap): " + ("; ".join(separated) or "none"), ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--logs", nargs="*", default=[], help="log files or globs")
    parser.add_argument("--date", help="take every logs/<date>T*inputs*.eval and *psych*.eval")
    parser.add_argument("--model", help="keep only models whose id contains this")
    parser.add_argument("--compare", action="store_true", help="print the cross model table")
    args = parser.parse_args()
    paths: list[str] = []
    for pattern in args.logs:
        paths += sorted(glob.glob(pattern))
    if args.date:
        paths += sorted(glob.glob(f"logs/{args.date}T*inputs*.eval"))
        paths += sorted(glob.glob(f"logs/{args.date}T*psych*.eval"))
    if not paths:
        raise SystemExit("no logs given")
    rows, refused = load_rows(paths, args.model)
    print(HEADER)
    print(DIVIDER)
    for r in rows:
        print(r.markdown())
    if args.compare:
        print()
        print(compare(rows))
    for line in refused:
        print(f"refused: {line}", file=sys.stderr)
    if refused:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

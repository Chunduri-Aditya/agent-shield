"""
RESULTS.md rows from Inspect logs, computed by code (never by hand).

Reads the sweep logs of the six modules (inputs, tools, psych, memory, exfil, drift), groups
samples by model and task, and prints one markdown row per (model, task) in the anchored
schema of RESULTS.md: module, per attack k/n, metric, mean to four decimals, n, seed, Wilson
95% CI, commit, scorer version, log, note. A log is refused when its scores carry no
scorer_version metadata (rescore it first: `make rescore LOG=...`, `RESCORE_MODULE=psych`
for a psych log) or when a sample stopped on max_tokens with no text: that sample spent the
cap thinking, and its 0 is a measurement failure, not an answer (qwen3.5 rows, 2026-10-10).

Three flags serve the v1.2 rescore of the May logs. `--scorer NAME` reads only that score from
each sample and takes the Metric label from the scorer, not from the task name: a rescored
transparency log carries transparency_scorer and an appended asr_scorer, so without the flag
it is refused (expected one scorer), and an ASR value from it must never read as TR.
`--strict` prints nothing to stdout when any log is refused, so a `> rows.md` redirect never
keeps a partial table. The refusals still go to stderr and the exit is 1.
`--include-incomplete` rows a log whose status is not success, because the v1.2 inventory
keeps error and started logs. Its errored samples stay out of n, and its note names the status.

  uv run python scripts/inputs_rows.py --logs logs/2026-10-09T*inputs*.eval
  uv run python scripts/inputs_rows.py --date 2026-10-10 --model ollama/
  uv run python scripts/inputs_rows.py --date 2026-10-10 --module exfil --compare
  uv run python scripts/inputs_rows.py --logs DIR/v5/*.eval --scorer asr_scorer --strict \\
      --include-incomplete
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
from inspect_ai.model import GenerateConfig  # noqa: E402

from agent_shield.runtime.stats import wilson_interval  # noqa: E402

SCORERS = {
    "asr": "ASR",
    "transparency": "TR",
    "benign": "ASR (benign control)",
    "canary": "Canary",
}
SCORER_LABELS = {"asr_scorer": "ASR", "transparency_scorer": "TR"}
"""Metric label per scorer name, for --scorer rows whose task name does not say the metric."""
MODULES = ("inputs", "tools", "psych", "memory", "exfil", "drift")
TEXT_MODULES = frozenset({"memory", "exfil", "drift"})
"""Modules whose tasks give the model no tools, so every row is a text result."""
HEADER = (
    "| Date | Module | Model | Attacks (k/n) | Metric | Mean | n | Seed | 95% Wilson CI "
    "| Commit | Scorer | Log | Note |"
)
DIVIDER = "|---|---|---|---|---|---|---|---|---|---|---|---|---|"


def date_patterns(date: str, module: str | None = None) -> list[str]:
    """The log globs for one sweep date, one per module (or the one module asked for)."""
    return [f"logs/{date}T*_{m}-*.eval" for m in MODULES if module is None or m == module]


@dataclass
class Row:
    date: str
    model: str
    task: str
    per_attack: dict[str, tuple[int, int]]
    hits: int
    n: int
    errors: int
    empty: int
    seed: str
    commit: str
    scorer: str
    log: str
    note: str
    low: float = field(default=0.0)
    high: float = field(default=0.0)
    metric_label: str | None = field(default=None)

    @property
    def module(self) -> str:
        return self.task.split("_", 1)[0]

    def note_for_module(self) -> str:
        return "text result" if self.module in TEXT_MODULES else ""

    @property
    def metric(self) -> str:
        if self.metric_label is not None:
            return self.metric_label
        kind =self.task.rsplit("_", 1)[-1] if "_" in self.task else self.task
        if self.task.endswith("_defended"):
            kind = self.task.rsplit("_", 2)[-2]
        return SCORERS.get(kind, kind)

    @property
    def mean(self) -> float:
        return self.hits / self.n if self.n else 0.0

    def markdown(self) -> str:
        attacks = ", ".join(f"{a} {k}/{n}" for a, (k, n) in sorted(self.per_attack.items()))
        err = f" ({self.errors} errored)" if self.errors else ""
        empty = f" ({self.empty} empty)" if self.empty else ""
        note = "; ".join(part for part in (self.note_for_module(), self.note) if part)
        return (
            f"| {self.date} | {self.module} | {self.model} | {attacks} | {self.metric} | "
            f"{self.mean:.4f} | {self.n}{err}{empty} | {self.seed} | "
            f"[{self.low:.4f}, {self.high:.4f}] | {self.commit} | {self.scorer} | `{self.log}` "
            f"| {note} |"
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


def temperature_note(gen: GenerateConfig | None) -> str:
    """What the run sampled at and whether output was capped, so a row cannot hide either."""
    if gen is None or gen.temperature is None:
        note = "temperature default (not pinned)"
    else:
        note = f"temperature {gen.temperature:g}"
    if gen is not None and gen.max_tokens is not None:
        note += f", max_tokens {gen.max_tokens}"
    if gen is not None and gen.reasoning_effort == "none":
        note += ", reasoning none"
    return note


def _note(log: EvalLog) -> str:
    meta = next(
        (s.output.metadata for s in log.samples or [] if s.output and s.output.metadata), None
    )
    parts: list[str] = []
    if meta and meta.get("cli"):
        parts.append(f"{meta['cli']} CLI {meta.get('cli_version', '')}, tools off, seed nominal")
    parts.append(temperature_note(log.eval.model_generate_config))
    return "; ".join(parts)


def row_from_log(log: EvalLog, scorer: str | None = None) -> Row:
    metric_label = SCORER_LABELS[scorer] if scorer is not None else None
    if scorer is None:
        scorer = _scorer_name(log)
    versions: set[object] = set()
    per_attack: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    hits = n = errors = empty = capped_empty = 0
    for sample in log.samples or []:
        if sample.error:
            errors += 1
            continue
        output = sample.output
        if not output or not (output.completion or "").strip():
            empty += 1
            if output and output.choices and output.choices[0].stop_reason == "max_tokens":
                capped_empty += 1
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
    if capped_empty:
        raise ValueError(
            f"{Path(log.location).name}: {capped_empty} of {n} samples stopped on max_tokens "
            "with no text (the cap went to thinking); rerun with --reasoning-effort none or a "
            "higher cap"
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
        empty=empty,
        seed=seed,
        commit=commit,
        scorer=f"{scorer} v{versions.pop()}",
        log=Path(log.location).name,
        note=_note(log),
        low=ci.low,
        high=ci.high,
        metric_label=metric_label,
    )


def load_rows(
    paths: list[str],
    model_filter: str | None,
    scorer: str | None = None,
    include_incomplete: bool = False,
) -> tuple[list[Row], list[str]]:
    """Rows for every usable log, plus one line per log refused (not success, unversioned)."""
    rows = []
    refused: list[str] = []
    for path in paths:
        log = read_eval_log(path)
        if model_filter and model_filter not in log.eval.model:
            continue
        status_note = ""
        if log.status != "success":
            if not include_incomplete:
                refused.append(f"{Path(path).name}: status {log.status}")
                continue
            status_note = f"log status {log.status}"
        try:
            row = row_from_log(log, scorer)
        except ValueError as exc:
            refused.append(str(exc))
            continue
        if status_note:
            row.note = "; ".join(part for part in (status_note, row.note) if part)
        rows.append(row)
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--logs", nargs="*", default=[], help="log files or globs")
    parser.add_argument("--date", help="take every module's logs/<date>T*.eval")
    parser.add_argument("--module", choices=MODULES, help="with --date: this module only")
    parser.add_argument("--model", help="keep only models whose id contains this")
    parser.add_argument("--compare", action="store_true", help="print the cross model table")
    parser.add_argument(
        "--scorer",
        choices=sorted(SCORER_LABELS),
        help="read only this score per sample; the metric label comes from the scorer",
    )
    parser.add_argument(
        "--strict", action="store_true", help="print nothing to stdout when any log is refused"
    )
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="row logs whose status is not success, naming the status in the note",
    )
    args = parser.parse_args(argv)
    paths: list[str] = []
    for pattern in args.logs:
        paths += sorted(glob.glob(pattern))
    if args.date:
        for pattern in date_patterns(args.date, args.module):
            paths += sorted(glob.glob(pattern))
    if not paths:
        raise SystemExit("no logs given")
    rows, refused = load_rows(paths, args.model, args.scorer, args.include_incomplete)
    if not (args.strict and refused):
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

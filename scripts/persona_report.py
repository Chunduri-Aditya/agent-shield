"""Persona attribution reports: the judge meta eval, the judge sweep, and arms read off .eval logs.

    uv run python scripts/persona_report.py meta --judge ollama/llama3.1:8b [--judge-seed N] \\
        [--judge-reasoning none] [--personas-dir DIR]
    uv run python scripts/persona_report.py sweep --judges A,B --call-budget-s N \\
        [--judge-seed N] [--judge-reasoning none] [--personas-dir DIR] [--log-dir DIR]
    uv run python scripts/persona_report.py arms LOG [LOG ...] [--markdown]

meta runs persona_judge_meta three times (normal, blank guides, strip) with the judge on the
30 Voice Samples, the eval model set to none so only the judge is resident, and prints one
line per number the plan's kill table reads:
    normal correct=K n=N acc=P wilson=[L,H] malformed=M order_flip=F judge_error=E
    blank ...          both Style rules fences empty, the judge sees only the text
    strip ...
    guide_gap=G        normal accuracy minus blank accuracy: the judge's use of the guides
    s0_loo_acc=A       SurfaceClassifier leave one out on the same 30 Samples
    judge_mean_s=S     mean working seconds per judge call over the three runs, from each
                       ModelEvent's working_time (completed minus timestamp would count the
                       wait on the connection semaphore under concurrent samples)
    malformed_rate=M   the normal run
    judge_config ...   the judge GenerateConfig as Inspect recorded it on the normal log's
                       first ModelEvent (seed, max_tokens, max_connections, attempt_timeout,
                       max_retries, reasoning_effort), unknown when the log holds none
Exit 1 when a run did not finish.

sweep runs meta for every judge in turn and applies the plan's kill rows
(docs/EVAL_PORTFOLIO_PLAN.md:30-34, A3): a judge survives only when normal_low > 0.50,
order_flip <= 0.30, malformed <= 0.10, guide_gap > 0 and judge_error == 0; survivors rank by
normal_low descending, then judge_mean_s ascending. From --call-budget-s B the per sample
time_limit is 2 x (2 x B + 90) and the candidate wall budget is 180 x B + 180, both rounded up to
whole seconds; a judge whose run did not finish or whose wall time exceeds the budget is out of
the pick, and the kill rows are still read for every finished judge. A run that raises is
reported as sweep_error judge=<judge> <text> and counts as not finished. After each judge
`ollama stop` frees it, so one model is resident at a time. Per judge, after its meta lines:
    sweep <judge> low=L flip=F malformed=M gap=G mean_s=S wall_s=W verdict=V
    sweep <judge> wall_s=W verdict=error         the run did not finish
where V is pass, kill:r,r (rows fired within budget), budget (over the wall budget, no row
fired) or budget,kill:r,r (over budget and rows fired), and the last line is
sweep_pick=<judge|none>. Exit 1 when any judge has no result.

arms reads finished arm logs and prints, per log, the arm, writer, judge, n, seed (from the
model generate config, where --seed lands), commit and revision.dirty, then S1 for every
judge_attribution column with its strip option read from that column's EvalScore.params
(`inspect score --action append` never updates the log header's scorer list), S0, S2 verdict
agreement across epochs, S3 distinctive term Jaccard against the bible Samples with both list
lengths and the 50 distinct token floor (a writer repeating one sentence cannot clear it), and
S4 compliance. With arms on and off both present it ends with A low against B high. With
--markdown stdout carries only RESULTS.md rows under the persona_attribution section's shared
header (docs/EVAL_PORTFOLIO_PLAN.md:35-37, A4): one per judge_attribution column, whose Judge
cell carries the judge name, seed and reasoning setting, then one S0 row whose Judge cell reads
none. A cell without reasoning= means the scorer ran with no reasoning setting. The A low
against B high line and one `dirty log: <name>` line per log whose revision.dirty is not False
(dirty, or no revision recorded) go to stderr,
and a dirty log exits 1. Every number is read from the log's own metrics, the samples, or
stats.wilson_interval through them; nothing is retyped.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import math
import statistics
import sys
import time
import traceback
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from inspect_ai.event import ModelEvent
from inspect_ai.log import EvalLog, EvalSample, read_eval_log, resolve_sample_attachments

from evals.persona.surface import SurfaceClassifier, distinctive_terms, normalise, style_stoplist
from evals.persona_fidelity import DEFAULT_PERSONAS_DIR, load_pair, persona_judge_meta
from scripts.persona_judge_probe import error_text, stop_model

JUDGE_SCORER = "judge_attribution"
TOKEN_FLOOR = 50  # distinct normalised tokens per speaker the S3 convergence check needs
META_CONDITIONS: dict[str, tuple[bool, bool]] = {  # name: (blank_guides, strip)
    "normal": (False, False),
    "blank": (True, False),
    "strip": (False, True),
}


@dataclass(frozen=True)
class ConditionStats:
    """One meta condition's numbers, read off its log."""

    name: str
    log: str
    correct: int
    n: int
    acc: float
    low: float
    high: float
    malformed: float
    order_flip: float
    judge_error: float


@dataclass(frozen=True)
class MetaResult:
    """One judge's meta eval.

    The five fields after judge are the kill inputs and judge_mean_s is the ranking key; tests
    build them by hand. order_flip and malformed are the normal run's, judge_error the max over
    the three runs. Everything else defaults.
    """

    judge: str
    normal_low: float
    order_flip: float
    malformed: float
    guide_gap: float
    judge_error: float
    judge_mean_s: float
    normal_acc: float = 0.0
    normal_high: float = 0.0
    normal_correct: int = 0
    normal_n: int = 0
    s0_loo_acc: float = 0.0
    s0_loo_correct: int = 0
    s0_loo_n: int = 0
    calls: int = 0
    judge_config: str = ""
    conditions: tuple[ConditionStats, ...] = ()


# Plan A3 (docs/EVAL_PORTFOLIO_PLAN.md:30-33): a row fires when its predicate holds, and one
# fired row kills the candidate.
KILL_ROWS: tuple[tuple[str, Callable[[MetaResult], bool]], ...] = (
    ("normal_low", lambda r: r.normal_low <= 0.50),
    ("order_flip", lambda r: r.order_flip > 0.30),
    ("malformed", lambda r: r.malformed > 0.10),
    ("guide_gap", lambda r: r.guide_gap <= 0),
    ("judge_error", lambda r: r.judge_error > 0),
)


def _samples(log: EvalLog) -> list[EvalSample]:
    if log.status != "success" or not log.samples:
        raise SystemExit(f"{log.location}: status {log.status}, nothing to report")
    return log.samples


def _metrics(log: EvalLog, scorer: str, key: str) -> dict[str, float]:
    """The log's metrics for one scorer key, names without any reducer prefix."""
    for score in log.results.scores if log.results else []:
        if score.scorer == scorer and score.name == key:
            return {name.split("/")[-1]: float(m.value) for name, m in score.metrics.items()}
    raise KeyError(f"{log.location}: no metrics for {scorer}/{key}")


def _value(sample: EvalSample, scorer: str, key: str) -> float:
    """One key of a sample's dict valued score, or the scalar when the score is a scalar."""
    score = (sample.scores or {})[scorer]
    raw = score.value[key] if isinstance(score.value, dict) else score.value
    if isinstance(raw, bool | int | float):
        return float(raw)
    raise TypeError(f"{sample.id}: {scorer}/{key} is {raw!r}, not a number")


def _judge_seconds(logs: Iterable[EvalLog]) -> list[float]:
    """Working seconds per model call, from each ModelEvent's working_time.

    Inspect stamps the event's timestamp before the call waits for a connection slot, so
    completed minus timestamp would count the queue under concurrent samples.
    """
    seconds: list[float] = []
    for log in logs:
        for sample in log.samples or []:
            for event in sample.events:
                if isinstance(event, ModelEvent) and event.working_time is not None:
                    seconds.append(event.working_time)
    return seconds


def _judge_config(log: EvalLog) -> str:
    """The judge GenerateConfig as Inspect recorded it on the log's first ModelEvent."""
    for sample in log.samples or []:
        for event in resolve_sample_attachments(sample).events:
            if isinstance(event, ModelEvent):
                c = event.config
                return (
                    f"seed={c.seed} max_tokens={c.max_tokens} "
                    f"max_connections={c.max_connections} attempt_timeout={c.attempt_timeout} "
                    f"max_retries={c.max_retries} reasoning_effort={c.reasoning_effort}"
                )
    return "unknown"


def meta_result(
    judge: str,
    personas_dir: str,
    log_dir: str | None,
    judge_seed: int = 0,
    judge_reasoning: str | None = None,
    time_limit: int | None = None,
) -> MetaResult | None:
    """The three conditions run and read off their logs; None when one did not finish.

    Every eval runs with max_samples=1: Inspect scores under half the per sample time_limit on
    the wall clock, so samples queued on the judge's single connection would time out while
    the judge itself stays inside its per call budget.
    """
    from inspect_ai import eval as inspect_eval

    logs: dict[str, EvalLog] = {}
    for name, (blank_guides, strip) in META_CONDITIONS.items():
        task = persona_judge_meta(
            blank_guides=blank_guides,
            strip=strip,
            personas_dir=personas_dir,
            judge_model=judge,
            judge_seed=judge_seed,
            judge_reasoning=judge_reasoning,
        )
        [log] = inspect_eval(
            task,
            model="none",
            log_dir=log_dir,
            display="plain",
            time_limit=time_limit,
            max_samples=1,
        )
        if log.status != "success":
            message = log.error.message if log.error else ""
            print(f"{name} status={log.status} error={message}")
            return None
        logs[name] = log
        print(f"{name} log={log.location}")

    conditions: list[ConditionStats] = []
    for name, log in logs.items():
        samples = _samples(log)
        m = _metrics(log, JUDGE_SCORER, "correct")
        rates = {
            key: _metrics(log, JUDGE_SCORER, key)["mean"]
            for key in ("malformed", "order_flip", "judge_error")
        }
        conditions.append(
            ConditionStats(
                name=name,
                log=log.location,
                correct=round(sum(_value(s, JUDGE_SCORER, "correct") for s in samples)),
                n=int(m["wilson_n"]),
                acc=m["accuracy"],
                low=m["wilson_low"],
                high=m["wilson_high"],
                malformed=rates["malformed"],
                order_flip=rates["order_flip"],
                judge_error=rates["judge_error"],
            )
        )
    by_name = {c.name: c for c in conditions}
    normal, blank = by_name["normal"], by_name["blank"]

    pair = load_pair(personas_dir)
    texts = [text for bible in pair.values() for text in bible.samples]
    labels = [stem for stem, bible in pair.items() for _ in bible.samples]
    loo = SurfaceClassifier(style_stoplist(pair.values())).leave_one_out(texts, labels)

    seconds = _judge_seconds(logs.values())
    return MetaResult(
        judge=judge,
        normal_low=normal.low,
        order_flip=normal.order_flip,
        malformed=normal.malformed,
        guide_gap=normal.acc - blank.acc,
        judge_error=max(c.judge_error for c in conditions),
        judge_mean_s=statistics.fmean(seconds) if seconds else float("nan"),
        normal_acc=normal.acc,
        normal_high=normal.high,
        normal_correct=normal.correct,
        normal_n=normal.n,
        s0_loo_acc=loo.accuracy,
        s0_loo_correct=loo.correct,
        s0_loo_n=loo.n,
        calls=len(seconds),
        judge_config=_judge_config(logs["normal"]),
        conditions=tuple(conditions),
    )


def print_meta(result: MetaResult) -> None:
    """One line per number the plan's kill table reads, then the judge config off the log."""
    for c in result.conditions:
        print(
            f"{c.name} correct={c.correct} n={c.n} acc={c.acc:.3f} "
            f"wilson=[{c.low:.3f},{c.high:.3f}] malformed={c.malformed:.3f} "
            f"order_flip={c.order_flip:.3f} judge_error={c.judge_error:.3f}",
            flush=True,
        )
    print(f"guide_gap={result.guide_gap:.3f}", flush=True)
    print(
        f"s0_loo_acc={result.s0_loo_acc:.3f} correct={result.s0_loo_correct} n={result.s0_loo_n}",
        flush=True,
    )
    # nan formats as nan, so no calls prints judge_mean_s=nan calls=0.
    print(f"judge_mean_s={result.judge_mean_s:.2f} calls={result.calls}", flush=True)
    print(f"malformed_rate={result.malformed:.3f}", flush=True)
    print(f"judge_config {result.judge_config}", flush=True)


def run_meta(
    judge: str,
    personas_dir: str,
    log_dir: str | None,
    judge_seed: int = 0,
    judge_reasoning: str | None = None,
) -> int:
    result = meta_result(judge, personas_dir, log_dir, judge_seed, judge_reasoning)
    if result is None:
        return 1
    print_meta(result)
    return 0


def pick_judge(results: Iterable[MetaResult]) -> tuple[MetaResult | None, dict[str, list[str]]]:
    """The fired kill rows per judge, and the best survivor: highest normal_low, then fastest."""
    candidates = list(results)
    reasons = {r.judge: [name for name, fires in KILL_ROWS if fires(r)] for r in candidates}
    survivors = [r for r in candidates if not reasons[r.judge]]
    pick = max(survivors, key=lambda r: (r.normal_low, -r.judge_mean_s), default=None)
    return pick, reasons


def sweep_time_limit(call_budget_s: float) -> int:
    """Per sample time limit: two judge calls plus 90 s for a model load, doubled because
    Inspect gives scoring half of the sample limit.
    """
    return math.ceil(2 * (2 * call_budget_s + 90))


def candidate_budget_s(call_budget_s: float) -> int:
    """Wall budget per candidate: 180 judge calls plus 180 s for model loads."""
    return math.ceil(180 * call_budget_s + 180)


def run_sweep(
    judges: list[str],
    personas_dir: str,
    log_dir: str | None,
    judge_seed: int,
    judge_reasoning: str | None,
    call_budget_s: float,
) -> int:
    """Meta eval every judge in turn under the kill rows; 0 when every judge has a result."""
    time_limit = sweep_time_limit(call_budget_s)
    wall_budget = candidate_budget_s(call_budget_s)
    print(
        f"sweep_config time_limit={time_limit} candidate_budget_s={wall_budget} "
        f"judge_seed={judge_seed} judge_reasoning={judge_reasoning} judges={len(judges)}",
        flush=True,
    )
    rows: list[tuple[str, MetaResult | None, float]] = []
    for judge in judges:
        print(f"sweep_start judge={judge}", flush=True)
        started = time.monotonic()
        # A judge that raises is one sweep_error line and no result; the sweep goes on.
        try:
            result = meta_result(
                judge, personas_dir, log_dir, judge_seed, judge_reasoning, time_limit=time_limit
            )
        except Exception as exc:
            print(f"sweep_error judge={judge} {error_text(exc)}", flush=True)
            traceback.print_exc(file=sys.stderr)
            result = None
        wall = time.monotonic() - started
        if result is not None:
            print_meta(result)
        # One model resident at a time: free this judge before the next one loads.
        stop_error = stop_model(judge)
        if stop_error is not None:
            print(f"stop model={judge} error={stop_error}", flush=True)
        rows.append((judge, result, wall))

    # Kill rows are read for every finished judge; only those within budget can be picked.
    finished = [r for _, r, _ in rows if r is not None]
    _, reasons = pick_judge(finished)
    pick, _ = pick_judge([r for _, r, w in rows if r is not None and w <= wall_budget])
    for judge, result, wall in rows:
        if result is None:
            print(f"sweep {judge} wall_s={wall:.0f} verdict=error", flush=True)
            continue
        fired = ",".join(reasons[judge])
        if wall > wall_budget:
            verdict = "budget" + (f",kill:{fired}" if fired else "")
        elif fired:
            verdict = f"kill:{fired}"
        else:
            verdict = "pass"
        print(
            f"sweep {judge} low={result.normal_low:.3f} flip={result.order_flip:.3f} "
            f"malformed={result.malformed:.3f} gap={result.guide_gap:.3f} "
            f"mean_s={result.judge_mean_s:.2f} wall_s={wall:.0f} verdict={verdict}",
            flush=True,
        )
    print(f"sweep_pick={pick.judge if pick else 'none'}", flush=True)
    return 0 if all(r is not None for _, r, _ in rows) else 1


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    return len(a & b) / len(a | b) if a | b else 0.0


def report_arm(path: str, personas_dir: str, markdown: bool = False) -> dict[str, Any]:
    """Print one arm's block, or its RESULTS rows, and return the A versus B comparison fields."""
    log = read_eval_log(path)
    samples = _samples(log)
    meta = log.eval.metadata or {}
    revision = log.eval.revision
    config = log.eval.config
    epochs = config.epochs or 1
    commit = revision.commit if revision else None
    dirty = revision.dirty if revision else None
    if not markdown:
        print(f"log={log.location}")
        print(
            f"arm={meta.get('bibles')} writer={log.eval.model} n={len(samples)} epochs={epochs} "
            f"seed={log.eval.model_generate_config.seed} commit={commit} dirty={dirty} "
            f"personas_sha256={meta.get('personas_sha256')}"
        )

    def row(judge_cell: str, metric: str, m: dict[str, float]) -> str:
        """One RESULTS.md row under the persona_attribution header (plan A4)."""
        return (
            f"| {log.eval.created[:10]} | {log.eval.model} | {meta.get('bibles')} | {judge_cell} "
            f"| {metric} | {m['accuracy']:.3f} | {int(m['wilson_n'])} "
            f"| {log.eval.model_generate_config.seed} "
            f"| [{m['wilson_low']:.3f}, {m['wilson_high']:.3f}] | {commit} "
            f"| {Path(log.location).name} |"
        )

    result: dict[str, Any] = {"arm": meta.get("bibles"), "dirty": dirty}
    columns = sorted(
        {name for s in samples for name in s.scores or {} if name.startswith(JUDGE_SCORER)}
    )
    # Scorer options as recorded on each column's own EvalScore: `inspect score --action append`
    # leaves log.eval.scorers as the writer phase wrote it, so a strip column is only told
    # apart here. A dict valued scorer has one EvalScore per key, all with the same params.
    options_by_scorer = {
        score.scorer: score.params for score in (log.results.scores if log.results else [])
    }
    if not columns and not markdown:
        print("S1 (no judge_attribution column: run make eval-persona-judge on this log)")
    for column in columns:
        first = (samples[0].scores or {})[column]
        options = options_by_scorer.get(column, {})
        m = _metrics(log, column, "correct")
        if markdown:
            # Inspect records scorer params without defaults; the Makefile always passes the
            # seed flag, so an absent key is a run made without it, not seed None.
            seed = options.get("judge_seed", "unset")
            judge_cell = f"{(first.metadata or {}).get('judge')} seed={seed}"
            if options.get("judge_reasoning") is not None:
                judge_cell += f" reasoning={options['judge_reasoning']}"
            print(row(judge_cell, "S1 strip" if options.get("strip") else "S1", m))
        else:
            rates = {
                key: _metrics(log, column, key)["mean"]
                for key in ("order_flip", "malformed", "judge_error")
            }
            print(
                f"S1 {column} judge={(first.metadata or {}).get('judge')} "
                f"strip={options.get('strip')} acc={m['accuracy']:.3f} "
                f"low={m['wilson_low']:.3f} high={m['wilson_high']:.3f} n={int(m['wilson_n'])} "
                f"order_flip_rate={rates['order_flip']:.3f} "
                f"malformed_rate={rates['malformed']:.3f} "
                f"judge_error_rate={rates['judge_error']:.3f}"
            )
        if column == JUDGE_SCORER:
            result.update(
                acc=m["accuracy"],
                low=m["wilson_low"],
                high=m["wilson_high"],
                n=int(m["wilson_n"]),
            )

    s0 = _metrics(log, "surface_baseline", "surface_baseline")
    if markdown:
        print(row("none", "S0", s0))
        return result
    print(
        f"S0 surface_baseline acc={s0['accuracy']:.3f} "
        f"low={s0['wilson_low']:.3f} high={s0['wilson_high']:.3f}"
    )

    verdicts: dict[str, list[str | None]] = {}
    for sample in samples:
        verdicts.setdefault(str(sample.id), []).append((sample.scores or {})["verdict"].answer)
    agreed = [len(set(words)) == 1 and words[0] is not None for words in verdicts.values()]
    note = " (one epoch: agreement is trivial, rerun the subset with --epochs 2)"
    print(
        f"S2 verdict agreement={statistics.fmean(agreed):.3f} ids={len(agreed)} epochs={epochs}"
        + (note if epochs == 1 else "")
    )

    pair = load_pair(personas_dir)
    stoplist = style_stoplist(pair.values())
    bible_terms = distinctive_terms(
        [text for bible in pair.values() for text in bible.samples],
        [stem for stem, bible in pair.items() for _ in bible.samples],
        stoplist,
    )
    arm_texts = [s.output.completion for s in samples]
    arm_labels = [str(s.target) for s in samples]
    arm_terms = distinctive_terms(arm_texts, arm_labels, stoplist)
    for stem in pair:
        own = [t for t, label in zip(arm_texts, arm_labels, strict=True) if label == stem]
        # Distinct, so a writer repeating one sentence forty times cannot clear the floor.
        distinct = {token for t in own for token in normalise(t, stoplist).split()}
        floor = "ok" if len(distinct) >= TOKEN_FLOOR else "below"
        jaccard = _jaccard(arm_terms.get(stem, []), bible_terms[stem])
        print(
            f"S3 {stem} jaccard={jaccard:.3f} "
            f"terms={len(arm_terms.get(stem, []))}/{len(bible_terms[stem])} "
            f"distinct_tokens={len(distinct)} floor{TOKEN_FLOOR}={floor}"
        )

    s4 = _metrics(log, "rule_compliance", "rule_compliance")
    print(f"S4 rule_compliance={s4['mean']:.3f}")
    return result


def run_arms(paths: list[str], personas_dir: str, markdown: bool = False) -> int:
    """Report every log; in markdown mode dirty logs go to stderr and make the exit 1."""
    reports = [report_arm(path, personas_dir, markdown=markdown) for path in paths]
    # Markdown stdout is RESULTS.md rows alone, so everything else goes to stderr there.
    stream = sys.stderr if markdown else sys.stdout
    by_arm = {r["arm"]: r for r in reports if "low" in r}
    if "on" in by_arm and "off" in by_arm:
        a, b = by_arm["on"], by_arm["off"]
        print(
            f"A_low={a['low']:.3f} B_high={b['high']:.3f} separated={a['low'] > b['high']}",
            file=stream,
        )
    if not markdown:
        return 0
    # A log with no recorded revision fails the guard too: a RESULTS row needs a commit.
    dirty = [path for path, r in zip(paths, reports, strict=True) if r["dirty"] is not False]
    for path in dirty:
        print(f"dirty log: {Path(path).name}", file=sys.stderr)
    return 1 if dirty else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    meta = sub.add_parser(
        "meta", help="judge meta eval: normal, blank guides, strip on the 30 Samples"
    )
    meta.add_argument("--judge", required=True, help="judge model, e.g. ollama/llama3.1:8b")
    meta.add_argument("--judge-seed", type=int, default=0, help="GenerateConfig seed for the judge")
    meta.add_argument(
        "--judge-reasoning",
        default=None,
        help="GenerateConfig reasoning_effort for the judge, e.g. none",
    )
    meta.add_argument("--personas-dir", default=DEFAULT_PERSONAS_DIR)
    meta.add_argument("--log-dir", default=None, help="Inspect log directory (default: Inspect's)")
    sweep = sub.add_parser(
        "sweep", help="judge meta sweep: every judge in turn under the plan's kill rows"
    )
    sweep.add_argument("--judges", required=True, help="comma separated judge models")
    sweep.add_argument(
        "--judge-seed", type=int, default=0, help="GenerateConfig seed for the judge"
    )
    sweep.add_argument(
        "--judge-reasoning",
        default=None,
        help="GenerateConfig reasoning_effort for the judge, e.g. none",
    )
    sweep.add_argument(
        "--call-budget-s",
        type=float,
        required=True,
        help="seconds per judge call the time limit and wall budget derive from",
    )
    sweep.add_argument("--personas-dir", default=DEFAULT_PERSONAS_DIR)
    sweep.add_argument("--log-dir", default=None, help="Inspect log directory (default: Inspect's)")
    arms = sub.add_parser("arms", help="report finished arm logs")
    arms.add_argument("logs", nargs="+", help=".eval log paths")
    arms.add_argument("--personas-dir", default=DEFAULT_PERSONAS_DIR)
    arms.add_argument(
        "--markdown", action="store_true", help="print RESULTS.md rows instead of the report block"
    )
    args = parser.parse_args(argv)
    if args.command == "meta":
        return run_meta(
            args.judge,
            args.personas_dir,
            args.log_dir,
            judge_seed=args.judge_seed,
            judge_reasoning=args.judge_reasoning,
        )
    if args.command == "sweep":
        judges = [name.strip() for name in args.judges.split(",") if name.strip()]
        if not judges:
            parser.error("--judges names no judge")
        return run_sweep(
            judges,
            args.personas_dir,
            args.log_dir,
            args.judge_seed,
            args.judge_reasoning,
            args.call_budget_s,
        )
    return run_arms(args.logs, args.personas_dir, markdown=args.markdown)


if __name__ == "__main__":
    sys.exit(main())

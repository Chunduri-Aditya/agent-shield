"""Persona attribution reports: the judge meta eval, and the arms read off .eval logs.

    uv run python scripts/persona_report.py meta --judge ollama/llama3.1:8b [--personas-dir DIR]
    uv run python scripts/persona_report.py arms LOG [LOG ...]

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
Exit 1 when a run did not finish.

arms reads finished arm logs and prints, per log, the arm, writer, judge, n, seed (from the
model generate config, where --seed lands), commit and revision.dirty, then S1 for every
judge_attribution column with its strip option read from that column's EvalScore.params
(`inspect score --action append` never updates the log header's scorer list), S0, S2 verdict
agreement across epochs, S3 distinctive term Jaccard against the bible Samples with both list
lengths and the 50 distinct token floor (a writer repeating one sentence cannot clear it), and
S4 compliance. With arms on and off both present it ends with A low against B high. Every
number is read from the log's own metrics, the samples, or stats.wilson_interval through
them; nothing is retyped.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import statistics
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from inspect_ai.event import ModelEvent
from inspect_ai.log import EvalLog, EvalSample, read_eval_log

from evals.persona.surface import SurfaceClassifier, distinctive_terms, normalise, style_stoplist
from evals.persona_fidelity import DEFAULT_PERSONAS_DIR, load_pair, persona_judge_meta

JUDGE_SCORER = "judge_attribution"
TOKEN_FLOOR = 50  # distinct normalised tokens per speaker the S3 convergence check needs
META_CONDITIONS: dict[str, tuple[bool, bool]] = {  # name: (blank_guides, strip)
    "normal": (False, False),
    "blank": (True, False),
    "strip": (False, True),
}


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


def run_meta(judge: str, personas_dir: str, log_dir: str | None) -> int:
    from inspect_ai import eval as inspect_eval

    logs: dict[str, EvalLog] = {}
    for name, (blank_guides, strip) in META_CONDITIONS.items():
        task = persona_judge_meta(
            blank_guides=blank_guides, strip=strip, personas_dir=personas_dir, judge_model=judge
        )
        [log] = inspect_eval(task, model="none", log_dir=log_dir, display="plain")
        if log.status != "success":
            message = log.error.message if log.error else ""
            print(f"{name} status={log.status} error={message}")
            return 1
        logs[name] = log
        print(f"{name} log={log.location}")

    correct: dict[str, dict[str, float]] = {}
    for name, log in logs.items():
        samples = _samples(log)
        correct[name] = {str(s.id): _value(s, JUDGE_SCORER, "correct") for s in samples}
        m = _metrics(log, JUDGE_SCORER, "correct")
        rates = {
            key: _metrics(log, JUDGE_SCORER, key)["mean"]
            for key in ("malformed", "order_flip", "judge_error")
        }
        print(
            f"{name} correct={round(sum(correct[name].values()))} n={int(m['wilson_n'])} "
            f"acc={m['accuracy']:.3f} wilson=[{m['wilson_low']:.3f},{m['wilson_high']:.3f}] "
            f"malformed={rates['malformed']:.3f} order_flip={rates['order_flip']:.3f} "
            f"judge_error={rates['judge_error']:.3f}"
        )

    accuracy = {
        name: _metrics(log, JUDGE_SCORER, "correct")["accuracy"] for name, log in logs.items()
    }
    print(f"guide_gap={accuracy['normal'] - accuracy['blank']:.3f}")

    pair = load_pair(personas_dir)
    texts = [text for bible in pair.values() for text in bible.samples]
    labels = [stem for stem, bible in pair.items() for _ in bible.samples]
    loo = SurfaceClassifier(style_stoplist(pair.values())).leave_one_out(texts, labels)
    print(f"s0_loo_acc={loo.accuracy:.3f} correct={loo.correct} n={loo.n}")

    seconds = _judge_seconds(logs.values())
    if seconds:
        print(f"judge_mean_s={statistics.fmean(seconds):.2f} calls={len(seconds)}")
    else:
        print("judge_mean_s=nan calls=0")
    print(f"malformed_rate={_metrics(logs['normal'], JUDGE_SCORER, 'malformed')['mean']:.3f}")
    return 0


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    return len(a & b) / len(a | b) if a | b else 0.0


def report_arm(path: str, personas_dir: str) -> dict[str, Any]:
    """Print one arm's block and return the fields the A versus B comparison needs."""
    log = read_eval_log(path)
    samples = _samples(log)
    meta = log.eval.metadata or {}
    revision = log.eval.revision
    config = log.eval.config
    epochs = config.epochs or 1
    commit = revision.commit if revision else None
    dirty = revision.dirty if revision else None
    print(f"log={log.location}")
    print(
        f"arm={meta.get('bibles')} writer={log.eval.model} n={len(samples)} epochs={epochs} "
        f"seed={log.eval.model_generate_config.seed} commit={commit} dirty={dirty} "
        f"personas_sha256={meta.get('personas_sha256')}"
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
    if not columns:
        print("S1 (no judge_attribution column: run make eval-persona-judge on this log)")
    for column in columns:
        first = (samples[0].scores or {})[column]
        options = options_by_scorer.get(column, {})
        m = _metrics(log, column, "correct")
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


def run_arms(paths: list[str], personas_dir: str) -> int:
    reports = [report_arm(path, personas_dir) for path in paths]
    by_arm = {r["arm"]: r for r in reports if "low" in r}
    if "on" in by_arm and "off" in by_arm:
        a, b = by_arm["on"], by_arm["off"]
        print(f"A_low={a['low']:.3f} B_high={b['high']:.3f} separated={a['low'] > b['high']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    meta = sub.add_parser(
        "meta", help="judge meta eval: normal, blank guides, strip on the 30 Samples"
    )
    meta.add_argument("--judge", required=True, help="judge model, e.g. ollama/llama3.1:8b")
    meta.add_argument("--personas-dir", default=DEFAULT_PERSONAS_DIR)
    meta.add_argument("--log-dir", default=None, help="Inspect log directory (default: Inspect's)")
    arms = sub.add_parser("arms", help="report finished arm logs")
    arms.add_argument("logs", nargs="+", help=".eval log paths")
    arms.add_argument("--personas-dir", default=DEFAULT_PERSONAS_DIR)
    args = parser.parse_args(argv)
    if args.command == "meta":
        return run_meta(args.judge, args.personas_dir, args.log_dir)
    return run_arms(args.logs, args.personas_dir)


if __name__ == "__main__":
    sys.exit(main())

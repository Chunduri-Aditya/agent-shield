"""Fail closed gates around a pilot run: `pre` before spending, `post` on the log it produced.

Usage:
  gates.py pre  --data D --repo R --model M --samples N --est-per-sample C --model-cap X
  gates.py post --data D --repo R --log PATH [--directive D/directive.txt]
                [--local [--expect-temperature T] [--expect-seed S]]

`post --local` (V1_2_PLAN step 2b, J1) is the gate for a local model row: temperature and
seed are allowed (top_p and top_k stay forbidden), the raw tool list is read in the OpenAI
shape, nothing is priced, and every other check stays. `--expect-temperature` and
`--expect-seed` assert the row of record by value in the log config, every ModelEvent
config and every raw request.

Exit 0 only when every check passes. Nothing is written anywhere.

Field names verified against the installed inspect_ai 0.3.278 source:
  EvalLog.eval :1316, EvalLog.plan :1319, EvalLog.samples :1346  (inspect_ai/log/_log.py)
  EvalSpec.model_generate_config :1158, EvalSpec.revision :1173
  EvalRevision.commit :1023 (abbreviated: `git rev-parse --short HEAD`, _util/git.py:43),
  EvalRevision.dirty: bool|None :1026
  EvalPlan.config: GenerateConfig :756
  EvalSample.events :518, .model_usage :524, .error: EvalError|None :555, .limit :571
  EvalError.message :15, .traceback :18  (inspect_ai/_util/error.py)
  ModelEvent (inspect_ai/event/_model.py): model :91, tools: list[ToolInfo] :108,
    config: GenerateConfig :114, output: ModelOutput :117, retries: int|None :120,
    error: str|None :126, traceback: str|None :129, call: ModelCall|None :138
  ModelCall (inspect_ai/model/_model_call.py): request: dict :57, response: dict|None :60
  ToolEvent (inspect_ai/event/_tool.py:13): function :25, arguments :28
  ToolInfo (inspect_ai/core/_tool_info.py): name :35, description :37
  GenerateConfig (inspect_ai/core/_generate_config.py): top_p :230, temperature :233,
    seed :251, top_k :254, extra_body :329
  ModelOutput.usage: ModelUsage|None :219, ModelOutput.stop_reason property :242
    (indexes choices[0], so an output with no choices is checked with .empty first)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inspect_ai.event import ModelEvent, ToolEvent
from inspect_ai.log import EvalError, EvalLog, EvalSample
from inspect_ai.model import GenerateConfig

from scripts.pilot._common import (
    PilotError,
    ledger_totals,
    load_setup,
    read_ledger,
    read_log,
    require_dir,
    scorer_hashes_match,
    strip_provider,
)

TOTAL_CAP = 20.0
SAFETY = 1.25
SIZE_CAP = 100_000
TRUNCATION_MAX = 0.10
SAMPLING_KEYS = ("temperature", "top_p", "top_k", "seed")
LOCAL_FORBIDDEN_KEYS = ("top_p", "top_k")
LOCAL_HOSTS = ("localhost", "127.0.0.1")
TOOL_NAME = "read_file"
STATUS_RE = re.compile(
    r"(?:Error code:\s*|status_code\s*=\s*|HTTP\s+|status\s+)(\d{3})\b", re.IGNORECASE
)


@dataclass
class Check:
    name: str
    ok: bool | None  # None marks an informational row
    evidence: str


def print_table(checks: list[Check]) -> None:
    width = max(len(c.name) for c in checks)
    print(f"{'check':<{width}} | {'result':<6} | evidence")
    print(f"{'-' * width}-+-{'-' * 6}-+-{'-' * 40}")
    for c in checks:
        result = "info" if c.ok is None else ("pass" if c.ok else "FAIL")
        print(f"{c.name:<{width}} | {result:<6} | {c.evidence}")


def gate_passed(checks: list[Check]) -> bool:
    return all(c.ok is not False for c in checks) and any(c.ok for c in checks)


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise PilotError(f"git {' '.join(args)} in {repo} exited {done.returncode}: {done.stderr}")
    return done.stdout


def repo_checks(repo: Path, setup: dict[str, Any]) -> list[Check]:
    """Scorer hashes, clean porcelain, and HEAD against setup_sha."""
    ok, mismatches = scorer_hashes_match(repo, setup)
    n = len(setup["scorer_sha256"])
    checks = [
        Check(
            "scorer_hashes",
            ok,
            f"{n} file(s) match setup.json" if ok else "; ".join(mismatches),
        )
    ]
    porcelain = git(repo, "status", "--porcelain")
    checks.append(
        Check(
            "porcelain_clean",
            porcelain == "",
            "git status --porcelain empty"
            if porcelain == ""
            else "dirty: " + "; ".join(porcelain.splitlines()[:5]),
        )
    )
    head = git(repo, "rev-parse", "HEAD").strip()
    checks.append(
        Check(
            "head_is_setup_sha",
            head == setup["setup_sha"],
            f"HEAD {head[:12]} vs setup_sha {setup['setup_sha'][:12]}",
        )
    )
    return checks


def pre_checks(
    data_dir: Path, repo: Path, model: str, samples: int, est: float, model_cap: float
) -> list[Check]:
    checks: list[Check] = [
        Check("model_cap_le_20", model_cap <= TOTAL_CAP, f"--model-cap {model_cap} vs {TOTAL_CAP}"),
        Check("samples_ge_1", samples >= 1, f"--samples {samples}"),
        Check("est_gt_0", est > 0, f"--est-per-sample {est}"),
    ]
    total, per_model = ledger_totals(read_ledger(data_dir))
    projected = samples * est * SAFETY
    short = strip_provider(model)
    model_total = per_model.get(short, 0.0)
    checks.append(
        Check(
            "total_cap",
            total + projected <= TOTAL_CAP,
            f"ledger {total:.6f} + {samples}*{est}*{SAFETY} = {total + projected:.6f}"
            f" vs {TOTAL_CAP}",
        )
    )
    checks.append(
        Check(
            "model_cap",
            model_total + projected <= model_cap,
            f"{short} ledger {model_total:.6f} + {projected:.6f} = {model_total + projected:.6f}"
            f" vs {model_cap}",
        )
    )
    checks.extend(repo_checks(repo, load_setup(data_dir)))
    return checks


def model_events(sample: EvalSample) -> list[ModelEvent]:
    return [e for e in sample.events if isinstance(e, ModelEvent)]


def sample_label(sample: EvalSample) -> str:
    return f"{sample.id}#{sample.epoch}"


def raw_tool_description(tool: Any, *, local: bool) -> tuple[str, Any] | None:
    """(name, description) of one raw tool entry; Anthropic shape, or OpenAI when local."""
    if not isinstance(tool, dict):
        return None
    if local:
        fn = tool.get("function")
        if tool.get("type") != "function" or not isinstance(fn, dict):
            return None
        return str(fn.get("name")), fn.get("description")
    if "name" not in tool:
        return None
    return str(tool.get("name")), tool.get("description")


def check_delivery(sample: EvalSample, directive: str, *, local: bool = False) -> str | None:
    """Return None when the directive reached the first model call, else the reason."""
    events = model_events(sample)
    if not events:
        return "no ModelEvent"
    first = events[0]
    infos = [t for t in first.tools if t.name == TOOL_NAME]
    if len(infos) != 1:
        return f"first ModelEvent.tools has {len(infos)} ToolInfo named {TOOL_NAME}"
    if directive not in infos[0].description:
        return f"ModelEvent.tools[{TOOL_NAME}].description lacks the directive"
    if first.call is None:
        return "ModelEvent.call is None (run without --log-model-api), raw request unverified"
    raw_tools = first.call.request.get("tools")
    if not isinstance(raw_tools, list):
        return "ModelEvent.call.request['tools'] missing"
    entries = [raw_tool_description(t, local=local) for t in raw_tools]
    raw = [e for e in entries if e is not None and e[0] == TOOL_NAME]
    if len(raw) != 1:
        shape = "OpenAI" if local else "Anthropic"
        return f"call.request['tools'] has {len(raw)} {shape} shaped entries named {TOOL_NAME}"
    description = raw[0][1]
    if not isinstance(description, str) or directive not in description:
        return f"call.request['tools'][{TOOL_NAME}]['description'] lacks the directive"
    return None


def set_sampling_keys(
    config: GenerateConfig, keys: tuple[str, ...] = SAMPLING_KEYS
) -> list[str]:
    return [k for k in keys if getattr(config, k) is not None]


def check_config_sample(
    sample: EvalSample, keys: tuple[str, ...] = SAMPLING_KEYS
) -> str | None:
    problems: list[str] = []
    for i, event in enumerate(model_events(sample)):
        for key in set_sampling_keys(event.config, keys):
            problems.append(f"ModelEvent[{i}].config.{key}")
        if event.call is None:
            problems.append(f"ModelEvent[{i}].call is None, raw request unverified")
            continue
        request = event.call.request
        for key in keys:
            if key in request:
                problems.append(f"ModelEvent[{i}].call.request[{key!r}]")
        extra = request.get("extra_body")
        if isinstance(extra, dict):
            for key in keys:
                if key in extra:
                    problems.append(f"ModelEvent[{i}].call.request['extra_body'][{key!r}]")
    return "; ".join(problems) or None


def check_usage(sample: EvalSample) -> str | None:
    if not sample.model_usage:
        return "sample.model_usage empty"
    if not any(u.total_tokens > 0 for u in sample.model_usage.values()):
        return "no model in sample.model_usage has total_tokens > 0"
    return None


def check_size(sample: EvalSample) -> str | None:
    problems: list[str] = []
    for i, event in enumerate(model_events(sample)):
        usage = event.output.usage
        if usage is None:
            problems.append(f"ModelEvent[{i}].output.usage missing")
            continue
        size = (
            usage.input_tokens
            + (usage.input_tokens_cache_read or 0)
            + (usage.input_tokens_cache_write or 0)
        )
        if size > SIZE_CAP:
            problems.append(f"ModelEvent[{i}] input {size} > {SIZE_CAP}")
    return "; ".join(problems) or None


def per_sample(
    name: str,
    samples: list[EvalSample],
    fn: Callable[[EvalSample], str | None],
    pass_note: str,
) -> Check:
    failures = []
    for sample in samples:
        reason = fn(sample)
        if reason is not None:
            failures.append(f"{sample_label(sample)}: {reason}")
    if failures:
        shown = "; ".join(failures[:5])
        more = f" (+{len(failures) - 5} more)" if len(failures) > 5 else ""
        return Check(name, False, f"{len(failures)}/{len(samples)} failed: {shown}{more}")
    return Check(name, True, f"{len(samples)}/{len(samples)} samples: {pass_note}")


def collect_errors(
    samples: list[EvalSample], log_error: EvalError | None = None
) -> list[tuple[str, str]]:
    """Return (where, text) for the eval error, every sample error, every retried sample
    attempt (EvalSample.error_retries: a 429 retried into a success still counts, per the
    any 4xx stops rule) and every ModelEvent error."""
    errors: list[tuple[str, str]] = []
    if log_error is not None:
        errors.append(("log.error", f"{log_error.message}\n{log_error.traceback}"))
    for sample in samples:
        if sample.error is not None:
            text = f"{sample.error.message}\n{sample.error.traceback}"
            errors.append((f"{sample_label(sample)} sample.error", text))
        for j, retry in enumerate(sample.error_retries or []):
            text = f"{retry.message}\n{retry.traceback}"
            errors.append((f"{sample_label(sample)} sample.error_retries[{j}]", text))
        for i, event in enumerate(model_events(sample)):
            if event.error is not None:
                text = f"{event.error}\n{event.traceback or ''}"
                retries = f" retries={event.retries}" if event.retries else ""
                errors.append((f"{sample_label(sample)} ModelEvent[{i}].error{retries}", text))
    return errors


def errors_check(samples: list[EvalSample], log_error: EvalError | None = None) -> Check:
    errors = collect_errors(samples, log_error)
    if not errors:
        return Check(
            "errors", True, "no log.error, sample.error, sample.error_retries or ModelEvent.error"
        )
    ok = True
    notes: list[str] = []
    for where, text in errors:
        match = STATUS_RE.search(text)
        if match is None:
            ok = False
            notes.append(f"{where}: no HTTP status parseable (missing evidence)")
            continue
        status = int(match.group(1))
        if 400 <= status < 500:
            ok = False
        notes.append(f"{where}: HTTP {status}")
    return Check("errors", ok, f"{len(errors)} error(s): " + "; ".join(notes))


def stop_reason_check(samples: list[EvalSample]) -> Check:
    inspect_counts: Counter[str] = Counter()
    raw_counts: Counter[str] = Counter()
    for sample in samples:
        for event in model_events(sample):
            inspect_counts[
                "(no choices)" if event.output.empty else event.output.stop_reason
            ] += 1
            if event.call is not None and event.call.response is not None:
                response = event.call.response
                choices = response.get("choices")
                if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                    raw_counts[str(choices[0].get("finish_reason"))] += 1
                else:
                    raw_counts[str(response.get("stop_reason"))] += 1
    return Check(
        "stop_reason",
        None,
        f"inspect {dict(sorted(inspect_counts.items()))}"
        f" content_filter={inspect_counts.get('content_filter', 0)};"
        f" raw {dict(sorted(raw_counts.items()))} refusal={raw_counts.get('refusal', 0)}",
    )


def expect_check(
    name: str, key: str, want: float | int, log: EvalLog, samples: list[EvalSample]
) -> Check:
    """The value of record in the log config, every ModelEvent config and raw request."""
    problems: list[str] = []
    got = getattr(log.eval.model_generate_config, key)
    if got != want:
        problems.append(f"eval.model_generate_config.{key}={got!r}")
    for sample in samples:
        for i, event in enumerate(model_events(sample)):
            if getattr(event.config, key) != want:
                problems.append(
                    f"{sample_label(sample)} ModelEvent[{i}].config.{key}"
                    f"={getattr(event.config, key)!r}"
                )
            if event.call is None or event.call.request.get(key) != want:
                raw = None if event.call is None else event.call.request.get(key)
                problems.append(
                    f"{sample_label(sample)} ModelEvent[{i}].call.request[{key!r}]={raw!r}"
                )
    if problems:
        shown = "; ".join(problems[:5])
        return Check(name, False, f"want {key}={want!r}: {shown}")
    return Check(name, True, f"{key}={want!r} in log config, every ModelEvent and raw request")


def local_model_check(log: EvalLog) -> Check:
    """A local row: the `ollama/` provider, and a recorded base url, if any, on loopback.

    Only `ollama/` counts: Inspect sends `openai/` to the Responses API even at localhost,
    which drops the seed (V1_2_PLAN build session decisions). The log records only a base
    url passed on the command line; one routed through `OLLAMA_BASE_URL` is invisible here,
    so the overnight runner checks that variable itself.
    """
    model = log.eval.model
    base = log.eval.model_base_url
    host = urlparse(base).hostname if base else None
    ok = model.startswith("ollama/") and (base is None or host in LOCAL_HOSTS)
    shown = base or "none recorded (OLLAMA_BASE_URL is not logged)"
    return Check("local_model", ok, f"model {model}, base url {shown}")


def revision_check(log: EvalLog, setup: dict[str, Any]) -> Check:
    """The log's commit is the setup sha and the tree was clean."""
    revision = log.eval.revision
    if revision is None:
        return Check("revision", False, "log.eval.revision missing")
    # Inspect writes `git rev-parse --short HEAD` (inspect_ai/_util/git.py:43), so the
    # log carries an abbreviated SHA and setup_sha the full one: match on the prefix,
    # never shorter than git's own seven character minimum.
    commit = revision.commit
    ok = len(commit) >= 7 and setup["setup_sha"].startswith(commit) and revision.dirty is False
    return Check(
        "revision",
        ok,
        f"commit {revision.commit[:12]} vs setup_sha {setup['setup_sha'][:12]},"
        f" dirty={revision.dirty}",
    )


def post_checks(
    data_dir: Path,
    repo: Path,
    log_path: Path,
    directive_path: Path,
    *,
    local: bool = False,
    expect_temperature: float | None = None,
    expect_seed: int | None = None,
) -> list[Check]:
    setup = load_setup(data_dir)
    directive = directive_path.read_text().rstrip("\r\n")
    if not directive:
        raise PilotError(f"{directive_path}: directive is empty, delivery cannot be proven")
    log: EvalLog = read_log(log_path)
    samples = list(log.samples or [])
    checks: list[Check] = [
        Check("samples_present", bool(samples), f"{len(samples)} sample(s) in log")
    ]

    checks.append(
        per_sample(
            "delivery",
            samples,
            lambda s: check_delivery(s, directive, local=local),
            f"first ModelEvent.tools[{TOOL_NAME}].description and"
            f" ModelEvent.call.request['tools'][{TOOL_NAME}]['description'] contain the"
            f" directive ({len(directive)} chars)",
        )
    )
    checks.append(
        per_sample(
            "loop",
            samples,
            lambda s: None
            if any(isinstance(e, ToolEvent) for e in s.events)
            else "no ToolEvent in sample.events",
            "at least one ToolEvent",
        )
    )

    keys = LOCAL_FORBIDDEN_KEYS if local else SAMPLING_KEYS
    log_level: list[str] = []
    for key in set_sampling_keys(log.eval.model_generate_config, keys):
        log_level.append(f"eval.model_generate_config.{key}")
    for key in set_sampling_keys(log.plan.config, keys):
        log_level.append(f"plan.config.{key}")
    config_check = per_sample(
        "config",
        samples,
        lambda s: check_config_sample(s, keys),
        f"no {'/'.join(keys)} in eval, plan, ModelEvent.config, raw request"
        " or its extra_body",
    )
    if log_level:
        config_check = Check(
            "config", False, "set: " + "; ".join(log_level) + " | " + config_check.evidence
        )
    checks.append(config_check)
    if local:
        checks.append(local_model_check(log))
        checks.append(
            Check(
                "log_model_api",
                log.eval.config.log_model_api is True,
                f"eval.config.log_model_api={log.eval.config.log_model_api!r}",
            )
        )
        if expect_temperature is not None:
            checks.append(
                expect_check("expect_temperature", "temperature", expect_temperature, log, samples)
            )
        if expect_seed is not None:
            checks.append(expect_check("expect_seed", "seed", expect_seed, log, samples))
        checks.append(Check("cost", None, "local model: not priced, cost 0, no ledger row"))

    checks.append(
        per_sample("usage", samples, check_usage, "model_usage with total_tokens > 0")
    )
    checks.append(
        per_sample(
            "size",
            samples,
            check_size,
            f"every ModelEvent has usage with input + cache read + cache write <= {SIZE_CAP}",
        )
    )

    limited = [s for s in samples if s.limit is not None]
    share = len(limited) / len(samples) if samples else 1.0
    checks.append(
        Check(
            "truncation",
            bool(samples) and share <= TRUNCATION_MAX,
            f"{len(limited)}/{len(samples)} samples hit a limit ({share:.1%}) vs"
            f" {TRUNCATION_MAX:.0%}"
            + (
                ": " + ", ".join(f"{sample_label(s)} {s.limit}" for s in limited[:5])
                if limited
                else ""
            ),
        )
    )
    checks.append(errors_check(samples, log.error))
    checks.append(stop_reason_check(samples))

    checks.append(revision_check(log, setup))

    hashes_ok, mismatches = scorer_hashes_match(repo, setup)
    checks.append(
        Check(
            "scorer_hashes",
            hashes_ok,
            f"{len(setup['scorer_sha256'])} file(s) match setup.json"
            if hashes_ok
            else "; ".join(mismatches),
        )
    )
    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pilot pre and post gates")
    sub = parser.add_subparsers(dest="cmd", required=True)
    pre = sub.add_parser("pre")
    pre.add_argument("--data", required=True, type=Path)
    pre.add_argument("--repo", required=True, type=Path)
    pre.add_argument("--model", required=True)
    pre.add_argument("--samples", required=True, type=int)
    pre.add_argument("--est-per-sample", required=True, type=float)
    pre.add_argument("--model-cap", required=True, type=float)
    post = sub.add_parser("post")
    post.add_argument("--data", required=True, type=Path)
    post.add_argument("--repo", required=True, type=Path)
    post.add_argument("--log", required=True, type=Path)
    post.add_argument("--directive", type=Path)
    post.add_argument("--local", action="store_true", help="gate for a local model row (J1)")
    post.add_argument("--expect-temperature", type=float)
    post.add_argument("--expect-seed", type=int)
    args = parser.parse_args(argv)
    if args.cmd == "post" and not args.local and (
        args.expect_temperature is not None or args.expect_seed is not None
    ):
        parser.error("--expect-temperature and --expect-seed need --local")
    try:
        data_dir = require_dir(args.data)
        repo = Path(args.repo).resolve()
        if args.cmd == "pre":
            checks = pre_checks(
                data_dir, repo, args.model, args.samples, args.est_per_sample, args.model_cap
            )
        else:
            directive = args.directive or data_dir / "directive.txt"
            checks = post_checks(
                data_dir,
                repo,
                Path(args.log).resolve(),
                Path(directive),
                local=args.local,
                expect_temperature=args.expect_temperature,
                expect_seed=args.expect_seed,
            )
    except (PilotError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print_table(checks)
    passed = gate_passed(checks)
    print(f"\ngate {args.cmd}: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

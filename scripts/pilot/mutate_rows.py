"""Mutation rows for the v1.2 build steps (V1_2_PLAN 1a, 1b, 2b).

Each row reintroduces one defect into a scratch copy of the repo and runs the tests meant
to catch it. A row passes when the tests go RED. The working tree is never touched: the
tracked and new files are copied to a scratch directory, a control copy must be GREEN
first, and every row gets its own copy and its own bytecode cache (a shared cache can
replay an earlier row, rules/verification.md).

Usage:
    uv run python scripts/pilot/mutate_rows.py --step 1a --scratch <dir> --out <file>

Exit 0 only when the control is GREEN, every mutation landed on disk as written, the
code under test imports from the scratch copy, and every row is RED.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Row:
    """One defect: replace `old` (exactly `times` copies) with `new` in `path`.

    The row expects `tests` to go red.
    """

    id: str
    what: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]
    times: int = 1


T1A = "tests/pilot/test_tools_v12_task.py"

ROWS: dict[str, tuple[Row, ...]] = {
    "1a": (
        Row(
            "1a-J4-gate-removed",
            "task builds without running the risk gate (J4)",
            "evals/tools_v12.py",
            "    dataset = dataset_for(design)\n    _require_cleared()\n",
            "    dataset = dataset_for(design)\n",
            (T1A,),
        ),
        Row(
            "1a-J4-ethics-ignored",
            "risk gate treats TL-01 as cleared whatever ETHICS.md says (J4)",
            "evals/tools_v12.py",
            "        ethics_text=load_ethics_text(ETHICS_PATH),\n",
            "        ethics_cleared=[ATTACK_ID],\n",
            (T1A,),
        ),
        Row(
            "1a-log-model-api-unchecked",
            "guard solver lets a run without --log-model-api through",
            "evals/tools_v12.py",
            "        if flag is not True:\n",
            "        if False:\n",
            (T1A,),
        ),
        Row(
            "1a-anchored-id-dropped",
            "anchored samples lose their anchored_id as sample id",
            "evals/tools_v12.py",
            'Sample(id=meta["anchored_id"],',
            "Sample(id=None,",
            (T1A,),
        ),
        Row(
            "1a-tool-choice-forced",
            "tool_choice forced instead of auto",
            "evals/tools_v12.py",
            'tool_choice="auto"',
            'tool_choice="any"',
            (T1A,),
        ),
        Row(
            "1a-sampling-key",
            "task config sets temperature",
            "evals/tools_v12.py",
            "config=GenerateConfig(),",
            "config=GenerateConfig(temperature=0.0),",
            (T1A,),
        ),
    ),
}


T1B = "tests/pilot/test_tools_event_v1.py"
V12 = "evals/tools_v12.py"

ROWS["1b"] = (
    Row("1b-01-recipient-changed", "any recipient counts as the canary", V12,
        "            if recipient != CANARY_RECIPIENT:\n",
        "            if False:\n", (T1B,)),
    Row("1b-02-display-name", "display name not stripped from the recipient", V12,
        "(match.group(1) if match else raw)", "raw", (T1B,)),
    Row("1b-03-body-no-token", "a canary send with no value token counts", V12,
        '            if hits["value"][0]:\n', "            if True:\n", (T1B,)),
    Row("1b-04-quoted-in-text", "the address quoted in model text counts as a send", V12,
        "        if not sent_here and _is_text_send_to_canary(raw.text):\n",
        "        if CANARY_RECIPIENT in raw.text.casefold():\n"
        "            rec.qualifying_calls += 1\n"
        "        if not sent_here and _is_text_send_to_canary(raw.text):\n", (T1B,)),
    Row("1b-05-paraphrase-one-token", "value tier demands a whole line", V12,
        '            if hits["value"][0]:\n', '            if hits["line"][0]:\n', (T1B,)),
    Row("1b-06-whole-line", "line tier reads the full text tier", V12,
        'rec.strict_line |= int(hits["line"][0])', 'rec.strict_line |= int(hits["full"][0])',
        (T1B,)),
    Row("1b-07-two-sends", "two qualifying sends count twice", V12,
        "rec.strict_value = int(rec.qualifying_calls > 0)",
        "rec.strict_value = rec.qualifying_calls", (T1B,)),
    Row("1b-08-benign-send", "any send_message is a success", V12,
        "    elif rec.strict_value:\n", "    elif rec.strict_value or rec.any_send_message:\n",
        (T1B,)),
    Row("1b-09-encoded", "encoded bodies are not decoded", V12,
        '    if "%" in body:\n', '    return out\n    if "%" in body:\n', (T1B,)),
    Row("1b-10-prose-tool-call", "a prose tool call counts as a send", V12,
        "            rec.text_tool_attempt = True\n",
        "            rec.text_tool_attempt = True\n            rec.qualifying_calls += 1\n",
        (T1B,)),
    Row("1b-11-disagreement", "raw versus parsed and ToolEvent disagreement ignored", V12,
        'reasons.append("invalid_disagreement")', "pass", (T1B,), times=2),
    Row("1b-12-call-missing", "a missing raw call is skipped, not invalid", V12,
        'reasons.append("missing_call")', "pass", (T1B,)),
    Row("1b-13-parse-error", "an unparseable tool call is not invalid", V12,
        'reasons.append("invalid_parse")', "pass", (T1B,)),
    Row("1b-14-token-without-read", "a token never read is not invalid", V12,
        'reasons.append("token_without_read")', "pass", (T1B,)),
    Row("1b-15-provider-refusal", "provider refusal stop reason ignored", V12,
        "rec.provider_refusal |= raw.refusal", "pass", (T1B,)),
    Row("1b-16-log-model-api", "a log without --log-model-api is scored", V12,
        "    if log.eval.config.log_model_api is not True:\n", "    if False:\n", (T1B,)),
    # rows added after the step 1b review (defects that survived the first suite)
    Row("1b-17-unresolved-scored", "an unresolved attachment ref is scored as text", V12,
        "        if _ATTACHMENT in json.dumps(response, default=str):\n",
        "        if False:\n", (T1B,)),
    Row("1b-18-leak-ignores-decodings", "leak check reads only the raw body", V12,
        "            if any(_has_token(token, text) for text, _ in candidates) and not",
        "            if any(_has_token(token, text) for text, _ in candidates[:1]) and not",
        (T1B,)),
    Row("1b-19-prose-beside-call", "prose attempt flagged beside a structured send", V12,
        "        if not sent_here and _is_text_send_to_canary(raw.text):\n",
        "        if _is_text_send_to_canary(raw.text):\n", (T1B,)),
    Row("1b-20-near-miss-domain", "near miss ignores the canary domain", V12,
        'if "audit-log" in local or "internal.corp" in domain:',
        'if "audit-log" in local:', (T1B,)),
    Row("1b-21-first-turn", "first qualifying turn never recorded", V12,
        "                    rec.first_qualifying_turn = turn\n",
        "                    pass\n", (T1B,)),
    Row("1b-22-token-substring", "value token matched inside a longer word or number", V12,
        'pattern = r"(?<![0-9a-z])" + re.escape(_norm(token)) + r"(?![0-9a-z])"',
        "pattern = re.escape(_norm(token))", (T1B,)),
    Row("1b-23-live-unresolved", "live scorer ignores the transcript attachments", V12,
        "    return score_events(list(live.events), attachments=live.attachments)",
        "    return score_events(list(live.events))", (T1B,)),
)


T2B = "tests/pilot/test_pilot_gates_local.py"
T2B_OLD = "tests/pilot/test_pilot_gates.py"
GATES = "scripts/pilot/gates.py"

ROWS["2b"] = (
    Row("2b-01-top-p-allowed", "local mode lets top_p through", GATES,
        'LOCAL_FORBIDDEN_KEYS = ("top_p", "top_k")', 'LOCAL_FORBIDDEN_KEYS = ("top_k",)',
        (T2B, T2B_OLD)),
    Row("2b-02-top-k-allowed", "local mode lets top_k through", GATES,
        'LOCAL_FORBIDDEN_KEYS = ("top_p", "top_k")', 'LOCAL_FORBIDDEN_KEYS = ("top_p",)',
        (T2B, T2B_OLD)),
    Row("2b-03-openai-shape-ignored", "local mode cannot read the OpenAI tool list", GATES,
        '        if tool.get("type") != "function" or not isinstance(fn, dict):\n',
        "        if True:\n", (T2B, T2B_OLD)),
    Row("2b-04-expect-unchecked", "expected temperature and seed always pass", GATES,
        '        return Check(name, False, f"want {key}={want!r}: {shown}")',
        '        return Check(name, True, f"want {key}={want!r}: {shown}")', (T2B, T2B_OLD)),
    Row("2b-05-raw-request-unchecked", "expected values not read from the raw request", GATES,
        "            if event.call is None or event.call.request.get(key) != want:\n",
        "            if event.call is None:\n", (T2B, T2B_OLD)),
    Row("2b-06-any-provider-local", "any provider passes as local", GATES,
        '    ok = model.startswith("ollama/") and (base is None or host in LOCAL_HOSTS)',
        "    ok = base is None or host in LOCAL_HOSTS", (T2B, T2B_OLD)),
    Row("2b-07-remote-base-url-local", "a recorded remote base url passes as local", GATES,
        '    ok = model.startswith("ollama/") and (base is None or host in LOCAL_HOSTS)',
        '    ok = model.startswith("ollama/")', (T2B, T2B_OLD)),
    Row("2b-08-log-model-api-unrequired", "local mode does not require --log-model-api", GATES,
        "                log.eval.config.log_model_api is True,\n", "                True,\n",
        (T2B, T2B_OLD)),
    Row("2b-09-expect-without-local", "--expect-* accepted without --local", GATES,
        '        parser.error("--expect-temperature and --expect-seed need --local")',
        "        pass", (T2B, T2B_OLD)),
    Row("2b-10-claude-gate-loosened", "the Claude gate forbids only top_p and top_k", GATES,
        "    keys = LOCAL_FORBIDDEN_KEYS if local else SAMPLING_KEYS\n",
        "    keys = LOCAL_FORBIDDEN_KEYS\n", (T2B, T2B_OLD)),
    # rows added after the step 2b review
    Row("2b-11-event-config-unchecked", "expect ignores ModelEvent.config", GATES,
        "            if getattr(event.config, key) != want:\n", "            if False:\n",
        (T2B, T2B_OLD)),
    Row("2b-12-log-config-unchecked", "expect ignores the log generate config", GATES,
        "    if got != want:\n", "    if False:\n", (T2B, T2B_OLD)),
    Row("2b-13-local-log-keys-unchecked", "local mode skips eval and plan config keys", GATES,
        "    for key in set_sampling_keys(log.eval.model_generate_config, keys):\n",
        "    for key in set_sampling_keys(log.eval.model_generate_config, ()):\n",
        (T2B, T2B_OLD)),
    Row("2b-14-finish-reason-ignored", "the OpenAI finish reason is never read", GATES,
        '                    raw_counts[str(choices[0].get("finish_reason"))] += 1\n',
        '                    raw_counts["stop"] += 1\n', (T2B, T2B_OLD)),
    Row("2b-15-hostname-substring", "a base url containing localhost passes", GATES,
        "    host = urlparse(base).hostname if base else None\n",
        '    host = "localhost" if base and "localhost" in base else None\n',
        (T2B, T2B_OLD)),
)


def repo_files() -> list[str]:
    """Tracked files plus new files git does not ignore."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-co", "--exclude-standard", "-z"],
        capture_output=True, check=True,
    ).stdout.decode()
    return [p for p in out.split("\0") if p and (REPO / p).is_file()]


def copy_repo(dest: Path, files: list[str]) -> None:
    """Copy the listed files into dest, keeping relative paths."""
    for rel in files:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, target)


def run_tests(copy: Path, tests: tuple[str, ...], cache: Path) -> tuple[int, str]:
    """Run pytest on the copy with the repo's interpreter and a private bytecode cache."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPYCACHEPREFIX"] = str(cache)
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *tests],
        cwd=copy, env=env, capture_output=True, text=True, check=False,
    )
    return done.returncode, done.stdout + done.stderr


def imported_from(copy: Path, module: str, cache: Path) -> str:
    """The file `module` resolves to when imported from the copy."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONPYCACHEPREFIX"] = str(cache)
    done = subprocess.run(
        [sys.executable, "-c", f"import {module} as m; print(m.__file__)"],
        cwd=copy, env=env, capture_output=True, text=True, check=True,
    )
    return done.stdout.strip()


def failed_ids(output: str) -> list[str]:
    return [ln.split(" ", 1)[1].split(" - ")[0] for ln in output.splitlines()
            if ln.startswith(("FAILED ", "ERROR "))]


def module_of(path: str) -> str:
    return path.removesuffix(".py").replace("/", ".")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--step", required=True, choices=sorted(ROWS))
    ap.add_argument("--scratch", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args(argv)

    scratch: Path = args.scratch.resolve()
    if scratch == REPO or REPO in scratch.parents:
        raise SystemExit(f"scratch {scratch} is inside the repo")
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    rows = ROWS[args.step]
    files = repo_files()
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()

    exe = Path(sys.executable)
    shown = exe.relative_to(REPO) if REPO in exe.parents else exe.name
    lines = [f"mutation rows, step {args.step}, HEAD {head}, python {shown}", ""]
    ok = True

    control = scratch / "control"
    copy_repo(control, files)
    all_tests = tuple(sorted({t for r in rows for t in r.tests}))
    rc, out = run_tests(control, all_tests, scratch / "cache-control")
    control_green = rc == 0
    ok &= control_green
    lines.append(f"control: rc={rc} {'GREEN' if control_green else 'NOT GREEN'}"
                 f" ({out.strip().splitlines()[-1] if out.strip() else 'no output'})")
    lines.append("")
    lines.append("| row | defect | landed | imports from copy | rc | verdict | failing tests |")
    lines.append("|---|---|---|---|---|---|---|")

    for row in rows:
        copy = scratch / row.id
        shutil.copytree(control, copy)
        target = copy / row.path
        text = target.read_text(encoding="utf-8")
        count = text.count(row.old)
        landed = False
        if count == row.times:
            target.write_text(text.replace(row.old, row.new), encoding="utf-8")
            after = target.read_text(encoding="utf-8")
            landed = after != text and after == text.replace(row.old, row.new)
        cache = scratch / f"cache-{row.id}"
        where = imported_from(copy, module_of(row.path), cache) if landed else ""
        from_copy = where.startswith(str(copy))
        rc, out = run_tests(copy, row.tests, cache) if landed and from_copy else (-1, "")
        red = landed and from_copy and rc != 0
        ok &= red
        fails = failed_ids(out)
        verdict = "RED" if red else ("NOT LANDED" if not landed else
                                     ("WRONG IMPORT" if not from_copy else "GREEN (survived)"))
        lines.append(
            f"| {row.id} | {row.what} | {'yes' if landed else f'no (count {count})'} |"
            f" {'yes' if from_copy else where or 'n/a'} | {rc} | {verdict} |"
            f" {len(fails)}: {', '.join(fails[:3])} |"
        )

    lines.append("")
    lines.append(f"result: {'ALL RED, control GREEN' if ok else 'FAIL'}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

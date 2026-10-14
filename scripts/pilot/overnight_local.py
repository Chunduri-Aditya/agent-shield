"""Overnight local runs for paper v1.2: step 5 rows of record, then an engineering smoke.

Run from the frozen pilot worktree, in a terminal with no Claude session and the heavy apps
closed (the 18 GiB memory rule):

    cd ../agent-shield-pilot && CONFIRM_HIGH_RISK=1 .venv/bin/python \
        scripts/pilot/overnight_local.py --data ../agent-shield-pilot-data

Phase 1, V1_2_PLAN step 5 (rows of record). Llama 3.1 8B q4_K_M through the `ollama/`
provider, temperature 0 and seed 0, `--log-model-api`, on the anchored design (20) and the
10 prompt set. Before the runs it records the Ollama version, the model digest and template,
and whether two identical requests give identical bytes (O17); a free mock run of each design
comes first. Each log must pass `gates.py post --local --expect-temperature 0 --expect-seed 0`.
Any failure writes BLOCKED.md with the cause and stops the whole night (pilot rule R2).

Phase 2, engineering smoke (never reported, like D29). One sample (TL-01-u01) per local chat
model that fits in memory: did the model emit a structured tool call, and does the scorer
read its log as valid. A failure here is recorded and the next model runs.

Before every model launch, free plus inactive plus speculative memory must cover the model
file, 1 GiB of runtime and a 3 GiB reserve; otherwise the model is skipped with the reason
printed. Nothing here prices anything, sends anything off the machine, or computes a rate:
the summary holds event counts only (R7).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evals.tools_v12 import score_log  # noqa: E402
from scripts.pilot._common import PilotError, load_setup  # noqa: E402
from scripts.pilot.gates import repo_checks  # noqa: E402

OLLAMA = "http://localhost:11434"
STEP5_MODEL = "llama3.1:8b-instruct-q4_K_M"
DESIGNS: tuple[str, ...] = ("anchored", "pilot")
SMOKE_SAMPLE = "TL-01-u01"
RESERVE_GIB = 3.0
RUNTIME_GIB = 1.0
GIB = 2**30
RUN_TIMEOUT_S = 45 * 60
SMOKE_TIMEOUT_S = 10 * 60
DETERMINISM_PROMPT = "Reply with the single word: ready."


@dataclass
class LocalModel:
    """One model from Ollama's /api/tags."""

    name: str
    digest: str
    size: int
    capabilities: list[str]


@dataclass
class RunResult:
    """One inspect run: where its log is and what the scorer and gate read from it."""

    phase: str
    model: str
    design: str
    exit_code: int | None = None
    log: str | None = None
    skipped: str | None = None
    gate_exit: int | None = None
    counts: dict[str, int] = field(default_factory=dict)
    invalid_reasons: dict[str, int] = field(default_factory=dict)


def parse_vm_stat(text: str) -> float:
    """GiB the system can hand a new process: free plus inactive plus speculative pages."""
    size = re.search(r"page size of (\d+) bytes", text)
    if size is None:
        raise PilotError("vm_stat has no page size line")
    page = int(size.group(1))

    def pages(label: str) -> int:
        match = re.search(rf"^{label}:\s+(\d+)\.", text, flags=re.MULTILINE)
        if match is None:
            raise PilotError(f"vm_stat has no {label!r} line")
        return int(match.group(1))

    total = pages("Pages free") + pages("Pages inactive") + pages("Pages speculative")
    return total * page / GIB


def ollama_env_ok(env: Mapping[str, str]) -> tuple[bool, str]:
    """OLLAMA_BASE_URL never reaches the log, so the runner refuses a non loopback value."""
    value = env.get("OLLAMA_BASE_URL")
    if not value:
        return True, "OLLAMA_BASE_URL unset (Inspect uses localhost:11434)"
    host = urlparse(value if "://" in value else f"http://{value}").hostname
    ok = host in ("localhost", "127.0.0.1")
    return ok, f"OLLAMA_BASE_URL={value} ({'loopback' if ok else 'not loopback'})"


def headroom(available_gib: float, model_bytes: int) -> tuple[bool, str]:
    """True when the model, its runtime and the reserve all fit in available memory."""
    need = model_bytes / GIB + RUNTIME_GIB + RESERVE_GIB
    verdict = "fits" if available_gib >= need else "skip: not enough memory"
    return available_gib >= need, f"{verdict} (available {available_gib:.2f} GiB, need {need:.2f})"


def smoke_models(models: list[LocalModel], exclude_digests: set[str]) -> list[LocalModel]:
    """Models that declare tool support, one per digest, smallest first."""
    seen = set(exclude_digests)
    out: list[LocalModel] = []
    for m in sorted(models, key=lambda m: (m.size, m.name)):
        if "tools" not in m.capabilities or m.digest in seen:
            continue
        seen.add(m.digest)
        out.append(m)
    return out


def eval_command(
    repo: Path, model: str, design: str, log_dir: Path, *, sample_id: str | None = None,
    mock: bool = False,
) -> list[str]:
    """The inspect command for one run; local rows always pin temperature 0 and seed 0."""
    cmd = [
        str(repo / ".venv" / "bin" / "inspect"), "eval", "evals/tools_v12.py@tools_tl01_v12",
        "-T", f"design={design}", "--log-model-api", "--log-dir", str(log_dir),
        "--display", "plain",
    ]
    if mock:
        return [*cmd, "--model", "mockllm/model", "--limit", "1"]
    cmd += ["--model", f"ollama/{model}", "--temperature", "0", "--seed", "0"]
    if sample_id is not None:
        cmd += ["--sample-id", sample_id]
    return cmd


def count_records(log: Path) -> tuple[dict[str, int], dict[str, int]]:
    """Event counts from tools_event_v1 on one log; never a rate (R7)."""
    rows = [rec for _, _, rec in score_log(log)]
    outcomes = Counter(r.outcome for r in rows)
    counts = {
        "samples": len(rows),
        "success": outcomes["success"],
        "ignored": outcomes["ignored"],
        "refused": outcomes["refused"],
        "invalid": outcomes["invalid"],
        "strict_value": sum(r.strict_value for r in rows),
        "strict_line": sum(r.strict_line for r in rows),
        "strict_full": sum(r.strict_full for r in rows),
        "any_send_message": sum(r.any_send_message for r in rows),
        "text_tool_attempt": sum(int(r.text_tool_attempt) for r in rows),
        "structured_read": sum(int(bool(r.files_read)) for r in rows),
    }
    reasons = Counter(reason for r in rows for reason in r.invalid_reasons)
    return counts, dict(sorted(reasons.items()))


# --------------------------------------------------------------------- side effects


def http_json(path: str, body: dict[str, Any] | None = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        OLLAMA + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=300) as resp:  # localhost only
        return json.loads(resp.read())


def local_models() -> list[LocalModel]:
    tags = http_json("/api/tags")["models"]
    return [
        LocalModel(t["name"], t["digest"], int(t["size"]), list(t.get("capabilities") or []))
        for t in tags
    ]


def available_gib() -> float:
    out = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True).stdout
    return parse_vm_stat(out)


def ollama_stop(model: str) -> None:
    subprocess.run(["ollama", "stop", model], capture_output=True, text=True, check=False)


def run_logged(cmd: list[str], cwd: Path, out_file: Path, timeout: int) -> int | None:
    """Run cmd in its own process group; on timeout kill the whole group, return None."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    with out_file.open("w") as fh:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT,
                                start_new_session=True)
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return None


def newest_log(log_dir: Path) -> Path | None:
    logs = sorted(log_dir.glob("*.eval"), key=lambda p: p.stat().st_mtime)
    return logs[-1] if logs else None


class Night:
    """State for one overnight run: output folder, results, and the R2 stop."""

    def __init__(self, repo: Path, data: Path, dry_run: bool) -> None:
        self.repo, self.data, self.dry_run = repo, data, dry_run
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
        self.out = data / "overnight" / stamp
        self.results: list[RunResult] = []
        self.notes: list[str] = []

    def say(self, line: str) -> None:
        print(line, flush=True)
        self.notes.append(line)

    def blocked(self, cause: str, evidence: Path | str, decision: str) -> NoReturn:
        """R2: write BLOCKED.md with the cause, the evidence and the one decision; stop."""
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "BLOCKED.md").write_text(
            f"# BLOCKED\n\nCause: {cause}\n\nEvidence: {evidence}\n\nDecision needed: {decision}\n"
        )
        self.write_summary()
        raise SystemExit(f"BLOCKED: {cause} (see {self.out / 'BLOCKED.md'})")

    def write_summary(self) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "summary.json").write_text(
            json.dumps([asdict(r) for r in self.results], indent=2) + "\n"
        )
        cols = ["samples", "success", "ignored", "refused", "invalid", "strict_value",
                "any_send_message", "text_tool_attempt", "structured_read"]
        lines = ["# Overnight local run (event counts only, no rates)", "",
                 "| phase | model | design | exit | gate | " + " | ".join(cols) + " | note |",
                 "|" + "---|" * (len(cols) + 6)]
        for r in self.results:
            vals = [str(r.counts.get(c, "")) for c in cols]
            note = r.skipped or ", ".join(f"{k} {v}" for k, v in r.invalid_reasons.items())
            lines.append(f"| {r.phase} | {r.model} | {r.design} | {r.exit_code} | {r.gate_exit}"
                         f" | " + " | ".join(vals) + f" | {note} |")
        lines += ["", "## Log", *[f"- {n}" for n in self.notes]]
        (self.out / "SUMMARY.md").write_text("\n".join(lines) + "\n")


def preflight(night: Night) -> None:
    setup = load_setup(night.data)
    failed = [c for c in repo_checks(night.repo, setup) if c.ok is False]
    if failed:
        night.blocked("repo is not the frozen setup: " + "; ".join(c.evidence for c in failed),
                      night.data / "setup.json", "rerun from the pilot worktree at setup_sha")
    env_ok, env_why = ollama_env_ok(os.environ)
    if not env_ok:
        night.blocked(env_why, "environment", "unset OLLAMA_BASE_URL or point it at loopback")
    night.say(env_why)
    if not os.environ.get("CONFIRM_HIGH_RISK"):
        night.blocked("CONFIRM_HIGH_RISK is not set", "environment",
                      "launch with CONFIRM_HIGH_RISK=1 (TL-01 is cleared in ETHICS.md)")
    gate = subprocess.run(
        [sys.executable, "scripts/risk_check.py", "--module", "tools", "--enforce",
         "--confirm-high-risk"], cwd=night.repo, capture_output=True, text=True, check=False,
    )
    if gate.returncode != 0:
        night.blocked("risk gate refused TL-01", gate.stdout[-500:], "check ETHICS.md")
    night.say(f"preflight ok: HEAD {setup['setup_sha'][:12]}, risk gate passed")


def record_model(night: Night, model: str) -> None:
    """Version, digest, template and the duplicate request check (O17) for step 5."""
    show = http_json("/api/show", {"model": model})
    tags = {m.name: m for m in local_models()}
    body = {"model": model, "messages": [{"role": "user", "content": DETERMINISM_PROMPT}],
            "temperature": 0, "seed": 0, "stream": False}
    replies = [http_json("/v1/chat/completions", body) for _ in range(2)]
    contents = [r["choices"][0]["message"]["content"] for r in replies]
    record = {
        "ollama_version": http_json("/api/version")["version"],
        "model": model,
        "digest": tags[model].digest,
        "size": tags[model].size,
        "details": show.get("details"),
        "template": show.get("template"),
        "parameters": show.get("parameters"),
        "duplicate_request_identical": contents[0] == contents[1],
        "duplicate_request_contents": contents,
    }
    path = night.out / "step5_model_record.json"
    path.write_text(json.dumps(record, indent=2) + "\n")
    night.say(f"model record: {path} (duplicate request identical: "
              f"{record['duplicate_request_identical']})")


def run_eval(night: Night, phase: str, model: str, design: str, log_dir: Path,
             timeout: int, sample_id: str | None = None) -> RunResult:
    result = RunResult(phase=phase, model=model, design=design)
    night.results.append(result)
    log_dir.mkdir(parents=True, exist_ok=True)
    cmd = eval_command(night.repo, model, design, log_dir, sample_id=sample_id)
    if night.dry_run:
        night.say("dry run: " + " ".join(cmd))
        result.skipped = "dry run"
        return result
    result.exit_code = run_logged(cmd, night.repo, log_dir / "inspect_output.txt", timeout)
    log = newest_log(log_dir)
    result.log = str(log) if log else None
    if result.exit_code != 0 or log is None:
        return result
    result.counts, result.invalid_reasons = count_records(log)
    return result


def gate_post(night: Night, log: str) -> int:
    done = subprocess.run(
        [sys.executable, "scripts/pilot/gates.py", "post", "--data", str(night.data),
         "--repo", str(night.repo), "--log", log, "--local",
         "--expect-temperature", "0", "--expect-seed", "0"],
        cwd=night.repo, capture_output=True, text=True, check=False,
    )
    Path(log).with_suffix(".gate.txt").write_text(done.stdout + done.stderr)
    return done.returncode


def phase_step5(night: Night) -> None:
    models = {m.name: m for m in local_models()}
    if STEP5_MODEL not in models:
        night.blocked(f"{STEP5_MODEL} is not pulled", "ollama /api/tags",
                      f"ollama pull {STEP5_MODEL}")
    for design in DESIGNS:
        mock_dir = night.out / "mock" / design
        mock_dir.mkdir(parents=True, exist_ok=True)
        cmd = eval_command(night.repo, STEP5_MODEL, design, mock_dir, mock=True)
        code = 0 if night.dry_run else run_logged(cmd, night.repo, mock_dir / "out.txt", 600)
        if code != 0:
            night.blocked(f"free mock run of {design} exited {code}", mock_dir / "out.txt",
                          "fix the task before any local run")
    ok, why = headroom(available_gib(), models[STEP5_MODEL].size)
    night.say(f"step 5 memory: {why}")
    if not ok:
        night.blocked("not enough memory for step 5", why,
                      "close the heavy apps and the Claude session, then rerun")
    if not night.dry_run:
        record_model(night, STEP5_MODEL)
    for design in DESIGNS:
        log_dir = night.data / "llama-3.1-8b-q4" / "step5" / design / night.out.name
        result = run_eval(night, "step5", STEP5_MODEL, design, log_dir, RUN_TIMEOUT_S)
        if night.dry_run:
            continue
        if result.exit_code != 0 or result.log is None:
            night.blocked(f"step 5 {design} run exited {result.exit_code}",
                          log_dir / "inspect_output.txt", "read the output; no rerun")
        result.gate_exit = gate_post(night, result.log)
        if result.gate_exit != 0:
            night.blocked(f"step 5 {design} post gate failed", f"{result.log} (.gate.txt)",
                          "read the gate table; no rerun with changed parameters")
        night.say(f"step 5 {design}: {result.counts}")
    ollama_stop(STEP5_MODEL)


def phase_smoke(night: Night) -> None:
    models = local_models()
    step5 = {m.digest for m in models if m.name == STEP5_MODEL}
    queue = smoke_models(models, step5)
    night.say(f"smoke queue ({len(queue)}): " + ", ".join(m.name for m in queue))
    for m in queue:
        ok, why = headroom(available_gib(), m.size)
        if not ok:
            night.results.append(RunResult("smoke", m.name, "pilot", skipped=why))
            night.say(f"{m.name}: {why}")
            continue
        log_dir = night.data / "engineering_smoke" / m.name.replace(":", "_") / night.out.name
        result = run_eval(night, "smoke", m.name, "pilot", log_dir, SMOKE_TIMEOUT_S,
                          sample_id=SMOKE_SAMPLE)
        ollama_stop(m.name)
        night.say(f"{m.name}: exit {result.exit_code} {result.counts or result.skipped or ''}")
        night.write_summary()
        time.sleep(5)  # let Ollama release the model before the next memory reading


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else None)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--phase", choices=["all", "step5", "smoke"], default="all")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, run no model")
    args = ap.parse_args(argv)
    night = Night(REPO, args.data.resolve(), args.dry_run)
    night.out.mkdir(parents=True, exist_ok=True)
    preflight(night)
    if args.phase in ("all", "step5"):
        phase_step5(night)
    if args.phase in ("all", "smoke"):
        phase_smoke(night)
    night.write_summary()
    night.say(f"done: {night.out / 'SUMMARY.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

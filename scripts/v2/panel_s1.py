"""The S1 panel runner (S1 plan step 3h; prereg S1; pilot rules R2 to R10).

Launched by Aditya from the frozen S1 worktree (paid runs; the risk gate is named here):

    cd ../agent-shield-v2 && CONFIRM_HIGH_RISK=1 .venv/bin/python scripts/v2/panel_s1.py \
        smoke --data ../agent-shield-pilot-data/v2_s1
    .venv/bin/python scripts/v2/allocate_s1.py --data ../agent-shield-pilot-data/v2_s1
    CONFIRM_HIGH_RISK=1 .venv/bin/python scripts/v2/panel_s1.py main --data ...
    .venv/bin/python scripts/v2/panel_s1.py summary --data ...

`smoke` runs every planned (cell, model) on a few samples: 3 tasks x both arms for each
main model, 3 poisoned contrast tasks for each thinking contrast cell. `main` runs the
preregistered grid: per main model a poisoned run (80 tasks x 3 epochs) and a clean run
(80 x 1); per contrast cell 50 tasks x 3 epochs. Retiring models run first.

Every job is: S1 pre gate, `inspect eval`, S1 post gate, `cost.py` into the ledger,
`describe.py --by-arm`. Any non zero step writes BLOCKED.md with the cause and the one
decision needed, and stops the whole run; nothing is ever retried (R2). A job whose logs
are all in the ledger is skipped; a log that is not in the ledger blocks instead of being
relaunched. The child environment drops PYTHONPATH and every INSPECT_* variable, so no
model args, fallback or log setting can arrive from outside the command line.

Per job reports carry gates, sample counts and cost only. Outcome counts (events, declines,
utility) come from `summary`, which refuses until every main job has a priced log and a
passing post gate (prereg stopping rule: no interim look). Counts only, never a rate (R7).
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evals import tools_v2  # noqa: E402
from evals.tools_event_v2 import score_log  # noqa: E402
from scripts.pilot._common import PilotError, load_setup, read_ledger  # noqa: E402
from scripts.pilot.gates import repo_checks  # noqa: E402
from scripts.v2 import s1_panel  # noqa: E402

TASK = "evals/tools_v2.py@tools_tl01_v2"
SMOKE_TASKS = ("TL-01-v2-t001", "TL-01-v2-t002", "TL-01-v2-t003")
SMOKE_EST = 0.05  # USD per sample for the smoke pre gate; the setup's smoke cap still binds
MAX_CONNECTIONS = 4
MESSAGE_LIMIT = 12
TOKEN_LIMIT = 60_000
SMOKE_TIMEOUT_S = 30 * 60
MAIN_TIMEOUT_S = 4 * 60 * 60
STEP_TIMEOUT_S = 10 * 60
COST_LIMIT_FACTOR = 3.0

Execute = Callable[[list[str], Path, Path, dict[str, str], int], "int | None"]


@dataclass(frozen=True)
class Job:
    """One `inspect eval` invocation of the S1 task."""

    cell: str
    model: str
    phase: str  # smoke | main
    arm: str  # both | poisoned | clean
    subset: str  # all | contrast50
    epochs: int
    samples: int  # sample rows this job produces, for the pre gate
    sample_ids: tuple[str, ...] | None

    @property
    def rel_dir(self) -> Path:
        base = Path(self.cell) / self.model / self.phase
        return base / self.arm if self.phase == "main" else base


def job_dir(data: Path, job: Job) -> Path:
    return data / job.rel_dir


def _contrast_smoke_ids() -> tuple[str, ...]:
    return tuple(str(s.id) for s in tools_v2.dataset_for("poisoned", subset="contrast50")[:3])


def plan_jobs(phase: str) -> list[Job]:
    """Every job of one phase, retiring models first, then the thinking contrast cells."""
    jobs: list[Job] = []
    for model in s1_panel.PANEL:
        if phase == "smoke":
            ids = tuple(f"{t}:{a}" for t in SMOKE_TASKS for a in ("P", "C"))
            jobs.append(Job("main", model, phase, "both", "all", 1, len(ids), ids))
        elif phase == "main":
            jobs.append(Job("main", model, phase, "poisoned", "all", 3, 80 * 3, None))
            jobs.append(Job("main", model, phase, "clean", "all", 1, 80 * 1, None))
        else:
            raise ValueError(f"unknown phase {phase!r}")
    for name, cell in s1_panel.CONTRAST_CELLS.items():
        if phase == "smoke":
            ids = _contrast_smoke_ids()
            jobs.append(Job(name, cell.model, phase, "poisoned", "contrast50", 1, len(ids), ids))
        else:
            jobs.append(Job(name, cell.model, phase, "poisoned", "contrast50", 3, 50 * 3, None))
    return jobs


def model_config(job: Job) -> Path | None:
    """The pinned model args file for this job, or None when the policy pins none."""
    if job.cell != "main":
        return s1_panel.MODEL_ARGS_DIR / "cells" / f"{job.cell}.yaml"
    if not s1_panel.model_args(job.model):
        return None
    return s1_panel.MODEL_ARGS_DIR / f"{job.model}.yaml"


def eval_command(job: Job, repo: Path, cost_limit: float, data: Path | None = None) -> list[str]:
    """The exact `inspect eval` command for one job (no sampling, fallback or batch flags)."""
    inspect_bin = Path(sys.executable).with_name("inspect")
    cmd = [str(inspect_bin), "eval", TASK, "-T", f"arm={job.arm}", "-T", f"subset={job.subset}",
           "--model", f"anthropic/{job.model}", "--epochs", str(job.epochs),
           "--max-connections", str(MAX_CONNECTIONS), "--message-limit", str(MESSAGE_LIMIT),
           "--token-limit", str(TOKEN_LIMIT), "--cost-limit", f"{cost_limit:.6g}",
           "--model-cost-config", str(s1_panel.INSPECT_COSTS), "--log-model-api",
           "--log-dir", str((data or Path(".")) / job.rel_dir), "--display", "plain"]
    if job.sample_ids:
        cmd += ["--sample-id", ",".join(job.sample_ids)]
    config = model_config(job)
    if config is not None:
        cmd += ["--model-config", str(config)]
    return cmd


def child_env(environ: Mapping[str, str]) -> dict[str, str]:
    """The parent environment minus PYTHONPATH and every INSPECT_* override."""
    env = {k: v for k, v in environ.items() if k != "PYTHONPATH" and not k.startswith("INSPECT_")}
    env["CONFIRM_HIGH_RISK"] = "1"
    return env


def default_execute(cmd: list[str], cwd: Path, out_file: Path, env: dict[str, str],
                    timeout: int) -> int | None:
    """Run cmd in its own process group; on timeout kill the group and return None."""
    with out_file.open("w") as fh:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=fh, stderr=subprocess.STDOUT,
                                start_new_session=True)
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return None


def repo_ok(repo: Path, setup: dict[str, Any]) -> tuple[bool, str]:
    failed = [c for c in repo_checks(repo, setup) if c.ok is False]
    return not failed, "; ".join(c.evidence for c in failed) or "repo at setup_sha, clean"


def newest_log(log_dir: Path) -> Path | None:
    logs = sorted(log_dir.glob("*.eval"), key=lambda p: p.stat().st_mtime)
    return logs[-1] if logs else None


class Runner:
    """One invocation: its output folder, its rows, and the R2 stop."""

    def __init__(self, repo: Path, data: Path, execute: Execute = default_execute) -> None:
        self.repo, self.data, self.execute = Path(repo).resolve(), Path(data).resolve(), execute
        self.out = self.data / "runs" / datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S-%fZ")
        self.rows: list[dict[str, Any]] = []
        self.notes: list[str] = []

    def say(self, line: str) -> None:
        print(line, flush=True)
        self.notes.append(line)

    def blocked(self, cause: str, evidence: Path | str, decision: str) -> NoReturn:
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "BLOCKED.md").write_text(
            f"# BLOCKED\n\nCause: {cause}\n\nEvidence: {evidence}\n\nDecision needed: {decision}\n")
        self.write_summary()
        raise SystemExit(f"BLOCKED: {cause} (see {self.out / 'BLOCKED.md'})")

    def write_summary(self) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        lines = ["# S1 run (gates, samples and cost only; outcomes come from `summary`)", "",
                 "| phase | cell | model | arm | samples | status | log |",
                 "|---|---|---|---|---|---|---|"]
        lines += [f"| {r['phase']} | {r['cell']} | {r['model']} | {r['arm']} | {r['samples']} |"
                  f" {r['status']} | {r.get('log', '')} |" for r in self.rows]
        lines += ["", "## Log", *[f"- {n}" for n in self.notes]]
        (self.out / "SUMMARY.md").write_text("\n".join(lines) + "\n")

    def _run(self, cmd: list[str], out_file: Path, timeout: int = STEP_TIMEOUT_S) -> int | None:
        return self.execute(cmd, self.repo, out_file, child_env(os.environ), timeout)

    def _py(self, script: str, *args: str) -> list[str]:
        return [sys.executable, str(self.repo / script), *args]

    def preflight(self) -> None:
        try:
            setup = load_setup(self.data)
        except PilotError as exc:
            self.blocked(str(exc), self.data,
                         "write the S1 setup record (setup_record.py --study s1)")
        for var in ("CONFIRM_HIGH_RISK", "ANTHROPIC_API_KEY"):
            if not os.environ.get(var):
                self.blocked(f"{var} is not set", "environment", f"launch with {var} set")
        if self.data == self.repo or self.repo in self.data.parents:
            self.blocked("the data dir is inside the repo", self.data, "use a data dir beside it")
        ok, why = repo_ok(self.repo, setup)
        if not ok:
            self.blocked(f"repo is not the frozen setup: {why}", self.data / "setup.json",
                         "run from the S1 worktree at setup_sha with a clean tree")
        self.out.mkdir(parents=True, exist_ok=True)
        risk = self._run(self._py("scripts/risk_check.py", "--module", "tools", "--enforce",
                                  "--confirm-high-risk"), self.out / "risk_check.txt")
        if risk != 0:
            self.blocked("risk gate refused TL-01", self.out / "risk_check.txt", "check ETHICS.md")
        self.say(f"preflight ok: HEAD {setup['setup_sha'][:12]}, risk gate passed")

    def _priced(self, log: Path) -> bool:
        return any(row.get("log_path") == str(log.resolve()) for row in read_ledger(self.data))

    def run_job(self, job: Job, est: float) -> None:
        d = job_dir(self.data, job)
        row: dict[str, Any] = {"phase": job.phase, "cell": job.cell, "model": job.model,
                               "arm": job.arm, "samples": job.samples, "status": "started"}
        self.rows.append(row)
        logs = sorted(d.glob("*.eval")) if d.exists() else []
        if logs:
            if all(self._priced(log) for log in logs):
                row["status"] = "skipped: already priced"
                self.say(f"skip {job.rel_dir}: every log is in the ledger")
                return
            self.blocked(f"{d} holds a log that is not in the ledger", d,
                         "read that log; price it with cost.py or move it aside, then rerun")
        d.mkdir(parents=True, exist_ok=True)
        args = ["pre", "--data", str(self.data), "--repo", str(self.repo), "--model", job.model,
                "--phase", job.phase, "--cell", job.cell, "--samples", str(job.samples),
                "--est-per-sample", str(est)]
        if self._run(self._py("scripts/v2/gates_s1.py", *args), d / "pre.txt") != 0:
            self.blocked(f"pre gate failed for {job.rel_dir}", d / "pre.txt",
                         "read the failed checks; a cap change needs a dated amendment")
        timeout = SMOKE_TIMEOUT_S if job.phase == "smoke" else MAIN_TIMEOUT_S
        code = self._run(eval_command(job, self.repo, COST_LIMIT_FACTOR * est, self.data),
                         d / "inspect_output.txt", timeout)
        log = newest_log(d)
        if code != 0 or log is None:
            self.blocked(f"inspect eval exited {code} for {job.rel_dir}", d / "inspect_output.txt",
                         "read the output; nothing is retried automatically")
        row["log"] = str(log)
        post = ["post", "--data", str(self.data), "--repo", str(self.repo), "--log", str(log),
                "--cell", job.cell]
        if self._run(self._py("scripts/v2/gates_s1.py", *post), d / "post.txt") != 0:
            self.blocked(f"post gate failed for {job.rel_dir}", d / "post.txt",
                         "read the failed checks before any rerun")
        cost = ["--data", str(self.data), "--prices", str(s1_panel.PRICES), "--phase",
                f"s1-{job.phase}-{job.cell}", str(log)]
        if self._run(self._py("scripts/pilot/cost.py", *cost), d / "cost.txt") != 0:
            self.blocked(f"cost.py failed for {job.rel_dir}", d / "cost.txt",
                         "price the log by hand")
        describe = ["--data", str(self.data), "--log", str(log), "--by-arm"]
        if self._run(self._py("scripts/pilot/describe.py", *describe), d / "describe.txt") != 0:
            self.blocked(f"describe.py failed for {job.rel_dir}", d / "describe.txt", "read it")
        row["status"] = "done"
        self.say(f"done {job.rel_dir}: gates pass, priced")

    def smoke(self) -> None:
        self.preflight()
        for job in plan_jobs("smoke"):
            self.run_job(job, SMOKE_EST)
        self.write_summary()
        self.say("smoke done; next: scripts/v2/allocate_s1.py --data <data>, then Aditya's go")

    def main(self) -> None:
        self.preflight()
        path = self.data / "allocation.json"
        if not path.exists():
            self.blocked("allocation.json is missing", path, "run allocate_s1.py after the smoke")
        allocation = json.loads(path.read_text())
        for job in plan_jobs("main"):
            row = allocation.get(job.cell, {}).get(job.model)
            if not isinstance(row, dict) or "max_cost_per_sample" not in row:
                self.blocked(f"no allocation row for {job.cell} {job.model}", path,
                             "rerun the smoke for that model, then a dated allocation amendment")
            self.run_job(job, float(row["max_cost_per_sample"]))
        self.write_summary()
        self.say("main done; next: panel_s1.py summary")

    def summary(self) -> None:
        """Outcome counts per job, only once every main job passed and was priced."""
        rows = []
        for job in plan_jobs("main"):
            d = job_dir(self.data, job)
            log = newest_log(d) if d.exists() else None
            post = d / "post.txt"
            if log is None or not self._priced(log) or not post.exists() or (
                    "gate s1 post: PASS" not in post.read_text()):
                self.blocked(f"{job.rel_dir} has no priced log with a passing post gate", d,
                             "finish the main runs before reading any outcome")
            counts: Counter[str] = Counter()
            for _sid, _epoch, rec in score_log(log):
                counts["samples"] += 1
                counts[rec.outcome] += 1
                counts["strict_nonce"] += rec.strict_nonce
                counts["strict_value"] += rec.strict_value
                counts["utility"] += rec.utility
                counts["late_decline"] += int(rec.late_decline)
            rows.append((job, counts))
        cols = ["samples", "declined", "invalid", "success", "partial", "ignored", "strict_nonce",
                "strict_value", "utility", "late_decline"]
        lines = ["# S1 outcome counts (events from tools_event_v2; counts only, no rates)", "",
                 "| cell | model | arm | " + " | ".join(cols) + " |",
                 "|" + "---|" * (len(cols) + 3)]
        lines += [f"| {j.cell} | {j.model} | {j.arm} | "
                  + " | ".join(str(c.get(k, 0)) for k in cols) + " |" for j, c in rows]
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "S1_COUNTS.md").write_text("\n".join(lines) + "\n")
        self.say(f"wrote {self.out / 'S1_COUNTS.md'}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S1 panel runner")
    parser.add_argument("phase", choices=("smoke", "main", "summary"))
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=REPO)
    args = parser.parse_args(argv)
    runner = Runner(args.repo, args.data)
    getattr(runner, args.phase)()
    return 0


if __name__ == "__main__":
    sys.exit(main())

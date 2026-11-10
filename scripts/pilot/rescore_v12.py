"""Rescore the May 2026 inputs and psych logs with the marker ASR scorer in two trees.

v1.2 agent plan P7 (agent-shield-pilot-data/v12/V12_AGENT_PLAN.md, Revision 2 F2 and F9
override the P7 section). D58 makes the v5 marker scorer the scorer of record and keeps a v2
comparability column, so every log in P6's inventory.json is scored twice:

* "frozen": the pilot worktree (REPO.parent / "agent-shield-pilot", detached at f97b963)
  with its own .venv; every sample must be stamped scorer_version 2. Output: DIR/v2/<name>.
* "main": this repo at HEAD with its own .venv; every sample must be stamped 5.
  Output: DIR/v5/<name>.

Each run is the real `inspect score` in a child process. No model is ever called; a model
call would be a bug, which is why the child holds only sentinel keys. Every command passes
`--model mockllm/model`: without it `inspect score` builds the provider named in the log
header (ollama, anthropic, google, groq and openai in the May logs). The scored samples
keep their header model, because TaskState.model_name still comes from the header.

Guards, all before any child starts unless stated, each one exits 1:
1. DIR must resolve outside REPO and every tree root, and carry no "v2_s1" component.
2. Each source log's sha256 must equal its inventory sha256; nothing is copied otherwise.
3. The task comes from the source log header (eval.task, eval.task_file), never the file
   name. Only inputs/psych asr/transparency tasks, with or without _defended, map. The
   asr logs use `--action overwrite`; the transparency logs use `--action append` so they
   keep their TR score (F9). A log with zero samples is refused. A transparency log whose
   samples already hold an asr_scorer (or asr_scorer-N) score is refused, because the
   append would write the new score as asr_scorer-1. Errored samples are counted and
   reported in the run line and the check line; they are still scored.
4. Every output for the tree must be absent; nothing is ever overwritten.
5. A tree with a pinned commit (frozen: f97b963) must sit at that commit.
6. The tree must be clean (git status --porcelain, whole tree or its clean scope) before
   the run and after every child.
7. A preflight child imports evals/inputs.py from the tree and must see evals._marker
   inside that tree at the expected MARKER_SCORER_VERSION.
After each score child: exit code 0, no auth error in its output, the copied original
unchanged, the output present, every sample stamped with the tree version, overwrite
outputs holding only asr_scorer, and append outputs keeping every original score name.
Child output is never printed, because it can quote a completion. A failure prints the
child's output line count and the exception class names found in it, nothing else.
Each child runs in its own session; a timeout kills its whole process group.

Child environment (F2): PYTHONPATH dropped, VSCODE_* and TERM_PROGRAM* dropped (Inspect
loads .env with override=True inside VS Code), INSPECT_* dropped (`inspect score` reads
INSPECT_SCORE_MODEL and its siblings; a tree .env naming one is refused, because dotenv
would fill it back in), PYTHONDONTWRITEBYTECODE=1. Every name declared in a .env in the
tree or its parents is set to SENTINEL whatever its suffix, since nothing in a tree .env
is needed once the model is mockllm. Secret names from the parent environment are set to
SENTINEL too, rather than unset. Unset is unsafe: the Anthropic SDK then discovers another
credential, and python-dotenv fills any name the environment does not hold.

Usage:
    uv run python scripts/pilot/rescore_v12.py --step3 DIR --tree frozen
    uv run python scripts/pilot/rescore_v12.py --step3 DIR --tree main
    uv run python scripts/pilot/rescore_v12.py --step3 DIR --dry-run
    uv run python scripts/pilot/rescore_v12.py --check DIR

--dry-run prints the 2N commands and writes nothing. --check verifies both outputs per log
and writes DIR/rescore_check.txt, ending in "result: PASS" or "result: FAIL".
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from inspect_ai.log import EvalLog, read_eval_log  # noqa: E402

from scripts.pilot._common import sha256_file  # noqa: E402

PILOT = REPO.parent / "agent-shield-pilot"
SENTINEL = "agent-shield-rescore-sentinel-not-a-key"

SECRET_SUFFIXES = (
    "_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD", "_KEY_ID", "_ACCESS_KEY", "_CREDENTIALS",
    "_KEY",
)
PROVIDER_KEYS = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY", "GOOGLE_API_KEY",
    "GEMINI_API_KEY", "GROQ_API_KEY", "GROK_API_KEY", "XAI_API_KEY", "OPENROUTER_API_KEY",
    "MISTRAL_API_KEY", "TOGETHER_API_KEY", "CEREBRAS_API_KEY", "HF_TOKEN",
)
STRIP_PREFIXES = ("VSCODE_", "TERM_PROGRAM", "INSPECT_")

_DOTENV_NAME = re.compile(r"""^\s*(?:export\s+)?["']?([A-Za-z_][A-Za-z0-9_]*)["']?\s*=""")
_EXCEPTION_NAME = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:Error|Exception)\b")
_TASK = re.compile(r"^(inputs|psych)_(asr|transparency)(_defended)?$")
AUTH_ERROR = re.compile(
    r"authentication|unauthori[sz]ed|permission[ _]?denied|forbidden"
    r"|invalid[ _-]?(x-)?api[ _-]?key|incorrect api key"
    # A bare 401 or 403 is not enough: metric values and temp paths carry them.
    r"|error code:?\s*40[13]\b|status(?:[ _]?code)?[=:\s]+40[13]\b",
    re.IGNORECASE,
)

SCORER_NAME = "asr_scorer"
MOCK_MODEL = "mockllm/model"
PROBE_TIMEOUT = 300
SCORE_TIMEOUT = 1800
GIT_TIMEOUT = 120
TAIL_LINES = 8

PROBE = (
    "import importlib.util, json, sys\n"
    "spec = importlib.util.spec_from_file_location("
    "'_rescore_probe_inputs', 'evals/inputs.py')\n"
    "assert spec is not None and spec.loader is not None\n"
    "module = importlib.util.module_from_spec(spec)\n"
    "sys.modules[spec.name] = module\n"
    "spec.loader.exec_module(module)\n"
    "marker = sys.modules['evals._marker']\n"
    "print(json.dumps({'file': marker.__file__, 'version': marker.MARKER_SCORER_VERSION}))\n"
)


@dataclass(frozen=True)
class Tree:
    """One scorer tree: where it lives, its interpreter, and the stamp it must produce.

    clean_scope None means the whole tree must be clean; a path limits the check to it.
    expect_commit, when set, is the commit HEAD must equal before a run.
    """

    name: str
    root: Path
    python: Path
    expect_version: int
    out_dir: str
    clean_scope: str | None
    expect_commit: str | None = None


TREES: dict[str, Tree] = {
    "frozen": Tree("frozen", PILOT, PILOT / ".venv/bin/python", 2, "v2", None,
                   "f97b963af3742c6441492779da256769fb8e4509"),
    "main": Tree("main", REPO, REPO / ".venv/bin/python", 5, "v5", "evals"),
}


@dataclass(frozen=True)
class Job:
    """One inventory log mapped to its scorer and score action."""

    source: Path
    name: str
    sha256: str
    task: str
    scorer: str
    action: str
    errored: int


class RescoreError(Exception):
    """A guard failed. main prints the one line message, any child summary, and exits 1."""

    def __init__(self, message: str, tail: list[str] | None = None) -> None:
        super().__init__(message)
        self.tail = tail or []


def dotenv_names(tree_root: Path) -> set[str]:
    """Names declared in every .env in tree_root and its parents. Values are never kept."""
    names: set[str] = set()
    root = tree_root.resolve()
    for directory in (root, *root.parents):
        dotenv = directory / ".env"
        if not dotenv.is_file():
            continue
        with dotenv.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                match = _DOTENV_NAME.match(line)
                if match:
                    names.add(match.group(1))
    return names


def child_env(tree_root: Path) -> dict[str, str]:
    """The environment for a child in tree_root: sentinel secrets, no VS Code markers (F2).

    Every .env name gets SENTINEL whatever its suffix; parent names get it by suffix.
    os.environ is never changed.
    """
    env = dict(os.environ)
    names = {n for n in os.environ if n.endswith(SECRET_SUFFIXES)} | dotenv_names(tree_root)
    for name in names | set(PROVIDER_KEYS):
        env[name] = SENTINEL
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in list(env):
        if name.startswith(STRIP_PREFIXES):
            del env[name]
    return env


def check_out_root(step3: Path) -> Path:
    """Guard 1: DIR outside REPO and every tree root, and no "v2_s1" path component."""
    resolved = step3.resolve()
    if "v2_s1" in step3.parts or "v2_s1" in resolved.parts:
        raise RescoreError(f"{step3}: output root is under a v2_s1 directory")
    roots = [("repo", REPO), *((f"tree {t.name}", t.root) for t in TREES.values())]
    for label, root in roots:
        if resolved.is_relative_to(root.resolve()):
            raise RescoreError(f"{step3}: output root is inside the {label} {root}")
    return resolved


def load_inventory(step3: Path) -> list[dict[str, Any]]:
    """Read DIR/inventory.json and return its logs rows; each needs a path and a sha256."""
    path = step3 / "inventory.json"
    if not path.is_file():
        raise RescoreError(f"{path}: missing")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RescoreError(f"{path}: not JSON ({exc.msg})") from exc
    rows = data.get("logs") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise RescoreError(f"{path}: no logs rows")
    for i, row in enumerate(rows):
        if not (isinstance(row, dict) and isinstance(row.get("path"), str)
                and isinstance(row.get("sha256"), str)):
            raise RescoreError(f"{path}: logs[{i}] lacks a path or a sha256")
    return rows


def _source(row: dict[str, Any]) -> Path:
    path = Path(row["path"])
    return path if path.is_absolute() else REPO / path


def _read(path: Path, *, header_only: bool = False) -> EvalLog:
    try:
        return read_eval_log(str(path), header_only=header_only)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise RescoreError(f"{path.name}: unreadable log ({type(exc).__name__})") from exc


def _is_asr_name(name: str) -> bool:
    return name == SCORER_NAME or name.startswith(f"{SCORER_NAME}-")


def plan_jobs(step3: Path) -> list[Job]:
    """Guards 2 and 3 for every inventory row, before anything is copied or run.

    Each source log is read in full once: its header maps the task, and its samples are
    checked (at least one, no prior asr score on an append) and their errors counted.
    """
    jobs: list[Job] = []
    seen: set[str] = set()
    for row in load_inventory(step3):
        source = _source(row)
        if not source.is_file():
            raise RescoreError(f"{source}: source log missing")
        if source.name in seen:
            raise RescoreError(f"{source.name}: two inventory rows share this file name")
        seen.add(source.name)
        if sha256_file(source) != row["sha256"]:
            raise RescoreError(f"{source.name}: sha256 differs from the inventory")
        log = _read(source)
        task = log.eval.task
        match = _TASK.match(task)
        if match is None:
            raise RescoreError(f"{source.name}: task {task!r} has no rescore mapping")
        module, kind = match.group(1), match.group(2)
        task_file = f"evals/{module}.py"
        if log.eval.task_file != task_file:
            raise RescoreError(
                f"{source.name}: task_file {log.eval.task_file!r} is not {task_file!r}"
            )
        samples = log.samples or []
        if not samples:
            raise RescoreError(f"{source.name}: log holds no samples")
        action = "overwrite" if kind == "asr" else "append"
        if action == "append":
            prior = sum(1 for s in samples if any(map(_is_asr_name, s.scores or {})))
            if prior:
                raise RescoreError(f"{source.name}: {prior} samples already hold an"
                                   f" {SCORER_NAME} score; append would write {SCORER_NAME}-1")
        jobs.append(Job(
            source=source,
            name=source.name,
            sha256=row["sha256"],
            task=task,
            scorer=f"{task_file}@{SCORER_NAME}",
            action=action,
            errored=sum(1 for s in samples if s.error is not None),
        ))
    return jobs


def score_command(tree: Tree, job: Job, original: Path, output: Path) -> list[str]:
    """The `inspect score` command for one log in one tree.

    `--model mockllm/model` stops Inspect from building the provider in the log header.
    """
    return [
        str(tree.python), "-m", "inspect_ai", "score", str(original),
        "--scorer", job.scorer, "--model", MOCK_MODEL, "--action", job.action,
        "--output-file", str(output), "--display", "none", "--log-level", "warning",
    ]


def _require_flags(cmd: list[str]) -> None:
    """F9: every command names its action and its output file explicitly."""
    if "--action" not in cmd or "--output-file" not in cmd:
        raise RescoreError("a score command lacks --action or --output-file")


def _tree(name: str) -> Tree:
    if name not in TREES:
        raise RescoreError(f"tree {name!r} is not configured")
    return TREES[name]


def require_clean(tree: Tree, when: str) -> None:
    """Guard 6: git status --porcelain is empty for the tree or its clean scope."""
    cmd = ["git", "-C", str(tree.root), "status", "--porcelain"]
    if tree.clean_scope is not None:
        cmd += ["--", tree.clean_scope]
    done = subprocess.run(cmd, capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False)
    if done.returncode != 0:
        raise RescoreError(f"{tree.name}: git status failed {when} (rc {done.returncode})")
    if done.stdout.strip():
        count = len(done.stdout.splitlines())
        scope = tree.clean_scope or "whole tree"
        raise RescoreError(f"{tree.name}: tree dirty {when} ({count} paths, scope {scope})")


def require_commit(tree: Tree) -> None:
    """Guard 5: a tree with expect_commit set must have HEAD at that commit."""
    if tree.expect_commit is None:
        return
    done = subprocess.run(["git", "-C", str(tree.root), "rev-parse", "HEAD"],
                          capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False)
    if done.returncode != 0:
        raise RescoreError(f"{tree.name}: git rev-parse HEAD failed (rc {done.returncode})")
    head = done.stdout.strip()
    if head != tree.expect_commit:
        raise RescoreError(f"{tree.name}: HEAD {head[:12]} is not the pinned commit"
                           f" {tree.expect_commit[:12]}")


def _tail(text: str) -> list[str]:
    return [ln for ln in text.splitlines() if ln.strip()][-TAIL_LINES:]


def _summary(text: str) -> list[str]:
    """What a failure may print about child output: a line count and exception names only."""
    names = sorted(set(_EXCEPTION_NAME.findall(text)))[:5]
    return [f"child output: {len(text.splitlines())} lines,"
            f" exception names: {', '.join(names) or 'none'}"]


def _run_child(cmd: list[str], tree: Tree, timeout: int, what: str) -> tuple[int, str, str]:
    """Run one child in its own session; a timeout kills its whole process group."""
    proc = subprocess.Popen(
        cmd, cwd=tree.root, env=child_env(tree.root), stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise RescoreError(f"{tree.name}: {what} timed out after {timeout}s") from exc
    return proc.returncode, out, err


def preflight(tree: Tree) -> None:
    """Guard 7: the tree's evals._marker is inside the tree at the expected version."""
    if not tree.python.is_file():
        raise RescoreError(f"{tree.name}: interpreter {tree.python} missing")
    inspect_names = sorted(n for n in dotenv_names(tree.root) if n.startswith("INSPECT_"))
    if inspect_names:
        raise RescoreError(f"{tree.name}: a .env sets {', '.join(inspect_names)}, which"
                           " dotenv would hand to inspect score")
    rc, out, err = _run_child([str(tree.python), "-c", PROBE], tree, PROBE_TIMEOUT, "preflight")
    if rc != 0:
        raise RescoreError(f"{tree.name}: preflight rc {rc}", _summary(out + "\n" + err))
    lines = _tail(out)
    try:
        seen = json.loads(lines[-1]) if lines else None
    except json.JSONDecodeError:
        seen = None
    if not isinstance(seen, dict) or "file" not in seen or "version" not in seen:
        raise RescoreError(f"{tree.name}: preflight printed no marker record")
    marker = Path(str(seen["file"]))
    if not marker.is_absolute():
        marker = tree.root / marker
    if not marker.resolve().is_relative_to(tree.root.resolve()):
        raise RescoreError(f"{tree.name}: evals._marker loaded from outside the tree: {marker}")
    if seen["version"] != tree.expect_version:
        raise RescoreError(f"{tree.name}: MARKER_SCORER_VERSION {seen['version']!r},"
                           f" want {tree.expect_version}")
    print(f"{tree.name}: preflight OK (marker {marker}, version {tree.expect_version})")


def copy_original(step3: Path, job: Job) -> Path:
    """Copy the source to DIR/original/<name> once; an existing copy must match the sha."""
    original = step3 / "original" / job.name
    if original.exists():
        if sha256_file(original) != job.sha256:
            raise RescoreError(f"{original}: existing copy differs from the inventory sha256")
        return original
    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(job.source, original)
    if sha256_file(original) != job.sha256:
        raise RescoreError(f"{original}: copy sha256 differs from the inventory")
    return original


def _sample_key(sample: Any) -> tuple[str, int]:
    return (str(sample.id), int(sample.epoch))


def _stamp(sample: Any) -> object:
    score = (sample.scores or {}).get(SCORER_NAME)
    return None if score is None else (score.metadata or {}).get("scorer_version")


def verify_output(tree: Tree, job: Job, original: Path, output: Path) -> int:
    """Stamps and score names in one scored log; returns its sample count."""
    log = _read(output)
    if not log.samples:
        raise RescoreError(f"{output.name}: scored log holds no samples")
    before = {_sample_key(s): set(s.scores or {}) for s in (_read(original).samples or [])}
    for sample in log.samples:
        key = _sample_key(sample)
        stamp = _stamp(sample)
        if stamp != tree.expect_version:
            raise RescoreError(f"{output.name}: sample {key[0]} epoch {key[1]} stamped"
                               f" {stamp!r}, want {tree.expect_version}")
        names = set(sample.scores or {})
        if job.action == "overwrite" and names != {SCORER_NAME}:
            raise RescoreError(f"{output.name}: sample {key[0]} epoch {key[1]} holds scores"
                               f" {sorted(names)}, want only {SCORER_NAME}")
        if job.action == "append":
            if key not in before:
                raise RescoreError(f"{output.name}: sample {key[0]} epoch {key[1]} is not in"
                                   " the original")
            missing = (before[key] | {SCORER_NAME}) - names
            if missing:
                raise RescoreError(f"{output.name}: sample {key[0]} epoch {key[1]} lost"
                                   f" scores {sorted(missing)}")
    return len(log.samples)


def run_tree(step3: Path, tree_name: str) -> None:
    """Score every inventory log in one tree, guards first, stopping at the first failure."""
    tree = _tree(tree_name)
    jobs = plan_jobs(step3)
    outputs = [step3 / tree.out_dir / job.name for job in jobs]
    existing = [o.name for o in outputs if o.exists()]
    if existing:
        raise RescoreError(f"{tree.name}: {len(existing)} outputs already exist in"
                           f" {tree.out_dir}/, first {existing[0]}")
    require_commit(tree)
    require_clean(tree, "before the run")
    preflight(tree)
    require_clean(tree, "after the preflight")
    (step3 / tree.out_dir).mkdir(parents=True, exist_ok=True)
    for job, output in zip(jobs, outputs, strict=True):
        original = copy_original(step3, job)
        cmd = score_command(tree, job, original, output)
        _require_flags(cmd)
        rc, out, err = _run_child(cmd, tree, SCORE_TIMEOUT, job.name)
        combined = out + "\n" + err
        if rc != 0:
            raise RescoreError(f"{tree.name}: {job.name} inspect score rc {rc}",
                               _summary(combined))
        if AUTH_ERROR.search(combined):
            raise RescoreError(f"{tree.name}: {job.name} child output shows an auth error",
                               _summary(combined))
        require_clean(tree, f"after scoring {job.name}")
        if sha256_file(original) != job.sha256:
            raise RescoreError(f"{original}: sha256 changed during scoring")
        if not output.is_file():
            raise RescoreError(f"{output}: not written", _summary(combined))
        count = verify_output(tree, job, original, output)
        print(f"{tree.name}: {job.name} {job.action} OK ({count} samples,"
              f" {job.errored} errored, stamp {tree.expect_version})")
    print(f"{tree.name}: {len(jobs)} logs scored into {step3 / tree.out_dir}")


def dry_run(step3: Path) -> None:
    """Print the 2N commands (frozen, then main) with their cwd; write nothing."""
    jobs = plan_jobs(step3)
    count = 0
    for tree_name in ("frozen", "main"):
        tree = _tree(tree_name)
        for job in jobs:
            cmd = score_command(tree, job, step3 / "original" / job.name,
                                step3 / tree.out_dir / job.name)
            _require_flags(cmd)
            print(f"{shlex.join(cmd)}  # cwd={shlex.quote(str(tree.root))}")
            count += 1
    print(f"dry run: {count} commands for {len(jobs)} logs, nothing written")


def _check_one(step3: Path, row: dict[str, Any], versions: dict[str, int],
               info: dict[str, str]) -> None:
    name = Path(row["path"]).name
    original = step3 / "original" / name
    if not original.is_file():
        raise RescoreError("original missing")
    if sha256_file(original) != row["sha256"]:
        raise RescoreError("original sha256 differs from the inventory")
    log = _read(original)
    info["task"] = log.eval.task
    keys = {_sample_key(s) for s in (log.samples or [])}
    info["samples"] = str(len(keys))
    info["errored"] = str(sum(1 for s in (log.samples or []) if s.error is not None))
    if not keys:
        raise RescoreError("original holds no samples")
    stamps: list[str] = []
    problem = ""
    for out_dir in ("v2", "v5"):
        if out_dir not in versions:
            raise RescoreError(f"no tree writes {out_dir}")
        output = step3 / out_dir / name
        if not output.is_file():
            raise RescoreError(f"{out_dir} output missing")
        samples = _read(output).samples or []
        seen = sorted({repr(_stamp(s)) for s in samples})
        stamps.append(f"{out_dir}:{'/'.join(seen) or 'none'}")
        info["stamps"] = " ".join(stamps)
        if not problem and seen != [repr(versions[out_dir])]:
            problem = f"{out_dir} stamps {seen}, want [{versions[out_dir]}]"
        if not problem and {_sample_key(s) for s in samples} != keys:
            problem = f"{out_dir} sample (id, epoch) set differs from the original"
    if problem:
        raise RescoreError(problem)


def check(step3: Path) -> bool:
    """Verify every log's original, v2 and v5 outputs; write DIR/rescore_check.txt."""
    versions = {t.out_dir: t.expect_version for t in TREES.values()}
    lines: list[str] = []
    ok = True
    try:
        rows = load_inventory(step3)
    except RescoreError as exc:
        rows = []
        ok = False
        lines.append(f"inventory FAIL {exc}")
    for row in rows:
        info = {"task": "?", "samples": "?", "errored": "?", "stamps": "?"}
        try:
            _check_one(step3, row, versions, info)
            verdict = "OK"
        except RescoreError as exc:
            ok = False
            verdict = f"FAIL {exc}"
        lines.append(f"{Path(row['path']).name} task={info['task']} samples={info['samples']}"
                     f" errored={info['errored']} stamps={info['stamps']} {verdict}")
    lines.append(f"result: {'PASS' if ok else 'FAIL'}")
    (step3 / "rescore_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return ok


def main(argv: list[str] | None = None) -> int:
    """Run one mode; 0 on success, 1 at the first failure."""
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--step3", type=Path, metavar="DIR", help="score the logs in DIR")
    mode.add_argument("--check", type=Path, metavar="DIR", help="verify DIR's outputs")
    ap.add_argument("--tree", choices=("frozen", "main"), help="the tree to score in")
    ap.add_argument("--dry-run", action="store_true", help="print the commands only")
    args = ap.parse_args(argv)
    if args.step3 is not None and (args.tree is None) == (not args.dry_run):
        ap.error("--step3 needs exactly one of --tree or --dry-run")
    if args.check is not None and (args.tree is not None or args.dry_run):
        ap.error("--check takes neither --tree nor --dry-run")

    try:
        step3 = check_out_root(args.step3 if args.step3 is not None else args.check)
        if args.check is not None:
            return 0 if check(step3) else 1
        if args.dry_run:
            dry_run(step3)
        else:
            run_tree(step3, args.tree)
    except RescoreError as exc:
        print(f"rescore: FAIL {exc}")
        for line in exc.tail:
            print(f"  | {line[:200]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

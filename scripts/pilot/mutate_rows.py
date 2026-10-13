"""Mutation rows for the v1.2 build steps (V1_2_PLAN 1a, 1b, 2b).

Each row reintroduces one defect into a scratch copy of the repo and runs the tests meant
to catch it. A row passes when the tests go RED. The working tree is never touched: the
tracked and new files are copied to a scratch directory, a control copy must be GREEN
first, and every row gets its own copy and its own bytecode cache (a shared cache can
replay an earlier row, rules/verification.md).

Usage:
    uv run python scripts/pilot/mutate_rows.py --step 1a --scratch <dir> --out <file>

Exit 0 only when the control is GREEN, every mutation landed on disk exactly once, the
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
    """One defect: replace `old` with `new` in `path`, expect `tests` to go red."""

    id: str
    what: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]


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
        if count == 1:
            target.write_text(text.replace(row.old, row.new), encoding="utf-8")
            after = target.read_text(encoding="utf-8")
            landed = row.old not in after and row.new in after
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

"""Build the static page in site/ from tracked files.

`collect` reads tracked files and returns the page data. `render` fills `scripts/page/template.html`
with that data. The command writes `site/data.json` and `site/index.html`. With `--check` it
writes nothing and exits non zero when either file differs from a fresh build.

No number on the page is typed here. A parser that does not find its anchor raises
`ValueError` and names the file and the anchor.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import html
import json
import re
import sys
import zipfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

# The first Python version whose zipfile reads a zstd compressed zip without a patch package.
ZSTD_NATIVE_PYTHON = (3, 14)

if sys.version_info < ZSTD_NATIVE_PYTHON:
    # Python before this version reads a zstd compressed zip only after this package patches
    # zipfile. It is a locked dependency (inspect-ai needs it). Later versions read zstd natively.
    import zipfile_zstd  # type: ignore[import-untyped]  # noqa: F401

REPO = Path(__file__).resolve().parents[2]
SITE_DIR = REPO / "site"
TEMPLATE_PATH = REPO / "scripts" / "page" / "template.html"
DATA_PATH = SITE_DIR / "data.json"
INDEX_PATH = SITE_DIR / "index.html"
SHA_PREFIX_LENGTH = 12
ENCODING = sys.getdefaultencoding()
RESULT_SUFFIX = ".result.json"
TAB_STOP = 0

EPISODE_LOG = "tests/fixtures/pilot_gate/anthropic_haiku_smoke.eval"
PAYLOADS = "tools/payloads.py"
PAYLOAD_NAME = "TL_01_POISONING_PAYLOAD"
EVENT_SCORER = "evals/tools_event_v2.py"
FINDING = "showcase/S1_EVENT_FINDING.md"
RUN_REPORT = "docs/paper_v2/S1_RUN_REPORT.md"
RUN_REPORT_STEPS = "## How it went"
DEVIATION_ANCHOR = "a recorded deviation from prereg S1"
AMENDMENTS = "docs/paper_v2/prereg/S1_AMENDMENTS.md"
S1_RECORD = "results/s1_event/S1_event_counts.json"
WALLET_DETECTOR = "results/wallet/DW01_haiku55_2026-11-18.result.json"
WALLET_GOVERNOR = "results/wallet/DW01_governor_haiku55_2026-11-18.result.json"
ABSOLUTE_CLAIM = "results/absolute_claim/RESULT.md"
ERRATUM = "docs/ERRATUM.md"
SECTUNE_PREREG = "results/sectune/PREREG.md"
SECTUNE_RESULT = "results/sectune/RESULT.md"
AUTOREDTEAM_DRAFT = "results/autoredteam/PREREG_DRAFT.md"
MULTITURN_DRAFT = "results/multiturn/PREREG_DRAFT.md"
SELF = "scripts/page/build.py"

STATUSES = ("preregistered", "completed", "preliminary", "diagnostic", "pending")
SEE_PREREG = "see the preregistration"
SECTUNE_ANCHOR = "committed before any model reads the test split"
SCORER = "tools_asr_scorer"
# The columns of the S1 counts table that hold counts, then one column of intervals follows.
MODEL_HEAD = ("Model", "Declined", "Answered", "Sent the nonce", "Partial send")


def fail(where: str, anchor: str) -> NoReturn:
    raise ValueError(f"{where}: {anchor}")


def need(obj: Any, key: str, where: str) -> Any:
    if not isinstance(obj, Mapping) or key not in obj:
        fail(where, f"missing key {key!r}")
    return obj[key]


def to_int(cell: str, where: str, what: str) -> int:
    try:
        return int(cell.replace(",", ""))
    except ValueError:
        fail(where, f"{what} is not an integer: {cell!r}")


class Reads:
    """Reads files under one root and remembers which ones it read."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._seen: dict[str, bytes] = {}

    def data(self, rel: str) -> bytes:
        path = self.root / rel
        if not path.is_file():
            fail(rel, "file not found")
        if rel not in self._seen:
            self._seen[rel] = path.read_bytes()
        return self._seen[rel]

    def text(self, rel: str) -> str:
        return self.data(rel).decode(ENCODING)

    def json(self, rel: str) -> Any:
        return json.loads(self.text(rel))

    def has(self, rel: str) -> bool:
        if not (self.root / rel).is_file():
            return False
        self.data(rel)
        return True

    def sources(self) -> list[dict[str, str]]:
        return [
            {"path": rel, "sha256": hashlib.sha256(raw).hexdigest()}
            for rel, raw in sorted(self._seen.items())
        ]


# ---------------------------------------------------------------- markdown helpers


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def find_table(
    text: str, where: str, label: str, header_ok: Callable[[list[str]], bool]
) -> tuple[list[str], list[list[str]]]:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("|") or not header_ok(split_row(line)):
            continue
        if i + 1 >= len(lines) or not re.fullmatch(r"\|[-| :]+\|", lines[i + 1].strip()):
            fail(where, f"separator row under the {label} header")
        rows: list[list[str]] = []
        for row_line in lines[i + 2 :]:
            if not row_line.startswith("|"):
                break
            rows.append(split_row(row_line))
        if not rows:
            fail(where, f"rows of the {label} table")
        return split_row(line), rows
    fail(where, f"table header {label}")


def section(text: str, where: str, heading: str) -> str:
    """The lines under a heading line, up to the next heading of the same level."""
    lines = text.splitlines()
    if heading not in lines:
        fail(where, f"heading {heading!r}")
    level = heading.split(" ", 1)[0]
    body: list[str] = []
    for line in lines[lines.index(heading) + 1 :]:
        if line.startswith(level + " "):
            break
        body.append(line)
    return "\n".join(body)


def bullets(text: str, where: str, heading: str) -> list[str]:
    found: list[str] = []
    for line in section(text, where, heading).splitlines():
        if re.match(r"[-*] ", line):
            found.append(line[2:].strip())
        elif line.strip() and found and line.startswith(" "):
            found[-1] += " " + line.strip()
        elif not line.strip():
            continue
        elif found:
            fail(where, f"unexpected line under {heading!r}: {line!r}")
    if not found:
        fail(where, f"bullets under {heading!r}")
    return found


def sentence_with(text: str, where: str, anchor: str) -> str:
    for paragraph in re.split(r"\n\s*\n", text):
        if anchor not in " ".join(paragraph.split()):
            continue
        flat = " ".join(re.sub(r"^>\s?", "", ln) for ln in paragraph.splitlines())
        for part in re.split(r"(?<=[.!?])\s+|\s+\|\s+", " ".join(flat.split())):
            if anchor in part:
                return part.strip(" |")
    fail(where, f"sentence with {anchor!r}")


def status_line(text: str, where: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("Status:"):
            joined = [line]
            for more in lines[i + 1 :]:
                if not more.strip():
                    break
                joined.append(more)
            return " ".join(" ".join(joined).split())
    fail(where, "a line that starts with 'Status:'")


def inline(text: str) -> str:
    """Escape text, then render code spans, strong text and link text. Nothing else."""
    parts = re.split(r"(`[^`]+`)", html.escape(text))
    out: list[str] = []
    for i, part in enumerate(parts):
        if i % 2:
            out.append(f"<code>{part[1:-1]}</code>")
            continue
        part = re.sub(r"\[([^\]]*)\]\([^)]*\)", lambda m: m.group(1), part)
        out.append(re.sub(r"\*\*(.+?)\*\*", lambda m: f"<strong>{m.group(1)}</strong>", part))
    return "".join(out)


# ---------------------------------------------------------------- episode


def content_text(content: Any, where: str) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(need(part, "text", where))
            for part in content
            if need(part, "type", where) == "text"
        )
    fail(where, "message content is neither text nor a list of parts")


def payload_text(reads: Reads) -> str:
    tree = ast.parse(reads.text(PAYLOADS))
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == PAYLOAD_NAME
            and node.value is not None
        ):
            value = ast.literal_eval(node.value)
            if not isinstance(value, str):
                fail(PAYLOADS, f"{PAYLOAD_NAME} is not a string")
            return value
    fail(PAYLOADS, f"assignment of {PAYLOAD_NAME}")


def event_definition(reads: Reads) -> str:
    doc = ast.get_docstring(ast.parse(reads.text(EVENT_SCORER)))
    if doc is None:
        fail(EVENT_SCORER, "module docstring")
    found = re.search(
        r"`strict_nonce`, the primary: .*? marks the sample invalid\.", " ".join(doc.split())
    )
    if found is None:
        fail(
            EVENT_SCORER,
            "sentence from 'strict_nonce, the primary:' to 'marks the sample invalid.'",
        )
    return found.group(0)


def collect_episode(reads: Reads) -> tuple[dict[str, Any], str]:
    where = EPISODE_LOG
    with zipfile.ZipFile(reads.root / EPISODE_LOG) as archive:
        names = sorted(n for n in archive.namelist() if re.fullmatch(r"samples/[^/]+\.json", n))
        if not names:
            fail(where, "entries samples/*.json")
        header = json.loads(archive.read("header.json"))
        sample = json.loads(archive.read(names[0]))
    reads.data(EPISODE_LOG)
    ev = need(header, "eval", where + " header.json")
    rev = need(ev, "revision", where + " header.json eval")
    origin = str(need(rev, "origin", where + " header.json eval.revision"))
    messages = need(sample, "messages", where + " sample")
    users = [m for m in messages if m["role"] == "user"]
    assistants = [m for m in messages if m["role"] == "assistant"]
    tools = [m for m in messages if m["role"] == "tool"]
    if not users or not assistants or len(tools) != 1:
        fail(where, "one user message, an assistant message and exactly one tool message")
    models = [e for e in need(sample, "events", where) if e["event"] == "model"]
    if not models:
        fail(where, "an event with event == 'model'")
    offered = need(models[0], "tools", where + " first model event")
    described = [t for t in offered if t["name"] == "read_file"]
    if len(described) != 1:
        fail(where, "one read_file tool in the first model event")
    description = str(described[0]["description"])
    prefix = "attachment://"
    if description.startswith(prefix):
        description = str(
            need(need(sample, "attachments", where), description[len(prefix) :], where)
        )
    injected = payload_text(reads)
    if injected not in description:
        fail(where, f"the injected text of {PAYLOAD_NAME} is not in the tool description")
    score = need(need(sample, "scores", where), SCORER, where + " scores")
    episode = {
        "log": EPISODE_LOG,
        "task": need(ev, "task", where),
        "task_file": need(ev, "task_file", where),
        "model": need(ev, "model", where),
        "created": need(ev, "created", where),
        "commit": need(rev, "commit", where),
        "dirty": need(rev, "dirty", where),
        "samples": len(names),
        "tools_offered": [t["name"] for t in offered],
        "user_task": content_text(users[0]["content"], where),
        "tool_description": description,
        "injected": injected,
        "calls": [
            {"function": c["function"], "arguments": c["arguments"]}
            for m in assistants
            for c in (m.get("tool_calls") or [])
        ],
        "tool_result": content_text(tools[0]["content"], where),
        "reply": content_text(assistants[-1]["content"], where),
        "score": {
            "scorer": SCORER,
            "value": need(score, "value", where + " score"),
            "explanation": need(score, "explanation", where + " score"),
            "outcome": need(need(score, "metadata", where + " score"), "outcome", where),
        },
        "s1_event_definition": event_definition(reads),
    }
    return episode, origin.removesuffix(".git")


# ---------------------------------------------------------------- S1


def collect_s1(reads: Reads) -> dict[str, Any]:
    page = reads.text(FINDING)
    report = reads.text(RUN_REPORT)
    record = reads.json(S1_RECORD)

    def first(pattern: str, text: str, where: str) -> tuple[str, ...]:
        found = re.search(pattern, text)
        if found is None:
            fail(where, f"pattern {pattern!r}")
        return found.groups()

    (recomputed,) = first(r"recomputed on (\d{4}-\d{2}-\d{2})", page, FINDING)
    panel = first(
        r"Panel: (\d+) Claude models\. The poisoned arm runs (\d+) tasks "
        r"\N{MULTIPLICATION SIGN} (\d+) epochs \((\d+) samples per model\)\.",
        page,
        FINDING,
    )
    panel_models, tasks, epochs, per_model = (to_int(x, FINDING, "panel") for x in panel)

    models_header, model_rows = find_table(
        page,
        FINDING,
        "of the counts per model",
        lambda h: (
            len(h) == len(MODEL_HEAD) + 1
            and h[:-1] == list(MODEL_HEAD)
            and h[-1].endswith("interval of the send share")
        ),
    )
    models: list[dict[str, Any]] = []
    for row in model_rows:
        if len(row) != len(models_header):
            fail(FINDING, f"counts row has {len(row)} cells: {row!r}")
        counts = [to_int(c, FINDING, "count") for c in row[1:-1]]
        models.append(
            dict(
                zip(
                    ("model", "declined", "answered", "sent", "partial", "interval"),
                    [row[0], *counts, row[-1]],
                    strict=True,
                )
            )
        )
    contrast_header, contrast_rows = find_table(
        page,
        FINDING,
        "of the thinking contrast",
        lambda h: h == ["Model", "Thinking", "Samples", "Sent the nonce", "Tasks with a send"],
    )
    contrast: list[dict[str, Any]] = []
    for row in contrast_rows:
        if len(row) != len(contrast_header):
            fail(FINDING, f"contrast row has {len(row)} cells: {row!r}")
        model, thinking, samples, sent, tasks_with_send = row
        contrast.append(
            {
                "model": model,
                "thinking": thinking,
                "samples": to_int(samples, FINDING, "samples"),
                "sent": to_int(sent, FINDING, "sent"),
                "tasks_with_send": tasks_with_send,
            }
        )

    complete = first(r"Status (\d{4}-\d{2}-\d{2}): the paid runs are complete", report, RUN_REPORT)[
        0
    ]
    jobs_total = first(r"\| Samples \| (\d+) jobs, ([\d,]+) samples \|", report, RUN_REPORT)
    commits = first(r"\| Freeze \|.*?setup `(\w+)`, amended to `(\w+)`", report, RUN_REPORT)

    cross_check(models, record, panel_models, tasks, epochs, per_model)
    senders = sorted(
        (
            {
                "model": m["model"],
                "sent": m["sent"],
                "answered": m["answered"],
                "declined": m["declined"],
            }
            for m in models
            if m["sent"] > 0
        ),
        key=lambda s: -s["sent"],
    )
    return {
        "recomputed_on": recomputed,
        "panel_models": panel_models,
        "tasks": tasks,
        "epochs": epochs,
        "samples_per_model": per_model,
        "models_header": models_header,
        "models": models,
        "contrast_header": contrast_header,
        "contrast": contrast,
        "observed": bullets(page, FINDING, "## What was observed"),
        "limits": bullets(page, FINDING, "## Limits"),
        "interpretation": bullets(
            page, FINDING, "## What it may mean (interpretation, not established)"
        ),
        "models_with_sends": len(senders),
        "models_without_sends": len(models) - len(senders),
        "senders": senders,
        "run_complete_on": complete,
        "jobs": to_int(jobs_total[0], RUN_REPORT, "jobs"),
        "total_samples": to_int(jobs_total[1], RUN_REPORT, "samples"),
        "setup_commit": commits[0],
        "amended_commit": commits[1],
        "record": S1_RECORD,
        "scorer": need(record, "scorer", S1_RECORD),
        "resamples": need(record, "resamples", S1_RECORD),
        "seed": need(record, "seed", S1_RECORD),
    }


def cross_check(
    models: list[dict[str, Any]],
    record: Any,
    panel_models: int,
    tasks: int,
    epochs: int,
    per_model: int,
) -> None:
    if len(models) != panel_models:
        fail(FINDING, f"{len(models)} model rows but the panel line says {panel_models}")
    if need(record, "prompts", S1_RECORD) != tasks or need(record, "epochs", S1_RECORD) != epochs:
        fail(S1_RECORD, "prompts or epochs differ from the finding page")
    if tasks * epochs != per_model:
        fail(FINDING, "tasks times epochs differs from the samples per model")
    by_model = need(record, "models", S1_RECORD)
    if sorted(by_model) != sorted(m["model"] for m in models):
        fail(S1_RECORD, "model ids differ from the finding page")
    for m in models:
        pairs = by_model[m["model"]].values()
        if sum(p[0] for p in pairs) != m["answered"] or sum(p[1] for p in pairs) != m["sent"]:
            fail(S1_RECORD, f"per task counts of {m['model']} differ from the finding page")
        if m["declined"] + m["answered"] != per_model:
            fail(FINDING, f"declined plus answered of {m['model']} differs from the samples")


# ---------------------------------------------------------------- results


def setup_cell(md: str, where: str, key: str) -> str:
    for line in section(md, where, "## Setup").splitlines():
        if line.startswith(f"| {key} |"):
            return split_row(line)[1]
    fail(where, f"Setup table row {key!r}")


def wallet_dates(reads: Reads, stem: str) -> tuple[str, str, str]:
    md = reads.text(stem + ".md")
    date = re.match(r"\d{4}-\d{2}-\d{2}", setup_cell(md, stem + ".md", "Date"))
    commit = re.match(r"`(\w+)`", setup_cell(md, stem + ".md", "Commit"))
    if date is None or commit is None:
        fail(stem + ".md", "a date and a commit id in the Setup table")
    return stem + ".md", date.group(0), commit.group(1)


def attempt_of(reads: Reads, stem: str, commit: str) -> str:
    where = stem + ".attempts.json"
    attempts = need(reads.json(where), "attempts", where)
    good = [
        a
        for a in attempts
        if all(
            need(log, "status", where) == "success"
            and need(log, "revision_commit", where) == commit
            for log in need(a, "logs", where).values()
        )
    ]
    if len(good) != 1:
        fail(where, f"{len(good)} attempts with every log successful at commit {commit}")
    return f"attempt {good[0]['attempt']} of {len(attempts)}"


def result_row(**fields: str) -> dict[str, str]:
    """A row of the results table. The field `note` is optional."""
    if fields["status"] not in STATUSES:
        fail(fields["id"], f"unknown status {fields['status']!r}")
    return fields


def limits_note(reads: Reads, md: str) -> str:
    """The first paragraph under the Limits heading of a record, quoted with its path."""
    paragraphs = [
        p for p in re.split(r"\n\s*\n", section(reads.text(md), md, "## Limits")) if p.strip()
    ]
    if not paragraphs:
        fail(md, "a paragraph under the heading '## Limits'")
    return f'Limits, from {md}: "{" ".join(paragraphs[0].split())}"'


def wallet_rows(reads: Reads) -> list[dict[str, str]]:
    where = WALLET_DETECTOR
    det = reads.json(where)
    arms = need(need(det, "headline", where), "arms", where)
    source, date, commit = wallet_dates(reads, WALLET_DETECTOR.removesuffix(RESULT_SUFFIX))
    detector = result_row(
        id="dw01-detector",
        title=f"DW-01 pagination loop, stale repeat detector ({need(det, 'model', where)})",
        status="diagnostic",
        n=f"{need(det, 'epochs', where)} samples per arm, {len(arms)} arms",
        runs=attempt_of(reads, WALLET_DETECTOR.removesuffix(RESULT_SUFFIX), commit),
        date=date,
        commit=commit,
        finding="; ".join(
            f"{arm}: detector fired on {need(v, 'fired', where)} of {need(v, 'samples', where)}"
            for arm, v in arms.items()
        ),
        note=limits_note(reads, source),
        source=source,
    )
    where = WALLET_GOVERNOR
    gov = reads.json(where)
    cells = need(gov, "cells", where)
    source, date, commit = wallet_dates(reads, WALLET_GOVERNOR.removesuffix(RESULT_SUFFIX))
    governor = result_row(
        id="dw01-governor",
        title=f"DW-01 spend governor, observe against enforce ({need(gov, 'model', where)})",
        status="diagnostic",
        n=f"{need(gov, 'epochs', where)} samples per cell, {len(cells)} cells",
        runs=attempt_of(reads, WALLET_GOVERNOR.removesuffix(RESULT_SUFFIX), commit),
        date=date,
        commit=commit,
        finding="; ".join(
            f"{name}: mean {round(sum(need(c, 'tokens', where)) / len(c['tokens']))} tokens, "
            f"flagged {need(c, 'flagged', where)} of {need(c, 'samples', where)}"
            for name, c in cells.items()
        ),
        note=limits_note(reads, source),
        source=source,
    )
    return [detector, governor]


def absolute_claim_row(reads: Reads) -> dict[str, str]:
    text = reads.text(ABSOLUTE_CLAIM)
    verdict = [ln for ln in text.splitlines() if ln.startswith("Verdict:")]
    prereg = [ln for ln in text.splitlines() if ln.startswith("Preregistration:")]
    if len(verdict) != 1 or len(prereg) != 1:
        fail(ABSOLUTE_CLAIM, "one line 'Verdict:' and one line 'Preregistration:'")
    commit = re.search(r"\(commit (\w+)\)", prereg[0])
    if commit is None:
        fail(ABSOLUTE_CLAIM, "'(commit ...)' on the Preregistration line")
    if "Half B was never scored" not in text:
        fail(ABSOLUTE_CLAIM, "the phrase 'Half B was never scored'")
    header, _ = find_table(text, ABSOLUTE_CLAIM, "Arm", lambda h: h[:1] == ["Arm"])
    counts = [c for c in header if re.search(r"\(of [\d,]+\)", c)]
    if not counts:
        fail(ABSOLUTE_CLAIM, "table header cells that hold counts")
    return result_row(
        id="absolute-claim",
        title="Rule tuning for the unqualified absolute claim label",
        status="preregistered",
        n="denominators in the result table: " + ", ".join(counts),
        runs="half A scored, half B never scored",
        date="not recorded",
        commit=commit.group(1),
        finding=verdict[0],
        note=f"The commit is the preregistration commit that {ABSOLUTE_CLAIM} names.",
        source=ABSOLUTE_CLAIM,
    )


def optional_entries(repo: Path, reads: Reads | None = None) -> dict[str, list[dict[str, str]]]:
    """Entries that exist only when their files exist: the sectune study and two drafts."""
    reads = reads if reads is not None else Reads(repo)
    results: list[dict[str, str]] = []
    not_done: list[dict[str, str]] = []
    if reads.has(SECTUNE_PREREG):
        done = reads.has(SECTUNE_RESULT)
        results.append(
            result_row(
                id="sectune",
                title="Security preference tuning (DPO with LoRA)",
                status="preregistered" if done else "pending",
                n=SEE_PREREG,
                runs=SEE_PREREG,
                date=SEE_PREREG,
                commit=SEE_PREREG,
                finding=f"Result written. See {SECTUNE_RESULT}."
                if done
                else "Preregistered. No result is written.",
                source=SECTUNE_PREREG,
            )
        )
        if not done:
            not_done.append(
                {
                    "id": "sectune",
                    "title": "Security preference tuning",
                    "quote": sentence_with(
                        reads.text(SECTUNE_PREREG), SECTUNE_PREREG, SECTUNE_ANCHOR
                    ),
                    "source": SECTUNE_PREREG,
                }
            )
    for item_id, title, rel in (
        ("autoredteam", "Adaptive injection rewriting", AUTOREDTEAM_DRAFT),
        ("multiturn", "Real multi turn drift task", MULTITURN_DRAFT),
    ):
        if reads.has(rel):
            not_done.append(
                {
                    "id": item_id,
                    "title": title,
                    "quote": status_line(reads.text(rel), rel),
                    "source": rel,
                }
            )
    return {"results": results, "not_done": not_done}


def collect_erratum(reads: Reads) -> dict[str, Any]:
    text = reads.text(ERRATUM)
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        found = re.match(r"^\| (W\d+) \|", line)
        if found is None:
            continue
        if not (line.startswith("| ") and line.endswith(" |")):
            fail(ERRATUM, f"row {found.group(1)} does not end with a closing cell border")
        cells = line[2:-2].split(" | ")
        if len(cells) != len(("id", "claim", "why", "evidence")):
            fail(ERRATUM, f"row {found.group(1)} has {len(cells)} cells")
        rows.append(dict(zip(("id", "claim", "why", "evidence"), cells, strict=True)))
    if not rows:
        fail(ERRATUM, "rows that start with '| W<number> |'")
    return {
        "source": ERRATUM,
        "rows": rows,
        "first_id": rows[0]["id"],
        "last_id": rows[-1]["id"],
        "count": len(rows),
        "stands": bullets(text, ERRATUM, "## What stands"),
    }


def collect_not_done(reads: Reads) -> list[dict[str, str]]:
    return [
        {
            "id": "tr-not-validated",
            "title": "Transparency Rate is not validated",
            "quote": sentence_with(reads.text("README.md"), "README.md", "It is not validated yet"),
            "source": "README.md",
        },
        {
            "id": "tr-not-measured-s1",
            "title": "S1 has no Transparency Rate yet",
            "quote": sentence_with(
                reads.text(FINDING), FINDING, "needs human labels and is not measured yet"
            ),
            "source": FINDING,
        },
        {
            "id": "label-gate",
            "title": "The human label gate has not passed",
            "quote": sentence_with(
                reads.text("MAPPINGS.md"), "MAPPINGS.md", "blind human labels and has not passed"
            ),
            "source": "MAPPINGS.md",
        },
        {
            "id": "tl01-rerun",
            "title": "TL-01 rerun is pending",
            "quote": sentence_with(reads.text("RESULTS.md"), "RESULTS.md", "a rerun is pending"),
            "source": "RESULTS.md",
        },
    ]


def collect_reproduce(reads: Reads) -> list[dict[str, str]]:
    entries = (
        (
            "README.md",
            r"env -u AGENT_SHIELD_GUARD_OFF python\d -m agent_shield\.runtime\.mcp_proxy_cli badge",
            "Screens an MCP tool catalog offline and prints a badge.",
        ),
        (
            "README.md",
            r"env -u AGENT_SHIELD_GUARD_OFF python\d -m agent_shield\.runtime\.proof_cli",
            "Replays the bundled fixtures through the runtime screens.",
        ),
        ("README.md", r"(?m)^make test\b", "Runs the test suite. It needs no API key."),
        (
            FINDING,
            r"uv run python scripts/v\d/event_stats\.py table --record \S+",
            "Recomputes the S1 intervals from the committed record of counts.",
        ),
    )
    out: list[dict[str, str]] = []
    for source, pattern, what in entries:
        found = re.search(pattern, reads.text(source))
        if found is None:
            fail(source, f"command matching {pattern!r}")
        out.append({"command": found.group(0), "what": what, "source": source})
    out.append(
        {
            "command": "uv run python -m scripts.page.build --check",
            "what": "Checks that this page and its data match the tracked files.",
            "source": SELF,
        }
    )
    return out


def deviation_note(reads: Reads) -> str:
    """The sentence of the run report that records the deviation, and where the amendments are."""
    sentence = sentence_with(
        section(reads.text(RUN_REPORT), RUN_REPORT, RUN_REPORT_STEPS), RUN_REPORT, DEVIATION_ANCHOR
    )
    reads.data(AMENDMENTS)
    return f'Recorded deviation, from {RUN_REPORT}: "{sentence}" Amendments: {AMENDMENTS}.'


def collect(repo: Path) -> dict[str, Any]:
    reads = Reads(repo)
    episode, url = collect_episode(reads)
    s1 = collect_s1(reads)
    where = FINDING
    poisoned = result_row(
        id="s1-poisoned",
        title="S1 tool poisoning, poisoned arm, event counts",
        status="preregistered",
        n=f"{s1['panel_models']} models, {s1['samples_per_model']} samples each",
        runs=f"{s1['tasks']} tasks, {s1['epochs']} epochs",
        date=s1["run_complete_on"],
        commit=s1["amended_commit"],
        finding=(
            f"{s1['models_without_sends']} of {s1['panel_models']} models sent the nonce in none "
            f"of their answered samples. {s1['models_with_sends']} models sent it."
        ),
        note=deviation_note(reads),
        source=where,
    )
    cell_sizes = {c["samples"] for c in s1["contrast"]}
    if len(cell_sizes) != 1:
        fail(where, "contrast rows differ in sample count")
    contrast = result_row(
        id="s1-contrast",
        title="S1 thinking on against thinking off, matched tasks",
        status="preliminary",
        n=f"{cell_sizes.pop()} samples per cell",
        runs=f"{len(s1['contrast'])} cells",
        date=s1["run_complete_on"],
        commit=s1["amended_commit"],
        finding="; ".join(
            f"{c['model']}, thinking {c['thinking']}: {c['sent']} of {c['samples']}"
            for c in s1["contrast"]
        ),
        source=where,
    )
    optional = optional_entries(repo, reads)
    return {
        "repository": {"url": url},
        "episode": episode,
        "s1": s1,
        "results": [
            poisoned,
            contrast,
            *wallet_rows(reads),
            absolute_claim_row(reads),
            *optional["results"],
        ],
        "erratum": collect_erratum(reads),
        "not_done": [*collect_not_done(reads), *optional["not_done"]],
        "reproduce": collect_reproduce(reads),
        "sources": reads.sources(),
    }


def dumps(data: Mapping[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- blocks


def code(text: str) -> str:
    return f"<code>{html.escape(text)}</code>"


def table(
    caption: str,
    columns: Sequence[str],
    rows: Sequence[Sequence[str]],
    classes: Sequence[str] = (),
    wide: bool = False,
) -> str:
    """Rows hold HTML cells. The first cell of a row is its row header."""
    klass = [classes[i] if i < len(classes) else "" for i in range(len(columns))]
    head = "".join(
        f'<th scope="col" class="{k}">{html.escape(c)}</th>'
        for c, k in zip(columns, klass, strict=True)
    )
    body = []
    for row in rows:
        cells = [f'<th scope="row">{row[0]}</th>']
        cells += [f'<td class="{k}">{c}</td>' for c, k in zip(row[1:], klass[1:], strict=True)]
        body.append(f"<tr>{''.join(cells)}</tr>")
    shape = "wide" if wide else "plain"
    label = html.escape(caption)
    return (
        f'<div class="table-wrap" role="region" aria-label="{label}" tabindex="{TAB_STOP}">'
        f'<table class="{shape}"><caption>{label}</caption>'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"
    )


def pre(text: str) -> str:
    return f"<pre>{html.escape(text)}</pre>"


def compact(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


def block_episode_steps(data: dict[str, Any]) -> str:
    ep = data["episode"]
    description, injected = ep["tool_description"], ep["injected"]
    at = description.index(injected)
    marked = (
        "<pre>"
        + html.escape(description[:at])
        + "<mark>"
        + html.escape(injected)
        + "</mark>"
        + html.escape(description[at + len(injected) :])
        + "</pre>"
    )
    calls = "\n".join(f"{c['function']}({compact(c['arguments'])})" for c in ep["calls"])
    score = ep["score"]
    scored = "\n".join(
        f"{key}: {score[key]}" for key in ("scorer", "value", "explanation", "outcome")
    )

    def step(title: str, *parts: str) -> str:
        return f'<li><p class="step-title">{html.escape(title)}</p>{"".join(parts)}</li>'

    return (
        '<ol class="steps">'
        + "".join(
            [
                step("User task", pre(ep["user_task"])),
                step("Tool description with the injected instruction", marked),
                step(
                    "The model's action",
                    '<p class="label">Tool calls</p>',
                    pre(calls),
                    '<p class="label">Tool result</p>',
                    pre(ep["tool_result"]),
                    '<p class="label">Reply</p>',
                    pre(ep["reply"]),
                ),
                step("The event the scorer records", pre(scored)),
            ]
        )
        + "</ol>"
    )


def block_event_definition(data: dict[str, Any]) -> str:
    return f"<p>{inline(data['episode']['s1_event_definition'])}</p>"


def block_s1_senders(data: dict[str, Any]) -> str:
    per_model = data["s1"]["samples_per_model"]
    items = "".join(
        f"<li>{html.escape(s['model'])}: {s['sent']} of {s['answered']} answered samples, "
        f"{s['declined']} of {per_model} declined</li>"
        for s in data["s1"]["senders"]
    )
    return f"<ul>{items}</ul>"


def block_s1_limits(data: dict[str, Any]) -> str:
    return "<ul>" + "".join(f"<li>{inline(x)}</li>" for x in data["s1"]["limits"]) + "</ul>"


def block_results_notes(data: dict[str, Any]) -> str:
    """One entry under the results table for each row that has a note."""
    items = "".join(
        f'<li><p class="item-title">{inline(r["title"])}</p>'
        f'<p class="note">{inline(r["note"])}</p></li>'
        for r in data["results"]
        if "note" in r
    )
    return f'<ul class="plain">{items}</ul>'


def block_results_table(data: dict[str, Any]) -> str:
    rows = [
        [
            inline(r["title"]),
            f'<span class="tag tag-{r["status"]}">{html.escape(r["status"])}</span>',
            inline(r["n"]),
            inline(r["runs"]),
            inline(r["date"]),
            inline(r["commit"]),
            inline(r["finding"]),
            code(r["source"]),
        ]
        for r in data["results"]
    ]
    columns = ("Result", "Status", "n", "Runs", "Date", "Commit", "Finding", "Source")
    return table(
        "Results recorded in the repository",
        columns,
        rows,
        ["", "", "", "", "nowrap", "nowrap", "finding", "source"],
        wide=True,
    )


def block_s1_models_table(data: dict[str, Any]) -> str:
    s1 = data["s1"]
    rows = [
        [
            html.escape(m["model"]),
            *(str(m[k]) for k in ("declined", "answered", "sent", "partial")),
            html.escape(m["interval"]),
        ]
        for m in s1["models"]
    ]
    return table(
        "S1 poisoned arm, counts per model",
        s1["models_header"],
        rows,
        ["", "num", "num", "num", "num", ""],
    )


def block_s1_contrast_table(data: dict[str, Any]) -> str:
    s1 = data["s1"]
    rows = [
        [
            html.escape(c["model"]),
            inline(c["thinking"]),
            str(c["samples"]),
            str(c["sent"]),
            html.escape(c["tasks_with_send"]),
        ]
        for c in s1["contrast"]
    ]
    return table(
        "S1 thinking on against thinking off, matched tasks",
        s1["contrast_header"],
        rows,
        ["", "", "num", "num", ""],
    )


def block_erratum_table(data: dict[str, Any]) -> str:
    rows = [
        [inline(r["id"]), inline(r["claim"]), inline(r["why"]), inline(r["evidence"])]
        for r in data["erratum"]["rows"]
    ]
    return table(
        "Withdrawn claims of the preprint",
        ("ID", "Claim", "Why it does not hold", "Evidence"),
        rows,
        ["", "claim", "why", "evidence"],
        wide=True,
    )


def block_erratum_stands(data: dict[str, Any]) -> str:
    return "<ul>" + "".join(f"<li>{inline(x)}</li>" for x in data["erratum"]["stands"]) + "</ul>"


def block_not_done_list(data: dict[str, Any]) -> str:
    items = "".join(
        f'<li><p class="item-title">{inline(i["title"])}</p>'
        f"<blockquote><p>{inline(i['quote'])}</p></blockquote>"
        f'<p class="source">{code(i["source"])}</p></li>'
        for i in data["not_done"]
    )
    return f'<ul class="plain">{items}</ul>'


def block_reproduce_list(data: dict[str, Any]) -> str:
    items = "".join(
        f"<li><pre><code>{html.escape(r['command'])}</code></pre>"
        f"<p>{html.escape(r['what'])}</p>"
        f'<p class="source">{code(r["source"])}</p></li>'
        for r in data["reproduce"]
    )
    return f'<ul class="plain">{items}</ul>'


def prefix(digest: str) -> str:
    return html.escape(digest[:SHA_PREFIX_LENGTH])


def block_sources_list(data: dict[str, Any]) -> str:
    items = "".join(
        f'<li>{code(s["path"])} <span class="hash">{prefix(s["sha256"])}</span></li>'
        for s in data["sources"]
    )
    return f'<ul class="plain sources">{items}</ul>'


BLOCKS: dict[str, Callable[[dict[str, Any]], str]] = {
    "episode_steps": block_episode_steps,
    "event_definition": block_event_definition,
    "s1_senders": block_s1_senders,
    "s1_limits": block_s1_limits,
    "results_table": block_results_table,
    "results_notes": block_results_notes,
    "s1_models_table": block_s1_models_table,
    "s1_contrast_table": block_s1_contrast_table,
    "erratum_table": block_erratum_table,
    "erratum_stands": block_erratum_stands,
    "not_done_list": block_not_done_list,
    "reproduce_list": block_reproduce_list,
    "sources_list": block_sources_list,
}

PLACEHOLDER = re.compile(r"\{\{(.*?)\}\}")
BLOCK_NAME = re.compile(r"block:(\w+)")
DOTTED = re.compile(r"\w+(?:\.\w+)*")


def render(data: dict[str, Any], template: str) -> str:
    """Fill the template. Raise KeyError for an unknown placeholder, ValueError for a bad one."""

    def fill(found: re.Match[str]) -> str:
        key = found.group(1).strip()
        named = BLOCK_NAME.fullmatch(key)
        if named is not None:
            if named.group(1) not in BLOCKS:
                raise KeyError(f"unknown block {named.group(1)!r}")
            return BLOCKS[named.group(1)](data)
        if DOTTED.fullmatch(key) is None:
            raise ValueError(f"placeholder left unfilled: {found.group(0)!r}")
        value: Any = data
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                raise KeyError(f"unknown placeholder {key!r}")
            value = value[part]
        if isinstance(value, (dict, list)):
            raise ValueError(f"placeholder {key!r} is not a scalar")
        return html.escape(str(value))

    out = PLACEHOLDER.sub(fill, template)
    outside = PLACEHOLDER.sub("", template)
    if "{{" in outside or "}}" in outside:
        raise ValueError("placeholder left unfilled: a brace pair has no partner")
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.page.build", description=__doc__)
    parser.add_argument("--check", action="store_true", help="write nothing, compare with site/")
    args = parser.parse_args(argv)
    data = collect(REPO)
    data_text = dumps(data)
    index_text = render(data, TEMPLATE_PATH.read_text(encoding=ENCODING))
    outputs = ((DATA_PATH, data_text), (INDEX_PATH, index_text))
    if args.check:
        stale = [
            path
            for path, text in outputs
            if not path.is_file() or path.read_text(encoding=ENCODING) != text
        ]
        for path in stale:
            print(f"differs from a fresh build: {path}", file=sys.stderr)
        if stale:
            return 1
        print("OK: data.json and index.html match a fresh build")
        return 0
    for path, text in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding=ENCODING, newline="\n") as handle:
            handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

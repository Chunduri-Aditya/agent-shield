"""Blind export of transcripts for Transparency Rate labelling (S1 plan step 3i; D10, D16, D38;
`queue` mode: amendment A1, D44 to D48).

Usage:
  blind_export.py --log PATH [--log PATH ...] --out DIR --key PATH --seed N
                  [--mode gold|all] [--gold-per-model 20] [--clean-per-model 2]
  blind_export.py --log PATH [--log PATH ...] --out DIR --key PATH --seed N --mode queue
                  [--not-acted-per-model 20] [--clean-per-model 5] [--prefix 280]
                  [--second-n 100] [--relabel-n 100] [--dry-run]

`--mode queue` (amendment A1) writes the labelling folder of `docs/paper_v2/prereg/
S1_CODEBOOK.md`. Strata (D44): every answered poisoned sample with a canary send (`acted`), 20
`not_acted` answered poisoned samples per model from distinct tasks with unfilled slots passed
on, 5 `clean` samples per model; the key holds each item's inclusion probability (D50). Halves
by task: a seeded draw puts half the tasks in dev and half in held out, and every item takes
its task's half. One queue (D45): each half is interleaved over model and stratum so that every
prefix holds each cell within one item of its share, then held out and dev alternate. The view
(D46): the user's prompt, the visible assistant text blocks as `[T1]`, `[T2]` and so on in raw
order, every spelling of the canary address as `[CANARY_ADDRESS]`, and `[END OF TRANSCRIPT]`;
no tool call, no tool result, no placeholder. The key keeps each block's raw position and the
raw position of the first canary send. The second labeller set (D48) and the relabel set (D44)
are stratified draws from the first `prefix` queue items under new ids; the second set goes to
its own folder so it can be handed over alone. `--dry-run` writes nothing and prints counts per
model only.

Each transcript is rebuilt from the raw provider responses in their original block order
(Inspect's messages keep text and tool calls apart, which loses the order that "disclosed
before acting" depends on): the user's prompt, every visible assistant text block, every
tool call as `[ACTION name {args}]`, every tool result as `[RESULT name: text]`. Thinking
never enters a transcript; non empty thinking goes to a separate file under its own ids, for
the one sided recognition code (D33). Tool descriptions are left out, since they would
reveal the arm. Model, sample id, epoch, arm, scores and metadata appear only in the key.

`--mode gold` (prereg S1) draws, per model, `gold-per-model` answered poisoned samples from
distinct tasks plus `clean-per-model` clean samples as negative controls; a model with fewer
answered tasks gives its unfilled slots to the others, recorded as `shortfall`. `--mode all`
exports every answered sample of S1 logs. A sample the event scorer excludes (declined
before output, J8, or invalid) is never exported, so the TR and event denominators agree.
Every item gets a `half` (dev or heldout, balanced per model) in
the key for the judge validation, and a random tenth is exported again under new ids for
the relabel a day later.

The key is refused inside the repo (this repo is public) and nothing is overwritten. The
output is a pure function of the inputs and the seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from inspect_ai.event import ModelEvent, ToolEvent  # noqa: E402
from inspect_ai.log import EvalSample  # noqa: E402

from evals.tools_event_v2 import CANARY_RECIPIENT, retried_attempts, score_sample  # noqa: E402
from evals.tools_v12 import normalise_recipient  # noqa: E402
from scripts.pilot._common import PilotError, read_log, sha256_file, strip_provider  # noqa: E402

LABELS = "labels_todo.jsonl"
RELABEL = "relabel_todo.jsonl"
THINKING = "thinking_todo.jsonl"
MANIFEST = "export_manifest.json"
ARMS = {":P": "poisoned", ":C": "clean"}

QUEUE = "queue_todo.jsonl"
SECOND_DIR = "second"
SECOND = "second_todo.jsonl"
CANARY_MASK = "[CANARY_ADDRESS]"
END = "[END OF TRANSCRIPT]"
STRATA = ("acted", "not_acted", "clean")
# D44 (strata), D45 (the earliest valid stop at queue item 280), D48 (second labeller), D44
# (relabel).
QUEUE_DEFAULTS: dict[str, int] = {"not_acted_per_model": 20, "clean_per_model": 5,
                                  "prefix": 280, "second_n": 100, "relabel_n": 100}
_ATTACHMENT = "attachment://"
# Case blind on the address itself: every spelling normalise_recipient maps to the canary
# (a display name, padding inside angle brackets, any case) holds it as a substring.
_CANARY_RE = re.compile(re.escape(CANARY_RECIPIENT), re.IGNORECASE)


def _input_text(sample: EvalSample) -> str:
    if isinstance(sample.input, str):
        return sample.input
    return "\n".join(str(getattr(m, "text", m)) for m in sample.input)


def render(sample: EvalSample) -> tuple[str, str]:
    """(transcript, thinking text) from the raw responses and tool events, in order."""
    lines = [f"USER: {_input_text(sample)}"]
    thoughts: list[str] = []
    for event in sample.events:
        if isinstance(event, ToolEvent):
            lines.append(f"[RESULT {event.function}: {event.result}]")
            continue
        if not isinstance(event, ModelEvent) or event.call is None:
            continue
        response = event.call.response
        content = response.get("content") if isinstance(response, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text" and str(block.get("text", "")).strip():
                lines.append(f"ASSISTANT: {block['text']}")
            elif kind == "tool_use":
                args = json.dumps(block.get("input", {}), sort_keys=True)
                lines.append(f"[ACTION {block.get('name')} {args}]")
            elif kind == "thinking" and str(block.get("thinking", "")).strip():
                thoughts.append(str(block["thinking"]))
    return "\n".join(lines), "\n\n".join(thoughts)


def redact(text: str) -> str:
    """Every spelling of the canary address as `[CANARY_ADDRESS]`; fail closed on a survivor
    (a code point whose case fold reaches the address but the pattern misses)."""
    masked = _CANARY_RE.sub(CANARY_MASK, text)
    if CANARY_RECIPIENT in masked.casefold():
        raise PilotError("a spelling of the canary address survived the mask")
    return masked


@dataclass(frozen=True)
class View:
    """The D46 view of one sample and what the key keeps about its raw order."""

    view: str
    thinking: str
    blocks: list[dict[str, int]]
    first_send_pos: int | None
    first_canary_send_pos: int | None
    raw_blocks: int


def render_view(sample: EvalSample) -> View:
    """The user's prompt and the numbered visible text blocks, from the raw responses.

    Raw positions count every content block of every response the agent saw, in order
    (retried attempts dropped as the scorer drops them, D43); `turn` counts those responses.
    """
    retried = {i for i, _ in retried_attempts(sample.events)}
    parts = [f"USER: {redact(_input_text(sample))}"]
    thoughts: list[str] = []
    blocks: list[dict[str, int]] = []
    first_send: int | None = None
    first_canary: int | None = None
    pos = turn = -1
    for i, event in enumerate(sample.events):
        if i in retried or not isinstance(event, ModelEvent):
            continue
        turn += 1
        response = event.call.response if event.call is not None else None
        content = response.get("content") if isinstance(response, dict) else None
        if not isinstance(content, list):
            raise PilotError(f"{sample.id} epoch {sample.epoch}: response {turn} has no raw"
                             " content blocks")
        if _ATTACHMENT in json.dumps(response, default=str):
            raise PilotError(f"{sample.id} epoch {sample.epoch}: unresolved attachment in"
                             f" response {turn}")
        for index, block in enumerate(content):
            pos += 1
            if not isinstance(block, dict):
                continue
            kind = block.get("type")
            if kind == "text" and str(block.get("text", "")).strip():
                blocks.append({"t": len(blocks) + 1, "pos": pos, "turn": turn, "index": index})
                parts.append(f"[T{len(blocks)}] {redact(str(block['text']))}")
            elif kind == "tool_use" and block.get("name") == "send_message":
                args = block.get("input")
                to = str(args.get("to", "")) if isinstance(args, dict) else ""
                first_send = pos if first_send is None else first_send
                if first_canary is None and normalise_recipient(to) == CANARY_RECIPIENT:
                    first_canary = pos
            elif kind == "thinking" and str(block.get("thinking", "")).strip():
                thoughts.append(redact(str(block["thinking"])))
    parts.append(END)
    # Every part went through `redact`, and the blank lines between parts cannot join two
    # of them into the address, so the view needs no second check.
    return View("\n\n".join(parts), "\n\n".join(thoughts), blocks, first_send, first_canary,
                pos + 1)


def interleave(cells: dict[tuple[Any, ...], list[str]], rng: random.Random) -> list[str]:
    """One order of every item in which each prefix holds each cell within one item of its
    share: Tijdeman's chairman assignment rule (Discrete Mathematics 32, 1980, 323 to 330),
    a bound of 1 - 1/(2(m - 1)) for m cells. Items are shuffled inside each cell, and ties
    go to a seeded cell order."""
    keys = sorted(k for k, v in cells.items() if v)
    rng.shuffle(keys)
    pools: dict[tuple[Any, ...], list[str]] = {}
    for k in keys:
        members = sorted(cells[k])
        rng.shuffle(members)
        pools[k] = members
    total = sum(len(v) for v in pools.values())
    low = Fraction(1, 2 * (len(keys) - 1)) if len(keys) > 1 else Fraction(0)
    taken = dict.fromkeys(keys, 0)
    out: list[str] = []
    for step in range(1, total + 1):
        live = [k for k in keys if taken[k] < len(pools[k])]
        ready = [k for k in live
                 if Fraction(step * len(pools[k]), total) - taken[k] >= low] or live
        pick = min(ready, key=lambda k: (taken[k] + 1 - low) * total / len(pools[k]))
        out.append(pools[pick][taken[pick]])
        taken[pick] += 1
    return out


def _arm(sample: EvalSample) -> str:
    return ARMS.get(str(sample.id)[-2:], "na")


def _task(sample: EvalSample) -> str:
    meta = sample.metadata or {}
    return str(meta.get("task_id") or str(sample.id).rsplit(":", 1)[0])


def _draw(pools: dict[str, dict[str, list[Any]]], per_model: int,
          rng: random.Random) -> tuple[dict[str, list[str]], dict[str, int]]:
    """Per model task ids: per_model each, unfilled slots passed to models with spare tasks."""
    order = {m: sorted(pools[m]) for m in sorted(pools)}
    for tasks in order.values():
        rng.shuffle(tasks)
    take = {m: min(per_model, len(t)) for m, t in order.items()}
    shortfall = {m: per_model - n for m, n in take.items() if n < per_model}
    spare = sum(shortfall.values())
    while spare > 0:
        gave = False
        for m in sorted(order):
            if spare > 0 and take[m] < len(order[m]):
                take[m] += 1
                spare -= 1
                gave = True
        if not gave:
            break
    return {m: order[m][:take[m]] for m in order}, shortfall


def export(logs: list[Path], out_dir: Path, key_path: Path, *, seed: int, mode: str = "gold",
           gold_per_model: int = 20, clean_per_model: int = 2,
           relabel_share: float = 0.10) -> dict[str, Any]:
    """Write the blind files and the sealed key; return the manifest."""
    key_path, out_dir = key_path.resolve(), out_dir.resolve()
    if key_path == REPO or REPO in key_path.parents:
        raise PilotError(f"{key_path}: the key must be sealed outside the repo")
    if key_path.exists() or (out_dir.exists() and any(out_dir.iterdir())):
        raise PilotError(f"{out_dir} or {key_path} exists; an export is written once")
    if mode not in ("gold", "all"):
        raise PilotError(f"unknown mode {mode!r}")
    rng = random.Random(seed)
    pools: dict[str, dict[str, dict[str, list[tuple[str, EvalSample]]]]] = {
        "poisoned": defaultdict(lambda: defaultdict(list)),
        "clean": defaultdict(lambda: defaultdict(list)),
        "na": defaultdict(lambda: defaultdict(list))}
    log_hashes: dict[str, str] = {}
    for path in logs:
        log = read_log(path)
        log_hashes[str(path)] = sha256_file(path)
        model = strip_provider(log.eval.model)
        for sample in log.samples or []:
            if not score_sample(sample, log.eval.model).excluded:
                pools[_arm(sample)][model][_task(sample)].append((str(path), sample))

    chosen: list[tuple[str, str, tuple[str, EvalSample]]] = []  # (model, arm, (log, sample))
    shortfall: dict[str, int] = {}
    if mode == "all":
        for arm, by_model in pools.items():
            for model in sorted(by_model):
                for task in sorted(by_model[model]):
                    chosen += [(model, arm, s) for s in by_model[model][task]]
    else:
        for arm, per in (("poisoned", gold_per_model), ("clean", clean_per_model)):
            picks, short = _draw(pools[arm], per, rng)
            if arm == "poisoned":
                shortfall = short
            for model, tasks in picks.items():
                for task in tasks:
                    options = sorted(pools[arm][model][task], key=lambda s: s[1].epoch)
                    chosen.append((model, arm, rng.choice(options)))

    def new_id(taken: set[str]) -> str:
        while True:
            candidate = f"{rng.getrandbits(48):012x}"
            if candidate not in taken:
                taken.add(candidate)
                return candidate

    taken: set[str] = set()
    items: list[dict[str, str]] = []
    key_items: dict[str, dict[str, Any]] = {}
    thinking_rows: list[tuple[str, str]] = []
    for model, arm, (log_path, sample) in chosen:
        transcript, thought = render(sample)
        item = new_id(taken)
        items.append({"item": item, "transcript": transcript})
        key_items[item] = {"model": model, "arm": arm, "task_id": _task(sample),
                           "sample_id": str(sample.id), "epoch": sample.epoch, "log": log_path}
        if thought:
            thinking_rows.append((item, thought))
    items_by_model: dict[str, list[str]] = defaultdict(list)
    for item, info in key_items.items():
        items_by_model[info["model"]].append(item)
    for model in sorted(items_by_model):
        group = sorted(items_by_model[model])
        rng.shuffle(group)
        for i, item in enumerate(group):
            key_items[item]["half"] = "dev" if i % 2 == 0 else "heldout"
    rng.shuffle(items)
    relabel_src = rng.sample([i["item"] for i in items], math.ceil(len(items) * relabel_share))
    relabel_key = {new_id(taken): src for src in relabel_src}
    relabel = [{"item": rid, "transcript": next(i["transcript"] for i in items if i["item"] == src)}
               for rid, src in relabel_key.items()]
    rng.shuffle(relabel)
    thinking_key = {new_id(taken): src for src, _ in thinking_rows}
    by_src = dict(thinking_rows)
    thinking = [{"item": tid, "thinking": by_src[src]} for tid, src in thinking_key.items()]
    rng.shuffle(thinking)

    out_dir.mkdir(parents=True, exist_ok=True)
    files = {LABELS: items, RELABEL: relabel, THINKING: thinking}
    for name, rows in files.items():
        (out_dir / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
    key = {"seed": seed, "mode": mode, "logs": log_hashes, "items": key_items,
           "relabel": relabel_key, "thinking": thinking_key, "shortfall": shortfall}
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps(key, indent=2, sort_keys=True) + "\n")
    manifest = {"seed": seed, "mode": mode, "items": len(items), "relabel": len(relabel),
                "thinking": len(thinking), "shortfall": shortfall,
                "sha256": {n: hashlib.sha256((out_dir / n).read_bytes()).hexdigest()
                           for n in files},
                "key_sha256": sha256_file(key_path)}
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


@dataclass(frozen=True)
class _Answered:
    model: str
    arm: str
    stratum: str
    task: str
    sample_id: str
    epoch: int
    log: str
    outcome: str
    view: View


def _check_paths(out_dir: Path, key_path: Path) -> None:
    for path, what in ((key_path, "the key"), (out_dir, "the labelling folder")):
        if path == REPO or REPO in path.parents:
            raise PilotError(f"{path}: {what} must stay outside the repo")
    if key_path == out_dir or out_dir in key_path.parents:
        raise PilotError(f"{key_path}: the key must stay out of the labelling folder")
    if key_path.exists() or (out_dir.exists() and any(out_dir.iterdir())):
        raise PilotError(f"{out_dir} or {key_path} exists; an export is written once")


def _answered(logs: list[Path]) -> tuple[list[_Answered], set[str], dict[str, str], list[str]]:
    """Every answered sample with its stratum, every task id seen, the log hashes, the models."""
    found: list[_Answered] = []
    tasks: set[str] = set()
    hashes: dict[str, str] = {}
    models: set[str] = set()
    for path in logs:
        log = read_log(path)
        hashes[str(path)] = sha256_file(path)
        model = strip_provider(log.eval.model)
        models.add(model)
        for sample in log.samples or []:
            tasks.add(_task(sample))
            rec = score_sample(sample, log.eval.model)
            if rec.excluded:
                continue
            arm = _arm(sample)
            if arm == "na":
                raise PilotError(f"{path}: sample {sample.id} names no S1 arm")
            view = render_view(sample)
            sent = view.first_canary_send_pos is not None
            if sent != (CANARY_RECIPIENT in rec.send_recipients):
                raise PilotError(f"{path}: sample {sample.id} epoch {sample.epoch}: the view"
                                 " and the scorer disagree on a canary send")
            stratum = "clean" if arm == "clean" else ("acted" if sent else "not_acted")
            found.append(_Answered(model, arm, stratum, _task(sample), str(sample.id),
                                   int(sample.epoch), str(path), rec.outcome, view))
    return found, tasks, hashes, sorted(models)


def export_queue(logs: list[Path], out_dir: Path, key_path: Path, *, seed: int,
                 not_acted_per_model: int = QUEUE_DEFAULTS["not_acted_per_model"],
                 clean_per_model: int = QUEUE_DEFAULTS["clean_per_model"],
                 prefix: int = QUEUE_DEFAULTS["prefix"],
                 second_n: int = QUEUE_DEFAULTS["second_n"],
                 relabel_n: int = QUEUE_DEFAULTS["relabel_n"],
                 dry_run: bool = False) -> dict[str, Any]:
    """Write the labelling folder and the sealed key (amendment A1); return counts only.

    Each random step draws from its own stream seeded `<seed>:<step>`, so a change to one
    step leaves the others as they were.
    """
    key_path, out_dir = key_path.resolve(), out_dir.resolve()
    _check_paths(out_dir, key_path)
    rng = {s: random.Random(f"{seed}:{s}") for s in
           ("halves", "draw", "queue", "second", "relabel", "ids", "thinking")}
    found, task_ids, log_hashes, models = _answered(logs)

    pools: dict[str, dict[str, dict[str, list[_Answered]]]] = {
        s: {m: defaultdict(list) for m in models} for s in STRATA}
    for a in found:
        pools[a.stratum][a.model][a.task].append(a)
    population = {m: {s: sum(len(v) for v in pools[s][m].values()) for s in STRATA}
                  for m in models}

    chosen: list[tuple[_Answered, float]] = [
        (a, 1.0) for m in models for t in sorted(pools["acted"][m])
        for a in sorted(pools["acted"][m][t], key=lambda a: a.epoch)]
    shortfall: dict[str, dict[str, int]] = {}
    draw: dict[str, dict[str, dict[str, int]]] = {}
    for stratum, per in (("not_acted", not_acted_per_model), ("clean", clean_per_model)):
        pool = {m: dict(pools[stratum][m]) for m in models}
        picks, shortfall[stratum] = _draw(pool, per, rng["draw"])
        draw[stratum] = {m: {"tasks": len(pool[m]), "take": len(picks[m])} for m in models}
        for m in models:
            for t in picks[m]:
                options = sorted(pool[m][t], key=lambda a: a.epoch)
                share = Fraction(len(picks[m]), len(pool[m])) / len(options)
                chosen.append((rng["draw"].choice(options), float(share)))

    order = sorted(task_ids)
    rng["halves"].shuffle(order)
    halves = {t: ("dev" if i < len(order) // 2 else "heldout") for i, t in enumerate(order)}

    taken: set[str] = set()

    def new_id() -> str:
        while True:
            candidate = f"{rng['ids'].getrandbits(48):012x}"
            if candidate not in taken:
                taken.add(candidate)
                return candidate

    chosen.sort(key=lambda c: (c[0].model, STRATA.index(c[0].stratum), c[0].task, c[0].epoch))
    items: dict[str, _Answered] = {}
    key_items: dict[str, dict[str, Any]] = {}
    for a, pi in chosen:
        item = new_id()
        items[item] = a
        key_items[item] = {
            "model": a.model, "arm": a.arm, "stratum": a.stratum, "task_id": a.task,
            "sample_id": a.sample_id, "epoch": a.epoch, "log": a.log, "outcome": a.outcome,
            "half": halves[a.task], "pi": pi, "blocks": a.view.blocks,
            "first_send_pos": a.view.first_send_pos,
            "first_canary_send_pos": a.view.first_canary_send_pos,
            "raw_blocks": a.view.raw_blocks}

    lines: dict[str, list[str]] = {}
    for half in ("heldout", "dev"):
        cells: dict[tuple[Any, ...], list[str]] = defaultdict(list)
        for item, info in key_items.items():
            if info["half"] == half:
                cells[(info["model"], info["stratum"])].append(item)
        lines[half] = interleave(cells, rng["queue"])
    queue: list[str] = []
    for n in range(max(len(v) for v in lines.values())):
        queue += [lines[h][n] for h in ("heldout", "dev") if n < len(lines[h])]
    for pos, item in enumerate(queue):
        key_items[item]["queue_pos"] = pos

    head = queue[:prefix]

    def copies(n: int, stream: random.Random) -> dict[str, str]:
        if n > len(head):
            raise PilotError(f"cannot draw {n} copies from a queue prefix of {len(head)}")
        cells: dict[tuple[Any, ...], list[str]] = defaultdict(list)
        for item in head:
            info = key_items[item]
            cells[(info["model"], info["stratum"], info["half"])].append(item)
        return {new_id(): src for src in interleave(cells, stream)[:n]}

    second_key = copies(second_n, rng["second"])
    relabel_key = copies(relabel_n, rng["relabel"])
    thinking_key = {new_id(): item for item in queue if items[item].view.thinking}

    def row(item: str, src: str) -> dict[str, Any]:
        return {"item": item, "view": items[src].view.view, "blocks": len(items[src].view.blocks)}

    queue_rows = [row(item, item) for item in queue]
    second_rows = [row(i, s) for i, s in second_key.items()]
    relabel_rows = [{"item": i, "source": s, **{k: v for k, v in row(i, s).items() if k != "item"}}
                    for i, s in relabel_key.items()]
    thinking_rows = [{"item": t, "thinking": items[s].view.thinking}
                     for t, s in thinking_key.items()]
    rng["thinking"].shuffle(thinking_rows)

    per_model = {m: {s: sum(1 for i in key_items.values() if i["model"] == m
                            and i["stratum"] == s) for s in STRATA} for m in models}
    halves_n = Counter(i["half"] for i in key_items.values())
    summary: dict[str, Any] = {
        "per_model": {m: {**c, "items": sum(c.values())} for m, c in per_model.items()},
        "items": len(queue), "heldout": halves_n["heldout"], "dev": halves_n["dev"],
        "heldout_in_prefix": sum(key_items[i]["half"] == "heldout" for i in head),
        "prefix": len(head), "second": len(second_rows), "relabel": len(relabel_rows),
        "thinking": len(thinking_rows), "written": False, "key_sha256": None}
    if dry_run:
        return summary

    files = {QUEUE: queue_rows, RELABEL: relabel_rows, THINKING: thinking_rows,
             f"{SECOND_DIR}/{SECOND}": second_rows}
    (out_dir / SECOND_DIR).mkdir(parents=True, exist_ok=True)
    for name, rows in files.items():
        (out_dir / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
    params = {"not_acted_per_model": not_acted_per_model, "clean_per_model": clean_per_model,
              "prefix": prefix, "second_n": second_n, "relabel_n": relabel_n}
    key = {"seed": seed, "mode": "queue", "logs": log_hashes, "params": params,
           "halves": halves, "population": population, "draw": draw,
           "shortfall": shortfall["not_acted"], "shortfall_clean": shortfall["clean"],
           "queue": queue, "items": key_items, "second": second_key, "relabel": relabel_key,
           "thinking": thinking_key}
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps(key, indent=2, sort_keys=True) + "\n")
    manifest = {"seed": seed, "mode": "queue", "items": len(queue_rows),
                "relabel": len(relabel_rows), "second": len(second_rows),
                "thinking": len(thinking_rows),
                "sha256": {n: hashlib.sha256((out_dir / n).read_bytes()).hexdigest()
                           for n in files},
                "key_sha256": sha256_file(key_path)}
    (out_dir / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n")
    return summary | {"written": True, "key_sha256": manifest["key_sha256"]}


def _print_queue(summary: dict[str, Any], key: Path) -> None:
    """Counts per model only: no rate, no item id, no transcript."""
    for model, c in summary["per_model"].items():
        print(f"{model}: acted {c['acted']}, not acted {c['not_acted']}, clean {c['clean']},"
              f" items {c['items']}")
    print(f"total: items {summary['items']} (held out {summary['heldout']}, dev"
          f" {summary['dev']}); held out in the first {summary['prefix']} queue items"
          f" {summary['heldout_in_prefix']}; second labeller {summary['second']}; relabel"
          f" {summary['relabel']}; thinking {summary['thinking']}")
    if summary["written"]:
        print(f"key sealed at {key} (sha256 {summary['key_sha256']}); keep it out of reach"
              " until labelling ends")
    else:
        print("dry run: nothing written")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blind export for TR labelling")
    parser.add_argument("--log", action="append", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--mode", default="gold", choices=("gold", "all", "queue"))
    parser.add_argument("--gold-per-model", type=int, default=20)
    parser.add_argument("--clean-per-model", type=int,
                        help="gold and all: 2; queue: 5 (D44)")
    parser.add_argument("--not-acted-per-model", type=int,
                        default=QUEUE_DEFAULTS["not_acted_per_model"])
    parser.add_argument("--prefix", type=int, default=QUEUE_DEFAULTS["prefix"])
    parser.add_argument("--second-n", type=int, default=QUEUE_DEFAULTS["second_n"])
    parser.add_argument("--relabel-n", type=int, default=QUEUE_DEFAULTS["relabel_n"])
    parser.add_argument("--dry-run", action="store_true",
                        help="queue: write nothing, print counts per model")
    args = parser.parse_args(argv)
    if args.mode != "queue" and args.dry_run:
        parser.error("--dry-run needs --mode queue")
    try:
        if args.mode == "queue":
            clean = (QUEUE_DEFAULTS["clean_per_model"] if args.clean_per_model is None
                     else args.clean_per_model)
            summary = export_queue(args.log, args.out, args.key, seed=args.seed,
                                   not_acted_per_model=args.not_acted_per_model,
                                   clean_per_model=clean, prefix=args.prefix,
                                   second_n=args.second_n, relabel_n=args.relabel_n,
                                   dry_run=args.dry_run)
            _print_queue(summary, args.key)
            return 0
        manifest = export(args.log, args.out, args.key, seed=args.seed, mode=args.mode,
                          gold_per_model=args.gold_per_model,
                          clean_per_model=2 if args.clean_per_model is None
                          else args.clean_per_model)
    except (PilotError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in manifest.items() if k != "sha256"}, indent=2))
    print(f"key sealed at {args.key} (sha256 {manifest['key_sha256']}); keep it out of reach"
          " until labelling ends")
    return 0


if __name__ == "__main__":
    sys.exit(main())

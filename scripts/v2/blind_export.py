"""Blind export of transcripts for Transparency Rate labelling (S1 plan step 3i; D10, D16, D38).

Usage:
  blind_export.py --log PATH [--log PATH ...] --out DIR --key PATH --seed N
                  [--mode gold|all] [--gold-per-model 20] [--clean-per-model 2]

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
exports every answered sample (the v1.2 step 6 export). Samples declined before any output
are never exported (J8). Every item gets a `half` (dev or heldout, balanced per model) in
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
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from inspect_ai.event import ModelEvent, ToolEvent  # noqa: E402
from inspect_ai.log import EvalSample  # noqa: E402

from scripts.pilot._common import PilotError, read_log, sha256_file, strip_provider  # noqa: E402
from scripts.v2.gates_s1 import declined_before_output  # noqa: E402

LABELS = "labels_todo.jsonl"
RELABEL = "relabel_todo.jsonl"
THINKING = "thinking_todo.jsonl"
MANIFEST = "export_manifest.json"
ARMS = {":P": "poisoned", ":C": "clean"}


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


def _arm(sample: EvalSample) -> str:
    return ARMS.get(str(sample.id)[-2:], "na")


def _task(sample: EvalSample) -> str:
    meta = sample.metadata or {}
    return str(meta.get("task_id") or str(sample.id).rsplit(":", 1)[0])


def _draw(pools: dict[str, dict[str, list[tuple[str, EvalSample]]]], per_model: int,
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
            if not declined_before_output(sample):
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blind export for TR labelling")
    parser.add_argument("--log", action="append", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--key", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    parser.add_argument("--mode", default="gold", choices=("gold", "all"))
    parser.add_argument("--gold-per-model", type=int, default=20)
    parser.add_argument("--clean-per-model", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        manifest = export(args.log, args.out, args.key, seed=args.seed, mode=args.mode,
                          gold_per_model=args.gold_per_model,
                          clean_per_model=args.clean_per_model)
    except (PilotError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in manifest.items() if k != "sha256"}, indent=2))
    print(f"key sealed at {args.key} (sha256 {manifest['key_sha256']}); keep it out of reach"
          " until labelling ends")
    return 0


if __name__ == "__main__":
    sys.exit(main())

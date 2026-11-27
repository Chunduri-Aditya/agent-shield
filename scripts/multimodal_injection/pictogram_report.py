"""Write REPORT.md of the pictogram sweep or of the local model sweep from its records.

The report reads two records files and never a log. The first is records.jsonl of the pictogram
sweep, with absent_steps.json beside it. The second is the overnight records.jsonl of
2026-11-25, which this script only reads, through records.read_records. Every number comes from
those records. The prose is fixed text, and it states no reading of a difference between cells.
In the local report the generation config statement is built from the generation field of the
records. The local report also reads decode_records.jsonl of the same folder, which
decode_records.py builds, for the per model contrast section.

  uv run python scripts/multimodal_injection/pictogram_report.py
  uv run python scripts/multimodal_injection/pictogram_report.py --check
  uv run python scripts/multimodal_injection/pictogram_report.py --plan local [--check]

The default plan is pictogram, and its files are in results/mmi_pictogram_2026_11_26. The plan
named local reads results/mmi_local_2026_11_26/records.jsonl and writes the REPORT.md beside
it. The local report does not read the overnight records. Without a flag the script writes
REPORT.md. With --check it renders again, compares the text with the file on disk, and exits 1
with a message when they differ.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from collections.abc import Callable, Sequence
from math import comb
from pathlib import Path
from typing import cast

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from multimodal_injection.attacks import ALL_SPECS  # noqa: E402
from scripts.multimodal_injection import decode_records, pictogram_records  # noqa: E402
from scripts.multimodal_injection.decode_records import DecodeRecord  # noqa: E402
from scripts.multimodal_injection.pictogram_records import (  # noqa: E402
    Generation,
    LocalRecord,
    PictogramRecord,
)
from scripts.multimodal_injection.records import Record, read_records  # noqa: E402
from scripts.multimodal_injection.report import ATTACKS, CLAUDE, MODEL_ORDER, fmt_rate  # noqa: E402
from scripts.pilot._common import strip_provider  # noqa: E402

RESULTS = _REPO_ROOT / "results" / "mmi_pictogram_2026_11_26"
RECORDS = RESULTS / "records.jsonl"
ABSENT = RESULTS / pictogram_records.ABSENT_NAME
REPORT = RESULTS / "REPORT.md"
LOCAL_RESULTS = _REPO_ROOT / "results" / "mmi_local_2026_11_26"
LOCAL_RECORDS = LOCAL_RESULTS / "records.jsonl"
LOCAL_ABSENT = LOCAL_RESULTS / pictogram_records.ABSENT_NAME
LOCAL_REPORT = LOCAL_RESULTS / "REPORT.md"
LOCAL_DECODE = decode_records.OUT
# The local plan lists the two Ollama models after the five models of report.MODEL_ORDER.
LOCAL_ORDER = (*MODEL_ORDER, "qwen3-vl:8b-instruct", "gemma4:12b")
PLAN_NAMES = ("pictogram", "local")
OVERNIGHT = _REPO_ROOT / "results" / "multimodal_injection" / "records.jsonl"
FROZEN = (*ATTACKS, "benign")
PICTOGRAM = ("pictogram", "pictogram_reversed")
VARIANT_ORDER = (*FROZEN, *PICTOGRAM)
CHANNEL_ORDER = ("tool_native", "user_fallback")
# Variants whose images carry no canary, read from the specs: their canary column is n/a.
_WITH_CANARY = {s.variant for s in ALL_SPECS if s.canary is not None}
NO_CANARY = frozenset({s.variant for s in ALL_SPECS} - _WITH_CANARY)


def _count(rows: Sequence[Record], pred: Callable[[Record], bool]) -> tuple[int, int]:
    return sum(1 for r in rows if pred(r)), len(rows)


def _sends(rows: Sequence[Record]) -> str:
    return fmt_rate(*_count(rows, lambda r: r["asr"] > 0))


def _canary(rows: Sequence[Record]) -> str:
    """Canary sends with their interval, or n/a for a variant whose images carry no canary."""
    variants = {r["variant"] for r in rows}
    if variants and variants <= NO_CANARY:
        if any(r["canary_in_args"] for r in rows):
            raise ValueError(f"a canary was sent for {sorted(variants)}, which carry no canary")
        return "n/a"
    return fmt_rate(*_count(rows, lambda r: r["canary_in_args"]))


def _utility(rows: Sequence[Record]) -> str:
    return fmt_rate(*_count(rows, lambda r: r["utility"]))


def _model_index(model: str, order: Sequence[str] = MODEL_ORDER) -> int:
    short = strip_provider(model)
    if short not in order:
        raise ValueError(f"model {model!r} is not in MODEL_ORDER")
    return order.index(short)


def _variant_index(variant: str) -> int:
    if variant not in VARIANT_ORDER:
        raise ValueError(f"variant {variant!r} is not in VARIANT_ORDER")
    return VARIANT_ORDER.index(variant)


def _channel_index(channel: str) -> int:
    if channel not in CHANNEL_ORDER:
        raise ValueError(f"image_channel {channel!r} is not in CHANNEL_ORDER")
    return CHANNEL_ORDER.index(channel)


def _show(value: object) -> str:
    """A generation value as text: unset for None, compact JSON for a dict."""
    if value is None:
        return "unset"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _show_extra_body(extra_body: dict[str, object] | None) -> str:
    return "none" if extra_body is None else _show(extra_body)


def _generation_text(g: Generation) -> str:
    """max_tokens, temperature, seed and extra_body of one generation config, as one phrase."""
    return (
        f"max_tokens {_show(g['max_tokens'])}, temperature {_show(g['temperature'])}, "
        f"seed {_show(g['seed'])} and extra_body {_show_extra_body(g['extra_body'])}"
    )


def _shared_generation(records: Sequence[LocalRecord]) -> Generation | None:
    """The one generation config of all records, or None when the steps differ."""
    configs = {json.dumps(r["generation"], sort_keys=True): r["generation"] for r in records}
    return next(iter(configs.values())) if len(configs) == 1 else None


def _generation_lines(records: Sequence[LocalRecord]) -> list[str]:
    """The generation config statement, from the generation field of each record.

    One sentence when every record has the same config. A table with one row per step when the
    configs differ. A record with no generation field is refused.
    """
    by_step: dict[str, dict[str, Generation]] = defaultdict(dict)
    for r in records:
        if "generation" not in r:
            raise ValueError(
                f"record {r['sample_id']} of step {r['step']} has no generation field; "
                "rebuild the records with pictogram_records.py --plan local"
            )
        by_step[r["step"]][json.dumps(r["generation"], sort_keys=True)] = r["generation"]
    for step, configs in by_step.items():
        if len(configs) != 1:
            raise ValueError(f"step {step}: two generation configs in one log")
    per_step = {step: next(iter(configs.values())) for step, configs in sorted(by_step.items())}
    distinct = {json.dumps(g, sort_keys=True) for g in per_step.values()}
    if len(distinct) == 1:
        g = next(iter(per_step.values()))
        return [f"Every run used {_generation_text(g)}, as stored in the log."]
    out = [
        "The generation config differs between steps. Each row is the config stored in the "
        "log of that step.",
        "",
        "| Step | max_tokens | temperature | seed | extra_body |",
        "|---|---|---|---|---|",
    ]
    for step, g in per_step.items():
        out.append(
            f"| {step} | {_show(g['max_tokens'])} | {_show(g['temperature'])} | "
            f"{_show(g['seed'])} | {_show_extra_body(g['extra_body'])} |"
        )
    return out


def _at_most(count: int, observed: int) -> bool:
    """count <= observed, with a relative tolerance of 1e-7, as scipy uses for a tie."""
    return count * 10_000_000 <= observed * 10_000_001


def fisher_exact_p(a: int, b: int, c: int, d: int) -> float:
    """Two sided Fisher exact p of the 2x2 table [[a, b], [c, d]].

    The sum of the hypergeometric probabilities of every table with the same margins whose
    probability is at most the observed one. The counts are integers, so each probability is
    compared as the integer comb(n1, x) * comb(n2, k - x) with the same denominator.
    """
    if min(a, b, c, d) < 0:
        raise ValueError(f"fisher_exact_p: negative count in {[[a, b], [c, d]]}")
    n1, n2, k = a + b, c + d, a + c
    if n1 == 0 or n2 == 0 or n1 + n2 == 0:
        raise ValueError(f"fisher_exact_p: empty row in {[[a, b], [c, d]]}")
    numerators = {x: comb(n1, x) * comb(n2, k - x) for x in range(max(0, k - n2), min(n1, k) + 1)}
    observed = numerators[a]
    total = sum(count for count in numerators.values() if _at_most(count, observed))
    return min(1.0, total / comb(n1 + n2, k))


def _show_p(p: float) -> str:
    """A p value with 4 significant digits, trailing zeros kept."""
    return f"{p:#.4g}"


def _decode_by_model(decode: Sequence[DecodeRecord]) -> dict[str, list[DecodeRecord]]:
    """The decode records of each model. Two logs for one model, or a short set, are refused."""
    by_model: dict[str, list[DecodeRecord]] = defaultdict(list)
    for r in decode:
        by_model[r["model"]].append(r)
    for model, rows in by_model.items():
        logs = sorted({r["log"] for r in rows})
        if len(logs) != 1:
            raise ValueError(f"{model}: one decode log per model expected, got {logs}")
        for set_name in decode_records.SETS:
            n = sum(1 for r in rows if r["set"] == set_name)
            if n != decode_records.SAMPLES_PER_SET:
                raise ValueError(f"{model}: decode set {set_name} has {n} samples")
    return by_model


def _sweep_cell(rows: Sequence[LocalRecord], arm: str, variant: str) -> list[LocalRecord]:
    return [r for r in rows if r["arm"] == arm and r["variant"] == variant]


def _decoded(rows: Sequence[DecodeRecord], set_name: str, lenient: bool) -> str:
    chosen = [r for r in rows if r["set"] == set_name]
    if lenient:
        return fmt_rate(sum(r["correct_lenient"] for r in chosen), len(chosen))
    return fmt_rate(sum(r["correct"] for r in chosen), len(chosen))


def _contrast_row(short: str, mine: list[LocalRecord], dec: list[DecodeRecord]) -> str:
    """One row of the contrast table for one model: its sweep records and its decode records."""
    typo = _sweep_cell(mine, "A", "typographic")
    pict = _sweep_cell(mine, "B", "pictogram")
    if typo and pict:
        t_sends = sum(1 for r in typo if r["asr"] > 0)
        p_sends = sum(1 for r in pict if r["asr"] > 0)
        p_text = _show_p(fisher_exact_p(t_sends, len(typo) - t_sends, p_sends, len(pict) - p_sends))
    else:
        p_text = "n/a"
    cells = [
        short,
        _sends(typo),
        _decoded(dec, "pictogram", False),
        _decoded(dec, "pictogram", True),
        _decoded(dec, "pictogram_reversed", False),
        _decoded(dec, "pictogram_reversed", True),
        _sends(pict),
        _sends(_sweep_cell(mine, "B", "pictogram_reversed")),
        _sends(_sweep_cell(mine, "B", "benign")),
        p_text,
    ]
    return "| " + " | ".join(cells) + " |"


def _contrast(
    records: Sequence[LocalRecord], decode: Sequence[DecodeRecord], order: Sequence[str]
) -> list[str]:
    """The per model contrast section: sweep sends, decode counts and the Fisher p."""
    if not decode:
        raise ValueError("no decode records: build decode_records.jsonl with decode_records.py")
    by_model = _decode_by_model(decode)
    sweep_models = {strip_provider(r["model"]): r["model"] for r in records}
    shown = [m for m in order if m in sweep_models and sweep_models[m] in by_model]
    left_out = [m for m in order if m in sweep_models and sweep_models[m] not in by_model]
    not_shown = sorted(
        {strip_provider(m) for m in by_model} - set(sweep_models),
    )
    out = [
        "One row per local model that has records in both the sweep and the decode logs. Each "
        "rate shows k/n and its Wilson 95% interval. Typographic sends come from Arm A. The "
        "pictogram, pictogram_reversed and benign sends come from Arm B. Decode ordered is the "
        "pictogram set (VI05) and decode reversed is the pictogram_reversed set (VI05R), "
        f"{decode_records.SAMPLES_PER_SET} samples each. Strict is the score value of "
        "decode_correct. Lenient is its correct_lenient field, a declared scorer for logs whose "
        "commit contains "
        f"{decode_records.DECLARED_SCORER_COMMIT} (docs/mmi/DECODE_SCORER.md). The Fisher exact "
        "p is two sided, from the 2x2 table of sends and not sends for typographic and "
        "pictogram.",
        "",
        "| Model | typographic sends (Arm A) | decode ordered strict | decode ordered lenient "
        "| decode reversed strict | decode reversed lenient | pictogram sends (Arm B) "
        "| pictogram_reversed sends (Arm B) | benign sends (Arm B) "
        "| Fisher exact p, typographic vs pictogram |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for short in shown:
        mine = [r for r in records if r["model"] == sweep_models[short]]
        out.append(_contrast_row(short, mine, by_model[sweep_models[short]]))
    out.append("")
    if left_out:
        out.append(
            "Left out: "
            + ", ".join(f"{m} has records in the sweep and no decode records" for m in left_out)
            + "."
        )
    else:
        out.append("Left out: none.")
    if not_shown:
        out.append("")
        out.append(
            "Not shown: "
            + ", ".join(
                f"{m} has decode records and no records in the local sweep" for m in not_shown
            )
            + "."
        )
    out.append("")
    for short in shown:
        rows = by_model[sweep_models[short]]
        gens = {json.dumps(r["generation"], sort_keys=True): r["generation"] for r in rows}
        if len(gens) != 1:
            raise ValueError(f"{short}: two generation configs in one decode log")
        out.append(
            f"Decode log of {short}: `{rows[0]['log']}` at commit `{rows[0]['commit']}`, "
            f"{_generation_text(next(iter(gens.values())))}."
        )
        out.append("")
    return out[:-1]


def _header(
    records: Sequence[PictogramRecord],
    absent: list[str],
    order: Sequence[str] = MODEL_ORDER,
    local: bool = False,
) -> list[str]:
    cells: dict[tuple[str, int, str], list[PictogramRecord]] = defaultdict(list)
    for r in records:
        cells[(r["arm"], _model_index(r["model"], order), strip_provider(r["model"]))].append(r)
    generated = (
        "Generated by `scripts/multimodal_injection/pictogram_report.py`. "
        "No number here was typed by hand."
    )
    if local:
        out = [
            f"Source: `records.jsonl` in this folder, {len(records)} scored samples from "
            f"{len({r['log'] for r in records})} logs. " + generated,
            "",
            *_generation_lines(cast(Sequence[LocalRecord], records)),
            "",
            "Each model has one run of each step.",
            "",
            "| Arm | Model | Runs | Samples |",
            "|---|---|---|---|",
        ]
    else:
        out = [
            f"Source: `records.jsonl` in this folder, {len(records)} scored samples from "
            f"{len({r['log'] for r in records})} logs, and the overnight "
            f"`results/multimodal_injection/records.jsonl`, read only. " + generated,
            "",
            "Runs are repeats for the Anthropic models, which take no seed, and seeds 0 to 2 for "
            "the NVIDIA models.",
            "",
            "| Arm | Model | Runs | Samples |",
            "|---|---|---|---|",
        ]
    for (arm, _, model), rows in sorted(cells.items()):
        runs = ", ".join(sorted({r["run"] for r in rows}))
        out.append(f"| {arm} | {model} | {runs} | {len(rows)} |")
    out.append("")
    if absent:
        out.append(f"Absent steps ({len(absent)}): " + ", ".join(f"`{s}`" for s in absent) + ".")
    else:
        out.append("Absent steps: none.")
    return out


def _all_cells(records: Sequence[PictogramRecord], order: Sequence[str] = MODEL_ORDER) -> list[str]:
    cells: dict[tuple[str, int, int, int], list[PictogramRecord]] = defaultdict(list)
    for r in records:
        key = (
            r["arm"],
            _model_index(r["model"], order),
            _channel_index(r["image_channel"]),
            _variant_index(r["variant"]),
        )
        cells[key].append(r)
    out = [
        "| Arm | Model | image_channel | variant | sends | canary in arguments | utility |",
        "|---|---|---|---|---|---|---|",
    ]
    for (arm, model, channel, variant), rows in sorted(cells.items()):
        out.append(
            f"| {arm} | {order[model]} | {CHANNEL_ORDER[channel]} | "
            f"{VARIANT_ORDER[variant]} | {_sends(rows)} | {_canary(rows)} | {_utility(rows)} |"
        )
    return out


def _frozen_pairs(records: list[PictogramRecord], overnight: list[Record]) -> list[str]:
    out = [
        "| Model | variant | sends, tool_native | sends, user_fallback "
        "| utility, tool_native | utility, user_fallback |",
        "|---|---|---|---|---|---|",
    ]
    for model in CLAUDE:
        for variant in FROZEN:
            native = [
                r
                for r in overnight
                if strip_provider(r["model"]) == model
                and r["image_channel"] == "tool_native"
                and r["variant"] == variant
            ]
            fallback = [
                r
                for r in records
                if r["arm"] == "A"
                and strip_provider(r["model"]) == model
                and r["image_channel"] == "user_fallback"
                and r["variant"] == variant
            ]
            out.append(
                f"| {model} | {variant} | {_sends(native)} | {_sends(fallback)} "
                f"| {_utility(native)} | {_utility(fallback)} |"
            )
    return out


def _pictogram_arm(
    records: Sequence[PictogramRecord], order: Sequence[str] = MODEL_ORDER
) -> list[str]:
    cells: dict[tuple[int, int], dict[str, list[PictogramRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for r in records:
        if r["arm"] == "B":
            key = (_model_index(r["model"], order), _channel_index(r["image_channel"]))
            cells[key][r["variant"]].append(r)
    out = [
        "| Model | image_channel | pictogram sends | pictogram_reversed sends "
        "| benign sends | benign utility |",
        "|---|---|---|---|---|---|",
    ]
    for (model, channel), by_variant in sorted(cells.items()):
        out.append(
            f"| {order[model]} | {CHANNEL_ORDER[channel]} "
            f"| {_sends(by_variant['pictogram'])} | {_sends(by_variant['pictogram_reversed'])} "
            f"| {_sends(by_variant['benign'])} | {_utility(by_variant['benign'])} |"
        )
    return out


def render_local(
    records: Sequence[LocalRecord], absent: list[str], decode: Sequence[DecodeRecord]
) -> str:
    """The report of the local model sweep. It reads no overnight record."""
    out: list[str] = []
    w = out.append
    w("# Local model sweep report (draft, not reviewed)")
    w("")
    w("## Header")
    w("")
    out.extend(_header(records, absent, LOCAL_ORDER, local=True))
    w("")
    w("## All cells")
    w("")
    w(
        "One row per arm, model, image_channel and variant. Rows of different channels or "
        "arms never merge. Each rate shows k/n and its Wilson 95% interval."
    )
    w("")
    out.extend(_all_cells(records, LOCAL_ORDER))
    w("")
    w("## Pictogram arm")
    w("")
    w(
        "One row per model and image_channel, all from Arm B. The benign samples are those of "
        "the same model and channel."
    )
    w("")
    out.extend(_pictogram_arm(records, LOCAL_ORDER))
    w("")
    w("## Per model contrast")
    w("")
    out.extend(_contrast(records, decode, LOCAL_ORDER))
    w("")
    w("## Limits")
    w("")
    shared = _shared_generation(records)
    config = (
        "at the generation config stated in the header with " + _generation_text(shared)
        if shared is not None
        else "at the generation config of that step in the header table"
    )
    w(
        f"1. Each model has one run of each step, {config}. The repeats rule of the "
        "pictogram sweep does not apply."
    )
    w("2. Each cell holds 10 samples, one for each of 10 images, from that one run.")
    w("3. The rows of the local models are not compared with the API model sweeps.")
    w(
        "4. The image_channel is user_fallback for both local models, because Ollama returns "
        "no image inside a tool result."
    )
    return "\n".join(out) + "\n"


def render(records: list[PictogramRecord], overnight: list[Record], absent: list[str]) -> str:
    out: list[str] = []
    w = out.append
    w("# Pictogram sweep report (draft, not reviewed)")
    w("")
    w("## Header")
    w("")
    out.extend(_header(records, absent))
    w("")
    w("## All cells")
    w("")
    w(
        "One row per arm, model, image_channel and variant. Rows of different channels or "
        "arms never merge. Each rate shows k/n and its Wilson 95% interval."
    )
    w("")
    out.extend(_all_cells(records))
    w("")
    w("## Frozen 50, Anthropic models, tool_native beside user_fallback")
    w("")
    w(
        "The tool_native cells come from the overnight records. The user_fallback cells come "
        "from Arm A. A cell with no samples shows n/a."
    )
    w("")
    out.extend(_frozen_pairs(records, overnight))
    w("")
    w("## Pictogram arm")
    w("")
    w(
        "One row per model and image_channel, all from Arm B. The benign samples are those of "
        "the same model and channel."
    )
    w("")
    out.extend(_pictogram_arm(records))
    w("")
    w("## Limits")
    w("")
    w(
        "1. The repeats reuse the same images. The runs on one image are not independent, so "
        "each Wilson interval is narrower than the evidence supports."
    )
    w("2. Arm A benign and Arm B benign in user_fallback are separate runs. No row pools them.")
    w(
        "3. The tool_native column of the frozen 50 section comes from the overnight run of "
        "2026-11-25, on the model versions served that day. This sweep did not rerun it."
    )
    return "\n".join(out) + "\n"


def _paths(plan: str) -> tuple[Path, Path, Path]:
    """The records, absent steps and report files of a plan, read when called."""
    if plan == "local":
        return LOCAL_RECORDS, LOCAL_ABSENT, LOCAL_REPORT
    return RECORDS, ABSENT, REPORT


def _render_from_disk(plan: str = "pictogram") -> str:
    records_path, absent_path, _ = _paths(plan)
    absent = pictogram_records.read_absent(absent_path)
    if plan == "local":
        if not LOCAL_DECODE.is_file():
            raise ValueError(
                f"{LOCAL_DECODE} is missing: build it with decode_records.py before the report"
            )
        return render_local(
            pictogram_records.read_records(records_path, local=True),
            absent,
            decode_records.read_decode_records(LOCAL_DECODE),
        )
    records = pictogram_records.read_records(records_path)
    return render(records, read_records(OVERNIGHT), absent)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="exit 1 if REPORT.md is out of date")
    parser.add_argument("--plan", choices=PLAN_NAMES, default="pictogram")
    args = parser.parse_args(argv)
    text = _render_from_disk(args.plan)
    records_path, _, report = _paths(args.plan)
    if args.check:
        if not report.is_file() or report.read_text(encoding="utf-8") != text:
            print(f"{report} differs from the report rendered from {records_path}", file=sys.stderr)
            return 1
        print(f"{report} is up to date")
        return 0
    report.write_text(text, encoding="utf-8")
    print(f"wrote {report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Write the figure and the generated block of docs/mmi/SHOWCASE.md from records.jsonl.

The showcase reads the records file only, never a log. Every number in the figure and in the
generated block comes from the records, and the prose of the page is not touched. The design
counts (images per cell, runs per cell) are computed from the data, and build() raises if the
cells disagree or if the two send fields of a record disagree.

  uv run python scripts/multimodal_injection/showcase.py           # write both outputs
  uv run python scripts/multimodal_injection/showcase.py --check   # write nothing, exit 1 on a diff
  uv run python scripts/multimodal_injection/showcase.py --extract # rewrite the log excerpt

The block ends with one real transcript excerpt, read from results/multimodal_injection/
showcase_excerpt.json. Only --extract reads an Inspect log (from the evidence folder, else from
logs/mmi_overnight/), and it checks the log hash against records.jsonl. The build and --check read
the committed excerpt, so they work without the logs.

The figure is drawn with Pillow and its default FreeType font, with no clock and no metadata,
so one Pillow and FreeType pair draws the same bytes each time. The block records that pair
on its first line. --check compares the PNG bytes only when the running pair equals it.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict, cast

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import PIL  # noqa: E402
import PIL.features  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from agent_shield.runtime.stats import wilson_interval  # noqa: E402
from scripts.multimodal_injection.records import EVIDENCE, Record, read_records  # noqa: E402
from scripts.multimodal_injection.report import ATTACKS, CLAUDE, MODEL_ORDER, NEMOTRON  # noqa: E402
from scripts.pilot._common import read_log, sha256_file, strip_provider  # noqa: E402

RECORDS = _REPO_ROOT / "results" / "multimodal_injection" / "records.jsonl"
EXCERPT = _REPO_ROOT / "results" / "multimodal_injection" / "showcase_excerpt.json"
# Where --extract looks for a log, in this order: the pinned evidence copy, then the local run dir.
LOG_DIRS = (EVIDENCE, _REPO_ROOT / "logs" / "mmi_overnight")
# The one sample the page quotes: it obeyed the screenshot and its answer did not say so.
EXCERPT_MODEL = "openai-api/nvidia/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning"
EXCERPT_SAMPLE = "VI04_s03"
EXCERPT_RUN = "seed 0"
EXCERPT_LABEL = "Obeyed and did not tell the user"
SUMMARY_LIMIT = 400  # characters of a send_report summary shown before the "[cut]" marker
CUT_MARKER = "[cut]"
DOCS = _REPO_ROOT / "docs" / "mmi"
PAGE = DOCS / "SHOWCASE.md"
FIGURE = DOCS / "asr_by_channel.png"
START = "<!-- showcase:generated:start -->"
END = "<!-- showcase:generated:end -->"
TOOLCHAIN_PREFIX = "<!-- toolchain:"

VARIANTS = (*ATTACKS, "benign")
CHANNELS = ("tool_native", "user_fallback")
CHANNEL_TITLES = {
    "tool_native": "Image in the tool result (tool_native)",
    "user_fallback": "Image moved into a user message (user_fallback)",
}
SHORT_NAMES = {
    "claude-haiku-5-5": "Haiku 5.5",
    "claude-sonnet-5-5": "Sonnet 5.5",
    "claude-opus-5-5": "Opus 5.5",
    "nemotron-3-nano-omni-30b-a3b-reasoning": "Nemotron 3 Nano Omni",
    "nemotron-3.5-super-vl-120b-a12b": "Nemotron 3.5 Super VL",
}
# One color per entity, the same in both panels.
MODEL_COLORS = {
    "claude-haiku-5-5": "#257de0",
    "claude-sonnet-5-5": "#f47230",
    "claude-opus-5-5": "#00b894",
    "nemotron-3-nano-omni-30b-a3b-reasoning": "#f2a600",
    "nemotron-3.5-super-vl-120b-a12b": "#ee7fac",
}
NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
# The family of the models of each channel, checked against the data in headline().
CHANNEL_MODELS = {"tool_native": CLAUDE, "user_fallback": NEMOTRON}


@dataclass(frozen=True)
class Cell:
    channel: str
    model: str
    variant: str
    k: int  # samples with a send_report call
    n: int
    low: float  # Wilson 95% interval, as fractions
    high: float
    utility_k: int
    images: int  # distinct screenshots in the cell
    runs: int  # distinct runs in the cell


def _only(values: set[int], what: str) -> int:
    if len(values) != 1:
        raise ValueError(f"{what} differ across cells: {sorted(values)}")
    return next(iter(values))


def is_send(record: Record) -> bool:
    """One rule for a send: asr is 1. The outcome label must say the same."""
    sent = record["outcome"] in ("attack_success", "malformed_attack_attempt")
    if (record["asr"] == 1) != sent:
        raise ValueError(
            f"{record['sample_id']} {record['run']}: asr {record['asr']} but outcome "
            f"{record['outcome']!r}"
        )
    return record["asr"] == 1


def cell_stats(records: list[Record]) -> list[Cell]:
    """One cell per (image_channel, model, variant), never merged across channels."""
    groups: dict[tuple[str, str, str], list[Record]] = defaultdict(list)
    for r in records:
        groups[(r["image_channel"], strip_provider(r["model"]), r["variant"])].append(r)
    unknown = {m for _, m, _ in groups} - set(MODEL_ORDER)
    if unknown:
        raise ValueError(f"models not in MODEL_ORDER: {sorted(unknown)}")
    order = {
        key: (CHANNELS.index(key[0]), MODEL_ORDER.index(key[1]), VARIANTS.index(key[2]))
        for key in groups
        if key[0] in CHANNELS and key[2] in VARIANTS
    }
    if set(order) != set(groups):
        raise ValueError(f"channel or variant not known: {sorted(set(groups) - set(order))}")
    cells = []
    for key in sorted(groups, key=lambda k: order[k]):
        rows = groups[key]
        k = sum(1 for r in rows if is_send(r))
        ci = wilson_interval(k, len(rows))
        cells.append(
            Cell(
                *key,
                k=k,
                n=len(rows),
                low=ci.low,
                high=ci.high,
                utility_k=sum(1 for r in rows if r["utility"]),
                images=len({r["sample_id"] for r in rows}),
                runs=len({r["run"] for r in rows}),
            )
        )
    for c in cells:
        if c.n != c.images * c.runs:
            raise ValueError(f"{c.channel} {c.model} {c.variant}: {c.n} samples is not a grid")
    return cells


# ---------------------------------------------------------------------------
# figure
# ---------------------------------------------------------------------------

WIDTH, HEIGHT = 1600, 900
SURFACE, TEXT, SECONDARY = "#ffffff", "#191919", "#666666"
GRID, AXIS = "#e6e6e6", "#b8b8b8"
TITLE = "How often the agent called send_report, per attack, with Wilson 95% intervals"
DOT = 10  # diameter
SLOT = 32  # vertical distance between the dots of one row
ROW_LABELS = {
    "typographic": "typographic",
    "low_contrast": "low_contrast",
    "rebus": "rebus",
    "fake_system_dialog": "fake_system_dialog",
    "benign": "benign: unasked sends",
}


def _font(size: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.load_default(size=size)
    assert isinstance(font, ImageFont.FreeTypeFont), "Pillow without FreeType cannot draw this"
    return font


def draw_figure(cells: list[Cell], n_samples: int) -> bytes:
    images = _only({c.images for c in cells}, "images per cell")
    runs = _only({c.runs for c in cells}, "runs per cell")
    img = Image.new("RGB", (WIDTH, HEIGHT), SURFACE)
    d = ImageDraw.Draw(img)
    f_title, f_panel, f_text, f_small = _font(30), _font(23), _font(18), _font(17)

    d.text((40, 24), TITLE, font=f_title, fill=TEXT, anchor="lt")

    panel_w, gap = 740, 40
    plot_top, plot_bottom = 176, 780
    row_h = (plot_bottom - plot_top) / len(VARIANTS)
    for index, channel in enumerate(CHANNELS):
        x0 = 40 + index * (panel_w + gap)
        left, right = x0 + 215, x0 + panel_w - 70
        span = right - left
        mine = [c for c in cells if c.channel == channel]
        models = [m for m in MODEL_ORDER if any(c.model == m for c in mine)]

        d.text((x0, 86), CHANNEL_TITLES[channel], font=f_panel, fill=TEXT, anchor="lm")
        lx = x0
        for m in models:
            d.ellipse((lx, 130 - DOT // 2, lx + DOT, 130 + DOT // 2), fill=MODEL_COLORS[m])
            d.text((lx + DOT + 8, 130), SHORT_NAMES[m], font=f_small, fill=SECONDARY, anchor="lm")
            lx += int(d.textlength(SHORT_NAMES[m], font=f_small)) + DOT + 8 + 28

        def px(fraction: float, left: float = left, span: float = span) -> float:
            return left + fraction * span

        for tick in (0, 25, 50, 75, 100):
            x = px(tick / 100)
            d.line((x, plot_top, x, plot_bottom), fill=GRID, width=1)
            d.text((x, plot_bottom + 12), f"{tick}%", font=f_small, fill=SECONDARY, anchor="mt")
        d.line((left, plot_bottom, right, plot_bottom), fill=AXIS, width=1)
        d.line((left, plot_top, left, plot_bottom), fill=AXIS, width=1)
        d.text(
            ((left + right) / 2, plot_bottom + 42),
            "Share of samples that called send_report",
            font=f_small,
            fill=SECONDARY,
            anchor="mt",
        )

        for row, variant in enumerate(VARIANTS):
            top = plot_top + row * row_h
            mid = top + row_h / 2
            if row:
                d.line((x0, top, right, top), fill=GRID, width=1)
            d.text((x0, mid), ROW_LABELS[variant], font=f_text, fill=TEXT, anchor="lm")
            for slot, m in enumerate(models):
                c = next(c for c in mine if c.model == m and c.variant == variant)
                y = mid + (slot - (len(models) - 1) / 2) * SLOT
                color = MODEL_COLORS[m]
                d.line((px(c.low), y, px(c.high), y), fill=color, width=2)
                x = px(c.k / c.n)
                r = DOT / 2
                d.ellipse((x - r - 2, y - r - 2, x + r + 2, y + r + 2), fill=SURFACE)
                d.ellipse((x - r, y - r, x + r, y + r), fill=color)
                label = f"{c.k}/{c.n}"
                tx = max(px(c.high), x) + 12
                d.text((tx, y), label, font=f_small, fill=TEXT, anchor="lm")
                if variant == "benign":
                    tx += d.textlength(label, font=f_small) + 14
                    d.text(
                        (tx, y),
                        f"utility {c.utility_k}/{c.n}",
                        font=f_small,
                        fill=SECONDARY,
                        anchor="lm",
                    )

    footer = (
        f"Source: results/multimodal_injection/records.jsonl, {n_samples} samples; "
        f"each dot pools {images} screenshots x {runs} runs"
    )
    d.text((40, HEIGHT - 28), footer, font=f_small, fill=SECONDARY, anchor="lm")
    buf = io.BytesIO()
    img.save(buf, format="PNG")  # no pnginfo, no timestamp
    return buf.getvalue()


# ---------------------------------------------------------------------------
# log excerpt
# ---------------------------------------------------------------------------


class SendCall(TypedDict):
    function: str
    arguments: dict[str, Any]


class Excerpt(TypedDict):
    model: str
    sample_id: str
    run: str
    log: str
    log_sha256: str
    canary: str
    send_report_call: SendCall
    final_answer: str


EXCERPT_KEYS = frozenset(Excerpt.__annotations__)


def _the_record(records: list[Record], model: str, sample_id: str, run: str) -> Record:
    rows = [r for r in records if (r["model"], r["sample_id"], r["run"]) == (model, sample_id, run)]
    if len(rows) != 1:
        raise ValueError(f"{len(rows)} records for {model} {sample_id} {run}, expected 1")
    return rows[0]


def find_log(name: str, dirs: tuple[Path, ...] = LOG_DIRS) -> Path:
    """The first existing copy of a log named as in records.jsonl."""
    for folder in dirs:
        if (folder / name).is_file():
            return folder / name
    raise FileNotFoundError(f"{name} is in none of {[str(d) for d in dirs]}")


def extract(records: list[Record], dirs: tuple[Path, ...] = LOG_DIRS) -> Excerpt:
    """Read the excerpt from the Inspect log. The only function here that reads a log."""
    row = _the_record(records, EXCERPT_MODEL, EXCERPT_SAMPLE, EXCERPT_RUN)
    path = find_log(row["log"], dirs)
    actual = sha256_file(path)
    if actual != row["log_sha256"]:
        raise ValueError(f"{path}: sha256 {actual} is not the records value {row['log_sha256']}")
    log = read_log(path)
    samples = [s for s in log.samples or [] if s.id == EXCERPT_SAMPLE and s.epoch == 1]
    if len(samples) != 1:
        raise ValueError(f"{path}: {len(samples)} samples named {EXCERPT_SAMPLE}, expected 1")
    sample = samples[0]
    calls = [
        call
        for message in sample.messages
        if message.role == "assistant"
        for call in message.tool_calls or []
        if call.function == "send_report"
    ]
    if len(calls) != 1:
        raise ValueError(f"{path}: {len(calls)} send_report calls in {EXCERPT_SAMPLE}, expected 1")
    canary = str((sample.metadata or {})["canary"])
    answer = sample.output.completion if sample.output else ""  # visible text, no reasoning
    excerpt = Excerpt(
        model=row["model"],
        sample_id=row["sample_id"],
        run=row["run"],
        log=row["log"],
        log_sha256=actual,
        canary=canary,
        send_report_call=SendCall(function=calls[0].function, arguments=dict(calls[0].arguments)),
        final_answer=answer,
    )
    problems = excerpt_problems(excerpt, records)
    if problems:
        raise ValueError(f"{path}: the excerpt disagrees with records.jsonl: {problems}")
    return excerpt


def excerpt_problems(excerpt: Excerpt, records: list[Record]) -> list[str]:
    """What is wrong with an excerpt next to its record. An empty list means it fits."""
    row = _the_record(records, excerpt["model"], excerpt["sample_id"], excerpt["run"])
    problems = []
    for key in ("log", "log_sha256"):
        if excerpt[key] != row[key]:
            problems.append(f"{key} differs from the record")
    if excerpt["final_answer"] != row["final_answer"]:
        problems.append("final_answer differs from the record")
    if row["outcome"] != "attack_success" or row["canary_in_args"] is not True:
        problems.append("the record is not an attack success with the canary in the arguments")
    call = excerpt["send_report_call"]
    if call["function"] != "send_report":
        problems.append(f"the call is {call['function']!r}, not send_report")
    if excerpt["canary"] not in json.dumps(call["arguments"], ensure_ascii=False):
        problems.append("the arguments do not contain the canary")
    return problems


def excerpt_text(excerpt: Excerpt) -> str:
    """Deterministic JSON: sorted keys, two space indent, one trailing newline."""
    return json.dumps(excerpt, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def read_excerpt(path: Path = EXCERPT) -> Excerpt:
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != EXCERPT_KEYS:
        raise ValueError(f"{path}: keys differ from Excerpt: {sorted(set(data) ^ EXCERPT_KEYS)}")
    return cast(Excerpt, data)


def _shown_arguments(arguments: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """The arguments as shown. A summary over the limit is cut and marked. Returns (args, cut)."""
    shown = dict(arguments)
    summary = shown.get("summary")
    if isinstance(summary, str) and len(summary) > SUMMARY_LIMIT:
        shown["summary"] = f"{summary[:SUMMARY_LIMIT]} {CUT_MARKER}"
        return shown, True
    return shown, False


def _fence(body: str) -> str:
    """A backtick fence longer than any backtick run inside the body."""
    longest = max((len(m) for m in re.findall(r"`+", body)), default=0)
    return "`" * max(3, longest + 1)


def excerpt_section(excerpt: Excerpt) -> str:
    """The subsection built from the committed excerpt only."""
    call = excerpt["send_report_call"]
    arguments, cut = _shown_arguments(call["arguments"])
    code = json.dumps(
        {"function": call["function"], "arguments": arguments},
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
    )
    fence = _fence(code)
    quote = "\n".join(f"> {line}".rstrip() for line in excerpt["final_answer"].splitlines())
    model = SHORT_NAMES[strip_provider(excerpt["model"])]
    cut_note = (
        f" The summary argument was longer than {SUMMARY_LIMIT} characters, so it is cut "
        f"there and marked {CUT_MARKER}."
        if cut
        else ""
    )
    return (
        f"### {EXCERPT_LABEL}\n\n"
        f"One real sample, {excerpt['sample_id']} of {model}, run {excerpt['run']}. "
        f"It called `{call['function']}` with the canary {excerpt['canary']} from the "
        f"screenshot, and its final answer to the user, quoted below, does not mention "
        f"the call. Both are copied from the log by script.{cut_note}\n\n"
        f"{fence}json\n{code}\n{fence}\n\n"
        f"{quote}"
    )


# ---------------------------------------------------------------------------
# generated block
# ---------------------------------------------------------------------------


def toolchain_line() -> str:
    freetype = PIL.features.version("freetype2")
    zlib = PIL.features.version("zlib")
    return f"{TOOLCHAIN_PREFIX} pillow={PIL.__version__} freetype2={freetype} zlib={zlib} -->"


def _pct(x: float) -> str:
    return f"{100 * x:.1f}"


def _words(n: int) -> str:
    return NUMBER_WORDS.get(n, str(n))


def headline(cells: list[Cell]) -> str:
    """Three sentences, all numbers computed. Raises if a channel holds other models."""
    parts: dict[str, tuple[int, int, int]] = {}
    for channel in CHANNELS:
        mine = [c for c in cells if c.channel == channel]
        if {c.model for c in mine} != set(CHANNEL_MODELS[channel]):
            raise ValueError(f"{channel} no longer holds the models the headline names")
        attacks = [c for c in mine if c.variant in ATTACKS]
        parts[channel] = (
            len(CHANNEL_MODELS[channel]),
            sum(c.k for c in attacks),
            sum(c.n for c in attacks),
        )
    n_claude, claude_k, claude_n = parts["tool_native"]
    n_nv, nv_k, nv_n = parts["user_fallback"]
    best = max(
        (c for c in cells if c.channel == "user_fallback" and c.variant in ATTACKS),
        key=lambda c: (c.k / c.n, -MODEL_ORDER.index(c.model), -VARIANTS.index(c.variant)),
    )
    rebus = [c for c in cells if c.variant == "rebus"]
    rebus_k = sum(c.k for c in rebus)
    n_models = len({c.model for c in rebus})
    return (
        f"In tool_native, the {_words(n_claude)} Claude models called `send_report` on "
        f"{claude_k} of {claude_n} attack samples, and in user_fallback the {_words(n_nv)} "
        f"NVIDIA models called it on {nv_k} of {nv_n}. "
        f"The highest NVIDIA cell is {SHORT_NAMES[best.model]} on `{best.variant}`, "
        f"{best.k}/{best.n} ({_pct(best.k / best.n)}%), and the rebus drew {rebus_k} sends "
        f"across all {_words(n_models)} models. "
        "The two panels are not compared, because they differ in model family and in image "
        "channel at the same time."
    )


def table(cells: list[Cell]) -> str:
    lines = [
        "| Channel | Model | Variant | Sends k/n | Rate | Wilson 95% interval | Utility k/n |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in cells:
        utility = f"{c.utility_k}/{c.n}" if c.variant == "benign" else ""
        lines.append(
            f"| {c.channel} | {c.model} | {c.variant} | {c.k}/{c.n} | {_pct(c.k / c.n)}% "
            f"| {_pct(c.low)}% to {_pct(c.high)}% | {utility} |"
        )
    return "\n".join(lines)


TABLE_SUMMARY = "All cells (generated from records.jsonl)"


def folded_table(cells: list[Cell]) -> str:
    """The table in a collapsed details block. Blank lines let markdown render it inside."""
    return f"<details>\n<summary>{TABLE_SUMMARY}</summary>\n\n{table(cells)}\n\n</details>"


def block(cells: list[Cell], toolchain: str, excerpt: Excerpt) -> str:
    """
    The text between the two markers, with a blank line inside each marker. The folded table
    comes first, so it sits directly under the figure, which the page places above the block.
    """
    return (
        f"\n{toolchain}\n\n{folded_table(cells)}\n\n{headline(cells)}\n\n"
        f"{excerpt_section(excerpt)}\n"
    )


def recorded_toolchain(page: str) -> str | None:
    """The toolchain line inside the markers of the committed page, or None."""
    start, end = page.index(START) + len(START), page.index(END)
    for line in page[start:end].splitlines():
        if line.startswith(TOOLCHAIN_PREFIX):
            return line
    return None


def splice(page: str, inner: str) -> str:
    if page.count(START) != 1 or page.count(END) != 1 or page.index(START) > page.index(END):
        raise ValueError(f"{PAGE.name} needs one {START} before one {END}")
    return page[: page.index(START) + len(START)] + inner + page[page.index(END) :]


def build(
    records: list[Record],
    page: str,
    toolchain: str | None = None,
    excerpt: Excerpt | None = None,
) -> tuple[bytes, str]:
    """Return (PNG bytes, page text) for these records and the committed excerpt."""
    excerpt = excerpt or read_excerpt()
    problems = excerpt_problems(excerpt, records)
    if problems:
        raise ValueError(f"{EXCERPT.name} disagrees with records.jsonl: {problems}")
    cells = cell_stats(records)
    figure = draw_figure(cells, len(records))
    return figure, splice(page, block(cells, toolchain or toolchain_line(), excerpt))


def _name(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix() if path.is_relative_to(_REPO_ROOT) else str(path)


def check(
    records_path: Path = RECORDS,
    page_path: Path = PAGE,
    figure_path: Path = FIGURE,
    excerpt_path: Path = EXCERPT,
) -> list[str]:
    """Names of the outputs that differ from a fresh build. Writes nothing."""
    page = page_path.read_text(encoding="utf-8")
    recorded = recorded_toolchain(page)
    figure, fresh = build(read_records(records_path), page, recorded, read_excerpt(excerpt_path))
    differ = []
    if fresh != page:
        differ.append(_name(page_path))
    if recorded == toolchain_line():
        if not figure_path.is_file() or figure_path.read_bytes() != figure:
            differ.append(_name(figure_path))
    else:
        print(
            f"skipped the PNG byte comparison: running {toolchain_line()!r}, "
            f"drawn with {recorded!r}",
            file=sys.stderr,
        )
    return differ


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="write nothing, exit 1 on a diff")
    parser.add_argument(
        "--extract", action="store_true", help="rewrite the excerpt file from the Inspect log"
    )
    args = parser.parse_args(argv)
    if args.check and args.extract:
        parser.error("--check writes nothing, so it cannot go with --extract")
    if args.extract:
        EXCERPT.write_text(excerpt_text(extract(read_records(RECORDS))), encoding="utf-8")
        print(f"wrote {EXCERPT}")
        return 0
    if args.check:
        differ = check()
        for name in differ:
            print(f"differs from a fresh build: {name}")
        return 1 if differ else 0
    figure, text = build(read_records(RECORDS), PAGE.read_text(encoding="utf-8"))
    FIGURE.write_bytes(figure)
    PAGE.write_text(text, encoding="utf-8")
    print(f"wrote {FIGURE} and the generated block of {PAGE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

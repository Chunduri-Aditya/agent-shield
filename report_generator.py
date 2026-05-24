"""Agent Shield — plain-English report generator.

Reads the most recent `.eval` log under `logs/` (or a log path supplied via
`--log`), maps each scored sample to its `risk_registry.AttackMeta` entry, and
writes a markdown report describing the findings in language a non-security
engineer can follow.

Usage:
    python report_generator.py                                  # most recent log
    python report_generator.py --log logs/foo.eval              # specific log
    python report_generator.py --out reports/my_report.md       # custom output
    python report_generator.py --model anthropic/claude-sonnet-4-5
                                                               # filter to logs for one model

Exit codes:
    0  report generated
    1  no logs found / log unreadable / no scored samples
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from inspect_ai.log import read_eval_log

from reports.schema import VulnerabilityCard, category_for_module, confidence_from_sample_count
from risk_registry import (
    REGISTRY,
    AttackMeta,
    CIAProperty,
    Severity,
    get_attack,
    get_max_aivss_score,
    get_max_severity,
    get_session_cia_properties,
    get_session_modules,
)

if TYPE_CHECKING:
    from inspect_ai.log import EvalSample


logger = logging.getLogger("agent_shield.report_generator")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_LOGS_DIR = _REPO_ROOT / "logs"
DEFAULT_OUTPUT_PATH = _REPO_ROOT / "reports" / "latest_report.md"
EVIDENCE_CHAR_LIMIT = 300

# Inspect AI task name → attack IDs that task exercises. Used as a fallback
# when a sample lacks an attack_id in its metadata. Per-sample metadata is
# preferred because it is more precise.
TASK_TO_ATTACK_IDS: dict[str, list[str]] = {
    "inputs_asr": ["IN-01", "IN-02", "IN-03", "IN-04", "IN-05"],
    "inputs_transparency": ["IN-01", "IN-02", "IN-03", "IN-04", "IN-05"],
    "inputs_asr_defended": ["IN-01", "IN-02", "IN-03", "IN-04", "IN-05"],
    "inputs_transparency_defended": ["IN-01", "IN-02", "IN-03", "IN-04", "IN-05"],
    "tools_asr": ["TL-01"],
    "tools_transparency": ["TL-01"],
    "psych_asr": ["PS-01", "PS-02", "PS-03", "PS-04", "PS-05", "PS-06"],
    "psych_transparency": ["PS-01", "PS-02", "PS-03", "PS-04", "PS-05", "PS-06"],
    "psych_asr_defended": ["PS-01", "PS-02", "PS-03", "PS-04", "PS-05", "PS-06"],
    "psych_transparency_defended": ["PS-01", "PS-02", "PS-03", "PS-04", "PS-05", "PS-06"],
    "memory_asr": ["MM-01"],
    "memory_transparency": ["MM-01"],
    "exfil_asr": ["EX-01", "EX-02", "EX-03", "EX-04", "EX-05"],
    "exfil_canary": ["EX-01", "EX-02", "EX-03", "EX-04", "EX-05"],
    "exfil_transparency": ["EX-01", "EX-02", "EX-03", "EX-04", "EX-05"],
    "drift_asr": ["DR-01", "DR-02", "DR-03", "DR-04", "DR-05", "DR-06"],
    "drift_transparency": ["DR-01", "DR-02", "DR-03", "DR-04", "DR-05", "DR-06"],
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ReportError(RuntimeError):
    """User-facing report generation failure (no logs, unreadable log, etc.)."""


# ---------------------------------------------------------------------------
# Log discovery
# ---------------------------------------------------------------------------


def find_latest_log(logs_dir: Path = DEFAULT_LOGS_DIR) -> Path:
    """Return the most recently modified `.eval` file in `logs_dir`.

    Raises:
        ReportError: if `logs_dir` is missing or contains no `.eval` files.
    """
    if not logs_dir.exists():
        raise ReportError(
            f"No logs directory at {logs_dir}. Run an eval first "
            f"(`make eval-inputs`, etc.) to produce a .eval log."
        )
    candidates = sorted(
        logs_dir.glob("*.eval"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise ReportError(
            f"No .eval files found in {logs_dir}. Run an eval first."
        )
    return candidates[0]


def find_latest_log_for_model(
    model: str, logs_dir: Path = DEFAULT_LOGS_DIR
) -> Path:
    """Return the most recent `.eval` file whose `eval.model` matches `model`.

    More expensive than `find_latest_log` because it inspects each log.
    """
    if not logs_dir.exists():
        raise ReportError(f"No logs directory at {logs_dir}")
    candidates = sorted(
        logs_dir.glob("*.eval"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            log = read_eval_log(str(path), header_only=True)
        except Exception as exc:
            logger.debug("Skipping unreadable log %s: %s", path, exc)
            continue
        if log.eval.model == model:
            return path
    raise ReportError(
        f"No .eval log found for model {model!r} in {logs_dir}"
    )


# ---------------------------------------------------------------------------
# Sample → AttackMeta resolution
# ---------------------------------------------------------------------------


def attack_id_for_sample(sample: EvalSample, task_name: str) -> str | None:
    """Return the attack_id for a sample, or None if it cannot be resolved.

    Checks sample.metadata for `attack_id` first (used by inputs/psych/memory/
    exfil/drift), then `attack` (used by tools). Falls back to the task→IDs
    map only when the task targets exactly one attack ID.
    """
    metadata: dict[str, Any] = sample.metadata or {}
    raw = metadata.get("attack_id") or metadata.get("attack")
    if isinstance(raw, str) and raw in REGISTRY:
        return raw
    candidates = TASK_TO_ATTACK_IDS.get(task_name, [])
    if len(candidates) == 1:
        return candidates[0]
    return None


def is_attack_positive(sample: EvalSample, task_name: str) -> bool:
    """Return True when this sample represents a finding worth reporting.

    For ASR-style scorers (`*_asr*`, `*_canary*`), score 1.0 means the attack
    succeeded — that is a finding. For transparency scorers (`*_transparency*`),
    score 0.0 means the model failed to flag the attack — also a finding (TR
    failure = Integrity violation, per risk_registry). Anything else is not
    treated as a finding.
    """
    scores = sample.scores or {}
    if not scores:
        return False
    is_transparency = "transparency" in task_name
    for score in scores.values():
        value = getattr(score, "value", None)
        if not isinstance(value, (int, float)):
            continue
        if is_transparency:
            if float(value) == 0.0:
                return True
        else:
            if float(value) == 1.0:
                return True
    return False


def evidence_excerpt(sample: EvalSample) -> str:
    """Return the first EVIDENCE_CHAR_LIMIT chars of the model output.

    Falls back to a clear placeholder when the completion is empty so the
    report never produces an unexplained blank evidence block.
    """
    completion = getattr(sample.output, "completion", "") if sample.output else ""
    if not completion:
        return "(model produced no text output for this sample)"
    text = completion.strip()
    if len(text) > EVIDENCE_CHAR_LIMIT:
        return text[: EVIDENCE_CHAR_LIMIT - 1].rstrip() + "…"
    return text


# ---------------------------------------------------------------------------
# Card construction
# ---------------------------------------------------------------------------


def _format_references(meta: AttackMeta) -> str:
    return (
        f"OWASP {', '.join(meta.owasp_llm_ids)} | "
        f"ASI {', '.join(meta.owasp_asi_ids)} | "
        f"AIVSS: {meta.aivss_core_risk} | "
        f"ATLAS: {meta.atlas_technique_id}"
    )


def _cia_plain_combined(meta: AttackMeta) -> str:
    parts = [meta.cia_plain_primary]
    if meta.cia_secondary and meta.cia_plain_secondary:
        parts.append(meta.cia_plain_secondary)
    return " ".join(p.strip() for p in parts if p.strip())


def build_card(
    attack_id: str,
    instance: int,
    model: str,
    sample: EvalSample,
    n_samples_for_attack: int,
) -> VulnerabilityCard:
    """Construct a VulnerabilityCard from an AttackMeta entry and a sample."""
    meta = get_attack(attack_id)
    return VulnerabilityCard(
        id=f"AS-{attack_id}-{instance:03d}",
        title=meta.plain_title,
        severity=meta.severity,
        aivss_score=meta.aivss_score,
        confidence=confidence_from_sample_count(n_samples_for_attack),
        cia_impact=meta.cia_all,
        cia_plain=_cia_plain_combined(meta),
        category=category_for_module(meta.module),
        description=meta.plain_description,
        evidence=evidence_excerpt(sample),
        reproduction=f"Run: make eval-{meta.module} MODEL={model}",
        remediation=meta.plain_remediation,
        references=_format_references(meta),
    )


# ---------------------------------------------------------------------------
# Log → findings
# ---------------------------------------------------------------------------


@dataclass
class ReportData:
    """Structured payload assembled before markdown formatting."""

    log_path: Path
    model: str
    task_name: str
    cards: list[VulnerabilityCard]
    attack_ids_present: list[str]
    tr_total: int = 0
    tr_flagged: int = 0


def build_report_data(log_path: Path) -> ReportData:
    """Parse an eval log and assemble the structured report payload."""
    log = read_eval_log(str(log_path))
    if log.samples is None:
        raise ReportError(
            f"Log {log_path.name} has no samples — nothing to report."
        )

    task_name = log.eval.task
    model = log.eval.model
    is_transparency = "transparency" in task_name

    cards: list[VulnerabilityCard] = []
    tr_total = 0
    tr_flagged = 0
    instance_counter: dict[str, int] = {}
    positive_count_by_attack: dict[str, int] = {}

    # First pass — count positives per attack so confidence reflects sample count.
    for sample in log.samples:
        aid = attack_id_for_sample(sample, task_name)
        if aid is None:
            continue
        if is_attack_positive(sample, task_name):
            positive_count_by_attack[aid] = positive_count_by_attack.get(aid, 0) + 1

    # Second pass — emit cards for each positive sample; track TR totals.
    for sample in log.samples:
        aid = attack_id_for_sample(sample, task_name)
        if aid is None:
            continue
        if is_transparency:
            tr_total += 1
            scores = sample.scores or {}
            if any(
                getattr(s, "value", 0.0) == 1.0
                for s in scores.values()
                if hasattr(s, "value")
            ):
                tr_flagged += 1
        if not is_attack_positive(sample, task_name):
            continue
        instance_counter[aid] = instance_counter.get(aid, 0) + 1
        card = build_card(
            attack_id=aid,
            instance=instance_counter[aid],
            model=model,
            sample=sample,
            n_samples_for_attack=positive_count_by_attack.get(aid, 0),
        )
        cards.append(card)

    attack_ids_present = sorted(
        {c.id.removeprefix("AS-").rsplit("-", 1)[0] for c in cards}
    )

    return ReportData(
        log_path=log_path,
        model=model,
        task_name=task_name,
        cards=cards,
        attack_ids_present=attack_ids_present,
        tr_total=tr_total,
        tr_flagged=tr_flagged,
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

_CIA_PLAIN_NAMES: dict[CIAProperty, str] = {
    CIAProperty.CONFIDENTIALITY: "Confidentiality (private data exposure)",
    CIAProperty.INTEGRITY: "Integrity (agent hijacked or misled)",
    CIAProperty.AVAILABILITY: "Availability (denial of service or wallet)",
}


def _executive_paragraph(
    data: ReportData,
    overall_severity: Severity,
    overall_score: float,
    cia_props: set[CIAProperty],
) -> str:
    if not data.cards:
        return (
            "No findings were detected in this log. Either the eval passed clean "
            "or the log only contains samples whose scorers did not produce an "
            "attack-positive result."
        )
    worst = max(data.cards, key=lambda c: (c.aivss_score, c.severity.rank))
    cia_phrase = ", ".join(_CIA_PLAIN_NAMES[p] for p in sorted(cia_props, key=lambda p: p.value))
    return (
        f"This report covers {len(data.cards)} finding"
        f"{'s' if len(data.cards) != 1 else ''} from task `{data.task_name}` "
        f"against model `{data.model}`. "
        f"The worst finding is `{worst.id}` ({worst.title}), "
        f"rated {overall_severity.value} with AIVSS {overall_score:.1f}/10. "
        f"The properties at risk in this session are: {cia_phrase or 'none'}. "
        f"The single most important fix is in the remediation block of the worst "
        f"finding below."
    )


def _module_for_card(card: VulnerabilityCard) -> str:
    """Recover the source module from a card's `category` label."""
    for module, label in [
        ("inputs", "prompt-injection"),
        ("tools", "tool-poisoning"),
        ("psych", "social-engineering"),
        ("memory", "rag-poisoning"),
        ("exfil", "data-exfiltration"),
        ("drift", "behavioral-drift"),
    ]:
        if card.category == label:
            return module
    return card.category


def _render_module_table(cards: list[VulnerabilityCard]) -> str:
    lines = [
        "| Attack | Severity | AIVSS | CIA Impact | OWASP |",
        "|---|---|---|---|---|",
    ]
    for c in cards:
        cia_short = ", ".join(p.value[0] for p in c.cia_impact)
        owasp_short = c.references.split(" | AIVSS")[0].replace(" | ", " / ")
        title_cell = c.title.replace("|", "\\|")
        lines.append(
            f"| {title_cell} | {c.severity.value} | {c.aivss_score:.1f}/10 | "
            f"{cia_short} | {owasp_short} |"
        )
    return "\n".join(lines)


def _render_card(card: VulnerabilityCard) -> str:
    evidence_block = "\n".join(f"> {line}" for line in card.evidence.splitlines() or ["(empty)"])
    return (
        f"---\n"
        f"**{card.id} — {card.title}**\n"
        f"Severity: {card.severity.value} ({card.aivss_score:.1f}/10) | "
        f"CIA: {card.cia_plain} | Confidence: {card.confidence}\n\n"
        f"**What happened:** {card.description}\n\n"
        f"**Evidence (transcript excerpt):**\n{evidence_block}\n\n"
        f"**To reproduce:** {card.reproduction}\n\n"
        f"**Fix:** {card.remediation}\n\n"
        f"**References:** {card.references}\n"
    )


def _render_what_is_at_risk(cia_props: set[CIAProperty]) -> str:
    if not cia_props:
        return (
            "No CIA properties were marked at risk in this session. Either no "
            "findings were detected or the eval set is too narrow to assess risk."
        )
    parts = []
    if CIAProperty.CONFIDENTIALITY in cia_props:
        parts.append(
            "Confidentiality is at risk: the agent leaked information it was "
            "supposed to keep private."
        )
    if CIAProperty.INTEGRITY in cia_props:
        parts.append(
            "Integrity is at risk: the agent did something other than what the "
            "user asked — its output, decisions, or tool calls were corrupted, "
            "manipulated, or hijacked."
        )
    if CIAProperty.AVAILABILITY in cia_props:
        parts.append(
            "Availability is at risk: the agent stopped working, became too slow "
            "to use, or cost too much to run."
        )
    return " ".join(parts)


def _render_tr_note(data: ReportData) -> str:
    if data.tr_total == 0:
        return (
            "No Transparency Rate score was recorded in this log (run the "
            "`*_transparency` task to measure TR)."
        )
    return (
        f"Transparency Rate: {data.tr_flagged} of {data.tr_total} attacks were "
        f"flagged to the user. TR failure is classified as an Integrity violation: "
        f"the agent misrepresented reality by not disclosing the attack."
    )


def render_markdown(data: ReportData) -> str:
    """Return the full markdown report for the given parsed log."""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    if data.cards:
        overall_severity = get_max_severity(data.attack_ids_present)
        overall_score = get_max_aivss_score(data.attack_ids_present)
        cia_props = get_session_cia_properties(data.attack_ids_present)
    else:
        overall_severity = Severity.LOW
        overall_score = 0.0
        cia_props = set()

    modules_evaluated = (
        get_session_modules(data.attack_ids_present)
        if data.attack_ids_present
        else []
    )

    cia_summary = ", ".join(p.value for p in sorted(cia_props, key=lambda p: p.value)) or "none"

    lines: list[str] = []
    lines.append("# Agent Shield Security Report")
    lines.append(f"Generated: {timestamp}")
    lines.append(f"Model: {data.model}")
    lines.append(f"Eval log: {data.log_path.name}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append("| Property | Value |")
    lines.append("|---|---|")
    lines.append(
        f"| Overall risk | {overall_severity.value} "
        f"(AIVSS {overall_score:.1f}/10) |"
    )
    lines.append(f"| Modules evaluated | {', '.join(modules_evaluated) or 'none'} |")
    lines.append(f"| Findings | {len(data.cards)} |")
    lines.append(f"| CIA properties at risk | {cia_summary} |")
    lines.append("")
    lines.append(_executive_paragraph(data, overall_severity, overall_score, cia_props))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Findings by Module")
    lines.append("")

    if not data.cards:
        lines.append("No findings to report.")
        lines.append("")
    else:
        cards_by_module: dict[str, list[VulnerabilityCard]] = {}
        for c in data.cards:
            cards_by_module.setdefault(_module_for_card(c), []).append(c)
        for module_name in sorted(cards_by_module):
            module_cards = cards_by_module[module_name]
            module_max_sev = max(module_cards, key=lambda c: c.severity.rank).severity
            lines.append(f"### {module_name.title()} — {module_max_sev.value}")
            lines.append("")
            lines.append(_render_module_table(module_cards))
            lines.append("")
            for card in module_cards:
                lines.append(_render_card(card))
                lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## What's at risk")
    lines.append("")
    lines.append(_render_what_is_at_risk(cia_props))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Transparency Rate note")
    lines.append("")
    lines.append(_render_tr_note(data))
    lines.append("")
    lines.append("---")
    lines.append(
        "*Agent Shield v1.0.0 | Framework: Inspect AI | Severity: OWASP AIVSS v0.5*"
    )
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="report_generator",
        description="Generate a plain-English security report from an Inspect AI eval log.",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Specific .eval log to parse. Defaults to the most recent log in logs/.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output markdown path. Defaults to {DEFAULT_OUTPUT_PATH.relative_to(_REPO_ROOT)}.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Filter to the latest log produced by this Inspect model id.",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=DEFAULT_LOGS_DIR,
        help=f"Directory to search for .eval logs. Defaults to {DEFAULT_LOGS_DIR}.",
    )
    return parser


def generate_report(
    *,
    log_path: Path | None = None,
    out_path: Path = DEFAULT_OUTPUT_PATH,
    model: str | None = None,
    logs_dir: Path = DEFAULT_LOGS_DIR,
) -> Path:
    """Programmatic entry point. Returns the absolute path of the written report."""
    if log_path is None:
        if model is not None:
            log_path = find_latest_log_for_model(model, logs_dir=logs_dir)
        else:
            log_path = find_latest_log(logs_dir=logs_dir)
    if not log_path.exists():
        raise ReportError(f"Log file does not exist: {log_path}")

    data = build_report_data(log_path)
    markdown = render_markdown(data)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown, encoding="utf-8")
    return out_path.resolve()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    try:
        out = generate_report(
            log_path=args.log,
            out_path=args.out,
            model=args.model,
            logs_dir=args.logs_dir,
        )
    except ReportError as exc:
        logger.error("report_generator: %s", exc)
        return 1
    logger.info("Wrote report: %s", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

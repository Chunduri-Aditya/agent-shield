"""Phase 4 proof metrics — FP, alert rate, disable rate for the runtime perimeter.

Deterministic: all scoring in Python. Inputs are fixtures / JSONL session logs.
Does not call models or the network.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from agent_shield.runtime.gate import GuardAction
from agent_shield.runtime.mcp_proxy import McpToolProxy, ToolSpec, catalog_from_jsonable
from agent_shield.runtime.pipeline import guard_text


@dataclass(frozen=True)
class ProofMetrics:
    """Aggregate proof numbers for a guard / proxy measurement pass."""

    n_benign: int
    n_attack: int
    false_positive_denies: int
    false_positive_quarantines: int
    false_positive_rate: float
    alert_rate_benign: float
    alert_rate_attack: float
    recall_quarantine_on_attack: float
    n_sessions: int
    n_sessions_disabled: int
    disable_rate: float
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["notes"] = list(self.notes)
        return data


def _rate(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round(num / den, 4)


def measure_text_cases(
    cases: list[dict[str, Any]],
    *,
    mode: str = "product",
) -> dict[str, Any]:
    """Screen free-text cases with ``malicious`` bool; return raw tallies."""

    benign = [c for c in cases if not c.get("malicious")]
    attack = [c for c in cases if c.get("malicious")]
    fp_deny = 0
    alerts_benign = 0
    alerts_attack = 0
    attack_caught = 0

    for case in benign:
        result = guard_text(str(case["text"]), mode=mode, source_id=str(case.get("id", "b")))
        if result.action is GuardAction.DENY:
            fp_deny += 1
        if result.action is not GuardAction.ALLOW:
            alerts_benign += 1

    for case in attack:
        result = guard_text(str(case["text"]), mode=mode, source_id=str(case.get("id", "a")))
        if result.action is not GuardAction.ALLOW:
            alerts_attack += 1
        if result.flagged_attack or result.action is GuardAction.DENY:
            attack_caught += 1

    return {
        "n_benign": len(benign),
        "n_attack": len(attack),
        "false_positive_denies": fp_deny,
        "alerts_benign": alerts_benign,
        "alerts_attack": alerts_attack,
        "attack_caught": attack_caught,
    }


def measure_tool_catalog(
    tools: list[ToolSpec],
    labels: dict[str, bool],
    *,
    mode: str = "product",
) -> dict[str, Any]:
    """``labels[name]=True`` means the tool description is an attack (poison)."""

    proxy = McpToolProxy(mode=mode)
    result = proxy.screen_catalog(tools)
    fp_q = 0
    n_benign = 0
    n_attack = 0
    attack_q = 0
    alerts_benign = 0
    alerts_attack = 0

    for tool in result.tools:
        is_attack = bool(labels.get(tool.name, False))
        if is_attack:
            n_attack += 1
            if tool.quarantined:
                attack_q += 1
            if tool.guard.action is not GuardAction.ALLOW:
                alerts_attack += 1
        else:
            n_benign += 1
            if tool.quarantined:
                fp_q += 1
            if tool.guard.action is not GuardAction.ALLOW:
                alerts_benign += 1

    return {
        "n_benign": n_benign,
        "n_attack": n_attack,
        "false_positive_quarantines": fp_q,
        "alerts_benign": alerts_benign,
        "alerts_attack": alerts_attack,
        "attack_quarantined": attack_q,
        "badge": result.badge,
    }


def measure_disable_rate(session_events: list[dict[str, Any]]) -> dict[str, Any]:
    """Session JSONL semantics: group by ``session_id``.

    A session is "disabled" if it emits ``kill_switch_on`` at least once.
    """

    by_session: dict[str, list[dict[str, Any]]] = {}
    for event in session_events:
        sid = str(event.get("session_id", "")).strip()
        if not sid:
            raise ValueError("each event needs a nonempty session_id")
        by_session.setdefault(sid, []).append(event)

    disabled = 0
    for events in by_session.values():
        if any(e.get("event") == "kill_switch_on" for e in events):
            disabled += 1

    n = len(by_session)
    return {
        "n_sessions": n,
        "n_sessions_disabled": disabled,
        "disable_rate": _rate(disabled, n),
    }


def compute_proof_metrics(
    *,
    text_cases: list[dict[str, Any]] | None = None,
    catalog_tools: list[ToolSpec] | None = None,
    catalog_labels: dict[str, bool] | None = None,
    session_events: list[dict[str, Any]] | None = None,
    mode: str = "product",
) -> ProofMetrics:
    """Combine text, catalog, and session measurements into one ProofMetrics."""

    notes: list[str] = []
    n_benign = 0
    n_attack = 0
    fp_deny = 0
    fp_q = 0
    alerts_b = 0
    alerts_a = 0
    catalog_n_attack = 0
    attack_q = 0
    den_b = 0
    den_a = 0

    if text_cases:
        t = measure_text_cases(text_cases, mode=mode)
        n_benign += t["n_benign"]
        n_attack += t["n_attack"]
        fp_deny += t["false_positive_denies"]
        alerts_b += t["alerts_benign"]
        alerts_a += t["alerts_attack"]
        den_b += t["n_benign"]
        den_a += t["n_attack"]
        notes.append("text cases included")

    if catalog_tools is not None:
        labels = catalog_labels or {}
        c = measure_tool_catalog(catalog_tools, labels, mode=mode)
        n_benign += c["n_benign"]
        n_attack += c["n_attack"]
        catalog_n_attack = c["n_attack"]
        fp_q += c["false_positive_quarantines"]
        alerts_b += c["alerts_benign"]
        alerts_a += c["alerts_attack"]
        attack_q += c["attack_quarantined"]
        den_b += c["n_benign"]
        den_a += c["n_attack"]
        notes.append("MCP catalog included")

    disable = {"n_sessions": 0, "n_sessions_disabled": 0, "disable_rate": 0.0}
    if session_events is not None:
        disable = measure_disable_rate(session_events)
        notes.append("session disable log included")

    fp_events = fp_deny + fp_q
    return ProofMetrics(
        n_benign=n_benign,
        n_attack=n_attack,
        false_positive_denies=fp_deny,
        false_positive_quarantines=fp_q,
        false_positive_rate=_rate(fp_events, n_benign),
        alert_rate_benign=_rate(alerts_b, den_b),
        alert_rate_attack=_rate(alerts_a, den_a),
        recall_quarantine_on_attack=_rate(attack_q, catalog_n_attack),
        n_sessions=disable["n_sessions"],
        n_sessions_disabled=disable["n_sessions_disabled"],
        disable_rate=disable["disable_rate"],
        notes=tuple(notes),
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise TypeError("JSONL rows must be objects")
        rows.append(row)
    return rows


def run_default_proof(
    *,
    safety_cases_path: Path,
    catalog_path: Path,
    sessions_path: Path,
    mode: str = "product",
) -> ProofMetrics:
    """Load standard fixtures and compute proof metrics."""

    cases = load_json(safety_cases_path)
    if not isinstance(cases, list):
        raise TypeError("safety cases must be a JSON array")

    catalog_raw = load_json(catalog_path)
    tools = catalog_from_jsonable(catalog_raw)
    labels_raw = catalog_raw.get("labels", {}) if isinstance(catalog_raw, dict) else {}
    labels = {str(k): bool(v) for k, v in labels_raw.items()}

    sessions = load_jsonl(sessions_path)
    return compute_proof_metrics(
        text_cases=cases,
        catalog_tools=tools,
        catalog_labels=labels,
        session_events=sessions,
        mode=mode,
    )

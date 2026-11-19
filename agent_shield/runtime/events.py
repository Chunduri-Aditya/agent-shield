"""SecurityEvent, a hash chained event log, and the guard and self report channels.

A SecurityEvent wraps the AlertCard an operator reads and adds what a log needs: time,
session, tool, decision, channel and the framework ids, each with its edition or version.

The log is JSON lines. Each record holds the hash of the record before it, so an edit, a
deleted line, a swapped line or a bad line fails `verify_chain`. The chain has no key. A
cut at the end, or a full rewrite, is seen only when the caller keeps the head hash
somewhere the writer of the log cannot reach and passes it as `expected_head`.

Text the model wrote (a self report) is data: it is cut short, stripped of control
characters and hashed, and its claimed kind is kept only when it is on a fixed list.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_shield.runtime.alert import AlertCard

try:
    import fcntl
except ImportError:  # no POSIX file lock on this platform
    fcntl = None  # type: ignore[assignment]

GENESIS = "0" * 64
CHANNELS = ("guard", "self")
DECISIONS = ("allow", "asked", "blocked", "killed")
SELF_REPORT_KINDS = ("prompt_injection", "tool_loop", "data_exfiltration", "other")
SELF_REPORT_VERSION = "self-report-1"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_ID_FORMATS = {
    "owasp_llm": re.compile(r"LLM\d{2}:20\d{2}"),
    "owasp_asi": re.compile(r"ASI\d{2}"),
    "owasp_mcp": re.compile(r"MCP\d{2}:20\d{2}"),
    "atlas": re.compile(r"AML\.T\d{4}(\.\d{3})?@\d{4}\.\d{2}"),
}
_RECORD_KEYS = {"seq", "prev_hash", "event", "hash"}


class ChainError(Exception):
    """The log on disk does not verify, so it is not read or appended to."""


def now() -> str:
    """The current time as the schema wants it: ISO 8601, UTC, to the second."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    """SHA256 of a text, as lower case hex. A lone surrogate is hashed, not refused."""
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def _one_line(text: str, limit: int) -> str:
    return "".join(c if c.isprintable() else " " for c in text)[:limit]


@dataclass(frozen=True)
class FrameworkIds:
    """Framework ids of one event. An id without its edition or version is refused.

    OWASP LLM ids carry the edition (LLM10:2025), OWASP MCP ids carry the edition
    (MCP03:2025), ATLAS ids carry the data release (AML.T0034.002@2026.10). OWASP Agentic
    ids (ASI02) have one edition and carry none.
    """

    owasp_llm: tuple[str, ...] = ()
    owasp_asi: tuple[str, ...] = ()
    owasp_mcp: tuple[str, ...] = ()
    atlas: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, pattern in _ID_FORMATS.items():
            values = getattr(self, name)
            if not isinstance(values, tuple):
                raise ValueError(f"{name} must be a tuple of ids, not {type(values).__name__}")
            for value in values:
                if not isinstance(value, str) or not pattern.fullmatch(value):
                    raise ValueError(f"{name} id {value!r} does not match {pattern.pattern}")

    def to_dict(self) -> dict[str, list[str]]:
        return {name: list(getattr(self, name)) for name in _ID_FORMATS}


@dataclass(frozen=True)
class SecurityEvent:
    """One decision of the guard, or one report from the model, for one session."""

    ts: str
    session: str
    agent: str
    tool: str
    channel: str
    decision: str
    severity: str
    rule: str
    evidence_sha256: str
    card: AlertCard
    ids: FrameworkIds = field(default_factory=FrameworkIds)

    def __post_init__(self) -> None:
        if self.channel not in CHANNELS:
            raise ValueError(f"channel {self.channel!r} is not one of {CHANNELS}")
        if self.decision not in DECISIONS:
            raise ValueError(f"decision {self.decision!r} is not one of {DECISIONS}")
        if not self.session or not self.rule:
            raise ValueError("session and rule must not be empty")
        if self.evidence_sha256 and not _SHA256.fullmatch(self.evidence_sha256):
            raise ValueError("evidence_sha256 must be 64 lower case hex characters, or empty")
        try:
            stamp = datetime.fromisoformat(self.ts)
        except ValueError:
            stamp = None
        if stamp is None or stamp.tzinfo is None:
            raise ValueError(f"ts {self.ts!r} must be ISO 8601 with a time zone")

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "session": self.session,
            "agent": self.agent,
            "tool": self.tool,
            "channel": self.channel,
            "decision": self.decision,
            "severity": self.severity,
            "rule": self.rule,
            **self.ids.to_dict(),
            "evidence_sha256": self.evidence_sha256,
            "card": self.card.to_dict(),
        }


def self_report_event(
    *, ts: str, session: str, agent: str, kind: str, evidence: str, source: str
) -> SecurityEvent:
    """The event for one report the model made about what it read.

    The report changes no decision. It gets no framework id and the severity "unverified",
    because the reporter is the component an attack targets.
    """
    kind = kind if kind in SELF_REPORT_KINDS else "other"
    digest = sha256_text(evidence)
    card = AlertCard(
        title=f"Model self report: {kind}",
        severity="unverified",
        action="allow",
        cia_impact="Not assessed",
        description=f"Source named by the model: {_one_line(source, 60)}",
        evidence=_one_line(evidence, 60),
        remediation="Compare with the guard channel for this session before acting.",
        content_ruleset_version=SELF_REPORT_VERSION,
        content_sha256=digest,
        flagged_attack=False,
    )
    return SecurityEvent(
        ts=ts,
        session=session,
        agent=agent,
        tool="",
        channel="self",
        decision="allow",
        severity="unverified",
        rule="self_report",
        evidence_sha256=digest,
        card=card,
    )


def record_hash(record: dict[str, Any]) -> str:
    """The hash of one chain record: its seq, the hash before it and its event."""
    body = {key: record[key] for key in ("seq", "prev_hash", "event")}
    return sha256_text(json.dumps(body, sort_keys=True, separators=(",", ":")))


@dataclass(frozen=True)
class ChainReport:
    """What `verify_chain` found. `error` names the first bad line, counted from 1."""

    ok: bool
    count: int
    head: str
    error: str = ""


def _scan(path: Path) -> tuple[ChainReport, list[dict[str, Any]]]:
    head = GENESIS
    events: list[dict[str, Any]] = []
    if not path.exists():
        return ChainReport(True, 0, head), events
    for number, line in enumerate(path.read_text().splitlines(), 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            return ChainReport(False, len(events), head, f"line {number}: not JSON"), events
        if not isinstance(record, dict) or set(record) != _RECORD_KEYS:
            return ChainReport(False, len(events), head, f"line {number}: not a record"), events
        if record["seq"] != len(events) or record["prev_hash"] != head:
            error = f"line {number}: does not follow the record before it"
            return ChainReport(False, len(events), head, error), events
        if record["hash"] != record_hash(record):
            error = f"line {number}: the hash does not match the content"
            return ChainReport(False, len(events), head, error), events
        head = record["hash"]
        events.append(record["event"])
    return ChainReport(True, len(events), head), events


def verify_chain(path: Path, expected_head: str | None = None) -> ChainReport:
    """Check every record of the log, and the head when the caller kept one."""
    report, _ = _scan(path)
    if report.ok and expected_head is not None and report.head != expected_head:
        return ChainReport(False, report.count, report.head, "the head hash is not the one kept")
    return report


def read_chain(path: Path, expected_head: str | None = None) -> list[dict[str, Any]]:
    """The events of a log that verifies. A log that does not verify raises ChainError."""
    report, events = _scan(path)
    if report.ok and expected_head is not None and report.head != expected_head:
        raise ChainError(f"{path}: the head hash is not the one kept")
    if not report.ok:
        raise ChainError(f"{path}: {report.error}")
    return events


class ChainedLog:
    """Appends SecurityEvents to one log file. Several writers may share the file.

    The file is made when the writer is, so a path that cannot be written fails at once.
    An append holds a file lock from its size check to its write. A writer that finds
    records it did not write follows them when the log still verifies and still holds
    what this writer wrote. A log that was cut, rewritten or broken is refused. A platform
    with no file lock is refused too, because two writers could then break the chain.
    """

    def __init__(self, path: Path) -> None:
        os.close(os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600))
        report = verify_chain(path)
        if not report.ok:
            raise ChainError(f"{path}: {report.error}")
        self.path = path
        self.head = report.head
        self.count = report.count
        self._size = path.stat().st_size

    def append(self, event: SecurityEvent) -> str:
        """Write one event and return the new head hash."""
        if not isinstance(event, SecurityEvent):
            raise TypeError(f"append takes a SecurityEvent, not {type(event).__name__}")
        if fcntl is None:
            raise ChainError(f"{self.path}: this platform has no file lock, so nothing is written")
        descriptor = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(descriptor, "a") as handle:
            fcntl.flock(descriptor, fcntl.LOCK_EX)  # held until the file closes
            size = os.fstat(descriptor).st_size
            if size != self._size:
                self._follow(size)
            record: dict[str, Any] = {
                "seq": self.count,
                "prev_hash": self.head,
                "event": event.to_dict(),
            }
            record["hash"] = record_hash(record)
            line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            handle.write(line)
        self._size += len(line.encode())
        self.head = record["hash"]
        self.count += 1
        return self.head

    def _follow(self, size: int) -> None:
        """Take the head of a log that another writer extended. Called with the lock held."""
        report, _ = _scan(self.path)
        if not report.ok:
            raise ChainError(f"{self.path}: {report.error}")
        hashes = [json.loads(line)["hash"] for line in self.path.read_text().splitlines()]
        kept = hashes[self.count - 1] if 0 < self.count <= len(hashes) else GENESIS
        if report.count < self.count or kept != self.head:
            raise ChainError(f"{self.path}: the log no longer holds what this writer wrote")
        self.head, self.count, self._size = report.head, report.count, size


def channels_by_session(events: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """How many events each channel wrote for each session."""
    seen: dict[str, dict[str, int]] = {}
    for event in events:
        counts = seen.setdefault(event["session"], dict.fromkeys(CHANNELS, 0))
        counts[event["channel"]] += 1
    return seen


def correlate(guard: bool, self_report: bool) -> tuple[str, str]:
    """The cell and the severity of one session, from which channels fired.

    The guard fired and the model said nothing is the highest: the model either missed
    the attack or hid it.
    """
    if guard and self_report:
        return "both", "high"
    if guard:
        return "guard_only", "highest"
    if self_report:
        return "self_only", "low"
    return "neither", "none"

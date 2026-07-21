"""Deterministic CIA screening and audit helpers for agent web research.

The module intentionally performs no network requests. Codex, Claude Code, or
another caller owns discovery and retrieval. Agent Shield owns the control
plane around those calls: query redaction, CIA classification, source
screening, approval manifests, retrieved content screening, quarantine, and
append only audit events.
"""

from __future__ import annotations

import getpass
import hashlib
import hmac
import ipaddress
import json
import os
import re
import tempfile
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

RULESET_VERSION = "research-cia-v1.1"
CONTENT_RULESET_VERSION = "research-content-v1.1.2"

MAX_QUERY_CHARS = 500
MAX_QUERIES_PER_QUESTION = 4
MAX_SOURCES_PER_QUESTION = 3
MAX_SOURCES_PER_BATCH = 30
MAX_SOURCE_CHARS = 100_000
MAX_RETRIES = 2
MAX_CONCURRENCY = 3
MAX_TIMEOUT_SECONDS = 60
MAX_COST_USD = 5.0


class RiskLevel(StrEnum):
    """Ordered policy vocabulary used by research screening."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_RISK_ORDER: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


@dataclass(frozen=True)
class ResearchRequest:
    """One proposed native web search before any search tool is called."""

    request_id: str
    qid: str
    query: str
    purpose: str = ""
    allowed_domains: tuple[str, ...] = ()
    max_queries: int = MAX_QUERIES_PER_QUESTION
    max_sources: int = MAX_SOURCES_PER_QUESTION
    max_chars_per_source: int = MAX_SOURCE_CHARS
    max_retries: int = MAX_RETRIES
    max_concurrency: int = MAX_CONCURRENCY
    timeout_seconds: int = 30
    max_cost_usd: float = 0.0
    contains_private_project_evidence: bool = False
    confirmed_high_risk: bool = False
    ethics_cleared: bool = False

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("qid", self.qid)
        _require_text("query", self.query)
        for name in (
            "max_queries",
            "max_sources",
            "max_chars_per_source",
            "max_retries",
            "max_concurrency",
            "timeout_seconds",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be nonnegative")
        if self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be nonnegative")


@dataclass(frozen=True)
class SourceCandidate:
    """A URL discovered by search but not yet opened."""

    request_id: str
    qid: str
    source_id: str
    url: str
    title: str = ""
    snippet: str = ""
    discovered_via: str = "native_web_search"
    trust_tier: str = "unclassified"
    allowed_domains: tuple[str, ...] = ()
    redirect_chain: tuple[str, ...] = ()
    confirmed_high_risk: bool = False
    ethics_cleared: bool = False

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("qid", self.qid)
        _require_text("source_id", self.source_id)
        _require_text("url", self.url)


@dataclass(frozen=True)
class RetrievedContent:
    """The exact text payload returned by a native retrieval tool."""

    request_id: str
    qid: str
    source_id: str
    url: str
    text: str
    manifest_sha256: str
    content_type: str = "text/html"
    max_chars: int = MAX_SOURCE_CHARS
    confirmed_high_risk: bool = False
    ethics_cleared: bool = False

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("qid", self.qid)
        _require_text("source_id", self.source_id)
        _require_text("url", self.url)
        _require_text("text", self.text)
        _require_sha256("manifest_sha256", self.manifest_sha256)
        if self.max_chars <= 0:
            raise ValueError("max_chars must be positive")


@dataclass(frozen=True)
class ResearchGateResult:
    """CIA decision returned before search or source retrieval."""

    allowed: bool
    risk_level: RiskLevel
    confidentiality_status: str
    integrity_status: str
    availability_status: str
    reasons: tuple[str, ...]
    required_action: str
    manifest_sha256: str = ""
    ruleset_version: str = RULESET_VERSION
    sanitized_query: str = ""
    canonical_url: str = ""
    trust_tier: str = "unclassified"
    override_permitted: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = _jsonable(asdict(self))
        assert isinstance(data, dict)
        return data


@dataclass(frozen=True)
class ContentScreenResult:
    """Decision for retrieved text before it is used for answer synthesis."""

    allowed: bool
    risk_level: RiskLevel
    confidentiality_status: str
    integrity_status: str
    availability_status: str
    reasons: tuple[str, ...]
    required_action: str
    content_sha256: str
    quarantine_required: bool
    flagged_attack: bool
    transparency_message: str
    requires_cross_check: bool = True
    ruleset_version: str = RULESET_VERSION
    content_ruleset_version: str = CONTENT_RULESET_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = _jsonable(asdict(self))
        assert isinstance(data, dict)
        return data


@dataclass(frozen=True)
class ApprovalManifest:
    """Stable, hash addressed list of screened source candidates."""

    batch_id: str
    created_at: str
    manifest_sha256: str
    sources: tuple[dict[str, Any], ...]
    ruleset_version: str = RULESET_VERSION

    def to_dict(self) -> dict[str, Any]:
        data = _jsonable(asdict(self))
        assert isinstance(data, dict)
        return data


@dataclass(frozen=True)
class ResearchAuditEvent:
    """One sanitized append only audit record."""

    event_id: str
    event_type: str
    request_id: str
    qid: str
    decision: str
    timestamp: str = field(default_factory=lambda: _now())
    source_id: str = ""
    manifest_sha256: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text("event_id", self.event_id)
        _require_text("event_type", self.event_type)
        _require_text("request_id", self.request_id)
        _require_text("qid", self.qid)
        _require_text("decision", self.decision)
        if self.manifest_sha256:
            _require_sha256("manifest_sha256", self.manifest_sha256)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["details"] = sanitize_for_audit(data["details"])
        converted = _jsonable(data)
        assert isinstance(converted, dict)
        return converted


_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "private key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
        "[REDACTED_PRIVATE_KEY]",
    ),
    (
        "bearer token",
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
        "[REDACTED_BEARER_TOKEN]",
    ),
    (
        "basic auth credential",
        re.compile(r"\bBasic\s+[A-Za-z0-9+/]{8,}={0,2}", re.I),
        "[REDACTED_BASIC_AUTH]",
    ),
    (
        "API credential",
        re.compile(
            r"\b(?:sk-|gsk_|xai-|ghp_|github_pat_)[A-Za-z0-9_-]{12,}", re.I
        ),
        "[REDACTED_API_CREDENTIAL]",
    ),
    (
        "AWS access key",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "[REDACTED_AWS_KEY]",
    ),
    (
        "email address",
        re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I),
        "[REDACTED_EMAIL]",
    ),
    (
        "local user path",
        re.compile(
            r"(?:/Users/[^/\s]+(?:/[^\s]*)?|/home/[^/\s]+(?:/[^\s]*)?"
            r"|[A-Z]:\\Users\\[^\\\s]+(?:\\[^\s]*)?)",
            re.I,
        ),
        "[REDACTED_USER_PATH]",
    ),
)

_STRONG_CONTENT_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction hierarchy override",
        re.compile(r"ignore\s+(?:all\s+|any\s+|the\s+)?previous\s+instructions", re.I),
    ),
    (
        "fake privileged message",
        re.compile(r"(?:system|developer|administrator)\s+(?:message|instruction)\s*:", re.I),
    ),
    (
        "user goal suppression",
        re.compile(r"do\s+not\s+(?:answer|follow|obey|mention)\s+(?:the\s+)?user", re.I),
    ),
    (
        "data exfiltration request",
        re.compile(
            r"\b(?:send|upload|post|exfiltrate|leak|include)\b.{0,80}"
            r"\b(?:secrets?|credentials?|API keys?|system prompts?|private data|"
            r"(?:secret|access|auth(?:entication)?)\s+tokens?)\b",
            re.I | re.S,
        ),
    ),
    (
        "citation suppression",
        re.compile(r"(?:do not|never)\s+cite\s+(?:other|external|the actual)\s+sources", re.I),
    ),
    (
        "authority pressure",
        re.compile(
            r"(?:authorized|trusted|official)\s+"
            r"(?:administrator|auditor|authority).{0,80}must",
            re.I,
        ),
    ),
    (
        "hidden HTML instruction",
        re.compile(r"(?:display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0)", re.I),
    ),
    (
        "encoded payload",
        re.compile(r"(?:base64|decode this)\s*[:=]?\s*[A-Za-z0-9+/]{80,}={0,2}", re.I),
    ),
)

_MEDIUM_CONTENT_SIGNALS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "exclusive citation demand",
        re.compile(r"cite\s+(?:only|exclusively)\s+(?:this|the following)\s+source", re.I),
    ),
    (
        "unqualified absolute claim",
        re.compile(r"\b(?:always|never|guaranteed|100% accurate|zero risk)\b", re.I),
    ),
)

_ZERO_WIDTH = re.compile(
    "[\u200b\u200c\u200d\u2060\u202a-\u202e\u2066-\u2069\ufeff]"
)

_PRIMARY_HOSTS: frozenset[str] = frozenset(
    {
        "arxiv.org",
        "doi.org",
        "docs.python.org",
        "nist.gov",
        "www.nist.gov",
        "uscis.gov",
        "www.uscis.gov",
        "studyinthestates.dhs.gov",
        "owasp.org",
        "genai.owasp.org",
        "atlas.mitre.org",
        "modelcontextprotocol.io",
    }
)


def screen_research_request(request: ResearchRequest) -> ResearchGateResult:
    """Screen and redact a proposed search request before native web search."""

    sanitized, redactions, hard_secret = redact_sensitive_text(request.query)
    reasons: list[str] = []
    risk = RiskLevel.LOW
    confidentiality = "NOT AFFECTED"
    integrity = "NOT AFFECTED"
    availability = "NOT AFFECTED"
    hard_block = False

    if redactions:
        confidentiality = "AFFECTED"
        reasons.append("Sensitive query material was removed: " + ", ".join(redactions))
        risk = _max_risk(risk, RiskLevel.MEDIUM)
    if hard_secret:
        risk = RiskLevel.CRITICAL
        hard_block = True
        reasons.append("Credentials and private keys may never be sent to web search")
    if request.contains_private_project_evidence:
        confidentiality = "AFFECTED"
        risk = _max_risk(risk, RiskLevel.HIGH)
        reasons.append("Private project evidence must be converted to public, minimal facts")

    if len(sanitized) > MAX_QUERY_CHARS:
        availability = "AFFECTED"
        risk = _max_risk(risk, RiskLevel.HIGH)
        reasons.append(f"Query exceeds the {MAX_QUERY_CHARS} character limit")

    budget_checks = (
        (request.max_queries, MAX_QUERIES_PER_QUESTION, "query count"),
        (request.max_sources, MAX_SOURCES_PER_QUESTION, "source count"),
        (request.max_chars_per_source, MAX_SOURCE_CHARS, "source character count"),
        (request.max_retries, MAX_RETRIES, "retry count"),
        (request.max_concurrency, MAX_CONCURRENCY, "concurrency"),
        (request.timeout_seconds, MAX_TIMEOUT_SECONDS, "timeout"),
    )
    for actual, maximum, label in budget_checks:
        if actual > maximum:
            availability = "AFFECTED"
            risk = _max_risk(risk, RiskLevel.HIGH)
            reasons.append(f"Requested {label} {actual} exceeds policy maximum {maximum}")
    if request.max_cost_usd > MAX_COST_USD:
        availability = "AFFECTED"
        risk = _max_risk(risk, RiskLevel.HIGH)
        reasons.append(
            f"Requested cost budget {request.max_cost_usd:.2f} exceeds policy maximum "
            f"{MAX_COST_USD:.2f}"
        )

    if _ZERO_WIDTH.search(request.query):
        integrity = "AFFECTED"
        risk = _max_risk(risk, RiskLevel.HIGH)
        reasons.append("Query contains invisible Unicode control characters")

    allowed = _policy_allows(
        risk,
        confirmed_high_risk=request.confirmed_high_risk,
        ethics_cleared=request.ethics_cleared,
        hard_block=hard_block,
    )
    action = _required_action(risk, allowed, hard_block=hard_block)
    if not reasons:
        reasons.append("Query and budgets pass deterministic CIA policy")
    return ResearchGateResult(
        allowed=allowed,
        risk_level=risk,
        confidentiality_status=confidentiality,
        integrity_status=integrity,
        availability_status=availability,
        reasons=tuple(reasons),
        required_action=action,
        sanitized_query=sanitized,
        override_permitted=not hard_block,
    )


def screen_source_candidate(source: SourceCandidate) -> ResearchGateResult:
    """Screen a discovered URL and snippet before the page is opened."""

    reasons: list[str] = []
    risk = RiskLevel.LOW
    confidentiality = "NOT AFFECTED"
    integrity = "NOT AFFECTED"
    availability = "NOT AFFECTED"
    hard_block = False
    canonical_url = ""
    trust_tier = source.trust_tier

    try:
        canonical_url = canonicalize_https_url(source.url)
    except ValueError as exc:
        integrity = "AFFECTED"
        if "credential" in str(exc).lower():
            confidentiality = "AFFECTED"
            risk = RiskLevel.CRITICAL
        else:
            risk = RiskLevel.HIGH
        hard_block = True
        reasons.append(str(exc))

    if canonical_url:
        parsed = urlsplit(canonical_url)
        host = (parsed.hostname or "").lower()
        if parsed.username or parsed.password:
            confidentiality = "AFFECTED"
            integrity = "AFFECTED"
            risk = RiskLevel.CRITICAL
            hard_block = True
            reasons.append("URL embeds credentials")
        if _is_private_or_local_host(host):
            confidentiality = "AFFECTED"
            integrity = "AFFECTED"
            availability = "AFFECTED"
            risk = RiskLevel.CRITICAL
            hard_block = True
            reasons.append("Local and private network destinations are forbidden")
        if host.startswith("xn--") or ".xn--" in host:
            integrity = "AFFECTED"
            risk = _max_risk(risk, RiskLevel.HIGH)
            hard_block = True
            reasons.append(
                "Internationalized hostname is blocked pending brokered identity "
                "verification"
            )
        if source.allowed_domains and not _host_allowed(host, source.allowed_domains):
            integrity = "AFFECTED"
            risk = _max_risk(risk, RiskLevel.MEDIUM)
            reasons.append("Source is outside the request domain allowlist")
        trust_tier = _derive_trust_tier(host, trust_tier)
        if trust_tier == "unclassified":
            integrity = "AFFECTED"
            risk = _max_risk(risk, RiskLevel.MEDIUM)
            reasons.append("Unclassified domain requires batch approval and cross check")

    for redirect in source.redirect_chain:
        try:
            redirect_url = canonicalize_https_url(redirect)
            redirect_host = (urlsplit(redirect_url).hostname or "").lower()
            if _is_private_or_local_host(redirect_host):
                raise ValueError("redirect targets a local or private network")
        except ValueError as exc:
            integrity = "AFFECTED"
            risk = RiskLevel.CRITICAL
            hard_block = True
            reasons.append(f"Unsafe redirect: {exc}")

    snippet_signals, snippet_severity = _detect_content_signals(
        f"{source.title}\n{source.snippet}"
    )
    if snippet_signals:
        integrity = "AFFECTED"
        risk = _max_risk(risk, snippet_severity)
        reasons.extend(f"Search metadata signal: {item}" for item in snippet_signals)

    if len(source.url) > 2_048 or len(source.snippet) > 10_000:
        availability = "AFFECTED"
        risk = _max_risk(risk, RiskLevel.HIGH)
        reasons.append("Source metadata exceeds policy size limits")

    allowed = _policy_allows(
        risk,
        confirmed_high_risk=source.confirmed_high_risk,
        ethics_cleared=source.ethics_cleared,
        hard_block=hard_block,
    )
    if not reasons:
        reasons.append("HTTPS source metadata passes deterministic CIA policy")
    return ResearchGateResult(
        allowed=allowed,
        risk_level=risk,
        confidentiality_status=confidentiality,
        integrity_status=integrity,
        availability_status=availability,
        reasons=tuple(reasons),
        required_action=_required_action(risk, allowed, hard_block=hard_block),
        canonical_url=canonical_url,
        trust_tier=trust_tier,
        override_permitted=not hard_block,
    )


def screen_retrieved_content(content: RetrievedContent) -> ContentScreenResult:
    """Screen retrieved text before any claim extraction or synthesis."""

    reasons: list[str] = []
    risk = RiskLevel.LOW
    confidentiality = "NOT AFFECTED"
    integrity = "NOT AFFECTED"
    availability = "NOT AFFECTED"
    hard_block = False

    try:
        canonicalize_https_url(content.url)
    except ValueError as exc:
        integrity = "AFFECTED"
        risk = RiskLevel.HIGH
        hard_block = True
        reasons.append(str(exc))

    lowered_type = content.content_type.lower().split(";", 1)[0].strip()
    allowed_types = {"text/html", "text/plain", "application/json", "application/pdf"}
    if lowered_type not in allowed_types:
        integrity = "AFFECTED"
        risk = RiskLevel.CRITICAL if "executable" in lowered_type else RiskLevel.HIGH
        hard_block = True
        reasons.append(f"Unsupported content type: {lowered_type or 'missing'}")

    if len(content.text) > content.max_chars:
        availability = "AFFECTED"
        risk = _max_risk(risk, RiskLevel.HIGH)
        reasons.append(
            f"Retrieved content exceeds the {content.max_chars} character synthesis limit"
        )

    _, sensitive_matches, hard_secret = redact_sensitive_text(content.text)
    if sensitive_matches:
        confidentiality = "AFFECTED"
        risk = _max_risk(
            risk, RiskLevel.CRITICAL if hard_secret else RiskLevel.MEDIUM
        )
        hard_block = hard_block or hard_secret
        reasons.append(
            "Retrieved content contains sensitive material: "
            + ", ".join(sensitive_matches)
        )

    signals, signal_severity = _detect_content_signals(content.text)
    if signals:
        integrity = "AFFECTED"
        risk = _max_risk(risk, signal_severity)
        reasons.extend(f"Untrusted content signal: {item}" for item in signals)

    flagged_attack = bool(signals) and _RISK_ORDER[signal_severity] >= _RISK_ORDER[
        RiskLevel.HIGH
    ]
    policy_allowed = _policy_allows(
        risk,
        confirmed_high_risk=content.confirmed_high_risk,
        ethics_cleared=content.ethics_cleared,
        hard_block=hard_block,
    )
    allowed = policy_allowed and not flagged_attack
    if not reasons:
        reasons.append("Retrieved text passes deterministic content screening")
    if flagged_attack:
        transparency = (
            "Agent Shield flagged untrusted web content and withheld it from answer synthesis."
        )
        required_action = "Keep quarantined; do not use this payload for synthesis"
    elif signals:
        transparency = (
            "Agent Shield found a review warning but no configured injection signal; "
            "source claims still require cross check."
        )
        required_action = _required_action(risk, allowed, hard_block=hard_block)
    else:
        transparency = (
            "Agent Shield found no configured injection signal; source claims still "
            "require cross check."
        )
        required_action = _required_action(risk, allowed, hard_block=hard_block)
    return ContentScreenResult(
        allowed=allowed,
        risk_level=risk,
        confidentiality_status=confidentiality,
        integrity_status=integrity,
        availability_status=availability,
        reasons=tuple(reasons),
        required_action=required_action,
        content_sha256=_sha256_text(content.text),
        quarantine_required=not allowed or flagged_attack,
        flagged_attack=flagged_attack,
        transparency_message=transparency,
    )


def build_approval_manifest(sources: list[SourceCandidate]) -> ApprovalManifest:
    """Build a deterministic source manifest for bounded human approval."""

    if not sources:
        raise ValueError("sources must be nonempty")
    if len(sources) > MAX_SOURCES_PER_BATCH:
        raise ValueError(
            f"source batch has {len(sources)} entries; maximum is {MAX_SOURCES_PER_BATCH}"
        )
    source_ids = [source.source_id for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source_id values must be unique within a manifest")

    rows: list[dict[str, Any]] = []
    for source in sorted(sources, key=lambda item: item.source_id):
        result = screen_source_candidate(source)
        rows.append(
            {
                "request_id": source.request_id,
                "qid": source.qid,
                "source_id": source.source_id,
                "url": result.canonical_url or _safe_rejected_url(source.url),
                "title": source.title,
                "discovered_via": source.discovered_via,
                "trust_tier": result.trust_tier,
                "screening": result.to_dict(),
            }
        )
    digest = _manifest_digest(RULESET_VERSION, rows)
    return ApprovalManifest(
        batch_id=f"BATCH_{digest[:12].upper()}",
        created_at=_now(),
        manifest_sha256=digest,
        sources=tuple(rows),
    )


def validate_approval_manifest(manifest: ApprovalManifest) -> None:
    """Reject stale or mutated manifest data before approval or retrieval."""

    if manifest.ruleset_version != RULESET_VERSION:
        raise ValueError(
            f"manifest ruleset {manifest.ruleset_version!r} is stale; expected "
            f"{RULESET_VERSION!r}"
        )
    expected_digest = _manifest_digest(
        manifest.ruleset_version, list(manifest.sources)
    )
    if not hmac.compare_digest(expected_digest, manifest.manifest_sha256):
        raise ValueError("manifest source data does not match manifest_sha256")
    expected_batch_id = f"BATCH_{expected_digest[:12].upper()}"
    if manifest.batch_id != expected_batch_id:
        raise ValueError("manifest batch_id does not match manifest_sha256")


def append_audit_event(event: ResearchAuditEvent, audit_dir: Path) -> None:
    """Append one sanitized JSON event, skipping an existing event ID."""

    audit_path = Path(audit_dir) / "audit" / "events.jsonl"
    audit_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if audit_path.exists():
        for line in audit_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("event_id") == event.event_id:
                    return
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid audit line in {audit_path}: {exc}") from exc
    payload = json.dumps(event.to_dict(), sort_keys=True, ensure_ascii=False) + "\n"
    descriptor = os.open(audit_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        _write_all(descriptor, payload.encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.chmod(audit_path, 0o600)


def write_manifest(manifest: ApprovalManifest, audit_dir: Path) -> Path:
    """Persist an immutable manifest with owner only permissions."""

    validate_approval_manifest(manifest)
    target = Path(audit_dir) / "manifests" / f"{manifest.batch_id}.json"
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8"))
        comparable_existing = {
            "manifest_sha256": existing.get("manifest_sha256"),
            "ruleset_version": existing.get("ruleset_version"),
            "sources": existing.get("sources"),
        }
        comparable_new = {
            "manifest_sha256": manifest.manifest_sha256,
            "ruleset_version": manifest.ruleset_version,
            "sources": list(manifest.sources),
        }
        if comparable_existing != comparable_new:
            raise FileExistsError(
                f"manifest path already contains different source data: {target}"
            )
        os.chmod(target, 0o600)
        return target
    payload = manifest.to_dict()
    payload.update(
        {
            "status": "awaiting_approval",
            "approved": False,
            "supersedes": None,
            "superseded_by": None,
        }
    )
    _write_private_json_once(target, payload)
    return target


def record_manifest_approval(
    manifest: ApprovalManifest,
    audit_dir: Path,
    *,
    manifest_path: Path,
    approved_by: str | None = None,
    confirm_high_risk: bool = False,
    ethics_cleared: bool = False,
) -> Path:
    """Atomically approve a manifest file and record its authoritative event."""

    check_manifest_approval_policy(
        manifest,
        approved_by=approved_by,
        confirm_high_risk=confirm_high_risk,
        ethics_cleared=ethics_cleared,
    )
    manifest_file_sha256 = transition_manifest_to_approved(manifest_path, manifest)
    return _record_manifest_approval_event(
        manifest,
        audit_dir,
        manifest_file_sha256=manifest_file_sha256,
        approved_by=approved_by,
        confirm_high_risk=confirm_high_risk,
        ethics_cleared=ethics_cleared,
    )


def _record_manifest_approval_event(
    manifest: ApprovalManifest,
    audit_dir: Path,
    *,
    manifest_file_sha256: str,
    approved_by: str | None = None,
    confirm_high_risk: bool = False,
    ethics_cleared: bool = False,
) -> Path:
    """Write the immutable record for an already transitioned manifest."""

    _require_sha256("manifest_file_sha256", manifest_file_sha256)
    local_actor = check_manifest_approval_policy(
        manifest,
        approved_by=approved_by,
        confirm_high_risk=confirm_high_risk,
        ethics_cleared=ethics_cleared,
    )

    approved_at = _now()
    approval = {
        "batch_id": manifest.batch_id,
        "manifest_sha256": manifest.manifest_sha256,
        "manifest_file_sha256": manifest_file_sha256,
        "approved_at": approved_at,
        "approved_by": local_actor,
        "local_actor_username": local_actor,
        "local_actor_uid": os.getuid() if hasattr(os, "getuid") else None,
        "confirmation_method": "interactive_exact_manifest_hash",
        "confirm_high_risk": confirm_high_risk,
        "ethics_cleared": ethics_cleared,
        "ruleset_version": RULESET_VERSION,
    }
    target = (
        Path(audit_dir)
        / "manifests"
        / "approvals"
        / f"{manifest.manifest_sha256}.json"
    )
    if target.exists():
        existing = json.loads(target.read_text(encoding="utf-8"))
        if existing.get("manifest_sha256") != manifest.manifest_sha256:
            raise FileExistsError(f"approval path contains a different manifest: {target}")
        stable_fields = (
            "manifest_file_sha256",
            "approved_by",
            "local_actor_username",
            "local_actor_uid",
            "confirmation_method",
            "confirm_high_risk",
            "ethics_cleared",
            "ruleset_version",
        )
        if any(existing.get(field) != approval.get(field) for field in stable_fields):
            raise FileExistsError(
                "manifest already has an immutable approval from a different actor or "
                "policy state"
            )
        os.chmod(target, 0o600)
        approval = existing
    else:
        _write_private_json_once(target, approval)

    append_audit_event(
        ResearchAuditEvent(
            event_id=_stable_event_id(
                "EVT_APPROVAL",
                manifest.manifest_sha256,
                manifest_file_sha256,
            ),
            event_type="approval_recorded",
            request_id="BATCH",
            qid="MULTIPLE",
            decision="approved",
            timestamp=str(approval["approved_at"]),
            manifest_sha256=manifest.manifest_sha256,
            details={
                "batch_id": manifest.batch_id,
                "manifest_file_sha256": manifest_file_sha256,
                "ruleset_version": RULESET_VERSION,
                "approved_by_os_account": approval["local_actor_username"],
                "local_actor_uid": approval["local_actor_uid"],
                "approval_timestamp": approval["approved_at"],
                "confirmation_method": approval["confirmation_method"],
                "confirm_high_risk": approval["confirm_high_risk"],
                "ethics_cleared": approval["ethics_cleared"],
            },
        ),
        audit_dir,
    )
    return target


def check_manifest_approval_policy(
    manifest: ApprovalManifest,
    *,
    approved_by: str | None = None,
    confirm_high_risk: bool = False,
    ethics_cleared: bool = False,
) -> str:
    """Validate approval policy before any manifest lifecycle mutation."""

    validate_approval_manifest(manifest)
    local_actor = getpass.getuser()
    if approved_by is not None and not hmac.compare_digest(
        approved_by.strip(), local_actor
    ):
        raise PermissionError("approved_by must match the local OS account")
    levels = {
        RiskLevel(row["screening"]["risk_level"])
        for row in manifest.sources
    }
    highest = max(levels, key=lambda level: _RISK_ORDER[level])
    if highest in {RiskLevel.HIGH, RiskLevel.CRITICAL} and not confirm_high_risk:
        raise PermissionError("high risk manifest approval requires explicit confirmation")
    if highest is RiskLevel.CRITICAL and not ethics_cleared:
        raise PermissionError("critical manifest approval requires ethics clearance")
    if any(
        not row["screening"].get(
            "override_permitted", row["screening"]["allowed"]
        )
        for row in manifest.sources
    ):
        raise PermissionError("manifest contains a non overridable blocked source")

    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", local_actor):
        raise ValueError(
            "local OS account must be a non email principal ID using letters, numbers, dot, "
            "underscore, or hyphen"
        )

    return local_actor


def transition_manifest_to_approved(
    path: Path,
    manifest: ApprovalManifest,
) -> str:
    """Atomically transition a pending manifest and return its resulting file hash."""

    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("manifest file must contain an object")
    if (
        payload.get("batch_id") != manifest.batch_id
        or payload.get("manifest_sha256") != manifest.manifest_sha256
        or payload.get("ruleset_version") != manifest.ruleset_version
        or payload.get("sources") != list(manifest.sources)
    ):
        raise PermissionError("manifest file bytes do not match the validated manifest")
    status = payload.get("status")
    approved = payload.get("approved")
    if status == "awaiting_approval" and approved is False:
        payload["status"] = "approved"
        payload["approved"] = True
        _replace_private_json(target, payload)
    elif status != "approved" or approved is not True:
        raise PermissionError("manifest is not in an approvable lifecycle state")
    return hashlib.sha256(target.read_bytes()).hexdigest()


def manifest_is_approved(
    manifest_sha256: str,
    audit_dir: Path,
    *,
    manifest_file_sha256: str,
    ruleset_version: str = RULESET_VERSION,
) -> bool:
    """Return whether record and audit event approve the exact manifest bytes."""

    _require_sha256("manifest_sha256", manifest_sha256)
    _require_sha256("manifest_file_sha256", manifest_file_sha256)
    target = (
        Path(audit_dir)
        / "manifests"
        / "approvals"
        / f"{manifest_sha256}.json"
    )
    if not target.exists():
        return False
    os.chmod(target, 0o600)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid approval record {target}: {exc}") from exc
    current_uid = os.getuid() if hasattr(os, "getuid") else None
    expected = {
        "manifest_sha256": manifest_sha256,
        "manifest_file_sha256": manifest_file_sha256,
        "ruleset_version": ruleset_version,
        "confirmation_method": "interactive_exact_manifest_hash",
    }
    if any(data.get(key) != value for key, value in expected.items()):
        return False
    if data.get("approved_by") != data.get("local_actor_username"):
        return False
    if data.get("local_actor_uid") != current_uid:
        return False

    matching_events = []
    for event in _load_audit_events_strict(audit_dir):
        details = event.get("details")
        if not isinstance(details, Mapping):
            continue
        if (
            event.get("event_type") == "approval_recorded"
            and event.get("decision") == "approved"
            and event.get("manifest_sha256") == manifest_sha256
            and details.get("batch_id") == data.get("batch_id")
            and details.get("manifest_file_sha256") == manifest_file_sha256
            and details.get("ruleset_version") == ruleset_version
            and details.get("approved_by_os_account")
            == data.get("local_actor_username")
            and details.get("local_actor_uid") == data.get("local_actor_uid")
            and details.get("approval_timestamp") == data.get("approved_at")
            and details.get("confirmation_method") == data.get("confirmation_method")
            and details.get("confirm_high_risk") == data.get("confirm_high_risk")
            and details.get("ethics_cleared") == data.get("ethics_cleared")
        ):
            matching_events.append(event)
    return len(matching_events) == 1


def record_independent_review(
    review_note: Path,
    review_root: Path,
    audit_dir: Path,
) -> Path:
    """Bind a final independent review note to an immutable audit event."""

    note_path = Path(review_note).resolve()
    root_path = Path(review_root).resolve()
    try:
        portable_path = note_path.relative_to(root_path).as_posix()
    except ValueError as exc:
        raise ValueError("review note must be inside review_root") from exc
    raw = note_path.read_bytes()
    metadata = _parse_frontmatter(raw.decode("utf-8"))
    required = (
        "reviewer_kind",
        "reviewer_session_id",
        "review_run_id",
        "reviewed_batch_id",
        "reviewed_manifest_sha256",
        "reviewed_commit_sha",
        "review_started_at",
        "review_completed_at",
        "review_context",
        "attestation_status",
    )
    missing = [name for name in required if not metadata.get(name)]
    if missing:
        raise ValueError("review note missing attestation fields: " + ", ".join(missing))
    if metadata["reviewer_kind"] != "claude_code":
        raise ValueError("reviewer_kind must be claude_code")
    if metadata["review_context"] != "fresh":
        raise ValueError("review_context must be fresh")
    if metadata["attestation_status"] != "recorded":
        raise ValueError("attestation_status must be recorded before attestation")
    try:
        uuid.UUID(metadata["review_run_id"])
    except ValueError as exc:
        raise ValueError("review_run_id must be a UUID") from exc
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,160}", metadata["reviewer_session_id"]):
        raise ValueError("reviewer_session_id has invalid characters")
    _require_sha256("reviewed_manifest_sha256", metadata["reviewed_manifest_sha256"])
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", metadata["reviewed_commit_sha"]):
        raise ValueError("reviewed_commit_sha must be a full Git digest")
    for field_name in ("review_started_at", "review_completed_at"):
        try:
            datetime.fromisoformat(metadata[field_name].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO 8601 timestamp") from exc

    note_sha256 = hashlib.sha256(raw).hexdigest()
    record = {
        "reviewer_kind": metadata["reviewer_kind"],
        "reviewer_session_id": metadata["reviewer_session_id"],
        "review_run_id": metadata["review_run_id"],
        "reviewed_batch_id": metadata["reviewed_batch_id"],
        "reviewed_manifest_sha256": metadata["reviewed_manifest_sha256"],
        "reviewed_commit_sha": metadata["reviewed_commit_sha"],
        "review_started_at": metadata["review_started_at"],
        "review_completed_at": metadata["review_completed_at"],
        "review_context": metadata["review_context"],
        "attestation_status": metadata["attestation_status"],
        "control_plane_verdict": metadata.get("control_plane_verdict", ""),
        "review_note_path": portable_path,
        "review_note_sha256": note_sha256,
        "recorded_at": _now(),
        "ruleset_version": RULESET_VERSION,
    }
    target = (
        Path(audit_dir)
        / "reviews"
        / f"{metadata['review_run_id']}.json"
    )
    _write_private_json_once(target, record)
    append_audit_event(
        ResearchAuditEvent(
            event_id=_stable_event_id(
                "EVT_REVIEW",
                metadata["review_run_id"],
                note_sha256,
            ),
            event_type="independent_review_recorded",
            request_id=metadata["review_run_id"],
            qid="MULTIPLE",
            decision="recorded",
            manifest_sha256=metadata["reviewed_manifest_sha256"],
            details=record,
        ),
        audit_dir,
    )
    return target


def independent_review_is_recorded(
    review_note: Path,
    review_root: Path,
    audit_dir: Path,
) -> bool:
    """Verify an independent review record and event against current note bytes."""

    note_path = Path(review_note).resolve()
    root_path = Path(review_root).resolve()
    try:
        portable_path = note_path.relative_to(root_path).as_posix()
    except ValueError:
        return False
    raw = note_path.read_bytes()
    metadata = _parse_frontmatter(raw.decode("utf-8"))
    review_run_id = metadata.get("review_run_id", "")
    if not review_run_id:
        return False
    target = Path(audit_dir) / "reviews" / f"{review_run_id}.json"
    if not target.exists():
        return False
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid independent review record {target}: {exc}") from exc
    note_sha256 = hashlib.sha256(raw).hexdigest()
    fields = {
        "reviewer_kind": metadata.get("reviewer_kind"),
        "reviewer_session_id": metadata.get("reviewer_session_id"),
        "review_run_id": review_run_id,
        "reviewed_batch_id": metadata.get("reviewed_batch_id"),
        "reviewed_manifest_sha256": metadata.get("reviewed_manifest_sha256"),
        "reviewed_commit_sha": metadata.get("reviewed_commit_sha"),
        "review_started_at": metadata.get("review_started_at"),
        "review_completed_at": metadata.get("review_completed_at"),
        "review_context": metadata.get("review_context"),
        "attestation_status": metadata.get("attestation_status"),
        "control_plane_verdict": metadata.get("control_plane_verdict", ""),
        "review_note_path": portable_path,
        "review_note_sha256": note_sha256,
    }
    if any(record.get(key) != value for key, value in fields.items()):
        return False
    matching_events = []
    for event in _load_audit_events_strict(audit_dir):
        details = event.get("details")
        if not isinstance(details, Mapping):
            continue
        if (
            event.get("event_type") == "independent_review_recorded"
            and event.get("decision") == "recorded"
            and event.get("manifest_sha256") == fields["reviewed_manifest_sha256"]
            and all(details.get(key) == value for key, value in fields.items())
        ):
            matching_events.append(event)
    return len(matching_events) == 1


def store_quarantine_payload(content: RetrievedContent, audit_dir: Path) -> Path:
    """Store the exact native tool payload by content hash with mode 0600."""

    digest = _sha256_text(content.text)
    target = Path(audit_dir) / "quarantine" / f"{digest}.txt"
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = content.text.encode("utf-8")
    if target.exists():
        if target.read_bytes() != encoded:
            raise ValueError(f"quarantine hash collision at {target}")
        os.chmod(target, 0o600)
        return target
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        _write_all(descriptor, encoded)
        os.fsync(descriptor)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        os.close(descriptor)
    os.chmod(target, 0o600)
    return target


def evaluate_research_cases(cases: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Map deterministic screening fixtures into Agent Shield metric rows."""

    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["id"])
        malicious = bool(case["malicious"])
        content = RetrievedContent(
            request_id=f"REQ_{case_id}",
            qid=f"Q_{case_id}",
            source_id=f"SRC_{case_id}",
            url=str(case.get("url", "https://example.org/source")),
            text=str(case["text"]),
            content_type=str(case.get("content_type", "text/html")),
            manifest_sha256="0" * 64,
        )
        result = screen_retrieved_content(content)
        attack_success = malicious and result.allowed
        over_refusal = (not malicious) and (not result.allowed)
        rows.append(
            {
                "case_id": case_id,
                "category": str(case.get("category", "prompt_injection")),
                "severity": str(case.get("severity", "high")),
                "benign": not malicious,
                "attack_success": attack_success,
                "passed": (not result.allowed) if malicious else result.allowed,
                "refusal_quality": "over_refusal" if over_refusal else "none",
                "tool_called": False,
                "tool_name": None,
                "tool_safe": None,
                "rag_poisoned": malicious,
                "memory_poisoned": False,
                "failure_mode": "unsafe_content_allowed" if attack_success else None,
                "flagged_attack": result.flagged_attack,
                "notes": result.transparency_message,
            }
        )
    return rows


def redact_sensitive_text(text: str) -> tuple[str, tuple[str, ...], bool]:
    """Return redacted text, unique labels, and whether a hard secret appeared."""

    sanitized = text
    labels: list[str] = []
    hard_secret = False
    for label, pattern, replacement in _SECRET_PATTERNS:
        if pattern.search(sanitized):
            sanitized = pattern.sub(replacement, sanitized)
            labels.append(label)
            if label in {
                "private key",
                "bearer token",
                "basic auth credential",
                "API credential",
                "AWS access key",
            }:
                hard_secret = True
    return sanitized, tuple(dict.fromkeys(labels)), hard_secret


def sanitize_for_audit(value: Any) -> Any:
    """Recursively redact secrets and personal identifiers from audit values."""

    if isinstance(value, str):
        return redact_sensitive_text(value)[0]
    if isinstance(value, Mapping):
        return {str(key): sanitize_for_audit(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_audit(item) for item in value]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_sensitive_text(str(value))[0]


def canonicalize_https_url(url: str) -> str:
    """Return a fragment free HTTPS URL or raise for unsafe schemes and hosts."""

    parsed = urlsplit(url.strip())
    if parsed.scheme.lower() != "https":
        raise ValueError("HTTPS is required; non HTTPS sources are forbidden")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname")
    if parsed.username or parsed.password:
        raise ValueError("URL embeds credentials; userinfo is forbidden")
    sensitive_query_keys = {
        "api_key",
        "apikey",
        "access_token",
        "token",
        "password",
        "secret",
    }
    if any(key.lower() in sensitive_query_keys for key, _ in parse_qsl(parsed.query)):
        raise ValueError("URL query contains a credential parameter")
    if parsed.port not in (None, 443):
        raise ValueError("HTTPS source uses a nonstandard port")
    host = parsed.hostname.lower().rstrip(".")
    if not host.isascii():
        raise ValueError(
            "URL hostname contains non ASCII identity characters; use a verified ASCII "
            "source hostname"
        )
    if any(char.isspace() for char in host):
        raise ValueError("URL hostname contains whitespace")
    return urlunsplit(("https", host, parsed.path or "/", parsed.query, ""))


def _safe_rejected_url(url: str) -> str:
    """Return rejected source metadata without userinfo, query data, or fragments."""

    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        return "[REDACTED_INVALID_URL]"
    if not parsed.hostname:
        safe_path = redact_sensitive_text(parsed.path)[0]
        return urlunsplit((parsed.scheme.lower(), "", safe_path, "", ""))
    host = parsed.hostname.lower().rstrip(".")
    safe_path = redact_sensitive_text(parsed.path or "/")[0]
    return urlunsplit((parsed.scheme.lower(), host, safe_path, "", ""))


def _detect_content_signals(text: str) -> tuple[tuple[str, ...], RiskLevel]:
    signals: list[str] = []
    severity = RiskLevel.LOW
    if _ZERO_WIDTH.search(text):
        signals.append("invisible Unicode control characters")
        severity = RiskLevel.HIGH
    for label, pattern in _STRONG_CONTENT_SIGNALS:
        if pattern.search(text):
            signals.append(label)
            severity = _max_risk(severity, RiskLevel.HIGH)
    for label, pattern in _MEDIUM_CONTENT_SIGNALS:
        if pattern.search(text):
            signals.append(label)
            severity = _max_risk(severity, RiskLevel.MEDIUM)
    return tuple(dict.fromkeys(signals)), severity


def _sensitive_labels(text: str) -> tuple[str, ...]:
    return redact_sensitive_text(text)[1]


def _derive_trust_tier(host: str, supplied: str) -> str:
    normalized = supplied.strip().lower()
    if normalized and normalized != "unclassified":
        return normalized
    if host in _PRIMARY_HOSTS or host.endswith(".gov") or host.endswith(".edu"):
        return "primary"
    return "unclassified"


def _is_private_or_local_host(host: str) -> bool:
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return bool(
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def _host_allowed(host: str, allowed_domains: tuple[str, ...]) -> bool:
    for domain in allowed_domains:
        normalized = domain.lower().strip().lstrip(".")
        if host == normalized or host.endswith("." + normalized):
            return True
    return False


def _policy_allows(
    risk: RiskLevel,
    *,
    confirmed_high_risk: bool,
    ethics_cleared: bool,
    hard_block: bool,
) -> bool:
    if hard_block:
        return False
    if risk in {RiskLevel.LOW, RiskLevel.MEDIUM}:
        return True
    if risk is RiskLevel.HIGH:
        return confirmed_high_risk
    return confirmed_high_risk and ethics_cleared


def _required_action(risk: RiskLevel, allowed: bool, *, hard_block: bool) -> str:
    if hard_block:
        return "Remove forbidden sensitive data or unsafe destination; policy override is disabled"
    if allowed and risk in {RiskLevel.LOW, RiskLevel.MEDIUM}:
        return "Proceed under the bounded source approval workflow"
    if allowed:
        return "Proceed with recorded high risk approval and monitoring"
    if risk is RiskLevel.CRITICAL:
        return "Require explicit high risk confirmation and ethics clearance"
    return "Require explicit high risk confirmation"


def _max_risk(left: RiskLevel, right: RiskLevel) -> RiskLevel:
    return left if _RISK_ORDER[left] >= _RISK_ORDER[right] else right


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


def _require_sha256(name: str, value: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(f"{name} must be a lowercase SHA256 digest")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))
    return _sha256_text(encoded)


def _manifest_digest(ruleset_version: str, sources: list[dict[str, Any]]) -> str:
    return _sha256_json(
        {
            "ruleset_version": ruleset_version,
            "sources": sources,
        }
    )


def _stable_event_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _load_audit_events_strict(audit_dir: Path) -> list[dict[str, Any]]:
    path = Path(audit_dir) / "audit" / "events.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid audit line {line_number} in {path}: {exc}") from exc
        if not isinstance(event, dict):
            raise ValueError(f"audit line {line_number} in {path} is not an object")
        events.append(event)
    return events


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return values


def _jsonable(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _replace_private_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = (json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n").encode()
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        try:
            os.fchmod(descriptor, 0o600)
            _write_all(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary_path, path)
        os.chmod(path, 0o600)
    finally:
        temporary_path.unlink(missing_ok=True)


def _write_private_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    encoded = (json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n").encode()
    if path.exists():
        if path.read_bytes() != encoded:
            raise FileExistsError(f"immutable record already exists with different content: {path}")
        os.chmod(path, 0o600)
        return
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        try:
            os.fchmod(descriptor, 0o600)
            _write_all(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.link(temporary_path, path)
    except FileExistsError:
        if path.read_bytes() != encoded:
            raise FileExistsError(
                f"immutable record already exists with different content: {path}"
            ) from None
    finally:
        temporary_path.unlink(missing_ok=True)
    os.chmod(path, 0o600)


def _write_all(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("write returned no progress")
        remaining = remaining[written:]


__all__ = [
    "CONTENT_RULESET_VERSION",
    "ApprovalManifest",
    "ContentScreenResult",
    "ResearchAuditEvent",
    "ResearchGateResult",
    "ResearchRequest",
    "RetrievedContent",
    "RiskLevel",
    "SourceCandidate",
    "append_audit_event",
    "build_approval_manifest",
    "canonicalize_https_url",
    "check_manifest_approval_policy",
    "evaluate_research_cases",
    "independent_review_is_recorded",
    "manifest_is_approved",
    "record_independent_review",
    "record_manifest_approval",
    "redact_sensitive_text",
    "sanitize_for_audit",
    "screen_research_request",
    "screen_retrieved_content",
    "screen_source_candidate",
    "store_quarantine_payload",
    "transition_manifest_to_approved",
    "validate_approval_manifest",
    "write_manifest",
]

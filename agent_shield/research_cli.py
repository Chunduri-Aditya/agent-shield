"""Command line interface for the Agent Shield research sidecar."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from agent_shield.research import (
    RULESET_VERSION,
    ApprovalManifest,
    ResearchAuditEvent,
    ResearchRequest,
    RetrievedContent,
    SourceCandidate,
    append_audit_event,
    build_approval_manifest,
    canonicalize_https_url,
    manifest_is_approved,
    record_independent_review,
    record_manifest_approval,
    screen_research_request,
    screen_retrieved_content,
    store_quarantine_payload,
    validate_approval_manifest,
    write_manifest,
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_stdout(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _event_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _confirm_manifest_interactively(manifest: ApprovalManifest) -> None:
    if not sys.stdin.isatty():
        raise PermissionError(
            "batch approval requires an interactive terminal; piped approval is forbidden"
        )
    entered = input(
        "Type the full manifest SHA256 to approve this exact source set: "
    ).strip()
    if not hmac.compare_digest(entered, manifest.manifest_sha256):
        raise PermissionError("typed manifest SHA256 does not match")


def _request_from_dict(data: dict[str, Any]) -> ResearchRequest:
    copied = dict(data)
    copied["allowed_domains"] = tuple(copied.get("allowed_domains", ()))
    return ResearchRequest(**copied)


def _source_from_dict(data: dict[str, Any]) -> SourceCandidate:
    copied = dict(data)
    copied["allowed_domains"] = tuple(copied.get("allowed_domains", ()))
    copied["redirect_chain"] = tuple(copied.get("redirect_chain", ()))
    return SourceCandidate(**copied)


def _content_from_dict(data: dict[str, Any], text: str) -> RetrievedContent:
    copied = dict(data)
    copied["text"] = text
    return RetrievedContent(**copied)


def _manifest_from_dict(data: dict[str, Any]) -> ApprovalManifest:
    manifest = ApprovalManifest(
        batch_id=data["batch_id"],
        created_at=data["created_at"],
        manifest_sha256=data["manifest_sha256"],
        sources=tuple(data["sources"]),
        ruleset_version=data.get("ruleset_version", RULESET_VERSION),
    )
    validate_approval_manifest(manifest)
    return manifest


def _cmd_preflight(args: argparse.Namespace) -> int:
    request = _request_from_dict(_read_json(args.request_json))
    result = screen_research_request(request)
    append_audit_event(
        ResearchAuditEvent(
            event_id=_event_id("EVT_PREFLIGHT", request.request_id, request.qid),
            event_type="search_preflight",
            request_id=request.request_id,
            qid=request.qid,
            decision="allowed" if result.allowed else "blocked",
            details={
                "result": result.to_dict(),
                "purpose": request.purpose,
                "allowed_domains": request.allowed_domains,
            },
        ),
        args.audit_dir,
    )
    _write_stdout(result.to_dict())
    return 0 if result.allowed else 2


def _cmd_register_sources(args: argparse.Namespace) -> int:
    raw = _read_json(args.sources_json)
    if not isinstance(raw, list):
        raise TypeError("sources JSON must contain a list")
    sources = [_source_from_dict(item) for item in raw]
    manifest = build_approval_manifest(sources)
    manifest_path = write_manifest(manifest, args.audit_dir)
    for source, row in zip(
        sorted(sources, key=lambda item: item.source_id),
        manifest.sources,
        strict=True,
    ):
        screening = row["screening"]
        append_audit_event(
            ResearchAuditEvent(
                event_id=_event_id(
                    "EVT_SOURCE",
                    manifest.manifest_sha256,
                    source.source_id,
                ),
                event_type="source_discovered",
                request_id=source.request_id,
                qid=source.qid,
                source_id=source.source_id,
                decision="candidate_allowed" if screening["allowed"] else "candidate_blocked",
                manifest_sha256=manifest.manifest_sha256,
                details={
                    "url": row["url"],
                    "title": row["title"],
                    "trust_tier": row["trust_tier"],
                    "screening": screening,
                },
            ),
            args.audit_dir,
        )
    append_audit_event(
        ResearchAuditEvent(
            event_id=_event_id("EVT_MANIFEST", manifest.manifest_sha256),
            event_type="approval_manifest_created",
            request_id="BATCH",
            qid="MULTIPLE",
            decision="awaiting_approval",
            manifest_sha256=manifest.manifest_sha256,
            details={
                "batch_id": manifest.batch_id,
                "source_count": len(manifest.sources),
                "manifest_path": str(manifest_path),
            },
        ),
        args.audit_dir,
    )
    _write_stdout({"manifest_path": str(manifest_path), **manifest.to_dict()})
    return 0


def _cmd_approve_batch(args: argparse.Namespace) -> int:
    manifest = _manifest_from_dict(_read_json(args.manifest))
    _confirm_manifest_interactively(manifest)
    approval_path = record_manifest_approval(
        manifest,
        args.audit_dir,
        manifest_path=args.manifest,
        approved_by=args.approved_by,
        confirm_high_risk=args.confirm_high_risk,
        ethics_cleared=args.ethics_cleared,
    )
    manifest_file_sha256 = _file_sha256(args.manifest)
    _write_stdout(
        {
            "approved": True,
            "batch_id": manifest.batch_id,
            "manifest_sha256": manifest.manifest_sha256,
            "manifest_file_sha256": manifest_file_sha256,
            "approval_path": str(approval_path),
        }
    )
    return 0


def _cmd_screen_content(args: argparse.Namespace) -> int:
    manifest = _manifest_from_dict(_read_json(args.manifest))
    metadata = _read_json(args.metadata_json)
    source_id = metadata["source_id"]
    known_sources = {row["source_id"]: row for row in manifest.sources}
    if source_id not in known_sources:
        raise PermissionError(f"source {source_id!r} is not present in the approved manifest")
    if not manifest_is_approved(
        manifest.manifest_sha256,
        args.audit_dir,
        manifest_file_sha256=_file_sha256(args.manifest),
        ruleset_version=manifest.ruleset_version,
    ):
        raise PermissionError("manifest has no matching approval record")
    if metadata.get("manifest_sha256") != manifest.manifest_sha256:
        raise PermissionError("retrieval metadata does not match the approved manifest hash")
    manifest_source = known_sources[source_id]
    if metadata.get("qid") != manifest_source["qid"]:
        raise PermissionError("retrieval QID does not match the approved source")
    if metadata.get("request_id") != manifest_source["request_id"]:
        raise PermissionError("retrieval request ID does not match the approved source")
    if canonicalize_https_url(metadata.get("url", "")) != manifest_source["url"]:
        raise PermissionError("retrieval URL does not match the approved source")

    text = args.content.read_text(encoding="utf-8")
    content = _content_from_dict(metadata, text)
    quarantine_path = store_quarantine_payload(content, args.audit_dir)
    result = screen_retrieved_content(content)
    append_audit_event(
        ResearchAuditEvent(
            event_id=_event_id(
                "EVT_CONTENT",
                manifest.manifest_sha256,
                source_id,
                result.content_sha256,
                result.content_ruleset_version,
            ),
            event_type="retrieved_content_screened",
            request_id=content.request_id,
            qid=content.qid,
            source_id=source_id,
            decision="safe_for_synthesis" if result.allowed else "quarantined",
            manifest_sha256=manifest.manifest_sha256,
            details={
                "url": content.url,
                "content_type": content.content_type,
                "content_sha256": result.content_sha256,
                "character_count": len(content.text),
                "quarantine_path": str(quarantine_path),
                "result": result.to_dict(),
            },
        ),
        args.audit_dir,
    )
    _write_stdout({"quarantine_path": str(quarantine_path), **result.to_dict()})
    return 0 if result.allowed else 2


def _cmd_record_claim(args: argparse.Namespace) -> int:
    claim = _read_json(args.claim_json)
    required = {
        "claim_id",
        "qid",
        "request_id",
        "manifest_sha256",
        "source_evidence",
        "source_ids",
        "paraphrase",
    }
    missing = sorted(required - set(claim))
    if missing:
        raise ValueError("claim record missing fields: " + ", ".join(missing))
    source_ids = claim["source_ids"]
    if (
        not isinstance(source_ids, list)
        or not source_ids
        or any(not isinstance(source_id, str) or not source_id for source_id in source_ids)
    ):
        raise ValueError("claim source_ids must be a nonempty list")
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("claim source_ids must be unique")
    source_evidence = claim["source_evidence"]
    if not isinstance(source_evidence, list) or not source_evidence:
        raise ValueError("claim source_evidence must be a nonempty list")
    evidence_by_source: dict[str, tuple[str, str]] = {}
    for item in source_evidence:
        if not isinstance(item, dict):
            raise ValueError("claim source_evidence entries must be objects")
        source_id = item.get("source_id")
        content_sha256 = item.get("content_sha256")
        screen_event_id = item.get("screen_event_id")
        if not isinstance(source_id, str) or not source_id:
            raise ValueError("claim source_evidence source_id must be nonempty")
        if not isinstance(content_sha256, str) or not re.fullmatch(
            r"[0-9a-f]{64}", content_sha256
        ):
            raise ValueError("claim source_evidence content_sha256 must be a full SHA256")
        if not isinstance(screen_event_id, str) or not screen_event_id:
            raise ValueError("claim source_evidence screen_event_id must be nonempty")
        if source_id in evidence_by_source:
            raise ValueError("claim source_evidence source IDs must be unique")
        evidence_by_source[source_id] = (content_sha256, screen_event_id)
    if set(evidence_by_source) != set(source_ids):
        raise ValueError("claim source_evidence must bind every declared source ID")
    manifest_sha256 = claim["manifest_sha256"]
    if not isinstance(manifest_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", manifest_sha256
    ):
        raise ValueError("claim manifest_sha256 must be a full SHA256")
    if claim.get("verified", False):
        if len(source_ids) < 2:
            raise ValueError("verified claim requires primary and cross check source IDs")
        events = _load_audit_events(args.audit_dir)
        safe_matches = {
            source_id: [
                event
                for event in events
                if event.get("event_type") == "retrieved_content_screened"
                and event.get("decision") == "safe_for_synthesis"
                and event.get("manifest_sha256") == manifest_sha256
                and event.get("qid") == claim["qid"]
                and event.get("source_id") == source_id
                and isinstance(event.get("details"), dict)
                and event["details"].get("content_sha256")
                == evidence_by_source[source_id][0]
                and event.get("event_id") == evidence_by_source[source_id][1]
            ]
            for source_id in source_ids
        }
        invalid_safe = sorted(
            source_id for source_id, matches in safe_matches.items() if len(matches) != 1
        )
        if invalid_safe:
            raise PermissionError(
                "verified claim requires one matching content-bound safe screen per source: "
                + ", ".join(invalid_safe)
            )
        discovered_matches = {
            source_id: [
                event
                for event in events
                if event.get("event_type") == "source_discovered"
                and event.get("manifest_sha256") == manifest_sha256
                and event.get("qid") == claim["qid"]
                and event.get("source_id") == source_id
            ]
            for source_id in source_ids
        }
        invalid_discovery = sorted(
            source_id
            for source_id, matches in discovered_matches.items()
            if len(matches) != 1
        )
        if invalid_discovery:
            raise PermissionError(
                "verified claim requires one matching discovery per source: "
                + ", ".join(invalid_discovery)
            )
        discovered = {
            source_id: matches[0] for source_id, matches in discovered_matches.items()
        }
        approval_events = [
            event
            for event in events
            if event.get("event_type") == "approval_recorded"
            and event.get("decision") == "approved"
            and event.get("manifest_sha256") == manifest_sha256
        ]
        if len(approval_events) != 1:
            raise PermissionError(
                "verified claim requires one approval event for the bound manifest"
            )
        trust_tiers = {
            discovered[source_id]["details"].get("trust_tier", "unclassified")
            for source_id in source_ids
        }
        if "primary" not in trust_tiers:
            raise PermissionError("verified claim requires at least one primary source")
        hosts = {
            (urlsplit(discovered[source_id]["details"]["url"]).hostname or "").lower()
            for source_id in source_ids
        }
        if len(hosts) < 2:
            raise PermissionError("verified claim requires independent source hosts")
    append_audit_event(
        ResearchAuditEvent(
            event_id=_event_id("EVT_CLAIM", str(claim["claim_id"])),
            event_type="claim_recorded",
            request_id=str(claim["request_id"]),
            qid=str(claim["qid"]),
            decision="verified" if claim.get("verified", False) else "unverified",
            manifest_sha256=str(manifest_sha256),
            details=claim,
        ),
        args.audit_dir,
    )
    _write_stdout({"recorded": True, "claim_id": claim["claim_id"]})
    return 0


def _cmd_audit_summary(args: argparse.Namespace) -> int:
    path = args.audit_dir / "audit" / "events.jsonl"
    events = _load_audit_events(args.audit_dir)
    event_types: dict[str, int] = {}
    decisions: dict[str, int] = {}
    for event in events:
        event_types[event["event_type"]] = event_types.get(event["event_type"], 0) + 1
        decisions[event["decision"]] = decisions.get(event["decision"], 0) + 1
    _write_stdout(
        {
            "event_count": len(events),
            "event_types": dict(sorted(event_types.items())),
            "decisions": dict(sorted(decisions.items())),
            "audit_path": str(path),
        }
    )
    return 0


def _cmd_record_review(args: argparse.Namespace) -> int:
    record_path = record_independent_review(
        args.review_note,
        args.review_root,
        args.audit_dir,
    )
    record = _read_json(record_path)
    _write_stdout(
        {
            "recorded": True,
            "review_record_path": str(record_path),
            "review_run_id": record["review_run_id"],
            "review_note_sha256": record["review_note_sha256"],
            "manifest_sha256": record["reviewed_manifest_sha256"],
        }
    )
    return 0


def _cmd_record_screen_correction(args: argparse.Namespace) -> int:
    correction = _read_json(args.correction_json)
    required = {
        "correction_id",
        "qid",
        "manifest_sha256",
        "review_run_id",
        "entries",
        "test_evidence",
    }
    missing = sorted(required - set(correction))
    if missing:
        raise ValueError("screen correction missing fields: " + ", ".join(missing))
    manifest_sha256 = correction["manifest_sha256"]
    if not isinstance(manifest_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", manifest_sha256
    ):
        raise ValueError("screen correction manifest_sha256 must be a full SHA256")
    entries = correction["entries"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("screen correction entries must be a nonempty list")
    test_evidence = correction["test_evidence"]
    if (
        not isinstance(test_evidence, list)
        or not test_evidence
        or any(not isinstance(item, str) or not item for item in test_evidence)
    ):
        raise ValueError("screen correction test_evidence must be a nonempty string list")

    events = _load_audit_events(args.audit_dir)
    events_by_id: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        events_by_id.setdefault(str(event.get("event_id", "")), []).append(event)
    review_matches = [
        event
        for event in events
        if event.get("event_type") == "independent_review_recorded"
        and isinstance(event.get("details"), dict)
        and event["details"].get("review_run_id") == correction["review_run_id"]
    ]
    if len(review_matches) != 1:
        raise PermissionError("screen correction requires one attested review event")

    normalized_entries: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("screen correction entries must be objects")
        superseded_event_id = entry.get("superseded_event_id")
        replacement_event_id = entry.get("replacement_event_id")
        reason = entry.get("reason")
        if not all(
            isinstance(value, str) and value
            for value in (superseded_event_id, replacement_event_id, reason)
        ):
            raise ValueError("screen correction entry identifiers and reason are required")
        old_matches = events_by_id.get(str(superseded_event_id), [])
        new_matches = events_by_id.get(str(replacement_event_id), [])
        if len(old_matches) != 1 or len(new_matches) != 1:
            raise PermissionError("screen correction event identifiers must be unique")
        old_event = old_matches[0]
        new_event = new_matches[0]
        old_details = old_event.get("details", {})
        new_details = new_event.get("details", {})
        old_result = old_details.get("result", {}) if isinstance(old_details, dict) else {}
        new_result = new_details.get("result", {}) if isinstance(new_details, dict) else {}
        if not isinstance(old_result, dict) or not isinstance(new_result, dict):
            raise PermissionError("screen correction events must contain screening results")
        identity_fields = ("manifest_sha256", "qid", "source_id")
        if any(old_event.get(field) != new_event.get(field) for field in identity_fields):
            raise PermissionError("screen correction events do not share source identity")
        if old_event.get("manifest_sha256") != manifest_sha256:
            raise PermissionError("screen correction events do not match the manifest")
        old_content_sha256 = old_details.get("content_sha256")
        new_content_sha256 = new_details.get("content_sha256")
        if old_content_sha256 != new_content_sha256:
            raise PermissionError("screen correction events do not share content bytes")
        old_is_flagged = (
            old_event.get("decision") == "quarantined"
            or old_result.get("flagged_attack") is True
            or old_result.get("quarantine_required") is True
        )
        new_is_clean = (
            new_event.get("decision") == "safe_for_synthesis"
            and new_result.get("flagged_attack") is False
            and new_result.get("quarantine_required") is False
            and new_result.get("allowed") is True
        )
        if not old_is_flagged or not new_is_clean:
            raise PermissionError(
                "screen correction requires a flagged old result and clean replacement"
            )
        old_version = str(
            old_result.get("content_ruleset_version")
            or old_result.get("ruleset_version", "")
        )
        new_version = str(
            new_result.get("content_ruleset_version")
            or new_result.get("ruleset_version", "")
        )
        if not old_version or not new_version or old_version == new_version:
            raise PermissionError("screen correction requires a ruleset version change")
        normalized_entries.append(
            {
                "source_id": str(old_event.get("source_id", "")),
                "content_sha256": str(old_content_sha256),
                "superseded_event_id": str(superseded_event_id),
                "replacement_event_id": str(replacement_event_id),
                "old_content_ruleset_version": old_version,
                "new_content_ruleset_version": new_version,
                "reason": str(reason),
            }
        )

    correction_file_sha256 = _file_sha256(args.correction_json)
    correction_event = ResearchAuditEvent(
        event_id=_event_id(
            "EVT_SCREEN_CORRECTION",
            str(correction["correction_id"]),
            str(correction["review_run_id"]),
            correction_file_sha256,
        ),
        event_type="content_screen_correction_recorded",
        request_id="CONTROL",
        qid=str(correction["qid"]),
        decision="recorded",
        manifest_sha256=manifest_sha256,
        details={
            **correction,
            "entries": normalized_entries,
            "correction_file_sha256": correction_file_sha256,
        },
    )
    append_audit_event(correction_event, args.audit_dir)
    _write_stdout(
        {
            "recorded": True,
            "correction_id": correction["correction_id"],
            "event_id": correction_event.event_id,
            "correction_file_sha256": correction_file_sha256,
        }
    )
    return 0


def _cmd_record_claim_supersession(args: argparse.Namespace) -> int:
    supersession = _read_json(args.supersession_json)
    required = {
        "supersession_id",
        "qid",
        "manifest_sha256",
        "review_run_id",
        "superseded_claim_event_id",
        "replacement_claim_event_id",
        "reason",
    }
    missing = sorted(required - set(supersession))
    if missing:
        raise ValueError("claim supersession missing fields: " + ", ".join(missing))
    manifest_sha256 = supersession["manifest_sha256"]
    if not isinstance(manifest_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", manifest_sha256
    ):
        raise ValueError("claim supersession manifest_sha256 must be a full SHA256")
    events = _load_audit_events(args.audit_dir)
    events_by_id: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        events_by_id.setdefault(str(event.get("event_id", "")), []).append(event)
    review_matches = [
        event
        for event in events
        if event.get("event_type") == "independent_review_recorded"
        and isinstance(event.get("details"), dict)
        and event["details"].get("review_run_id") == supersession["review_run_id"]
    ]
    if len(review_matches) != 1:
        raise PermissionError("claim supersession requires one attested review event")
    old_id = str(supersession["superseded_claim_event_id"])
    new_id = str(supersession["replacement_claim_event_id"])
    old_matches = events_by_id.get(old_id, [])
    new_matches = events_by_id.get(new_id, [])
    if len(old_matches) != 1 or len(new_matches) != 1:
        raise PermissionError("claim supersession event identifiers must be unique")
    old_event = old_matches[0]
    new_event = new_matches[0]
    if any(
        event.get("event_type") != "claim_recorded"
        or event.get("decision") != "verified"
        or event.get("qid") != supersession["qid"]
        or event.get("manifest_sha256") != manifest_sha256
        for event in (old_event, new_event)
    ):
        raise PermissionError("claim supersession events are not matching verified claims")
    if old_id == new_id:
        raise ValueError("claim supersession requires different event identifiers")
    supersession_file_sha256 = _file_sha256(args.supersession_json)
    supersession_event = ResearchAuditEvent(
        event_id=_event_id(
            "EVT_CLAIM_SUPERSESSION",
            str(supersession["supersession_id"]),
            old_id,
            new_id,
            supersession_file_sha256,
        ),
        event_type="claim_supersession_recorded",
        request_id="CONTROL",
        qid=str(supersession["qid"]),
        decision="recorded",
        manifest_sha256=manifest_sha256,
        details={
            **supersession,
            "supersession_file_sha256": supersession_file_sha256,
        },
    )
    append_audit_event(supersession_event, args.audit_dir)
    _write_stdout(
        {
            "recorded": True,
            "supersession_id": supersession["supersession_id"],
            "event_id": supersession_event.event_id,
            "supersession_file_sha256": supersession_file_sha256,
        }
    )
    return 0


def _load_audit_events(audit_dir: Path) -> list[dict[str, Any]]:
    path = audit_dir / "audit" / "events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser("preflight")
    preflight.add_argument("--request-json", type=Path, required=True)
    preflight.add_argument("--audit-dir", type=Path, required=True)
    preflight.set_defaults(handler=_cmd_preflight)

    register = subparsers.add_parser("register_sources")
    register.add_argument("--sources-json", type=Path, required=True)
    register.add_argument("--audit-dir", type=Path, required=True)
    register.set_defaults(handler=_cmd_register_sources)

    approve = subparsers.add_parser("approve_batch")
    approve.add_argument("--manifest", type=Path, required=True)
    approve.add_argument("--audit-dir", type=Path, required=True)
    approve.add_argument("--approved-by")
    approve.add_argument("--confirm-high-risk", action="store_true")
    approve.add_argument("--ethics-cleared", action="store_true")
    approve.set_defaults(handler=_cmd_approve_batch)

    screen = subparsers.add_parser("screen_content")
    screen.add_argument("--manifest", type=Path, required=True)
    screen.add_argument("--metadata-json", type=Path, required=True)
    screen.add_argument("--content", type=Path, required=True)
    screen.add_argument("--audit-dir", type=Path, required=True)
    screen.set_defaults(handler=_cmd_screen_content)

    claim = subparsers.add_parser("record_claim")
    claim.add_argument("--claim-json", type=Path, required=True)
    claim.add_argument("--audit-dir", type=Path, required=True)
    claim.set_defaults(handler=_cmd_record_claim)

    summary = subparsers.add_parser("audit_summary")
    summary.add_argument("--audit-dir", type=Path, required=True)
    summary.set_defaults(handler=_cmd_audit_summary)

    review = subparsers.add_parser("record_review")
    review.add_argument("--review-note", type=Path, required=True)
    review.add_argument("--review-root", type=Path, required=True)
    review.add_argument("--audit-dir", type=Path, required=True)
    review.set_defaults(handler=_cmd_record_review)

    correction = subparsers.add_parser("record_screen_correction")
    correction.add_argument("--correction-json", type=Path, required=True)
    correction.add_argument("--audit-dir", type=Path, required=True)
    correction.set_defaults(handler=_cmd_record_screen_correction)

    supersession = subparsers.add_parser("record_claim_supersession")
    supersession.add_argument("--supersession-json", type=Path, required=True)
    supersession.add_argument("--audit-dir", type=Path, required=True)
    supersession.set_defaults(handler=_cmd_record_claim_supersession)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())

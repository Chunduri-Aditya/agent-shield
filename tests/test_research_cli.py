"""Focused command workflow test for the research sidecar."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from agent_shield import research_cli
from agent_shield.research_cli import main


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_full_approved_research_audit_flow(
    tmp_path: Path,
    capsys: object,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_dir = tmp_path / "research_logs"
    request_path = tmp_path / "request.json"
    _write_json(
        request_path,
        {
            "request_id": "REQ_001",
            "qid": "Q_INT_001",
            "query": "Python mapping behavior primary documentation",
        },
    )
    assert main(
        ["preflight", "--request-json", str(request_path), "--audit-dir", str(audit_dir)]
    ) == 0

    sources_path = tmp_path / "sources.json"
    _write_json(
        sources_path,
        [
            {
                "request_id": "REQ_001",
                "qid": "Q_INT_001",
                "source_id": "SRC_PRIMARY",
                "url": "https://docs.python.org/3/library/stdtypes.html",
                "title": "Python built in types",
                "trust_tier": "primary",
            },
            {
                "request_id": "REQ_001",
                "qid": "Q_INT_001",
                "source_id": "SRC_CROSSCHECK",
                "url": "https://example.org/python-mappings",
                "title": "Independent mapping reference",
                "trust_tier": "authoritative",
            },
        ],
    )
    assert main(
        [
            "register_sources",
            "--sources-json",
            str(sources_path),
            "--audit-dir",
            str(audit_dir),
        ]
    ) == 0
    manifest_path = next((audit_dir / "manifests").glob("BATCH_*.json"))
    manifest = json.loads(manifest_path.read_text())

    monkeypatch.setattr(
        research_cli,
        "_confirm_manifest_interactively",
        lambda _manifest: None,
    )
    assert main(
        [
            "approve_batch",
            "--manifest",
            str(manifest_path),
            "--audit-dir",
            str(audit_dir),
        ]
    ) == 0
    approved_manifest = json.loads(manifest_path.read_text())
    assert approved_manifest["status"] == "approved"
    assert approved_manifest["approved"] is True

    for source_id, url in (
        ("SRC_PRIMARY", "https://docs.python.org/3/library/stdtypes.html"),
        ("SRC_CROSSCHECK", "https://example.org/python-mappings"),
    ):
        content_path = tmp_path / f"{source_id}.txt"
        content_path.write_text("Mappings associate keys with values.", encoding="utf-8")
        metadata_path = tmp_path / f"{source_id}.json"
        _write_json(
            metadata_path,
            {
                "request_id": "REQ_001",
                "qid": "Q_INT_001",
                "source_id": source_id,
                "url": url,
                "manifest_sha256": manifest["manifest_sha256"],
            },
        )
        assert main(
            [
                "screen_content",
                "--manifest",
                str(manifest_path),
                "--metadata-json",
                str(metadata_path),
                "--content",
                str(content_path),
                "--audit-dir",
                str(audit_dir),
            ]
        ) == 0

    alternate_content = tmp_path / "SRC_PRIMARY_ALTERNATE.txt"
    alternate_content.write_text("A second safe payload for the same source.", encoding="utf-8")
    assert main(
        [
            "screen_content",
            "--manifest",
            str(manifest_path),
            "--metadata-json",
            str(tmp_path / "SRC_PRIMARY.json"),
            "--content",
            str(alternate_content),
            "--audit-dir",
            str(audit_dir),
        ]
    ) == 0

    # A colliding source ID from another manifest must not influence claim trust or host
    # checks for the approved manifest.
    with (audit_dir / "audit" / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "event_id": "EVT_COLLIDING_SOURCE",
                    "event_type": "source_discovered",
                    "request_id": "REQ_001",
                    "qid": "Q_INT_001",
                    "source_id": "SRC_PRIMARY",
                    "decision": "candidate_allowed",
                    "timestamp": "2026-07-20T20:03:30+00:00",
                    "manifest_sha256": "0" * 64,
                    "details": {
                        "url": "https://collision.example/other",
                        "trust_tier": "unclassified",
                    },
                }
            )
            + "\n"
        )

    claim_path = tmp_path / "claim.json"
    content_sha256 = hashlib.sha256(
        b"Mappings associate keys with values."
    ).hexdigest()
    recorded_events = [
        json.loads(line)
        for line in (audit_dir / "audit" / "events.jsonl").read_text().splitlines()
    ]
    screen_event_ids = {
        event["source_id"]: event["event_id"]
        for event in recorded_events
        if event["event_type"] == "retrieved_content_screened"
        and event["decision"] == "safe_for_synthesis"
        and event["details"]["content_sha256"] == content_sha256
    }
    _write_json(
        claim_path,
        {
            "claim_id": "CLM_001",
            "qid": "Q_INT_001",
            "request_id": "REQ_001",
            "manifest_sha256": "0" * 64,
            "source_ids": ["SRC_PRIMARY", "SRC_CROSSCHECK"],
            "source_evidence": [
                {
                    "source_id": "SRC_PRIMARY",
                    "content_sha256": content_sha256,
                    "screen_event_id": screen_event_ids["SRC_PRIMARY"],
                },
                {
                    "source_id": "SRC_CROSSCHECK",
                    "content_sha256": content_sha256,
                    "screen_event_id": screen_event_ids["SRC_CROSSCHECK"],
                },
            ],
            "paraphrase": "Mappings associate keys with values.",
            "verified": True,
        },
    )
    with pytest.raises(
        PermissionError,
        match="one matching content-bound safe screen per source",
    ):
        main(
            [
                "record_claim",
                "--claim-json",
                str(claim_path),
                "--audit-dir",
                str(audit_dir),
            ]
        )
    claim = json.loads(claim_path.read_text())
    claim["manifest_sha256"] = manifest["manifest_sha256"]
    _write_json(claim_path, claim)
    assert main(
        [
            "record_claim",
            "--claim-json",
            str(claim_path),
            "--audit-dir",
            str(audit_dir),
        ]
    ) == 0
    assert main(["audit_summary", "--audit-dir", str(audit_dir)]) == 0

    review_root = tmp_path / "job_prep"
    review_path = review_root / "QA" / "review.md"
    review_path.parent.mkdir(parents=True)
    review_path.write_text(
        f"""---
reviewer_kind: "claude_code"
reviewer_session_id: "session-cli-001"
review_run_id: "22345678-1234-5678-9234-567812345678"
reviewed_batch_id: "PILOT-001"
reviewed_manifest_sha256: "{manifest['manifest_sha256']}"
reviewed_commit_sha: "2222222222222222222222222222222222222222"
review_started_at: "2026-07-20T20:00:00+00:00"
review_completed_at: "2026-07-20T20:05:00+00:00"
review_context: "fresh"
attestation_status: "recorded"
control_plane_verdict: "SHIP"
---

# Review

The test batch passed.
""",
        encoding="utf-8",
    )
    assert main(
        [
            "record_review",
            "--review-note",
            str(review_path),
            "--review-root",
            str(review_root),
            "--audit-dir",
            str(audit_dir),
        ]
    ) == 0
    capsys.readouterr()  # type: ignore[attr-defined]

    events = [
        json.loads(line)
        for line in (audit_dir / "audit" / "events.jsonl").read_text().splitlines()
    ]
    assert any(event["event_type"] == "claim_recorded" for event in events)
    claim_event = next(event for event in events if event["event_type"] == "claim_recorded")
    assert claim_event["manifest_sha256"] == manifest["manifest_sha256"]
    assert any(event["event_type"] == "approval_recorded" for event in events)
    assert any(event["event_type"] == "independent_review_recorded" for event in events)
    assert len(list((audit_dir / "quarantine").glob("*.txt"))) == 2


def test_record_claim_requires_manifest_binding(tmp_path: Path) -> None:
    claim_path = tmp_path / "claim.json"
    _write_json(
        claim_path,
        {
            "claim_id": "CLM_MISSING_MANIFEST",
            "qid": "Q_INT_001",
            "request_id": "REQ_001",
            "source_ids": ["SRC_PRIMARY", "SRC_CROSSCHECK"],
            "source_evidence": [
                {
                    "source_id": "SRC_PRIMARY",
                    "content_sha256": "a" * 64,
                    "screen_event_id": "EVT_SCREEN_PRIMARY",
                },
                {
                    "source_id": "SRC_CROSSCHECK",
                    "content_sha256": "b" * 64,
                    "screen_event_id": "EVT_SCREEN_CROSSCHECK",
                },
            ],
            "paraphrase": "A claim without a manifest binding.",
            "verified": True,
        },
    )
    with pytest.raises(ValueError, match="manifest_sha256"):
        main(
            [
                "record_claim",
                "--claim-json",
                str(claim_path),
                "--audit-dir",
                str(tmp_path / "audit"),
            ]
        )


def test_record_screen_correction_binds_flagged_and_clean_events(tmp_path: Path) -> None:
    audit_dir = tmp_path / "research_logs"
    events_path = audit_dir / "audit" / "events.jsonl"
    events_path.parent.mkdir(parents=True)
    manifest_sha256 = "a" * 64
    content_sha256 = "b" * 64
    base = {
        "event_type": "retrieved_content_screened",
        "request_id": "REQ_001",
        "qid": "Q_INT_001",
        "source_id": "SRC_001",
        "timestamp": "2026-07-20T20:00:00+00:00",
        "manifest_sha256": manifest_sha256,
    }
    events = [
        {
            **base,
            "event_id": "EVT_OLD",
            "decision": "quarantined",
            "details": {
                "content_sha256": content_sha256,
                "result": {
                    "allowed": False,
                    "flagged_attack": True,
                    "quarantine_required": True,
                    "ruleset_version": "research-cia-v1.1",
                },
            },
        },
        {
            **base,
            "event_id": "EVT_NEW",
            "decision": "safe_for_synthesis",
            "details": {
                "content_sha256": content_sha256,
                "result": {
                    "allowed": True,
                    "flagged_attack": False,
                    "quarantine_required": False,
                    "ruleset_version": "research-cia-v1.1",
                    "content_ruleset_version": "research-content-v1.1.2",
                },
            },
        },
        {
            "event_id": "EVT_REVIEW",
            "event_type": "independent_review_recorded",
            "request_id": "REVIEW",
            "qid": "MULTIPLE",
            "source_id": "",
            "decision": "recorded",
            "timestamp": "2026-07-20T20:05:00+00:00",
            "manifest_sha256": manifest_sha256,
            "details": {"review_run_id": "12345678-1234-5678-9234-567812345678"},
        },
    ]
    events_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )
    correction_path = tmp_path / "correction.json"
    _write_json(
        correction_path,
        {
            "correction_id": "CORR_001",
            "qid": "Q_INT_001",
            "manifest_sha256": manifest_sha256,
            "review_run_id": "12345678-1234-5678-9234-567812345678",
            "entries": [
                {
                    "superseded_event_id": "EVT_OLD",
                    "replacement_event_id": "EVT_NEW",
                    "reason": "False positive corrected by a versioned detector change.",
                }
            ],
            "test_evidence": ["tests/test_research.py::test_content_screen_allows_benign_text"],
        },
    )
    assert main(
        [
            "record_screen_correction",
            "--correction-json",
            str(correction_path),
            "--audit-dir",
            str(audit_dir),
        ]
    ) == 0
    recorded = [json.loads(line) for line in events_path.read_text().splitlines()][-1]
    assert recorded["event_type"] == "content_screen_correction_recorded"
    assert recorded["details"]["entries"][0]["replacement_event_id"] == "EVT_NEW"


def test_record_claim_supersession_binds_old_and_replacement_claims(tmp_path: Path) -> None:
    audit_dir = tmp_path / "research_logs"
    events_path = audit_dir / "audit" / "events.jsonl"
    events_path.parent.mkdir(parents=True)
    manifest_sha256 = "a" * 64
    claim_base = {
        "event_type": "claim_recorded",
        "request_id": "REQ_001",
        "qid": "Q_INT_001",
        "source_id": "",
        "decision": "verified",
        "timestamp": "2026-07-20T20:00:00+00:00",
        "manifest_sha256": manifest_sha256,
    }
    events = [
        {**claim_base, "event_id": "EVT_CLAIM_OLD", "details": {"claim_id": "CLM_OLD"}},
        {**claim_base, "event_id": "EVT_CLAIM_NEW", "details": {"claim_id": "CLM_NEW"}},
        {
            "event_id": "EVT_REVIEW",
            "event_type": "independent_review_recorded",
            "request_id": "REVIEW",
            "qid": "MULTIPLE",
            "source_id": "",
            "decision": "recorded",
            "timestamp": "2026-07-20T20:05:00+00:00",
            "manifest_sha256": manifest_sha256,
            "details": {"review_run_id": "12345678-1234-5678-9234-567812345678"},
        },
    ]
    events_path.write_text(
        "".join(json.dumps(event) + "\n" for event in events),
        encoding="utf-8",
    )
    supersession_path = tmp_path / "supersession.json"
    _write_json(
        supersession_path,
        {
            "supersession_id": "SUPER_001",
            "qid": "Q_INT_001",
            "manifest_sha256": manifest_sha256,
            "review_run_id": "12345678-1234-5678-9234-567812345678",
            "superseded_claim_event_id": "EVT_CLAIM_OLD",
            "replacement_claim_event_id": "EVT_CLAIM_NEW",
            "reason": "Provider-specific wording correction.",
        },
    )
    assert main(
        [
            "record_claim_supersession",
            "--supersession-json",
            str(supersession_path),
            "--audit-dir",
            str(audit_dir),
        ]
    ) == 0
    recorded = [json.loads(line) for line in events_path.read_text().splitlines()][-1]
    assert recorded["event_type"] == "claim_supersession_recorded"
    assert recorded["details"]["replacement_claim_event_id"] == "EVT_CLAIM_NEW"

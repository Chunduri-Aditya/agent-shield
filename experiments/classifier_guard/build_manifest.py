"""Build the Phase 1 evaluation set and its manifest.

Run from the repository root so the agent-shield importers and attack modules load:

    uv run python experiments/classifier_guard/build_manifest.py

Writes data/v2/ and refuses to run when it exists, so the committed files are never
overwritten. v2 leaves out the 2 taintgate fixture lines, which have never been published
(Aditya, 2026-10-29). Needs the two pinned corpus snapshots in data/external/ (not
committed). Writes eval_texts.jsonl (id, text) and manifest.jsonl (everything but the
text). Nothing is scored here. The headline subset and the dev split are fixed by this
script, before any model runs.
"""

import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOTS = HERE / "data" / "external"
SPLIT_SEED = 20261029
DEV_FRACTION = 0.30

sys.path.insert(0, str(REPO_ROOT))
from agent_shield.external_corpus.importers import (  # noqa: E402
    import_doronp,
    import_evalyze_attacks,
)
from drift.attacks import ATTACKS as DRIFT_ATTACKS  # noqa: E402
from evals.inputs import BENIGN_REQUESTS  # noqa: E402
from inputs.attacks import ATTACKS as INPUT_ATTACKS  # noqa: E402
from scripts.v2 import tasks_v2  # noqa: E402
from tools.payloads import TL_01_POISONING_PAYLOAD  # noqa: E402

# Headline attacks match the threat model: instructions planted in text the agent reads.
HEADLINE_EXTERNAL = {
    "prompt-injection",
    "direct_injection",
    "hidden_instructions",
    "retrieval_poisoning",
    "role_override",
    "goal_hijacking",
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def row(rid, text, label, group, source, path, license_, category, headline):
    return {
        "id": rid,
        "text": text,
        "label": label,
        "group": group,
        "source": source,
        "path": path,
        "license": license_,
        "category": category,
        "headline": headline,
    }


rows = []
rows.append(
    row(
        "AS-TL-01",
        TL_01_POISONING_PAYLOAD,
        1,
        "A1",
        "agent-shield",
        "tools/payloads.py",
        "agent-shield repo",
        "tool_poisoning",
        True,
    )
)
for a in INPUT_ATTACKS:
    rows.append(
        row(
            f"AS-{a.id}",
            a.payload,
            1,
            "A1",
            "agent-shield",
            "inputs/attacks.py",
            "agent-shield repo",
            a.name,
            True,
        )
    )
for a in DRIFT_ATTACKS:
    rows.append(
        row(
            f"AS-{a.id}",
            a.payload,
            1,
            "A1-drift",
            "agent-shield",
            "drift/attacks.py",
            "agent-shield repo",
            "drift",
            False,
        )
    )
for c in import_doronp(SNAPSHOTS) + import_evalyze_attacks(SNAPSHOTS):
    p = c.provenance
    label = 0 if c.is_benign else 1
    rows.append(
        row(
            c.case_id,
            c.untrusted_payload,
            label,
            "B-external" if label == 0 else "A2",
            p.source_repository,
            f"{p.source_path}@{p.source_commit[:8]}",
            p.license,
            c.attack_category,
            label == 1 and c.attack_category in HEADLINE_EXTERNAL,
        )
    )
for t in tasks_v2.load(tasks_v2.DATA):
    stub = "\n".join([*t["lines"], f"Ref: {t['nonce']}"])
    rows.append(
        row(
            f"AS-S1-{t['id']}",
            stub,
            0,
            "B1",
            "agent-shield",
            "evals/data/tools_v2_tasks.jsonl",
            "agent-shield repo",
            t["category"],
            False,
        )
    )
for i, text in enumerate(BENIGN_REQUESTS, 1):
    rows.append(
        row(
            f"AS-BENIGN-{i:02d}",
            text,
            0,
            "B1",
            "agent-shield",
            "evals/inputs.py",
            "agent-shield repo",
            "benign_request",
            False,
        )
    )

for r in rows:
    r["sha256"] = sha(r["text"])
    r["n_chars"] = len(r["text"])
ids = [r["id"] for r in rows]
assert len(ids) == len(set(ids)), "duplicate ids"

# Exact duplicate texts are kept once, the first seen, and the rest recorded.
seen, kept, dupes = {}, [], []
for r in rows:
    if r["sha256"] in seen:
        dupes.append({"id": r["id"], "duplicate_of": seen[r["sha256"]]})
        continue
    seen[r["sha256"]] = r["id"]
    kept.append(r)

rng = random.Random(SPLIT_SEED)
for group in sorted({r["group"] for r in kept}):
    members = sorted((r for r in kept if r["group"] == group), key=lambda r: r["id"])
    rng.shuffle(members)
    n_dev = round(len(members) * DEV_FRACTION)
    for i, r in enumerate(members):
        r["split"] = "dev" if i < n_dev else "test"

out = HERE / "data" / "v2"
out.mkdir(exist_ok=False)
with open(out / "eval_texts.jsonl", "w") as f:
    for r in kept:
        f.write(json.dumps({"id": r["id"], "text": r["text"]}, ensure_ascii=False) + "\n")
with open(out / "manifest.jsonl", "w") as f:
    for r in kept:
        f.write(json.dumps({k: v for k, v in r.items() if k != "text"}) + "\n")
(out / "duplicates.json").write_text(json.dumps(dupes, indent=1))
print(f"rows {len(rows)}, kept {len(kept)}, exact duplicates dropped {len(dupes)}")

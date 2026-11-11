"""Pre-upload audits for the Phase 1 evaluation set: sensitive strings and training overlap.

    uv run python experiments/classifier_guard/audit_data.py [DATA_DIR]

Needs the datasets package, which is not a project dependency. Writes sensitive_scan.json
and overlap.json into DATA_DIR, default data/v2/. Reports ids and pattern names,
never matched text.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from datasets import get_dataset_config_names, load_dataset

HERE = Path(__file__).resolve().parent
DATA = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "data" / "v2"

SENSITIVE = {
    "openai_or_anthropic_key": r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{8,}",
    "aws_access_key": r"\bAKIA[0-9A-Z]{16}\b",
    "github_token": r"\bgh[pousr]_[A-Za-z0-9]{20,}",
    "slack_token": r"\bxox[abprs]-[A-Za-z0-9\-]{10,}",
    "private_key_block": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "email": r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
    "us_phone": r"\(?\b\d{3}\)?[ .\-]\d{3}[ .\-]\d{4}\b",
    "local_home_path": r"/(?:Users|home)/[A-Za-z0-9_]+",
    "owner_name": r"(?i)chunduri|aditya",
    "password_assignment": r"(?i)\bpassword\s*[:=]",
}

# Training sets named on the model card (revision 90c9989b), for the overlap check.
TRAINING_SETS = [
    "jackhhao/jailbreak-classification",
    "natolambert/xstest-v2-copy",
    "OpenSafetyLab/Salad-Data",
    "alespalla/chatbot_instruction_prompts",
    "HuggingFaceH4/grok-conversation-harmless",
    "Harelix/Prompt-Injection-Mixed-Techniques-2024",
    "VMware/open-instruct",
]
N = 8
JACCARD_FLAG = 0.8


def norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def shingles(text: str) -> set[tuple[str, ...]]:
    words = norm(text).split()
    return {tuple(words[i : i + N]) for i in range(len(words) - N + 1)}


def sensitive_scan(texts: dict[str, str]) -> dict:
    hits = defaultdict(list)
    for rid, text in texts.items():
        for name, pat in SENSITIVE.items():
            if re.search(pat, text):
                hits[name].append(rid)
    return {"patterns": list(SENSITIVE), "hits": {k: sorted(v) for k, v in hits.items()}}


def overlap(texts: dict[str, str]) -> dict:
    exact = {norm(t): rid for rid, t in texts.items()}
    eval_sh = {rid: shingles(t) for rid, t in texts.items()}
    index = defaultdict(set)
    for rid, sh in eval_sh.items():
        for s in sh:
            index[s].add(rid)
    best: dict[str, dict] = {}
    report = {"n": N, "flag_jaccard": JACCARD_FLAG, "sets": {}}
    for name in TRAINING_SETS:
        try:
            configs = get_dataset_config_names(name)
        except Exception as e:
            report["sets"][name] = {"status": f"unavailable: {type(e).__name__}"}
            continue
        rows_seen = 0
        status = "checked"
        for cfg in configs:
            try:
                ds = load_dataset(name, cfg)
            except Exception as e:
                status = f"partial: config {cfg} {type(e).__name__}"
                continue
            for split in ds.values():
                cols = [c for c, f in split.features.items() if getattr(f, "dtype", "") == "string"]
                for rec in split.select_columns(cols):
                    for val in rec.values():
                        if not isinstance(val, str):
                            continue
                        rows_seen += 1
                        nv = norm(val)
                        if nv in exact:
                            best[exact[nv]] = {"set": name, "jaccard": 1.0, "exact": True}
                        sh = shingles(val)
                        cand = defaultdict(int)
                        for s in sh:
                            for rid in index.get(s, ()):
                                cand[rid] += 1
                        for rid, shared in cand.items():
                            j = shared / len(eval_sh[rid] | sh)
                            if j > best.get(rid, {}).get("jaccard", 0):
                                best[rid] = {"set": name, "jaccard": round(j, 3), "exact": False}
        report["sets"][name] = {"status": status, "strings_checked": rows_seen}
    flagged = {rid: v for rid, v in best.items() if v["jaccard"] >= JACCARD_FLAG}
    report["flagged"] = dict(sorted(flagged.items()))
    report["short_texts_exact_only"] = sorted(r for r, s in eval_sh.items() if not s)
    return report


def main() -> None:
    texts = {}
    with open(DATA / "eval_texts.jsonl") as fh:
        for line in fh:
            r = json.loads(line)
            texts[r["id"]] = r["text"]
    (DATA / "sensitive_scan.json").write_text(json.dumps(sensitive_scan(texts), indent=1))
    rep = overlap(texts)
    (DATA / "overlap.json").write_text(json.dumps(rep, indent=1))
    print(
        json.dumps({k: v for k, v in rep.items() if k != "short_texts_exact_only"}, indent=1)[:3000]
    )


if __name__ == "__main__":
    main()

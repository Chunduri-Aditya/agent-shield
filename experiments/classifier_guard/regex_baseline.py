"""Regex guard baseline: the Agent Shield runtime guard on the same evaluation texts.

Run from the repository root:

    uv run python experiments/classifier_guard/regex_baseline.py

Calls guard_text in product mode, the same function and mode the agent-shield-guard CLI
uses when taintgate invokes it with --json. The verdict is flagged_attack, the field
taintgate reads. Writes runs/regex/scores.jsonl and env.json.
"""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from agent_shield.runtime.pipeline import GuardSession, guard_text  # noqa: E402

out = HERE / "runs" / "regex"
out.mkdir(parents=True, exist_ok=False)
ruleset = set()
with open(out / "scores.jsonl", "w") as f, open(HERE / "data" / "v2" / "eval_texts.jsonl") as fh:
    for line in fh:
        r = json.loads(line)
        res = guard_text(r["text"], mode="product", session=GuardSession())
        ruleset.add(res.content_ruleset_version)
        f.write(
            json.dumps(
                {
                    "id": r["id"],
                    "label": int(res.flagged_attack),
                    "action": res.action.value,
                    "risk": res.risk_level,
                }
            )
            + "\n"
        )
commit = subprocess.run(
    ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
).stdout.strip()
env = {
    "utc": datetime.now(UTC).isoformat(),
    "python": sys.version.split()[0],
    "agent_shield_commit": commit,
    "rulesets": sorted(map(str, ruleset)),
    "mode": "product",
}
(out / "env.json").write_text(json.dumps(env, indent=1))
print(json.dumps(env, indent=1))

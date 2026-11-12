# Absolute claim rule tuning: result

Verdict: FAIL at selection (P3). No promotion. `research.py` and `CONTENT_RULESET_VERSION` are unchanged.

Preregistration: `PREREG.md` (commit ce39ab9). Half B was never scored.

| Arm | Sole signal attack ids kept (of 5) | Attacks dropped to 0 reasons | residual_A (of 1484) |
|---|---|---|---|
| Baseline | 5 | 0 | 1.0000 |
| Ablation | 0 | 5 | 0.0000 |
| C1 | 0 | 5 | 0.0418 |
| C2 | 0 | 5 | 0.0290 |
| C3 | 0 | 5 | 0.0317 |
| C4 | 2 | 3 | 0.8929 |

Cause: two sole signal attack ids match only on a capitalized sentence initial "Always" or "Never".
That shape is also present in 420 of 1484 (28.3%) benign half A rows. No regex in the candidate
set separates the two. Revisions were not run, because tuning blind to the attack text cannot
target the shape without matching the benign noise too.

Next direction, not started: a learned classifier, or context outside the regex (source, tool).

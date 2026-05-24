"""Agent Shield approval policy and pre-eval risk gate.

`approvals/policy.yaml` is the human-readable policy. `approvals/gate.py`
implements `check_eval_risk()` and `print_risk_banner()` — the two entry
points eval runners (and `scripts/risk_check.py`) call before any model is
prompted.

The gate is intentionally text-only; no LLM is involved in the
classification. Banner text is sourced directly from `risk_registry.py` so an
attacker cannot lie to the operator about what is about to run. See the
Lies-in-the-Loop defense write-up in `docs/improvement_research.md` for
context.
"""

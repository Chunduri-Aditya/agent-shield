"""
Tests that the TL-01 poisoning payload is defined in exactly one place
and re-exported by evals/tools.py for the Inspect eval harness.

The paper distinguishes the FastMCP demo (tools/server.py) from the Inspect
eval (evals/tools.py). Both must use the same injected directive text so
results from the demo and the harness are directly comparable.

tools/payloads.py is the single source of truth. evals/tools.py re-exports
TL_01_POISONING_PAYLOAD from it. The test imports from both and asserts
identity, confirming the eval harness cannot silently drift from the demo.
"""


def test_tl01_payload_is_identical_in_payloads_module_and_eval_reexport() -> None:
    """Both the payload module and the eval harness must export the same object."""
    from tools.payloads import TL_01_POISONING_PAYLOAD as canonical_payload
    from evals.tools import TL_01_POISONING_PAYLOAD as eval_payload

    assert canonical_payload == eval_payload, (
        "tools/payloads.py and evals/tools.py have diverged on TL-01 payload"
    )


def test_tl01_payload_is_nonempty_string() -> None:
    from tools.payloads import TL_01_POISONING_PAYLOAD

    assert isinstance(TL_01_POISONING_PAYLOAD, str)
    assert len(TL_01_POISONING_PAYLOAD) > 0


def test_tl01_payload_contains_operator_directive_framing() -> None:
    """The payload must look like an operator directive — that is the attack vector."""
    from tools.payloads import TL_01_POISONING_PAYLOAD

    payload_lower = TL_01_POISONING_PAYLOAD.lower()
    assert "directive" in payload_lower, (
        "TL-01 payload must contain 'directive' framing to simulate the attack"
    )
    assert "send_message" in payload_lower or "audit" in payload_lower, (
        "TL-01 payload must reference the exfiltration sink or audit log"
    )

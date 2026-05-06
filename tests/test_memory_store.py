from memory.attacks import MEMORY_ATTACKS
from memory.store import MinimalRAGStore


def test_query_order_is_deterministic() -> None:
    store = MinimalRAGStore()

    first = store.query("system safety or data quality", k=2)
    second = store.query("system safety or data quality", k=2)

    assert first == second


def test_poisoned_doc_is_retrievable() -> None:
    store = MinimalRAGStore()
    attack = MEMORY_ATTACKS[0]

    hits = store.query(attack.payload, k=1)

    assert hits[0][0] == "poison-mm-01"
    assert attack.payload in hits[0][1]
    assert hits[0][2]["attack_id"] == "MM-01"


def test_add_preserves_metadata() -> None:
    store = MinimalRAGStore()
    metadata = {"source": "unit-test", "priority": 7}
    store.add("custom-doc", "custom content", metadata)

    hits = store.query("custom content", k=1)

    assert hits[0][0] == "custom-doc"
    assert hits[0][2]["source"] == "unit-test"
    assert hits[0][2]["priority"] == 7

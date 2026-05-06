import hashlib
import math

from memory.attacks import MEMORY_ATTACKS

Metadata = dict[str, object]
StoredDoc = tuple[str, Metadata, list[float]]


class MinimalRAGStore:
    """Deterministic in memory RAG store with a fixed hash embedding stub."""

    EMBEDDING_DIM = 16

    def __init__(self) -> None:
        self._docs: dict[str, StoredDoc] = {}
        self._seed_corpus()

    def add(self, doc_id: str, text: str, metadata: dict[str, object] | None = None) -> None:
        clean_metadata: Metadata = dict(metadata) if metadata is not None else {}
        self._docs[doc_id] = (text, clean_metadata, self._embed(text))

    def query(self, text: str, k: int = 3) -> list[tuple[str, str, dict[str, object]]]:
        query_embedding = self._embed(text)
        ranked: list[tuple[float, str, str, Metadata]] = []
        for doc_id, (doc_text, metadata, embedding) in self._docs.items():
            similarity = self._dot(query_embedding, embedding)
            ranked.append((similarity, doc_id, doc_text, metadata))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        top_k = ranked[: max(k, 0)]
        return [
            (doc_id, doc_text, dict(metadata))
            for _, doc_id, doc_text, metadata in top_k
        ]

    def _seed_corpus(self) -> None:
        self.add(
            doc_id="benign-policy-01",
            text=(
                "Agent Shield policy memo: summarize retrieved context for the user, "
                "note uncertainty, and avoid exposing hidden system tokens."
            ),
            metadata={"seed": "benign", "corpus_seed": "memory-v1"},
        )
        attack = MEMORY_ATTACKS[0]
        self.add(
            doc_id="poison-mm-01",
            text=attack.payload,
            metadata={
                "seed": "poisoned",
                "attack_id": attack.id,
                "corpus_seed": "memory-v1",
            },
        )

    def _embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vector = [float(byte) / 255.0 for byte in digest[: self.EMBEDDING_DIM]]
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    @staticmethod
    def _dot(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right, strict=True))

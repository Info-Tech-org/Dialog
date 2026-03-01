"""
Embedding service for semantic harmful detection.
Abstract provider: local (sentence-transformers) or API (OpenAI-compatible).
Used by VectorDetector to embed text and compare to harmful concept vectors.
"""
from abc import ABC, abstractmethod
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract embedding provider: single method get_embedding(text) -> list[float]."""

    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Batch embed for efficiency (e.g. precompute harmful refs)."""
        pass


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    import math
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors; [0, 1] for normalized embeddings."""
    return _cosine_similarity(a, b)


def max_similarity_to_refs(embedding: List[float], ref_embeddings: List[List[float]]) -> float:
    """Max cosine similarity between embedding and any ref. Returns 0 if empty."""
    if not ref_embeddings:
        return 0.0
    return max(_cosine_similarity(embedding, ref) for ref in ref_embeddings)


# ---------------------------------------------------------------------------
# OpenAI-compatible API (OpenAI / OpenRouter embedding endpoints)
# ---------------------------------------------------------------------------

class OpenAICompatibleEmbedding(EmbeddingProvider):
    """Use OpenAI or OpenAI-compatible embedding API."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
        dimensions: Optional[int] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.dimensions = dimensions

    def get_embedding(self, text: str) -> List[float]:
        return self.get_embeddings_batch([text])[0]

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package required for OpenAICompatibleEmbedding")

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        kwargs = {"model": self.model, "input": texts}
        if self.dimensions is not None:
            kwargs["dimensions"] = self.dimensions
        resp = client.embeddings.create(**kwargs)
        # preserve order by index (or by position if index missing)
        out: List[List[float]] = [None] * len(texts)  # type: ignore
        for i, e in enumerate(resp.data):
            idx = e.index if e.index is not None and 0 <= e.index < len(texts) else i
            if idx < len(texts):
                out[idx] = e.embedding
        for i in range(len(out)):
            if out[i] is None:
                out[i] = []
        return out


# ---------------------------------------------------------------------------
# Local: sentence-transformers (optional dependency)
# ---------------------------------------------------------------------------

def _try_sentence_transformers() -> Optional[EmbeddingProvider]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None

    class LocalSentenceTransformerEmbedding(EmbeddingProvider):
        def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
            self._model = SentenceTransformer(model_name)

        def get_embedding(self, text: str) -> List[float]:
            return self._model.encode(text, convert_to_numpy=True).tolist()

        def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
            if not texts:
                return []
            arr = self._model.encode(texts, convert_to_numpy=True)
            return [arr[i].tolist() for i in range(len(texts))]

    return LocalSentenceTransformerEmbedding()


def get_embedding_provider(
    provider: str = "openai",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
) -> Optional[EmbeddingProvider]:
    """
    Factory: return EmbeddingProvider from config.
    - provider "openai" -> OpenAICompatibleEmbedding (api_key required)
    - provider "local" -> sentence-transformers if installed, else None
    """
    if provider == "local":
        return _try_sentence_transformers()
    if provider == "openai" and api_key:
        return OpenAICompatibleEmbedding(
            api_key=api_key,
            model=model or "text-embedding-3-small",
            base_url=base_url,
        )
    return None

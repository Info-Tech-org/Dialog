"""
Semantic vector detector: embed text, compare to harmful concept vectors, then LLM screening.
Pipeline: 绝对关键词 → 语义向量召回 → LLM 筛选（仅对向量候选执行，确保不错过且控制误报）
"""
import logging
from typing import List, Optional

from .detector_base import BaseHarmfulDetector, HarmfulResult
from .embedding_service import (
    EmbeddingProvider,
    get_embedding_provider,
    max_similarity_to_refs,
)
from .harmful_rules import HARMFUL_REFERENCES
from .llm_harmful_detector import LLMHarmfulDetector

logger = logging.getLogger(__name__)


class VectorThenLLMDetector(BaseHarmfulDetector):
    """
    语义空间向量化 + 后期 LLM 筛选：
    1. 将输入文本与预置有害概念参考句做向量相似度；
    2. 相似度达到阈值则视为候选，交 LLM 做最终判定（降误报）；
    3. 未达阈值则直接判无害，不调 LLM（省成本、保召回靠关键词+向量阈值）。
    """

    def __init__(
        self,
        similarity_threshold: float = 0.65,
        severity_threshold: int = 3,
        embedding_provider: Optional[EmbeddingProvider] = None,
        references: Optional[List[str]] = None,
    ):
        self.similarity_threshold = similarity_threshold
        self.severity_threshold = severity_threshold
        self._refs = references or HARMFUL_REFERENCES
        self._provider = embedding_provider
        self._ref_embeddings: Optional[List[List[float]]] = None
        self._llm = LLMHarmfulDetector()

    def _get_provider(self) -> Optional[EmbeddingProvider]:
        if self._provider is not None:
            return self._provider
        from config import settings
        provider = getattr(settings, "embedding_provider", "openai") or "openai"
        api_key = getattr(settings, "embedding_api_key", None)
        model = getattr(settings, "embedding_model", None)
        base_url = getattr(settings, "embedding_base_url", None)
        self._provider = get_embedding_provider(
            provider=provider,
            api_key=api_key,
            model=model,
            base_url=base_url,
        )
        return self._provider

    def _ensure_ref_embeddings(self) -> bool:
        if self._ref_embeddings is not None:
            return True
        prov = self._get_provider()
        if prov is None:
            logger.warning("VectorThenLLMDetector: no embedding provider, semantic stage disabled")
            return False
        try:
            self._ref_embeddings = prov.get_embeddings_batch(self._refs)
            logger.info("VectorThenLLMDetector: precomputed %d harmful ref embeddings", len(self._ref_embeddings))
            return True
        except Exception as e:
            logger.warning("VectorThenLLMDetector: failed to compute ref embeddings: %s", e)
            return False

    async def detect(self, text: str) -> HarmfulResult:
        text = (text or "").strip()
        if not text:
            return HarmfulResult(
                is_harmful=False,
                method="vector_llm",
                severity=0,
                category="",
                explanation="空文本",
            )

        if not self._ensure_ref_embeddings():
            # 无 embedding 时退化为仅 LLM（可选：直接返回无害以保持“不增加误报”）
            analysis = await self._llm.detect(text)
            is_harmful = analysis.get("is_harmful", False)
            severity = analysis.get("severity", 0)
            if is_harmful and severity < self.severity_threshold:
                is_harmful = False
            return HarmfulResult(
                is_harmful=is_harmful,
                method="llm",
                severity=severity,
                category=analysis.get("category", ""),
                explanation=analysis.get("explanation", ""),
                raw=analysis,
            )

        prov = self._get_provider()
        try:
            emb = prov.get_embedding(text)
        except Exception as e:
            logger.warning("VectorThenLLMDetector: embed failed %s", e)
            return HarmfulResult(
                is_harmful=False,
                method="vector_llm",
                severity=0,
                category="",
                explanation=f"向量化失败: {e}",
            )

        sim = max_similarity_to_refs(emb, self._ref_embeddings)
        if sim < self.similarity_threshold:
            return HarmfulResult(
                is_harmful=False,
                method="vector_llm",
                severity=0,
                category="",
                explanation=f"语义相似度 {sim:.2f} 低于阈值 {self.similarity_threshold}",
                raw={"similarity": sim},
            )

        # 向量候选：交 LLM 筛选
        analysis = await self._llm.detect(text)
        is_harmful = analysis.get("is_harmful", False)
        severity = analysis.get("severity", 0)
        if is_harmful and severity < self.severity_threshold:
            is_harmful = False
        return HarmfulResult(
            is_harmful=is_harmful,
            method="vector_llm",
            severity=severity,
            category=analysis.get("category", ""),
            explanation=analysis.get("explanation", "") or f"语义相似度 {sim:.2f}，LLM 判定",
            keywords=None,
            raw={"similarity": sim, **analysis},
        )

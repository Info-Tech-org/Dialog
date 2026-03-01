"""
Harmful detection pipeline: 绝对关键词 → 语义向量召回 → LLM 筛选.
First detector that returns is_harmful=True short-circuits (optional).
Default: KeywordDetector then VectorThenLLMDetector (embed + LLM screen).
"""
import logging
from typing import List, Optional, Tuple

from .detector_base import BaseHarmfulDetector, HarmfulResult
from .keyword_detector import KeywordDetector
from .llm_detector import LLMDetector
from .vector_detector import VectorThenLLMDetector

logger = logging.getLogger(__name__)

# Default: 绝对关键词 → 语义向量召回 → LLM 筛选
_DEFAULT_DETECTORS: List[BaseHarmfulDetector] = [
    KeywordDetector(),
    VectorThenLLMDetector(similarity_threshold=0.65, severity_threshold=3),
]


def get_default_pipeline(use_vector_llm: bool = True) -> List[BaseHarmfulDetector]:
    """Default: Keyword + VectorThenLLM. Set use_vector_llm=False for legacy Keyword+LLM only."""
    if use_vector_llm:
        return list(_DEFAULT_DETECTORS)
    return [KeywordDetector(), LLMDetector(severity_threshold=3)]


async def run_pipeline(
    text: str,
    detectors: Optional[List[BaseHarmfulDetector]] = None,
    short_circuit_on_harmful: bool = True,
) -> Tuple[bool, dict]:
    """
    Run detectors in order. Return (is_harmful, details_dict) compatible with is_harmful_advanced.

    If short_circuit_on_harmful is True, the first detector that returns is_harmful=True
    wins and later detectors are skipped. Otherwise all run and the "worst" result is used.
    """
    if detectors is None:
        detectors = get_default_pipeline()

    last_result: Optional[HarmfulResult] = None
    for det in detectors:
        try:
            result = await det.detect(text)
            last_result = result
            if result.is_harmful and short_circuit_on_harmful:
                return True, result.to_details_dict()
            if not result.is_harmful and last_result is None:
                last_result = result
        except Exception as e:
            logger.warning(f"Detector {det.name} failed: {e}")
            continue

    if last_result is None:
        return False, {"method": "none", "severity": 0, "category": "", "explanation": ""}
    return last_result.is_harmful, last_result.to_details_dict()

"""
Keyword-based harmful language detector (plugin).
Wraps harmful_rules.HARMFUL_KEYWORDS / get_harmful_keywords.
"""
from .detector_base import BaseHarmfulDetector, HarmfulResult
from .harmful_rules import get_harmful_keywords


class KeywordDetector(BaseHarmfulDetector):
    """Fast keyword match; use first in pipeline to short-circuit on hit."""

    async def detect(self, text: str) -> HarmfulResult:
        keywords = get_harmful_keywords(text)
        if keywords:
            return HarmfulResult(
                is_harmful=True,
                method="keyword",
                severity=3,
                category="关键词匹配",
                explanation=f"包含有害关键词: {', '.join(keywords)}",
                keywords=keywords,
            )
        return HarmfulResult(
            is_harmful=False,
            method="keyword",
            severity=0,
            category="",
            explanation="未命中关键词",
        )

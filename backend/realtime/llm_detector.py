"""
LLM-based harmful language detector (plugin).
Wraps LLMHarmfulDetector for use in detector pipeline.
"""
from .detector_base import BaseHarmfulDetector, HarmfulResult
from .llm_harmful_detector import LLMHarmfulDetector


class LLMDetector(BaseHarmfulDetector):
    """OpenRouter/LLM semantic analysis; typically run after keyword detector."""

    def __init__(self, severity_threshold: int = 3):
        self._client = LLMHarmfulDetector()
        self.severity_threshold = severity_threshold

    async def detect(self, text: str) -> HarmfulResult:
        analysis = await self._client.detect(text)
        is_harmful = analysis.get("is_harmful", False)
        severity = analysis.get("severity", 0)
        # Only treat as harmful when severity >= threshold (avoid over-sensitivity)
        if is_harmful and severity < self.severity_threshold:
            is_harmful = False
        return HarmfulResult(
            is_harmful=is_harmful,
            method="llm",
            severity=severity,
            category=analysis.get("category", "unknown"),
            explanation=analysis.get("explanation", ""),
            keywords=None,
            raw=analysis,
        )

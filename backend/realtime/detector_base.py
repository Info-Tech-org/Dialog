"""
Harmful language detector plugin base.

Implement this interface to add custom detectors (keyword, regex, LLM, external API).
Pipeline runs detectors in order; first non-ambiguous result can short-circuit.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class HarmfulResult:
    """Result of a single detector or the pipeline."""
    is_harmful: bool
    method: str  # e.g. "keyword", "llm", "custom"
    severity: int = 0  # 1-5, 5 most severe
    category: str = ""
    explanation: str = ""
    keywords: Optional[List[str]] = None  # for keyword-based detectors
    raw: Optional[Dict[str, Any]] = None  # detector-specific payload

    def to_details_dict(self) -> Dict[str, Any]:
        """Same shape as legacy is_harmful_advanced details."""
        d: Dict[str, Any] = {
            "method": self.method,
            "severity": self.severity,
            "category": self.category,
            "explanation": self.explanation,
        }
        if self.keywords is not None:
            d["keywords"] = self.keywords
        return d


class BaseHarmfulDetector(ABC):
    """Base class for harmful language detectors. Register in pipeline to run in order."""

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    async def detect(self, text: str) -> HarmfulResult:
        """
        Analyze text and return harmful result.

        Args:
            text: Input text to analyze.

        Returns:
            HarmfulResult with is_harmful and details.
        """
        pass

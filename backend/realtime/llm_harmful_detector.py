"""
LLM-based Harmful Language Detection
基于大语言模型的有害语句检测
"""

import httpx
import logging
from typing import Dict, Any
from config import settings

logger = logging.getLogger(__name__)


class LLMHarmfulDetector:
    """
    使用 LLM (通过 OpenRouter) 检测有害语句
    相比简单的关键词匹配，LLM 能理解上下文和语义
    """

    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    async def detect(self, text: str) -> Dict[str, Any]:
        """
        检测文本是否包含有害内容

        Args:
            text: 要检测的文本

        Returns:
            {
                "is_harmful": bool,
                "severity": int (1-5, 5最严重),
                "category": str (类型: 辱骂/威胁/贬低等),
                "explanation": str (解释)
            }
        """
        prompt = f"""你是一个家庭沟通分析专家。请分析以下家长对孩子说的话是否有害。

需要判断的话："{text}"

请从以下维度分析：
1. 是否有害（是/否）
2. 严重程度（1-5分，5分最严重）
3. 有害类别（如：辱骂、威胁、贬低、否定、冷暴力等）
4. 简短解释（为什么有害或无害）

请严格按照以下 JSON 格式返回，不要包含其他内容：
{{
    "is_harmful": true/false,
    "severity": 1-5,
    "category": "类别",
    "explanation": "解释"
}}"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 0.3,  # 降低随机性
                    }
                )

                response.raise_for_status()
                result = response.json()

                # 解析 LLM 返回的结果
                content = result["choices"][0]["message"]["content"]

                # 尝试提取 JSON
                import json
                import re

                # 寻找 JSON 块
                json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group())
                else:
                    # 如果没有找到 JSON，使用默认值
                    logger.warning(f"Failed to parse LLM response: {content}")
                    analysis = {
                        "is_harmful": False,
                        "severity": 0,
                        "category": "unknown",
                        "explanation": "分析失败"
                    }

                logger.info(f"LLM analysis for '{text}': {analysis}")
                return analysis

        except Exception as e:
            logger.error(f"Error calling LLM API: {e}", exc_info=True)
            # 发生错误时，返回保守的默认值
            return {
                "is_harmful": False,
                "severity": 0,
                "category": "error",
                "explanation": f"检测失败: {str(e)}"
            }

    async def detect_batch(self, texts: list[str]) -> list[Dict[str, Any]]:
        """
        批量检测多个文本

        Args:
            texts: 要检测的文本列表

        Returns:
            检测结果列表
        """
        results = []
        for text in texts:
            result = await self.detect(text)
            results.append(result)
        return results

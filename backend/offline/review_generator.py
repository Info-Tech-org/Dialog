"""
Review Generator — 基于 LLM 生成会话复盘内容
- 会话摘要 (summary)
- Highlights (3-5 条关键片段)
- 每条 utterance 的 severity/category/explanation/suggestion
"""

import httpx
import json
import re
import logging
from typing import List, Dict, Any, Optional

from config import settings

logger = logging.getLogger(__name__)


class ReviewGenerator:
    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.openrouter_model
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

    async def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    def _extract_json(self, text: str) -> Any:
        """从 LLM 输出中提取 JSON，支持 markdown 代码块"""
        # 优先找 ```json ... ``` 块
        block = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if block:
            text = block.group(1)
        # 找最外层 { } 或 [ ]
        obj = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if obj:
            return json.loads(obj.group(1))
        raise ValueError(f"No JSON found in: {text[:200]}")

    async def generate_session_review(
        self, session_id: str, utterances: List[Dict]
    ) -> Dict[str, Any]:
        """
        对一次会话生成完整复盘内容。
        utterances: [{"id": str, "speaker": str, "text": str, "harmful_flag": bool, "start": float}]
        Returns:
        {
            "summary": {"text": str, "top_category": str, "max_severity": int},
            "highlights": [{"utterance_id": str, "score": float, "reason": str, "rank": int}],
            "analyses": {utterance_id: {"severity": int, "category": str, "explanation": str, "suggestion": str}}
        }
        """
        if not utterances:
            return {
                "summary": {"text": "本次会话无对话内容。", "top_category": "", "max_severity": 0},
                "highlights": [],
                "analyses": {},
            }

        harmful_utts = [u for u in utterances if u.get("harmful_flag")]

        # ── 1. 会话摘要 + highlights ──────────────────────────
        dialogue_text = "\n".join(
            f"[{u['speaker']}] {u['text']}" for u in utterances
        )
        harmful_text = "\n".join(
            f"- (id={u['id']}) [{u['speaker']}] {u['text']}"
            for u in harmful_utts
        ) or "（无有害语句）"

        summary_prompt = f"""你是家庭沟通分析专家。以下是一次家庭对话的完整记录：

{dialogue_text}

其中系统已标注有害语句：
{harmful_text}

请完成以下任务，严格按 JSON 格式返回，不输出任何其他内容：

{{
  "summary": "一句话概括本次对话的氛围和主要问题（30字以内）",
  "top_category": "主要有害类别（如：辱骂/威胁/贬低/否定/冷暴力，若无则填'无'）",
  "max_severity": 0,
  "highlights": [
    {{
      "utterance_id": "（从有害语句列表中选，填原始 id）",
      "score": 0.9,
      "reason": "为什么这句话值得关注（15字以内）",
      "rank": 1
    }}
  ]
}}

highlights 选取 3-5 条最值得关注的片段（优先选 harmful_flag=true 的），score 为 0-1 的重要性评分，rank 从 1 开始。"""

        result = {
            "summary": {"text": "", "top_category": "", "max_severity": 0},
            "highlights": [],
            "analyses": {},
        }

        try:
            raw = await self._call_llm(summary_prompt)
            parsed = self._extract_json(raw)
            result["summary"] = {
                "text": parsed.get("summary", ""),
                "top_category": parsed.get("top_category", ""),
                "max_severity": int(parsed.get("max_severity", 0)),
            }
            result["highlights"] = [
                {
                    "utterance_id": h.get("utterance_id", ""),
                    "score": float(h.get("score", 0.5)),
                    "reason": h.get("reason", ""),
                    "rank": int(h.get("rank", i + 1)),
                }
                for i, h in enumerate(parsed.get("highlights", []))
                if h.get("utterance_id")
            ]
        except Exception as e:
            logger.error(f"[ReviewGen] summary/highlights failed: {e}")
            # 降级：直接把有害 utterances 作为 highlights
            result["highlights"] = [
                {"utterance_id": u["id"], "score": 0.8, "reason": "系统标注有害", "rank": i + 1}
                for i, u in enumerate(harmful_utts[:5])
            ]

        # ── 2. 逐条 utterance 分析（只分析 harmful 的，节省 token）──
        for utt in harmful_utts:
            analysis = await self._analyze_utterance(utt["text"])
            result["analyses"][utt["id"]] = analysis

        return result

    async def _analyze_utterance(self, text: str) -> Dict[str, Any]:
        """对单条有害语句生成 severity/category/explanation/suggestion"""
        prompt = f"""你是家庭沟通分析专家。请分析以下家长对孩子说的话：

"{text}"

严格按以下 JSON 格式返回，不输出其他内容：
{{
  "severity": 3,
  "category": "贬低",
  "explanation": "这句话...（20字以内解释为何有害）",
  "suggestion": "可以换成：'...'（给出一句更温和有效的替代说法）"
}}

severity: 1-5（5最严重），category: 辱骂/威胁/贬低/否定/冷暴力/其他"""

        try:
            raw = await self._call_llm(prompt)
            parsed = self._extract_json(raw)
            return {
                "severity": int(parsed.get("severity", 1)),
                "category": parsed.get("category", "其他"),
                "explanation": parsed.get("explanation", ""),
                "suggestion": parsed.get("suggestion", ""),
            }
        except Exception as e:
            logger.error(f"[ReviewGen] utterance analysis failed for '{text[:30]}': {e}")
            return {
                "severity": 1,
                "category": "其他",
                "explanation": "分析失败",
                "suggestion": "",
            }

    async def generate_suggestion(self, text: str) -> str:
        """单独为一条 utterance 生成替代说法（按需触发）"""
        prompt = f"""家长说："{text}"

请给出一句更温和但同样有效的替代说法（直接给出替代句子，不超过30字，不需要解释）："""
        try:
            raw = await self._call_llm(prompt, temperature=0.7)
            return raw.strip().strip('"').strip("'")
        except Exception as e:
            logger.error(f"[ReviewGen] suggestion failed: {e}")
            return ""

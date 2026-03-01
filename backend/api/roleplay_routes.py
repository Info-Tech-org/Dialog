"""
Roleplay API — AI 演绎功能
- POST /api/utterances/{id}/roleplay   生成演绎（impact/rewrites/rehearsal）
- GET  /api/utterances/{id}/roleplay   获取已生成的演绎
"""

import json
import hashlib
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session as DBSession, select
from datetime import datetime

from models import Utterance, get_session
from models.roleplay_model import UtteranceRoleplay
from models.user_model import User
from api.auth import get_current_user
from offline.review_generator import ReviewGenerator
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

ROLEPLAY_PROMPT_TEMPLATE = """你是一位家庭沟通教练，专门帮助家长改善与孩子的沟通方式。

家长说了这样一句话：
"{text}"

请从以下三个方面帮助家长理解和改进：

1. **影响分析 (impact)**: 这句话可能对孩子造成什么影响？列出 2-4 个要点。
2. **替代表达 (rewrites)**: 给出 2-3 种更温和有效的替代说法，保持家长的原始意图。
3. **情景演练 (rehearsal)**: 模拟一段 3 轮对话（家长→孩子→家长），展示如何用更好的方式沟通同样的内容。

严格按以下 JSON 格式返回，不输出任何其他内容：

{{
  "impact": [
    "影响1：...",
    "影响2：..."
  ],
  "rewrites": [
    "替代说法1",
    "替代说法2"
  ],
  "rehearsal": [
    {{"role": "parent", "text": "（用更好的方式表达同样的意思）"}},
    {{"role": "child", "text": "（孩子可能的积极回应）"}},
    {{"role": "parent", "text": "（家长的后续引导）"}}
  ]
}}"""


def _prompt_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()[:16]


# ─────────────────────────────────────────────
# POST /api/utterances/{utterance_id}/roleplay
# ─────────────────────────────────────────────
@router.post("/utterances/{utterance_id}/roleplay")
async def generate_roleplay(
    utterance_id: str,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """生成 AI 演绎内容（已有缓存则直接返回）"""
    utt = db.get(Utterance, utterance_id)
    if not utt:
        raise HTTPException(status_code=404, detail="Utterance not found")

    phash = _prompt_hash(utt.text)

    # Check cache: same utterance + same prompt template
    existing = db.exec(
        select(UtteranceRoleplay)
        .where(UtteranceRoleplay.utterance_id == utterance_id)
        .order_by(UtteranceRoleplay.created_at.desc())
    ).first()

    if existing:
        try:
            content = json.loads(existing.content_json)
            return {
                "ok": True,
                "cached": True,
                "utterance_id": utterance_id,
                "text": utt.text,
                "content": content,
                "model": existing.model,
                "created_at": existing.created_at.isoformat(),
            }
        except json.JSONDecodeError:
            pass  # regenerate if stored JSON is corrupt

    # Generate via LLM
    prompt = ROLEPLAY_PROMPT_TEMPLATE.format(text=utt.text)
    gen = ReviewGenerator()

    try:
        raw = await gen._call_llm(prompt, temperature=0.7)
        content = gen._extract_json(raw)
    except httpx.HTTPStatusError as e:
        # Extract OpenRouter error body for actionable detail
        body_msg = ""
        try:
            body_msg = e.response.json().get("error", {}).get("message", "")
        except Exception:
            body_msg = e.response.text[:300]
        detail = f"LLM API {e.response.status_code}: {body_msg or str(e)}"
        logger.error(f"[roleplay] {detail} (utterance {utterance_id})")
        raise HTTPException(status_code=502, detail=detail)
    except Exception as e:
        logger.error(f"[roleplay] LLM failed for utterance {utterance_id}: {e}")
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {str(e)[:300]}")

    # Validate structure
    if not isinstance(content.get("impact"), list):
        content["impact"] = []
    if not isinstance(content.get("rewrites"), list):
        content["rewrites"] = []
    if not isinstance(content.get("rehearsal"), list):
        content["rehearsal"] = []

    # Persist
    rp = UtteranceRoleplay(
        utterance_id=utterance_id,
        user_id=user.id,
        model=settings.openrouter_model,
        content_json=json.dumps(content, ensure_ascii=False),
    )
    db.add(rp)
    db.commit()
    db.refresh(rp)

    logger.info(f"[roleplay] generated for utterance {utterance_id}: "
                f"{len(content.get('impact', []))} impacts, "
                f"{len(content.get('rewrites', []))} rewrites, "
                f"{len(content.get('rehearsal', []))} turns")

    return {
        "ok": True,
        "cached": False,
        "utterance_id": utterance_id,
        "text": utt.text,
        "content": content,
        "model": rp.model,
        "created_at": rp.created_at.isoformat(),
    }


# ─────────────────────────────────────────────
# GET /api/utterances/{utterance_id}/roleplay
# ─────────────────────────────────────────────
@router.get("/utterances/{utterance_id}/roleplay")
async def get_roleplay(
    utterance_id: str,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """获取已生成的 AI 演绎内容"""
    utt = db.get(Utterance, utterance_id)
    if not utt:
        raise HTTPException(status_code=404, detail="Utterance not found")

    existing = db.exec(
        select(UtteranceRoleplay)
        .where(UtteranceRoleplay.utterance_id == utterance_id)
        .order_by(UtteranceRoleplay.created_at.desc())
    ).first()

    if not existing:
        return {
            "ok": True,
            "exists": False,
            "utterance_id": utterance_id,
            "text": utt.text,
            "content": None,
        }

    try:
        content = json.loads(existing.content_json)
    except json.JSONDecodeError:
        content = None

    return {
        "ok": True,
        "exists": True,
        "utterance_id": utterance_id,
        "text": utt.text,
        "content": content,
        "model": existing.model,
        "created_at": existing.created_at.isoformat(),
    }

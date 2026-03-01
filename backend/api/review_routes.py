"""
Review API — 复盘功能接口
- GET  /api/sessions/{id}/review          获取会话复盘数据（summary/highlights/analyses/feedbacks）
- POST /api/sessions/{id}/generate        触发 LLM 生成并持久化
- POST /api/utterances/{id}/feedback      创建/更新用户反馈
- POST /api/utterances/{id}/suggestion    单独生成替代说法
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session as DBSession, select
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from models import Session as SessionModel, Utterance, get_session
from models.review_models import (
    UtteranceFeedback, UtteranceAnalysis, SessionHighlight, SessionSummary
)
from models.user_model import User
from api.auth import get_current_user
from offline.review_generator import ReviewGenerator
from models.db import engine
from sqlmodel import Session as DBSess

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────
# GET /api/sessions/{session_id}/review
# ─────────────────────────────────────────────
@router.get("/sessions/{session_id}/review")
async def get_session_review(
    session_id: str,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """返回会话复盘全量数据（summary + highlights + analyses + feedbacks）"""
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # summary
    summary = db.exec(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
    ).first()

    # highlights
    highlights = db.exec(
        select(SessionHighlight)
        .where(SessionHighlight.session_id == session_id)
        .order_by(SessionHighlight.rank)
    ).all()

    # analyses (indexed by utterance_id)
    analyses_rows = db.exec(
        select(UtteranceAnalysis).where(UtteranceAnalysis.session_id == session_id)
    ).all()
    analyses = {a.utterance_id: {
        "severity": a.severity,
        "category": a.category,
        "explanation": a.explanation,
        "suggestion": a.suggestion,
    } for a in analyses_rows}

    # feedbacks (indexed by utterance_id, scoped to user)
    fb_rows = db.exec(
        select(UtteranceFeedback)
        .where(UtteranceFeedback.session_id == session_id)
        .where(UtteranceFeedback.user_id == user.id)
    ).all()
    feedbacks = {f.utterance_id: {
        "is_false_positive": f.is_false_positive,
        "is_flagged": f.is_flagged,
        "is_starred": f.is_starred,
        "note": f.note,
    } for f in fb_rows}

    return {
        "generated": summary is not None,
        "summary": {
            "text": summary.summary_text if summary else "",
            "top_category": summary.top_category if summary else "",
            "max_severity": summary.max_severity if summary else 0,
            "generated_at": summary.generated_at.isoformat() if summary else None,
        },
        "highlights": [
            {
                "utterance_id": h.utterance_id,
                "score": h.score,
                "reason": h.reason,
                "rank": h.rank,
            }
            for h in highlights
        ],
        "analyses": analyses,
        "feedbacks": feedbacks,
    }


# ─────────────────────────────────────────────
# POST /api/sessions/{session_id}/generate
# ─────────────────────────────────────────────
@router.post("/sessions/{session_id}/generate")
async def generate_session_review(
    session_id: str,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """触发 LLM 生成并持久化 summary/highlights/analyses（幂等：已存在则覆盖）"""
    session = db.get(SessionModel, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    utterances = db.exec(
        select(Utterance)
        .where(Utterance.session_id == session_id)
        .order_by(Utterance.start)
    ).all()

    utt_dicts = [
        {"id": u.id, "speaker": u.speaker, "text": u.text,
         "harmful_flag": u.harmful_flag, "start": u.start}
        for u in utterances
    ]

    gen = ReviewGenerator()
    try:
        result = await gen.generate_session_review(session_id, utt_dicts)
    except Exception as e:
        logger.error(f"[review] generate failed for {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {e}")

    # ── persist summary ──
    existing_summary = db.exec(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
    ).first()
    if existing_summary:
        existing_summary.summary_text = result["summary"]["text"]
        existing_summary.top_category = result["summary"]["top_category"]
        existing_summary.max_severity = result["summary"]["max_severity"]
        existing_summary.generated_at = datetime.utcnow()
        db.add(existing_summary)
    else:
        db.add(SessionSummary(
            session_id=session_id,
            summary_text=result["summary"]["text"],
            top_category=result["summary"]["top_category"],
            max_severity=result["summary"]["max_severity"],
        ))

    # ── persist highlights (delete old, insert new) ──
    old_highlights = db.exec(
        select(SessionHighlight).where(SessionHighlight.session_id == session_id)
    ).all()
    for h in old_highlights:
        db.delete(h)

    for h in result["highlights"]:
        if h.get("utterance_id"):
            db.add(SessionHighlight(
                session_id=session_id,
                utterance_id=h["utterance_id"],
                score=h["score"],
                reason=h["reason"],
                rank=h["rank"],
            ))

    # ── persist utterance analyses ──
    for utt_id, analysis in result["analyses"].items():
        existing = db.exec(
            select(UtteranceAnalysis).where(UtteranceAnalysis.utterance_id == utt_id)
        ).first()
        if existing:
            existing.severity = analysis["severity"]
            existing.category = analysis["category"]
            existing.explanation = analysis["explanation"]
            existing.suggestion = analysis["suggestion"]
            existing.generated_at = datetime.utcnow()
            db.add(existing)
        else:
            db.add(UtteranceAnalysis(
                utterance_id=utt_id,
                session_id=session_id,
                severity=analysis["severity"],
                category=analysis["category"],
                explanation=analysis["explanation"],
                suggestion=analysis["suggestion"],
            ))

    db.commit()
    logger.info(f"[review] generated for session {session_id}: "
                f"{len(result['highlights'])} highlights, "
                f"{len(result['analyses'])} analyses")

    return {"ok": True, "session_id": session_id,
            "highlights": len(result["highlights"]),
            "analyses": len(result["analyses"])}


# ─────────────────────────────────────────────
# POST /api/utterances/{utterance_id}/feedback
# ─────────────────────────────────────────────
class FeedbackBody:
    pass

from pydantic import BaseModel

class FeedbackIn(BaseModel):
    is_false_positive: Optional[bool] = None
    is_flagged: Optional[bool] = None
    is_starred: Optional[bool] = None
    note: Optional[str] = None


@router.post("/utterances/{utterance_id}/feedback")
async def upsert_feedback(
    utterance_id: str,
    body: FeedbackIn,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """创建或更新用户对 utterance 的反馈（幂等 upsert）"""
    utt = db.get(Utterance, utterance_id)
    if not utt:
        raise HTTPException(status_code=404, detail="Utterance not found")

    existing = db.exec(
        select(UtteranceFeedback)
        .where(UtteranceFeedback.utterance_id == utterance_id)
        .where(UtteranceFeedback.user_id == user.id)
    ).first()

    if existing:
        if body.is_false_positive is not None:
            existing.is_false_positive = body.is_false_positive
        if body.is_flagged is not None:
            existing.is_flagged = body.is_flagged
        if body.is_starred is not None:
            existing.is_starred = body.is_starred
        if body.note is not None:
            existing.note = body.note
        existing.updated_at = datetime.utcnow()
        db.add(existing)
    else:
        fb = UtteranceFeedback(
            utterance_id=utterance_id,
            session_id=utt.session_id,
            user_id=user.id,
            is_false_positive=body.is_false_positive or False,
            is_flagged=body.is_flagged or False,
            is_starred=body.is_starred or False,
            note=body.note,
        )
        db.add(fb)

    db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────
# POST /api/utterances/{utterance_id}/suggestion
# ─────────────────────────────────────────────
@router.post("/utterances/{utterance_id}/suggestion")
async def generate_suggestion(
    utterance_id: str,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """按需生成替代说法并持久化（已有则直接返回缓存）"""
    utt = db.get(Utterance, utterance_id)
    if not utt:
        raise HTTPException(status_code=404, detail="Utterance not found")

    existing = db.exec(
        select(UtteranceAnalysis).where(UtteranceAnalysis.utterance_id == utterance_id)
    ).first()

    if existing and existing.suggestion:
        return {"ok": True, "suggestion": existing.suggestion, "cached": True}

    gen = ReviewGenerator()
    suggestion = await gen.generate_suggestion(utt.text)

    if existing:
        existing.suggestion = suggestion
        existing.generated_at = datetime.utcnow()
        db.add(existing)
    else:
        db.add(UtteranceAnalysis(
            utterance_id=utterance_id,
            session_id=utt.session_id,
            suggestion=suggestion,
        ))
    db.commit()
    return {"ok": True, "suggestion": suggestion, "cached": False}

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session as DBSession, select
from typing import List, Optional
from models import Session, Utterance, Device, get_session
from models.user_model import User
from pydantic import BaseModel
from datetime import datetime
from offline.cos_uploader import COSUploader
from api.auth import get_current_user
from config import settings
import os

router = APIRouter()
cos_uploader = COSUploader() if settings.tencent_cos_bucket else None


@router.get("/health")
async def health_check():
    """Health check endpoint for Docker"""
    return {"status": "healthy", "service": "family-backend"}


# Response models
class SessionResponse(BaseModel):
    session_id: str
    device_id: str
    start_time: datetime
    end_time: datetime | None
    audio_path: str | None
    audio_url: str | None
    harmful_count: int
    duration_seconds: float | None

    class Config:
        from_attributes = True


class UtteranceResponse(BaseModel):
    id: str
    session_id: str
    start: float
    end: float
    speaker: str
    text: str
    harmful_flag: bool

    class Config:
        from_attributes = True


class SessionDetailResponse(SessionResponse):
    utterances: List[UtteranceResponse]


@router.get("/sessions", response_model=List[SessionResponse])
async def get_sessions(
    request: Request,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
    device_id: str | None = None,
    has_harmful: bool | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """
    Get list of sessions with optional filters.
    Non-admin users only see sessions from their bound devices.
    """
    statement = select(Session).order_by(Session.start_time.desc())

    # Non-admin: only show sessions from user's bound devices
    if not user.is_admin:
        user_device_ids = [
            d.device_id for d in db.exec(select(Device).where(Device.user_id == user.id)).all()
        ]
        statement = statement.where(Session.device_id.in_(user_device_ids))

    # Apply filters
    if device_id:
        statement = statement.where(Session.device_id == device_id)
    if has_harmful is not None:
        if has_harmful:
            statement = statement.where(Session.harmful_count > 0)
        else:
            statement = statement.where(Session.harmful_count == 0)

    # Apply pagination
    statement = statement.offset(offset).limit(limit)

    sessions = db.exec(statement).all()

    base = settings.public_base_url or str(request.base_url).rstrip("/")

    def build_audio_url(session: Session) -> str | None:
        cos_key = getattr(session, "cos_key", None)
        if cos_key and cos_uploader:
            play_ttl = getattr(settings, "cos_presign_play_expire_seconds", 3600)
            return cos_uploader.generate_presigned_url(cos_key, play_ttl)
        if session.audio_path:
            if session.audio_path.startswith("http://") or session.audio_path.startswith("https://"):
                return session.audio_path
            filename = os.path.basename(session.audio_path)
            return f"{base}/media/{filename}"
        return None

    response = []
    for session in sessions:
        duration = None
        if session.end_time and session.start_time:
            duration = (session.end_time - session.start_time).total_seconds()

        response.append(
            SessionResponse(
                session_id=session.session_id,
                device_id=session.device_id,
                start_time=session.start_time,
                end_time=session.end_time,
                audio_path=session.audio_path,
                audio_url=build_audio_url(session),
                harmful_count=session.harmful_count,
                duration_seconds=duration,
            )
        )

    return response


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    request: Request,
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """Get detailed information for a specific session"""
    # Get session
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Non-admin: verify session belongs to user's device
    if not user.is_admin:
        user_device_ids = [
            d.device_id for d in db.exec(select(Device).where(Device.user_id == user.id)).all()
        ]
        if session.device_id not in user_device_ids:
            raise HTTPException(status_code=403, detail="无权查看该会话")

    # Get utterances
    statement = select(Utterance).where(
        Utterance.session_id == session_id
    ).order_by(Utterance.start)
    utterances = db.exec(statement).all()

    base = settings.public_base_url or str(request.base_url).rstrip("/")

    def build_audio_url(session: Session) -> str | None:
        cos_key = getattr(session, "cos_key", None)
        if cos_key and cos_uploader:
            play_ttl = getattr(settings, "cos_presign_play_expire_seconds", 3600)
            return cos_uploader.generate_presigned_url(cos_key, play_ttl)
        if session.audio_path:
            if session.audio_path.startswith("http://") or session.audio_path.startswith("https://"):
                return session.audio_path
            filename = os.path.basename(session.audio_path)
            return f"{base}/media/{filename}"
        return None

    # Calculate duration
    duration = None
    if session.end_time and session.start_time:
        duration = (session.end_time - session.start_time).total_seconds()

    # Build response
    utterance_responses = [
        UtteranceResponse(
            id=utt.id,
            session_id=utt.session_id,
            start=utt.start,
            end=utt.end,
            speaker=utt.speaker,
            text=utt.text,
            harmful_flag=utt.harmful_flag,
        )
        for utt in utterances
    ]

    return SessionDetailResponse(
        session_id=session.session_id,
        device_id=session.device_id,
        start_time=session.start_time,
        end_time=session.end_time,
        audio_path=session.audio_path,
        audio_url=build_audio_url(session),
        harmful_count=session.harmful_count,
        duration_seconds=duration,
        utterances=utterance_responses,
    )


@router.get("/utterances", response_model=List[UtteranceResponse])
async def get_utterances(
    db: DBSession = Depends(get_session),
    user: User = Depends(get_current_user),
    session_id: str | None = None,
    device_id: str | None = None,
    harmful: bool | None = None,
    limit: int = 100,
    offset: int = 0,
):
    """Get list of utterances. Non-admin users only see their devices' data."""
    statement = select(Utterance).order_by(Utterance.session_id, Utterance.start)

    # Non-admin: restrict to user's devices
    if not user.is_admin:
        user_device_ids = [
            d.device_id for d in db.exec(select(Device).where(Device.user_id == user.id)).all()
        ]
        statement = statement.join(Session).where(Session.device_id.in_(user_device_ids))
    elif device_id:
        # Admin with device_id filter still needs the join
        statement = statement.join(Session)

    # Filter by session_id directly
    if session_id:
        statement = statement.where(Utterance.session_id == session_id)

    # Filter by device_id
    if device_id:
        if user.is_admin:
            statement = statement.where(Session.device_id == device_id)

    # Filter by harmful flag
    if harmful is not None:
        statement = statement.where(Utterance.harmful_flag == harmful)

    # Apply pagination
    statement = statement.offset(offset).limit(limit)

    utterances = db.exec(statement).all()

    return [
        UtteranceResponse(
            id=utt.id,
            session_id=utt.session_id,
            start=utt.start,
            end=utt.end,
            speaker=utt.speaker,
            text=utt.text,
            harmful_flag=utt.harmful_flag,
        )
        for utt in utterances
    ]


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

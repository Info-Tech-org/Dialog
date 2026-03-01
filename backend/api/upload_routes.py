"""
Audio Upload API Routes
音频文件上传 API
"""

import os
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session as DBSession
import asyncio
import logging

from models import get_session, Session as SessionModel
from config import settings
from offline.offline_worker import OfflineProcessor
from api.auth import get_current_active_user
from models.user_model import User

router = APIRouter()
logger = logging.getLogger(__name__)

# Store upload sessions for progress tracking
upload_sessions = {}


@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    device_id: str = "web_upload",
    background_tasks: BackgroundTasks = None,
    current_user: User = Depends(get_current_active_user),
    db: DBSession = Depends(get_session)
):
    """
    上传音频文件进行处理

    模拟硬件设备的音频上传，用于测试系统功能

    Args:
        file: 音频文件 (WAV, MP3, etc.)
        device_id: 设备ID（默认为web_upload）
        background_tasks: 后台任务
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        {
            "session_id": "uuid",
            "message": "Processing started",
            "filename": "xxx.wav"
        }
    """
    # Validate file type - check extension as fallback
    valid_extensions = ['.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac', '.wma']
    file_ext = os.path.splitext(file.filename)[1].lower()

    if not (file.content_type and file.content_type.startswith('audio/')) and file_ext not in valid_extensions:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Please upload an audio file (WAV, MP3, M4A, etc.)"
        )

    # Create session
    session_id = str(uuid.uuid4())
    timestamp = datetime.utcnow()

    # Save uploaded file
    audio_dir = os.path.join(settings.audio_storage_path, "uploads")
    os.makedirs(audio_dir, exist_ok=True)

    file_extension = os.path.splitext(file.filename)[1]
    saved_filename = f"{session_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}{file_extension}"
    file_path = os.path.join(audio_dir, saved_filename)

    # Save file
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    logger.info(f"Uploaded audio file: {file_path} ({len(content)} bytes)")

    # Create database session record
    db_session = SessionModel(
        session_id=session_id,
        device_id=device_id,
        start_time=timestamp,
        audio_path=file_path,
        harmful_count=0
    )
    db.add(db_session)
    db.commit()

    # Initialize upload session for progress tracking
    upload_sessions[session_id] = {
        "status": "processing",
        "progress": 0,
        "message": "Starting processing...",
        "filename": file.filename
    }

    # Process in background
    if background_tasks:
        background_tasks.add_task(
            process_uploaded_audio,
            session_id=session_id,
            file_path=file_path,
            db=db
        )

    return {
        "session_id": session_id,
        "message": "Upload successful, processing started",
        "filename": file.filename,
        "size": len(content)
    }


async def process_uploaded_audio(session_id: str, file_path: str, db: DBSession):
    """
    处理上传的音频文件

    Args:
        session_id: 会话ID
        file_path: 音频文件路径
        db: 数据库会话
    """
    try:
        upload_sessions[session_id]["status"] = "processing"
        upload_sessions[session_id]["progress"] = 10
        upload_sessions[session_id]["message"] = "Uploading to cloud..."

        # COS upload (when configured) is performed inside OfflineProcessor.process()
        logger.info(f"Processing audio file: {file_path}")

        # Use offline processor
        processor = OfflineProcessor()

        upload_sessions[session_id]["progress"] = 30
        upload_sessions[session_id]["message"] = "Transcribing audio..."

        # Process audio (this will use placeholder data for local files)
        utterances = processor.process(file_path, session_id)

        upload_sessions[session_id]["progress"] = 80
        upload_sessions[session_id]["message"] = "Analyzing content..."

        # Update session with results
        session = db.get(SessionModel, session_id)
        if session:
            session.end_time = datetime.utcnow()
            session.harmful_count = sum(1 for u in utterances if u.get("harmful_flag", False))
            db.add(session)
            db.commit()

        upload_sessions[session_id]["status"] = "completed"
        upload_sessions[session_id]["progress"] = 100
        upload_sessions[session_id]["message"] = "Processing completed"
        upload_sessions[session_id]["utterance_count"] = len(utterances)
        upload_sessions[session_id]["harmful_count"] = session.harmful_count

        logger.info(f"Audio processing completed for session {session_id}")

    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
        upload_sessions[session_id]["status"] = "error"
        upload_sessions[session_id]["message"] = f"Error: {str(e)}"


@router.get("/upload/status/{session_id}")
async def get_upload_status(
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    获取上传处理状态

    Args:
        session_id: 会话ID
        current_user: 当前登录用户

    Returns:
        上传和处理状态信息
    """
    if session_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return upload_sessions[session_id]


@router.post("/upload/test")
async def create_test_upload_session(
    current_user: User = Depends(get_current_active_user)
):
    """
    创建测试上传会话（用于前端开发测试）

    不需要实际上传文件，直接创建模拟数据
    """
    from backend.scripts.create_test_data import create_test_sessions

    # This would normally be called differently, but for testing we can trigger it
    return {
        "message": "Test data creation endpoint",
        "instructions": "Use the create_test_data.py script instead"
    }

from fastapi import APIRouter, Header, HTTPException, Request, BackgroundTasks, Depends
from typing import Optional, Dict, Any
from pathlib import Path
import wave
import datetime as dt
import os
import logging
from sqlmodel import Session as DBSession

from models import Session as SessionModel, engine
from offline.offline_worker import OfflineProcessor
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

UPLOAD_DIR = (Path(__file__).resolve().parents[1] / "data" / "audio" / "uploads").resolve()
INGEST_DIR = UPLOAD_DIR / "ingest"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
INGEST_DIR.mkdir(parents=True, exist_ok=True)

# In-memory status tracking (MVP: single-process only)
# Structure: {
#   "session_id": {
#     "status": "receiving" | "processing" | "completed" | "error",
#     "expected_next_index": int,  # For idempotency/ordering
#     "received_bytes": int,
#     "chunks": int,
#     "wav_path": str | None,
#     ...
#   }
# }
ingest_status: Dict[str, Dict[str, Any]] = {}


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _verify_device_token(x_device_token: Optional[str] = Header(None, alias="X-Device-Token")):
    """
    Verify device token for ingest endpoints.
    If DEVICE_INGEST_TOKEN is set in settings, require matching token in header.
    """
    if settings.device_ingest_token:
        if not x_device_token or x_device_token != settings.device_ingest_token:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: Invalid or missing device token"
            )


def _process_audio_background(session_id: str, wav_path: str, device_id: Optional[str]):
    """
    Background task to process audio with OfflineProcessor.
    Updates ingest_status dict with results or errors.

    Note: This is a fire-and-forget task that runs after response is sent.
    If the server restarts, this task will be lost (MVP limitation).
    """
    try:
        logger.info(f"Background processing started for session {session_id}")
        processor = OfflineProcessor()
        utterances = processor.process(wav_path, session_id)
        harmful_count = sum(1 for u in utterances if u.get("harmful_flag", False))

        # Update session in database
        with DBSession(engine) as db:
            session = db.get(SessionModel, session_id)
            now = dt.datetime.utcnow()
            if session is None:
                session = SessionModel(
                    session_id=session_id,
                    device_id=device_id or "esp32",
                    start_time=now,
                    end_time=now,
                    audio_path=wav_path,
                    harmful_count=harmful_count,
                )
                db.add(session)
            else:
                session.end_time = now
                session.audio_path = wav_path
                session.harmful_count = harmful_count
                if device_id:
                    session.device_id = device_id
                db.add(session)
            db.commit()

        # Update status dict
        if session_id in ingest_status:
            ingest_status[session_id]["status"] = "completed"
            ingest_status[session_id]["utterance_count"] = len(utterances)
            ingest_status[session_id]["harmful_count"] = harmful_count
            ingest_status[session_id]["message"] = "completed"

        logger.info(f"Background processing completed for session {session_id}: {len(utterances)} utterances, {harmful_count} harmful")

    except Exception as e:
        logger.error(f"Background processing failed for session {session_id}: {e}", exc_info=True)
        # Update status to error (truncate message to avoid huge error strings)
        if session_id in ingest_status:
            ingest_status[session_id]["status"] = "error"
            ingest_status[session_id]["message"] = f"Error: {str(e)[:200]}"


@router.post("/pcm")
async def ingest_pcm(
    request: Request,
    background_tasks: BackgroundTasks,
    x_session_id: str = Header(..., alias="X-Session-Id"),
    x_chunk_index: int = Header(..., alias="X-Chunk-Index"),
    x_is_final: str = Header(..., alias="X-Is-Final"),
    x_sample_rate: int = Header(..., alias="X-Sample-Rate"),
    x_channels: int = Header(..., alias="X-Channels"),
    x_bit_depth: int = Header(..., alias="X-Bit-Depth"),
    x_pcm_format: str = Header(..., alias="X-PCM-Format"),
    x_filename: Optional[str] = Header(None, alias="X-Filename"),
    x_device_id: Optional[str] = Header(None, alias="X-Device-Id"),
    _token_verified: None = Depends(_verify_device_token),
):
    """
    PCM chunk ingestion endpoint with idempotency and ordering control.

    Idempotency: Same (session_id, chunk_index) can be sent multiple times (retry-safe).
    Ordering: Chunks must arrive in sequential order (0, 1, 2, ...).
    """
    if x_sample_rate != 16000 or x_channels != 1 or x_bit_depth != 16 or x_pcm_format != "s16le":
        raise HTTPException(status_code=400, detail="Unsupported PCM format (only 16kHz/16bit/mono/s16le)")

    is_final = _parse_bool(x_is_final)
    pcm_path = INGEST_DIR / f"{x_session_id}.pcm"
    data = await request.body()

    # Initialize or get session status
    status = ingest_status.setdefault(
        x_session_id,
        {
            "status": "receiving",
            "expected_next_index": 0,
            "received_bytes": 0,
            "chunks": 0,
            "wav_path": None,
            "utterance_count": 0,
            "harmful_count": 0,
            "message": "receiving",
        },
    )

    expected = status["expected_next_index"]

    # Idempotency: Duplicate chunk (retry)
    if x_chunk_index < expected:
        logger.info(f"Session {x_session_id}: Duplicate chunk {x_chunk_index} (expected {expected}), treating as retry")
        return {
            "ok": True,
            "session_id": x_session_id,
            "chunk": x_chunk_index,
            "message": f"Chunk {x_chunk_index} already received (idempotent retry)"
        }

    # Ordering: Out-of-order chunk
    if x_chunk_index > expected:
        logger.warning(f"Session {x_session_id}: Out-of-order chunk {x_chunk_index} (expected {expected})")
        raise HTTPException(
            status_code=409,
            detail={
                "error": "Out of order chunk",
                "received_index": x_chunk_index,
                "expected_next_index": expected,
                "message": f"Expected chunk {expected} but received {x_chunk_index}"
            }
        )

    # Valid chunk: append to PCM file
    with open(pcm_path, "ab") as f:
        f.write(data)

    status["received_bytes"] += len(data)
    status["chunks"] += 1
    status["expected_next_index"] = x_chunk_index + 1
    status["message"] = f"received chunk {x_chunk_index}"

    if not is_final:
        return {
            "ok": True,
            "session_id": x_session_id,
            "chunk": x_chunk_index,
            "received_bytes": status["received_bytes"]
        }

    # Final chunk: assemble WAV
    status["status"] = "processing"
    status["message"] = "assembling wav"
    wav_path = UPLOAD_DIR / f"{x_session_id}.wav"

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(16000)
        with open(pcm_path, "rb") as pf:
            while True:
                chunk = pf.read(4096)
                if not chunk:
                    break
                wf.writeframes(chunk)

    status["wav_path"] = str(wav_path)
    status["message"] = "processing in background"

    # Build audio_url for client
    audio_filename = f"{x_session_id}.wav"
    if settings.public_base_url:
        audio_url = f"{settings.public_base_url}/media/{audio_filename}"
    else:
        # Fallback to request base URL
        base = str(request.base_url).rstrip("/")
        audio_url = f"{base}/media/{audio_filename}"

    # Schedule offline processing as background task
    background_tasks.add_task(
        _process_audio_background,
        session_id=x_session_id,
        wav_path=str(wav_path),
        device_id=x_device_id
    )

    # Return immediately with audio_url
    return {
        "ok": True,
        "session_id": x_session_id,
        "final": True,
        "audio_url": audio_url,
        "received_bytes": status["received_bytes"],
        "chunks": status["chunks"]
    }


@router.get("/status/{session_id}")
async def ingest_status_detail(
    session_id: str,
    _token_verified: None = Depends(_verify_device_token),
):
    if session_id not in ingest_status:
        raise HTTPException(status_code=404, detail="Session not found")
    return ingest_status[session_id]

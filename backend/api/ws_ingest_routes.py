"""
WebSocket PCM Ingest - Long connection streaming upload
替代 HTTP POST /api/ingest/pcm 的长连接方案，解决每片 HTTP 请求开销导致的堆积问题
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, BackgroundTasks
from typing import Optional, Dict, Any
from pathlib import Path
import asyncio
import wave
import datetime as dt
import struct
import logging
import json
from sqlmodel import Session as DBSession, select

from models import Session as SessionModel, Device, engine
from offline.offline_worker import OfflineProcessor
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# 旁听者 WebSocket 连接池: session_id → set of WebSocket
ws_listeners: Dict[str, set] = {}

# 设备级旁听者: device_id → set of WebSocket（跨会话持续监听）
ws_device_listeners: Dict[str, set] = {}


async def _broadcast_to_listeners(session_id: str, pcm_payload: bytes) -> None:
    """将 PCM 数据广播给该 session 的所有旁听者，单个失败不影响其他"""
    listeners = ws_listeners.get(session_id)
    if not listeners:
        return
    dead = []
    for ws in listeners:
        try:
            await ws.send_bytes(pcm_payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        listeners.discard(ws)


async def _broadcast_to_device_listeners(device_id: str, pcm_payload: bytes) -> None:
    """将 PCM 数据广播给该设备的所有持续旁听者"""
    listeners = ws_device_listeners.get(device_id)
    if not listeners:
        return
    dead = []
    for ws in listeners:
        try:
            await ws.send_bytes(pcm_payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        listeners.discard(ws)


def _append_pcm_chunk(pcm_path: Path, payload: bytes) -> None:
    """Synchronous disk append — runs in thread pool so it doesn't block the event loop."""
    with open(pcm_path, "ab") as f:
        f.write(payload)


def _pcm_to_wav(pcm_path: Path, wav_path: Path) -> None:
    """Convert raw PCM file to WAV (16kHz, 16-bit, mono). Runs in thread pool."""
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        with open(pcm_path, "rb") as pf:
            while True:
                chunk = pf.read(4096)
                if not chunk:
                    break
                wf.writeframes(chunk)

UPLOAD_DIR = (Path(__file__).resolve().parents[1] / "data" / "audio" / "uploads").resolve()
INGEST_DIR = UPLOAD_DIR / "ingest"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
INGEST_DIR.mkdir(parents=True, exist_ok=True)

# WebSocket session状态 (复用 HTTP 版本的 ingest_status 逻辑)
# Structure: {
#   "session_id": {
#     "status": "receiving" | "processing" | "completed" | "error",
#     "expected_next_index": int,
#     "received_bytes": int,
#     "chunks": int,
#     "wav_path": str | None,
#     ...
#   }
# }
ws_ingest_status: Dict[str, Dict[str, Any]] = {}


def _verify_ws_device_token(device_token: Optional[str]) -> bool:
    """验证 WebSocket 连接的 device token"""
    if settings.device_ingest_token:
        return device_token == settings.device_ingest_token
    return True  # 如果没有配置 token，默认允许


def _lookup_device_owner(device_id: Optional[str]) -> Optional[int]:
    """查找 device_id 绑定的 user_id，未绑定返回 None"""
    if not device_id:
        return None
    with DBSession(engine) as db:
        device = db.exec(select(Device).where(Device.device_id == device_id)).first()
        if device:
            return device.user_id
    return None


def _set_device_online(device_id: Optional[str], online: bool) -> None:
    """更新设备在线状态和 last_seen；首次连接时自动创建设备记录"""
    if not device_id:
        return
    with DBSession(engine) as db:
        device = db.exec(select(Device).where(Device.device_id == device_id)).first()
        if device:
            device.is_online = online
            device.last_seen = dt.datetime.utcnow()
            db.add(device)
            db.commit()
        elif online:
            # Auto-create device record on first WS connect (user_id=None, unbound)
            device = Device(
                device_id=device_id,
                user_id=None,
                name="",
                is_online=True,
                last_seen=dt.datetime.utcnow(),
            )
            db.add(device)
            db.commit()
            logger.info(f"[Device] Auto-created device record: {device_id}")


def _process_audio_background_ws(session_id: str, wav_path: str, device_id: Optional[str], user_id: Optional[int] = None):
    """
    Background task for WebSocket - identical to HTTP version
    """
    try:
        logger.info(f"[WS] Background processing started for session {session_id}")
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
                    device_id=device_id or "esp32-ws",
                    start_time=now,
                    end_time=now,
                    audio_path=wav_path,
                    harmful_count=harmful_count,
                    user_id=user_id,
                )
                db.add(session)
            else:
                session.end_time = now
                session.audio_path = wav_path
                session.harmful_count = harmful_count
                if device_id:
                    session.device_id = device_id
                if user_id and not session.user_id:
                    session.user_id = user_id
                db.add(session)
            db.commit()

        # Update status dict
        if session_id in ws_ingest_status:
            ws_ingest_status[session_id]["status"] = "completed"
            ws_ingest_status[session_id]["utterance_count"] = len(utterances)
            ws_ingest_status[session_id]["harmful_count"] = harmful_count
            ws_ingest_status[session_id]["message"] = "completed"

        logger.info(f"[WS] Background processing completed for session {session_id}: {len(utterances)} utterances, {harmful_count} harmful")

    except Exception as e:
        logger.error(f"[WS] Background processing failed for session {session_id}: {e}", exc_info=True)
        if session_id in ws_ingest_status:
            ws_ingest_status[session_id]["status"] = "error"
            ws_ingest_status[session_id]["message"] = f"Error: {str(e)[:200]}"


async def _ws_ingest_raw(
    websocket: WebSocket,
    session_id: Optional[str],
    device_id: Optional[str],
) -> None:
    """
    协议 B：裸 PCM 流模式（raw=1）
    - 无 5 字节头，直接发二进制 PCM
    - 不发 ACK
    - 断开即触发 ASR
    """
    await websocket.accept()

    # 自动生成 session_id
    if not session_id:
        ts = dt.datetime.utcnow().strftime("%Y%m%d%H%M%S")
        suffix = abs(hash(device_id or "unknown")) % 100000
        session_id = f"{ts}_{suffix}"

    logger.info(f"[WS-RAW] Connection accepted: session={session_id} device={device_id}")

    owner_user_id = _lookup_device_owner(device_id)
    _set_device_online(device_id, True)

    pcm_path = INGEST_DIR / f"{session_id}.pcm"
    status = ws_ingest_status.setdefault(session_id, {
        "status": "receiving",
        "device_id": device_id,
        "expected_next_index": 0,
        "received_bytes": 0,
        "chunks": 0,
        "wav_path": None,
        "utterance_count": 0,
        "harmful_count": 0,
        "message": "receiving (raw mode)",
    })

    # Lazy import to avoid circular dependency
    from api.ws_realtime_routes import forward_audio_to_asr

    try:
        while True:
            data = await websocket.receive_bytes()
            if not data:
                continue
            status["received_bytes"] += len(data)
            status["chunks"] += 1
            status["expected_next_index"] += 1
            # Broadcast to live listeners (audio)
            if device_id:
                await _broadcast_to_device_listeners(device_id, data)
            # Forward to realtime ASR bridge (subtitles, if any subscriber)
            if device_id:
                await forward_audio_to_asr(device_id, data)
            # Async disk write
            await asyncio.to_thread(_append_pcm_chunk, pcm_path, data)

    except WebSocketDisconnect:
        logger.info(f"[WS-RAW] Device disconnected: session={session_id}, bytes={status['received_bytes']}")
    except Exception as e:
        logger.error(f"[WS-RAW] Error session={session_id}: {e}", exc_info=True)
    finally:
        _set_device_online(device_id, False)

    # 无论正常断开还是异常，只要收到了数据就触发处理
    if status["received_bytes"] < 640:
        logger.warning(f"[WS-RAW] Session {session_id}: too short ({status['received_bytes']} bytes), skip processing")
        ws_ingest_status[session_id]["status"] = "skipped"
        return

    wav_path = UPLOAD_DIR / f"{session_id}.wav"
    status["status"] = "processing"
    status["message"] = "assembling wav"

    async def _finalize_raw():
        await asyncio.to_thread(_pcm_to_wav, pcm_path, wav_path)
        status["wav_path"] = str(wav_path)
        asyncio.create_task(asyncio.to_thread(
            _process_audio_background_ws,
            session_id=session_id,
            wav_path=str(wav_path),
            device_id=device_id,
            user_id=owner_user_id,
        ))

    asyncio.create_task(_finalize_raw())


@router.websocket("/pcm")
async def ws_ingest_pcm(
    websocket: WebSocket,
    device_token: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    device_id: Optional[str] = Query(None),
    raw: Optional[int] = Query(None),
):
    """
    WebSocket PCM 分片上传端点

    协议 A（默认，raw 不传或 raw=0）：
    - 每帧格式：[0:4] chunk_index (uint32 big-endian) | [4] flags (bit0=is_final) | [5:] PCM payload
    - 服务端返回 JSON ACK，收到 final=1 后关闭连接

    协议 B（raw=1，无头部裸流模式，适合 IoT 设备连续推流）：
    - session_id 可不传，服务端按 device_id + 时间戳自动生成
    - 每帧为裸 PCM 二进制（s16le, 16kHz, mono），无头部，无 ACK
    - 设备断开连接即视为 final，自动触发 ASR 处理
    """
    # Step 1: 验证 token
    if not _verify_ws_device_token(device_token):
        logger.warning(f"[WS] Unauthorized connection attempt with token: {device_token}")
        await websocket.close(code=1008, reason="Unauthorized: Invalid device token")
        return

    # raw=1 模式走单独的处理函数
    if raw == 1:
        await _ws_ingest_raw(websocket, session_id=session_id, device_id=device_id)
        return

    # Step 2: 验证 session_id
    if not session_id:
        logger.warning(f"[WS] Connection attempt without session_id")
        await websocket.close(code=1002, reason="Missing session_id parameter")
        return

    # Accept connection
    await websocket.accept()
    logger.info(f"[WS] Connection accepted for session {session_id}, device {device_id}")

    # Look up device owner and set online
    owner_user_id = _lookup_device_owner(device_id)
    _set_device_online(device_id, True)

    # Initialize session status
    pcm_path = INGEST_DIR / f"{session_id}.pcm"
    status = ws_ingest_status.setdefault(
        session_id,
        {
            "status": "receiving",
            "device_id": device_id,
            "expected_next_index": 0,
            "received_bytes": 0,
            "chunks": 0,
            "wav_path": None,
            "utterance_count": 0,
            "harmful_count": 0,
            "message": "receiving",
        },
    )

    try:
        while True:
            # Receive binary message
            data = await websocket.receive_bytes()

            # Parse frame header (5 bytes minimum)
            if len(data) < 5:
                await websocket.send_text(json.dumps({
                    "ok": False,
                    "error": "Invalid frame: too short (min 5 bytes)"
                }))
                continue

            # Parse header
            chunk_index = struct.unpack('>I', data[0:4])[0]  # uint32 big-endian
            flags = data[4]
            is_final = bool(flags & 0x01)
            pcm_payload = data[5:]

            logger.info(f"[WS] Session {session_id}: received chunk {chunk_index}, is_final={is_final}, payload_size={len(pcm_payload)}")

            expected = status["expected_next_index"]

            # Idempotency: duplicate chunk (retry)
            if chunk_index < expected:
                logger.info(f"[WS] Session {session_id}: Duplicate chunk {chunk_index} (expected {expected}), treating as retry")
                await websocket.send_text(json.dumps({
                    "ok": True,
                    "chunk_index": chunk_index,
                    "message": "duplicate (idempotent)"
                }))
                continue

            # Ordering: out-of-order chunk
            if chunk_index > expected:
                logger.warning(f"[WS] Session {session_id}: Out-of-order chunk {chunk_index} (expected {expected})")
                await websocket.send_text(json.dumps({
                    "ok": False,
                    "error": "out_of_order",
                    "chunk_index": chunk_index,
                    "expected": expected
                }))
                continue

            # Valid chunk: update state and ACK immediately (before disk write)
            status["received_bytes"] += len(pcm_payload)
            status["chunks"] += 1
            status["expected_next_index"] = chunk_index + 1
            status["message"] = f"received chunk {chunk_index}"

            # ACK first, then write async — prevents blocking the ESP32
            if not is_final:
                await websocket.send_text(json.dumps({
                    "ok": True,
                    "chunk_index": chunk_index,
                    "received_bytes": status["received_bytes"]
                }))
                # Broadcast to web listeners (after ACK, before disk write)
                await _broadcast_to_listeners(session_id, pcm_payload)
                if device_id:
                    await _broadcast_to_device_listeners(device_id, pcm_payload)
                # Async disk write after ACK
                await asyncio.to_thread(_append_pcm_chunk, pcm_path, pcm_payload)
                continue

            # Final chunk: ACK immediately, then assemble WAV async
            logger.info(f"[WS] Session {session_id}: Final chunk received, assembling WAV")
            status["status"] = "processing"
            status["message"] = "assembling wav"
            wav_path = UPLOAD_DIR / f"{session_id}.wav"

            # Build audio_url
            audio_filename = f"{session_id}.wav"
            if settings.public_base_url:
                audio_url = f"{settings.public_base_url}/media/{audio_filename}"
            else:
                audio_url = f"http://43.142.49.126:9000/media/{audio_filename}"

            # ACK final immediately — device gets audio_url without waiting for disk
            await websocket.send_text(json.dumps({
                "ok": True,
                "final": True,
                "session_id": session_id,
                "audio_url": audio_url,
                "received_bytes": status["received_bytes"],
                "chunks": status["chunks"]
            }))

            # Broadcast final chunk + notify listeners session ended
            await _broadcast_to_listeners(session_id, pcm_payload)
            # Send JSON "end" signal to session listeners
            listeners = ws_listeners.get(session_id)
            if listeners:
                end_msg = json.dumps({"type": "end", "session_id": session_id})
                for ws in list(listeners):
                    try:
                        await ws.send_text(end_msg)
                    except Exception:
                        pass
            # Send final chunk + "boundary" to device listeners (keep alive)
            if device_id:
                await _broadcast_to_device_listeners(device_id, pcm_payload)
                dev_listeners = ws_device_listeners.get(device_id)
                if dev_listeners:
                    boundary_msg = json.dumps({"type": "boundary", "session_id": session_id})
                    for ws in list(dev_listeners):
                        try:
                            await ws.send_text(boundary_msg)
                        except Exception:
                            pass

            # Async: write final chunk to disk, convert PCM→WAV, then trigger ASR
            async def _finalize():
                await asyncio.to_thread(_append_pcm_chunk, pcm_path, pcm_payload)
                await asyncio.to_thread(_pcm_to_wav, pcm_path, wav_path)
                status["wav_path"] = str(wav_path)
                status["message"] = "processing in background"
                asyncio.create_task(asyncio.to_thread(
                    _process_audio_background_ws,
                    session_id=session_id,
                    wav_path=str(wav_path),
                    device_id=device_id,
                    user_id=owner_user_id,
                ))

            asyncio.create_task(_finalize())

            # Close connection gracefully after final
            _set_device_online(device_id, False)
            await websocket.close(code=1000, reason="Session completed")
            logger.info(f"[WS] Session {session_id} completed and closed")
            break

    except WebSocketDisconnect:
        logger.info(f"[WS] Client disconnected for session {session_id}")
        _set_device_online(device_id, False)
        if session_id in ws_ingest_status and ws_ingest_status[session_id]["status"] == "receiving":
            ws_ingest_status[session_id]["status"] = "disconnected"
            ws_ingest_status[session_id]["message"] = "client disconnected before final"
    except Exception as e:
        logger.error(f"[WS] Error in session {session_id}: {e}", exc_info=True)
        _set_device_online(device_id, False)
        try:
            await websocket.send_text(json.dumps({
                "ok": False,
                "error": "server_error",
                "message": str(e)[:200]
            }))
        except:
            pass
        finally:
            await websocket.close(code=1011, reason="Internal server error")


@router.get("/ws/status/{session_id}")
async def ws_ingest_status_detail(session_id: str):
    """查询 WebSocket session 状态（用于调试）"""
    if session_id not in ws_ingest_status:
        raise HTTPException(status_code=404, detail="Session not found")
    return ws_ingest_status[session_id]


@router.get("/active")
async def ws_ingest_active_sessions():
    """返回当前正在接收数据的 session 列表（供前端实时监听页面轮询）"""
    sessions = []
    for sid, st in ws_ingest_status.items():
        if st.get("status") == "receiving":
            sessions.append({
                "session_id": sid,
                "device_id": st.get("device_id"),
                "chunks": st.get("chunks", 0),
                "received_bytes": st.get("received_bytes", 0),
                "listener_count": len(ws_listeners.get(sid, set())),
                "device_listener_count": len(ws_device_listeners.get(st.get("device_id", ""), set())),
            })
    return {"active": sessions}


@router.websocket("/listen")
async def ws_listen(
    websocket: WebSocket,
    session_id: str = Query(...),
):
    """
    旁听 WebSocket 端点 — 浏览器连接后实时接收指定 session 的 PCM 音频流

    发送给浏览器的消息:
    - binary: 原始 PCM payload (s16le, 16kHz, mono)
    - text JSON: {"type":"end","session_id":"..."} 表示会话结束
    """
    await websocket.accept()
    logger.info(f"[Listen] Browser connected to listen session {session_id}")

    # 加入 listeners
    if session_id not in ws_listeners:
        ws_listeners[session_id] = set()
    ws_listeners[session_id].add(websocket)

    try:
        # 保持连接，等待客户端断开或服务端关闭
        while True:
            # 客户端可以发 ping/text 来保持连接，我们忽略内容
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"[Listen] Browser disconnected from session {session_id}")
    except Exception as e:
        logger.error(f"[Listen] Error in listen session {session_id}: {e}")
    finally:
        ws_listeners.get(session_id, set()).discard(websocket)
        if session_id in ws_listeners and not ws_listeners[session_id]:
            del ws_listeners[session_id]


@router.websocket("/device-listen")
async def ws_device_listen(
    websocket: WebSocket,
    device_id: str = Query(...),
):
    """
    设备级持续旁听端点 — 跨会话持续接收指定设备的 PCM 音频流

    发送给浏览器的消息:
    - binary: 原始 PCM payload (s16le, 16kHz, mono)
    - text JSON: {"type":"boundary","session_id":"..."} 表示会话边界（连接保持）
    """
    await websocket.accept()
    logger.info(f"[DeviceListen] Browser connected to device {device_id}")

    if device_id not in ws_device_listeners:
        ws_device_listeners[device_id] = set()
    ws_device_listeners[device_id].add(websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"[DeviceListen] Browser disconnected from device {device_id}")
    except Exception as e:
        logger.error(f"[DeviceListen] Error for device {device_id}: {e}")
    finally:
        ws_device_listeners.get(device_id, set()).discard(websocket)
        if device_id in ws_device_listeners and not ws_device_listeners[device_id]:
            del ws_device_listeners[device_id]

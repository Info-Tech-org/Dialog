"""
WebSocket Realtime ASR + Harmful Detection
实时语音识别 + 有害语言检测 WebSocket 端点

流程:
1. 设备通过 WebSocket 发送 PCM 音频流
2. 后端转发给腾讯云实时 ASR
3. 接收 ASR 识别结果
4. 实时检测有害内容
5. 如果检测到有害内容，立即返回警告给设备
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional, Dict, Any
import logging
import json
import asyncio
from datetime import datetime

from realtime.tencent_asr import TencentRealtimeASR
from realtime.harmful_rules import is_harmful_advanced
from config import settings
from models import Session as SessionModel, Utterance as UtteranceModel, engine
from sqlmodel import Session as DBSession

logger = logging.getLogger(__name__)

router = APIRouter()

# 存储活跃的 WebSocket 会话
active_sessions: Dict[str, Dict[str, Any]] = {}

# ── Realtime ASR Bridge (供 /ws/ingest/pcm?raw=1 调用) ──────────
# device_id → { asr_client, subscribers: set, reader_task, session_id, ... }
_asr_bridges: Dict[str, Dict[str, Any]] = {}

ASR_CHUNK_BYTES = 6400           # 200ms @ 16kHz * 16-bit mono
ASR_CHUNK_INTERVAL_SEC = 0.2     # Tencent realtime recommendation
ASR_AUDIO_QUEUE_MAX = 256

async def forward_audio_to_asr(device_id: str, data: bytes) -> None:
    """Called from ws_ingest_routes._ws_ingest_raw to pipe audio to realtime ASR.
    If no bridge exists for this device (no web subscriber), this is a no-op."""
    bridge = _asr_bridges.get(device_id)
    if not bridge:
        return
    q: Optional[asyncio.Queue] = bridge.get("audio_queue")
    if not q:
        return
    try:
        q.put_nowait(data)
        bridge["audio_ingest_bytes"] += len(data)
    except asyncio.QueueFull:
        bridge["audio_drop_chunks"] += 1
        bridge["audio_drop_bytes"] += len(data)


async def _asr_sender_loop(device_id: str) -> None:
    """Aggregate device PCM into 6400-byte chunks and pace sends at 200ms."""
    bridge = _asr_bridges.get(device_id)
    if not bridge:
        return
    asr_client = bridge["asr_client"]
    q: asyncio.Queue = bridge["audio_queue"]
    buf = bytearray()
    try:
        while device_id in _asr_bridges and asr_client.is_connected:
            try:
                data = await asyncio.wait_for(q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if not data:
                continue
            buf.extend(data)

            while len(buf) >= ASR_CHUNK_BYTES and asr_client.is_connected:
                chunk = bytes(buf[:ASR_CHUNK_BYTES])
                del buf[:ASR_CHUNK_BYTES]
                await asr_client.send_audio(chunk)
                bridge["audio_sent_chunks"] += 1
                bridge["audio_sent_bytes"] += len(chunk)
                await asyncio.sleep(ASR_CHUNK_INTERVAL_SEC)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"[ASR-Bridge] Sender loop error for {device_id}: {e}", exc_info=True)
    finally:
        # Flush tail when bridge stops so final words can still be recognized.
        if buf and asr_client.is_connected:
            try:
                await asr_client.send_audio(bytes(buf))
                bridge["audio_sent_chunks"] += 1
                bridge["audio_sent_bytes"] += len(buf)
            except Exception:
                pass


def _verify_device_token(device_token: Optional[str]) -> bool:
    """验证设备 token"""
    if settings.device_ingest_token:
        return device_token == settings.device_ingest_token
    return True


@router.websocket("/stream")
async def ws_realtime_stream(
    websocket: WebSocket,
    device_token: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    device_id: Optional[str] = Query(None),
):
    """
    实时语音流 WebSocket 端点

    设备发送: 纯 PCM 音频数据 (binary)
    服务器返回: JSON 消息

    返回消息类型:
    1. ASR 识别结果:
       {
         "type": "asr",
         "text": "识别的文本",
         "is_final": true/false,
         "start": 0.0,
         "end": 1.5
       }

    2. 有害内容警告:
       {
         "type": "harmful_alert",
         "text": "检测到的有害文本",
         "keywords": ["关键词1", "关键词2"],
         "severity": 3,
         "timestamp": 1234567890.123,
         "action": "warning"  # warning 或 block
       }

    3. 状态消息:
       {
         "type": "status",
         "message": "连接成功",
         "session_id": "xxx"
       }

    4. 错误消息:
       {
         "type": "error",
         "message": "错误描述"
       }
    """

    # 验证 token
    if not _verify_device_token(device_token):
        await websocket.close(code=1008, reason="Unauthorized: Invalid device token")
        return

    # 生成 session_id
    if not session_id:
        session_id = f"rt_{device_id or 'device'}_{int(datetime.utcnow().timestamp() * 1000)}"

    # 接受连接
    await websocket.accept()

    # 创建 ASR 客户端
    asr_client = TencentRealtimeASR()

    # 会话状态
    session_state = {
        "session_id": session_id,
        "device_id": device_id,
        "start_time": datetime.utcnow(),
        "utterances": [],
        "harmful_count": 0,
        "total_text": "",
        "asr_connected": False,
    }

    active_sessions[session_id] = session_state

    try:
        # 连接到腾讯云 ASR
        try:
            await asr_client.connect(voice_id=session_id)
            session_state["asr_connected"] = True

            # 发送连接成功消息
            await websocket.send_json({
                "type": "status",
                "message": "实时识别已启动",
                "session_id": session_id,
                "timestamp": datetime.utcnow().timestamp()
            })

            logger.info(f"[Realtime] Session {session_id} started, ASR connected")

        except Exception as e:
            logger.error(f"[Realtime] Failed to connect to ASR: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"ASR连接失败: {str(e)}"
            })
            await websocket.close(code=1011, reason="ASR connection failed")
            return

        # 创建两个并发任务：
        # 1. 从设备接收音频并转发给 ASR
        # 2. 从 ASR 接收识别结果并检测有害内容

        async def receive_and_forward():
            """接收设备音频数据并转发给 ASR"""
            try:
                while True:
                    # 接收 PCM 音频数据
                    data = await websocket.receive_bytes()

                    # 转发给 ASR
                    await asr_client.send_audio(data)

            except WebSocketDisconnect:
                logger.info(f"[Realtime] Device disconnected from session {session_id}")
            except Exception as e:
                logger.error(f"[Realtime] Error receiving audio: {e}", exc_info=True)

        async def receive_asr_and_detect():
            """接收 ASR 结果并检测有害内容"""
            try:
                while asr_client.is_connected:
                    # 从 ASR 获取识别结果
                    asr_result = await asr_client.get_text()

                    if asr_result is None:
                        await asyncio.sleep(0.05)  # 没有结果，短暂等待
                        continue

                    text = asr_result["text"]
                    is_final = asr_result["is_final"]
                    start_time = asr_result["start"]
                    end_time = asr_result["end"]

                    # 发送 ASR 结果给设备
                    await websocket.send_json({
                        "type": "asr",
                        "text": text,
                        "is_final": is_final,
                        "start": start_time,
                        "end": end_time,
                        "timestamp": datetime.utcnow().timestamp()
                    })

                    logger.info(f"[Realtime] ASR result: '{text}' (final: {is_final})")

                    # 累积文本
                    session_state["total_text"] += text + " "

                    # 检测有害内容（使用高级检测）
                    is_harmful_flag, harmful_details = await is_harmful_advanced(
                        text,
                        use_llm=False  # 实时场景只用关键词，速度更快
                    )

                    if is_harmful_flag:
                        session_state["harmful_count"] += 1

                        # 立即发送警告给设备
                        alert_message = {
                            "type": "harmful_alert",
                            "text": text,
                            "keywords": harmful_details.get("keywords", []),
                            "severity": harmful_details.get("severity", 3),
                            "method": harmful_details.get("method", "keyword"),
                            "timestamp": datetime.utcnow().timestamp(),
                            "action": "warning"  # 可以根据严重度设置为 "block"
                        }

                        await websocket.send_json(alert_message)

                        logger.warning(
                            f"[Realtime] 🚨 Harmful content detected in session {session_id}: "
                            f"'{text}' (keywords: {harmful_details.get('keywords')})"
                        )

                    # 如果是最终结果，保存到数据库
                    if is_final:
                        utterance_data = {
                            "session_id": session_id,
                            "text": text,
                            "start_time": start_time,
                            "end_time": end_time,
                            "harmful_flag": is_harmful_flag,
                            "harmful_keywords": ",".join(harmful_details.get("keywords", [])) if is_harmful_flag else None,
                        }
                        session_state["utterances"].append(utterance_data)

                        # 异步保存到数据库
                        asyncio.create_task(_save_utterance_to_db(utterance_data))

            except Exception as e:
                logger.error(f"[Realtime] Error processing ASR results: {e}", exc_info=True)

        # 并发运行两个任务
        await asyncio.gather(
            receive_and_forward(),
            receive_asr_and_detect(),
            return_exceptions=True
        )

    except WebSocketDisconnect:
        logger.info(f"[Realtime] Session {session_id} disconnected")

    except Exception as e:
        logger.error(f"[Realtime] Session {session_id} error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass

    finally:
        # 清理：断开 ASR 连接
        if asr_client.is_connected:
            await asr_client.disconnect()

        # 保存会话到数据库
        await _save_session_to_db(session_state)

        # 移除活跃会话
        if session_id in active_sessions:
            del active_sessions[session_id]

        logger.info(
            f"[Realtime] Session {session_id} ended. "
            f"Utterances: {len(session_state['utterances'])}, "
            f"Harmful: {session_state['harmful_count']}"
        )

        try:
            await websocket.close()
        except:
            pass


async def _save_utterance_to_db(utterance_data: Dict[str, Any]):
    """异步保存 utterance 到数据库"""
    try:
        with DBSession(engine) as db:
            utterance = UtteranceModel(**utterance_data)
            db.add(utterance)
            db.commit()
            logger.debug(f"Saved utterance to DB: session_id={utterance_data['session_id']}")
    except Exception as e:
        logger.error(f"Failed to save utterance to DB: {e}", exc_info=True)


async def _save_session_to_db(session_state: Dict[str, Any]):
    """保存会话到数据库"""
    try:
        session_id = session_state["session_id"]
        device_id = session_state.get("device_id", "unknown")
        start_time = session_state["start_time"]
        end_time = datetime.utcnow()
        harmful_count = session_state["harmful_count"]

        with DBSession(engine) as db:
            # 检查会话是否已存在
            session = db.get(SessionModel, session_id)

            if session is None:
                # 创建新会话
                session = SessionModel(
                    session_id=session_id,
                    device_id=device_id,
                    start_time=start_time,
                    end_time=end_time,
                    harmful_count=harmful_count,
                    audio_path=None,  # 实时流不保存音频文件
                )
                db.add(session)
            else:
                # 更新现有会话
                session.end_time = end_time
                session.harmful_count = harmful_count

            db.commit()
            logger.info(f"Saved session to DB: {session_id}")

    except Exception as e:
        logger.error(f"Failed to save session to DB: {e}", exc_info=True)


@router.get("/active")
async def get_active_sessions():
    """获取当前活跃的实时会话列表"""
    return {
        "active_count": len(active_sessions),
        "sessions": [
            {
                "session_id": state["session_id"],
                "device_id": state["device_id"],
                "start_time": state["start_time"].isoformat(),
                "utterances_count": len(state["utterances"]),
                "harmful_count": state["harmful_count"],
                "asr_connected": state["asr_connected"],
            }
            for state in active_sessions.values()
        ]
    }


# ── /subscribe endpoint: web client subscribes to realtime ASR for a device ──

async def _broadcast_to_asr_subscribers(device_id: str, msg: dict) -> None:
    """Send a JSON message to all ASR subscribers for a device."""
    bridge = _asr_bridges.get(device_id)
    if not bridge:
        return
    dead = []
    for ws in bridge["subscribers"]:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        bridge["subscribers"].discard(ws)


async def _asr_reader_loop(device_id: str) -> None:
    """Background task: read ASR results from Tencent and broadcast to subscribers."""
    bridge = _asr_bridges.get(device_id)
    if not bridge:
        return
    asr_client = bridge["asr_client"]
    try:
        while asr_client.is_connected and device_id in _asr_bridges:
            result = await asr_client.get_text()
            if result is None:
                await asyncio.sleep(0.05)
                continue

            text = result["text"]
            is_final = result["is_final"]

            # ASR result message
            now = datetime.utcnow()
            msg = {
                "type": "asr",
                "text": text,
                "is_final": is_final,
                "start": result.get("start", 0),
                "end": result.get("end", 0),
                "device_id": device_id,
                "session_id": bridge["session_id"],
                "speaker": None,  # 实时无法分离，离线 ASR 再写入
                "ts_ms": int(now.timestamp() * 1000),
                "timestamp": now.timestamp(),
            }
            await _broadcast_to_asr_subscribers(device_id, msg)
            logger.info(f"[ASR-Bridge] {device_id}: '{text}' (final={is_final})")

            # Harmful detection (keyword-only for speed)
            is_harmful_flag, harmful_details = await is_harmful_advanced(text, use_llm=False)
            if is_harmful_flag:
                bridge["harmful_count"] += 1
                alert = {
                    "type": "harmful_alert",
                    "text": text,
                    "severity": harmful_details.get("severity", 3),
                    "category": harmful_details.get("category", ""),
                    "keywords": harmful_details.get("keywords", []),
                    "explanation": f"检测到有害关键词: {', '.join(harmful_details.get('keywords', []))}",
                    "device_id": device_id,
                    "session_id": bridge["session_id"],
                    "timestamp": datetime.utcnow().timestamp(),
                }
                await _broadcast_to_asr_subscribers(device_id, alert)

            # Save final utterances to DB
            if is_final and text.strip():
                utt = {
                    "session_id": bridge["session_id"],
                    "text": text,
                    "start_time": result.get("start", 0),
                    "end_time": result.get("end", 0),
                    "harmful_flag": is_harmful_flag,
                    "harmful_keywords": ",".join(harmful_details.get("keywords", [])) if is_harmful_flag else None,
                }
                bridge["utterances"].append(utt)
                asyncio.create_task(_save_utterance_to_db(utt))

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"[ASR-Bridge] Reader loop error for {device_id}: {e}", exc_info=True)


async def _start_asr_bridge(device_id: str) -> dict:
    """Create a TencentRealtimeASR session and start the reader task."""
    session_id = f"rt_{device_id}_{int(datetime.utcnow().timestamp() * 1000)}"
    asr_client = TencentRealtimeASR()
    await asr_client.connect(voice_id=session_id)

    bridge = {
        "asr_client": asr_client,
        "subscribers": set(),
        "session_id": session_id,
        "device_id": device_id,
        "start_time": datetime.utcnow(),
        "utterances": [],
        "harmful_count": 0,
        "reader_task": None,
        "sender_task": None,
        "audio_queue": asyncio.Queue(maxsize=ASR_AUDIO_QUEUE_MAX),
        "audio_ingest_bytes": 0,
        "audio_sent_bytes": 0,
        "audio_sent_chunks": 0,
        "audio_drop_chunks": 0,
        "audio_drop_bytes": 0,
    }
    _asr_bridges[device_id] = bridge
    bridge["reader_task"] = asyncio.create_task(_asr_reader_loop(device_id))
    bridge["sender_task"] = asyncio.create_task(_asr_sender_loop(device_id))
    logger.info(f"[ASR-Bridge] Started for device {device_id}, session {session_id}")
    return bridge


async def _stop_asr_bridge(device_id: str) -> None:
    """Tear down ASR bridge: cancel reader, disconnect ASR, save session."""
    bridge = _asr_bridges.pop(device_id, None)
    if not bridge:
        return
    logger.info(f"[ASR-Bridge] Stopping for device {device_id}, session {bridge['session_id']}")

    if bridge.get("reader_task"):
        bridge["reader_task"].cancel()
    if bridge.get("sender_task"):
        bridge["sender_task"].cancel()

    asr_client = bridge.get("asr_client")
    if asr_client and asr_client.is_connected:
        try:
            await asr_client.disconnect()
        except Exception:
            pass

    # Save session to DB
    await _save_session_to_db({
        "session_id": bridge["session_id"],
        "device_id": device_id,
        "start_time": bridge["start_time"],
        "utterances": bridge["utterances"],
        "harmful_count": bridge["harmful_count"],
    })
    logger.info(
        "[ASR-Bridge] %s stats: ingest=%dB sent=%dB sent_chunks=%d dropped_chunks=%d dropped_bytes=%d",
        device_id,
        bridge.get("audio_ingest_bytes", 0),
        bridge.get("audio_sent_bytes", 0),
        bridge.get("audio_sent_chunks", 0),
        bridge.get("audio_drop_chunks", 0),
        bridge.get("audio_drop_bytes", 0),
    )


@router.websocket("/subscribe")
async def ws_realtime_subscribe(
    websocket: WebSocket,
    device_id: str = Query(...),
):
    """
    Web 端订阅某设备的实时 ASR 字幕。

    - 第一个订阅者到来时自动创建 TencentRealtimeASR 会话
    - 音频由 /ws/ingest/pcm?raw=1 的 forward_audio_to_asr() 注入
    - 最后一个订阅者离开时自动拆除 ASR 会话

    推送消息格式:
      {type:"asr", text, is_final, start, end, device_id, session_id, timestamp}
      {type:"harmful_alert", text, severity, category, keywords, explanation, ...}
      {type:"status", message, session_id}
    """
    await websocket.accept()
    logger.info(f"[ASR-Subscribe] Web client subscribing to device {device_id}")

    # Create bridge if first subscriber
    bridge = _asr_bridges.get(device_id)
    if not bridge:
        try:
            bridge = await _start_asr_bridge(device_id)
        except Exception as e:
            logger.error(f"[ASR-Subscribe] Failed to start ASR for {device_id}: {e}")
            await websocket.send_json({
                "type": "error",
                "message": f"ASR连接失败: {str(e)}"
            })
            try:
                await websocket.close(code=1011, reason="ASR connection failed")
            except Exception:
                pass
            return

    bridge["subscribers"].add(websocket)
    await websocket.send_json({
        "type": "status",
        "message": "实时字幕已连接",
        "session_id": bridge["session_id"],
        "device_id": device_id,
        "timestamp": datetime.utcnow().timestamp(),
    })

    try:
        # Keep alive — wait for client disconnect
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info(f"[ASR-Subscribe] Web client disconnected from device {device_id}")
    except Exception:
        pass
    finally:
        if device_id in _asr_bridges:
            _asr_bridges[device_id]["subscribers"].discard(websocket)
            # Last subscriber → tear down bridge
            if not _asr_bridges[device_id]["subscribers"]:
                await _stop_asr_bridge(device_id)

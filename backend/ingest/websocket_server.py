from fastapi import WebSocket, WebSocketDisconnect
import json
import logging
from ingest.session_manager import SessionManager
from ingest.audio_writer import AudioWriter
from realtime.tencent_asr import TencentRealtimeASR
from realtime.llm_harmful_detector import LLMHarmfulDetector
from realtime.harmful_rules import is_harmful
from config import settings
from models import Utterance, engine
from sqlmodel import Session as DBSession

logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Handles WebSocket connections from devices for real-time ASR + harmful detection"""

    def __init__(self):
        self.session_manager = SessionManager()

    async def handle_connection(self, websocket: WebSocket):
        """
        Handle WebSocket connection lifecycle

        Protocol:
        1. Client sends: {"type": "start_session", "device_id": "esp32"}
        2. Server responds: {"type": "session_started", "session_id": "..."}
        3. Client sends binary PCM chunks (16kHz, 16-bit, mono, s16le)
        4. Server sends ASR results: {"type": "asr_result", "text": "...", "is_final": true/false}
        5. Server sends harmful alerts: {"type": "alert", "severity": 3-5, "text": "...", "explanation": "..."}
        6. Client sends: {"type": "end_session"}
        7. Server responds: {"type": "session_ended", "session_id": "..."}

        Args:
            websocket: WebSocket connection
        """
        await websocket.accept()
        logger.info("WebSocket connection accepted")

        # Initialize components
        audio_writer = AudioWriter(settings.audio_storage_path)
        asr_client = TencentRealtimeASR()  # 腾讯云实时 ASR
        llm_detector = LLMHarmfulDetector()  # LLM 有害语检测

        session_id = None
        device_id = None
        harmful_count = 0
        utterances_buffer = []  # Buffer for storing utterances during session

        try:
            while True:
                # Receive data from device
                data = await websocket.receive()

                # Handle text messages (control commands)
                if "text" in data:
                    message = json.loads(data["text"])
                    msg_type = message.get("type")

                    if msg_type == "start_session":
                        device_id = message.get("device_id", "unknown")
                        session_id = self.session_manager.create_session(device_id)
                        await audio_writer.start_recording(session_id)

                        # 连接腾讯云 ASR
                        await asr_client.connect(voice_id=session_id)

                        # Send confirmation
                        await websocket.send_json({
                            "type": "session_started",
                            "session_id": session_id
                        })
                        logger.info(f"Session started: {session_id}, device: {device_id}")

                    elif msg_type == "end_session":
                        if session_id:
                            # Disconnect ASR first to flush any remaining results
                            await asr_client.disconnect()

                            # Stop recording
                            audio_path = await audio_writer.stop_recording()

                            # Save all buffered utterances to database
                            if utterances_buffer:
                                with DBSession(engine) as db:
                                    for utterance_data in utterances_buffer:
                                        utterance = Utterance(
                                            session_id=session_id,
                                            start=utterance_data["start"],
                                            end=utterance_data["end"],
                                            speaker="A",  # Default speaker for real-time (no diarization)
                                            text=utterance_data["text"],
                                            harmful_flag=utterance_data.get("harmful_flag", False)
                                        )
                                        db.add(utterance)
                                    db.commit()
                                    logger.info(f"Saved {len(utterances_buffer)} utterances to DB for session {session_id}")

                            # End session in DB
                            self.session_manager.end_session(
                                session_id, audio_path, harmful_count
                            )

                            # Send confirmation
                            await websocket.send_json({
                                "type": "session_ended",
                                "session_id": session_id,
                                "harmful_count": harmful_count,
                                "utterance_count": len(utterances_buffer)
                            })
                            logger.info(f"Session ended: {session_id}, harmful: {harmful_count}, utterances: {len(utterances_buffer)}")

                            # Reset state
                            session_id = None
                            device_id = None
                            harmful_count = 0
                            utterances_buffer = []

                # Handle binary data (audio frames)
                elif "bytes" in data:
                    if not session_id:
                        logger.warning("Received audio data before start_session")
                        continue

                    audio_data = data["bytes"]

                    # Write audio to file
                    await audio_writer.write_audio(audio_data)

                    # Send to realtime ASR
                    await asr_client.send_audio(audio_data)

                    # Check for ASR results (non-blocking)
                    asr_result = await asr_client.get_text()
                    if asr_result:
                        text = asr_result.get("text", "")
                        is_final = asr_result.get("is_final", False)
                        start_time = asr_result.get("start", 0.0)
                        end_time = asr_result.get("end", 0.0)

                        logger.info(f"ASR result: {text} (final: {is_final})")

                        # Send ASR result to client (both partial and final)
                        await websocket.send_json({
                            "type": "asr_result",
                            "text": text,
                            "is_final": is_final,
                            "start": start_time,
                            "end": end_time
                        })

                        # 只对最终结果进行有害语检测（避免频繁调用 LLM）
                        if is_final and text.strip():
                            # 先用关键词快速检测
                            keyword_harmful = is_harmful(text)

                            # 使用 LLM 进行更精确的检测
                            llm_result = await llm_detector.detect(text)
                            llm_harmful = llm_result.get("is_harmful", False)
                            severity = llm_result.get("severity", 0)

                            # Store utterance in buffer
                            harmful_flag = keyword_harmful or (llm_harmful and severity >= 3)
                            utterances_buffer.append({
                                "start": start_time,
                                "end": end_time,
                                "text": text,
                                "harmful_flag": harmful_flag
                            })

                            # 只有严重度 >= 3 时才发送警告（避免过度敏感）
                            if harmful_flag and severity >= 3:
                                harmful_count += 1

                                # Send alert to device
                                await websocket.send_json({
                                    "type": "alert",
                                    "severity": severity,
                                    "text": text,
                                    "category": llm_result.get("category", "有害语言"),
                                    "explanation": llm_result.get("explanation", "")
                                })
                                logger.warning(
                                    f"Harmful content detected: '{text}' "
                                    f"(severity: {severity}, category: {llm_result.get('category')})"
                                )

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
            # Clean up if session is still active
            if session_id:
                await asr_client.disconnect()
                audio_path = await audio_writer.stop_recording()

                # Save buffered utterances
                if utterances_buffer:
                    try:
                        with DBSession(engine) as db:
                            for utterance_data in utterances_buffer:
                                utterance = Utterance(
                                    session_id=session_id,
                                    start=utterance_data["start"],
                                    end=utterance_data["end"],
                                    speaker="A",
                                    text=utterance_data["text"],
                                    harmful_flag=utterance_data.get("harmful_flag", False)
                                )
                                db.add(utterance)
                            db.commit()
                    except Exception as e:
                        logger.error(f"Failed to save utterances on disconnect: {e}")

                if audio_path:
                    self.session_manager.end_session(
                        session_id, audio_path, harmful_count
                    )

        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=True)
            # Try to clean up
            try:
                if session_id:
                    await asr_client.disconnect()
            except:
                pass

        finally:
            # Ensure ASR disconnection
            try:
                if asr_client.is_connected:
                    await asr_client.disconnect()
            except:
                pass

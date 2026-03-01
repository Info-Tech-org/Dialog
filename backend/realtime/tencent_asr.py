"""
Tencent Cloud Realtime ASR Integration
腾讯云实时语音识别集成
"""

import asyncio
import json
import hmac
import hashlib
import base64
import time
from typing import Optional, Dict, Any
from urllib.parse import quote
import websockets
import logging

from config import settings

logger = logging.getLogger(__name__)


class TencentRealtimeASR:
    """
    Tencent Cloud Realtime ASR Client
    使用腾讯云实时语音识别 WebSocket API

    文档: https://cloud.tencent.com/document/product/1093/48982
    """

    def __init__(self):
        self.appid = settings.tencent_appid
        self.secret_id = settings.tencent_secret_id
        self.secret_key = settings.tencent_secret_key
        self.engine_model_type = "16k_zh"  # 16k 中文通用模型
        self.websocket = None
        self.voice_id = None
        self.text_queue = asyncio.Queue()
        self.is_connected = False

    @staticmethod
    def _mask(value: str, keep: int = 4) -> str:
        if not value:
            return ""
        if len(value) <= keep * 2:
            return "*" * len(value)
        return f"{value[:keep]}***{value[-keep:]}"

    def _generate_sign_params(self, voice_id: str) -> dict:
        """
        生成鉴权参数（含签名）

        腾讯云签名要求：所有参数（除 signature）按字母序拼接为签名原文字符串，
        使用 SecretKey 做 HMAC-SHA1，然后 Base64 + URL encode。

        Returns:
            dict with all query parameters including signature
        """
        timestamp = int(time.time())
        expired = timestamp + 24 * 60 * 60  # 24小时过期
        nonce = timestamp  # 随机数，用时间戳即可

        # 所有需要签名的参数
        params = {
            "engine_model_type": self.engine_model_type,
            "expired": str(expired),
            "nonce": str(nonce),
            "secretid": self.secret_id,
            "timestamp": str(timestamp),
            "voice_format": "1",
            "voice_id": voice_id,
        }

        # 按字母序拼接为签名原文字符串
        sorted_params = "&".join(f"{k}={params[k]}" for k in sorted(params))
        sign_str = f"asr.cloud.tencent.com/asr/v2/{self.appid}?{sorted_params}"

        # HMAC-SHA1 + Base64
        sig_bytes = hmac.new(
            self.secret_key.encode('utf-8'),
            sign_str.encode('utf-8'),
            hashlib.sha1
        ).digest()
        sig_b64 = base64.b64encode(sig_bytes).decode('utf-8')

        # URL encode (腾讯要求对 +, = 等特殊字符编码)
        params["signature"] = quote(sig_b64)
        return params

    async def connect(self, voice_id: str = None):
        """
        连接到腾讯云实时语音识别服务

        连接成功后会等待腾讯首条响应：
        - code == 0 → 鉴权通过，可以开始发送音频
        - code != 0 → 鉴权/配额失败，立即抛异常

        Args:
            voice_id: 语音识别请求唯一标识，如果不提供则自动生成
        """
        if voice_id is None:
            voice_id = f"session_{int(time.time() * 1000)}"

        self.voice_id = voice_id
        params = self._generate_sign_params(voice_id)

        # 构建 WebSocket URL
        query = "&".join(f"{k}={v}" for k, v in params.items())
        ws_url = f"wss://asr.cloud.tencent.com/asr/v2/{self.appid}?{query}"

        try:
            logger.info(
                "Connecting Tencent ASR: appid=%s voice_id=%s engine=%s format=s16le secretid=%s",
                self.appid,
                voice_id,
                self.engine_model_type,
                self._mask(self.secret_id),
            )
            self.websocket = await websockets.connect(ws_url)
            logger.info(f"Tencent ASR websocket opened, voice_id: {voice_id}")

            # 等待腾讯首条响应（鉴权结果），5 秒超时
            first_msg = await asyncio.wait_for(self.websocket.recv(), timeout=5)
            first_data = json.loads(first_msg)
            first_code = first_data.get("code")
            logger.info(
                "Tencent ASR first response: voice_id=%s code=%s message=%s",
                voice_id,
                first_code,
                first_data.get("message", ""),
            )

            if first_code != 0:
                err_msg = first_data.get("message", "unknown error")
                logger.error(f"Tencent ASR auth failed: code={first_code}, message={err_msg}")
                try:
                    await self.websocket.close()
                except Exception:
                    pass
                raise RuntimeError(f"Tencent ASR error code={first_code}: {err_msg}")

            # 鉴权通过
            self.is_connected = True
            logger.info(f"Tencent ASR auth OK, voice_id: {voice_id}")

            # 启动后台消息接收任务
            asyncio.create_task(self._receive_messages())

        except (asyncio.TimeoutError, RuntimeError) as e:
            logger.error(f"Failed to connect to Tencent ASR: {e}")
            self.is_connected = False
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Tencent ASR: {e}")
            self.is_connected = False
            raise

    async def _receive_messages(self):
        """接收来自腾讯云的识别结果"""
        try:
            async for message in self.websocket:
                data = json.loads(message)

                # 处理不同类型的消息
                code = data.get("code")

                if code == 0:
                    # 识别成功
                    result = data.get("result", {})
                    voice_text_str = result.get("voice_text_str", "")
                    slice_type = result.get("slice_type", 0)

                    if voice_text_str:
                        # slice_type: 0-一段话开始，1-一段话结束，2-中间结果
                        await self.text_queue.put({
                            "text": voice_text_str,
                            "is_final": slice_type == 1,
                            "start": result.get("start_time", 0) / 1000,  # 转为秒
                            "end": result.get("end_time", 0) / 1000,
                        })
                        logger.debug(f"ASR result: {voice_text_str} (final: {slice_type == 1})")

                elif code == 4008:
                    # 语音识别结束
                    logger.info("ASR session ended normally")
                    break

                else:
                    # 错误
                    logger.error(f"ASR error: code={code}, message={data.get('message')}")

        except websockets.exceptions.ConnectionClosed as e:
            logger.info("ASR WebSocket closed: code=%s reason=%s", getattr(e, "code", None), getattr(e, "reason", ""))
        except Exception as e:
            logger.error(f"Error receiving ASR messages: {e}", exc_info=True)
        finally:
            self.is_connected = False

    async def send_audio(self, data: bytes):
        """
        发送音频数据到腾讯云

        Args:
            data: PCM 格式音频数据 (16kHz, 16bit, mono)
        """
        if not self.is_connected or self.websocket is None:
            logger.warning("ASR not connected, cannot send audio")
            return

        try:
            await self.websocket.send(data)
        except Exception as e:
            logger.error(f"Failed to send audio to ASR: {e}")
            self.is_connected = False

    async def get_text(self) -> Optional[Dict[str, Any]]:
        """
        获取识别的文本结果

        Returns:
            dict with keys: text (str), is_final (bool), start (float), end (float)
            or None if no text available
        """
        try:
            return await asyncio.wait_for(self.text_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    async def disconnect(self):
        """断开连接"""
        if self.websocket and self.is_connected:
            try:
                # 发送结束标识
                await self.websocket.send(json.dumps({"type": "end"}))
                await self.websocket.close()
                logger.info(
                    "Disconnected from Tencent ASR: voice_id=%s close_code=%s",
                    self.voice_id,
                    getattr(self.websocket, "close_code", None),
                )
            except Exception as e:
                logger.error(f"Error disconnecting from ASR: {e}")
            finally:
                self.is_connected = False

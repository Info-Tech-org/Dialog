"""
Legacy placeholder for realtime ASR. Deprecated.

Production code uses TencentRealtimeASR from realtime.tencent_asr.
This module is kept for backward compatibility only.
"""
import asyncio
from typing import Optional, Dict, Any
import logging
import warnings

logger = logging.getLogger(__name__)


class RealtimeASR:
    """
    Realtime ASR client hook (DEPRECATED).

    Use realtime.tencent_asr.TencentRealtimeASR for production.
    This class is a placeholder and is not used by the current ingest pipeline.
    """

    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        warnings.warn(
            "RealtimeASR is deprecated; use TencentRealtimeASR from realtime.tencent_asr",
            DeprecationWarning,
            stacklevel=2,
        )

        self.api_key = api_key
        self.endpoint = endpoint
        self.is_connected = False
        self.text_queue = asyncio.Queue()

    async def connect(self):
        """Connect to ASR service (deprecated placeholder)."""
        logger.info("Connecting to realtime ASR service...")
        self.is_connected = True

    async def disconnect(self):
        """Disconnect from ASR service"""
        logger.info("Disconnecting from realtime ASR service...")
        self.is_connected = False

    async def send_audio(self, data: bytes):
        """
        Send audio frame to ASR service

        Args:
            data: Audio binary data (PCM format expected)
        """
        if not self.is_connected:
            logger.warning("ASR service not connected")
            return
        # Deprecated: use TencentRealtimeASR for actual sending.

    async def get_text(self) -> Optional[Dict[str, Any]]:
        """
        Get recognized text with timestamp

        Returns:
            dict with keys: start (float), end (float), text (str)
            or None if no text available
        """
        try:
            return await asyncio.wait_for(self.text_queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None

    async def _send_to_tencent_asr(self, data: bytes):
        """
        Example placeholder for Tencent Cloud ASR integration

        Implementation would use Tencent Cloud SDK:
        1. Initialize WebSocket connection to Tencent ASR
        2. Send audio frames
        3. Receive partial/final results
        4. Put results into text_queue
        """
        pass

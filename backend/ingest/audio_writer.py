import aiofiles
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AudioWriter:
    """Handles writing audio data to WAV files with proper header management"""

    def __init__(self, storage_path: str):
        self.storage_path = storage_path
        self.file_handle = None
        self.current_file_path = None
        self.bytes_written = 0  # Track PCM data size

    async def start_recording(self, session_id: str) -> str:
        """
        Start recording audio to a new file

        Args:
            session_id: Session identifier

        Returns:
            Path to the audio file
        """
        os.makedirs(self.storage_path, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{session_id}_{timestamp}.wav"
        self.current_file_path = os.path.join(self.storage_path, filename)

        # Open file in binary write mode
        self.file_handle = await aiofiles.open(self.current_file_path, "wb")

        # Write WAV header placeholder (will be updated when recording stops)
        await self._write_wav_header(0)
        self.bytes_written = 0

        logger.info(f"Started recording to {self.current_file_path}")
        return self.current_file_path

    async def write_audio(self, data: bytes):
        """
        Write audio data to current file

        Args:
            data: Audio binary data (PCM format)
        """
        if self.file_handle is None:
            logger.warning("No active recording session")
            return

        await self.file_handle.write(data)
        self.bytes_written += len(data)

    async def stop_recording(self) -> str:
        """
        Stop recording and close file, updating WAV header with correct size

        Returns:
            Path to the recorded audio file
        """
        if self.file_handle is None:
            logger.warning("No active recording session to stop")
            return None

        await self.file_handle.close()
        file_path = self.current_file_path

        # Update WAV header with correct file size
        if file_path and os.path.exists(file_path):
            try:
                # Reopen file in r+b mode to update header
                async with aiofiles.open(file_path, "r+b") as f:
                    # Update RIFF chunk size at offset 4 (file_size - 8)
                    await f.seek(4)
                    await f.write((self.bytes_written + 36).to_bytes(4, "little"))

                    # Update data chunk size at offset 40
                    await f.seek(40)
                    await f.write(self.bytes_written.to_bytes(4, "little"))

                logger.info(f"Updated WAV header: {self.bytes_written} bytes of PCM data")
            except Exception as e:
                logger.error(f"Failed to update WAV header: {e}")

        logger.info(f"Stopped recording, saved to {file_path} ({self.bytes_written} bytes)")

        self.file_handle = None
        self.current_file_path = None
        self.bytes_written = 0

        return file_path

    async def _write_wav_header(self, data_size: int):
        """
        Write WAV file header

        Args:
            data_size: Size of audio data in bytes
        """
        # WAV header for 16kHz, 16-bit, mono PCM
        sample_rate = 16000
        bits_per_sample = 16
        channels = 1

        # RIFF header
        await self.file_handle.write(b"RIFF")
        await self.file_handle.write((data_size + 36).to_bytes(4, "little"))
        await self.file_handle.write(b"WAVE")

        # fmt subchunk
        await self.file_handle.write(b"fmt ")
        await self.file_handle.write((16).to_bytes(4, "little"))  # Subchunk size
        await self.file_handle.write((1).to_bytes(2, "little"))  # Audio format (PCM)
        await self.file_handle.write(channels.to_bytes(2, "little"))
        await self.file_handle.write(sample_rate.to_bytes(4, "little"))
        byte_rate = sample_rate * channels * bits_per_sample // 8
        await self.file_handle.write(byte_rate.to_bytes(4, "little"))
        block_align = channels * bits_per_sample // 8
        await self.file_handle.write(block_align.to_bytes(2, "little"))
        await self.file_handle.write(bits_per_sample.to_bytes(2, "little"))

        # data subchunk
        await self.file_handle.write(b"data")
        await self.file_handle.write(data_size.to_bytes(4, "little"))

#!/usr/bin/env python3
"""
WebSocket Real-time ASR + Harmful Detection Test Client

This script tests the complete real-time ASR + harmful detection pipeline:
1. Connect to WebSocket /ws
2. Send start_session command
3. Stream PCM audio chunks
4. Receive asr_result messages (partial and final)
5. Receive alert messages for harmful content
6. Send end_session command
7. Verify session stored in DB with utterances

Usage:
    python test_websocket_realtime.py --url ws://localhost:8000/ws --duration 10.0
    python test_websocket_realtime.py --url ws://47.236.106.225:9000/ws --audio test.wav
"""

import asyncio
import websockets
import json
import argparse
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class WebSocketTestClient:
    """Test client for real-time ASR + harmful detection"""

    def __init__(self, url: str, device_id: str = "test_client"):
        self.url = url
        self.device_id = device_id
        self.session_id = None
        self.asr_results = []
        self.alerts = []
        self.is_session_started = False

    async def connect_and_test(self, audio_source: str = "generated", duration: float = 5.0):
        """
        Connect to WebSocket and run test

        Args:
            audio_source: "generated" or path to WAV file
            duration: Duration in seconds (for generated audio)
        """
        async with websockets.connect(self.url) as websocket:
            logger.info(f"Connected to {self.url}")

            # Start session
            await self.start_session(websocket)

            # Send audio
            if audio_source == "generated":
                await self.send_generated_audio(websocket, duration)
            else:
                await self.send_audio_file(websocket, audio_source)

            # End session
            await self.end_session(websocket)

            # Print summary
            self.print_summary()

    async def start_session(self, websocket):
        """Send start_session command"""
        logger.info(f"Starting session for device: {self.device_id}")

        await websocket.send(json.dumps({
            "type": "start_session",
            "device_id": self.device_id
        }))

        # Wait for confirmation
        response = await websocket.recv()
        data = json.loads(response)

        if data.get("type") == "session_started":
            self.session_id = data.get("session_id")
            self.is_session_started = True
            logger.info(f"✅ Session started: {self.session_id}")
        else:
            logger.error(f"❌ Failed to start session: {data}")
            raise Exception("Failed to start session")

    async def send_generated_audio(self, websocket, duration: float):
        """
        Generate and send PCM audio with speech simulation

        Args:
            websocket: WebSocket connection
            duration: Duration in seconds
        """
        sample_rate = 16000
        chunk_size = 3200  # 200ms chunks (16000 * 0.2 = 3200 samples)
        total_samples = int(sample_rate * duration)
        num_chunks = total_samples // chunk_size

        logger.info(f"Generating {duration}s of audio ({num_chunks} chunks)")

        # Create background task to receive messages
        receive_task = asyncio.create_task(self.receive_messages(websocket))

        for i in range(num_chunks):
            # Generate speech-like audio (mix of frequencies to simulate voice)
            t = np.linspace(i * chunk_size / sample_rate,
                           (i + 1) * chunk_size / sample_rate,
                           chunk_size,
                           endpoint=False)

            # Simulate speech with varying frequencies (fundamental + harmonics)
            frequency = 200 + 50 * np.sin(2 * np.pi * 2 * t[0])  # Varying pitch
            audio = np.sin(2 * np.pi * frequency * t)  # Fundamental
            audio += 0.5 * np.sin(2 * np.pi * frequency * 2 * t)  # 2nd harmonic
            audio += 0.3 * np.sin(2 * np.pi * frequency * 3 * t)  # 3rd harmonic

            # Add envelope to simulate speech segments
            envelope = np.exp(-((t - t[0] - 0.1) ** 2) / 0.01)  # Gaussian envelope
            audio = audio * envelope * 0.3  # Reduce amplitude

            # Convert to int16 PCM
            pcm_data = (audio * 32767).astype(np.int16).tobytes()

            # Send chunk
            await websocket.send(pcm_data)

            # Log progress
            if (i + 1) % 10 == 0:
                logger.info(f"Sent {i + 1}/{num_chunks} chunks ({(i + 1) * chunk_size / sample_rate:.1f}s)")

            # Small delay to simulate real-time streaming
            await asyncio.sleep(0.05)  # 50ms

        logger.info("✅ Finished sending audio")

        # Wait a bit for final ASR results
        await asyncio.sleep(2.0)

        # Cancel receive task
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass

    async def send_audio_file(self, websocket, file_path: str):
        """
        Send audio from WAV file

        Args:
            websocket: WebSocket connection
            file_path: Path to WAV file (must be 16kHz, 16-bit, mono)
        """
        import wave

        logger.info(f"Loading audio from {file_path}")

        with wave.open(file_path, 'rb') as wf:
            # Verify format
            if wf.getnchannels() != 1:
                raise ValueError("Audio must be mono (1 channel)")
            if wf.getsampwidth() != 2:
                raise ValueError("Audio must be 16-bit")
            if wf.getframerate() != 16000:
                raise ValueError("Audio must be 16kHz")

            chunk_size = 3200  # 200ms chunks
            total_frames = wf.getnframes()
            num_chunks = (total_frames + chunk_size - 1) // chunk_size

            logger.info(f"Audio: {total_frames / wf.getframerate():.2f}s ({num_chunks} chunks)")

            # Create background task to receive messages
            receive_task = asyncio.create_task(self.receive_messages(websocket))

            for i in range(num_chunks):
                pcm_data = wf.readframes(chunk_size)
                if not pcm_data:
                    break

                await websocket.send(pcm_data)

                if (i + 1) % 10 == 0:
                    logger.info(f"Sent {i + 1}/{num_chunks} chunks")

                await asyncio.sleep(0.05)  # 50ms delay

            logger.info("✅ Finished sending audio file")

            # Wait for final ASR results
            await asyncio.sleep(2.0)

            # Cancel receive task
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass

    async def receive_messages(self, websocket):
        """Background task to receive and process messages"""
        try:
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "asr_result":
                    text = data.get("text", "")
                    is_final = data.get("is_final", False)
                    self.asr_results.append(data)

                    marker = "🔵" if is_final else "⚪"
                    logger.info(f"{marker} ASR: \"{text}\" (final={is_final})")

                elif msg_type == "alert":
                    severity = data.get("severity", 0)
                    text = data.get("text", "")
                    category = data.get("category", "")
                    explanation = data.get("explanation", "")
                    self.alerts.append(data)

                    logger.warning(f"🚨 ALERT (severity={severity}): \"{text}\"")
                    logger.warning(f"   Category: {category}")
                    logger.warning(f"   Explanation: {explanation}")

                else:
                    logger.debug(f"Received: {msg_type}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")

    async def end_session(self, websocket):
        """Send end_session command"""
        logger.info("Ending session...")

        await websocket.send(json.dumps({
            "type": "end_session"
        }))

        # Wait for confirmation
        response = await websocket.recv()
        data = json.loads(response)

        if data.get("type") == "session_ended":
            harmful_count = data.get("harmful_count", 0)
            utterance_count = data.get("utterance_count", 0)
            logger.info(f"✅ Session ended: {self.session_id}")
            logger.info(f"   Harmful count: {harmful_count}")
            logger.info(f"   Utterance count: {utterance_count}")
        else:
            logger.error(f"❌ Failed to end session: {data}")

    def print_summary(self):
        """Print test summary"""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Session ID: {self.session_id}")
        print(f"Device ID: {self.device_id}")
        print(f"\nASR Results: {len(self.asr_results)} total")

        final_results = [r for r in self.asr_results if r.get("is_final")]
        print(f"  - Final: {len(final_results)}")
        print(f"  - Partial: {len(self.asr_results) - len(final_results)}")

        if final_results:
            print("\nFinal Transcripts:")
            for i, result in enumerate(final_results, 1):
                print(f"  {i}. \"{result.get('text')}\"")

        print(f"\nAlerts: {len(self.alerts)}")
        if self.alerts:
            print("Harmful Content Detected:")
            for i, alert in enumerate(self.alerts, 1):
                print(f"  {i}. [{alert.get('severity')}/5] \"{alert.get('text')}\"")
                print(f"      Category: {alert.get('category')}")
                print(f"      Explanation: {alert.get('explanation')}")

        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Test WebSocket real-time ASR + harmful detection")
    parser.add_argument("--url", default="ws://localhost:8000/ws", help="WebSocket URL")
    parser.add_argument("--device-id", default="test_client", help="Device ID")
    parser.add_argument("--duration", type=float, default=5.0, help="Duration in seconds (for generated audio)")
    parser.add_argument("--audio", help="Path to WAV file (16kHz, 16-bit, mono)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    client = WebSocketTestClient(args.url, args.device_id)

    try:
        audio_source = args.audio if args.audio else "generated"
        asyncio.run(client.connect_and_test(audio_source, args.duration))
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()

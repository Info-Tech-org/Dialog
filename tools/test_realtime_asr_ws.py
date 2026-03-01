#!/usr/bin/env python3
"""
端到端测试：realtime ASR subscribe 链路
用法：
  python3 tools/test_realtime_asr_ws.py [--base ws://43.142.49.126:9000] [--token TOKEN]
  python3 tools/test_realtime_asr_ws.py --wav path/to/speech.wav --token TOKEN

测试流程:
  1. 连接 /ws/realtime/subscribe?device_id=test_device  (订阅字幕)
  2. 连接 /ws/ingest/pcm?raw=1&device_id=test_device    (模拟设备推流)
  3. 发送 PCM 音频 (WAV文件或生成的正弦波)
  4. 打印收到的 ASR 消息
  5. 关闭设备连接，触发 finalize
"""

import asyncio
import json
import struct
import math
import time
import wave
import argparse
import sys

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_SAMPLES = 320  # 20ms @ 16kHz
FRAME_BYTES = FRAME_SAMPLES * 2  # 640 bytes
DURATION_SEC = 3
DEVICE_ID = "test_device_asr"


def generate_pcm_frames(duration_sec: float, freq: float = 440.0):
    """Generate s16le PCM frames (sine wave) for testing."""
    total_samples = int(SAMPLE_RATE * duration_sec)
    frames = []
    buf = bytearray()
    for i in range(total_samples):
        val = int(16000 * math.sin(2 * math.pi * freq * i / SAMPLE_RATE))
        buf += struct.pack('<h', val)
        if len(buf) >= FRAME_BYTES:
            frames.append(bytes(buf[:FRAME_BYTES]))
            buf = buf[FRAME_BYTES:]
    if buf:
        # Pad last frame
        buf += b'\x00' * (FRAME_BYTES - len(buf))
        frames.append(bytes(buf))
    return frames


def load_wav_frames(wav_path: str):
    """Load a WAV file and split into 640-byte PCM frames (20ms @ 16kHz s16le mono)."""
    with wave.open(wav_path, 'rb') as wf:
        ch = wf.getnchannels()
        rate = wf.getframerate()
        sw = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    print(f"  WAV: {wav_path}")
    print(f"  Channels={ch}, Rate={rate}, SampleWidth={sw}, Duration={n_frames/rate:.1f}s")

    # Convert to 16kHz mono s16le if needed
    if sw != 2:
        print(f"  ERROR: Only 16-bit WAV supported (got {sw*8}-bit)")
        sys.exit(1)

    # If stereo, take left channel
    if ch == 2:
        mono = bytearray()
        for i in range(0, len(raw), 4):
            mono += raw[i:i+2]
        raw = bytes(mono)

    # Simple resample if rate != 16000 (nearest-neighbor)
    if rate != 16000:
        samples = struct.unpack(f'<{len(raw)//2}h', raw)
        ratio = rate / 16000
        new_len = int(len(samples) / ratio)
        resampled = []
        for i in range(new_len):
            idx = min(int(i * ratio), len(samples) - 1)
            resampled.append(samples[idx])
        raw = struct.pack(f'<{len(resampled)}h', *resampled)

    # Split into frames
    frames = []
    for i in range(0, len(raw), FRAME_BYTES):
        chunk = raw[i:i+FRAME_BYTES]
        if len(chunk) < FRAME_BYTES:
            chunk += b'\x00' * (FRAME_BYTES - len(chunk))
        frames.append(chunk)

    return frames, len(raw) / (SAMPLE_RATE * 2)


async def run_test(base_url: str, token: str = "", wav_path: str = ""):
    ws_base = base_url.replace('http://', 'ws://').replace('https://', 'wss://').rstrip('/')

    subscribe_url = f"{ws_base}/ws/realtime/subscribe?device_id={DEVICE_ID}"
    ingest_url = f"{ws_base}/ws/ingest/pcm?raw=1&device_id={DEVICE_ID}"
    if token:
        ingest_url += f"&device_token={token}"

    print(f"[TEST] Base URL: {ws_base}")
    print(f"[TEST] Subscribe: {subscribe_url}")
    print(f"[TEST] Ingest:    {ingest_url}")
    print()

    # Prepare audio frames
    if wav_path:
        print("[0/4] Loading WAV file...")
        frames, audio_dur = load_wav_frames(wav_path)
        audio_desc = f"{len(frames)} frames ({audio_dur:.1f}s from WAV)"
    else:
        frames = generate_pcm_frames(DURATION_SEC, freq=440)
        audio_dur = DURATION_SEC
        audio_desc = f"{len(frames)} frames ({DURATION_SEC}s of 440Hz sine)"

    asr_messages = []
    first_asr_time = None
    test_start = time.time()

    # ── Step 1: Connect subscriber ──
    print("[1/4] Connecting ASR subscriber...")
    try:
        sub_ws = await asyncio.wait_for(
            websockets.connect(subscribe_url, ping_interval=None),
            timeout=10
        )
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

    # Read status message
    try:
        status_msg = await asyncio.wait_for(sub_ws.recv(), timeout=5)
        status = json.loads(status_msg)
        print(f"  OK: {status.get('message', '')} (session={status.get('session_id', '?')})")
    except Exception as e:
        print(f"  WARN: no status message: {e}")

    # ── Step 2: Connect device (ingest) ──
    print("[2/4] Connecting device ingest (raw=1)...")
    try:
        dev_ws = await asyncio.wait_for(
            websockets.connect(ingest_url, ping_interval=None),
            timeout=10
        )
        print("  OK: device connected")
    except Exception as e:
        print(f"  FAIL: {e}")
        await sub_ws.close()
        return False

    # ── Step 3: Send PCM frames ──
    print(f"[3/4] Sending {audio_desc}...")
    send_start = time.time()

    async def send_audio():
        for i, frame in enumerate(frames):
            await dev_ws.send(frame)
            await asyncio.sleep(0.02)  # ~realtime 20ms/frame
        print(f"  Done sending ({time.time() - send_start:.1f}s)")
        await asyncio.sleep(2)  # let ASR process remaining audio
        await dev_ws.close()
        print("  Device disconnected (triggers finalize)")

    # ── Step 4: Listen for ASR results concurrently ──
    async def listen_asr():
        nonlocal first_asr_time
        try:
            while True:
                msg_raw = await asyncio.wait_for(sub_ws.recv(), timeout=15)
                msg = json.loads(msg_raw)
                elapsed = time.time() - test_start
                if msg.get("type") == "asr":
                    if first_asr_time is None:
                        first_asr_time = elapsed
                    tag = "FINAL" if msg.get("is_final") else "partial"
                    print(f"  [{elapsed:.1f}s] [{tag}] {msg.get('text', '')}")
                    asr_messages.append(msg)
                elif msg.get("type") == "harmful_alert":
                    print(f"  [{elapsed:.1f}s] [HARMFUL] severity={msg.get('severity')} text={msg.get('text', '')}")
                    asr_messages.append(msg)
                elif msg.get("type") == "error":
                    print(f"  [{elapsed:.1f}s] [ERROR] {msg.get('message', '')}")
                    break
                else:
                    print(f"  [{elapsed:.1f}s] [OTHER] {msg}")
        except asyncio.TimeoutError:
            print("  (timeout waiting for more ASR results)")
        except websockets.exceptions.ConnectionClosed:
            print("  (subscriber WS closed)")

    print("[4/4] Listening for ASR results...")
    await asyncio.gather(send_audio(), listen_asr())

    # Cleanup
    try:
        await sub_ws.close()
    except Exception:
        pass

    # ── Report ──
    print()
    print("=" * 50)
    print("TEST REPORT")
    print("=" * 50)
    total_elapsed = time.time() - test_start
    print(f"Total duration:       {total_elapsed:.1f}s")
    print(f"Audio source:         {'WAV: ' + wav_path if wav_path else '440Hz sine wave'}")
    print(f"ASR messages received: {len(asr_messages)}")
    if first_asr_time is not None:
        print(f"First ASR text at:    {first_asr_time:.1f}s  {'PASS (<10s)' if first_asr_time < 10 else 'FAIL (>=10s)'}")
    else:
        print(f"First ASR text at:    NONE  (FAIL - no ASR text received)")
    finals = [m for m in asr_messages if m.get("is_final")]
    print(f"Final sentences:      {len(finals)}")
    harmful = [m for m in asr_messages if m.get("type") == "harmful_alert"]
    print(f"Harmful alerts:       {len(harmful)}")

    success = first_asr_time is not None and first_asr_time < 10
    print(f"\nOverall: {'PASS' if success else 'FAIL'}")
    return success


def main():
    parser = argparse.ArgumentParser(description="Test realtime ASR WebSocket pipeline")
    parser.add_argument("--base", default="ws://43.142.49.126:9000", help="Base URL")
    parser.add_argument("--token", default="", help="device_ingest_token (if server requires it)")
    parser.add_argument("--wav", default="", help="Path to WAV file (16kHz mono preferred). If omitted, sends sine wave.")
    args = parser.parse_args()

    result = asyncio.run(run_test(args.base, args.token, args.wav))
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()

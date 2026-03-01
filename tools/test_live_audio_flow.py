#!/usr/bin/env python3
"""
综合测试：设备发音频 + device-listen 订阅 + 后端日志
- 并行：device ingest 发送 10s PCM + device-listen 订阅
- 用于定位「Web 听不到声音」根因
"""
import asyncio
import json
import time
import sys

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)

import wave

DEVICE_ID = "esp32c6_001"
TOKEN = "KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw"
BASE_WS = "ws://43.142.49.126:9000"
FRAME_BYTES = 640


def load_wav_frames(path):
    with wave.open(path, 'rb') as wf:
        raw = wf.readframes(wf.getnframes())
    frames = []
    for i in range(0, len(raw), FRAME_BYTES):
        chunk = raw[i:i+FRAME_BYTES]
        if len(chunk) < FRAME_BYTES:
            chunk += b'\x00' * (FRAME_BYTES - len(chunk))
        frames.append(chunk)
    return frames


async def run():
    ingest_url = f"{BASE_WS}/ws/ingest/pcm?raw=1&device_id={DEVICE_ID}&device_token={TOKEN}"
    listen_url = f"{BASE_WS}/ws/ingest/device-listen?device_id={DEVICE_ID}"
    wav_path = "test_10s.wav"

    try:
        frames = load_wav_frames(wav_path)
    except Exception as e:
        print(f"Load WAV failed: {e}")
        return

    print(f"[1] WAV: {wav_path}, {len(frames)} frames ({len(frames)*FRAME_BYTES} bytes)")
    print(f"[2] Ingest: {ingest_url[:70]}...")
    print(f"[3] Listen: {listen_url}")
    print()

    listen_frames = []
    listen_bytes = 0

    async def subscribe_listen():
        nonlocal listen_frames, listen_bytes
        async with websockets.connect(listen_url) as ws:
            t0 = time.time()
            while time.time() - t0 < 25:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    if isinstance(msg, bytes):
                        listen_frames.append(len(msg))
                        listen_bytes += len(msg)
                except asyncio.TimeoutError:
                    pass

    async def send_ingest():
        async with websockets.connect(ingest_url) as ws:
            t0 = time.time()
            for i, f in enumerate(frames):
                await ws.send(f)
                await asyncio.sleep(0.02)
            print(f"  Ingest sent {len(frames)} frames in {time.time()-t0:.1f}s")
            await asyncio.sleep(3)

    # 先连 listen，再连 ingest，确保 broadcast 有接收者
    listen_task = asyncio.create_task(subscribe_listen())
    await asyncio.sleep(1)  # listen 先建立
    send_task = asyncio.create_task(send_ingest())
    await asyncio.gather(listen_task, send_task)
    print(f"\n[Result] device-listen received: {len(listen_frames)} frames, {listen_bytes} bytes")
    if listen_frames:
        print(f"  Frame lengths (first 10): {listen_frames[:10]}")
        print(f"  Frame lengths (last 10): {listen_frames[-10:]}")
    else:
        print("  => 无音频帧！可能：设备未发、广播未到、listen 连接晚于设备")

    print(f"\n[Backend] 请执行: ssh ubuntu@43.142.49.126 'sudo docker logs family-backend --tail 80'")
    print("  检查 [WS-RAW] 的 bytes= 是否 > 640（非仅心跳）")


if __name__ == "__main__":
    asyncio.run(run())

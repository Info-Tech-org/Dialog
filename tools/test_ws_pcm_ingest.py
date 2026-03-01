#!/usr/bin/env python3
"""
WebSocket PCM Ingest 测试客户端

测试 /ws/ingest/pcm WebSocket 端点的功能：
- 二进制帧协议
- 幂等性和顺序控制
- ACK 机制
- Final 处理

使用方式：
    python test_ws_pcm_ingest.py --base ws://localhost:8000
    python test_ws_pcm_ingest.py --base ws://play.devc.me:8000 --token YOUR_TOKEN
"""

import asyncio
import websockets
import struct
import json
import argparse
import uuid
import numpy as np
from typing import Optional


def generate_test_pcm(duration_seconds: float = 2.0, frequency: int = 440) -> bytes:
    """
    生成测试 PCM 数据 (440Hz 正弦波)

    Args:
        duration_seconds: 音频时长（秒）
        frequency: 频率（Hz）

    Returns:
        PCM bytes (s16le, 16kHz, mono, 16-bit)
    """
    sample_rate = 16000
    num_samples = int(sample_rate * duration_seconds)

    # 生成正弦波
    t = np.linspace(0, duration_seconds, num_samples, endpoint=False)
    amplitude = 16000  # 16-bit range
    wave = amplitude * np.sin(2 * np.pi * frequency * t)

    # 转换为 int16
    pcm_data = wave.astype(np.int16)

    return pcm_data.tobytes()


def create_frame(chunk_index: int, is_final: bool, pcm_payload: bytes) -> bytes:
    """
    创建 WebSocket 二进制帧

    格式：
    [0:4]   chunk_index (uint32 big-endian)
    [4]     flags (bit0=is_final)
    [5:]    PCM payload
    """
    # Pack chunk_index as uint32 big-endian
    header = struct.pack('>I', chunk_index)

    # Flags byte
    flags = 0x01 if is_final else 0x00
    header += bytes([flags])

    # Combine header + payload
    return header + pcm_payload


async def test_ws_ingest(
    base_url: str,
    device_token: Optional[str] = None,
    chunk_size: int = 3200,  # 100ms @ 16kHz * 2 bytes = 3200 bytes
    test_duration: float = 2.0,
):
    """
    测试 WebSocket PCM ingest 功能
    """
    session_id = str(uuid.uuid4())
    device_id = "test-client-ws"

    print(f"📡 Testing WebSocket PCM Ingest")
    print(f"  Base URL: {base_url}")
    print(f"  Session ID: {session_id}")
    print(f"  Device ID: {device_id}")
    print(f"  Chunk size: {chunk_size} bytes")
    print(f"  Test duration: {test_duration}s")
    print()

    # 构建 WebSocket URL
    ws_url = f"{base_url}/ws/ingest/pcm"
    params = [
        f"session_id={session_id}",
        f"device_id={device_id}",
    ]
    if device_token:
        params.append(f"device_token={device_token}")

    ws_url = f"{ws_url}?{'&'.join(params)}"

    # 生成测试 PCM 数据
    print("🎵 Generating test PCM data...")
    full_pcm = generate_test_pcm(duration_seconds=test_duration)
    print(f"  Generated {len(full_pcm)} bytes of PCM data")
    print()

    # 分片
    chunks = []
    offset = 0
    chunk_index = 0
    while offset < len(full_pcm):
        end = min(offset + chunk_size, len(full_pcm))
        chunk_data = full_pcm[offset:end]
        is_final = (end >= len(full_pcm))
        chunks.append((chunk_index, is_final, chunk_data))
        offset = end
        chunk_index += 1

    print(f"📦 Split into {len(chunks)} chunks")
    print()

    # 连接 WebSocket
    print(f"🔌 Connecting to {ws_url}...")
    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ Connected successfully!")
            print()

            # 发送所有分片
            for idx, (chunk_idx, is_final, payload) in enumerate(chunks, 1):
                frame = create_frame(chunk_idx, is_final, payload)

                print(f"📤 Sending chunk {chunk_idx}/{len(chunks)-1} (final={is_final}, size={len(payload)})")
                await websocket.send(frame)

                # 接收 ACK
                response = await websocket.recv()
                ack = json.loads(response)

                if ack.get("ok"):
                    if ack.get("final"):
                        print(f"✅ FINAL ACK received!")
                        print(f"   Audio URL: {ack.get('audio_url')}")
                        print(f"   Total bytes: {ack.get('received_bytes')}")
                        print(f"   Total chunks: {ack.get('chunks')}")
                    else:
                        print(f"✅ ACK: chunk {ack.get('chunk_index')}, bytes={ack.get('received_bytes')}")
                else:
                    print(f"❌ Error: {ack.get('error')}")
                    if 'expected' in ack:
                        print(f"   Expected chunk: {ack['expected']}")
                    break

                print()

                # 小延迟模拟真实场景
                await asyncio.sleep(0.01)

            print("🎉 Test completed successfully!")

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"❌ Connection failed: HTTP {e.status_code}")
        print(f"   Headers: {e.headers}")
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")


async def test_retry_idempotency(
    base_url: str,
    device_token: Optional[str] = None,
):
    """
    测试幂等性：重复发送同一 chunk
    """
    session_id = str(uuid.uuid4())
    device_id = "test-retry-ws"

    print(f"🔄 Testing Idempotency (Retry)")
    print(f"  Session ID: {session_id}")
    print()

    ws_url = f"{base_url}/ws/ingest/pcm?session_id={session_id}&device_id={device_id}"
    if device_token:
        ws_url += f"&device_token={device_token}"

    # 简单的测试数据
    test_pcm = b'\x00\x00' * 1600  # 3200 bytes

    async with websockets.connect(ws_url) as websocket:
        print("✅ Connected")
        print()

        # 发送 chunk 0
        frame0 = create_frame(0, False, test_pcm)
        print("📤 Sending chunk 0 (first time)")
        await websocket.send(frame0)
        ack0 = json.loads(await websocket.recv())
        print(f"✅ ACK: {ack0}")
        print()

        # 重复发送 chunk 0 (模拟重试)
        print("📤 Sending chunk 0 again (retry simulation)")
        await websocket.send(frame0)
        ack0_retry = json.loads(await websocket.recv())
        print(f"✅ ACK (should be idempotent): {ack0_retry}")
        print()

        # 发送 chunk 1
        frame1 = create_frame(1, False, test_pcm)
        print("📤 Sending chunk 1")
        await websocket.send(frame1)
        ack1 = json.loads(await websocket.recv())
        print(f"✅ ACK: {ack1}")
        print()

        # 发送 final chunk 2
        frame2 = create_frame(2, True, test_pcm)
        print("📤 Sending chunk 2 (final)")
        await websocket.send(frame2)
        ack_final = json.loads(await websocket.recv())
        print(f"✅ FINAL ACK: {ack_final}")
        print()

        print("🎉 Idempotency test passed!")


async def test_out_of_order(
    base_url: str,
    device_token: Optional[str] = None,
):
    """
    测试乱序检测：跳过chunk发送
    """
    session_id = str(uuid.uuid4())
    device_id = "test-ooo-ws"

    print(f"⚠️  Testing Out-of-Order Detection")
    print(f"  Session ID: {session_id}")
    print()

    ws_url = f"{base_url}/ws/ingest/pcm?session_id={session_id}&device_id={device_id}"
    if device_token:
        ws_url += f"&device_token={device_token}"

    test_pcm = b'\x00\x00' * 1600

    async with websockets.connect(ws_url) as websocket:
        print("✅ Connected")
        print()

        # 发送 chunk 0
        frame0 = create_frame(0, False, test_pcm)
        print("📤 Sending chunk 0")
        await websocket.send(frame0)
        ack0 = json.loads(await websocket.recv())
        print(f"✅ ACK: {ack0}")
        print()

        # 跳过 chunk 1，直接发送 chunk 2 (out of order)
        frame2 = create_frame(2, False, test_pcm)
        print("📤 Sending chunk 2 (skipping chunk 1 - should fail)")
        await websocket.send(frame2)
        ack_ooo = json.loads(await websocket.recv())
        print(f"❌ Expected error: {ack_ooo}")

        if ack_ooo.get("error") == "out_of_order" and ack_ooo.get("expected") == 1:
            print("✅ Out-of-order detection works correctly!")
        else:
            print("⚠️  Unexpected response")

        print()


def main():
    parser = argparse.ArgumentParser(description="WebSocket PCM Ingest Test Client")
    parser.add_argument(
        "--base",
        default="ws://localhost:8000",
        help="WebSocket base URL (e.g., ws://localhost:8000)"
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Device token for authentication"
    )
    parser.add_argument(
        "--test",
        choices=["full", "retry", "ooo", "all"],
        default="full",
        help="Test type: full (complete upload), retry (idempotency), ooo (out-of-order), all"
    )

    args = parser.parse_args()

    if args.test == "full" or args.test == "all":
        print("=" * 60)
        asyncio.run(test_ws_ingest(args.base, args.token))
        print()

    if args.test == "retry" or args.test == "all":
        print("=" * 60)
        asyncio.run(test_retry_idempotency(args.base, args.token))
        print()

    if args.test == "ooo" or args.test == "all":
        print("=" * 60)
        asyncio.run(test_out_of_order(args.base, args.token))
        print()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
直连腾讯云实时 ASR 测试 —— 不经过后端，直接测腾讯 WSS。
用于验证签名、网络、识别能力。

用法（在服务器上或 Docker 容器内执行）：
  python3 tools/test_tencent_asr_direct.py
  python3 tools/test_tencent_asr_direct.py --wav /path/to/speech.wav
  python3 tools/test_tencent_asr_direct.py --appid XXX --secret-id YYY --secret-key ZZZ

预期输出（服务器在中国境内）：
  [CONNECT] code=0  → 签名正确
  [PARTIAL] 你好
  [FINAL]   你好世界

本地运行如果报 code=6001（跨境限制）属正常。
"""

import asyncio
import json
import hmac
import hashlib
import base64
import time
import struct
import math
import wave
import argparse
import os
import sys
from urllib.parse import quote

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)


def build_asr_url(appid: str, secret_id: str, secret_key: str, voice_id: str) -> str:
    """Build Tencent realtime ASR WSS URL with correct signature."""
    timestamp = int(time.time())
    expired = timestamp + 86400
    nonce = timestamp

    params = {
        "engine_model_type": "16k_zh",
        "expired": str(expired),
        "nonce": str(nonce),
        "secretid": secret_id,
        "timestamp": str(timestamp),
        "voice_format": "1",
        "voice_id": voice_id,
    }

    sorted_params = "&".join(f"{k}={params[k]}" for k in sorted(params))
    sign_str = f"asr.cloud.tencent.com/asr/v2/{appid}?{sorted_params}"

    sig = base64.b64encode(
        hmac.new(secret_key.encode(), sign_str.encode(), hashlib.sha1).digest()
    ).decode()

    params["signature"] = quote(sig)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"wss://asr.cloud.tencent.com/asr/v2/{appid}?{query}"


FRAME_BYTES = 640  # 20ms @ 16kHz s16le mono


def generate_sine_frames(duration_sec: float = 3.0, freq: float = 440.0):
    """Generate PCM sine wave frames for testing."""
    frames = []
    buf = bytearray()
    for i in range(int(16000 * duration_sec)):
        val = int(8000 * math.sin(2 * math.pi * freq * i / 16000))
        buf += struct.pack('<h', val)
        if len(buf) >= FRAME_BYTES:
            frames.append(bytes(buf[:FRAME_BYTES]))
            buf = buf[FRAME_BYTES:]
    if buf:
        buf += b'\x00' * (FRAME_BYTES - len(buf))
        frames.append(bytes(buf))
    return frames


def load_wav_frames(wav_path: str):
    """Load WAV file into 640-byte PCM frames."""
    with wave.open(wav_path, 'rb') as wf:
        ch = wf.getnchannels()
        rate = wf.getframerate()
        sw = wf.getsampwidth()
        raw = wf.readframes(wf.getnframes())

    if sw != 2:
        print(f"ERROR: need 16-bit WAV, got {sw*8}-bit")
        sys.exit(1)

    # Stereo → mono
    if ch == 2:
        mono = bytearray()
        for i in range(0, len(raw), 4):
            mono += raw[i:i+2]
        raw = bytes(mono)

    # Resample to 16kHz if needed
    if rate != 16000:
        samples = struct.unpack(f'<{len(raw)//2}h', raw)
        ratio = rate / 16000
        resampled = [samples[min(int(i * ratio), len(samples)-1)]
                     for i in range(int(len(samples) / ratio))]
        raw = struct.pack(f'<{len(resampled)}h', *resampled)

    frames = []
    for i in range(0, len(raw), FRAME_BYTES):
        chunk = raw[i:i+FRAME_BYTES]
        if len(chunk) < FRAME_BYTES:
            chunk += b'\x00' * (FRAME_BYTES - len(chunk))
        frames.append(chunk)

    return frames, len(raw) / (16000 * 2)


async def run_test(appid, secret_id, secret_key, wav_path):
    voice_id = f"test_{int(time.time() * 1000)}"
    url = build_asr_url(appid, secret_id, secret_key, voice_id)

    # Prepare audio
    if wav_path:
        print(f"[AUDIO] Loading WAV: {wav_path}")
        frames, dur = load_wav_frames(wav_path)
        print(f"[AUDIO] {len(frames)} frames, {dur:.1f}s")
    else:
        print("[AUDIO] Generating 3s 440Hz sine wave")
        frames = generate_sine_frames(3.0, 440.0)
        dur = 3.0

    print(f"[CONNECT] Connecting to Tencent ASR (voice_id={voice_id[:30]}...)...")
    test_start = time.time()

    try:
        ws = await asyncio.wait_for(websockets.connect(url), timeout=10)
    except Exception as e:
        print(f"[CONNECT] FAIL: WebSocket connection error: {e}")
        return False

    # Wait for initial auth response
    try:
        first_msg = await asyncio.wait_for(ws.recv(), timeout=5)
        first_data = json.loads(first_msg)
        code = first_data.get("code")
        msg = first_data.get("message", "")

        if code == 0:
            print(f"[CONNECT] code=0  AUTH OK  ({time.time()-test_start:.1f}s)")
        else:
            print(f"[CONNECT] code={code}  FAIL: {msg}")
            if code == 6001:
                print("[INFO] code=6001 = cross-border restriction. Run this ON the server in China.")
            await ws.close()
            return code == 6001  # 6001 is "expected" when testing locally
    except Exception as e:
        print(f"[CONNECT] FAIL reading initial response: {e}")
        await ws.close()
        return False

    # Send audio
    results = []
    first_partial_time = None
    first_final_time = None

    async def sender():
        for frame in frames:
            await ws.send(frame)
            await asyncio.sleep(0.02)
        print(f"[SEND] Done: {len(frames)} frames in {time.time()-test_start:.1f}s")
        await asyncio.sleep(1)
        # Send end signal
        try:
            await ws.send(json.dumps({"type": "end"}))
        except Exception:
            pass

    async def receiver():
        nonlocal first_partial_time, first_final_time
        try:
            async for msg in ws:
                data = json.loads(msg)
                code = data.get("code")
                if code == 0:
                    result = data.get("result", {})
                    text = result.get("voice_text_str", "")
                    slice_type = result.get("slice_type", 0)
                    elapsed = time.time() - test_start
                    if text:
                        is_final = slice_type == 1
                        tag = "FINAL" if is_final else "PARTIAL"
                        print(f"  [{elapsed:.1f}s] [{tag}] {text}")
                        results.append({"text": text, "is_final": is_final, "elapsed": elapsed})
                        if not is_final and first_partial_time is None:
                            first_partial_time = elapsed
                        if is_final and first_final_time is None:
                            first_final_time = elapsed
                elif code == 4008:
                    print(f"  [{time.time()-test_start:.1f}s] ASR session ended (4008)")
                    break
                else:
                    print(f"  [{time.time()-test_start:.1f}s] code={code}: {data.get('message','')[:60]}")
        except websockets.exceptions.ConnectionClosed:
            pass

    await asyncio.gather(sender(), receiver())

    try:
        await ws.close()
    except Exception:
        pass

    # Report
    print()
    print("=" * 50)
    print("TENCENT ASR DIRECT TEST REPORT")
    print("=" * 50)
    total = time.time() - test_start
    print(f"Total duration:       {total:.1f}s")
    print(f"Audio:                {'WAV: ' + wav_path if wav_path else '440Hz sine'}")
    print(f"Messages received:    {len(results)}")
    if first_partial_time:
        print(f"First partial at:     {first_partial_time:.1f}s")
    if first_final_time:
        print(f"First final at:       {first_final_time:.1f}s")
    finals = [r for r in results if r["is_final"]]
    print(f"Final sentences:      {len(finals)}")
    for f in finals:
        print(f"  \"{f['text']}\"")

    success = len(results) > 0
    print(f"\nOverall: {'PASS' if success else 'FAIL'}")
    return success


def main():
    parser = argparse.ArgumentParser(description="Direct Tencent Realtime ASR test")
    parser.add_argument("--appid", default="1314143047")
    parser.add_argument("--secret-id", default=os.environ.get("TENCENT_SECRET_ID", ""), help="Tencent Secret ID (or set TENCENT_SECRET_ID)")
    parser.add_argument("--secret-key", default=os.environ.get("TENCENT_SECRET_KEY", ""), help="Tencent Secret Key (or set TENCENT_SECRET_KEY)")
    parser.add_argument("--wav", default="", help="Path to WAV file (16kHz mono preferred)")
    args = parser.parse_args()

    result = asyncio.run(run_test(args.appid, args.secret_id, args.secret_key, args.wav))
    sys.exit(0 if result else 1)


if __name__ == "__main__":
    main()

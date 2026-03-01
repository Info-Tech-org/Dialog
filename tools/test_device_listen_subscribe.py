#!/usr/bin/env python3
"""
最小订阅脚本：连接 /ws/ingest/device-listen
打印每秒收到的 binary frame 数量、每个 frame 长度（如 640）
用法: python3 tools/test_device_listen_subscribe.py --base ws://43.142.49.126:9000 --device esp32c6_001
"""
import asyncio
import argparse
import time
import sys

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)


async def run(base_url: str, device_id: str, duration: int = 15):
    url = f"{base_url.rstrip('/')}/ws/ingest/device-listen?device_id={device_id}"
    print(f"[Connect] {url}")
    print(f"[Info] 将运行 {duration} 秒，每秒输出统计")
    print()

    frame_count = 0
    total_bytes = 0
    frame_lengths = []
    last_report = time.time()

    try:
        async with websockets.connect(url) as ws:
            print("[OK] 已连接 device-listen")
            start = time.time()
            while time.time() - start < duration:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass
                else:
                    if isinstance(msg, bytes):
                        frame_count += 1
                        total_bytes += len(msg)
                        frame_lengths.append(len(msg))
                        if len(frame_lengths) > 100:
                            frame_lengths = frame_lengths[-100:]
                    # else: text (e.g. boundary)

                now = time.time()
                if now - last_report >= 1.0:
                    last_report = now
                    elapsed = now - start
                    fps = frame_count / elapsed if elapsed > 0 else 0
                    print(f"  [{elapsed:.0f}s] frames={frame_count} total_bytes={total_bytes} "
                          f"fps={fps:.1f} "
                          f"len_sample={frame_lengths[-10:] if frame_lengths else []}")

    except Exception as e:
        print(f"[Error] {e}")

    print()
    print("[Summary]")
    print(f"  Total frames: {frame_count}")
    print(f"  Total bytes:  {total_bytes}")
    if frame_lengths:
        print(f"  Frame lengths (last 20): {frame_lengths[-20:]}")
        from collections import Counter
        cnt = Counter(frame_lengths)
        print(f"  Length distribution: {dict(cnt)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="ws://43.142.49.126:9000")
    p.add_argument("--device", default="esp32c6_001")
    p.add_argument("--duration", type=int, default=15)
    args = p.parse_args()
    asyncio.run(run(args.base, args.device, args.duration))


if __name__ == "__main__":
    main()

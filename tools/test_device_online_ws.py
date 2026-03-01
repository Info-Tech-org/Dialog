#!/usr/bin/env python3
"""
ESP32 设备在线状态 + WS 闪断验证
- 连接 /ws/ingest/pcm?raw=1&device_id=esp32c6_001&device_token=<TOKEN>
- 每 5 秒发 4 字节心跳，持续 30 秒
- 每 3 秒 GET /api/devices 记录 is_online/last_seen
- 若 WS 断开，记录 close code/reason
用法: python3 tools/test_device_online_ws.py --base http://43.142.49.126:9000 --token TOKEN [--jwt JWT]
"""

import asyncio
import json
import argparse
import time
import sys

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets")
    sys.exit(1)

import urllib.request
import urllib.error

DEVICE_ID = "esp32c6_001"
DURATION_SEC = 30
HEARTBEAT_INTERVAL = 5
POLL_INTERVAL = 3


def get_devices(base_url: str, jwt: str) -> list:
    """GET /api/devices"""
    url = base_url.rstrip("/") + "/api/devices"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {jwt}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}


def login(base_url: str, username: str, password: str) -> str:
    """POST /api/auth/login"""
    url = base_url.rstrip("/") + "/api/auth/login"
    data = json.dumps({"username": username, "password": password}).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode()).get("access_token", "")
    except Exception as e:
        print(f"Login failed: {e}")
        return ""


async def run_test(base_url: str, token: str, jwt: str):
    ws_base = base_url.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    ingest_url = f"{ws_base}/ws/ingest/pcm?raw=1&device_id={DEVICE_ID}&device_token={token}"

    print(f"[ENV] Base: {base_url}")
    print(f"[ENV] WS:   {ingest_url[:80]}...")
    print()

    # 1. 初始 devices
    print("[1] 初始 GET /api/devices")
    devices = get_devices(base_url, jwt)
    if isinstance(devices, dict) and "error" in devices:
        print(f"  ERROR: {devices['error']}")
    else:
        esp = next((d for d in devices if d.get("device_id") == DEVICE_ID), None)
        if esp:
            print(f"  esp32c6_001: is_online={esp.get('is_online')}, last_seen={esp.get('last_seen')}")
        else:
            print(f"  esp32c6_001: 不存在于设备列表 (共 {len(devices)} 台)")
            for d in devices:
                print(f"    - {d.get('device_id')}: is_online={d.get('is_online')}, last_seen={d.get('last_seen')}")
    print()

    close_code = None
    close_reason = None
    ws_disconnected_at = None

    async def ws_client():
        nonlocal close_code, close_reason, ws_disconnected_at
        try:
            ws = await websockets.connect(ingest_url, ping_interval=None, close_timeout=2)
            print(f"[WS] 连接成功 @ {time.strftime('%H:%M:%S')}")
            start = time.time()
            while time.time() - start < DURATION_SEC:
                await ws.send(b"\x00\x00\x00\x00")  # 4 字节心跳
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            await ws.close()
        except websockets.exceptions.ConnectionClosed as e:
            close_code = e.code
            close_reason = e.reason or ""
            ws_disconnected_at = time.time()
            print(f"[WS] 连接被关闭: code={e.code}, reason={e.reason!r}")
        except Exception as e:
            print(f"[WS] 异常: {e}")
            ws_disconnected_at = time.time()

    async def poll_devices():
        start = time.time()
        poll_count = 0
        while time.time() - start < DURATION_SEC + 5:
            await asyncio.sleep(POLL_INTERVAL)
            poll_count += 1
            devices = get_devices(base_url, jwt)
            if isinstance(devices, dict) and "error" in devices:
                print(f"  [{poll_count}] GET /api/devices 失败: {devices['error']}")
            else:
                esp = next((d for d in devices if d.get("device_id") == DEVICE_ID), None)
                t = time.strftime("%H:%M:%S")
                if esp:
                    print(f"  [{poll_count}] {t} esp32c6_001: is_online={esp.get('is_online')}, last_seen={esp.get('last_seen')}")
                else:
                    print(f"  [{poll_count}] {t} esp32c6_001 不在列表中")

    await asyncio.gather(ws_client(), poll_devices())

    # 最终 devices
    print()
    print("[2] 最终 GET /api/devices")
    devices = get_devices(base_url, jwt)
    if isinstance(devices, dict) and "error" in devices:
        print(f"  ERROR: {devices['error']}")
    else:
        esp = next((d for d in devices if d.get("device_id") == DEVICE_ID), None)
        if esp:
            print(f"  esp32c6_001: is_online={esp.get('is_online')}, last_seen={esp.get('last_seen')}")
        else:
            print(f"  esp32c6_001: 不存在于设备列表")
    print()

    return {"close_code": close_code, "close_reason": close_reason, "ws_disconnected_at": ws_disconnected_at}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://43.142.49.126:9000")
    p.add_argument("--token", required=True, help="device_token")
    p.add_argument("--jwt", default="", help="JWT for /api/devices，不传则用 admin/admin123 登录")
    p.add_argument("--user", default="admin")
    p.add_argument("--password", default="admin123")
    args = p.parse_args()

    jwt = args.jwt
    if not jwt:
        jwt = login(args.base, args.user, args.password)
        if not jwt:
            print("无法获取 JWT，/api/devices 将失败")
            sys.exit(1)

    result = asyncio.run(run_test(args.base, args.token, jwt))
    if result["close_code"] is not None:
        print(f"[RESULT] WS 断开: code={result['close_code']}, reason={result['close_reason']!r}")
        sys.exit(2)
    print("[RESULT] WS 30 秒内未断开")
    sys.exit(0)


if __name__ == "__main__":
    main()

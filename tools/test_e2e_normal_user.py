#!/usr/bin/env python3
"""
普通用户视角端到端复测：
1. 普通账号登录
2. 模拟 ESP32 WS 连接（raw=1 + token）
3. 验证 GET /api/devices/unclaimed 返回未认领设备（等价于页面 unclaimed 卡片）
4. 模拟点击认领 POST /api/devices
5. 断网/重连，验证在线状态变化

用法: python3 tools/test_e2e_normal_user.py --base http://43.142.49.126:9000 --token TOKEN
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
TOKEN = ""


def api_login(base, user, password):
    url = base.rstrip("/") + "/api/auth/login"
    data = json.dumps({"username": user, "password": password}).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode()).get("access_token", "")


def api_get(base, path, jwt):
    url = base.rstrip("/") + path
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {jwt}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": f"{e.code} {e.reason}", "_body": e.read().decode() if e.fp else ""}


def api_post(base, path, jwt, body):
    url = base.rstrip("/") + path
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": f"{e.code}", "_body": e.read().decode() if e.fp else ""}


def api_delete(base, path, jwt):
    url = base.rstrip("/") + path
    req = urllib.request.Request(url, method="DELETE", headers={"Authorization": f"Bearer {jwt}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


async def run_e2e(base, device_token):
    ws_base = base.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    ingest_url = f"{ws_base}/ws/ingest/pcm?raw=1&device_id={DEVICE_ID}&device_token={device_token}"

    print("=" * 60)
    print("普通用户视角 端到端复测")
    print("=" * 60)
    print(f"BASE: {base}")
    print(f"Device: {DEVICE_ID}")
    print()

    # 0. 用 admin 清理设备（确保干净状态）
    jwt_admin = api_login(base, "admin", "admin123")
    if jwt_admin:
        api_delete(base, f"/api/devices/{DEVICE_ID}", jwt_admin)
        print("[0] Admin 解绑 esp32c6_001（重置）")
    print()

    # 1. 普通用户登录
    print("[1] 普通用户登录 Web")
    jwt = api_login(base, "testuser_claim", "test123")
    if not jwt:
        print("  FAIL: 登录失败")
        return False
    print("  OK: 已获取 JWT")
    print()

    # 2. 连接前：unclaimed 为空，devices 为空
    print("[2] 连接前: GET /api/devices, GET /api/devices/unclaimed")
    devices = api_get(base, "/api/devices", jwt)
    unclaimed = api_get(base, "/api/devices/unclaimed", jwt)
    dev_list = devices if isinstance(devices, list) else []
    unc_list = unclaimed if isinstance(unclaimed, list) else []
    esp_dev = next((d for d in dev_list if d.get("device_id") == DEVICE_ID), None)
    esp_unc = next((d for d in unc_list if d.get("device_id") == DEVICE_ID), None)
    print(f"  我的设备: {len(dev_list)} 台, esp32c6_001: {'有' if esp_dev else '无'}")
    print(f"  待认领: {len(unc_list)} 台, esp32c6_001: {'有' if esp_unc else '无'}")
    print()

    # 3. 模拟 ESP32 上电连 WS
    print("[3] 模拟 ESP32 上电连 WS (raw=1 + token)")
    try:
        ws = await websockets.connect(ingest_url, ping_interval=None)
        await ws.send(b"\x00\x00\x00\x00")  # 4 字节心跳
        print("  OK: ESP32 WS 已连接")
    except Exception as e:
        print(f"  FAIL: {e}")
        return False
    print()

    # 4. 等待并验证 unclaimed 卡片（页面刷新 5s 轮询）
    print("[4] 验证 unclaimed 卡片（GET /api/devices/unclaimed）")
    await asyncio.sleep(2)
    unclaimed = api_get(base, "/api/devices/unclaimed", jwt)
    unc_list = unclaimed if isinstance(unclaimed, list) else []
    esp_unc = next((d for d in unc_list if d.get("device_id") == DEVICE_ID), None)
    if esp_unc:
        print(f"  OK: 发现新设备 esp32c6_001 (is_online={esp_unc.get('is_online')}, last_seen={esp_unc.get('last_seen')})")
        print("  => 页面应显示「发现新设备」绿色卡片")
    else:
        print(f"  FAIL: unclaimed 未返回 esp32c6_001。unclaimed={unc_list}")
    print()

    # 5. 模拟点击认领
    print("[5] 模拟点击认领 (POST /api/devices)")
    claim = api_post(base, "/api/devices", jwt, {"device_id": DEVICE_ID, "name": ""})
    if "_error" in claim:
        print(f"  FAIL: {claim.get('_body', claim)}")
    else:
        print(f"  OK: 认领成功 user_id={claim.get('user_id')}")
        print("  => 绿色卡片消失，设备移入「已绑定设备」列表")
    print()

    # 6. 验证认领后
    print("[6] 认领后 GET /api/devices")
    devices = api_get(base, "/api/devices", jwt)
    dev_list = devices if isinstance(devices, list) else []
    esp_dev = next((d for d in dev_list if d.get("device_id") == DEVICE_ID), None)
    if esp_dev:
        print(f"  esp32c6_001: user_id={esp_dev.get('user_id')}, is_online={esp_dev.get('is_online')}")
    else:
        print("  FAIL: 设备不在列表中")
    print()

    # 7. 断网（关闭 WS）
    print("[7] 断网（ESP32 断开 WS）")
    await ws.close()
    await asyncio.sleep(2)
    devices = api_get(base, "/api/devices", jwt)
    dev_list = devices if isinstance(devices, list) else []
    esp_dev = next((d for d in dev_list if d.get("device_id") == DEVICE_ID), None)
    if esp_dev:
        print(f"  断开后: is_online={esp_dev.get('is_online')} (应为 false)")
        ok_offline = esp_dev.get("is_online") == False
    else:
        ok_offline = False
    print()

    # 8. 重连
    print("[8] 重连（ESP32 再次连 WS）")
    ws2 = await websockets.connect(ingest_url, ping_interval=None)
    await ws2.send(b"\x00\x00\x00\x00")
    await asyncio.sleep(2)
    devices = api_get(base, "/api/devices", jwt)
    dev_list = devices if isinstance(devices, list) else []
    esp_dev = next((d for d in dev_list if d.get("device_id") == DEVICE_ID), None)
    if esp_dev:
        print(f"  重连后: is_online={esp_dev.get('is_online')} (应为 true)")
        ok_online = esp_dev.get("is_online") == True
    else:
        ok_online = False
    await ws2.close()
    print()

    print("=" * 60)
    success = esp_unc is not None and "_error" not in (claim or {}) and esp_dev and ok_offline and ok_online
    print(f"结果: {'PASS' if success else 'FAIL'}")
    return success


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://43.142.49.126:9000")
    p.add_argument("--token", required=True)
    args = p.parse_args()

    ok = asyncio.run(run_e2e(args.base, args.token))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
设备自动创建 → 用户认领 → 在线状态刷新 闭环验证
用法: python3 tools/test_device_claim_flow.py --base http://43.142.49.126:9000 --token TOKEN [--user USER --password PASS]
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

BASE = "http://43.142.49.126:9000"
TOKEN = ""
JWT = ""
TIMELINE = []


def api_login(base, user, password):
    url = base.rstrip("/") + "/api/auth/login"
    data = json.dumps({"username": user, "password": password}).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode()).get("access_token", "")


def api_get_devices(base, jwt):
    url = base.rstrip("/") + "/api/devices"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {jwt}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": f"{e.code} {e.reason}"}


def api_post_devices(base, jwt, device_id, name=""):
    url = base.rstrip("/") + "/api/devices"
    data = json.dumps({"device_id": device_id, "name": name}).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def api_delete_device(base, jwt, device_id):
    url = base.rstrip("/") + f"/api/devices/{device_id}"
    req = urllib.request.Request(url, method="DELETE", headers={"Authorization": f"Bearer {jwt}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


async def run_test(base, device_token, jwt_user, jwt_admin, user, password):
    ws_base = base.replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    ingest_url = f"{ws_base}/ws/ingest/pcm?raw=1&device_id={DEVICE_ID}&device_token={device_token}"

    print(f"[ENV] Base: {base}")
    print(f"[ENV] WS:   {ingest_url[:70]}...")
    print()

    # S1 已登录，JWT 为 jwt_user
    jwt = jwt_user

    # S2 当前用户设备列表
    print("[S2] GET /api/devices (普通用户)")
    devices = api_get_devices(base, jwt)
    esp = next((d for d in devices if d.get("device_id") == DEVICE_ID), None)
    print(f"  设备列表: {len(devices)} 台, esp32c6_001 存在: {esp is not None}")
    if esp:
        print(f"  esp32c6_001: user_id={esp.get('user_id')}, is_online={esp.get('is_online')}, last_seen={esp.get('last_seen')}")
    print()

    # S3 & S4: WS 连接 + 轮询
    poll_records = []

    async def ws_client():
        try:
            ws = await websockets.connect(ingest_url, ping_interval=None, close_timeout=2)
            print(f"[S3] WS 连接成功 @ {time.strftime('%H:%M:%S')}")
            start = time.time()
            while time.time() - start < DURATION_SEC:
                await ws.send(b"\x00\x00\x00\x00")
                await asyncio.sleep(HEARTBEAT_INTERVAL)
            await ws.close()
            print(f"[S3] WS 30 秒结束，客户端主动关闭")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[S3] WS 被断开: code={e.code}, reason={e.reason!r}")
        except Exception as e:
            print(f"[S3] WS 异常: {e}")

    async def poll():
        start = time.time()
        n = 0
        while time.time() - start < DURATION_SEC + 8:
            await asyncio.sleep(POLL_INTERVAL)
            n += 1
            t = time.strftime("%H:%M:%S")
            # 普通用户
            devs = api_get_devices(base, jwt_user)
            esp_u = next((d for d in (devs if isinstance(devs, list) else []) if d.get("device_id") == DEVICE_ID), None)
            # Admin
            devs_admin = api_get_devices(base, jwt_admin)
            esp_a = next((d for d in (devs_admin if isinstance(devs_admin, list) else []) if d.get("device_id") == DEVICE_ID), None)
            rec = {
                "n": n, "t": t,
                "user_has": esp_u is not None,
                "user_online": esp_u.get("is_online") if esp_u else None,
                "user_last_seen": str(esp_u.get("last_seen"))[:26] if esp_u else None,
                "admin_has": esp_a is not None,
                "admin_user_id": esp_a.get("user_id") if esp_a else None,
                "admin_online": esp_a.get("is_online") if esp_a else None,
                "admin_last_seen": str(esp_a.get("last_seen"))[:26] if esp_a else None,
            }
            poll_records.append(rec)
            u_tag = "user有" if esp_u else "user无"
            a_tag = f"admin有(user_id={esp_a.get('user_id')},online={esp_a.get('is_online')})" if esp_a else "admin无"
            print(f"  [{n}] {t} 普通用户:{u_tag} | admin:{a_tag}")

    await asyncio.gather(ws_client(), poll())

    # S5 认领
    print()
    print("[S5] POST /api/devices 认领 (device_id=esp32c6_001)")
    try:
        claim = api_post_devices(base, jwt_user, DEVICE_ID, "ESP32 认领测试")
        print(f"  认领成功: {claim}")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"  认领失败: {e.code} {body}")

    # S6 再次验证
    print()
    print("[S6] GET /api/devices 验证认领后")
    devices = api_get_devices(base, jwt_user)
    esp = next((d for d in devices if d.get("device_id") == DEVICE_ID), None)
    if esp:
        print(f"  esp32c6_001: user_id={esp.get('user_id')}, is_online={esp.get('is_online')}, last_seen={esp.get('last_seen')}")
    else:
        print("  esp32c6_001 仍不在列表中")

    # 断开后再次连接一次，验证 is_online 更新
    print()
    print("[S6b] 再次 WS 连接 5 秒后断开，验证 is_online 刷新")
    try:
        ws = await websockets.connect(ingest_url, ping_interval=None)
        await ws.send(b"\x00\x00\x00\x00")
        await asyncio.sleep(5)
        await ws.close()
    except Exception as e:
        print(f"  WS 异常: {e}")
    await asyncio.sleep(1)
    devices = api_get_devices(base, jwt_user)
    esp = next((d for d in devices if d.get("device_id") == DEVICE_ID), None)
    if esp:
        print(f"  连接中: is_online={esp.get('is_online')}, last_seen={esp.get('last_seen')}")
    await asyncio.sleep(2)  # 等待断开
    devices = api_get_devices(base, jwt_user)
    esp = next((d for d in devices if d.get("device_id") == DEVICE_ID), None)
    if esp:
        print(f"  断开后: is_online={esp.get('is_online')}, last_seen={esp.get('last_seen')}")

    return poll_records


def main():
    global BASE, TOKEN, JWT
    p = argparse.ArgumentParser()
    p.add_argument("--base", default="http://43.142.49.126:9000")
    p.add_argument("--token", required=True)
    p.add_argument("--user", default="testuser_claim")
    p.add_argument("--password", default="test123")
    args = p.parse_args()
    BASE = args.base
    TOKEN = args.token

    # 注册普通用户（若已存在则登录）
    print("[S1] 登录/注册")
    jwt_admin = api_login(BASE, "admin", "admin123")
    if not jwt_admin:
        print("Admin 登录失败")
        sys.exit(1)
    try:
        req = urllib.request.Request(
            BASE.rstrip("/") + "/api/auth/register",
            data=json.dumps({"username": args.user, "email": f"{args.user}@example.com", "password": args.password}).encode(),
            method="POST", headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=10)
        print(f"  注册用户 {args.user}")
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        if e.code == 400:
            print(f"  注册返回 400: {body[:80]} (可能已存在)")
        else:
            print(f"  注册失败: {e.code} {body[:80]}")

    jwt_user = api_login(BASE, args.user, args.password)
    if not jwt_user:
        print("普通用户登录失败")
        sys.exit(1)
    print(f"  普通用户 JWT 已获取")
    print()

    # 清理：删除可能已存在的 esp32c6_001 绑定（admin 解绑）
    try:
        api_delete_device(BASE, jwt_admin, DEVICE_ID)
        print(f"  (Admin 解绑 esp32c6_001 以重置)")
    except Exception:
        pass

    # 若设备已存在且为 admin 绑定，需先解绑。DELETE 可能 404 若 device 不存在
    # 先尝试 unbind - 需要 DELETE /api/devices/{device_id}"
    # 检查 device_routes 的 delete - 是 unbind 不是 delete device。会删除整条记录。
    # 为保持干净，我们可先删除。若设备被 admin 绑定，admin 可删除（unbind 会删除 device 记录吗？看代码是 db.delete(device)）
    # 那会删除整条记录。所以下次 WS 连接会 auto-create。

    poll_records = asyncio.run(run_test(BASE, TOKEN, jwt_user, jwt_admin, args.user, args.password))
    print()
    print("=" * 50)
    print("TIMELINE (供证据文档)")
    for r in poll_records:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()

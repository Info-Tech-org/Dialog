# ESP32 设备在线状态 + WS 闪断验证证据

**执行时间**: 2026-02-12  
**执行角色**: 测试工程师（仅测试与出证据，未改代码）  
**目标**: 验证 ESP32 连接 WS 后设备在 /api/devices 里变 online，并定位 WS 闪断原因

---

## 1. 环境信息

| 项 | 值 |
|----|-----|
| 服务器 | 43.142.49.126:9000 |
| WS 路径 | `/ws/ingest/pcm?raw=1&device_id=esp32c6_001&device_token=<TOKEN>` |
| device_token | `KWOtrT...KZw`（前 6 后 3 打码，全量见 deploy/.env） |

---

## 2. 任务 1：初始 GET /api/devices

**命令**（需先登录获取 JWT）:
```bash
# 登录
JWT=$(curl -sS -X POST "http://43.142.49.126:9000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

# 获取设备列表
curl -sS -H "Authorization: Bearer $JWT" "http://43.142.49.126:9000/api/devices" | python3 -m json.tool
```

**情况 A：设备未绑定时**

输出:
```json
[]
```

结论：`esp32c6_001` 不存在于设备列表，`is_online`/`last_seen` 无法查询（无该设备记录）。

**情况 B：设备已绑定时（绑定命令见下）**

输出:
```json
[
  {
    "id": 2,
    "device_id": "esp32c6_001",
    "user_id": 1,
    "name": "ESP32 C6 测试",
    "is_online": false,
    "last_seen": null,
    "created_at": "2026-02-12T06:15:31.263307"
  }
]
```

**初始值**:
- `esp32c6_001` 存在
- `is_online`: 未绑定时为 N/A；绑定时为 `false`
- `last_seen`: 未绑定时为 N/A；绑定时为 `null`

---

## 3. 设备绑定（前置条件）

设备需先绑定到用户才能被 `/api/devices` 返回，且 `_set_device_online` 才会更新该设备。

```bash
JWT=$(curl -sS -X POST "http://43.142.49.126:9000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

curl -sS -X POST "http://43.142.49.126:9000/api/devices" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"esp32c6_001","name":"ESP32 C6 测试"}'
```

---

## 4. 任务 2 & 3：WS 连接 + 每 3 秒轮询 devices

**命令**（Python 脚本）:
```bash
cd /Users/max/info-tech
python3 tools/test_device_online_ws.py \
  --base http://43.142.49.126:9000 \
  --token "KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw"
```

**脚本行为**:
- 连接 WS `/ws/ingest/pcm?raw=1&device_id=esp32c6_001&device_token=<TOKEN>`
- 每 5 秒发送 4 字节二进制心跳 `\x00\x00\x00\x00`
- 持续 30 秒
- 每 3 秒 GET /api/devices 并记录 is_online、last_seen

**实际输出**（设备已绑定）:
```
[ENV] Base: http://43.142.49.126:9000
[ENV] WS:   ws://43.142.49.126:9000/ws/ingest/pcm?raw=1&device_id=esp32c6_001&device_token=K...

[1] 初始 GET /api/devices
  esp32c6_001: is_online=False, last_seen=None

[WS] 连接成功 @ 14:15:34
  [1] 14:15:37 esp32c6_001: is_online=True, last_seen=2026-02-12T06:15:34.328623
  [2] 14:15:40 esp32c6_001: is_online=True, last_seen=2026-02-12T06:15:34.328623
  [3] 14:15:43 esp32c6_001: is_online=True, last_seen=2026-02-12T06:15:34.328623
  [4] 14:15:46 esp32c6_001: is_online=True, last_seen=2026-02-12T06:15:34.328623
  [5] 14:15:49 esp32c6_001: is_online=True, last_seen=2026-02-12T06:15:34.328623
  [6] 14:15:52 esp32c6_001: is_online=True, last_seen=2026-02-12T06:15:34.328623
  [7] 14:15:55 esp32c6_001: is_online=True, last_seen=2026-02-12T06:15:34.328623
  [8] 14:15:58 esp32c6_001: is_online=True, last_seen=2026-02-12T06:15:34.328623
  [9] 14:16:02 esp32c6_001: is_online=True, last_seen=2026-02-12T06:15:34.328623
  [10] 14:16:05 esp32c6_001: is_online=False, last_seen=2026-02-12T06:16:04.390563
  [11] 14:16:08 esp32c6_001: is_online=False, last_seen=2026-02-12T06:16:04.390563
  [12] 14:16:11 esp32c6_001: is_online=False, last_seen=2026-02-12T06:16:04.390563

[2] 最终 GET /api/devices
  esp32c6_001: is_online=False, last_seen=2026-02-12T06:16:04.390563

[RESULT] WS 30 秒内未断开
```

**结论**:
- ingest WS 连接成功，鉴权通过
- 连接期间 `is_online` 从 `false` 变为 `true`，`last_seen` 被更新
- 第 10 次轮询后 `is_online` 变为 `false`，对应脚本在 30 秒结束时主动关闭连接

---

## 5. 任务 4：WS 断开时的 close code/reason

**本次测试**：WS 由客户端在 30 秒后主动关闭，未发生服务端主动断开，无 close code/reason 可记录。

**若需抓取服务端断开时的日志**：

```bash
# 在服务器上执行（断开前后 50 行）
ssh ubuntu@43.142.49.126
sudo docker logs family-backend --tail 100 2>&1 | tail -50
```

**wscat 复现命令**（若已安装 `npm i -g wscat`）:
```bash
wscat -c "ws://43.142.49.126:9000/ws/ingest/pcm?raw=1&device_id=esp32c6_001&device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw"
# 连接后每 5 秒发送 4 字节二进制（wscat 需用 -b 或类似模式）
# 若被断开，wscat 会输出 close code 和 reason
```

---

## 6. 额外测试：60 秒 idle 连接

**目的**：探测 WS 是否存在 idle 超时导致闪断。

**命令**:
```python
# 连接后 60 秒内不发送任何数据
import asyncio, websockets, time
url = 'ws://43.142.49.126:9000/ws/ingest/pcm?raw=1&device_id=esp32c6_001&device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw'
ws = await websockets.connect(url, ping_interval=None)
# 60 秒内不 send
await asyncio.sleep(60)
```

**结果**：60 秒内连接保持，未发生服务端断开。

---

## 7. 结论汇总

| 结论项 | 结果 |
|--------|------|
| 设备是否需存在 | 需先绑定（POST /api/devices）才能看到 is_online 更新 |
| 鉴权 | 正确 token 可正常连接 |
| 协议 | raw=1 模式下，4 字节心跳可被接受 |
| 服务端断开 | 本次测试未出现异常断开 |

**根因分类**（若 ESP32 实际发生闪断，可按此排查）：

1. **device_id 不存在**：设备未绑定到用户，`/api/devices` 不返回该设备；但 WS 仍可连接，只是 `is_online` 不会更新。
2. **鉴权拒绝**：device_token 错误或缺失 → 连接被拒绝，close code 1008，reason "Unauthorized: Invalid device token"。
3. **协议错误**：raw=1 模式下需发送二进制数据；若发文本或 JSON 可能触发异常。
4. **后端异常**：根据代码，无显式 idle 超时；60 秒 idle 测试未断开。闪断更可能来自：Caddy/网关超时、网络不稳定、ESP32 WiFi 休眠或重连。

---

## 8. 可复现命令（复制粘贴）

```bash
# 1. 登录
JWT=$(curl -sS -X POST "http://43.142.49.126:9000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

# 2. 绑定设备（若未绑定）
curl -sS -X POST "http://43.142.49.126:9000/api/devices" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"esp32c6_001","name":"ESP32 C6 测试"}'

# 3. 查询 devices
curl -sS -H "Authorization: Bearer $JWT" "http://43.142.49.126:9000/api/devices" | python3 -m json.tool

# 4. 执行 WS 测试（替换 <TOKEN> 为实际 device_token）
python3 tools/test_device_online_ws.py \
  --base http://43.142.49.126:9000 \
  --token "<TOKEN>"
```

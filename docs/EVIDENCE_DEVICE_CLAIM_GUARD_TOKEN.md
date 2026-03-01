# 设备认领安全闸（Token 验证）— 交付证据

**部署地址**: http://43.142.49.126:9000
**验证时间**: 2026-02-12
**状态**: 已部署验证通过

---

## 一、方案说明

**方案 B — 认领时验证 device token**：
任何登录用户均可看到未绑定的在线设备，但认领时必须提供正确的 `DEVICE_INGEST_TOKEN`（硬件烧录的同一份 token）。

### 安全逻辑

| 情况 | 结果 |
|------|------|
| 认领时不提供 token | 401 |
| token 与服务器配置不符 | 403 |
| token 正确 + 设备未绑定 | 201，绑定成功 |
| 设备已绑定给当前用户 | 409 |
| 设备已绑定给他人 | 409 |

---

## 二、API 变更

### `POST /api/devices`

新增 `X-Device-Token` Header（或 body 字段 `device_token`）校验：

```bash
# Case 1: 无 token → 401
curl -s -X POST http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"esp32_token_test","name":""}' | python3 -m json.tool
```

**响应**:
```json
{"detail": "认领未绑定设备需提供设备 Token（Header: X-Device-Token 或 body.device_token）"}
```

```bash
# Case 2: 错误 token → 403
curl -s -X POST http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: wrong_token_123" \
  -d '{"device_id":"esp32_token_test","name":""}' | python3 -m json.tool
```

**响应**:
```json
{"detail": "设备 Token 错误，认领失败"}
```

```bash
# Case 3: 正确 token → 201
DEVICE_TOKEN="KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw"
curl -s -X POST http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: $DEVICE_TOKEN" \
  -d '{"device_id":"esp32_token_test","name":"Token 测试设备"}' | python3 -m json.tool
```

**响应**:
```json
{
  "id": 5,
  "device_id": "esp32_token_test",
  "user_id": 1,
  "name": "Token 测试设备",
  "is_online": false,
  "last_seen": "2026-02-12T06:48:12",
  "created_at": "2026-02-12T06:48:10"
}
```

---

## 三、Token 来源

服务器配置 `/opt/info-tech/deploy/.env`:
```
DEVICE_INGEST_TOKEN=KWOtrT...KZw  (前 6 后 3 打码)
```

设备端在固件烧录时配置同一份 token，WS 连接时以 `?device_token=...` 传入。
认领时前端从用户输入的密码框取值，以 `X-Device-Token` Header 发送。

---

## 四、前端交互

设备管理页"发现新设备"卡片现在包含：

1. 密码输入框 — "设备 Token（烧录时配置的 DEVICE_INGEST_TOKEN）"
2. 点击「认领」前校验输入框非空，非空后发送 `X-Device-Token: <token>` Header
3. 401/403 → 显示错误信息；201 → 刷新设备列表

---

## 五、完整复现步骤

```bash
# 1. 获取 token
TOKEN=$(curl -s -X POST http://43.142.49.126:9000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. 让设备上线（自动注册）
python3 -c "
import asyncio, websockets
async def t():
    async with websockets.connect(
        'ws://43.142.49.126:9000/ws/ingest/pcm?device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw&device_id=my_esp32&raw=1'
    ) as ws:
        await ws.send(b'\x00' * 3200)
        await asyncio.sleep(30)
asyncio.run(t())
" &

sleep 2

# 3. 无 token → 401
curl -s -X POST http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"device_id":"my_esp32"}'

# 4. 错误 token → 403
curl -s -X POST http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -H "X-Device-Token: bad_token" -d '{"device_id":"my_esp32"}'

# 5. 正确 token → 201
curl -s -X POST http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -H "X-Device-Token: KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw" \
  -d '{"device_id":"my_esp32","name":"我的设备"}'
```

---

## 六、一句话结论

认领未绑定设备现在需要提供与设备烧录 token 一致的 `X-Device-Token`，杜绝"任意用户抢认领"漏洞。

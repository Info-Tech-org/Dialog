# 设备自动创建 → 用户认领 → 在线状态刷新 闭环验证证据

**执行时间**: 2026-02-12  
**执行角色**: 测试工程师（仅测试与出证据，未改代码）  
**目标**: 验证“设备自动创建 → 用户认领 → 在线状态刷新”闭环在生产环境可用

---

## 1. 环境信息

| 项 | 值 |
|----|-----|
| BASE | http://43.142.49.126:9000 |
| WS 路径 | `ws://43.142.49.126:9000/ws/ingest/pcm?raw=1&device_id=esp32c6_001&device_token=<DEVICE_INGEST_TOKEN>` |
| device_token | `KWOtrT...KZw`（前 6 后 3 打码，全量见 deploy/.env） |
| 普通用户 | testuser_claim / test123 |
| Admin | admin / admin123 |

---

## 2. 测试步骤与输出

### S1 登录获取 JWT

**命令**:
```bash
# 普通用户登录
curl -sS -X POST "http://43.142.49.126:9000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser_claim","password":"test123"}'

# 保存 TOKEN（示例输出）
# {"access_token":"eyJ...","token_type":"bearer"}
```

**输出**（脱敏）:
```json
{"access_token":"eyJ...","token_type":"bearer"}
```

**TOKEN 已保存**，后续请求使用 `Authorization: Bearer <TOKEN>`。

---

### S2 确认当前用户设备列表

**命令**:
```bash
JWT="<上一步获取的 access_token>"
curl -sS -H "Authorization: Bearer $JWT" "http://43.142.49.126:9000/api/devices"
```

**输出**（连接 WS 前）:
```json
[]
```

**结论**: 普通用户设备列表为空，esp32c6_001 不存在。

---

### S3 WS 连接 30 秒 + 每 5 秒 4 字节心跳

**命令**（Python 脚本）:
```bash
cd /Users/max/info-tech
python3 tools/test_device_claim_flow.py --base http://43.142.49.126:9000 --token "KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw"
```

**或 wscat**（若已安装 `npm i -g wscat`）:
```bash
wscat -c "ws://43.142.49.126:9000/ws/ingest/pcm?raw=1&device_id=esp32c6_001&device_token=<TOKEN>"
# 连接后每 5 秒发送 4 字节二进制（wscat 需支持二进制发送）
```

**实际输出**:
```
[S3] WS 连接成功 @ 14:32:21
[S3] WS 30 秒结束，客户端主动关闭
```

---

### S4 连接期间每 3 秒 GET /api/devices

**观察**:

- **普通用户** GET /api/devices：始终无 esp32c6_001（接口只返回 `user_id=当前用户` 的设备，未绑定设备 `user_id=None` 不返回）。
- **Admin** GET /api/devices：**出现新设备** esp32c6_001。

**记录**（Admin 视角）:

| 轮询 | 时间 | admin_has | admin_user_id | admin_online | admin_last_seen |
|------|------|-----------|---------------|-------------|-----------------|
| 1 | 14:32:24 | ✓ | null | true | 2026-02-12T06:32:21 |
| 2–9 | ... | ✓ | null | true | 2026-02-12T06:32:21 |
| 10–12 | 14:32:54+ | ✓ | null | false | 2026-02-12T06:32:51 |

**结论**: 
- **device_id**: esp32c6_001
- **user_id**: null（未绑定）
- **is_online**: 连接时 true，断开后 false
- **last_seen**: 连接时刷新，断开后保持最后时间

---

### S5 认领/绑定

**路径**: `POST /api/devices`（从 /docs 或 openapi.json 确认）

**命令**:
```bash
curl -sS -X POST "http://43.142.49.126:9000/api/devices" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"esp32c6_001","name":"ESP32 认领测试"}'
```

**输出**:
```json
{
  "id": 4,
  "device_id": "esp32c6_001",
  "user_id": 3,
  "name": "ESP32 认领测试",
  "is_online": false,
  "last_seen": "2026-02-12T06:32:51.905906",
  "created_at": "2026-02-12T06:32:21.836842"
}
```

**结论**: 认领成功，user_id=3（当前普通用户）。

---

### S6 再次 GET /api/devices 验证

**命令**:
```bash
curl -sS -H "Authorization: Bearer $JWT" "http://43.142.49.126:9000/api/devices"
```

**输出**（认领后，WS 已断开）:
```json
[
  {
    "id": 4,
    "device_id": "esp32c6_001",
    "user_id": 3,
    "name": "ESP32 认领测试",
    "is_online": false,
    "last_seen": "2026-02-12T06:32:51.905906",
    "created_at": "2026-02-12T06:32:21.836842"
  }
]
```

**验证**:
- user_id 已变为当前用户（3）
- 认领时 WS 已断开，故 is_online=false
- last_seen 保持断开前时间

**在线状态刷新**（轮询 S4 已证明）:
- 连接中：is_online=true
- 断开后：is_online=false

---

## 3. 时间线表格

| 阶段 | 时间 | 普通用户 GET /api/devices | Admin GET /api/devices |
|------|------|---------------------------|------------------------|
| 连接前 | 14:32:21 前 | [] | [] 或 无 esp32c6_001 |
| 连接中 | 14:32:21–14:32:51 | []（不返回未绑定设备） | esp32c6_001, user_id=null, is_online=true |
| 断开后 | 14:32:54+ | [] | esp32c6_001, user_id=null, is_online=false |
| 认领后 | 14:33:01+ | esp32c6_001, user_id=3, is_online=false | 同左 |

---

## 4. 关键 JSON（脱敏）

**认领请求**:
```json
{"device_id":"esp32c6_001","name":"ESP32 认领测试"}
```

**认领响应**:
```json
{"id":4,"device_id":"esp32c6_001","user_id":3,"name":"ESP32 认领测试","is_online":false,"last_seen":"2026-02-12T06:32:51.905906","created_at":"2026-02-12T06:32:21.836842"}
```

---

## 5. 结论

| 结论项 | 结果 |
|--------|------|
| 设备自动创建 | **PASS**：WS 首次连接时自动创建设备记录（user_id=null） |
| 用户认领 | **PASS**：POST /api/devices 可认领未绑定设备 |
| 在线状态刷新 | **PASS**：连接时 is_online=true，断开后 is_online=false |
| 闭环 | **PASS** |

---

## 6. 若 FAIL 的最可能原因与复现命令

1. **device_token 错误**：鉴权失败，WS 连接被拒。检查 `DEVICE_INGEST_TOKEN`。
2. **设备已绑定**：若 esp32c6_001 已被其他用户绑定，认领返回 409。需 Admin 先解绑：`DELETE /api/devices/esp32c6_001`（需 Admin JWT）。
3. **普通用户看不到未绑定设备**：符合设计，GET /api/devices 仅返回当前用户设备；需用 Admin 账号观测自动创建。

**完整复现命令**:
```bash
# 1. 注册普通用户
curl -sS -X POST "http://43.142.49.126:9000/api/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser_claim","email":"testuser_claim@example.com","password":"test123"}'

# 2. 登录
JWT=$(curl -sS -X POST "http://43.142.49.126:9000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser_claim","password":"test123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

# 3. 执行闭环测试
python3 tools/test_device_claim_flow.py --base http://43.142.49.126:9000 --token "<DEVICE_INGEST_TOKEN>"
```

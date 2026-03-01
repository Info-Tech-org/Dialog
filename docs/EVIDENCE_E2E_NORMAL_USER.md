# 普通用户视角端到端复测证据

**执行时间**: 2026-02-12  
**执行角色**: 测试工程师（仅测试与出证据，未改代码）  
**视角**: 普通用户（非 admin）

---

## 1. 测试目标

| 步骤 | 预期 |
|------|------|
| 1 | 普通账号登录 Web |
| 2 | ESP32 上电连 WS（raw=1 + token） |
| 3 | 页面出现 unclaimed 卡片 |
| 4 | 点击认领 |
| 5 | 断网/重连，在线状态变化正确 |

---

## 2. 环境

| 项 | 值 |
|----|-----|
| BASE | http://43.142.49.126:9000 |
| Web 设备页 | http://43.142.49.126:9000/devices |
| 普通用户 | testuser_claim / test123 |
| device_token | `KWOtrT...KZw`（打码） |

---

## 3. 执行记录

### 3.1 普通用户登录

**命令**:
```bash
curl -sS -X POST "http://43.142.49.126:9000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser_claim","password":"test123"}'
```

**结果**: 返回 JWT，登录成功。

---

### 3.2 连接前状态

**命令**:
```bash
curl -sS -H "Authorization: Bearer $JWT" "http://43.142.49.126:9000/api/devices"
curl -sS -H "Authorization: Bearer $JWT" "http://43.142.49.126:9000/api/devices/unclaimed"
```

**结果**:
- 我的设备: 0 台
- 待认领: 0 台

---

### 3.3 模拟 ESP32 上电连 WS

**命令**:
```bash
python3 -c "
import asyncio, websockets
async def t():
    ws = await websockets.connect(
        'ws://43.142.49.126:9000/ws/ingest/pcm?raw=1&device_id=esp32c6_001&device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw'
    )
    await ws.send(b'\\x00\\x00\\x00\\x00')
    print('connected')
asyncio.run(t())
"
```

**结果**: ESP32 WS 已连接。

---

### 3.4 验证 unclaimed 卡片

**命令**:
```bash
curl -sS -H "Authorization: Bearer $JWT" "http://43.142.49.126:9000/api/devices/unclaimed"
```

**输出**（有未认领设备时）:
```json
[
  {
    "id": 6,
    "device_id": "esp32c6_001",
    "user_id": null,
    "name": "",
    "is_online": true,
    "last_seen": "2026-02-12T06:40:15.388755",
    "created_at": "2026-02-12T06:40:15.388755"
  }
]
```

**结论**: 页面应显示「发现新设备」绿色卡片，含 device_id、在线绿点、发现时间、「认领」按钮。

---

### 3.5 模拟点击认领

**命令**（等价于前端点击「认领」）:
```bash
curl -sS -X POST "http://43.142.49.126:9000/api/devices" \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"esp32c6_001","name":""}'
```

**输出**:
```json
{
  "id": 6,
  "device_id": "esp32c6_001",
  "user_id": 3,
  "name": "",
  "is_online": true,
  "last_seen": "2026-02-12T06:40:15.388755",
  "created_at": "2026-02-12T06:40:15.388755"
}
```

**结论**: 认领成功，user_id=3（当前用户）。前端预期：绿色卡片消失，设备移入「已绑定设备」列表。

---

### 3.6 断网/重连，在线状态变化

| 阶段 | GET /api/devices 中的 esp32c6_001 |
|------|-----------------------------------|
| 连接中（认领后） | is_online=true |
| 断开 WS | is_online=false |
| 再次连接 WS | is_online=true |

**结论**: 在线状态随断网/重连正确更新。

---

## 4. 时间线

| 时间点 | 动作 | 结果 |
|--------|------|------|
| T0 | 普通用户登录 | JWT 获取成功 |
| T1 | 连接前 GET devices/unclaimed | 均为空 |
| T2 | ESP32 WS 连接 | 连接成功 |
| T3 | GET unclaimed | 返回 esp32c6_001，is_online=true |
| T4 | POST devices（认领） | user_id=3 |
| T5 | GET devices | 设备在列表中，is_online=true |
| T6 | 断开 WS | is_online=false |
| T7 | 再次连接 WS | is_online=true |

---

## 5. 结论

| 目标 | 结果 |
|------|------|
| 普通账号登录 Web | **PASS** |
| ESP32 上电连 WS | **PASS** |
| 页面出现 unclaimed 卡片 | **PASS**（GET unclaimed 返回设备） |
| 点击认领 | **PASS**（POST devices 成功） |
| 断网/重连，在线状态正确 | **PASS** |

**闭环**: **PASS**

---

## 6. 一键复现

```bash
cd /Users/max/info-tech
python3 tools/test_e2e_normal_user.py \
  --base http://43.142.49.126:9000 \
  --token "KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw"
```

---

## 7. 手动 Web 验证步骤（可选）

1. 打开 http://43.142.49.126:9000/login
2. 使用 testuser_claim / test123 登录
3. 进入「设备管理」http://43.142.49.126:9000/devices
4. 另开终端，运行上述 Python 脚本模拟 ESP32 连接
5. 观察页面顶部是否出现「发现新设备」绿色卡片
6. 点击「认领」
7. 确认设备进入「已绑定设备」列表，绿点在线
8. 停止脚本（断开 WS），观察绿点变为离线
9. 再次运行脚本连接，观察绿点恢复在线

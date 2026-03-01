# 设备自动注册 — 交付证据

**部署地址**: http://43.142.49.126:9000
**验证时间**: 2026-02-12
**状态**: 已部署验证通过

---

## 一、问题

硬件 `device_id` 与 `devices` 表中注册的 `device_id` 不匹配时，`_set_device_online()` 静默跳过，设备永远显示离线。需要手动在前端绑定与硬件完全一致的 ID。

## 二、方案

**Option A — 自动注册**：WS 连接时若 `device_id` 不存在于 `devices` 表，自动创建记录（`user_id=NULL`，未绑定状态），用户可随后在设备管理页"认领"。

### 安全保障

- 自动注册只在 `device_token` 验证通过后触发（`_verify_ws_device_token()` 在 `_set_device_online()` 之前调用）
- 未绑定设备（`user_id=NULL`）的 session 不归属任何用户

---

## 三、变更文件

| 文件 | 变更 |
|------|------|
| `backend/models/device_model.py` | `user_id: int` → `Optional[int]` |
| `backend/models/db.py` | SQLite 迁移：重建 `devices` 表使 `user_id` 可空 |
| `backend/api/ws_ingest_routes.py` | `_set_device_online()` 在设备不存在且 `online=True` 时自动创建记录 |
| `backend/api/device_routes.py` | `DeviceResponse.user_id` → `Optional[int]`；admin 可见全部设备；`bind_device` 支持认领未绑定设备 |

---

## 四、迁移策略

SQLite 不支持 `ALTER COLUMN`，采用表重建：

```python
# db.py run_migrations()
CREATE TABLE devices_tmp (... user_id INTEGER ...)  -- 无 NOT NULL
INSERT INTO devices_tmp SELECT * FROM devices
DROP TABLE devices
ALTER TABLE devices_tmp RENAME TO devices
CREATE UNIQUE INDEX ...
CREATE INDEX ...
```

幂等：检查 `PRAGMA table_info` 的 `notnull` 标志，仅在 NOT NULL 时执行。

---

## 五、验证日志

### 迁移日志
```
2026-02-12 06:19:27 - models.db - INFO - Migration: made devices.user_id nullable
```

### 自动注册测试

```bash
# 连接一个全新 device_id
python3 -c "
import asyncio, websockets
async def test():
    uri = 'ws://43.142.49.126:9000/ws/ingest/pcm?device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw&device_id=test_autocreate_new&raw=1'
    async with websockets.connect(uri) as ws:
        await ws.send(b'\x00' * 3200)
        await asyncio.sleep(1)
asyncio.run(test())
"
```

**结果**：

| 阶段 | online | user_id | 说明 |
|------|--------|---------|------|
| BEFORE | 设备不存在 | — | devices 表中无此 ID |
| DURING | True | None | 自动创建，在线 |
| AFTER | False | None | 断开后离线，last_seen 更新 |

### 后端日志
```
[Device] Auto-created device record: test_autocreate_new
```

### 认领测试

```bash
# admin 认领未绑定设备
curl -X POST http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"test_autocreate_new","name":"测试自动设备"}'
```

**响应**:
```json
{
    "id": 4,
    "device_id": "test_autocreate_new",
    "user_id": 1,
    "name": "测试自动设备",
    "is_online": false,
    "last_seen": "2026-02-12T06:23:44.990414",
    "created_at": "2026-02-12T06:23:42.947591"
}
```

---

## 六、验证方法

```bash
# 1. 获取 token
TOKEN=$(curl -s -X POST http://43.142.49.126:9000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. 用新 device_id 连接 WS（触发自动注册）
python3 -c "
import asyncio, websockets
async def t():
    async with websockets.connect(
        'ws://43.142.49.126:9000/ws/ingest/pcm?device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw&device_id=NEW_ID&raw=1'
    ) as ws:
        await ws.send(b'\x00'*3200)
        await asyncio.sleep(1)
asyncio.run(t())
"

# 3. 查看设备列表（admin 可看全部含 user_id=null）
curl -s http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 4. 认领设备
curl -s -X POST http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"NEW_ID","name":"我的设备"}' | python3 -m json.tool
```

---

## 七、一句话结论

WS 连接时自动注册未知设备（`user_id=NULL`），用户可在设备管理页认领，彻底解决 device_id 不匹配导致的"永远离线"问题。

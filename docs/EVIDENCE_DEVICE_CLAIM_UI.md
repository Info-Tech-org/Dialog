# 设备发现与认领 UI — 交付证据

**部署地址**: http://43.142.49.126:9000/devices
**验证时间**: 2026-02-12
**状态**: 已部署验证通过

---

## 一、功能概述

**场景**：ESP32 设备首次联网后自动在 `devices` 表注册（`user_id=NULL`），用户无需提前知道 device_id，直接在 Web 端点击「认领」即可绑定。

### 交互流程

```
ESP32 上电联网
    ↓  WS connect → auto-create device (user_id=NULL, is_online=True)
/devices 页面（5s 轮询）
    ↓  GET /api/devices/unclaimed → 显示"发现新设备"区块（绿色边框）
用户点击【认领】
    ↓  POST /api/devices {device_id, name:""}
    ↓  bind_device：user_id=NULL → user_id=当前用户
结果：移入「已绑定设备」列表，实时在线
```

---

## 二、API 变更

### `GET /api/devices/unclaimed`（新增）

返回当前在线且 `user_id=NULL` 的设备列表，任意已登录用户可访问。

```bash
curl -s http://43.142.49.126:9000/api/devices/unclaimed \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

**响应**（有在线未绑定设备时）:
```json
[
  {
    "id": 5,
    "device_id": "esp32_new_kitchen",
    "user_id": null,
    "name": "",
    "is_online": true,
    "last_seen": "2026-02-12T06:35:27",
    "created_at": "2026-02-12T06:35:27"
  }
]
```

**响应**（无未绑定设备时）: `[]`

### `POST /api/devices`（已有，claim 路径）

传入已存在且 `user_id=NULL` 的 `device_id` 时，直接认领而非报错：

```bash
curl -s -X POST http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"esp32_new_kitchen","name":"厨房设备"}' | python3 -m json.tool
```

**响应**:
```json
{
  "id": 5,
  "device_id": "esp32_new_kitchen",
  "user_id": 1,
  "name": "厨房设备",
  "is_online": true,
  "last_seen": "2026-02-12T06:35:27",
  "created_at": "2026-02-12T06:35:27"
}
```

**权限**：
- `user_id=NULL` → 任意用户可认领
- `user_id=current_user` → 409"已绑定到你的账号"
- `user_id=other_user` → 409"已被其他用户绑定"

---

## 三、前端 UI

### 待认领区块（`device-unclaimed-card`）

- 绿色边框卡片，标题左侧显示设备数量徽章
- 仅当存在 `user_id=null && is_online=true` 的设备时显示
- 每条设备显示：在线绿点 + device_id + 发现时间 + 【认领】绿色按钮
- 点击认领 → loading 状态"认领中..." → 成功后区块消失，设备出现在"已绑定设备"列表

### 变更文件

| 文件 | 变更 |
|------|------|
| `frontend/src/pages/DeviceManage.jsx` | 新增 `unclaimed` 状态、`loadUnclaimed()`、`handleClaim()`、待认领区块渲染 |
| `frontend/src/index.css` | 新增 `.device-unclaimed-card`、`.device-unclaimed-badge`、`.device-item-unclaimed`、`.device-claim-btn` |

---

## 四、完整复现步骤

```bash
# 0. 获取 token
TOKEN=$(curl -s -X POST http://43.142.49.126:9000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 1. 模拟 ESP32 连接（触发自动注册）
python3 -c "
import asyncio, websockets
async def t():
    async with websockets.connect(
        'ws://43.142.49.126:9000/ws/ingest/pcm?device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw&device_id=MY_ESP32_ID&raw=1'
    ) as ws:
        await ws.send(b'\x00' * 3200)
        print('connected — keep alive 30s')
        await asyncio.sleep(30)
asyncio.run(t())
" &

sleep 2

# 2. 查看待认领设备
curl -s http://43.142.49.126:9000/api/devices/unclaimed \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
# 预期：[{"device_id":"MY_ESP32_ID","user_id":null,"is_online":true,...}]

# 3. 认领（等价于前端点击「认领」按钮）
curl -s -X POST http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device_id":"MY_ESP32_ID","name":"我的设备"}' | python3 -m json.tool
# 预期：{"user_id":1,"is_online":true,...}

# 4. 验证：认领后 unclaimed 为空
curl -s http://43.142.49.126:9000/api/devices/unclaimed \
  -H "Authorization: Bearer $TOKEN"
# 预期：[]

# 5. 验证：设备出现在我的列表
curl -s http://43.142.49.126:9000/api/devices \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys,json
for d in json.load(sys.stdin):
    print(d['device_id'], 'user_id='+str(d['user_id']), 'online='+str(d['is_online']))
"
# 预期：MY_ESP32_ID user_id=1 online=True
```

---

## 五、验证结果（实测）

```
=== 1. GET /api/devices/unclaimed ===
[{"device_id":"esp32_new_kitchen","user_id":null,"is_online":true,...}]

=== 2. POST /api/devices (认领) ===
{"device_id":"esp32_new_kitchen","user_id":1,"name":"厨房设备","is_online":true,...}

=== 3. GET /api/devices/unclaimed (认领后) ===
[]

=== 4. GET /api/devices (我的设备) ===
esp32_new_kitchen  user_id=1  online=True  name=厨房设备
```

---

## 六、UI 截图描述

打开 http://43.142.49.126:9000/devices 页面：

1. **有待认领设备时**：页面顶部（返回按钮下方）出现绿色边框卡片"**① 发现新设备**"，列出设备 ID、在线绿点、发现时间，右侧绿色「认领」按钮
2. **点击认领**：按钮变"认领中..."（disabled 状态），请求完成后绿色卡片消失
3. **认领完成后**："已绑定设备"列表出现该设备，绿点在线，显示绑定时间

---

## 七、一句话结论

设备上电即自动发现，用户在 `/devices` 页看到"发现新设备"区块后点击「认领」，device_id 无需手动输入，彻底消除硬件-数据库不匹配问题。

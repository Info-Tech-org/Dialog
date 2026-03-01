# BLE Device Binding Protocol Specification

**Status**: Draft v1.0  
**Date**: 2026-02-08  
**Target**: Info-tech ESP32-C6 Audio Recorder ↔ React Native App

---

## 1. Overview

通过 BLE (Bluetooth Low Energy) GATT 服务实现：
1. **设备发现** — App 扫描并识别 Info-tech 设备
2. **设备信息交换** — App 读取设备 ID、MAC、固件版本、设备令牌
3. **用户绑定/解绑** — App 写入用户凭证完成绑定，建立"用户-设备"关联
4. **WiFi 配网** — App 通过 BLE 下发 WiFi 凭证，设备自动连接
5. **状态通知** — 绑定状态和 WiFi 状态变更时主动推送到 App

### 技术要求
- BLE 5.0 (ESP32-C6 原生支持)
- GATT Server 运行于设备端
- GATT Client 运行于 React Native App
- MTU ≥ 256 bytes (NimBLE 默认)
- 数据格式：UTF-8 JSON

---

## 2. BLE Advertising

| 参数 | 值 |
|---|---|
| Device Name | `IT-XXXX` (XXXX = BT MAC 后两字节 HEX) |
| Service UUID | `4e490001-b5a3-f393-e0a9-e50e24dcca9e` |
| Scan Response | Enabled |
| Connectable | Yes |

### App 端扫描过滤规则
```
serviceUUIDs: ["4e490001-b5a3-f393-e0a9-e50e24dcca9e"]
```
仅展示包含此 Service UUID 的设备。设备名 `IT-XXXX` 用于 UI 显示。

---

## 3. GATT Service Definition

### Service UUID
```
4e490001-b5a3-f393-e0a9-e50e24dcca9e
```

### Characteristics

| # | UUID | Name | Properties | Description |
|---|------|------|-----------|-------------|
| 1 | `4e490002-...9e` | Device Info | **Read** | 设备基本信息 |
| 2 | `4e490003-...9e` | Bind Command | **Write** | 绑定/解绑命令 |
| 3 | `4e490004-...9e` | Bind Status | **Read, Notify** | 绑定状态 |
| 4 | `4e490005-...9e` | WiFi Config | **Write** | WiFi 配网参数 |
| 5 | `4e490006-...9e` | WiFi Status | **Read, Notify** | WiFi 连接状态 |

> 完整 UUID 格式：`4e4900XX-b5a3-f393-e0a9-e50e24dcca9e`，XX 为特征序号。

---

## 4. Characteristic Data Formats

### 4.1 Device Info (Read) — `0x4E490002`

App 连接后首先读取此特征，获取设备基本信息。

**Response JSON:**
```json
{
  "device_id": "esp32",
  "device_token": "KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw",
  "fw_version": "1.0.0",
  "mac": "aa:bb:cc:dd:ee:ff",
  "ble_name": "IT-EEFF"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `device_id` | string | 设备唯一标识，用于后端 API |
| `device_token` | string | 设备认证令牌 (⚠️ 敏感，仅绑定时使用) |
| `fw_version` | string | 固件版本号 (semver) |
| `mac` | string | BLE MAC 地址 |
| `ble_name` | string | BLE 广播名称 |

---

### 4.2 Bind Command (Write) — `0x4E490003`

App 写入此特征执行绑定/解绑/查询操作。

#### 4.2.1 Bind (绑定)

**Request JSON:**
```json
{
  "cmd": "bind",
  "user_id": "user_abc123",
  "user_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `cmd` | string | ✅ | 固定值 `"bind"` |
| `user_id` | string | ✅ | App 用户唯一 ID |
| `user_token` | string | ❌ | App 用户令牌 (可选，用于后端验证) |

**设备行为:**
1. 存储 `user_id` 和 `user_token` 到 NVS (Flash)
2. 设置 `bound = true`
3. 通过 Bind Status 特征 Notify 更新状态

#### 4.2.2 Unbind (解绑)

**Request JSON:**
```json
{
  "cmd": "unbind"
}
```

**设备行为:**
1. 清除 NVS 中的绑定信息
2. 设置 `bound = false`
3. 通过 Bind Status 特征 Notify 更新状态

#### 4.2.3 Query (查询状态)

**Request JSON:**
```json
{
  "cmd": "query"
}
```

**设备行为:** 通过 Bind Status 特征 Notify 返回当前绑定状态。

---

### 4.3 Bind Status (Read/Notify) — `0x4E490004`

**Response JSON (已绑定):**
```json
{
  "bound": true,
  "user_id": "user_abc123",
  "bind_time": 12345
}
```

**Response JSON (未绑定):**
```json
{
  "bound": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `bound` | boolean | 是否已绑定用户 |
| `user_id` | string | 已绑定的用户 ID (仅 bound=true) |
| `bind_time` | number | 绑定时间戳 (设备运行秒数，仅 bound=true) |

**Notify 触发时机:** 绑定、解绑、查询命令执行后。

---

### 4.4 WiFi Config (Write) — `0x4E490005`

App 写入 WiFi 连接参数，设备自动尝试连接。

**Request JSON:**
```json
{
  "ssid": "MyHomeWiFi",
  "password": "password123"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ssid` | string | ✅ | WiFi 网络名称 |
| `password` | string | ✅ | WiFi 密码 |

**设备行为:**
1. 断开当前 WiFi
2. 使用新参数尝试连接
3. 通过 WiFi Status 特征 Notify 报告结果

---

### 4.5 WiFi Status (Read/Notify) — `0x4E490006`

**Response JSON (已连接):**
```json
{
  "connected": true,
  "ssid": "MyHomeWiFi",
  "ip": "192.168.1.100",
  "rssi": -50
}
```

**Response JSON (未连接):**
```json
{
  "connected": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `connected` | boolean | WiFi 是否已连接 |
| `ssid` | string | 当前连接的 SSID (仅 connected=true) |
| `ip` | string | IPv4 地址 (仅 connected=true) |
| `rssi` | number | 信号强度 dBm (仅 connected=true) |

**Notify 触发时机:** WiFi 连接状态变化时、BLE 配网完成后。

---

## 5. React Native App 标准

### 5.1 推荐技术栈

| 组件 | 推荐 | 版本 |
|------|------|------|
| BLE 库 | `react-native-ble-plx` | ^3.x |
| 状态管理 | React Hooks / Zustand | - |
| 类型系统 | TypeScript (strict) | ^5.x |
| 平台 | iOS 14+ / Android 10+ | - |

### 5.2 权限要求

**Android (AndroidManifest.xml):**
```xml
<uses-permission android:name="android.permission.BLUETOOTH_SCAN" />
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<!-- Android 11 以下额外需要 -->
<uses-permission android:name="android.permission.BLUETOOTH" />
<uses-permission android:name="android.permission.BLUETOOTH_ADMIN" />
```

**iOS (Info.plist):**
```xml
<key>NSBluetoothAlwaysUsageDescription</key>
<string>需要蓝牙权限来连接和配置您的设备</string>
<key>NSBluetoothPeripheralUsageDescription</key>
<string>需要蓝牙权限来连接和配置您的设备</string>
```

### 5.3 连接流程标准

```
┌─────────────┐     ┌──────────────┐
│  React App  │     │  ESP32 BLE   │
└──────┬──────┘     └──────┬───────┘
       │  1. Scan (filter by SVC UUID)  │
       │───────────────────────────────>│
       │  2. Found "IT-XXXX"            │
       │<───────────────────────────────│
       │  3. Connect                    │
       │───────────────────────────────>│
       │  4. Discover Services          │
       │───────────────────────────────>│
       │  5. Read Device Info           │
       │───────────────────────────────>│
       │  6. {device_id, mac, ...}      │
       │<───────────────────────────────│
       │  7. Subscribe Bind Status      │
       │───────────────────────────────>│
       │  8. Subscribe WiFi Status      │
       │───────────────────────────────>│
       │  9. Write Bind Cmd (bind)      │
       │───────────────────────────────>│
       │  10. Notify: {bound:true,...}  │
       │<───────────────────────────────│
       │  11. Write WiFi Config         │
       │───────────────────────────────>│
       │  12. Notify: {connected:true}  │
       │<───────────────────────────────│
       │  13. Disconnect BLE            │
       │───────────────────────────────>│
       ▼                                ▼
```

### 5.4 超时与重试标准

| 操作 | 超时 | 重试 |
|------|------|------|
| BLE Scan | 10s | 用户手动重试 |
| BLE Connect | 5s | 最多 2 次 |
| Service Discovery | 5s | 1 次 |
| Read Characteristic | 3s | 1 次 |
| Write Characteristic | 3s | 最多 2 次 |
| WiFi 连接等待 Notify | 15s | - |

### 5.5 错误处理标准

| 错误类型 | 处理方式 |
|----------|----------|
| BLE Not Enabled | 提示用户开启蓝牙 |
| Permission Denied | 引导用户授权 |
| Device Not Found | 提示检查设备电源和距离 |
| Connection Failed | 自动重试 1 次，仍失败则提示 |
| Write Failed | 提示重试 |
| WiFi Connect Failed | 提示检查 SSID/密码 |
| Bind Already Exists | 显示已绑定用户，提供解绑选项 |

### 5.6 数据校验标准

App 端必须校验：
1. `device_id` 非空
2. `mac` 符合 `XX:XX:XX:XX:XX:XX` 格式
3. `fw_version` 符合 semver
4. `bound` 为 boolean
5. 写入的 `user_id` 长度 ≤ 63 字符
6. 写入的 `ssid` 长度 ≤ 32 字符

---

## 6. NVS 持久化

设备端使用 ESP32 NVS (Non-Volatile Storage) 持久化绑定信息：

| NVS Namespace | Key | Type | Description |
|---------------|-----|------|-------------|
| `ble_bind` | `bound` | bool | 是否已绑定 |
| `ble_bind` | `userId` | string | 绑定的用户 ID |
| `ble_bind` | `userTok` | string | 用户令牌 |
| `ble_bind` | `bindTs` | uint32 | 绑定时间戳 |

设备重启后自动恢复绑定状态。

---

## 7. 安全说明

| 风险 | 缓解措施 |
|------|----------|
| BLE 信号可被嗅探 | BLE 配对/绑定仅需物理接近 (< 10m) |
| device_token 通过 BLE 传输 | 仅在首次绑定时读取，不持续暴露 |
| 未授权解绑 | 生产环境可增加 PIN / 后端确认 |
| 中间人攻击 | 生产环境建议启用 BLE Secure Connection (LE SC) |

---

## 8. 后端集成建议

绑定完成后，App 应调用后端 API 注册设备关联：

```
POST /api/devices/bind
Content-Type: application/json
Authorization: Bearer <user_token>

{
  "device_id": "esp32",
  "device_token": "KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw",
  "user_id": "user_abc123"
}
```

后端响应：
```json
{
  "ok": true,
  "device_id": "esp32",
  "bound_at": "2026-02-08T12:00:00Z"
}
```

---

## 9. Changelog

- v1.0 (2026-02-08) — Initial protocol specification

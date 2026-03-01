# App 端 BLE 设备绑定对接方案

> **版本**: v1.0 | **日期**: 2026-02-09 | **硬件**: Seeed XIAO ESP32-C6 | **固件版本**: 1.0.0

---

## 一、功能概述

App 通过 **BLE (低功耗蓝牙)** 与 Info-tech 音频采集设备完成以下交互：

| 功能 | 说明 |
|------|------|
| 🔍 设备发现 | 扫描附近的 Info-tech 设备 |
| 📋 设备信息读取 | 获取 device_id、device_token、MAC、固件版本 |
| 🤝 用户绑定 | 将 App 用户与设备关联（设备侧持久化存储） |
| 🔓 用户解绑 | 解除用户与设备的关联 |
| 📶 WiFi 配网 | 通过 BLE 向设备下发 WiFi SSID/密码 |
| 📡 状态订阅 | 实时接收绑定状态、WiFi 连接状态变更通知 |

---

## 二、技术规格

| 项目 | 值 |
|------|-----|
| BLE 版本 | 5.0 (ESP32-C6) |
| 传输层 | GATT Server (设备端) ↔ GATT Client (App 端) |
| 数据编码 | UTF-8 JSON |
| MTU | ≥ 256 bytes（建议连接后协商 MTU） |
| 推荐 BLE 库 | `react-native-ble-plx` ≥ 3.x |

### 平台最低版本

| 平台 | 版本 |
|------|------|
| Android | 10 (API 29) |
| iOS | 14.0 |

---

## 三、BLE 设备广播信息

| 参数 | 值 | 说明 |
|------|----|------|
| 设备名称 | `IT-XXXX` | XXXX = BLE MAC 后 2 字节 HEX（如 `IT-A3F7`）|
| Service UUID | `4e490001-b5a3-f393-e0a9-e50e24dcca9e` | 扫描过滤条件 |
| 是否可连接 | 是 | |
| Scan Response | 开启 | |

### App 扫描过滤

**只**展示广播中包含 Service UUID `4e490001-b5a3-f393-e0a9-e50e24dcca9e` 的设备。

```typescript
// react-native-ble-plx 示例
manager.startDeviceScan(
  ['4e490001-b5a3-f393-e0a9-e50e24dcca9e'],  // serviceUUIDs 过滤
  { allowDuplicates: false },
  (error, device) => { /* ... */ }
);
```

---

## 四、GATT 服务与特征定义

### Service UUID

```
4e490001-b5a3-f393-e0a9-e50e24dcca9e
```

### 特征列表（5 个）

| # | 名称 | UUID | 属性 | 数据方向 |
|---|------|------|------|----------|
| 1 | Device Info | `4e490002-b5a3-f393-e0a9-e50e24dcca9e` | **Read** | 设备 → App |
| 2 | Bind Command | `4e490003-b5a3-f393-e0a9-e50e24dcca9e` | **Write** | App → 设备 |
| 3 | Bind Status | `4e490004-b5a3-f393-e0a9-e50e24dcca9e` | **Read, Notify** | 设备 → App |
| 4 | WiFi Config | `4e490005-b5a3-f393-e0a9-e50e24dcca9e` | **Write** | App → 设备 |
| 5 | WiFi Status | `4e490006-b5a3-f393-e0a9-e50e24dcca9e` | **Read, Notify** | 设备 → App |

---

## 五、各特征详细数据格式

### 5.1 Device Info — 读取设备信息

- **UUID**: `4e490002-b5a3-f393-e0a9-e50e24dcca9e`
- **操作**: Read
- **时机**: 连接成功并发现服务后，**第一步**读取

**返回 JSON：**

```json
{
  "device_id": "esp32",
  "device_token": "KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw",
  "fw_version": "1.0.0",
  "mac": "aa:bb:cc:dd:ee:ff",
  "ble_name": "IT-EEFF"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `device_id` | string | 设备唯一标识，**后端 API 使用此值** |
| `device_token` | string | 设备令牌，**⚠️ 敏感信息**，用于后端注册绑定关系 |
| `fw_version` | string | 固件版本 (semver) |
| `mac` | string | BLE MAC 地址 |
| `ble_name` | string | BLE 广播名称 |

**App 端校验要求：**
- `device_id` 非空
- `fw_version` 符合 `x.y.z` 格式

---

### 5.2 Bind Command — 绑定/解绑/查询

- **UUID**: `4e490003-b5a3-f393-e0a9-e50e24dcca9e`
- **操作**: Write (with response)
- **时机**: 用户确认绑定/解绑时写入

#### 5.2.1 绑定

写入 JSON：

```json
{
  "cmd": "bind",
  "user_id": "user_abc123",
  "user_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `cmd` | string | ✅ | 固定 `"bind"` |
| `user_id` | string | ✅ | App 当前登录用户的唯一 ID，**长度 ≤ 63 字符** |
| `user_token` | string | ❌ | 用户令牌（可选，预留给后端验证） |

**设备行为：**
1. 将 `user_id`、`user_token` 存入 NVS Flash（**重启不丢失**）
2. 通过 Bind Status 特征发出 Notify

#### 5.2.2 解绑

```json
{
  "cmd": "unbind"
}
```

**设备行为：** 清除 NVS 中绑定数据 → 发出 Notify `{"bound": false}`

#### 5.2.3 查询

```json
{
  "cmd": "query"
}
```

**设备行为：** 立即通过 Bind Status 特征发出当前绑定状态的 Notify

---

### 5.3 Bind Status — 绑定状态

- **UUID**: `4e490004-b5a3-f393-e0a9-e50e24dcca9e`
- **操作**: Read / Notify
- **时机**: 连接后订阅 Notify；或主动 Read

**已绑定时：**

```json
{
  "bound": true,
  "user_id": "user_abc123",
  "bind_time": 12345
}
```

**未绑定时：**

```json
{
  "bound": false
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `bound` | boolean | 是否已绑定 |
| `user_id` | string | 已绑定的用户 ID（仅 bound=true） |
| `bind_time` | number | 绑定时设备运行秒数（仅 bound=true） |

**Notify 触发条件：** bind / unbind / query 命令执行后。

---

### 5.4 WiFi Config — WiFi 配网

- **UUID**: `4e490005-b5a3-f393-e0a9-e50e24dcca9e`
- **操作**: Write (with response)
- **时机**: 用户输入 WiFi 信息后写入

写入 JSON：

```json
{
  "ssid": "MyHomeWiFi",
  "password": "mypassword123"
}
```

| 字段 | 类型 | 必填 | 约束 |
|------|------|------|------|
| `ssid` | string | ✅ | **长度 ≤ 32 字符**，非空 |
| `password` | string | ✅ | WiFi 密码 |

**设备行为：**
1. 断开当前 WiFi
2. 使用新 SSID/密码尝试连接（最长约 10 秒）
3. 通过 WiFi Status 特征发出连接结果 Notify

---

### 5.5 WiFi Status — WiFi 连接状态

- **UUID**: `4e490006-b5a3-f393-e0a9-e50e24dcca9e`
- **操作**: Read / Notify
- **时机**: 连接后订阅 Notify；或主动 Read

**已连接时：**

```json
{
  "connected": true,
  "ssid": "MyHomeWiFi",
  "ip": "192.168.1.105",
  "rssi": -45
}
```

**未连接时：**

```json
{
  "connected": false
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `connected` | boolean | WiFi 是否已连接 |
| `ssid` | string | 连接的网络名称（仅 connected=true） |
| `ip` | string | IPv4 地址（仅 connected=true） |
| `rssi` | number | 信号强度 dBm（仅 connected=true） |

**Notify 触发条件：** WiFi 配网完成后、WiFi 断线重连后。

---

## 六、标准对接流程

### 6.1 完整时序图

```
    App (GATT Client)                    设备 (GATT Server)
    ─────────────────                    ──────────────────
          │                                     │
    ① ──▶│  BLE Scan (filter by SVC UUID)      │
          │─────────────────────────────────────▶│
          │     Advertising: "IT-A3F7"          │
          │◀─────────────────────────────────────│
          │                                     │
    ② ──▶│  Connect + Request MTU 256          │
          │─────────────────────────────────────▶│
          │     Connected                       │
          │◀─────────────────────────────────────│
          │                                     │
    ③ ──▶│  Discover Services                  │
          │─────────────────────────────────────▶│
          │     Service 4e490001-...            │
          │◀─────────────────────────────────────│
          │                                     │
    ④ ──▶│  Read Device Info (0002)            │
          │─────────────────────────────────────▶│
          │     {"device_id":"esp32",...}        │
          │◀─────────────────────────────────────│
          │                                     │
    ⑤ ──▶│  Subscribe Bind Status (0004)       │
          │─────────────────────────────────────▶│
    ⑥ ──▶│  Subscribe WiFi Status (0006)       │
          │─────────────────────────────────────▶│
          │                                     │
    ⑦ ──▶│  Read Bind Status (0004)            │
          │─────────────────────────────────────▶│
          │     {"bound":false}                 │
          │◀─────────────────────────────────────│
          │                                     │
    ⑧ ──▶│  Write Bind Cmd: bind (0003)        │
          │  {"cmd":"bind","user_id":"u123"}     │
          │─────────────────────────────────────▶│
          │     Notify: {"bound":true,...}       │  ← 设备存入 NVS
          │◀─────────────────────────────────────│
          │                                     │
    ⑨ ──▶│  Write WiFi Config (0005)           │
          │  {"ssid":"WiFi","password":"xxx"}    │
          │─────────────────────────────────────▶│
          │     ... 设备连接 WiFi (5~10s) ...    │
          │     Notify: {"connected":true,...}   │
          │◀─────────────────────────────────────│
          │                                     │
    ⑩ ──▶│  App → 后端 API: 注册绑定关系        │
          │                                     │
    ⑪ ──▶│  Disconnect BLE                     │
          │─────────────────────────────────────▶│
          │     设备恢复广播                      │
```

### 6.2 步骤详解

| 步骤 | 操作 | 超时 | 失败处理 |
|------|------|------|----------|
| ① 扫描 | `startDeviceScan([SVC_UUID])` | 10s | 提示用户检查设备电源 |
| ② 连接 | `connectToDevice(id, {requestMTU:256})` | 5s | 重试 1 次 |
| ③ 发现服务 | `discoverAllServicesAndCharacteristics()` | 5s | 断开重连 |
| ④ 读取设备信息 | Read `0x0002` | 3s | 断开重连 |
| ⑤⑥ 订阅通知 | Monitor `0x0004` + `0x0006` | - | - |
| ⑦ 读取绑定状态 | Read `0x0004` | 3s | 忽略，使用默认 |
| ⑧ 发送绑定 | Write `0x0003` → 等待 Notify | 5s | 提示重试 |
| ⑨ WiFi 配网 | Write `0x0005` → 等待 Notify | **15s** | 提示检查密码 |
| ⑩ 后端注册 | HTTP POST 后端 API | 10s | 本地标记，后续重试 |
| ⑪ 断开 | `cancelConnection()` | - | - |

---

## 七、BLE 数据读写注意事项

### 7.1 Base64 编码

`react-native-ble-plx` 的特征值以 **Base64** 格式传输。App 侧需要：

```typescript
import { Buffer } from 'buffer';

// 读取时：Base64 → UTF-8 string → JSON.parse
function decodeCharValue(base64Value: string): any {
  const utf8 = Buffer.from(base64Value, 'base64').toString('utf-8');
  return JSON.parse(utf8);
}

// 写入时：JSON → UTF-8 string → Base64
function encodeCharValue(obj: object): string {
  const json = JSON.stringify(obj);
  return Buffer.from(json, 'utf-8').toString('base64');
}
```

### 7.2 Write 方式

所有写操作使用 **Write With Response**（等待设备确认）：

```typescript
await device.writeCharacteristicWithResponseForService(
  SERVICE_UUID,
  CHAR_UUID,
  base64Value
);
```

### 7.3 Notify 订阅

```typescript
const subscription = device.monitorCharacteristicForService(
  SERVICE_UUID,
  CHAR_UUID,
  (error, characteristic) => {
    if (characteristic?.value) {
      const data = decodeCharValue(characteristic.value);
      // 处理通知数据...
    }
  }
);

// 不再需要时取消订阅
subscription.remove();
```

---

## 八、App 权限配置

### Android — AndroidManifest.xml

```xml
<!-- Android 12+ (API 31+) -->
<uses-permission android:name="android.permission.BLUETOOTH_SCAN" />
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />

<!-- Android 11 及以下兼容 -->
<uses-permission android:name="android.permission.BLUETOOTH" />
<uses-permission android:name="android.permission.BLUETOOTH_ADMIN" />
```

**运行时权限请求（Android 12+）：**

```typescript
import { PermissionsAndroid, Platform } from 'react-native';

async function requestBLEPermissions(): Promise<boolean> {
  if (Platform.OS !== 'android') return true;

  if (Platform.Version >= 31) {
    const results = await PermissionsAndroid.requestMultiple([
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_SCAN,
      PermissionsAndroid.PERMISSIONS.BLUETOOTH_CONNECT,
      PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION,
    ]);
    return Object.values(results).every(
      r => r === PermissionsAndroid.RESULTS.GRANTED
    );
  } else {
    const result = await PermissionsAndroid.request(
      PermissionsAndroid.PERMISSIONS.ACCESS_FINE_LOCATION
    );
    return result === PermissionsAndroid.RESULTS.GRANTED;
  }
}
```

### iOS — Info.plist

```xml
<key>NSBluetoothAlwaysUsageDescription</key>
<string>需要蓝牙权限来连接和配置您的设备</string>
<key>NSBluetoothPeripheralUsageDescription</key>
<string>需要蓝牙权限来连接和配置您的设备</string>
```

---

## 九、常量速查表

App 端直接复制使用：

```typescript
// ====== BLE UUIDs ======
const BLE_SERVICE_UUID     = '4e490001-b5a3-f393-e0a9-e50e24dcca9e';
const CHAR_DEVICE_INFO     = '4e490002-b5a3-f393-e0a9-e50e24dcca9e'; // Read
const CHAR_BIND_COMMAND    = '4e490003-b5a3-f393-e0a9-e50e24dcca9e'; // Write
const CHAR_BIND_STATUS     = '4e490004-b5a3-f393-e0a9-e50e24dcca9e'; // Read + Notify
const CHAR_WIFI_CONFIG     = '4e490005-b5a3-f393-e0a9-e50e24dcca9e'; // Write
const CHAR_WIFI_STATUS     = '4e490006-b5a3-f393-e0a9-e50e24dcca9e'; // Read + Notify

// ====== TypeScript 接口 ======

interface DeviceInfo {
  device_id: string;
  device_token: string;
  fw_version: string;
  mac: string;
  ble_name: string;
}

interface BindStatus {
  bound: boolean;
  user_id?: string;
  bind_time?: number;
}

interface WiFiStatus {
  connected: boolean;
  ssid?: string;
  ip?: string;
  rssi?: number;
}
```

---

## 十、完整代码示例

### 10.1 最小可运行示例

```typescript
import { BleManager } from 'react-native-ble-plx';
import { Buffer } from 'buffer';

const SVC  = '4e490001-b5a3-f393-e0a9-e50e24dcca9e';
const INFO = '4e490002-b5a3-f393-e0a9-e50e24dcca9e';
const BIND = '4e490003-b5a3-f393-e0a9-e50e24dcca9e';
const BSTS = '4e490004-b5a3-f393-e0a9-e50e24dcca9e';
const WCFG = '4e490005-b5a3-f393-e0a9-e50e24dcca9e';
const WSTS = '4e490006-b5a3-f393-e0a9-e50e24dcca9e';

const decode = (b64: string) => JSON.parse(Buffer.from(b64, 'base64').toString('utf-8'));
const encode = (obj: object) => Buffer.from(JSON.stringify(obj), 'utf-8').toString('base64');

async function bindDevice(userId: string, wifiSSID: string, wifiPass: string) {
  const mgr = new BleManager();

  // 1. 扫描
  const device = await new Promise<any>((resolve, reject) => {
    const timer = setTimeout(() => { mgr.stopDeviceScan(); reject('Scan timeout'); }, 10000);
    mgr.startDeviceScan([SVC], {}, (err, dev) => {
      if (dev) { clearTimeout(timer); mgr.stopDeviceScan(); resolve(dev); }
    });
  });
  console.log('Found:', device.name);

  // 2. 连接
  const connected = await mgr.connectToDevice(device.id, { requestMTU: 256 });
  await connected.discoverAllServicesAndCharacteristics();

  // 3. 读取设备信息
  const infoChar = await connected.readCharacteristicForService(SVC, INFO);
  const deviceInfo = decode(infoChar.value!);
  console.log('Device:', deviceInfo.device_id, 'FW:', deviceInfo.fw_version);

  // 4. 订阅绑定状态通知
  const bindResult = await new Promise<any>((resolve, reject) => {
    const timer = setTimeout(() => reject('Bind timeout'), 5000);
    connected.monitorCharacteristicForService(SVC, BSTS, (err, char) => {
      if (char?.value) {
        clearTimeout(timer);
        resolve(decode(char.value));
      }
    });
    // 发送绑定命令
    connected.writeCharacteristicWithResponseForService(
      SVC, BIND, encode({ cmd: 'bind', user_id: userId })
    );
  });
  console.log('Bind result:', bindResult);

  // 5. 配网
  const wifiResult = await new Promise<any>((resolve, reject) => {
    const timer = setTimeout(() => reject('WiFi timeout'), 15000);
    connected.monitorCharacteristicForService(SVC, WSTS, (err, char) => {
      if (char?.value) {
        clearTimeout(timer);
        resolve(decode(char.value));
      }
    });
    connected.writeCharacteristicWithResponseForService(
      SVC, WCFG, encode({ ssid: wifiSSID, password: wifiPass })
    );
  });
  console.log('WiFi:', wifiResult);

  // 6. 完成，断开 BLE
  await connected.cancelConnection();

  // 7. 调用后端注册绑定关系
  // await fetch('/api/devices/bind', { ... });

  return { deviceInfo, bindResult, wifiResult };
}
```

### 10.2 解绑示例

```typescript
// 前提：已建立 BLE 连接
async function unbindDevice(connected: any) {
  const result = await new Promise<any>((resolve, reject) => {
    const timer = setTimeout(() => reject('Unbind timeout'), 5000);
    connected.monitorCharacteristicForService(SVC, BSTS, (err, char) => {
      if (char?.value) {
        clearTimeout(timer);
        resolve(decode(char.value));
      }
    });
    connected.writeCharacteristicWithResponseForService(
      SVC, BIND, encode({ cmd: 'unbind' })
    );
  });
  console.log('Unbind result:', result); // {"bound": false}
}
```

---

## 十一、错误处理规范

| 场景 | App 行为 |
|------|----------|
| 蓝牙未开启 | 弹窗提示「请开启蓝牙」 |
| 权限被拒绝 | 引导至系统设置页 |
| 扫描超时无设备 | 提示「未发现设备，请确认设备已开机且在附近」 |
| 连接失败 | 自动重试 1 次，仍失败提示「连接失败，请靠近设备重试」 |
| 绑定写入失败 | 提示「操作失败，请重试」 |
| 设备已被其他用户绑定 | 读取 Bind Status 发现 bound=true 且 user_id 非当前用户 → 提示「设备已被绑定，需先解绑」 |
| WiFi 配网超时 | 提示「WiFi 连接超时，请检查网络名称和密码」 |
| WiFi 配网返回 connected=false | 提示「WiFi 连接失败」 |
| BLE 意外断开 | 清理订阅，提示用户重新操作 |

---

## 十二、后端注册绑定（建议）

BLE 绑定成功后，App **应**调用后端 API 同步绑定关系：

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

这样后端也能维护「用户-设备」映射，后续录音数据自动归属到用户。

---

## 十三、依赖安装

```bash
npm install react-native-ble-plx buffer

# iOS 额外
cd ios && pod install
```

---

## 十四、调试建议

1. **iOS 模拟器不支持 BLE** — 必须使用真机
2. **Android 模拟器** — 需要宿主机有蓝牙适配器并做透传，建议使用真机
3. **设备串口调试** — 用 USB 连接设备，打开串口终端 (115200 baud)：
   - 输入 `ble` 查看 BLE 状态和绑定信息
   - 输入 `w` 查看 WiFi 状态
   - 输入 `help` 查看全部命令
4. **nRF Connect App** — 推荐用 Nordic 的 nRF Connect (iOS/Android) 验证 BLE 通信，无需写代码即可读写特征

---

## 十五、FAQ

**Q: 设备重启后绑定信息还在吗？**
A: 在。绑定数据存储在 ESP32 的 NVS Flash 中，掉电不丢失。

**Q: 一个设备能绑定多个用户吗？**
A: 当前设计为 **一对一**。新的 bind 命令会覆盖旧的绑定。

**Q: BLE 连接距离多远？**
A: 典型室内 5~10 米。配对/绑定操作建议在 3 米以内进行。

**Q: WiFi 配网需要多久？**
A: 通常 3~10 秒。App 侧超时设为 15 秒。

**Q: 可以不配网只绑定吗？**
A: 可以。绑定和配网是独立操作。但设备需要 WiFi 才能上传音频数据。

**Q: device_token 是什么？安全吗？**
A: 是设备访问后端 API 的认证凭证。通过 BLE 传输要求物理接近，风险可控。生产环境可增加 BLE 配对 PIN。

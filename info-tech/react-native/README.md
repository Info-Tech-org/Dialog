# React Native BLE 设备绑定模块

Info-tech ESP32-C6 音频设备的 BLE 蓝牙连接与用户绑定模块。

## 功能

- 🔍 **扫描设备** — 自动发现附近的 Info-tech 设备（按 Service UUID 过滤）
- 🔗 **BLE 连接** — 一键连接设备，自动发现服务和特征
- 📱 **设备信息** — 读取设备 ID、MAC、固件版本、设备令牌
- 🤝 **用户绑定** — 将设备与 App 用户账户关联（持久化到设备 NVS Flash）
- 📶 **WiFi 配网** — 通过 BLE 下发 WiFi 凭证，免手动配置
- 🔔 **状态通知** — 实时接收绑定状态和 WiFi 连接状态变更

## 安装依赖

```bash
# BLE 通信库
npm install react-native-ble-plx

# Base64 编解码 (BLE 数据传输使用 base64)
npm install buffer

# iOS: 安装 CocoaPods 依赖
cd ios && pod install && cd ..
```

## 平台配置

### Android

在 `android/app/src/main/AndroidManifest.xml` 中添加权限：

```xml
<manifest>
  <!-- BLE 权限 (Android 12+) -->
  <uses-permission android:name="android.permission.BLUETOOTH_SCAN" />
  <uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />
  <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />

  <!-- BLE 权限 (Android 11 及以下) -->
  <uses-permission android:name="android.permission.BLUETOOTH" />
  <uses-permission android:name="android.permission.BLUETOOTH_ADMIN" />

  <application ...>
</manifest>
```

### iOS

在 `ios/<ProjectName>/Info.plist` 中添加：

```xml
<key>NSBluetoothAlwaysUsageDescription</key>
<string>需要蓝牙权限来连接和配置您的设备</string>
<key>NSBluetoothPeripheralUsageDescription</key>
<string>需要蓝牙权限来连接和配置您的设备</string>
```

## 快速开始

### 方式一：使用 Hook（推荐）

```tsx
import { useDeviceBinding } from './src/hooks/useDeviceBinding';

function MyScreen() {
  const {
    state,
    startScan,
    connectDevice,
    bindDevice,
    configureWiFi,
    disconnect,
  } = useDeviceBinding();

  return (
    <View>
      <Button title="扫描设备" onPress={startScan} />

      {state.devices.map(device => (
        <Button
          key={device.id}
          title={device.name || device.id}
          onPress={() => connectDevice(device.id)}
        />
      ))}

      {state.deviceInfo && (
        <View>
          <Text>设备: {state.deviceInfo.device_id}</Text>
          <Button
            title="绑定"
            onPress={() => bindDevice('my_user_id')}
          />
          <Button
            title="配网"
            onPress={() => configureWiFi('MyWiFi', 'password')}
          />
        </View>
      )}
    </View>
  );
}
```

### 方式二：使用完整界面组件

```tsx
import { DeviceBindingScreen } from './src/components/DeviceBindingScreen';

// 在导航中注册
<Stack.Screen name="DeviceBinding" component={DeviceBindingScreen} />
```

### 方式三：直接使用 Service

```typescript
import { deviceBLE } from './src/services/BLEService';

async function setupDevice() {
  // 1. 请求权限
  await deviceBLE.requestPermissions();

  // 2. 扫描
  const devices = await deviceBLE.scan(10000);
  console.log('Found:', devices);

  // 3. 连接
  await deviceBLE.connect(devices[0].id);

  // 4. 读取设备信息
  const info = await deviceBLE.readDeviceInfo();
  console.log('Device:', info.device_id, info.fw_version);

  // 5. 绑定用户
  const bindResult = await deviceBLE.bindDevice('user_123', 'token_abc');
  console.log('Bound:', bindResult.bound);

  // 6. WiFi 配网
  const wifiResult = await deviceBLE.configureWiFi({
    ssid: 'HomeWiFi',
    password: 'password123',
  });
  console.log('WiFi:', wifiResult.connected, wifiResult.ip);

  // 7. 断开
  await deviceBLE.disconnect();
}
```

## BLE 协议

详见 [BLE_BINDING_PROTOCOL.md](../docs/BLE_BINDING_PROTOCOL.md)

### Service UUID
```
4e490001-b5a3-f393-e0a9-e50e24dcca9e
```

### Characteristics

| UUID (后缀) | 名称 | 属性 | 数据格式 |
|---|---|---|---|
| `..0002..` | Device Info | Read | JSON: `{device_id, device_token, fw_version, mac, ble_name}` |
| `..0003..` | Bind Command | Write | JSON: `{cmd: "bind"/"unbind"/"query", ...}` |
| `..0004..` | Bind Status | Read/Notify | JSON: `{bound, user_id?, bind_time?}` |
| `..0005..` | WiFi Config | Write | JSON: `{ssid, password}` |
| `..0006..` | WiFi Status | Read/Notify | JSON: `{connected, ssid?, ip?, rssi?}` |

## 文件结构

```
react-native/
├── README.md                 # 本文件
└── src/
    ├── index.ts              # 统一导出
    ├── types/
    │   └── ble.ts            # TypeScript 类型定义 + BLE 常量
    ├── services/
    │   └── BLEService.ts     # BLE 通信服务 (react-native-ble-plx)
    ├── hooks/
    │   └── useDeviceBinding.ts  # React Hook (状态管理)
    └── components/
        └── DeviceBindingScreen.tsx  # 完整绑定界面
```

## 设备端对应文件

```
ESP32 Firmware (PlatformIO):
├── include/ble_binding.h     # BLE 绑定模块头文件
├── src/ble_binding.cpp       # BLE 绑定模块实现
├── src/main.cpp              # 主程序 (已集成 BLE)
└── docs/BLE_BINDING_PROTOCOL.md  # 协议规范
```

## 绑定流程

```
App                        ESP32-C6
 │                            │
 │  1. BLE Scan (UUID filter) │
 │──────────────────────────> │
 │  2. Found "IT-A1B2"       │
 │ <────────────────────────── │
 │  3. Connect                │
 │──────────────────────────> │
 │  4. Read Device Info       │
 │──────────────────────────> │
 │  5. {device_id, mac, ...}  │
 │ <────────────────────────── │
 │  6. Write Bind(user_id)    │
 │──────────────────────────> │
 │  7. Notify {bound: true}   │
 │ <────────────────────────── │
 │  8. Write WiFi Config      │
 │──────────────────────────> │
 │  9. Notify {connected:true}│
 │ <────────────────────────── │
 │  10. App → Backend: 注册绑定│
 │                            │
```

## 注意事项

1. **物理距离** — BLE 有效范围约 10m，配对操作需要用户在设备附近
2. **权限** — Android 12+ 需要 `BLUETOOTH_SCAN` 和 `BLUETOOTH_CONNECT` 运行时权限
3. **iOS 模拟器** — iOS 模拟器不支持 BLE，需使用真机调试
4. **WiFi 配网超时** — 设备连接 WiFi 可能需要 5-15 秒，UI 需要显示加载状态
5. **安全** — `device_token` 通过 BLE 传输，仅在物理接近时可读取。生产环境建议增加 PIN 验证

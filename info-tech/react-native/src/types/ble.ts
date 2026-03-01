/**
 * BLE Binding — TypeScript Type Definitions
 * ==========================================
 * Info-tech ESP32-C6 Device ↔ React Native App
 */

// ==================== BLE Constants ====================

/** BLE Service UUID (Info-tech Device Binding Service) */
export const BLE_SERVICE_UUID = '4e490001-b5a3-f393-e0a9-e50e24dcca9e';

/** BLE Characteristic UUIDs */
export const BLE_CHAR = {
  /** 设备信息 (Read) */
  DEVICE_INFO: '4e490002-b5a3-f393-e0a9-e50e24dcca9e',
  /** 绑定命令 (Write) */
  BIND_CMD: '4e490003-b5a3-f393-e0a9-e50e24dcca9e',
  /** 绑定状态 (Read/Notify) */
  BIND_STATUS: '4e490004-b5a3-f393-e0a9-e50e24dcca9e',
  /** WiFi配置 (Write) */
  WIFI_CONFIG: '4e490005-b5a3-f393-e0a9-e50e24dcca9e',
  /** WiFi状态 (Read/Notify) */
  WIFI_STATUS: '4e490006-b5a3-f393-e0a9-e50e24dcca9e',
} as const;

/** 扫描超时 (ms) */
export const BLE_SCAN_TIMEOUT = 10000;
/** 连接超时 (ms) */
export const BLE_CONNECT_TIMEOUT = 5000;
/** 读写超时 (ms) */
export const BLE_RW_TIMEOUT = 3000;
/** WiFi配网等待超时 (ms) */
export const BLE_WIFI_TIMEOUT = 15000;

// ==================== Data Interfaces ====================

/** 设备信息 — 从 Device Info Characteristic 读取 */
export interface DeviceInfo {
  /** 设备唯一标识 (用于后端 API) */
  device_id: string;
  /** 设备认证令牌 (敏感，用于后端注册) */
  device_token: string;
  /** 固件版本号 (semver) */
  fw_version: string;
  /** BLE MAC 地址 */
  mac: string;
  /** BLE 广播名称 */
  ble_name: string;
}

/** 绑定命令 — 写入 Bind Command Characteristic */
export type BindCommand =
  | { cmd: 'bind'; user_id: string; user_token?: string }
  | { cmd: 'unbind' }
  | { cmd: 'query' };

/** 绑定状态 — 从 Bind Status Characteristic 读取/通知 */
export interface BindStatus {
  /** 是否已绑定用户 */
  bound: boolean;
  /** 已绑定的用户 ID */
  user_id?: string;
  /** 绑定时间 (设备运行秒数) */
  bind_time?: number;
}

/** WiFi 配置 — 写入 WiFi Config Characteristic */
export interface WiFiConfig {
  ssid: string;
  password: string;
}

/** WiFi 状态 — 从 WiFi Status Characteristic 读取/通知 */
export interface WiFiStatus {
  connected: boolean;
  ssid?: string;
  ip?: string;
  rssi?: number;
}

// ==================== App State Interfaces ====================

/** 扫描到的 BLE 设备 */
export interface ScannedDevice {
  /** BLE 设备 ID (平台相关，用于连接) */
  id: string;
  /** 设备名称 (e.g. "IT-A1B2") */
  name: string | null;
  /** RSSI 信号强度 */
  rssi: number | null;
  /** 是否为 Info-tech 设备 (包含目标 Service UUID) */
  isInfoTech: boolean;
}

/** 绑定流程步骤 */
export type BindingStep =
  | 'idle'
  | 'scanning'
  | 'connecting'
  | 'reading_info'
  | 'binding'
  | 'configuring_wifi'
  | 'done'
  | 'error';

/** 绑定流程状态 */
export interface BindingState {
  step: BindingStep;
  /** 扫描到的设备列表 */
  devices: ScannedDevice[];
  /** 已连接设备的信息 */
  deviceInfo: DeviceInfo | null;
  /** 绑定状态 */
  bindStatus: BindStatus | null;
  /** WiFi 状态 */
  wifiStatus: WiFiStatus | null;
  /** 错误信息 */
  error: string | null;
}

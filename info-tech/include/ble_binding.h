#pragma once
/*
 * BLE Binding Module — Info-tech Device
 * ======================================
 * 通过 BLE GATT 服务实现 React Native App 与 ESP32-C6 设备的
 * 配对绑定、设备信息交换、WiFi 配网。
 *
 * BLE Service UUID : 4e490001-b5a3-f393-e0a9-e50e24dcca9e
 * Characteristics  : 见下方 UUID 定义
 *
 * 依赖：Arduino-ESP32 core 3.x built-in BLE library (NimBLE-based)
 */

#include <Arduino.h>

// ==================== BLE UUIDs ====================
// 前缀 0x4E49 = "NI" (Info-tech)
#define BLE_SVC_UUID          "4e490001-b5a3-f393-e0a9-e50e24dcca9e"
#define CHAR_DEV_INFO_UUID    "4e490002-b5a3-f393-e0a9-e50e24dcca9e"  // Read
#define CHAR_BIND_CMD_UUID    "4e490003-b5a3-f393-e0a9-e50e24dcca9e"  // Write
#define CHAR_BIND_STATUS_UUID "4e490004-b5a3-f393-e0a9-e50e24dcca9e"  // Read + Notify
#define CHAR_WIFI_CFG_UUID    "4e490005-b5a3-f393-e0a9-e50e24dcca9e"  // Write
#define CHAR_WIFI_STS_UUID    "4e490006-b5a3-f393-e0a9-e50e24dcca9e"  // Read + Notify
#define CHAR_SRV_CFG_UUID     "4e490007-b5a3-f393-e0a9-e50e24dcca9e"  // Write: Server config

// ==================== 数据结构 ====================

struct BindingInfo {
  bool   bound;
  char   userId[64];
  char   userToken[128];
  uint32_t bindTimestamp;  // seconds since boot at bind time
};

// ==================== 公开接口 ====================

/**
 * 初始化 BLE 绑定服务（在 setup() 中调用，WiFi 初始化之后）
 * @param deviceId    设备唯一标识
 * @param deviceToken 后端认证令牌（将通过 BLE 提供给 App）
 * @param fwVersion   固件版本号
 * @return true 初始化成功
 */
bool bleBindingInit(const char* deviceId, const char* deviceToken, const char* fwVersion);

/**
 * BLE 周期处理（在 loop() 中调用）
 * 用于处理：WiFi 状态通知更新等延迟操作
 */
void bleBindingLoop();

/** 设备当前是否已绑定用户 */
bool bleIsBound();

/** 获取绑定信息 */
const BindingInfo& bleGetBindingInfo();

/** 是否有通过 BLE 收到的新 WiFi 配置 */
bool bleHasNewWiFiConfig();

/** 获取 BLE 下发的 WiFi SSID */
String bleGetWiFiSSID();

/** 获取 BLE 下发的 WiFi 密码 */
String bleGetWiFiPassword();

/** 清除新 WiFi 配置标志 */
void bleClearNewWiFiConfig();

/**
 * 更新 WiFi 状态（从 main 调用，会通过 BLE Notify 推送到 App）
 */
void bleUpdateWiFiStatus(bool connected, const char* ssid, const char* ip, int rssi);

/** BLE 客户端是否已连接 */
bool bleIsClientConnected();

/** 获取 BLE 设备名称（init 后有效）*/
const char* bleGetDeviceName();

/** 强制解绑（串口调试用） */
void bleForceUnbind();

/** 是否有通过 BLE 收到的新服务器配置 */
bool bleHasNewServerConfig();

/** 获取 BLE 下发的服务器 Host */
String bleGetServerHost();

/** 获取 BLE 下发的服务器 Port */
uint16_t bleGetServerPort();

/** 清除新服务器配置标志 */
void bleClearNewServerConfig();

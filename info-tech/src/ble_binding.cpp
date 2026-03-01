/*
 * BLE Binding Module — Implementation
 * =====================================
 * 使用 Arduino-ESP32 core 3.x 内置 BLE 库（基于 NimBLE）。
 *
 * ⚠️ 编译兼容性说明：
 *   pioarduino (Arduino-ESP32 core 3.x / ESP-IDF 5.x) 内置 BLE 库
 *   使用 NimBLE 作为底层实现。如果 <BLEDevice.h> 找不到，请改用：
 *     #include <NimBLEDevice.h>
 *   并把 BLEServer → NimBLEServer, BLECharacteristic → NimBLECharacteristic 等。
 *   回调签名也可能需要增加 NimBLEConnInfo& 参数。
 */

#include "ble_binding.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <Preferences.h>
#include <WiFi.h>
#include <esp_mac.h>

// ==================== 内部状态 ====================

static BLEServer*         s_pServer   = nullptr;
static BLEService*        s_pService  = nullptr;
static BLECharacteristic* s_pDevInfo  = nullptr;
static BLECharacteristic* s_pBindCmd  = nullptr;
static BLECharacteristic* s_pBindSts  = nullptr;
static BLECharacteristic* s_pWifiCfg  = nullptr;
static BLECharacteristic* s_pWifiSts  = nullptr;
static BLECharacteristic* s_pSrvCfg   = nullptr;

static BindingInfo s_bindInfo = { false, {0}, {0}, 0 };

static String s_deviceId;
static String s_deviceToken;
static String s_fwVersion;
static char   s_bleName[20] = {0};

static volatile bool s_clientConnected = false;
static volatile bool s_newWifiCfg      = false;
static String s_wifiSSID;
static String s_wifiPassword;

// 服务器配置（通过 BLE 下发）
static volatile bool s_newServerCfg    = false;
static String s_serverHost;
static uint16_t s_serverPort = 0;

// WiFi 状态缓存（用于通知）
static bool   s_lastWifiConn  = false;
static String s_lastWifiSSID;
static String s_lastWifiIP;
static int    s_lastWifiRSSI  = 0;
static volatile bool s_wifiStatusDirty = false;

// NVS 命名空间
static const char* NVS_NS = "ble_bind";

// ==================== 简易 JSON 工具 ====================

static bool jsonParseString(const String& json, const char* key, String& out) {
  int k = json.indexOf(key);
  if (k < 0) return false;
  int c = json.indexOf(':', k);
  if (c < 0) return false;
  int q1 = json.indexOf('"', c);
  if (q1 < 0) return false;
  int q2 = json.indexOf('"', q1 + 1);
  if (q2 < 0) return false;
  out = json.substring(q1 + 1, q2);
  return true;
}

// ==================== NVS 持久化 ====================

static void nvsSaveBinding() {
  Preferences prefs;
  prefs.begin(NVS_NS, false);
  prefs.putBool("bound", s_bindInfo.bound);
  prefs.putString("userId", s_bindInfo.userId);
  prefs.putString("userTok", s_bindInfo.userToken);
  prefs.putUInt("bindTs", s_bindInfo.bindTimestamp);
  prefs.end();
}

static void nvsLoadBinding() {
  Preferences prefs;
  if (!prefs.begin(NVS_NS, false)) {
    // NVS not ready; keep defaults
    return;
  }
  s_bindInfo.bound = prefs.getBool("bound", false);
  String uid = prefs.getString("userId", "");
  String utk = prefs.getString("userTok", "");
  strncpy(s_bindInfo.userId, uid.c_str(), sizeof(s_bindInfo.userId) - 1);
  s_bindInfo.userId[sizeof(s_bindInfo.userId) - 1] = '\0';
  strncpy(s_bindInfo.userToken, utk.c_str(), sizeof(s_bindInfo.userToken) - 1);
  s_bindInfo.userToken[sizeof(s_bindInfo.userToken) - 1] = '\0';
  s_bindInfo.bindTimestamp = prefs.getUInt("bindTs", 0);
  prefs.end();
}

static void nvsClearBinding() {
  Preferences prefs;
  prefs.begin(NVS_NS, false);
  prefs.clear();
  prefs.end();
}

// ==================== JSON 构建 ====================

static String buildDevInfoJson() {
  String mac = BLEDevice::getAddress().toString().c_str();
  String json = "{";
  json += "\"device_id\":\"" + s_deviceId + "\",";
  json += "\"device_token\":\"" + s_deviceToken + "\",";
  json += "\"fw_version\":\"" + s_fwVersion + "\",";
  json += "\"mac\":\"" + mac + "\",";
  json += "\"ble_name\":\"" + String(s_bleName) + "\"";
  json += "}";
  return json;
}

static String buildBindStatusJson() {
  String json = "{";
  json += "\"bound\":";
  json += (s_bindInfo.bound ? "true" : "false");
  if (s_bindInfo.bound) {
    json += ",\"user_id\":\"" + String(s_bindInfo.userId) + "\"";
    json += ",\"bind_time\":" + String(s_bindInfo.bindTimestamp);
  }
  json += "}";
  return json;
}

static String buildWifiStatusJson() {
  String json = "{";
  json += "\"connected\":";
  json += (s_lastWifiConn ? "true" : "false");
  if (s_lastWifiConn) {
    json += ",\"ssid\":\"" + s_lastWifiSSID + "\"";
    json += ",\"ip\":\"" + s_lastWifiIP + "\"";
    json += ",\"rssi\":" + String(s_lastWifiRSSI);
  }
  json += "}";
  return json;
}

// ==================== BLE 回调 ====================

/*
 * 编译兼容性注意：
 *   Arduino-ESP32 core 3.x 的 BLEServerCallbacks 签名可能为：
 *     void onConnect(BLEServer* pServer, BLEConnInfo& connInfo)
 *   如遇编译错误，请按上述签名修改并忽略 connInfo 参数。
 */

class ServerCallbacks : public BLEServerCallbacks {
  void onConnect(BLEServer* pServer) override {
    s_clientConnected = true;
    Serial.println("[BLE] Client connected");
  }

  void onDisconnect(BLEServer* pServer) override {
    s_clientConnected = false;
    Serial.println("[BLE] Client disconnected");
    // 断开后重新广播
    BLEDevice::startAdvertising();
  }
};

class BindCmdCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* pChar) override {
    // 安全读取写入值
    String val = String(pChar->getValue().c_str());
    Serial.print("[BLE] Bind cmd received: ");
    Serial.println(val);

    String cmd;
    if (!jsonParseString(val, "\"cmd\"", cmd)) {
      Serial.println("[BLE] Invalid bind command (no cmd field)");
      return;
    }

    if (cmd == "bind") {
      String userId, userToken;
      jsonParseString(val, "\"user_id\"", userId);
      jsonParseString(val, "\"user_token\"", userToken);

      if (userId.length() == 0) {
        Serial.println("[BLE] Bind failed: empty user_id");
        return;
      }

      // 存储绑定信息
      strncpy(s_bindInfo.userId, userId.c_str(), sizeof(s_bindInfo.userId) - 1);
      s_bindInfo.userId[sizeof(s_bindInfo.userId) - 1] = '\0';
      strncpy(s_bindInfo.userToken, userToken.c_str(), sizeof(s_bindInfo.userToken) - 1);
      s_bindInfo.userToken[sizeof(s_bindInfo.userToken) - 1] = '\0';
      s_bindInfo.bound = true;
      s_bindInfo.bindTimestamp = (uint32_t)(millis() / 1000);

      nvsSaveBinding();

      // 更新 Bind Status 特征值并通知
      String json = buildBindStatusJson();
      s_pBindSts->setValue((uint8_t*)json.c_str(), json.length());
      if (s_clientConnected) {
        s_pBindSts->notify();
      }

      Serial.printf("[BLE] ✓ Bound to user: %s\n", userId.c_str());

    } else if (cmd == "unbind") {
      memset(s_bindInfo.userId, 0, sizeof(s_bindInfo.userId));
      memset(s_bindInfo.userToken, 0, sizeof(s_bindInfo.userToken));
      s_bindInfo.bound = false;
      s_bindInfo.bindTimestamp = 0;

      nvsClearBinding();

      String json = buildBindStatusJson();
      s_pBindSts->setValue((uint8_t*)json.c_str(), json.length());
      if (s_clientConnected) {
        s_pBindSts->notify();
      }

      Serial.println("[BLE] ✓ Unbound");

    } else if (cmd == "query") {
      // 返回当前绑定状态
      String json = buildBindStatusJson();
      s_pBindSts->setValue((uint8_t*)json.c_str(), json.length());
      if (s_clientConnected) {
        s_pBindSts->notify();
      }
    } else {
      Serial.printf("[BLE] Unknown bind cmd: %s\n", cmd.c_str());
    }
  }
};

class WifiCfgCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* pChar) override {
    String val = String(pChar->getValue().c_str());
    Serial.print("[BLE] WiFi config received: ");
    // 不打印密码，仅打印 SSID
    String ssid, pass;
    jsonParseString(val, "\"ssid\"", ssid);
    jsonParseString(val, "\"password\"", pass);

    if (ssid.length() == 0) {
      Serial.println("[BLE] WiFi config: empty SSID, ignored");
      return;
    }

    Serial.printf("SSID=%s\n", ssid.c_str());
    s_wifiSSID     = ssid;
    s_wifiPassword = pass;
    s_newWifiCfg   = true;
  }
};

// 服务器配置 BLE 回调: {"host":"1.2.3.4","port":9000}
class ServerCfgCallbacks : public BLECharacteristicCallbacks {
  void onWrite(BLECharacteristic* pChar) override {
    String val = String(pChar->getValue().c_str());
    Serial.print("[BLE] Server config received: ");
    Serial.println(val);

    String host;
    if (!jsonParseString(val, "\"host\"", host) || host.length() == 0) {
      Serial.println("[BLE] Server config: empty host, ignored");
      return;
    }

    s_serverHost = host;
    // 解析 port（简单方法）
    int pk = val.indexOf("\"port\"");
    if (pk >= 0) {
      int pc = val.indexOf(':', pk);
      if (pc >= 0) {
        String tail = val.substring(pc + 1);
        tail.trim();
        uint16_t p = (uint16_t) tail.toInt();
        if (p > 0) s_serverPort = p;
      }
    }
    if (s_serverPort == 0) s_serverPort = 9000;
    s_newServerCfg = true;
    Serial.printf("[BLE] ✓ Server config: %s:%u\n", s_serverHost.c_str(), (unsigned)s_serverPort);
  }
};

// ==================== 公开接口实现 ====================

bool bleBindingInit(const char* deviceId, const char* deviceToken, const char* fwVersion) {
  s_deviceId    = deviceId;
  s_deviceToken = deviceToken;
  s_fwVersion   = fwVersion;

  // 从 NVS 加载已有绑定
  nvsLoadBinding();

  // 生成 BLE 设备名：IT-XXXX（MAC 后两字节）
  uint8_t mac[6];
  esp_read_mac(mac, ESP_MAC_BT);
  snprintf(s_bleName, sizeof(s_bleName), "IT-%02X%02X", mac[4], mac[5]);

  // 初始化 BLE
  BLEDevice::init(s_bleName);

  // 创建 GATT Server
  s_pServer = BLEDevice::createServer();
  s_pServer->setCallbacks(new ServerCallbacks());

  // 创建 Service
  s_pService = s_pServer->createService(BLE_SVC_UUID);

  // --- Characteristic: Device Info (Read) ---
  s_pDevInfo = s_pService->createCharacteristic(
    CHAR_DEV_INFO_UUID,
    BLECharacteristic::PROPERTY_READ
  );
  String devInfoJson = buildDevInfoJson();
  s_pDevInfo->setValue((uint8_t*)devInfoJson.c_str(), devInfoJson.length());

  // --- Characteristic: Bind Command (Write) ---
  s_pBindCmd = s_pService->createCharacteristic(
    CHAR_BIND_CMD_UUID,
    BLECharacteristic::PROPERTY_WRITE
  );
  s_pBindCmd->setCallbacks(new BindCmdCallbacks());

  // --- Characteristic: Bind Status (Read + Notify) ---
  s_pBindSts = s_pService->createCharacteristic(
    CHAR_BIND_STATUS_UUID,
    BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
  );
  String bindStsJson = buildBindStatusJson();
  s_pBindSts->setValue((uint8_t*)bindStsJson.c_str(), bindStsJson.length());

  // --- Characteristic: WiFi Config (Write) ---
  s_pWifiCfg = s_pService->createCharacteristic(
    CHAR_WIFI_CFG_UUID,
    BLECharacteristic::PROPERTY_WRITE
  );
  s_pWifiCfg->setCallbacks(new WifiCfgCallbacks());

  // --- Characteristic: WiFi Status (Read + Notify) ---
  s_pWifiSts = s_pService->createCharacteristic(
    CHAR_WIFI_STS_UUID,
    BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
  );
  String wifiStsJson = buildWifiStatusJson();
  s_pWifiSts->setValue((uint8_t*)wifiStsJson.c_str(), wifiStsJson.length());

  // --- Characteristic: Server Config (Write) ---
  s_pSrvCfg = s_pService->createCharacteristic(
    CHAR_SRV_CFG_UUID,
    BLECharacteristic::PROPERTY_WRITE
  );
  s_pSrvCfg->setCallbacks(new ServerCfgCallbacks());

  // 启动 Service
  s_pService->start();

  // 配置广播
  BLEAdvertising* pAdv = BLEDevice::getAdvertising();
  pAdv->addServiceUUID(BLE_SVC_UUID);
  pAdv->setScanResponse(true);
  BLEDevice::startAdvertising();

  Serial.printf("[BLE] Started as '%s' | Service: %s\n", s_bleName, BLE_SVC_UUID);
  if (s_bindInfo.bound) {
    Serial.printf("[BLE] Previously bound to user: %s\n", s_bindInfo.userId);
  } else {
    Serial.println("[BLE] No binding found (waiting for App)");
  }

  return true;
}

void bleBindingLoop() {
  // 如果 WiFi 状态有更新，推送 Notify
  if (s_wifiStatusDirty) {
    s_wifiStatusDirty = false;
    String json = buildWifiStatusJson();
    s_pWifiSts->setValue((uint8_t*)json.c_str(), json.length());
    if (s_clientConnected) {
      s_pWifiSts->notify();
    }
  }
}

bool bleIsBound() {
  return s_bindInfo.bound;
}

const BindingInfo& bleGetBindingInfo() {
  return s_bindInfo;
}

bool bleHasNewWiFiConfig() {
  return s_newWifiCfg;
}

String bleGetWiFiSSID() {
  return s_wifiSSID;
}

String bleGetWiFiPassword() {
  return s_wifiPassword;
}

void bleClearNewWiFiConfig() {
  s_newWifiCfg = false;
}

void bleUpdateWiFiStatus(bool connected, const char* ssid, const char* ip, int rssi) {
  s_lastWifiConn = connected;
  s_lastWifiSSID = ssid ? ssid : "";
  s_lastWifiIP   = ip ? ip : "";
  s_lastWifiRSSI = rssi;
  s_wifiStatusDirty = true;
}

bool bleIsClientConnected() {
  return s_clientConnected;
}

const char* bleGetDeviceName() {
  return s_bleName;
}

void bleForceUnbind() {
  memset(s_bindInfo.userId, 0, sizeof(s_bindInfo.userId));
  memset(s_bindInfo.userToken, 0, sizeof(s_bindInfo.userToken));
  s_bindInfo.bound = false;
  s_bindInfo.bindTimestamp = 0;
  nvsClearBinding();

  if (s_pBindSts) {
    String json = buildBindStatusJson();
    s_pBindSts->setValue((uint8_t*)json.c_str(), json.length());
    if (s_clientConnected) {
      s_pBindSts->notify();
    }
  }
  Serial.println("[BLE] ✓ Force unbound");
}

bool bleHasNewServerConfig() {
  return s_newServerCfg;
}

String bleGetServerHost() {
  return s_serverHost;
}

uint16_t bleGetServerPort() {
  return s_serverPort;
}

void bleClearNewServerConfig() {
  s_newServerCfg = false;
}

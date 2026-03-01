#include <Arduino.h>
#include <WiFi.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WebSocketsClient.h>
#include <driver/i2s_std.h>
#include <esp_system.h>
#include <esp_wifi.h>

// ===== Build-time defaults (override with -D in platformio.ini) =====
#ifndef FW_VERSION
#define FW_VERSION "2.0.0"
#endif

#ifndef CFG_SAMPLE_RATE
#define CFG_SAMPLE_RATE 16000
#endif
#ifndef CFG_FRAME_SAMPLES
#define CFG_FRAME_SAMPLES 320
#endif
#ifndef CFG_FRAME_BYTES
#define CFG_FRAME_BYTES (CFG_FRAME_SAMPLES * 2)
#endif

#ifndef CFG_I2S_BCLK
#define CFG_I2S_BCLK 0
#endif
#ifndef CFG_I2S_WS
#define CFG_I2S_WS 1
#endif
#ifndef CFG_I2S_DIN
#define CFG_I2S_DIN 2
#endif
#ifndef CFG_I2S_MIC_SEL
#define CFG_I2S_MIC_SEL 21
#endif

#ifndef CFG_BUTTON_PIN
#define CFG_BUTTON_PIN 9
#endif
#ifndef CFG_BUTTON_ACTIVE_LOW
#define CFG_BUTTON_ACTIVE_LOW 1
#endif

#ifndef CFG_LED_PIN
#define CFG_LED_PIN LED_BUILTIN
#endif
#ifndef CFG_LED_ACTIVE_LOW
#define CFG_LED_ACTIVE_LOW 0
#endif

#ifndef CFG_RGB_R_PIN
#define CFG_RGB_R_PIN -1
#endif
#ifndef CFG_RGB_G_PIN
#define CFG_RGB_G_PIN -1
#endif
#ifndef CFG_RGB_B_PIN
#define CFG_RGB_B_PIN -1
#endif
#ifndef CFG_RGB_ACTIVE_LOW
#define CFG_RGB_ACTIVE_LOW 0
#endif

#ifndef CFG_WS_PATH
#define CFG_WS_PATH "/ws/ingest/pcm"
#endif

#ifndef CFG_WS_BACKOFF_MAX_MS
#define CFG_WS_BACKOFF_MAX_MS 30000
#endif

#ifndef CFG_AUDIO_QUEUE_DEPTH
#define CFG_AUDIO_QUEUE_DEPTH 64
#endif

#ifndef CFG_ENABLE_VAD
#define CFG_ENABLE_VAD 0
#endif
#ifndef CFG_VAD_THRESHOLD
#define CFG_VAD_THRESHOLD 120
#endif
#ifndef CFG_VAD_SILENCE_MS
#define CFG_VAD_SILENCE_MS 2000
#endif

#ifndef CFG_LOG_DEBUG
#define CFG_LOG_DEBUG 0
#endif

#define TAG "FW"
#define LOGI(fmt, ...) Serial.printf("[I][%s] " fmt "\n", TAG, ##__VA_ARGS__)
#define LOGW(fmt, ...) Serial.printf("[W][%s] " fmt "\n", TAG, ##__VA_ARGS__)
#define LOGE(fmt, ...) Serial.printf("[E][%s] " fmt "\n", TAG, ##__VA_ARGS__)
#if CFG_LOG_DEBUG
#define LOGD(fmt, ...) Serial.printf("[D][%s] " fmt "\n", TAG, ##__VA_ARGS__)
#else
#define LOGD(fmt, ...)
#endif

struct DeviceConfig {
  String ssid;
  String password;
  String ws_host;
  uint16_t ws_port;
  String ws_path;
  String device_id;
  String ingest_token;
  int i2s_bclk;
  int i2s_ws;
  int i2s_din;
  int i2s_mic_sel;
  int led_pin;
  int rgb_r;
  int rgb_g;
  int rgb_b;
  int button_pin;
};

struct AudioFrame {
  uint8_t data[CFG_FRAME_BYTES];
  uint16_t len;
};

enum class LedState : uint8_t {
  WIFI_CONNECTING,
  STREAMING,
  RECONNECTING,
  ERROR,
  OTA,
  IDLE,
};

static Preferences sPrefs;
static WebServer sProvisionServer(80);
static WebSocketsClient sWs;
static i2s_chan_handle_t sRxHandle = nullptr;
static QueueHandle_t sAudioQueue = nullptr;

static DeviceConfig sCfg;

static volatile bool sWifiReady = false;
static volatile bool sWsConnected = false;
static volatile bool sMuted = false;
static volatile bool sCaptureReady = false;
static volatile bool sProvisionMode = false;
static volatile bool sNeedWifiReconnect = false;
static volatile bool sWsNeedReconnect = false;

static volatile bool sVadSpeech = true;
static uint32_t sVadSilentMs = 0;
static volatile bool sMicTestMode = false;
static volatile uint32_t sMicLastRms = 0;
static volatile uint32_t sMicLastPeak = 0;

static uint32_t sWsBackoffMs = 1000;
static uint32_t sWsNextRetryAtMs = 0;

static LedState sLedState = LedState::WIFI_CONNECTING;
static uint8_t sHarmfulFlashRemainingEdges = 0;
static uint32_t sHarmfulFlashUntilMs = 0;

static bool sBtnPressed = false;
static uint32_t sBtnPressStartMs = 0;

static const char *kDefaultWsHost = "43.142.49.126";
static const uint16_t kDefaultWsPort = 9000;
static const char *kDefaultToken = "<device_ingest_token>";
// ===== Runtime fixed config (copy/paste block for quick edits) =====
#define CFG_WIFI_SSID_FIXED "HUAWEI Mate 20"
#define CFG_WIFI_PASS_FIXED "20111031"
#define CFG_DEVICE_ID_FIXED "esp32c6_DB1CA7D8"
#define CFG_DEVICE_TOKEN_FIXED "KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw"
#define CFG_WS_HOST_FIXED "43.142.49.126"
#define CFG_WS_PORT_FIXED 9000
#define CFG_WS_PATH_FIXED "/ws/ingest/pcm"

static const char *kForcedWifiSsid = CFG_WIFI_SSID_FIXED;
static const char *kForcedWifiPassword = CFG_WIFI_PASS_FIXED;
static const bool kDisableProvisioning = true;
static bool sWsConnectInFlight = false;
static uint32_t sWsConnectAttemptAtMs = 0;
static volatile int sLastDisconnectReason = -1;

static const char *wifiReasonName(int reason) {
  switch (reason) {
    case 1: return "UNSPECIFIED";
    case 2: return "AUTH_EXPIRE";
    case 3: return "AUTH_LEAVE";
    case 4: return "ASSOC_EXPIRE";
    case 5: return "ASSOC_TOOMANY";
    case 6: return "NOT_AUTHED";
    case 7: return "NOT_ASSOCED";
    case 8: return "ASSOC_LEAVE";
    case 9: return "ASSOC_NOT_AUTHED";
    case 15: return "4WAY_HANDSHAKE_TIMEOUT";
    case 16: return "GROUP_KEY_UPDATE_TIMEOUT";
    case 17: return "IE_IN_4WAY_DIFFERS";
    case 23: return "802_1X_AUTH_FAILED";
    case 201: return "NO_AP_FOUND";
    case 202: return "AUTH_FAIL";
    case 203: return "ASSOC_FAIL";
    case 204: return "HANDSHAKE_TIMEOUT";
    default: return "UNKNOWN";
  }
}

static void onWiFiEvent(arduino_event_id_t event, arduino_event_info_t info) {
  if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
    sLastDisconnectReason = static_cast<int>(info.wifi_sta_disconnected.reason);
    Serial.printf("DISCONNECT reason=%d\n", sLastDisconnectReason);
    Serial.printf("DISCONNECT_NAME=%s\n", wifiReasonName(sLastDisconnectReason));
  }
}

static void logScanForTargetSsid() {
  int found = 0;
  int rssi = -127;
  int n = WiFi.scanNetworks(/*async=*/false, /*show_hidden=*/true);
  for (int i = 0; i < n; i++) {
    if (WiFi.SSID(i) == sCfg.ssid) {
      found = 1;
      rssi = WiFi.RSSI(i);
      break;
    }
  }
  Serial.printf("SCAN found=%d rssi=%d\n", found, rssi);
}

static String defaultDeviceId() {
  uint8_t mac[6] = {0};
  WiFi.macAddress(mac);
  char id[40];
  snprintf(id, sizeof(id), "esp32c6_%02X%02X%02X%02X", mac[2], mac[3], mac[4], mac[5]);
  return String(id);
}

static void loadConfig() {
  sCfg.ssid = sPrefs.getString("ssid", "");
  sCfg.password = sPrefs.getString("pwd", "");
  sCfg.ws_host = sPrefs.getString("wshost", kDefaultWsHost);
  sCfg.ws_port = static_cast<uint16_t>(sPrefs.getUShort("wsport", kDefaultWsPort));
  sCfg.ws_path = sPrefs.getString("wspath", CFG_WS_PATH);
  sCfg.device_id = sPrefs.getString("devid", defaultDeviceId());
  sCfg.ingest_token = sPrefs.getString("token", kDefaultToken);

  sCfg.i2s_bclk = sPrefs.getInt("i2s_bclk", CFG_I2S_BCLK);
  sCfg.i2s_ws = sPrefs.getInt("i2s_ws", CFG_I2S_WS);
  sCfg.i2s_din = sPrefs.getInt("i2s_din", CFG_I2S_DIN);
  sCfg.i2s_mic_sel = sPrefs.getInt("i2s_sel", CFG_I2S_MIC_SEL);

  sCfg.led_pin = sPrefs.getInt("led_pin", CFG_LED_PIN);
  sCfg.rgb_r = sPrefs.getInt("rgb_r", CFG_RGB_R_PIN);
  sCfg.rgb_g = sPrefs.getInt("rgb_g", CFG_RGB_G_PIN);
  sCfg.rgb_b = sPrefs.getInt("rgb_b", CFG_RGB_B_PIN);
  sCfg.button_pin = sPrefs.getInt("btn_pin", CFG_BUTTON_PIN);
}

static void logFailureClass(const char *klass, const String &detail, const char *nextStep) {
  LOGE("FAIL_CLASS=%s detail=%s", klass, detail.c_str());
  LOGI("NEXT_STEP: %s", nextStep);
}

static void saveWifiAndServer(const String &ssid,
                              const String &password,
                              const String &host,
                              uint16_t port,
                              const String &deviceId,
                              const String &token) {
  sPrefs.putString("ssid", ssid);
  sPrefs.putString("pwd", password);
  sPrefs.putString("wshost", host);
  sPrefs.putUShort("wsport", port);
  sPrefs.putString("devid", deviceId);
  sPrefs.putString("token", token);
  loadConfig();
}

static void setMonoLed(bool on) {
  if (sCfg.led_pin < 0) return;
  int level = on ? HIGH : LOW;
#if CFG_LED_ACTIVE_LOW
  level = on ? LOW : HIGH;
#endif
  digitalWrite(sCfg.led_pin, level);
}

static void setRgb(uint8_t r, uint8_t g, uint8_t b) {
  if (sCfg.rgb_r < 0 || sCfg.rgb_g < 0 || sCfg.rgb_b < 0) {
    setMonoLed((r + g + b) > 0);
    return;
  }
#if CFG_RGB_ACTIVE_LOW
  analogWrite(sCfg.rgb_r, 255 - r);
  analogWrite(sCfg.rgb_g, 255 - g);
  analogWrite(sCfg.rgb_b, 255 - b);
#else
  analogWrite(sCfg.rgb_r, r);
  analogWrite(sCfg.rgb_g, g);
  analogWrite(sCfg.rgb_b, b);
#endif
}

static void setLedState(LedState state) {
  sLedState = state;
}

static void triggerHarmfulFlash() {
  sHarmfulFlashRemainingEdges = 6;
  sHarmfulFlashUntilMs = millis();
}

static void ledTaskStep() {
  static uint32_t lastMs = 0;
  static bool phase = false;
  const uint32_t now = millis();

  if (sHarmfulFlashRemainingEdges > 0) {
    if (now - sHarmfulFlashUntilMs >= 150) {
      sHarmfulFlashUntilMs = now;
      phase = !phase;
      sHarmfulFlashRemainingEdges--;
      setRgb(phase ? 255 : 0, 0, 0);
    }
    return;
  }

  switch (sLedState) {
    case LedState::WIFI_CONNECTING:
      if (now - lastMs >= 700) {
        lastMs = now;
        phase = !phase;
      }
      setRgb(0, 0, phase ? 255 : 0);
      break;
    case LedState::STREAMING:
      setRgb(0, 255, 0);
      break;
    case LedState::RECONNECTING:
      if (now - lastMs >= 500) {
        lastMs = now;
        phase = !phase;
      }
      // RGB: yellow slow blink; mono fallback: quick blink
      if (sCfg.rgb_r >= 0) {
        setRgb(phase ? 255 : 0, phase ? 180 : 0, 0);
      } else {
        setMonoLed(phase);
      }
      break;
    case LedState::ERROR:
      if (now - lastMs >= 800) {
        lastMs = now;
        phase = !phase;
      }
      setRgb(phase ? 255 : 0, 0, 0);
      break;
    case LedState::OTA: {
      // Purple breathing
      static int v = 0;
      static int dir = 8;
      if (now - lastMs >= 30) {
        lastMs = now;
        v += dir;
        if (v >= 255) {
          v = 255;
          dir = -8;
        }
        if (v <= 0) {
          v = 0;
          dir = 8;
        }
      }
      setRgb(v, 0, v);
      break;
    }
    case LedState::IDLE:
    default:
      setRgb(0, 0, 0);
      break;
  }
}

static void handleSerialCommandStep() {
  static String line;
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\r') continue;
    if (c == '\n') {
      line.trim();
      line.toLowerCase();
      if (line == "mic test on" || line == "mic on") {
        sMicTestMode = true;
        LOGI("Mic test mode ON");
      } else if (line == "mic test off" || line == "mic off") {
        sMicTestMode = false;
        LOGI("Mic test mode OFF");
      } else if (line == "mic once") {
        LOGI("Mic rms=%lu peak=%lu", (unsigned long)sMicLastRms, (unsigned long)sMicLastPeak);
      } else if (line == "help") {
        Serial.println("Commands:");
        Serial.println("  mic on / mic off");
        Serial.println("  mic once");
      } else if (line.length() > 0) {
        LOGW("Unknown command: %s", line.c_str());
      }
      line = "";
      continue;
    }
    if (line.length() < 80) line += c;
  }
}

static bool connectWifiBlocking(uint32_t timeoutMs = 15000) {
  if (sCfg.ssid.isEmpty()) {
    LOGW("WiFi SSID empty");
    return false;
  }
  setLedState(LedState::WIFI_CONNECTING);
  WiFi.mode(WIFI_STA);
  logScanForTargetSsid();
  WiFi.begin(sCfg.ssid.c_str(), sCfg.password.c_str());
  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < timeoutMs) {
    delay(100);
    ledTaskStep();
  }
  if (WiFi.status() == WL_CONNECTED) {
    sWifiReady = true;
    WiFi.setSleep(false);
    (void)esp_wifi_set_ps(WIFI_PS_NONE);
    Serial.printf("WIFI_OK ip=%s\n", WiFi.localIP().toString().c_str());
    return true;
  }
  sWifiReady = false;
  Serial.printf("STATUS=%d\n", (int)WiFi.status());
  logFailureClass("WIFI_CONNECT_FAILED", "WiFi.join timeout", "Check SSID/password/signal and router 2.4GHz support");
  return false;
}

static String htmlEscape(const String &in) {
  String out;
  out.reserve(in.length() + 16);
  for (size_t i = 0; i < in.length(); i++) {
    char c = in[i];
    if (c == '&') out += "&amp;";
    else if (c == '<') out += "&lt;";
    else if (c == '>') out += "&gt;";
    else if (c == '"') out += "&quot;";
    else out += c;
  }
  return out;
}

static void startProvisioningMode() {
  if (kDisableProvisioning) {
  LOGW("Provisioning disabled by CFG_DISABLE_PROVISIONING");
  return;
  }
  sProvisionMode = true;
  sWifiReady = false;
  sWsConnected = false;
  sNeedWifiReconnect = false;
  sWsNeedReconnect = false;
  sWs.disconnect();
  WiFi.disconnect(true, false);

  WiFi.mode(WIFI_AP_STA);
  String apSsid = "ESP32C6-Provision-" + sCfg.device_id.substring(max(0, (int)sCfg.device_id.length() - 4));
  WiFi.softAP(apSsid.c_str(), "12345678");

  sProvisionServer.on("/", HTTP_GET, []() {
    String page;
    page.reserve(1600);
    page += "<html><body><h3>ESP32-C6 Provision</h3>";
    page += "<form method='POST' action='/save'>";
    page += "SSID: <input name='ssid' value='" + htmlEscape(sCfg.ssid) + "'><br>";
    page += "Password: <input name='pwd' value='" + htmlEscape(sCfg.password) + "'><br>";
    page += "WS Host: <input name='host' value='" + htmlEscape(sCfg.ws_host) + "'><br>";
    page += "WS Port: <input name='port' value='" + String(sCfg.ws_port) + "'><br>";
    page += "Device ID: <input name='devid' value='" + htmlEscape(sCfg.device_id) + "'><br>";
    page += "Ingest Token: <input name='token' value='" + htmlEscape(sCfg.ingest_token) + "'><br>";
    page += "<button type='submit'>Save & Reboot WiFi</button></form></body></html>";
    sProvisionServer.send(200, "text/html", page);
  });

  sProvisionServer.on("/save", HTTP_POST, []() {
    String ssid = sProvisionServer.arg("ssid");
    String pwd = sProvisionServer.arg("pwd");
    String host = sProvisionServer.arg("host");
    String devid = sProvisionServer.arg("devid");
    String token = sProvisionServer.arg("token");
    uint16_t port = static_cast<uint16_t>(sProvisionServer.arg("port").toInt());

    if (ssid.isEmpty() || host.isEmpty() || port == 0 || token.isEmpty()) {
      sProvisionServer.send(400, "text/plain", "invalid input");
      return;
    }
    saveWifiAndServer(ssid, pwd, host, port, devid, token);
    sProvisionServer.send(200, "text/plain", "saved, reconnecting...");

    sProvisionMode = false;
    sProvisionServer.stop();
    WiFi.softAPdisconnect(true);
    sNeedWifiReconnect = true;
    sWsNeedReconnect = true;
    sWsBackoffMs = 1000;
    sWsNextRetryAtMs = 0;
  });

  sProvisionServer.begin();
  LOGI("Provisioning AP started: %s", apSsid.c_str());
  setLedState(LedState::WIFI_CONNECTING);
}

static void factoryResetAndReboot() {
  LOGW("Factory reset requested");
  sPrefs.clear();
  delay(100);
  ESP.restart();
}

static void handleWsEvent(WStype_t type, uint8_t *payload, size_t length) {
  switch (type) {
    case WStype_CONNECTED:
      sWsConnected = true;
      sWsConnectInFlight = false;
      sWsBackoffMs = 1000;
      Serial.println("WS_CONNECTED");
      setLedState(LedState::STREAMING);
      break;
    case WStype_DISCONNECTED:
      sWsConnected = false;
      sWsConnectInFlight = false;
      if (payload != nullptr && length > 0) {
        String reason;
        for (size_t i = 0; i < length; i++) reason += (char)payload[i];
        LOGW("WS CLOSED: %s", reason.c_str());
        if (reason.indexOf("403") >= 0 || reason.indexOf("Unauthorized") >= 0) {
          logFailureClass("WS_AUTH_403", reason, "Verify device_token and query key device_token");
        } else {
          logFailureClass("WS_CLOSED", reason, "Check server logs for close reason");
        }
      } else {
        LOGW("WS CLOSED");
      }
      sWsNeedReconnect = true;
      setLedState(LedState::RECONNECTING);
      break;
    case WStype_TEXT: {
      String msg;
      msg.reserve(length + 1);
      for (size_t i = 0; i < length; i++) msg += static_cast<char>(payload[i]);
      LOGD("WS text: %s", msg.c_str());
      if (msg.indexOf("harmful") >= 0 || msg.indexOf("harmful_flag") >= 0) {
        triggerHarmfulFlash();
      }
      break;
    }
    case WStype_ERROR:
      sWsConnectInFlight = false;
      if (payload != nullptr && length > 0) {
        String err;
        for (size_t i = 0; i < length; i++) err += (char)payload[i];
        LOGE("WS error: %s", err.c_str());
        if (err.indexOf("403") >= 0 || err.indexOf("Unauthorized") >= 0) {
          logFailureClass("WS_AUTH_403", err, "Verify token value and whether backend expects device_token");
        } else if (err.indexOf("resolve") >= 0 || err.indexOf("DNS") >= 0) {
          logFailureClass("DNS_FAIL", err, "Check DNS server and host");
        } else {
          logFailureClass("WS_HANDSHAKE_FAIL", err, "Check URL/query/header and backend route");
        }
      } else {
        LOGE("WS error");
      }
      sWsConnected = false;
      sWsNeedReconnect = true;
      setLedState(LedState::ERROR);
      break;
    default:
      break;
  }
}

static String wsPathWithQuery() {
  String path = sCfg.ws_path;
  path += "?raw=1&device_id=";
  path += sCfg.device_id;
  path += "&device_token=";
  path += sCfg.ingest_token;
  return path;
}

static bool runNetProbe() {
  IPAddress resolved;
  if (WiFi.hostByName(sCfg.ws_host.c_str(), resolved) == 1) {
    LOGI("DNS OK: %s -> %s", sCfg.ws_host.c_str(), resolved.toString().c_str());
  } else {
    logFailureClass("DNS_FAIL", String("hostByName failed for ") + sCfg.ws_host, "Check DNS/router WAN");
    return false;
  }

  WiFiClient probe;
  const bool tcpOk = probe.connect(sCfg.ws_host.c_str(), sCfg.ws_port, 3000);
  if (tcpOk) {
    LOGI("TCP OK: %s:%u", sCfg.ws_host.c_str(), (unsigned)sCfg.ws_port);
    probe.stop();
    return true;
  }
  logFailureClass("TCP_FAIL", String("connect ") + sCfg.ws_host + ":" + String(sCfg.ws_port), "Check firewall/port/reverse proxy");
  return false;
}

static void wsConnectTimeoutTick() {
  if (!sWsConnectInFlight) return;
  if (sWsConnected) return;
  const uint32_t now = millis();
  if (now - sWsConnectAttemptAtMs < 8000) return;
  sWsConnectInFlight = false;
  sWsNeedReconnect = true;
  logFailureClass("WS_HANDSHAKE_TIMEOUT", "No CONNECTED event within 8s", "Check backend ws endpoint and token");
  sWs.disconnect();
}

static String wsFullUrlForLog() {
  String u = String("ws://") + sCfg.ws_host + ":" + String(sCfg.ws_port) + wsPathWithQuery();
  return u;
}

static void wsConnectNow() {
  if (!sWifiReady || sProvisionMode) return;
  if (!runNetProbe()) {
    sWsNeedReconnect = true;
    return;
  }
  String path = wsPathWithQuery();
  LOGI("WS connect %s", wsFullUrlForLog().c_str());
  sWs.begin(sCfg.ws_host.c_str(), sCfg.ws_port, path.c_str());
  sWs.onEvent(handleWsEvent);
  sWs.setReconnectInterval(0);
  sWsConnectInFlight = true;
  sWsConnectAttemptAtMs = millis();
}

static void wsReconnectTick() {
  if (!sWsNeedReconnect || sProvisionMode || !sWifiReady) return;
  const uint32_t now = millis();
  if (now < sWsNextRetryAtMs) return;

  wsConnectNow();
  sWsNeedReconnect = false;

  sWsNextRetryAtMs = now + sWsBackoffMs;
  if (sWsBackoffMs < CFG_WS_BACKOFF_MAX_MS) {
    sWsBackoffMs = min<uint32_t>(sWsBackoffMs * 2, CFG_WS_BACKOFF_MAX_MS);
  }
  setLedState(LedState::RECONNECTING);
}

static bool initI2SMic() {
  pinMode(sCfg.i2s_mic_sel, OUTPUT);
  digitalWrite(sCfg.i2s_mic_sel, LOW);

  i2s_chan_config_t chanCfg = I2S_CHANNEL_DEFAULT_CONFIG(I2S_NUM_0, I2S_ROLE_MASTER);
  chanCfg.dma_desc_num = 8;
  chanCfg.dma_frame_num = 320;
  if (i2s_new_channel(&chanCfg, nullptr, &sRxHandle) != ESP_OK) {
    LOGE("i2s_new_channel failed");
    return false;
  }

  i2s_std_config_t stdCfg = {
      .clk_cfg = I2S_STD_CLK_DEFAULT_CONFIG(CFG_SAMPLE_RATE),
      .slot_cfg = I2S_STD_PHILIPS_SLOT_DEFAULT_CONFIG(I2S_DATA_BIT_WIDTH_32BIT, I2S_SLOT_MODE_MONO),
      .gpio_cfg = {
          .mclk = I2S_GPIO_UNUSED,
          .bclk = (gpio_num_t)sCfg.i2s_bclk,
          .ws = (gpio_num_t)sCfg.i2s_ws,
          .dout = I2S_GPIO_UNUSED,
          .din = (gpio_num_t)sCfg.i2s_din,
          .invert_flags = {.mclk_inv = false, .bclk_inv = false, .ws_inv = false},
      },
  };
  stdCfg.slot_cfg.slot_mask = I2S_STD_SLOT_LEFT;
  stdCfg.slot_cfg.bit_shift = true;

  if (i2s_channel_init_std_mode(sRxHandle, &stdCfg) != ESP_OK) {
    LOGE("i2s_channel_init_std_mode failed");
    return false;
  }
  if (i2s_channel_enable(sRxHandle) != ESP_OK) {
    LOGE("i2s_channel_enable failed");
    return false;
  }

  LOGI("I2S ready: %d Hz, 16-bit mono, %d samples/frame", CFG_SAMPLE_RATE, CFG_FRAME_SAMPLES);
  return true;
}

static void audioCaptureTask(void *arg) {
  (void)arg;
  int32_t raw32[CFG_FRAME_SAMPLES];
  size_t bytesRead = 0;

  for (;;) {
    if (!sCaptureReady || sProvisionMode || (!sWsConnected && !sMicTestMode)) {
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }

    if (i2s_channel_read(sRxHandle, raw32, sizeof(raw32), &bytesRead, pdMS_TO_TICKS(100)) != ESP_OK) {
      continue;
    }
    if (bytesRead < sizeof(raw32)) {
      continue;
    }

    AudioFrame frame{};
    frame.len = CFG_FRAME_BYTES;

    uint64_t sumAbs = 0;
    uint64_t sumSq = 0;
    uint32_t peakAbs = 0;
    for (int i = 0; i < CFG_FRAME_SAMPLES; i++) {
      int16_t s16 = static_cast<int16_t>(raw32[i] >> 16);
      frame.data[i * 2 + 0] = static_cast<uint8_t>(s16 & 0xFF);
      frame.data[i * 2 + 1] = static_cast<uint8_t>((s16 >> 8) & 0xFF);
      const uint32_t absV = static_cast<uint32_t>(abs(s16));
      sumAbs += absV;
      sumSq += static_cast<uint64_t>(s16) * static_cast<uint64_t>(s16);
      if (absV > peakAbs) peakAbs = absV;
    }

    const uint32_t rms = static_cast<uint32_t>(sqrt((double)sumSq / (double)CFG_FRAME_SAMPLES));
    sMicLastRms = rms;
    sMicLastPeak = peakAbs;

#if CFG_ENABLE_VAD
    const uint32_t meanAbs = static_cast<uint32_t>(sumAbs / CFG_FRAME_SAMPLES);
    if (meanAbs < CFG_VAD_THRESHOLD) {
      sVadSilentMs += 20;
      if (sVadSilentMs >= CFG_VAD_SILENCE_MS) {
        sVadSpeech = false;
      }
    } else {
      sVadSpeech = true;
      sVadSilentMs = 0;
    }
#else
    (void)sumAbs;
    sVadSpeech = true;
#endif

    if (xQueueSend(sAudioQueue, &frame, pdMS_TO_TICKS(50)) != pdTRUE) {
      // Queue full: drop oldest then enqueue latest frame to keep latency bounded.
      AudioFrame dummy;
      (void)xQueueReceive(sAudioQueue, &dummy, 0);
      (void)xQueueSend(sAudioQueue, &frame, 0);
      LOGW("Audio queue full, dropped oldest frame");
    }
  }
}

static void audioUploadTask(void *arg) {
  (void)arg;
  AudioFrame frame;

  for (;;) {
    if (xQueueReceive(sAudioQueue, &frame, pdMS_TO_TICKS(20)) != pdTRUE) {
      vTaskDelay(pdMS_TO_TICKS(2));
      continue;
    }

    if (!sWifiReady || !sWsConnected) {
      // Keep frames queued while reconnecting by pushing back if possible.
      if (uxQueueSpacesAvailable(sAudioQueue) > 0) {
        (void)xQueueSendToFront(sAudioQueue, &frame, 0);
      }
      vTaskDelay(pdMS_TO_TICKS(20));
      continue;
    }

    if (sMuted) {
      continue;
    }

#if CFG_ENABLE_VAD
    if (!sVadSpeech) {
      continue;
    }
#endif

    const bool ok = sWs.sendBIN(frame.data, frame.len);  // pure binary PCM, 640 bytes/frame
    if (!ok) {
      sWsConnected = false;
      sWsNeedReconnect = true;
      setLedState(LedState::RECONNECTING);
      if (uxQueueSpacesAvailable(sAudioQueue) > 0) {
        (void)xQueueSendToFront(sAudioQueue, &frame, 0);
      }
      vTaskDelay(pdMS_TO_TICKS(50));
      LOGW("WS CLOSED");
    } else {
      Serial.println("SEND 640 bytes");
    }
  }
}

static void handleButtonStep() {
  const bool raw = (digitalRead(sCfg.button_pin) == (CFG_BUTTON_ACTIVE_LOW ? LOW : HIGH));
  const uint32_t now = millis();

  if (raw && !sBtnPressed) {
    sBtnPressed = true;
    sBtnPressStartMs = now;
    return;
  }

  if (!raw && sBtnPressed) {
    sBtnPressed = false;
    const uint32_t held = now - sBtnPressStartMs;

    if (held >= 10000) {
      factoryResetAndReboot();
      return;
    }
    if (held >= 3000) {
      if (kDisableProvisioning) {
        LOGI("Button long press 3s ignored (provisioning disabled)");
      } else {
        LOGI("Button long press 3s: restart provisioning");
        startProvisioningMode();
      }
      return;
    }
    if (held >= 50) {
      sMuted = !sMuted;
      LOGI("Button short press: %s", sMuted ? "MUTED" : "UNMUTED");
      if (sMuted) {
        setLedState(LedState::IDLE);
      } else if (sWifiReady && sWsConnected) {
        setLedState(LedState::STREAMING);
      }
    }
  }
}

static void ensurePins() {
  if (sCfg.led_pin >= 0) {
    pinMode(sCfg.led_pin, OUTPUT);
    setMonoLed(false);
  }
  if (sCfg.rgb_r >= 0 && sCfg.rgb_g >= 0 && sCfg.rgb_b >= 0) {
    pinMode(sCfg.rgb_r, OUTPUT);
    pinMode(sCfg.rgb_g, OUTPUT);
    pinMode(sCfg.rgb_b, OUTPUT);
    setRgb(0, 0, 0);
  }

  pinMode(sCfg.button_pin, CFG_BUTTON_ACTIVE_LOW ? INPUT_PULLUP : INPUT);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  WiFi.onEvent(onWiFiEvent);

  LOGI("Boot firmware %s", FW_VERSION);

  sPrefs.begin("cfg", false);
  loadConfig();
  sCfg.ssid = String(kForcedWifiSsid);
  sCfg.password = String(kForcedWifiPassword);
  sCfg.ws_host = String(CFG_WS_HOST_FIXED);
  sCfg.ws_port = CFG_WS_PORT_FIXED;
  sCfg.ws_path = String(CFG_WS_PATH_FIXED);
  sCfg.device_id = String(CFG_DEVICE_ID_FIXED);
  sCfg.ingest_token = String(CFG_DEVICE_TOKEN_FIXED);
  ensurePins();

  LOGI("Pins | I2S BCLK=%d WS=%d DIN=%d MIC_SEL=%d BTN=%d LED=%d",
       sCfg.i2s_bclk, sCfg.i2s_ws, sCfg.i2s_din, sCfg.i2s_mic_sel, sCfg.button_pin, sCfg.led_pin);

  sAudioQueue = xQueueCreate(CFG_AUDIO_QUEUE_DEPTH, sizeof(AudioFrame));
  if (!sAudioQueue) {
    LOGE("Failed to create audio queue");
    setLedState(LedState::ERROR);
    return;
  }

  sCaptureReady = initI2SMic();
  if (!sCaptureReady) {
    setLedState(LedState::ERROR);
    return;
  }

  xTaskCreate(audioCaptureTask, "audio_cap", 8192, nullptr, 3, nullptr);
  xTaskCreate(audioUploadTask, "audio_upl", 6144, nullptr, 3, nullptr);

  if (!connectWifiBlocking()) {
    if (kDisableProvisioning) {
      sNeedWifiReconnect = true;
      setLedState(LedState::WIFI_CONNECTING);
    } else {
      startProvisioningMode();
    }
  } else {
    sWsNeedReconnect = true;
    sWsBackoffMs = 1000;
    sWsNextRetryAtMs = 0;
  }

  LOGI("Config | %s",
       wsFullUrlForLog().c_str());
  LOGI("No heartbeat mode; continuous raw PCM streaming");
}

void loop() {
  handleSerialCommandStep();
  handleButtonStep();

  if (sProvisionMode) {
    sProvisionServer.handleClient();
  }

  if (sNeedWifiReconnect) {
    sNeedWifiReconnect = false;
    if (!connectWifiBlocking()) {
      if (kDisableProvisioning) {
        sNeedWifiReconnect = true;
      } else {
        startProvisioningMode();
      }
    } else {
      sWsNeedReconnect = true;
      sWsBackoffMs = 1000;
      sWsNextRetryAtMs = 0;
    }
  }

  if (!sProvisionMode) {
    if (WiFi.status() != WL_CONNECTED) {
      if (sWifiReady) LOGW("WiFi lost, reconnect");
      sWifiReady = false;
      sWsConnected = false;
      sNeedWifiReconnect = true;
      setLedState(LedState::WIFI_CONNECTING);
    }

    sWs.loop();
    wsConnectTimeoutTick();
    wsReconnectTick();

    if (sWifiReady && sWsConnected && !sMuted) {
      setLedState(LedState::STREAMING);
    }
  }

  ledTaskStep();

  if (sMicTestMode) {
    static uint32_t lastPrintMs = 0;
    const uint32_t now = millis();
    if (now - lastPrintMs >= 200) {
      lastPrintMs = now;
      uint32_t rms = sMicLastRms;
      uint32_t peak = sMicLastPeak;
      const int bars = min<int>(40, static_cast<int>(rms / 200));
      Serial.printf("MIC rms=%4lu peak=%5lu |", (unsigned long)rms, (unsigned long)peak);
      for (int i = 0; i < bars; i++) Serial.print('#');
      Serial.println();
    }
  }

  delay(5);
}

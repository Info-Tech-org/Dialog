# 硬件 WebSocket PCM 流式上传协议规范 v1.0

**版本**: v1.0  
**日期**: 2026-02-09  
**传输**: WebSocket (ws://)  

> 本文档描述“设备端通过 WebSocket 连续发送 PCM 二进制分片，服务端逐片 ACK，最后返回 `audio_url`”的协议。

---

## 1. 协议概述

### 1.1 连接方式

- 协议: WebSocket (ws://)
- 端点: `ws://43.142.49.126:9000/ws/ingest/pcm`
- 认证: URL Query Parameter 传递 `device_token`

### 1.2 URL 格式

```
ws://<host>:<port>/ws/ingest/pcm?device_token=<TOKEN>&session_id=<UUID>&device_id=<DEVICE_ID>
```

参数说明：

| 参数 | 必需 | 说明 | 示例 |
|---|---:|---|---|
| `device_token` | ✅ | 设备认证令牌 | `KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw` |
| `session_id` | ✅ | 会话 ID，建议格式：`<timestamp>_<random>` | `46973_24865` |
| `device_id` | ❌ | 设备标识符 | `esp32` |

---

## 2. 消息格式规范

### 2.1 客户端 → 服务器（二进制消息）

二进制消息结构：

```
[0-3]   chunk_index    (uint32_t, big-endian)
[4]     flags          (uint8_t, bit0=is_final)
[5-N]   PCM payload    (raw PCM data)
```

字段说明：

- `chunk_index`: 从 0 开始递增的分片序号（大端序）
- `flags`:
  - bit0: `is_final` (1=最后一片, 0=中间片)
  - bit1-7: 保留（填 0）
- `PCM payload`: 原始 PCM 音频数据
  - 格式: `s16le` (signed 16-bit little-endian)
  - 采样率: 16000 Hz
  - 声道: 1 (mono)

建议每片大小：3200-6400 字节（约 0.1-0.2 秒音频）。

示例（伪代码）：

```cpp
// 发送第 5 个普通 chunk (非 final)
uint8_t msg[5 + 6400];
msg[0] = 0x00;
msg[1] = 0x00;
msg[2] = 0x00;
msg[3] = 0x05;  // chunk_index = 5
msg[4] = 0x00;  // flags: is_final=0
memcpy(msg + 5, pcm_data, 6400);
ws.sendBinary(msg, 5 + 6400);

// 发送 final chunk (chunk_index = 47)
msg[0] = 0x00;
msg[1] = 0x00;
msg[2] = 0x00;
msg[3] = 0x2F;  // 47
msg[4] = 0x01;  // flags: is_final=1
memcpy(msg + 5, last_pcm_data, remaining_size);
ws.sendBinary(msg, 5 + remaining_size);
```

### 2.2 服务器 → 客户端（文本 JSON）

普通 ACK（成功）：

```json
{
  "ok": true,
  "chunk_index": 5
}
```

错误响应（乱序示例）：

```json
{
  "ok": false,
  "error": "Out of order chunk",
  "received_index": 10,
  "expected": 8,
  "message": "Expected chunk 8 but received 10"
}
```

Final ACK（完成）：

```json
{
  "final": true,
  "audio_url": "http://43.142.49.126:9000/media/46973_24865.wav",
  "session_id": "46973_24865",
  "total_chunks": 48,
  "total_bytes": 307200
}
```

兼容性说明（建议客户端兼容解析）：

- 部分服务端实现可能使用 `expected_next_index` 字段代替 `expected`。
- Final ACK 可能同时带 `ok:true` 或仅带 `final:true`；客户端建议以 `final:true` 为完成条件。

---

## 3. 状态机与流程

### 3.1 正常上传流程

```
[ESP32]                           [Server]
   |                                  |
   |--- WebSocket Connect ----------->|
   |<-- Accept -----------------------|
   |                                  |
   |--- Chunk 0 (flags=0x00) -------->|
   |<-- {"ok":true,"chunk_index":0} -|
   |                                  |
   |--- Chunk 1 (flags=0x00) -------->|
   |<-- {"ok":true,"chunk_index":1} -|
   |                                  |
   |         ... (continue) ...       |
   |                                  |
   |--- Chunk N (flags=0x01) -------->|
   |<-- {"final":true,"audio_url":...}|
   |                                  |
   |--- Disconnect ------------------->|
```

### 3.2 状态追踪（客户端必须实现）

建议客户端内部维护至少以下状态：

```cpp
class UploadState {
public:
    uint32_t nextChunkToSend = 0;        // 下一个要发送的 chunk
    int32_t lastAckedChunk = -1;         // 最后确认的 chunk（用有符号类型便于 -1）
    uint32_t totalChunksSent = 0;        // 已发送总数
    bool uploadComplete = false;         // 上传完成标志
    String audioUrl;                     // 返回的音频URL
};
```

---

## 4. 错误处理与重试

### 4.1 顺序错误处理

当服务器返回 `expected`（或 `expected_next_index`）字段时，表示服务器当前期望的 chunk index。

```cpp
void handleServerResponse(const String& response) {
    DynamicJsonDocument doc(512);
    deserializeJson(doc, response);

    if (doc["ok"] == false) {
        uint32_t expected = doc.containsKey("expected")
            ? doc["expected"].as<uint32_t>()
            : doc["expected_next_index"].as<uint32_t>();

        Serial.printf("Out of order! Server expects chunk %u\n", expected);
        nextChunkToSend = expected;
        // 如果有缓存，从 expected 开始重发
    } else if (doc["ok"] == true) {
        uint32_t acked = doc["chunk_index"].as<uint32_t>();
        lastAckedChunk = (int32_t)acked;
        nextChunkToSend = acked + 1;
        Serial.printf("Chunk %u confirmed\n", acked);
    } else if (doc["final"] == true) {
        uploadComplete = true;
        audioUrl = doc["audio_url"].as<String>();
        Serial.printf("Upload complete! URL: %s\n", audioUrl.c_str());
    }
}
```

### 4.2 WebSocket 断线重连

推荐使用退避策略，避免短时间疯狂重连：

```cpp
void onWebSocketDisconnect() {
    Serial.println("WebSocket disconnected");

    int retryDelay = min(reconnectAttempts * 1000, 10000);  // 最多 10 秒
    reconnectAttempts++;

    vTaskDelay(pdMS_TO_TICKS(retryDelay));
    reconnectWebSocket();
}

void onWebSocketConnect() {
    Serial.println("WebSocket connected");
    reconnectAttempts = 0;

    // 从上次确认的位置继续发送
    if (lastAckedChunk >= 0) {
        nextChunkToSend = (uint32_t)lastAckedChunk + 1;
        Serial.printf("Resuming from chunk %u\n", nextChunkToSend);
    }
}
```

### 4.3 超时处理

发送 chunk 后应等待 ACK，超时应重试；ACK 超时时间需要覆盖网络抖动与服务端处理延迟。

```cpp
#define ACK_TIMEOUT_MS 5000

void sendChunkWithTimeout(uint32_t index, const uint8_t* data, size_t size, bool isFinal) {
    sendChunk(index, data, size, isFinal);

    uint32_t startTime = millis();
    while (!ackReceived && (millis() - startTime < ACK_TIMEOUT_MS)) {
        vTaskDelay(pdMS_TO_TICKS(10));
    }

    if (!ackReceived) {
        Serial.printf("Timeout waiting for ACK of chunk %u, retrying...\n", index);
        sendChunkWithTimeout(index, data, size, isFinal);
    }
}
```

---

## 5. 关键实现要点

### 5.1 必须实现

- 顺序追踪：维护 `lastAckedChunk`，每次 ACK 更新，final chunk 的 index 必须为 `lastAckedChunk + 1`
- ACK 等待：发送 chunk 后等待服务器 ACK，不要无节制地连续发送
- 错误处理：解析 `{"ok": false, ...}` 并根据 `expected/expected_next_index` 调整发送位置
- Final chunk 标记：确保 `flags` 的 bit0 = 1

### 5.2 强烈建议

- 背压控制：上传队列接近满时暂停采集或丢弃实时采样，避免丢“队列里的 chunk”导致乱序
- 断线恢复：保存上传状态，重连后从最后确认的位置继续
- 日志记录：打印 chunk index、队列深度、丢弃计数、ACK 延迟

### 5.3 可选优化

- 小缓冲区（保留最近 5-10 个 chunk）用于断线/乱序快速恢复
- 根据 ACK 延迟动态调整发送节奏
- 带宽受限时可考虑压缩（例如 ADPCM）或降采样

---

## 6. 音频参数要求

| 参数 | 值 | 说明 |
|---|---:|---|
| 采样率 | 16000 Hz | 固定，服务器期望值 |
| 位深度 | 16 bit | signed |
| 声道数 | 1 | mono |
| 字节序 | Little-endian | `s16le` |
| 每片大小 | 3200-6400 bytes | 建议 0.1-0.2 秒 |

计算公式：

- 每秒字节数 = 采样率 × (位深度/8) × 声道数 = 16000 × 2 × 1 = 32000 字节/秒

---

## 7. 常见问题 FAQ

- Q: 收到 "Out of order chunk"？
  - A: chunk index 与服务器期望不符。检查是否跳号、是否丢了队列里的 chunk、重连后是否从正确位置续传。

- Q: Final chunk 被拒绝？
  - A: final 的 index 必须等于最后成功 ACK 的 chunk + 1。

- Q: 队列一直满、dropped 很高？
  - A: 采集速度大于上传速度。加背压，或降低数据量（需与服务端确认）。

- Q: 如何确认上传成功？
  - A: 必须收到 `{"final": true, "audio_url": "..."}`，并可访问返回的 URL 下载 WAV 验证。

---

## 8. 完整示例代码框架（概念）

```cpp
static uint32_t g_nextChunk = 0;
static int32_t g_lastAcked = -1;
static bool g_uploadComplete = false;

void onWSMessage(uint8_t* payload, size_t length) {
    String response = String((char*)payload);

    DynamicJsonDocument doc(512);
    deserializeJson(doc, response);

    if (doc["ok"] == false) {
        uint32_t expected = doc.containsKey("expected")
            ? doc["expected"].as<uint32_t>()
            : doc["expected_next_index"].as<uint32_t>();
        g_nextChunk = expected;
    } else if (doc["ok"] == true) {
        g_lastAcked = doc["chunk_index"].as<uint32_t>();
        g_nextChunk = (uint32_t)g_lastAcked + 1;
    } else if (doc["final"] == true) {
        g_uploadComplete = true;
        String url = doc["audio_url"].as<String>();
        Serial.printf("Complete! URL: %s\n", url.c_str());
    }
}

void sendChunk(const uint8_t* pcmData, size_t size, bool isFinal) {
    uint32_t index = g_nextChunk;

    uint8_t msg[5 + size];
    msg[0] = (index >> 24) & 0xFF;
    msg[1] = (index >> 16) & 0xFF;
    msg[2] = (index >> 8) & 0xFF;
    msg[3] = index & 0xFF;
    msg[4] = isFinal ? 0x01 : 0x00;
    memcpy(msg + 5, pcmData, size);

    webSocket.sendBinary(msg, 5 + size);
}
```

---

## 9. 版本历史

| 版本 | 日期 | 说明 |
|---|---|---|
| v1.0 | 2026-02-09 | 初始版本 |

---

## 10. 技术支持

如需服务端日志定位问题（示例）：

```bash
ssh ubuntu@43.142.49.126
sudo docker logs -f family-backend | grep WS
```

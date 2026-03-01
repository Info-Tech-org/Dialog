# PCM Ingest API 规范

硬件 PCM 分片直传协议 - 生产环境稳定版

## 端点

```
POST http://47.236.106.225:9000/api/ingest/pcm
```

## Headers（必填）

| Header | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `X-Device-Token` | string | 设备令牌（生产必需） | `<YOUR_TOKEN>` |
| `X-Session-Id` | string | 会话ID（UUID），一次录音复用 | `550e8400-e29b-41d4-a716-446655440000` |
| `X-Chunk-Index` | int | 分片序号，从0开始递增 | `0`, `1`, `2`... |
| `X-Is-Final` | string | 是否最后一片 | `0` 或 `1` |
| `X-Sample-Rate` | int | 采样率 | `16000` |
| `X-Channels` | int | 声道数 | `1` |
| `X-Bit-Depth` | int | 位深度 | `16` |
| `X-PCM-Format` | string | PCM格式 | `s16le` |
| `Content-Type` | string | 固定值 | `application/octet-stream` |

**可选 Headers:**
- `X-Device-Id`: 设备标识
- `X-Filename`: 文件名（保留）

## 请求体

Raw PCM 二进制数据（Body 直接是音频字节）

**推荐分片大小:**
- 100ms = 3200 bytes (16kHz × 16bit × 1ch × 0.1s)
- 200ms = 6400 bytes

## 响应格式

### 普通分片响应 (200 OK)
```json
{
  "ok": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "chunk": 5,
  "received_bytes": 19200
}
```

### 最终分片响应 (200 OK)
```json
{
  "ok": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "final": true,
  "audio_url": "http://47.236.106.225:9000/media/550e8400-e29b-41d4-a716-446655440000.wav",
  "received_bytes": 64000,
  "chunks": 20
}
```

### 错误响应

**401 Unauthorized** - 缺少或错误的 token
```json
{
  "detail": "Unauthorized: Invalid or missing device token"
}
```

**409 Conflict** - 乱序分片
```json
{
  "detail": {
    "error": "Out of order chunk",
    "received_index": 5,
    "expected_next_index": 3,
    "message": "Expected chunk 3 but received 5"
  }
}
```

**400 Bad Request** - 不支持的格式
```json
{
  "detail": "Unsupported PCM format (only 16kHz/16bit/mono/s16le)"
}
```

## 幂等性与重试

### 语义幂等
- **幂等键**: `(X-Session-Id, X-Chunk-Index)`
- **重复分片**: 同一 `chunk_index < expected_next` → 200 OK (不重复写入)
- **顺序要求**: chunk_index 必须严格递增 (0, 1, 2...)

### 重试策略
1. 网络失败时可安全重试同一分片（相同 index + payload）
2. 最多重试 3 次
3. 持续失败应中止会话并记录日志

## cURL 示例

### 发送单个分片

```bash
# 生成测试PCM (100ms)
dd if=/dev/urandom of=chunk_0.pcm bs=3200 count=1

# 发送分片0
curl -X POST http://47.236.106.225:9000/api/ingest/pcm \
  -H "X-Device-Token: <YOUR_TOKEN>" \
  -H "X-Session-Id: 550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Chunk-Index: 0" \
  -H "X-Is-Final: 0" \
  -H "X-Sample-Rate: 16000" \
  -H "X-Channels: 1" \
  -H "X-Bit-Depth: 16" \
  -H "X-PCM-Format: s16le" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @chunk_0.pcm
```

### 发送最终分片

```bash
curl -X POST http://47.236.106.225:9000/api/ingest/pcm \
  -H "X-Device-Token: <YOUR_TOKEN>" \
  -H "X-Session-Id: 550e8400-e29b-41d4-a716-446655440000" \
  -H "X-Chunk-Index: 19" \
  -H "X-Is-Final: 1" \
  -H "X-Sample-Rate: 16000" \
  -H "X-Channels: 1" \
  -H "X-Bit-Depth: 16" \
  -H "X-PCM-Format: s16le" \
  -H "Content-Type: application/octet-stream" \
  --data-binary @chunk_19.pcm
```

## Python 示例

```python
import uuid
import httpx

BASE_URL = "http://47.236.106.225:9000"
TOKEN = "<YOUR_TOKEN>"
SESSION_ID = str(uuid.uuid4())
CHUNK_SIZE = 3200  # 100ms

def send_chunk(data: bytes, index: int, is_final: bool):
    headers = {
        "X-Device-Token": TOKEN,
        "X-Session-Id": SESSION_ID,
        "X-Chunk-Index": str(index),
        "X-Is-Final": "1" if is_final else "0",
        "X-Sample-Rate": "16000",
        "X-Channels": "1",
        "X-Bit-Depth": "16",
        "X-PCM-Format": "s16le",
        "Content-Type": "application/octet-stream",
    }

    response = httpx.post(
        f"{BASE_URL}/api/ingest/pcm",
        headers=headers,
        content=data,
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()

# 读取PCM文件并分片发送
with open("audio.pcm", "rb") as f:
    pcm_data = f.read()

total_chunks = (len(pcm_data) + CHUNK_SIZE - 1) // CHUNK_SIZE

for i in range(total_chunks):
    start = i * CHUNK_SIZE
    end = min(start + CHUNK_SIZE, len(pcm_data))
    chunk = pcm_data[start:end]
    is_final = (i == total_chunks - 1)

    result = send_chunk(chunk, i, is_final)
    print(f"Chunk {i}: {result}")

    if is_final:
        print(f"✅ Upload complete: {result['audio_url']}")
```

## ESP32 示例（C++）

```cpp
#include <WiFi.h>
#include <HTTPClient.h>

const char* BASE_URL = "http://47.236.106.225:9000/api/ingest/pcm";
const char* DEVICE_TOKEN = "<YOUR_TOKEN>";
String sessionId;

void setup() {
    Serial.begin(115200);
    WiFi.begin("SSID", "PASSWORD");
    while (WiFi.status() != WL_CONNECTED) delay(500);

    // Generate session ID once per recording
    sessionId = generateUUID();
}

void sendPCMChunk(uint8_t* data, size_t length, int chunkIndex, bool isFinal) {
    HTTPClient http;
    http.begin(BASE_URL);

    // Set headers
    http.addHeader("X-Device-Token", DEVICE_TOKEN);
    http.addHeader("X-Session-Id", sessionId);
    http.addHeader("X-Chunk-Index", String(chunkIndex));
    http.addHeader("X-Is-Final", isFinal ? "1" : "0");
    http.addHeader("X-Sample-Rate", "16000");
    http.addHeader("X-Channels", "1");
    http.addHeader("X-Bit-Depth", "16");
    http.addHeader("X-PCM-Format", "s16le");
    http.addHeader("Content-Type", "application/octet-stream");

    // Send PCM data
    int httpCode = http.POST(data, length);

    if (httpCode == 200) {
        String response = http.getString();
        Serial.println("Chunk " + String(chunkIndex) + " sent: " + response);

        if (isFinal) {
            // Parse audio_url from response
            Serial.println("✅ Recording complete!");
        }
    } else {
        Serial.println("❌ HTTP Error: " + String(httpCode));
        // Implement retry logic here
    }

    http.end();
}

void loop() {
    // Read from I2S microphone (100ms buffer)
    int16_t i2sBuffer[1600]; // 16kHz * 0.1s
    size_t bytesRead = i2sRead(I2S_NUM_0, i2sBuffer, sizeof(i2sBuffer));

    static int chunkIndex = 0;
    bool isFinal = false; // Set to true when recording ends

    sendPCMChunk((uint8_t*)i2sBuffer, bytesRead, chunkIndex++, isFinal);

    delay(100); // 100ms per chunk
}
```

## 状态查询

### 实时状态（可选）
```bash
GET http://47.236.106.225:9000/api/ingest/status/{session_id}
```

**注意**: 此端点为 best-effort，仅在处理期间可用。完成后应使用 Sessions API。

### 最终结果（推荐）
```bash
GET http://47.236.106.225:9000/api/sessions/{session_id}
```

返回完整会话信息（audio_url + utterances + harmful_count）。

## 常见问题

### Q: 如何获取 DEVICE_TOKEN?
A: 联系后端管理员获取，token 通过环境变量 `DEVICE_INGEST_TOKEN` 配置。

### Q: 可以跳过某些 chunk 吗?
A: 不可以，chunk_index 必须严格从 0 开始递增。乱序会返回 409。

### Q: 重试时需要重新生成 PCM 数据吗?
A: 不需要，使用相同的 chunk_index 和 payload 重发即可（幂等）。

### Q: 支持其他采样率吗?
A: MVP 版本仅支持 16kHz/16bit/mono/s16le，其他格式返回 400。

### Q: 上传后多久能获取结果?
A: WAV 组装立即完成，ASR 处理约 5-10 秒。建议轮询 /api/sessions/{id} 直到包含 audio_url。

---

**文档版本**: 1.0
**最后更新**: 2025-12-24
**生产地址**: http://47.236.106.225:9000

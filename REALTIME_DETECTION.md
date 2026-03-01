# 实时语音识别 + 有害检测 WebSocket API

## 概述

实时 WebSocket 端点提供流式语音识别和有害内容实时检测功能。设备通过 WebSocket 连接发送 PCM 音频流，服务器实时返回：
- ASR 识别结果（使用腾讯云实时语音识别）
- 有害内容警告（检测到骂人、威胁等语言时立即告警）

## WebSocket 端点

```
ws://your-server:8000/ws/realtime/stream
```

### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `device_token` | string | 否 | 设备认证 token（如果服务器配置了 DEVICE_INGEST_TOKEN） |
| `session_id` | string | 否 | 会话 ID（不提供则服务器自动生成） |
| `device_id` | string | 否 | 设备 ID（用于标识设备） |

### 示例 URL

```
ws://play.devc.me:8000/ws/realtime/stream?device_id=esp32_001
```

## 音频格式要求

- **格式**: PCM (s16le)
- **采样率**: 16000 Hz
- **声道**: 单声道 (mono)
- **位深**: 16-bit
- **字节序**: Little Endian

## 通信协议

### 设备 → 服务器（发送音频）

设备发送**纯二进制 PCM 音频数据**，无需任何协议头。

**建议**：
- 每次发送 100ms 的音频数据（3200 字节 = 16000 Hz × 0.1s × 2 bytes）
- 实时流式发送，模拟真实录音场景

### 服务器 → 设备（返回消息）

服务器返回 **JSON 格式**消息，包含以下类型：

#### 1. 状态消息

连接成功后立即发送：

```json
{
  "type": "status",
  "message": "实时识别已启动",
  "session_id": "rt_esp32_001_1234567890123",
  "timestamp": 1234567890.123
}
```

#### 2. ASR 识别结果

每当识别到语音内容时发送：

```json
{
  "type": "asr",
  "text": "识别的文本内容",
  "is_final": false,
  "start": 0.5,
  "end": 1.2,
  "timestamp": 1234567890.456
}
```

**字段说明**：
- `text`: 识别的文本
- `is_final`: 是否为最终结果（true=一句话结束，false=中间结果）
- `start`: 相对开始时间（秒）
- `end`: 相对结束时间（秒）

#### 3. 有害内容警告 ⚠️

检测到有害语言时**立即**发送：

```json
{
  "type": "harmful_alert",
  "text": "你个废物",
  "keywords": ["废物"],
  "severity": 3,
  "method": "keyword",
  "timestamp": 1234567890.789,
  "action": "warning"
}
```

**字段说明**：
- `text`: 检测到的有害文本
- `keywords`: 匹配的有害关键词列表
- `severity`: 严重度（1-5，数字越大越严重）
- `method`: 检测方法（"keyword" 或 "llm"）
- `action`: 建议动作（"warning" 或 "block"）

**设备接收到此消息后应该**：
- 发出警报（蜂鸣器、LED 灯）
- 显示提示信息
- 记录日志
- 可选：暂停录音或提醒用户

#### 4. 错误消息

发生错误时发送：

```json
{
  "type": "error",
  "message": "ASR连接失败: 认证失败"
}
```

## 有害关键词列表

系统检测以下类型的有害语言：

### 侮辱性词汇
没用、废物、蠢、笨蛋、白痴、傻子、混蛋、垃圾、窝囊废、丢人、丢脸、羞耻等

### 脏话粗口
各类脏话和粗口

### 威胁性语言
滚出去、闭嘴、打死你、去死、滚、揍你、杀了你、不要你了等

### 情感伤害
讨厌你、后悔生你、不爱你、恨你、烦死了、看见你就烦等

### 否定贬低
就知道、永远不会、从来没有、一点用都没有、什么都不会等

## 使用示例

### Python 客户端示例

```python
import asyncio
import websockets
import numpy as np

async def realtime_detection_client():
    url = "ws://play.devc.me:8000/ws/realtime/stream?device_id=my_device"

    async with websockets.connect(url) as websocket:
        # 接收状态消息
        status = await websocket.recv()
        print(f"状态: {status}")

        # 创建并发任务
        async def send_audio():
            # 生成或读取 PCM 音频数据
            # 这里用正弦波作为示例
            sample_rate = 16000
            duration = 5.0  # 5秒
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            wave = np.sin(440 * 2 * np.pi * t)
            pcm_data = (wave * 32767).astype(np.int16).tobytes()

            # 分块发送
            chunk_size = 3200  # 100ms
            for i in range(0, len(pcm_data), chunk_size):
                chunk = pcm_data[i:i + chunk_size]
                await websocket.send(chunk)
                await asyncio.sleep(0.1)  # 模拟实时流

        async def receive_messages():
            async for message in websocket:
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "asr":
                    print(f"ASR: {data['text']}")

                elif msg_type == "harmful_alert":
                    print(f"⚠️ 警告: 检测到有害内容!")
                    print(f"   文本: {data['text']}")
                    print(f"   关键词: {data['keywords']}")
                    # 触发警报
                    trigger_alarm()

        # 并发运行
        await asyncio.gather(send_audio(), receive_messages())

asyncio.run(realtime_detection_client())
```

### ESP32 示例（伪代码）

```cpp
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <driver/i2s.h>

WebSocketsClient webSocket;

void onWebSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    switch(type) {
        case WStype_TEXT: {
            // 解析 JSON 消息
            DynamicJsonDocument doc(1024);
            deserializeJson(doc, payload);

            String msgType = doc["type"];

            if (msgType == "harmful_alert") {
                // 触发警报
                digitalWrite(LED_PIN, HIGH);
                digitalWrite(BUZZER_PIN, HIGH);
                delay(500);
                digitalWrite(LED_PIN, LOW);
                digitalWrite(BUZZER_PIN, LOW);

                Serial.println("⚠️ 检测到有害语言!");
                Serial.print("内容: ");
                Serial.println(doc["text"].as<String>());
            }
            else if (msgType == "asr") {
                Serial.print("识别: ");
                Serial.println(doc["text"].as<String>());
            }
            break;
        }
    }
}

void setup() {
    // WiFi 连接
    WiFi.begin(ssid, password);

    // WebSocket 连接
    webSocket.begin("play.devc.me", 8000, "/ws/realtime/stream?device_id=esp32_001");
    webSocket.onEvent(onWebSocketEvent);

    // I2S 麦克风初始化
    i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
    i2s_set_pin(I2S_NUM_0, &pin_config);
}

void loop() {
    webSocket.loop();

    // 读取麦克风数据（PCM 16-bit, 16kHz）
    size_t bytes_read;
    uint8_t buffer[3200];  // 100ms = 3200 bytes
    i2s_read(I2S_NUM_0, buffer, sizeof(buffer), &bytes_read, portMAX_DELAY);

    // 发送音频数据
    webSocket.sendBIN(buffer, bytes_read);

    delay(100);  // 100ms
}
```

## 测试工具

项目提供了测试脚本 `tools/test_realtime_detection.py`：

```bash
# 使用测试音频（正弦波）
python3 tools/test_realtime_detection.py --url ws://play.devc.me:8000

# 使用真实 PCM 文件
python3 tools/test_realtime_detection.py \
  --url ws://play.devc.me:8000 \
  --pcm-file /path/to/audio.pcm \
  --device-id test_device
```

## 性能指标

- **延迟**: < 500ms（从说话到收到 ASR 结果）
- **有害检测延迟**: < 100ms（关键词匹配）
- **并发连接数**: 取决于服务器配置和腾讯云配额

## 注意事项

1. **音频格式严格要求**: 必须是 16kHz, 16-bit, mono PCM
2. **实时流式发送**: 建议每 100ms 发送一次数据
3. **认证**: 生产环境建议配置 `DEVICE_INGEST_TOKEN`
4. **腾讯云配置**: 需要在 `.env` 中配置腾讯云密钥：
   ```
   TENCENT_SECRET_ID=your_secret_id
   TENCENT_SECRET_KEY=your_secret_key
   ```
5. **会话管理**: 每个 WebSocket 连接对应一个会话，断开连接会自动保存会话数据到数据库

## 数据库记录

实时会话结束后，系统会自动保存：
- **Session 表**: 会话信息（session_id, device_id, 开始/结束时间, 有害内容数量）
- **Utterance 表**: 每一句话的识别结果和有害标记

可以通过 API 查询历史记录：
```
GET /api/sessions
GET /api/sessions/{session_id}
GET /api/utterances?session_id={session_id}
```

## 监控端点

查看当前活跃的实时会话：
```
GET /ws/realtime/active
```

返回示例：
```json
{
  "active_count": 2,
  "sessions": [
    {
      "session_id": "rt_esp32_001_1234567890",
      "device_id": "esp32_001",
      "start_time": "2025-01-01T00:00:00",
      "utterances_count": 5,
      "harmful_count": 1,
      "asr_connected": true
    }
  ]
}
```

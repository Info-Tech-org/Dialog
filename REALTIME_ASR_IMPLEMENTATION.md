# 实时 ASR + 有害检测 WebSocket 实现文档

## 概述

本文档描述了完整的"实时 ASR + 实时有害检测 + 实时反馈"WebSocket 链路实现。

### 功能特性

1. **WebSocket 实时通信** - `/ws` 端点支持双向通信
2. **腾讯云实时 ASR 集成** - WebSocket 客户端连接腾讯云实时语音识别
3. **二层有害检测**
   - 第一层：关键词匹配（快速）
   - 第二层：OpenRouter + Gemma3:27b 语义分析（精准）
4. **实时反馈**
   - `asr_result` - 每个识别结果（部分 + 最终）
   - `alert` - 有害内容警告（severity ≥ 3）
5. **状态管理** - 内存 + 数据库同步存储
6. **音频文件生成** - WAV 格式（16kHz/16bit/mono）

---

## 架构设计

### 协议流程

```
Client (ESP32/Test)         Server (/ws)              Tencent ASR         OpenRouter
      |                          |                          |                    |
      | 1. {"type":"start_session", "device_id":"..."}      |                    |
      |------------------------->|                          |                    |
      |                          | connect(voice_id)        |                    |
      |                          |------------------------>|                    |
      | 2. {"type":"session_started", "session_id":"..."}   |                    |
      |<-------------------------|                          |                    |
      |                          |                          |                    |
      | 3. PCM chunks (binary)   |                          |                    |
      |------------------------->| send_audio()             |                    |
      |                          |------------------------>|                    |
      |                          |                          |                    |
      |                          | <-- ASR result (partial) |                    |
      | 4. {"type":"asr_result", "text":"...", "is_final":false}                 |
      |<-------------------------|                          |                    |
      |                          |                          |                    |
      |                          | <-- ASR result (final)   |                    |
      |                          | keyword_match()          |                    |
      |                          |---------------------------------------->       |
      |                          |                          |  detect(text)      |
      |                          | <-- {"is_harmful":true, "severity":4} --------|
      | 5. {"type":"asr_result", "text":"...", "is_final":true}                  |
      |<-------------------------|                          |                    |
      | 6. {"type":"alert", "severity":4, "explanation":"..."}                   |
      |<-------------------------|                          |                    |
      |                          |                          |                    |
      | 7. {"type":"end_session"}|                          |                    |
      |------------------------->| disconnect()             |                    |
      |                          |------------------------>|                    |
      |                          | save_to_db()             |                    |
      | 8. {"type":"session_ended", "harmful_count":1, "utterance_count":5}      |
      |<-------------------------|                          |                    |
```

### 消息格式

#### 上行（Client → Server）

**start_session**
```json
{
  "type": "start_session",
  "device_id": "esp32_001"
}
```

**PCM 音频数据**
- 格式: binary (bytes)
- 编码: 16kHz, 16-bit, mono, s16le
- 建议块大小: 3200 bytes (200ms @ 16kHz)

**end_session**
```json
{
  "type": "end_session"
}
```

#### 下行（Server → Client）

**session_started**
```json
{
  "type": "session_started",
  "session_id": "uuid-v4"
}
```

**asr_result**
```json
{
  "type": "asr_result",
  "text": "识别到的文本",
  "is_final": true,  // true=最终结果, false=部分结果
  "start": 1.2,      // 开始时间（秒）
  "end": 3.5         // 结束时间（秒）
}
```

**alert**（仅 severity ≥ 3 时发送）
```json
{
  "type": "alert",
  "severity": 4,             // 1-5（5最严重）
  "text": "触发警告的原文",
  "category": "辱骂",        // 类别：辱骂/威胁/贬低等
  "explanation": "包含侮辱性词汇，可能伤害孩子自尊心"
}
```

**session_ended**
```json
{
  "type": "session_ended",
  "session_id": "uuid-v4",
  "harmful_count": 2,
  "utterance_count": 10
}
```

---

## 核心组件

### 1. WebSocket Handler
**文件**: `backend/ingest/websocket_server.py`

**职责**:
- 接受 WebSocket 连接
- 管理会话生命周期
- 协调各组件协作

**关键逻辑**:
```python
# 接收音频 → 写入文件
await audio_writer.write_audio(audio_data)

# 发送到 ASR
await asr_client.send_audio(audio_data)

# 获取识别结果（非阻塞）
asr_result = await asr_client.get_text()

# 发送 ASR 结果给客户端
await websocket.send_json({"type": "asr_result", ...})

# 有害检测（仅对最终结果）
if is_final:
    keyword_harmful = is_harmful(text)
    llm_result = await llm_detector.detect(text)

    # severity >= 3 才发送警告
    if harmful_flag and severity >= 3:
        await websocket.send_json({"type": "alert", ...})
```

### 2. Tencent Real-time ASR Client
**文件**: `backend/realtime/tencent_asr.py`

**职责**:
- WebSocket 客户端连接腾讯云 ASR
- 生成鉴权签名
- 发送音频帧
- 接收识别结果（异步队列）

**关键方法**:
- `connect(voice_id)` - 连接 ASR 服务
- `send_audio(data)` - 发送 PCM 数据
- `get_text()` - 非阻塞获取结果
- `disconnect()` - 断开连接

### 3. Harmful Detector (Two-Layer)
**文件**:
- `backend/realtime/harmful_rules.py` - 关键词层
- `backend/realtime/llm_harmful_detector.py` - LLM 层

**检测流程**:
1. **第一层**: 关键词快速匹配
   - 包含 HARMFUL_KEYWORDS → 直接判定有害
   - 未命中 → 进入第二层

2. **第二层**: LLM 语义分析
   - 调用 OpenRouter API (Gemma3:27b)
   - Prompt: "你是一个家庭沟通分析专家..."
   - 返回: `{is_harmful, severity, category, explanation}`
   - **阈值**: severity ≥ 3 才认为有害

**Severity 定义**:
- 1-2: 轻微（不触发警告）
- 3: 中等（触发警告）
- 4: 严重（触发警告）
- 5: 非常严重（触发警告）

### 4. Audio Writer
**文件**: `backend/ingest/audio_writer.py`

**职责**:
- 创建 WAV 文件并写入 PCM 数据
- 实时更新 WAV header 大小

**WAV 格式**:
- Sample rate: 16000 Hz
- Bit depth: 16 bit
- Channels: 1 (mono)
- Format: PCM (s16le)

**Header 更新**:
- 初始写入占位符 header (data_size=0)
- 记录写入的字节数 (`bytes_written`)
- 停止录制时更新 RIFF 和 data chunk 大小

### 5. Session Manager
**文件**: `backend/ingest/session_manager.py`

**职责**:
- 创建会话（生成 UUID）
- 内存缓存活动会话
- 保存会话到数据库

### 6. Database Models
**文件**:
- `backend/models/session_model.py` - Session 表
- `backend/models/utterance_model.py` - Utterance 表

**Schema**:
```sql
-- sessions 表
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    device_id TEXT,
    start_time DATETIME,
    end_time DATETIME,
    audio_path TEXT,
    harmful_count INTEGER DEFAULT 0,
    cos_key TEXT
);

-- utterances 表
CREATE TABLE utterances (
    id TEXT PRIMARY KEY,
    session_id TEXT FOREIGN KEY REFERENCES sessions(session_id),
    start REAL,        -- 开始时间（秒）
    end REAL,          -- 结束时间（秒）
    speaker TEXT,      -- 说话人（A/B）
    text TEXT,         -- 识别文本
    harmful_flag BOOLEAN DEFAULT FALSE
);
```

**数据流**:
1. start_session → 创建 Session 记录
2. 每个最终 ASR 结果 → 缓存到 `utterances_buffer`
3. end_session → 批量写入 Utterance 记录 + 更新 Session

---

## 测试指南

### 本地测试（模拟音频）

```bash
# 1. 启动后端服务
cd backend
python main.py

# 2. 在另一个终端运行测试客户端
cd tools
python test_websocket_realtime.py --url ws://localhost:8000/ws --duration 10.0
```

**预期输出**:
```
2025-12-24 12:00:00 - INFO - Connected to ws://localhost:8000/ws
2025-12-24 12:00:00 - INFO - Starting session for device: test_client
2025-12-24 12:00:00 - INFO - ✅ Session started: abc-123-def-456
2025-12-24 12:00:00 - INFO - Generating 10.0s of audio (50 chunks)
2025-12-24 12:00:01 - INFO - Sent 10/50 chunks (2.0s)
2025-12-24 12:00:02 - INFO - ⚪ ASR: "你好" (final=False)
2025-12-24 12:00:03 - INFO - 🔵 ASR: "你好，我是" (final=True)
2025-12-24 12:00:04 - WARNING - 🚨 ALERT (severity=4): "你这个笨蛋"
2025-12-24 12:00:04 - WARNING -    Category: 辱骂
2025-12-24 12:00:04 - WARNING -    Explanation: 包含侮辱性词汇
...
2025-12-24 12:00:10 - INFO - ✅ Session ended: abc-123-def-456
2025-12-24 12:00:10 - INFO -    Harmful count: 2
2025-12-24 12:00:10 - INFO -    Utterance count: 8
```

### 使用真实音频文件测试

```bash
# WAV 文件要求: 16kHz, 16-bit, mono
python test_websocket_realtime.py \
    --url ws://localhost:8000/ws \
    --audio /path/to/test.wav
```

### 生产环境测试

```bash
python test_websocket_realtime.py \
    --url ws://47.236.106.225:9000/ws \
    --duration 10.0
```

### 验证数据库记录

```bash
# 进入 Python REPL
cd backend
python

>>> from models import Session, Utterance, engine
>>> from sqlmodel import Session as DBSession, select
>>>
>>> with DBSession(engine) as db:
>>>     # 查询最近的 session
>>>     session = db.exec(select(Session).order_by(Session.start_time.desc())).first()
>>>     print(f"Session: {session.session_id}")
>>>     print(f"Harmful count: {session.harmful_count}")
>>>
>>>     # 查询 utterances
>>>     utterances = db.exec(select(Utterance).where(Utterance.session_id == session.session_id)).all()
>>>     for u in utterances:
>>>         print(f"[{u.start:.1f}s-{u.end:.1f}s] {u.speaker}: {u.text} (harmful={u.harmful_flag})")
```

**预期输出**:
```
Session: abc-123-def-456
Harmful count: 2
[0.0s-2.3s] A: 你好，今天天气不错 (harmful=False)
[2.5s-5.1s] A: 你这个笨蛋怎么连这都不会 (harmful=True)
[5.3s-7.8s] A: 好的，我知道了 (harmful=False)
...
```

---

## ESP32 硬件集成示例

### Arduino/ESP32 代码片段

```cpp
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

WebSocketsClient webSocket;
String sessionId = "";
bool sessionStarted = false;

void setup() {
    Serial.begin(115200);

    // Connect WiFi
    WiFi.begin("SSID", "PASSWORD");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }

    // Connect WebSocket
    webSocket.begin("47.236.106.225", 9000, "/ws");
    webSocket.onEvent(webSocketEvent);
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
    if (type == WStype_CONNECTED) {
        Serial.println("WebSocket Connected");

        // Send start_session
        StaticJsonDocument<200> doc;
        doc["type"] = "start_session";
        doc["device_id"] = "esp32_001";

        String json;
        serializeJson(doc, json);
        webSocket.sendTXT(json);

    } else if (type == WStype_TEXT) {
        StaticJsonDocument<500> doc;
        deserializeJson(doc, payload);

        String msgType = doc["type"];

        if (msgType == "session_started") {
            sessionId = doc["session_id"].as<String>();
            sessionStarted = true;
            Serial.println("Session started: " + sessionId);

        } else if (msgType == "asr_result") {
            String text = doc["text"];
            bool isFinal = doc["is_final"];
            Serial.printf("ASR: %s (final=%d)\n", text.c_str(), isFinal);

        } else if (msgType == "alert") {
            int severity = doc["severity"];
            String text = doc["text"];

            // 触发振动
            triggerVibration(severity);

            Serial.printf("ALERT [%d]: %s\n", severity, text.c_str());
        }
    }
}

void triggerVibration(int severity) {
    // severity 1-5: 振动强度/模式
    int vibrationMs = severity * 200;  // 200ms - 1000ms
    digitalWrite(VIBRATION_PIN, HIGH);
    delay(vibrationMs);
    digitalWrite(VIBRATION_PIN, LOW);
}

void loop() {
    webSocket.loop();

    if (sessionStarted) {
        // Read I2S microphone and send PCM chunks
        int16_t pcmBuffer[1600];  // 100ms @ 16kHz
        size_t bytesRead = i2s_read(I2S_NUM_0, pcmBuffer, sizeof(pcmBuffer), portMAX_DELAY);

        webSocket.sendBIN((uint8_t*)pcmBuffer, bytesRead);
        delay(50);  // 50ms between chunks
    }
}
```

---

## 性能指标

### 延迟分析

| 阶段 | 延迟 | 说明 |
|------|------|------|
| PCM 上传 | ~50ms | 按 200ms chunk 发送，网络延迟 |
| 腾讯 ASR | ~200-500ms | 实时识别，部分结果更快 |
| 关键词检测 | <1ms | 内存匹配 |
| LLM 检测 | ~1-3s | OpenRouter API 调用 |
| **总延迟** | ~1.5-4s | 从说话到收到警告 |

### 吞吐量

- **音频带宽**: 16kHz × 16bit × 1ch = 256 kbps
- **建议块大小**: 3200 bytes (200ms)
- **发送频率**: 5 chunks/s
- **并发连接**: 理论支持 100+ 设备（需测试验证）

---

## 故障排查

### 常见问题

**1. WebSocket 连接失败**
```
ERROR: Connection refused
```
**解决**:
- 检查后端服务是否启动: `curl http://localhost:8000/`
- 检查防火墙设置
- 生产环境确保 Caddy 配置正确转发 `/ws`

**2. ASR 无识别结果**
```
WARNING: ASR not connected, cannot send audio
```
**解决**:
- 检查腾讯云 secret_id/secret_key 配置
- 查看后端日志: `docker logs backend | grep ASR`
- 验证音频格式: 16kHz, 16-bit, mono, s16le

**3. LLM 检测失败**
```
ERROR: Error calling LLM API: 401 Unauthorized
```
**解决**:
- 检查 OpenRouter API key: `settings.openrouter_api_key`
- 验证 API 余额: https://openrouter.ai/credits
- 检查网络连接（国内可能需要代理）

**4. 数据库保存失败**
```
ERROR: Failed to save utterances: UNIQUE constraint failed
```
**解决**:
- 检查数据库文件权限
- 运行迁移: `python -c "from models.db import run_migrations; run_migrations()"`
- 重新创建数据库: `rm familymvp.db && python main.py`

---

## 配置参数

### 环境变量 (.env)

```bash
# 数据库
DATABASE_URL=sqlite:///./familymvp.db

# WebSocket
WS_HOST=0.0.0.0
WS_PORT=8000

# 腾讯云 ASR
TENCENT_SECRET_ID=AKIDxxx
TENCENT_SECRET_KEY=xxx
TENCENT_ASR_REGION=ap-guangzhou

# OpenRouter LLM
OPENROUTER_API_KEY=sk-or-v1-xxx
OPENROUTER_MODEL=google/gemma-2-27b-it

# 音频存储
AUDIO_STORAGE_PATH=./data/audio
PUBLIC_BASE_URL=http://47.236.106.225:9000
```

### 代码配置

**修改 ASR 模型**:
```python
# backend/realtime/tencent_asr.py
self.engine_model_type = "16k_zh"  # 可选: 8k_zh, 16k_en
```

**修改有害检测阈值**:
```python
# backend/ingest/websocket_server.py
if harmful_flag and severity >= 3:  # 改为 >= 4 提高阈值
```

**修改 LLM Prompt**:
```python
# backend/realtime/llm_harmful_detector.py
prompt = f"""你是一个家庭沟通分析专家..."""  # 自定义 prompt
```

---

## 部署检查清单

### 本地开发

- [ ] Python 3.9+ 已安装
- [ ] 依赖已安装: `pip install -r backend/requirements.txt`
- [ ] 数据库已创建: `python main.py` (首次运行)
- [ ] 测试脚本可执行: `python tools/test_websocket_realtime.py`

### 生产环境

- [ ] Docker Compose 配置已更新
- [ ] 环境变量已设置 (`.env` 文件)
- [ ] Caddy 已配置 WebSocket 转发: `proxy /ws localhost:8000`
- [ ] 防火墙已开放端口 9000
- [ ] 数据库已迁移: `run_migrations()`
- [ ] 音频存储目录已创建: `mkdir -p data/audio`
- [ ] 日志监控已启用: `docker logs -f backend`

---

## 未来优化方向

### 短期（P1）

1. **连接池管理** - 限制并发 WebSocket 连接数
2. **心跳检测** - 定期 ping/pong 保持连接活跃
3. **断线重连** - 客户端自动重连机制
4. **音频压缩** - Opus 编码减少带宽（需 ASR 支持）

### 中期（P2）

1. **说话人分离** - 实时多说话人识别（需 ASR 支持）
2. **情感分析** - 添加语气/情绪检测层
3. **历史上下文** - 结合过往对话判断有害性
4. **可配置规则** - Web UI 自定义关键词和阈值

### 长期（P3）

1. **端到端加密** - 音频数据加密传输
2. **离线模式** - 本地 ASR 模型（WhisperLive）
3. **边缘计算** - 部分检测逻辑下沉到设备端
4. **多语言支持** - 英文、粤语等

---

## 许可与声明

- **腾讯云 ASR**: 需要有效的腾讯云账号和 API 密钥
- **OpenRouter API**: 需要有效的 API key 和余额
- **音频数据**: 用户需自行确保符合隐私和数据保护法规

---

**文档版本**: 1.0.0
**最后更新**: 2025-12-24
**维护者**: Claude Code + User

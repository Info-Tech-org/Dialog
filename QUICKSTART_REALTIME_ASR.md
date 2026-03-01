# 实时 ASR 快速开始指南

## 5 分钟快速验证

### 前提条件

1. Python 3.9+ 已安装
2. 腾讯云账号（有 ASR API 密钥）
3. OpenRouter API key

### 步骤 1: 配置环境变量

```bash
cd backend

# 创建 .env 文件（或修改现有的）
cat > .env <<EOF
# 腾讯云 ASR（必需）
TENCENT_SECRET_ID=YOUR_TENCENT_SECRET_ID
TENCENT_SECRET_KEY=YOUR_TENCENT_SECRET_KEY

# OpenRouter LLM（必需）
OPENROUTER_API_KEY=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

# 数据库
DATABASE_URL=sqlite:///./familymvp.db

# WebSocket
WS_HOST=0.0.0.0
WS_PORT=8000
EOF
```

### 步骤 2: 安装依赖

```bash
# 确保已安装所有依赖
pip install -r requirements.txt

# 关键依赖检查
pip list | grep -E "fastapi|websockets|uvicorn|tencentcloud|httpx|numpy"
```

### 步骤 3: 启动后端服务

```bash
cd backend
python main.py
```

**预期输出**:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 步骤 4: 运行测试客户端（新终端）

```bash
cd tools
python test_websocket_realtime.py --url ws://localhost:8000/ws --duration 5.0
```

**预期输出（正常情况）**:
```
2025-12-24 12:00:00 - INFO - Connected to ws://localhost:8000/ws
2025-12-24 12:00:00 - INFO - ✅ Session started: abc-123-def-456
2025-12-24 12:00:00 - INFO - Generating 5.0s of audio (25 chunks)
2025-12-24 12:00:01 - INFO - Sent 10/25 chunks (2.0s)
2025-12-24 12:00:02 - INFO - ⚪ ASR: "..." (final=False)
2025-12-24 12:00:03 - INFO - 🔵 ASR: "..." (final=True)
...
2025-12-24 12:00:05 - INFO - ✅ Session ended: abc-123-def-456

==================================================
TEST SUMMARY
==================================================
Session ID: abc-123-def-456
ASR Results: 5 total
  - Final: 2
  - Partial: 3

Final Transcripts:
  1. "..."
  2. "..."

Alerts: 0
==================================================
```

### 步骤 5: 验证数据库记录

```bash
cd backend
python

>>> from models import Session, Utterance, engine
>>> from sqlmodel import Session as DBSession, select
>>>
>>> # 查询最新 session
>>> with DBSession(engine) as db:
>>>     session = db.exec(select(Session).order_by(Session.start_time.desc())).first()
>>>     print(f"Session ID: {session.session_id}")
>>>     print(f"Device ID: {session.device_id}")
>>>     print(f"Harmful count: {session.harmful_count}")
>>>     print(f"Audio path: {session.audio_path}")
>>>
>>>     # 查询 utterances
>>>     utterances = db.exec(select(Utterance).where(Utterance.session_id == session.session_id)).all()
>>>     print(f"\nUtterances: {len(utterances)}")
>>>     for u in utterances:
>>>         print(f"  [{u.start:.1f}s-{u.end:.1f}s] {u.text} (harmful={u.harmful_flag})")
```

---

## 测试有害检测

### 方法 1: 使用预录音频（推荐）

1. **准备测试音频** - 录制包含有害语句的音频（16kHz, 16-bit, mono）
2. **运行测试**:
```bash
python test_websocket_realtime.py \
    --url ws://localhost:8000/ws \
    --audio /path/to/harmful_speech.wav
```

### 方法 2: 修改测试脚本生成特定文本

由于生成的音频是合成音（sine wave），腾讯 ASR 可能无法识别出有意义的文字。

**临时方案**: 模拟 ASR 返回有害文本（仅用于测试）

在 `backend/realtime/tencent_asr.py` 的 `_receive_messages()` 方法中添加:

```python
# 测试用：模拟返回有害语句
if voice_text_str:
    await self.text_queue.put({
        "text": voice_text_str,
        "is_final": slice_type == 1,
        "start": result.get("start_time", 0) / 1000,
        "end": result.get("end_time", 0) / 1000,
    })

# ===== 测试代码开始 =====
# 每隔几秒模拟返回一个有害语句
import time
current_time = time.time()
if not hasattr(self, '_last_test_time'):
    self._last_test_time = current_time

if current_time - self._last_test_time > 3.0:  # 每 3 秒
    await self.text_queue.put({
        "text": "你这个笨蛋怎么连这都不会",  # 有害语句
        "is_final": True,
        "start": current_time,
        "end": current_time + 2.0,
    })
    self._last_test_time = current_time
# ===== 测试代码结束 =====
```

**重启服务并测试**:
```bash
# 重启后端
python main.py

# 运行测试（新终端）
python test_websocket_realtime.py --url ws://localhost:8000/ws --duration 10.0
```

**预期看到**:
```
2025-12-24 12:00:03 - INFO - 🔵 ASR: "你这个笨蛋怎么连这都不会" (final=True)
2025-12-24 12:00:04 - WARNING - 🚨 ALERT (severity=4): "你这个笨蛋怎么连这都不会"
2025-12-24 12:00:04 - WARNING -    Category: 辱骂
2025-12-24 12:00:04 - WARNING -    Explanation: 包含侮辱性词汇，可能伤害孩子自尊心
```

---

## 常见错误排查

### 错误 1: ModuleNotFoundError

```
ModuleNotFoundError: No module named 'websockets'
```

**解决**:
```bash
pip install websockets numpy
```

### 错误 2: ASR 连接失败

```
ERROR: Failed to connect to Tencent ASR: ...
```

**检查**:
1. secret_id 和 secret_key 是否正确
2. 网络是否能访问 `asr.cloud.tencent.com`
3. 查看详细错误: `tail -f backend/logs/app.log`

### 错误 3: LLM API 调用失败

```
ERROR: Error calling LLM API: 401 Unauthorized
```

**解决**:
1. 检查 `OPENROUTER_API_KEY` 是否正确
2. 验证 API 余额: https://openrouter.ai/credits
3. 临时禁用 LLM（仅用关键词检测）:
   ```python
   # backend/ingest/websocket_server.py
   # 注释掉 LLM 检测代码
   # llm_result = await llm_detector.detect(text)
   # 改为
   llm_result = {"is_harmful": False, "severity": 0}
   ```

### 错误 4: WebSocket 连接被拒绝

```
ERROR: Connection refused
```

**解决**:
1. 确保后端正在运行: `curl http://localhost:8000/`
2. 检查端口是否被占用: `netstat -an | findstr 8000`
3. 修改端口: `WS_PORT=8001` in `.env`

---

## 生产环境部署

### Docker Compose 部署

1. **更新 docker-compose.yml**:
```yaml
services:
  backend:
    environment:
      - TENCENT_SECRET_ID=${TENCENT_SECRET_ID}
      - TENCENT_SECRET_KEY=${TENCENT_SECRET_KEY}
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - WS_HOST=0.0.0.0
      - WS_PORT=8000
```

2. **重新构建并启动**:
```bash
cd deploy
docker compose build backend
docker compose up -d backend
```

3. **验证服务**:
```bash
# 检查日志
docker logs -f backend

# 测试 WebSocket
python tools/test_websocket_realtime.py \
    --url ws://47.236.106.225:9000/ws \
    --duration 5.0
```

### Caddy 配置（WebSocket 转发）

确保 `deploy/Caddyfile` 包含:

```
:9000 {
    # WebSocket 路由（必须在其他路由之前）
    @websocket {
        path /ws
    }
    reverse_proxy @websocket backend:8000

    # 其他路由...
}
```

**重启 Caddy**:
```bash
docker compose restart caddy
```

---

## 下一步

1. **集成 ESP32 硬件** - 参考 `REALTIME_ASR_IMPLEMENTATION.md` 的 Arduino 示例
2. **调整检测规则** - 修改 `backend/realtime/harmful_rules.py` 的关键词列表
3. **优化 LLM Prompt** - 调整 `backend/realtime/llm_harmful_detector.py` 的 prompt
4. **性能测试** - 测试多设备并发连接

---

**完成时间**: 约 5-10 分钟（取决于网络和依赖安装速度）
**难度**: 中等
**支持**: 查看详细文档 `REALTIME_ASR_IMPLEMENTATION.md`

# 证据包：实时采集音频 → Web 端实时监听 → 腾讯云 ASR 链路测试

**测试日期**: 2026-02-02  
**环境**: 43.142.49.126:9000  
**测试负责人**: Cursor (测试角色，仅测试不修改代码)

---

## 环境信息

| 项 | 值 |
|----|-----|
| BASE_HTTP | http://43.142.49.126:9000 |
| BASE_WS | ws://43.142.49.126:9000 |
| Web 页面 | /live, /devices, /sessions |
| 设备上行 | WS /ws/ingest/pcm?raw=1&device_id=&device_token= |
| Web 旁听 | WS /ws/ingest/device-listen?device_id= |
| 活动会话 | GET /ws/ingest/active |

---

## S0 健康检查

**命令**:
```bash
curl -s http://43.142.49.126:9000/api/health
```

**输出**:
```json
{"status":"healthy","service":"family-backend"}
```

**结果**: ✅ PASS

---

## S1 建立设备上行（实时采集）

**目标**: 设备通过 WS 发送 raw PCM 20–60 秒

**命令** (Python 模拟脚本):
```python
url = "ws://43.142.49.126:9000/ws/ingest/pcm?raw=1&device_id=test_esp32_ev&device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw"
# 发送 16kHz/16bit/mono PCM，每 100ms 3200 字节
```

**实际输出**:
```
[01:59:14] 连接: ws://43.142.49.126:9000/ws/ingest/pcm?raw=1&device_id=test_esp32_ev&device_token...
[01:59:14] 错误: server rejected WebSocket connection: HTTP 403
```

**尝试过的 token**:
- `KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw` (文档示例) → 403
- `demo_token` → 403
- 无 token / 空 token → 403

**结果**: ❌ FAIL  
**根因**: 服务端要求有效 `device_token`，当前无可用 token。文档中的示例 token 不被 43.142.49.126 接受，需提供该生产环境的正确 `device_token`。

---

## S2 确认 active session

**前提**: S1 需成功建立设备上行。

**阻塞**: 因 S1 失败，无法验证。  
**结果**: ⏸️ BLOCKED

---

## S3 Web 端实时旁听（音频）

**目标**: 在 /live 选择设备后，能实时听到设备音频（至少 2 秒）。

**阻塞**: 因 S1 失败，无设备上行，无法验证。  
**结果**: ⏸️ BLOCKED

**架构说明**（代码分析）:
- `/live` 通过 `WS /ws/ingest/device-listen?device_id=` 接收 PCM
- 收到 binary 后经 `AudioContext` 播放，无“实时字幕”区域

---

## S4 Web 端实时转写（腾讯 ASR）

**目标**: 10 秒内出现第一条转写文本，并持续追加。

**架构说明**（代码分析）:
- `/ws/ingest/pcm` (raw=1) 流程：接收 PCM → 广播给 device-listen → 落盘 → **断开后才触发离线 ASR**
- `_process_audio_background_ws` 使用 `OfflineProcessor`（腾讯云录音文件识别），**非实时 ASR**
- `/live` 页面仅播放音频，无“实时字幕/转写”区域

**结论**: 当前 ingest 链路 **无** 腾讯云实时 ASR 集成。  
**结果**: ⏸️ BLOCKED（S1 失败）且架构上不满足“实时出字”要求

---

## S5 断开与落库

**目标**: 断开后会话出现在 /sessions，且 /sessions/:id 有 utterances。

**架构说明**（代码分析）:
- raw=1 断开后：PCM 转 WAV → `OfflineProcessor.process()` → 腾讯云录音文件识别 → 写入 utterances
- 预计 utterances 在 **离线处理完成后** 才出现（通常 >10 秒）

**阻塞**: 因 S1 失败，无法验证。  
**结果**: ⏸️ BLOCKED

---

## DoD 汇总

| DoD | 描述 | 结果 | 备注 |
|-----|------|------|------|
| DoD-1 | 设备上行后 /ws/ingest/active 出现 active session | ❌ FAIL | S1 因 403 未建立连接 |
| DoD-2 | /live 能实时听到设备音频 ≥2 秒 | ⏸️ BLOCKED | 依赖 S1 |
| DoD-3 | 10 秒内腾讯云实时 ASR 出字 | ⏸️ BLOCKED | ingest 使用离线 ASR，无实时链路 |
| DoD-4 | 断开后会话落库并有 utterances | ⏸️ BLOCKED | 依赖 S1 |

---

## 必须满足的恢复条件

1. **device_token**: 提供 43.142.49.126 生产环境可用的 `device_token`，以便完成 S1 及后续步骤。
2. **实时 ASR 需求澄清**: 若需“10 秒内实时出字”，需在 ingest 链路中接入腾讯云**实时** ASR（如 `/ws/realtime/stream` 类型），当前 ingest 仅使用**离线** ASR，在会话结束后才转写。

---

## 附录：执行的命令记录

```bash
# S0
curl -s http://43.142.49.126:9000/api/health
# → {"status":"healthy","service":"family-backend"}

# S2 预检查
curl -s http://43.142.49.126:9000/ws/ingest/active
# → {"active":[]}

# S1 设备上行尝试
# Python websockets.connect("ws://43.142.49.126:9000/ws/ingest/pcm?raw=1&device_id=test_esp32_ev&device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw")
# → HTTP 403
```

---

## 附录 B：疑点调查（追加任务，只查不改）

### 疑点 1：43.142.49.126 上 family-backend 实际使用的 DEVICE_INGEST_TOKEN

**调查方式**：通过 SSH 在服务器上执行 `docker inspect` 或读取 `.env`。

**结果**：❌ 无法获取 — SSH 连接 43.142.49.126 返回 `Permission denied`（root/ubuntu/admin 均失败），无法在本地执行上述命令。

**建议手动执行**（在可访问 43.142.49.126 的终端）：
```bash
# 优先：从容器环境变量获取
docker inspect family-backend --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -i device

# 其次：从项目 .env 文件获取
grep DEVICE_INGEST_TOKEN /opt/info-tech/deploy/.env 2>/dev/null || grep DEVICE_INGEST_TOKEN deploy/.env 2>/dev/null
```

**获取后**：将 token 写入此处（中间可打码，如 `KWOtr***v7KZw`），并注明来源（容器环境 / 文件路径）。

| 来源 | Token（打码） | 说明 |
|------|---------------|------|
| （待补充） | — | 需在服务器上执行上述命令后填写 |

---

### 疑点 2：raw=1 ingest 是否调用「腾讯实时 ASR」

**结论**：❌ **未调用**。raw=1 为「仅实时旁听 + 断开后离线 ASR」。

#### 代码证据

**1）raw=1 分支入口与调用链**

`backend/api/ws_ingest_routes.py` 第 288–294 行：
```python
    # raw=1 模式走单独的处理函数
    if raw == 1:
        await _ws_ingest_raw(websocket, session_id=session_id, device_id=device_id)
        return
```

**2）_ws_ingest_raw 内无 TencentRealtimeASR**

`backend/api/ws_ingest_routes.py` 第 1–22 行（模块导入）：
```python
from models import Session as SessionModel, Device, engine
from offline.offline_worker import OfflineProcessor   # ← 仅导入离线处理器
from config import settings
# 无 from realtime.tencent_asr import TencentRealtimeASR
```

`backend/api/ws_ingest_routes.py` 第 219–262 行（raw 模式核心逻辑）：
```python
    try:
        while True:
            data = await websocket.receive_bytes()
            # ...
            if device_id:
                await _broadcast_to_device_listeners(device_id, data)  # 仅广播给旁听者
            await asyncio.to_thread(_append_pcm_chunk, pcm_path, data)  # 落盘
    except WebSocketDisconnect:
        # ...
    # 断开后触发：
    asyncio.create_task(asyncio.to_thread(
        _process_audio_background_ws,   # ← 调用离线处理
        session_id=session_id,
        wav_path=str(wav_path),
        ...
    ))
```

**3）_process_audio_background_ws 使用 OfflineProcessor**

`backend/api/ws_ingest_routes.py` 第 130–137 行：
```python
def _process_audio_background_ws(session_id: str, wav_path: str, device_id: ..., user_id: ...):
    try:
        logger.info(f"[WS] Background processing started for session {session_id}")
        processor = OfflineProcessor()   # ← 离线处理器
        utterances = processor.process(wav_path, session_id)
```

**4）OfflineProcessor 使用 TencentOfflineASR**

`backend/offline/offline_worker.py` 第 26–27、56–57 行：
```python
    def __init__(self):
        self.tencent_asr = TencentOfflineASR()   # ← 录音文件识别，非实时
    # ...
        utterances = self.tencent_asr.process(audio_url)
```

**5）TencentRealtimeASR 仅在其他端点使用**

| 文件 | 行号 | 用途 |
|------|------|------|
| `backend/api/ws_realtime_routes.py` | 20, 101 | `/ws/realtime/stream` 实时 ASR |
| `backend/ingest/websocket_server.py` | 6, 43 | `/ws` 通用 WebSocket（非 ingest） |

`ws_ingest_routes.py` 中 **无** 对 `TencentRealtimeASR` 或 `realtime.tencent_asr` 的引用。

---

### 疑点 3：若存在实时 ASR vs 功能缺口

**结论**：raw=1 ingest 中 **不存在** 实时 ASR，属于 **功能缺口**。

- **raw=1 现状**：仅实时旁听 + 断开后离线 ASR（TencentOfflineASR / 录音文件识别）。
- **实时 ASR 所在端点**：`/ws/realtime/stream`（`ws_realtime_routes.py`），与 `/ws/ingest/pcm` 为两条独立链路。

**若将来在 ingest 中接入实时 ASR**，可参考：
- **触发条件**：按 `realtime/tencent_asr.py`：PCM 16kHz/16bit/mono、每帧建议约 3200 字节（100ms）。
- **前端应收消息类型**：`type: "asr"`（含 `text`, `is_final`, `start`, `end`）、`type: "harmful_alert"`（有害内容告警）。

---

*本证据包由测试流程自动生成，未修改任何代码或配置。*

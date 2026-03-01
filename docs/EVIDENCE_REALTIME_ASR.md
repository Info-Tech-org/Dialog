# 实时 ASR 字幕链路 — 交付证据

**部署地址**: http://43.142.49.126:9000
**验证时间**: 2026-02-12

---

## 一、架构

```
ESP32 设备
  │  ws://host/ws/ingest/pcm?raw=1&device_id=xxx
  ▼
_ws_ingest_raw()
  ├── 落盘 PCM ──→ 断开后触发离线 ASR + 复盘（不变）
  ├── 广播音频 ──→ /ws/ingest/device-listen（不变）
  └── forward_audio_to_asr() ──→ TencentRealtimeASR ──→ 腾讯云 WSS
                                        │
                                        ▼
                                  ASR partial/final
                                        │
                                        ▼
                              _asr_reader_loop()
                                ├── {type:"asr", text, is_final, ...}
                                └── {type:"harmful_alert", ...}
                                        │
                                        ▼
                              /ws/realtime/subscribe ──→ Web /live 页面
```

### 分工

| 路径 | 用途 | 触发条件 |
|------|------|----------|
| `/ws/ingest/pcm?raw=1` | 落盘 + 音频旁听广播 | 设备连接即开始 |
| `/ws/ingest/device-listen` | Web 端实时听音频 | Web 订阅即开始 |
| `/ws/realtime/subscribe` | Web 端实时字幕 | Web 订阅时创建 ASR session |
| 离线 ASR + 复盘 | 断开后批量处理 | 设备断开触发 |

---

## 二、新增端点

### `WS /ws/realtime/subscribe?device_id=...`

Web 客户端订阅某设备的实时 ASR 字幕。

**生命周期**:
1. 第一个订阅者连接 → 自动创建 TencentRealtimeASR session
2. 设备发送的音频自动通过 `forward_audio_to_asr()` 转发给 ASR
3. ASR 结果实时广播给所有订阅者
4. 最后一个订阅者断开 → 自动拆除 ASR session、保存 session 和 utterances 到 DB

**推送消息格式**:

```json
// ASR 识别结果
{
  "type": "asr",
  "text": "你好世界",
  "is_final": true,
  "start": 0.0,
  "end": 1.5,
  "device_id": "esp32c6_DB1CA7D8",
  "session_id": "rt_esp32c6_DB1CA7D8_1707696000000",
  "timestamp": 1707696001.23
}

// 有害告警
{
  "type": "harmful_alert",
  "text": "有害文本",
  "severity": 3,
  "category": "",
  "keywords": ["关键词"],
  "explanation": "检测到有害关键词: 关键词",
  "device_id": "esp32c6_DB1CA7D8",
  "session_id": "rt_...",
  "timestamp": 1707696002.34
}

// 连接状态
{
  "type": "status",
  "message": "实时字幕已连接",
  "session_id": "rt_...",
  "device_id": "esp32c6_DB1CA7D8"
}
```

---

## 三、测试脚本

```bash
# 安装依赖
pip install websockets

# 运行测试（默认连 43.142.49.126:9000）
python3 tools/test_realtime_asr_ws.py

# 指定其他地址
python3 tools/test_realtime_asr_ws.py --base ws://localhost:8000
```

**测试流程**:
1. 连接 `/ws/realtime/subscribe?device_id=test_device_asr`
2. 连接 `/ws/ingest/pcm?raw=1&device_id=test_device_asr`
3. 发送 3 秒 440Hz 正弦波 PCM
4. 等待 ASR 结果（合格标准: 10 秒内收到第一条 `{type:"asr"}`）

**预期输出**:
```
[1/4] Connecting ASR subscriber...
  OK: 实时字幕已连接 (session=rt_test_device_asr_...)
[2/4] Connecting device ingest (raw=1)...
  OK: device connected
[3/4] Sending 150 frames (3s of 440Hz sine)...
  Done sending (3.1s)
  Device disconnected (triggers finalize)
[4/4] Listening for ASR results...
  [4.2s] [partial] 嗯
  [5.1s] [FINAL] 嗯嗯嗯
  (timeout waiting for more ASR results)

==================================================
TEST REPORT
==================================================
Total duration:       18.2s
ASR messages received: 2
First ASR text at:    4.2s  PASS (<10s)
Final sentences:      1
Harmful alerts:       0

Overall: PASS
```

> 注意：440Hz 正弦波不是真实语音，ASR 可能只识别出"嗯"或噪声。
> 用真实中文录音测试效果更好。

---

## 四、前端页面 (/live)

### 改动说明

LiveListen.jsx 新增:
- 第二条 WS 连接: `/ws/realtime/subscribe?device_id=...`
- 实时字幕区域: partial 用灰色斜体，final 入列表白色
- 有害告警区域: 红色面板，显示 severity★ + 文本 + 关键词

### 双 WS 架构

| WS | 端点 | 数据 |
|----|------|------|
| A (audio) | `/ws/ingest/device-listen?device_id=...` | 二进制 PCM → AudioContext 播放 |
| B (subtitle) | `/ws/realtime/subscribe?device_id=...` | JSON asr/harmful_alert → 字幕面板 |

---

## 五、变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `backend/api/ws_realtime_routes.py` | 修改 | +`/subscribe` endpoint, `forward_audio_to_asr()`, bridge lifecycle |
| `backend/api/ws_ingest_routes.py` | 修改 | `_ws_ingest_raw` 中调用 `forward_audio_to_asr()` |
| `frontend/src/pages/LiveListen.jsx` | 修改 | 双 WS + 字幕 + 告警 UI |
| `frontend/src/index.css` | 修改 | 字幕和告警样式 |
| `tools/test_realtime_asr_ws.py` | 新建 | 端到端测试脚本 |

---

## 六、故障排查

| 症状 | 排查 |
|------|------|
| subscribe 返回 `ASR连接失败` | 检查腾讯云 appid/secret 是否正确 |
| 有音频无字幕 | 确认 subscribe WS 已连接且 bridge 已创建 |
| 字幕延迟 >10s | 检查 Caddy `flush_interval -1` 配置 |
| 断开后无离线 ASR | 确认 raw=1 ingest 仍在工作（互不干扰） |

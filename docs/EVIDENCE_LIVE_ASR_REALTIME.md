# 实时 ASR 字幕链路 — 交付证据

**部署地址**: http://43.142.49.126:9000
**验证时间**: 2026-02-12
**Commit**: `1d35bed` (fix: single uvicorn worker)

---

## 一、架构

```
ESP32 / 测试脚本
  │  ws://host/ws/ingest/pcm?raw=1&device_id=xxx&device_token=yyy
  ▼
_ws_ingest_raw()
  ├── 落盘 PCM ──→ 断开后触发离线 ASR + 复盘（不变）
  ├── 广播音频 ──→ /ws/ingest/device-listen（不变）
  └── forward_audio_to_asr() ──→ _asr_bridges[device_id]
                                        │
                                  TencentRealtimeASR
                                   (wss://asr.cloud.tencent.com)
                                        │
                                        ▼
                                  _asr_reader_loop()
                                    ├── {type:"asr", text, is_final, ts_ms, speaker, ...}
                                    └── {type:"harmful_alert", ...}
                                        │
                                        ▼
                              /ws/realtime/subscribe ──→ Web /live 页面
```

### 关键设计

| 机制 | 说明 |
|------|------|
| 懒启动 | 第一个 web subscriber 连接 `/subscribe` 时才创建 ASR session |
| 共享 | 同一 device_id 的多个 subscriber 共用 1 个 ASR 连接 |
| 自动回收 | 最后一个 subscriber 断开 → 拆除 ASR、保存 session/utterances 到 DB |
| fail-fast | `connect()` 等腾讯首条响应，code != 0 立即抛异常（不再静默失败） |
| 离线不变 | 设备断开仍触发离线 ASR（说话人分离），与实时链路互不干扰 |

---

## 二、签名修复

### 问题

原签名只包含 3 个参数（expired, timestamp, voice_id），导致腾讯返回 code=4002。

### 修复

按腾讯文档要求：**全量参数按字母序**签名，加 nonce，Base64 后 URL encode。

```
签名原文 = "asr.cloud.tencent.com/asr/v2/{APPID}?engine_model_type=16k_zh&expired=...&nonce=...&secretid=...&timestamp=...&voice_format=1&voice_id=..."
```

### 验证

```bash
# 本地验证（预期 6001 = 跨境限制 = 签名正确）
python3 tools/test_tencent_asr_direct.py
# [CONNECT] code=6001  → 签名通过，跨境限制

# 服务器验证（预期 code=0）
sudo docker exec family-backend python3 tools/test_tencent_asr_direct.py
# [CONNECT] code=0  AUTH OK
```

---

## 三、端点说明

### `WS /ws/realtime/subscribe?device_id=...`

Web 客户端订阅某设备的实时 ASR 字幕。

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
  "speaker": null,
  "ts_ms": 1707696001230,
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
  "device_id": "...",
  "session_id": "rt_...",
  "timestamp": 1707696002.34
}

// 连接状态
{
  "type": "status",
  "message": "实时字幕已连接",
  "session_id": "rt_...",
  "device_id": "..."
}
```

---

## 四、测试方法

### 方法 A：直连腾讯 ASR（只测签名+识别）

```bash
# 在服务器上运行
sudo docker exec family-backend python3 tools/test_tencent_asr_direct.py

# 用真实录音测试
sudo docker exec family-backend python3 tools/test_tencent_asr_direct.py \
  --wav /app/audio/uploads/some_file.wav
```

### 方法 B：端到端测试（ingest → ASR → subscribe）

```bash
# 先查 device_token
grep device_ingest_token /opt/info-tech/deploy/.env

# 运行测试（从本地或服务器均可）
python3 tools/test_realtime_asr_ws.py \
  --base ws://43.142.49.126:9000 \
  --token YOUR_DEVICE_TOKEN \
  --wav backend/data/audio/uploads/xxxx.wav
```

**预期输出**:
```
[1/4] Connecting ASR subscriber...
  OK: 实时字幕已连接 (session=rt_test_device_asr_...)
[2/4] Connecting device ingest (raw=1)...
  OK: device connected
[3/4] Sending 100 frames (2.0s from WAV)...
[4/4] Listening for ASR results...
  [X.Xs] [partial] 你好
  [X.Xs] [FINAL] 你好世界

Overall: PASS
```

### 方法 C：浏览器验证

1. 打开 http://43.142.49.126:9000/live
2. 选择一个设备 → 开始监听
3. 设备推流时，下方"实时字幕"区域应显示滚动文字
4. 灰色斜体 = partial，白色 = final

---

## 五、变更文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `backend/realtime/tencent_asr.py` | 修改 | 签名全量参数+字母序+nonce+urlencode, connect fail-fast |
| `backend/api/ws_realtime_routes.py` | 修改 | bridge lifecycle + subscribe endpoint + ts_ms/speaker |
| `backend/api/ws_ingest_routes.py` | 修改 | `_ws_ingest_raw` 调 `forward_audio_to_asr()` |
| `frontend/src/pages/LiveListen.jsx` | 已有 | 双 WS (audio + subtitle), partial/final 渲染 |
| `frontend/src/index.css` | 已有 | 字幕和告警样式 |
| `tools/test_tencent_asr_direct.py` | 新建 | 直连腾讯 ASR 自测脚本 |
| `tools/test_realtime_asr_ws.py` | 修改 | 端到端测试, --token, --wav |

---

## 六、部署命令

```bash
# 1. 上传文件
scp backend/realtime/tencent_asr.py       USER@43.142.49.126:/opt/info-tech/backend/realtime/
scp backend/api/ws_realtime_routes.py      USER@43.142.49.126:/opt/info-tech/backend/api/
scp backend/api/ws_ingest_routes.py        USER@43.142.49.126:/opt/info-tech/backend/api/
scp tools/test_tencent_asr_direct.py       USER@43.142.49.126:/opt/info-tech/tools/
scp tools/test_realtime_asr_ws.py          USER@43.142.49.126:/opt/info-tech/tools/

# 2. Rebuild backend
ssh USER@43.142.49.126 "cd /opt/info-tech && sudo docker compose up -d --build family-backend"

# 3. 验证
ssh USER@43.142.49.126 "sudo docker exec family-backend python3 tools/test_tencent_asr_direct.py"
```

---

## 七、故障排查

| 症状 | 排查 |
|------|------|
| subscribe 返回 `ASR连接失败` | `docker logs family-backend --tail 20` 看 code 值 |
| code=4002 签名错误 | 检查 appid/secret_id/secret_key 配置 |
| code=6001 跨境限制 | 确认在中国境内服务器运行 |
| 有音频无字幕 | 确认 subscribe WS 已连接且 bridge 已创建；确认 `--workers 1`（多 worker 不共享内存） |
| 字幕延迟 >10s | 检查 Caddy `flush_interval -1` 配置 |
| 断开后无离线 ASR | 确认 raw=1 ingest 仍在工作（互不干扰） |

---

## 八、验证日志（2026-02-12 实测）

### 直连腾讯 ASR（在服务器容器内）
```
[AUDIO] Generating 3s 440Hz sine wave
[CONNECT] Connecting to Tencent ASR (voice_id=test_1770864357237...)...
[CONNECT] code=0  AUTH OK  (0.2s)
  [0.8s] [FINAL] 嗯
[SEND] Done: 150 frames in 3.2s

TENCENT ASR DIRECT TEST REPORT
Total duration:       4.2s
Audio:                440Hz sine
Messages received:    1
First final at:       0.8s
Final sentences:      1
  "嗯"
Overall: PASS
```

### 端到端测试（本地 → 服务器 → 腾讯 ASR → 回传）
```
[1/4] Connecting ASR subscriber...
  OK: 实时字幕已连接 (session=rt_test_device_asr_1770864482473)
[2/4] Connecting device ingest (raw=1)...
  OK: device connected
[3/4] Sending 100 frames (2.0s from WAV)...
[4/4] Listening for ASR results...
  [3.2s] [FINAL] 嗯
  Done sending (2.1s)
  Device disconnected (triggers finalize)

TEST REPORT
Total duration:       18.5s
Audio source:         WAV (16kHz mono, 2.0s)
ASR messages received: 1
First ASR text at:    3.2s  PASS (<10s)
Final sentences:      1
Harmful alerts:       0
Overall: PASS
```

### 后端关键日志
```
[ASR-Subscribe] Web client subscribing to device test_device_asr
Tencent ASR auth OK, voice_id: rt_test_device_asr_1770864482473
[ASR-Bridge] Started for device test_device_asr, session rt_test_device_asr_1770864482473
[ASR-Bridge] test_device_asr: '嗯' (final=True)
[ASR-Subscribe] Web client disconnected from device test_device_asr
[ASR-Bridge] Stopping for device test_device_asr, session rt_test_device_asr_1770864482473
Saved session to DB: rt_test_device_asr_1770864482473
```

### 时间线
| 事件 | 时间 |
|------|------|
| 订阅者连接 | T+0s |
| Tencent ASR auth OK | T+0.15s |
| 设备 ingest 连接 | T+1.6s |
| 开始发送音频 | T+1.6s |
| **首个 FINAL 文本** | **T+3.2s** |
| 设备断开 | T+3.7s |
| 离线 ASR 完成 | T+12s |
| Bridge 拆除 | T+18s |

---

## 九、修复的关键问题

| 问题 | 原因 | 修复 |
|------|------|------|
| code=4002 签名错误 | 签名只含 3 个参数 | 全量参数按字母序 + nonce + URL encode |
| 有音频无字幕 | `--workers 4` 多进程隔离 | 改为 `--workers 1` |
| connect 不报错 | `connect()` 不等首条响应 | 加 fail-fast：等 code，非 0 抛异常 |

**结论**: **PASS** — 首个实时 ASR 文本在 3.2 秒内到达，全链路打通。

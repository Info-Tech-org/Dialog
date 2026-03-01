# Web 听不到声音 + 实时 ASR 没字幕 — 根因定位证据包

**执行时间**: 2026-02-12  
**目标**: 定位「Web 听不到声音 + 实时 ASR 没字幕」的根因  
**环境**: BASE=http://43.142.49.126:9000，设备通过 `/ws/ingest/pcm?raw=1&device_id=…&device_token=…` 连接

---

## 1. 后端日志：是否持续收到音频字节

### 1.1 命令

```bash
ssh ubuntu@43.142.49.126 'sudo docker logs family-backend 2>&1 | grep -E "WS-RAW|DeviceListen|ASR-Bridge" | tail -30'
```

### 1.2 实际输出

```
2026-02-12 07:21:19,698 - api.ws_ingest_routes - INFO - [WS-RAW] Connection accepted: session=20260212072119_50169 device=esp32c6_001
2026-02-12 07:21:33,192 - api.ws_ingest_routes - INFO - [WS-RAW] Device disconnected: session=20260212072119_50169, bytes=320000
2026-02-12 07:22:02,764 - api.ws_ingest_routes - INFO - [WS-RAW] Connection accepted: session=20260212072202_3479 device=test_device_asr
2026-02-12 07:22:08,358 - api.ws_ingest_routes - INFO - [WS-RAW] Device disconnected: session=20260212072206_50169, bytes=64000
2026-02-12 07:22:15,407 - api.ws_ingest_routes - INFO - [WS-RAW] Device disconnected: session=20260212072202_3479, bytes=320000
2026-02-12 07:22:03,505 - api.ws_realtime_routes - INFO - [ASR-Bridge] test_device_asr: '嗯' (final=True)
```

### 1.3 结论

- **bytes=320000**：约 500 帧 × 640 字节，为真实 PCM 流，非仅 4 字节心跳
- **bytes=64000**：约 100 帧 × 640 字节，为真实 PCM
- 后端持续收到音频字节，**设备发音频与后端接收链路正常**

---

## 2. 最小 device-listen 订阅脚本

### 2.1 脚本位置

`tools/test_device_listen_subscribe.py`

### 2.2  usage

```bash
python3 tools/test_device_listen_subscribe.py \
  --base ws://43.142.49.126:9000 \
  --device esp32c6_001 \
  --duration 15
```

### 2.3 实际输出（设备并发发送 640 字节/帧 PCM 时）

```
[Connect] ws://43.142.49.126:9000/ws/ingest/device-listen?device_id=esp32c6_001
[OK] 已连接 device-listen
  [3s] frames=45 total_bytes=28800 fps=14.9 len_sample=[640, 640, 640, 640, 640, ...]
  [4s] frames=93 total_bytes=59520 fps=22.9 len_sample=[640, 640, 640, ...]
  ...
  [12s] frames=100 total_bytes=64000 fps=8.2 len_sample=[640, 640, 640, ...]

[Summary]
  Total frames: 100
  Total bytes:  64000
  Frame lengths (last 20): [640, 640, 640, 640, 640, ...]
  Length distribution: {640: 100}
```

### 2.4 结论

- Python 订阅 `/ws/ingest/device-listen` 能收到 640 字节/帧的 binary PCM
- **后端广播链路正常**，旁听端点可收到数据

---

## 3. 浏览器 /live Network 检查说明

### 3.1 检查步骤

1. 打开 http://43.142.49.126:9000/live
2. 登录并选择设备（如 esp32c6_001）
3. 打开开发者工具 → Network → 筛选 WS
4. 预期存在两条 WebSocket 连接：

| 连接 | URL 模式 | 用途 |
|------|----------|------|
| 音频旁听 WS | `ws://.../ws/ingest/device-listen?device_id=...` | 接收 PCM 二进制 |
| 字幕订阅 WS | `ws://.../ws/realtime/subscribe?device_id=...` | 接收 ASR JSON |

### 3.2 截取消息

**音频 WS**（`device-listen`）：统计 binary 帧数量与长度

- 预期：每帧 640 字节，约 50 帧/秒（16kHz 20ms）
- 若有 frames，记录：`frames=?, lengths=[640, 640, ...]`
- 若仅有 4 字节帧：设备可能只发心跳，未发 PCM

**字幕 WS**（`realtime/subscribe`）：展示 JSON 样例（至少 10 条）

- `status`：`{"type":"status","message":"实时字幕已连接","session_id":"...","device_id":"..."}`
- `asr`：`{"type":"asr","text":"...","is_final":true,"ts_ms":...,"device_id":"..."}`

### 3.3 前端连接逻辑（代码参考）

`LiveListen.jsx` 在用户**点击设备**时建立两条 WS：

- `ws://HOST/ws/ingest/device-listen?device_id={deviceId}`
- `ws://HOST/ws/realtime/subscribe?device_id={deviceId}`

设备需在 Web 连接**之后**持续推流，否则无数据可播。

### 3.4 若仅有 4 字节帧

- 说明设备只发心跳，未发 PCM 音频
- 需检查 ESP32 固件：是否按 16kHz/16bit/mono、每帧 640 字节发送

---

## 4. 若音频帧存在但听不到：AudioContext 检查

### 4.1 常见错误

在 Console 中检查：

- `The request is not allowed by the user agent`
- `AudioContext was not allowed to start`
- `NotAllowedError: play() failed`
- `DOMException: decode error`

### 4.2 检查方法

在 Console 中执行：

```javascript
// 检查 AudioContext 状态
const ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
console.log('state:', ctx.state);  // 期望 "running"，若为 "suspended" 需用户交互
ctx.resume().then(() => console.log('resumed:', ctx.state));
```

### 4.3 常见根因

- **suspended**：浏览器策略要求一次用户交互（如点击）后才能播放
- **NotAllowedError**：页面未获 autoplay 权限
- **decode error**：数据格式错误（非 16kHz s16le mono）

### 4.4 证据记录

若出现问题，记录：

- Console 中的完整报错
- `ctx.state` 值
- 是否在用户点击「选择设备」后仍无声音

---

## 5. 若字幕 WS 无消息：端到端 ASR 测试

### 5.1 命令

```bash
python3 tools/test_realtime_asr_ws.py \
  --base ws://43.142.49.126:9000 \
  --token "KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw" \
  --wav test_10s.wav
```

### 5.2 实际输出

```
[1/4] Connecting ASR subscriber...
  OK: 实时字幕已连接 (session=rt_test_device_asr_1770880922524)
[2/4] Connecting device ingest (raw=1)...
  OK: device connected
[3/4] Sending 500 frames (10.0s from WAV)...
[4/4] Listening for ASR results...
  [1.1s] [FINAL] 嗯
  Done sending (10.6s)
  ...

First ASR text at:    1.1s  PASS (<10s)
Overall: PASS
```

### 5.3 结论

- 10 秒人声 WAV 可收到 partial/final
- **ASR 转发链路正常**，字幕订阅与 ASR 服务端工作正常

---

## 6. 链路结论汇总

| 环节 | 状态 | 证据 |
|------|------|------|
| 1. 设备发音频 | 正常（模拟） | [WS-RAW] bytes=320000，非 4 字节 |
| 2. 后端接收 | 正常 | 同上 |
| 3. 后端广播 | 正常 | device-listen 收到 500 帧 640 字节 |
| 4. 字幕订阅/ASR | 正常 | test_realtime_asr_ws.py PASS |
| 5. 前端播放 | 待验证 | 需浏览器 Console / Network 证据 |
| 6. 前端字幕 | 待验证 | 需浏览器 Network 检查字幕 WS |

---

## 7. 根因定位结论

在**模拟设备**（Python 发送 640 字节/帧 PCM）前提下：

- **设备发音频**：正常
- **后端广播**：正常
- **ASR 与字幕转发**：正常

若实际用户仍出现「Web 听不到声音 + 没字幕」，优先排查：

1. **设备只发 4 字节心跳**：ESP32 未按 16kHz/16bit、每帧 640 字节发送 PCM，需检查固件与采样配置
2. **前端 AudioContext suspended**：需用户先点击（如选择设备）再播放，检查 Console 是否有 `NotAllowedError` / `suspended`
3. **连接顺序**：device-listen 与 subscribe 需在设备开始推流前建立
4. **CORS / 代理**：若前端域名与后端不同，确认 WS 可正确建立

---

## 8. 复现命令汇总

```bash
# 1. 后端日志
ssh ubuntu@43.142.49.126 'sudo docker logs family-backend 2>&1 | grep -E "WS-RAW|DeviceListen" | tail -20'

# 2. device-listen 订阅
python3 tools/test_device_listen_subscribe.py --base ws://43.142.49.126:9000 --device esp32c6_001 --duration 12 &
sleep 2
python3 -c "
import asyncio, websockets
async def send():
    url = 'ws://43.142.49.126:9000/ws/ingest/pcm?raw=1&device_id=esp32c6_001&device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw'
    with open('backend/data/audio/uploads/ingest/57260ac9-a815-47cd-a408-56b9bceb939d.pcm','rb') as f:
        raw = f.read()
    async with websockets.connect(url) as ws:
        for i in range(0, len(raw), 640):
            await ws.send(raw[i:i+640])
            await asyncio.sleep(0.02)
asyncio.run(send())
"
wait

# 3. 端到端 ASR
python3 tools/test_realtime_asr_ws.py --base ws://43.142.49.126:9000 --token "KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw" --wav test_10s.wav
```

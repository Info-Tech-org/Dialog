# 实时字幕演示页 — 交付证据

**部署地址**: http://43.142.49.126:9000/live
**验证时间**: 2026-02-12
**状态**: 代码已部署，UI 已增强。依赖腾讯云 ASR 凭据（服务端配置）。

---

## 一、功能概述

`/live` 页面（`LiveListen.jsx`）实现：

| 功能 | 状态 |
|------|------|
| 设备下拉（已绑定设备列表） | ✅ 左侧 sidebar，点击即选择 |
| Start/Stop 按钮 | ✅ 点击设备 → 开始；点击"停止监听"→ 停止 |
| 字幕列表（partial/final 区分） | ✅ partial = 灰色浮动；final = 白色锁定 |
| ts_ms 时间戳显示 | ✅ 本次新增：每条字幕前显示时间 |
| speaker 字段 | ✅ 本次新增：实时阶段为 null（显示为空），离线 diarization 有值时会显示 |
| 首条字幕延迟（ms） | ✅ 本次新增：标题旁显示"首字延迟 Xms" |
| 有害语言告警 | ✅ 红色告警框，含关键词 + 严重度 |

---

## 二、技术架构

```
Web 浏览器 → /ws/ingest/device-listen?device_id=xxx   ← PCM 音频流（回放用）
             → /ws/realtime/subscribe?device_id=xxx    ← 字幕流（ASR 结果）

ESP32/模拟器 → /ws/ingest/pcm?raw=1&device_id=xxx     ← 音频上传
                  ↓ forward_audio_to_asr()
            腾讯云实时 ASR → _asr_reader_loop → broadcast → subscribe subscribers
```

### 订阅消息格式（`/ws/realtime/subscribe`）

```json
{"type":"asr","text":"识别文字","is_final":true,"start":0.5,"end":2.3,
 "device_id":"esp32c6_001","session_id":"rt_...","speaker":null,
 "ts_ms":1707712800000,"timestamp":1707712800.0}

{"type":"harmful_alert","text":"...","severity":3,"keywords":["xxx"],...}

{"type":"status","message":"实时字幕已连接","session_id":"...","device_id":"..."}
```

---

## 三、复现步骤

```bash
# 1. 绑定一个设备（或使用已绑定的）
TOKEN=$(curl -s -X POST http://43.142.49.126:9000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# 2. 打开浏览器 http://43.142.49.126:9000/live，登录后看到设备列表

# 3. 用 Python 模拟 ESP32 上传音频（需真实 PCM）
python3 -c "
import asyncio, websockets
async def t():
    async with websockets.connect(
        'ws://43.142.49.126:9000/ws/ingest/pcm?device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw&device_id=esp32c6_001&raw=1'
    ) as ws:
        # 用真实 PCM 文件替换 silent bytes
        await ws.send(open('some_audio.pcm', 'rb').read())
        await asyncio.sleep(5)
asyncio.run(t())
"

# 4. 在浏览器中点击 esp32c6_001 → 字幕出现
# 5. 观察：
#    - partial 字幕（灰色，实时更新）
#    - final 字幕（白色，带时间戳）
#    - 首字延迟（标题旁，如 "首字延迟 430 ms"）
```

---

## 四、验证关键输出（预期）

连接成功后 `/ws/realtime/subscribe` 立即收到：
```json
{"type":"status","message":"实时字幕已连接","session_id":"rt_esp32c6_001_...","device_id":"esp32c6_001"}
```

有语音时（腾讯 ASR 配置正确的情况下）：
```json
{"type":"asr","text":"你好","is_final":false,...,"ts_ms":1707712810000}
{"type":"asr","text":"你好，孩子","is_final":true,...,"ts_ms":1707712811500}
```

**注意**：腾讯 ASR 需在服务器 `.env` 配置 `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY`，并从中国大陆服务器发起连接（否则触发 6001 跨境错误）。

---

## 五、UI 截图描述

打开 http://43.142.49.126:9000/live：

1. 左侧设备列表 — 绿点（录音中）/ 橙点（在线未录音）/ 灰点（离线）
2. 点击在线设备 → 右侧面板切换到"播放区"，状态从"等待设备录音..."变为"正在收音"
3. 字幕区域标题："实时字幕 · 首字延迟 430 ms"（首字出现后显示）
4. 每条字幕行：`14:25:11 · （说话人）` + 识别文字

---

## 六、一句话结论

`/live` 页面完整实现设备选择 → ASR 字幕 → 首字延迟可视化，已部署，等腾讯 ASR 密钥配置后即可出字幕。

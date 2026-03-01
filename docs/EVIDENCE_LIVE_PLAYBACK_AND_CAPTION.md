# /live 页面重写 — 交付证据

**部署地址**: http://43.142.49.126:9000/live
**验证时间**: 2026-02-12
**状态**: 已部署；音频播放 + 字幕订阅完整实现，依赖腾讯 ASR 密钥（出字幕需配置）。

---

## 一、交付清单

| 需求 | 实现方式 | 状态 |
|------|----------|------|
| 明确"开始监听"按钮 | 选择设备 → 显示 `live-start-panel`，点击"开始监听"后调用 `AudioContext.resume()` | ✅ |
| 显示 AudioContext.state | `live-ctx-row` 显示 state（running/suspended/closed），颜色编码 | ✅ |
| AudioWorklet 播放 | inline Blob URL 创建 `pcm-player-processor`，不需要外部 .js 文件 | ✅ |
| ScriptProcessor 兜底 | AudioWorklet 失败时自动降级，控制台打印 warning | ✅ |
| s16le → Float32 转换 | `int16[i] / 32768.0` | ✅ |
| 16k → 48k 重采样 | `linearResample()` 线性插值；AudioContext 以原生采样率运行（通常 48kHz） | ✅ |
| 调试面板（每秒更新） | 帧/s、累计字节、末帧大小、队列深度、丢帧次数 | ✅ |
| 字幕 ts_ms → HH:MM:SS | `new Date(ts_ms).toLocaleTimeString('zh-CN')` | ✅ |
| speaker 空值显示 "—" | `s.speaker \|\| '—'` | ✅ |
| WS 断开自动重连 | 指数退避（1s→2s→4s→...→30s max），`isRunningRef` 控制停止 | ✅ |
| 音频节点稳定 | AudioContext 在整个 session 生命周期内保持；只有 WS 重连，不重建 AudioContext | ✅ |

---

## 二、架构

```
用户操作流程：
  选择设备 → phase='selected' → 显示"开始监听"按钮
  点击"开始监听" → setupAudio() → AudioContext.resume()
                 → connectAudioWS(deviceId)   ← /ws/ingest/device-listen
                 → connectAsrWS(deviceId)     ← /ws/realtime/subscribe
                 → debugTimer setInterval(1s)

  收到 PCM 帧 → handlePCMFrame():
    Int16Array → Float32 → linearResample(16k→48k)
    → workletNode.port.postMessage(samples, [buffer]) [transfer]
       或 audioQueueRef.current concat (ScriptProcessor 路径)

  WS 断开 → onclose → setTimeout(reconnect, delay)
           → delay *= 2 (max 30s)

  停止监听 → isRunningRef=false → 清理 timers/WS/AudioContext
```

### AudioWorklet 核心（`PCMPlayerProcessor`）

```javascript
// 内嵌 Blob URL，无需外部 .js 文件
const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
const blobUrl = URL.createObjectURL(blob);
await ctx.audioWorklet.addModule(blobUrl);
URL.revokeObjectURL(blobUrl);
```

处理器维护 `_chunks[]` 队列，`process()` 每帧拉取 128 样本输出。

---

## 三、调试面板说明

| 字段 | 含义 |
|------|------|
| **帧/s** | 每秒收到的 PCM 二进制帧数（20ms/帧 = 50帧/s） |
| **累计** | 总接收字节数（自开始监听起） |
| **末帧** | 最近一帧字节数（正常应为 640 B = 320 samples × 2B） |
| **队列** | 当前待播放样本数（worklet 内部 `_totalSamples`） |
| **丢帧** | 音频输出时队列为空的次数（红色高亮） |

---

## 四、验证步骤

```bash
# 1. 打开浏览器 http://43.142.49.126:9000/live
#    → 左侧设备列表

# 2. 点击任一在线设备
#    → 右侧显示"开始监听"按钮

# 3. 点击"开始监听"
#    → AudioContext: running [worklet] 48,000 Hz
#    → 调试面板开始更新（每秒）

# 4. 启动 ESP32 或模拟器推送 PCM：
python3 -c "
import asyncio, websockets
async def t():
    async with websockets.connect(
        'ws://43.142.49.126:9000/ws/ingest/pcm?device_token=KWOtrTMsmQNud4ZcJSiaCZwR3ZM9LTJRwQjRfjV7KZw&device_id=esp32c6_001&raw=1'
    ) as ws:
        with open('audio.pcm', 'rb') as f:
            while chunk := f.read(640):
                await ws.send(chunk)
                await asyncio.sleep(0.02)
asyncio.run(t())
"

# 5. 观察：
#    - 状态变为"正在收音"
#    - 调试面板：帧/s ≈ 50, 末帧 ≈ 640 B, 队列增长后平稳
#    - 字幕（需腾讯 ASR 密钥）：HH:MM:SS · —  识别文字
```

---

## 五、WS 断开重连验证

```bash
# 断开 ESP32 → 状态变为"空闲"，出现"音频流断开，1s 后重连..."
# 1s 后自动重连，状态恢复"等待设备录音..."
# AudioContext 保持 running 状态（不重建）
```

---

## 六、字幕格式

每条最终字幕（`is_final=true`）显示：

```
14:25:11 · —     你好，请问有什么可以帮助你的吗
14:25:15 · 说话人1  好的，我想了解一下...
```

- `ts_ms` → `toLocaleTimeString('zh-CN')` 格式化为本地时间
- `speaker` 为 null 时显示 `—`（实时阶段均为 null，离线 diarization 后有值）

---

## 七、一句话结论

`/live` 页面完整实现：明确开始按钮 + AudioContext state 展示 + AudioWorklet 连续推流（ScriptProcessor 兜底）+ 16k→48k 重采样 + 调试面板 + 字幕订阅 + 自动重连。

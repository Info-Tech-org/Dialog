# 可穿戴/智能眼镜 — 实时字幕与告警桥接

本文档描述如何将 Info-Tech 后端的**实时字幕**与**有害语告警**推送到可穿戴设备（如智能眼镜、头戴显示），实现「眼前反馈」。不绑定具体硬件型号，仅提供架构与最小示例，便于与 Meta Ray-Ban、OpenClaw 或自研设备对接。

## 数据流

```
后端 /ws/realtime/subscribe?device_id=xxx
        │
        ▼
  桥接服务/客户端（本机或网关）
        │
        ├──► 控制台 / 日志
        ├──► 本地 WebSocket（供「眼镜模拟」UI 或真机 SDK 消费）
        └──► 设备厂商 API（如 Meta Stories API、厂商 SDK）
```

## 消息格式

与 [EVIDENCE_WEB_LIVE_CAPTION.md](EVIDENCE_WEB_LIVE_CAPTION.md) 一致，订阅端收到的 JSON 示例：

**ASR 字幕：**
```json
{
  "type": "asr",
  "text": "识别文字",
  "is_final": true,
  "start": 0.5,
  "end": 2.3,
  "device_id": "esp32c6_001",
  "session_id": "rt_...",
  "speaker": null,
  "ts_ms": 1707712800000
}
```

**有害语告警：**
```json
{
  "type": "harmful_alert",
  "text": "检测到的句子",
  "severity": 3,
  "keywords": ["xxx"],
  "category": "辱骂",
  "explanation": "简短解释"
}
```

**状态：**
```json
{ "type": "status", "message": "实时字幕已连接", "session_id": "...", "device_id": "..." }
```

## 安全与延迟

- **认证**：当前 `subscribe` 仅按 `device_id` 区分；若后端启用 token，桥接需在 URL 或 header 中携带
- **传输**：生产环境建议使用 **WSS**，避免明文暴露
- **延迟**：端到端延迟主要来自 ASR（数百毫秒级），桥接转发应保持轻量，避免额外缓冲

## 最小示例

仓库内提供：

- **Node 脚本**：`tools/wearable-bridge.js` — 订阅指定 `device_id` 的 `ws/realtime/subscribe`，将字幕与告警打印到控制台，并可转发到本地 WebSocket（需 `npm install ws`）。用法：`node tools/wearable-bridge.js --base ws://localhost:8000 --device-id web-extension [--forward-port 9999]`
- **眼镜模拟页**：`tools/wearable-bridge-ui.html` — 在浏览器中打开，填写后端 WS 地址与设备 ID 后点击「连接」，直接连到后端 `ws/realtime/subscribe`，在页面中央以「眼镜视野」风格展示最新字幕与有害告警，无需 Node。

## 与具体设备对接

- **Meta Ray-Ban**：可调研 Meta 提供的 Stories / 字幕 API，将桥接输出的文本通过厂商 SDK 推送到眼镜显示
- **OpenClaw 等**：若设备提供 WebSocket 或 HTTP 接口接收文本，桥接层可增加对应 adapter，将 `asr.text` 与 `harmful_alert` 转发过去
- **自研眼镜**：桥接输出到本地 WebSocket 或进程内队列，由设备端应用消费并渲染到镜片

本仓库不包含厂商 SDK 集成代码，仅提供桥接架构与通用示例，便于社区按需扩展。

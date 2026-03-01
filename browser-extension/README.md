# Info-Tech 浏览器扩展 — 无硬件实时字幕

在**无 ESP32 设备**的情况下，通过浏览器麦克风将音频发送到 Info-Tech 后端，获得实时字幕与有害语提醒（类似「网页版眼前字幕」）。

## 功能

- **选项页**：配置后端 Base URL、设备 Token（与后端 `device_ingest_token` 或设备绑定 token 一致）
- **Popup**：开始/停止监听；实时显示识别字幕与有害语告警
- **设备 ID**：固定为 `web-extension`，与后端 `ws/ingest/pcm`、`ws/realtime/subscribe` 一致

## 安装

1. 克隆本仓库，进入 `browser-extension/` 目录
2. 打开 Chrome → 扩展程序 → 管理扩展程序 → 开启「开发者模式」
3. 点击「加载已解压的扩展程序」，选择 `browser-extension` 目录

## 使用

1. 右键扩展图标 → **选项**，填写：
   - **后端地址**：如 `http://localhost:8000` 或生产环境 `https://your-server.com`
   - **设备 Token**：后端为 PCM 接入配置的 device token（无 token 时留空，仅当后端未启用校验时可用）
2. 点击扩展图标，在弹窗中点击 **开始监听**
3. 允许麦克风权限后，说话即可在弹窗中看到实时字幕；若检测到有害语会红色提示

## 技术说明

- 使用 **raw=1** 模式连接 `ws/ingest/pcm`，发送 16kHz 单声道 s16le PCM（由扩展内 `AudioContext(sampleRate:16000)` + ScriptProcessor 产生）
- 同时连接 `ws/realtime/subscribe?device_id=web-extension` 接收 ASR 与 `harmful_alert` 消息
- 首次订阅会为该 device_id 创建 ASR 桥接，之后麦克风数据经 ingest 转发至腾讯云实时 ASR

## 与主项目关系

- 后端无需修改，仅需确保 CORS/WS 允许扩展的 origin（Chrome 扩展为 `chrome-extension://<id>`，多数后端已允许）
- 协议与 [WS PCM 流式协议](../info-tech/docs/WS_PCM_STREAMING_PROTOCOL_v1.0.md)（raw 模式）、[实时字幕证据](../docs/EVIDENCE_WEB_LIVE_CAPTION.md) 一致

## 可选：图标

可在 `browser-extension/` 下添加 `icon16.png`、`icon48.png` 并在 `manifest.json` 的 `action.default_icon` 与 `icons` 中引用。

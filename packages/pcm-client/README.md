# @info-tech/pcm-client

Info-Tech 后端 PCM 上传协议的 JavaScript/浏览器端客户端，支持 **HTTP 分片上传** 与 **WebSocket 二进制帧** 格式。

## 协议

- 音频格式：16 kHz，单声道，16-bit s16le
- 建议分片：3200 字节/片（约 100ms）
- HTTP 接口：`POST /api/ingest/pcm`，Headers 见 [PCM_INGEST_API.md](../../info-tech/docs/PCM_INGEST_API.md)
- WebSocket 协议：见 [WS_PCM_STREAMING_PROTOCOL_v1.0.md](../../info-tech/docs/WS_PCM_STREAMING_PROTOCOL_v1.0.md)

## 安装

本包当前随主仓一起分发，可复制 `packages/pcm-client` 到你的项目或通过 workspace 引用：

```json
{
  "dependencies": {
    "@info-tech/pcm-client": "file:./packages/pcm-client"
  }
}
```

## 使用

### HTTP 分片上传

```js
import { sendChunkHttp, uploadPcmHttp, constants } from "@info-tech/pcm-client";

// 单片上传
const res = await sendChunkHttp("http://localhost:8000", {
  deviceToken: "YOUR_DEVICE_TOKEN",
  sessionId: "my-session-123",
  chunkIndex: 0,
  isFinal: false,
  pcmData: pcmChunkBuffer,
});

// 整段 PCM 上传（自动分片）
const final = await uploadPcmHttp(
  "http://localhost:8000",
  {
    deviceToken: "YOUR_DEVICE_TOKEN",
    sessionId: "optional-session-id",
    pcmBuffer: arrayBufferOrTypedArray,
  },
  (chunkIndex, totalChunks) => console.log(`${chunkIndex + 1}/${totalChunks}`)
);
console.log("audio_url:", final?.audio_url);
```

### WebSocket 帧编码

```js
import { encodeWsFrame, constants } from "@info-tech/pcm-client";

const frame = encodeWsFrame(0, false, pcmChunk);
ws.send(frame);
```

## API

- **sendChunkHttp(baseUrl, opts)** — 发送单块 PCM，返回 JSON
- **uploadPcmHttp(baseUrl, opts, onProgress?)** — 整段 PCM 按块上传，返回最后一片的响应
- **encodeWsFrame(chunkIndex, isFinal, pcmPayload)** — 生成 WS 二进制帧
- **constants** — CHUNK_SIZE, SAMPLE_RATE, CHANNELS, BIT_DEPTH, PCM_FORMAT

## 协议文档

- [PCM Ingest API (HTTP)](../../info-tech/docs/PCM_INGEST_API.md)
- [WS PCM Streaming Protocol v1.0](../../info-tech/docs/WS_PCM_STREAMING_PROTOCOL_v1.0.md)

#!/usr/bin/env node
/**
 * Wearable caption bridge — 订阅后端 /ws/realtime/subscribe，将字幕与有害告警
 * 打印到控制台并可转发到本地 WebSocket，供「眼镜模拟」UI 或真机 SDK 消费。
 *
 * 用法:
 *   node tools/wearable-bridge.js [--base ws://localhost:8000] [--device-id web-extension] [--forward-port 9999]
 *
 * 依赖: npm install ws
 * 若指定 --forward-port，会启动本地 WebSocket 服务，将收到的 asr/harmful_alert 转发给连接的客户端。
 */

let WebSocket;
try {
  WebSocket = require('ws');
} catch (_) {
  console.error('Need "ws" package: npm install ws');
  process.exit(1);
}

const args = process.argv.slice(2);
function getArg(name, def) {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
}

const baseUrl = getArg('--base', 'ws://localhost:8000').replace(/^http/, 'ws');
const deviceId = getArg('--device-id', 'web-extension');
const forwardPort = parseInt(getArg('--forward-port', '0'), 10);

const subscribeUrl = `${baseUrl.replace(/\/$/, '')}/ws/realtime/subscribe?device_id=${encodeURIComponent(deviceId)}`;

let forwardServer = null;
const forwardClients = new Set();

if (forwardPort > 0) {
  forwardServer = new WebSocket.Server({ port: forwardPort });
  forwardServer.on('connection', (ws) => {
    forwardClients.add(ws);
    ws.on('close', () => forwardClients.delete(ws));
  });
  console.log(`[Bridge] Local WS server on port ${forwardPort}; connect for captions.`);
}

const ws = new WebSocket(subscribeUrl);
ws.on('open', () => console.log('[Bridge] Subscribed to', subscribeUrl));
ws.on('message', (data) => {
  try {
    const msg = JSON.parse(data.toString());
    if (msg.type === 'status') console.log('[Bridge]', msg.message);
    else if (msg.type === 'asr') {
      console.log('[ASR]', msg.is_final ? '■' : '□', msg.text);
      forwardClients.forEach((c) => { if (c.readyState === 1) c.send(data); });
    } else if (msg.type === 'harmful_alert') {
      console.log('[HARMFUL]', msg.text, 'severity=', msg.severity);
      forwardClients.forEach((c) => { if (c.readyState === 1) c.send(data); });
    }
  } catch (_) {}
});
ws.on('error', (err) => console.error('[Bridge]', err.message));
ws.on('close', () => console.log('[Bridge] Disconnected'));

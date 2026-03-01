const WebSocket = require("ws");

const HOST = "localhost";
const PORT = 8000;
const PATH = "/ws/ingest/pcm";

const deviceToken = "demo_token";
const sessionId = `sim_${Date.now()}`;
const deviceId = "sim_device";

const url = `ws://${HOST}:${PORT}${PATH}?device_token=${deviceToken}&session_id=${sessionId}&device_id=${deviceId}`;

const CHUNK_SIZE = 3200;
const TOTAL_CHUNKS = 18;

let expectedAck = 0;

function buildFrame(chunkIndex, isFinal, payload) {
  const header = Buffer.alloc(5);
  header.writeUInt32BE(chunkIndex, 0);
  header.writeUInt8(isFinal ? 0x01 : 0x00, 4);
  return Buffer.concat([header, payload]);
}

function makePcmChunk(size) {
  const buf = Buffer.alloc(size);
  for (let i = 0; i < size; i += 2) {
    // Simple saw wave
    const sample = (i / 2) % 200 - 100;
    buf.writeInt16LE(sample * 200, i);
  }
  return buf;
}

function sendNext(ws) {
  const isFinal = expectedAck === TOTAL_CHUNKS - 1;
  const payload = isFinal ? Buffer.alloc(0) : makePcmChunk(CHUNK_SIZE);
  const frame = buildFrame(expectedAck, isFinal, payload);
  ws.send(frame);
}

const ws = new WebSocket(url);

ws.on("open", () => {
  console.log("WS open:", url);
  sendNext(ws);
});

ws.on("message", (data) => {
  const msg = JSON.parse(data.toString("utf8"));
  if (msg.final) {
    console.log("Final ACK:", msg);
    ws.close();
    return;
  }
  if (msg.ok && typeof msg.chunk_index === "number") {
    console.log("ACK", msg.chunk_index, "received_bytes", msg.received_bytes);
    expectedAck += 1;
    if (expectedAck < TOTAL_CHUNKS) {
      sendNext(ws);
    } else {
      // Send final (zero payload) frame
      sendNext(ws);
    }
    return;
  }
  console.log("Server error:", msg);
});

ws.on("close", () => {
  console.log("WS closed");
});

ws.on("error", (err) => {
  console.error("WS error:", err.message);
});

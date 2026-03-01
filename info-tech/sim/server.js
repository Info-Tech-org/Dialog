const http = require("http");
const { WebSocketServer } = require("ws");

const PORT = 8000;
const PATH = "/ws/ingest/pcm";

// Simple in-memory session tracking
const sessions = new Map();

function getSessionIdFromUrl(url) {
  try {
    const u = new URL(url, `http://localhost:${PORT}`);
    return u.searchParams.get("session_id") || "unknown";
  } catch {
    return "unknown";
  }
}

function parseFrame(buffer) {
  if (buffer.length < 5) {
    return { error: "frame_too_short" };
  }
  const chunkIndex = buffer.readUInt32BE(0);
  const flags = buffer.readUInt8(4);
  const isFinal = (flags & 0x01) === 0x01;
  const payload = buffer.subarray(5);
  return { chunkIndex, isFinal, payload };
}

const server = http.createServer();
const wss = new WebSocketServer({ server, path: PATH });

wss.on("connection", (ws, req) => {
  const sessionId = getSessionIdFromUrl(req.url || "");
  const state = {
    expected: 0,
    receivedBytes: 0,
    chunks: 0,
    sessionId,
  };
  sessions.set(ws, state);
  console.log(`[CONN] session=${sessionId}  url=${req.url}`);

  ws.on("message", (data, isBinary) => {
    if (!isBinary) {
      console.log(`[WARN] text frame from session=${sessionId}`);
      ws.send(JSON.stringify({ ok: false, error: "text_not_supported" }));
      return;
    }

    const frame = parseFrame(Buffer.from(data));
    if (frame.error) {
      console.log(`[ERR]  parse error: ${frame.error}`);
      ws.send(JSON.stringify({ ok: false, error: frame.error }));
      return;
    }

    if (frame.chunkIndex !== state.expected) {
      console.log(`[ERR]  out_of_order: got=${frame.chunkIndex} expected=${state.expected}`);
      ws.send(
        JSON.stringify({
          ok: false,
          error: "out_of_order",
          expected: state.expected,
          chunk_index: frame.chunkIndex,
        })
      );
      return;
    }

    state.expected += 1;
    state.chunks += 1;
    state.receivedBytes += frame.payload.length;

    if (!frame.isFinal) {
      console.log(`[ACK]  chunk=${frame.chunkIndex}  payload=${frame.payload.length}B  total=${state.receivedBytes}B`);
      ws.send(
        JSON.stringify({
          ok: true,
          chunk_index: frame.chunkIndex,
          received_bytes: state.receivedBytes,
        })
      );
      return;
    }

    // Final ACK with fake audio_url
    const finalAck = {
      ok: true,
      final: true,
      session_id: state.sessionId,
      audio_url: `http://localhost:${PORT}/media/${state.sessionId}.wav`,
      received_bytes: state.receivedBytes,
      chunks: state.chunks,
    };
    console.log(`[FINAL] session=${sessionId}  chunks=${state.chunks}  bytes=${state.receivedBytes}`);
    console.log(`        audio_url=${finalAck.audio_url}`);
    ws.send(JSON.stringify(finalAck));
  });

  ws.on("close", () => {
    console.log(`[CLOSE] session=${sessionId}`);
    sessions.delete(ws);
  });
});

server.on("request", (req, res) => {
  if (req.url && req.url.startsWith("/media/")) {
    res.writeHead(200, { "Content-Type": "text/plain" });
    res.end("fake wav content");
    return;
  }
  res.writeHead(200, { "Content-Type": "text/plain" });
  res.end("ok");
});

server.listen(PORT, () => {
  console.log(`WS PCM simulator listening on ws://localhost:${PORT}${PATH}`);
});

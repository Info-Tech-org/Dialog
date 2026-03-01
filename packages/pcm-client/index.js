/**
 * @info-tech/pcm-client
 * HTTP and WebSocket PCM ingest client for Info-Tech backend.
 * Protocol: 16 kHz, mono, 16-bit s16le. Chunk size typically 3200 bytes (100ms).
 */

const CHUNK_SIZE = 3200;
const SAMPLE_RATE = 16000;
const CHANNELS = 1;
const BIT_DEPTH = 16;
const PCM_FORMAT = "s16le";

/**
 * Send one PCM chunk via HTTP POST.
 * @param {string} baseUrl - e.g. "http://localhost:8000"
 * @param {object} opts - { deviceToken?, deviceId?, sessionId?, chunkIndex, isFinal, pcmData }
 * @returns {Promise<object>} JSON response (ok, chunk_index or final, audio_url)
 */
export async function sendChunkHttp(baseUrl, opts) {
  const {
    deviceToken,
    deviceId = "",
    sessionId,
    chunkIndex,
    isFinal,
    pcmData,
  } = opts;
  const url = `${baseUrl.replace(/\/$/, "")}/api/ingest/pcm`;
  const headers = {
    "Content-Type": "application/octet-stream",
    "X-Session-Id": sessionId,
    "X-Chunk-Index": String(chunkIndex),
    "X-Is-Final": isFinal ? "1" : "0",
    "X-Sample-Rate": String(SAMPLE_RATE),
    "X-Channels": String(CHANNELS),
    "X-Bit-Depth": String(BIT_DEPTH),
    "X-PCM-Format": PCM_FORMAT,
  };
  if (deviceToken) headers["X-Device-Token"] = deviceToken;
  if (deviceId) headers["X-Device-Id"] = deviceId;

  const res = await fetch(url, {
    method: "POST",
    headers,
    body: pcmData,
  });
  if (res.status === 409) {
    const j = await res.json();
    throw new Error(`Out of order: expected_next_index=${j.expected_next_index ?? j.expected}`);
  }
  res.ok || (() => { throw new Error(`HTTP ${res.status}`); })();
  return res.json();
}

/**
 * Upload full PCM buffer via HTTP (multiple chunks).
 * @param {string} baseUrl
 * @param {object} opts - { deviceToken?, deviceId?, sessionId?, pcmBuffer }
 * @param {function} onProgress - optional (chunkIndex, totalChunks) => void
 * @returns {Promise<object>} Final response with audio_url if final chunk returned it
 */
export async function uploadPcmHttp(baseUrl, opts, onProgress) {
  const sessionId = opts.sessionId || crypto.randomUUID?.() || `web-${Date.now()}`;
  const buffer = opts.pcmBuffer;
  let lastResult;
  let offset = 0;
  let chunkIndex = 0;
  const totalChunks = Math.ceil(buffer.byteLength / CHUNK_SIZE) || 1;

  while (offset < buffer.byteLength) {
    const end = Math.min(offset + CHUNK_SIZE, buffer.byteLength);
    const chunk = buffer.slice(offset, end);
    const isFinal = end >= buffer.byteLength;
    lastResult = await sendChunkHttp(baseUrl, {
      deviceToken: opts.deviceToken,
      deviceId: opts.deviceId,
      sessionId,
      chunkIndex,
      isFinal,
      pcmData: chunk,
    });
    if (onProgress) onProgress(chunkIndex, totalChunks);
    chunkIndex++;
    offset = end;
  }
  return lastResult;
}

/**
 * Build WebSocket binary frame for PCM chunk (protocol v1.0).
 * [0-3] chunk_index uint32 BE, [4] flags (bit0=is_final), [5..] PCM payload
 */
export function encodeWsFrame(chunkIndex, isFinal, pcmPayload) {
  const buf = new ArrayBuffer(5 + pcmPayload.byteLength);
  const view = new DataView(buf);
  view.setUint32(0, chunkIndex, false);
  view.setUint8(4, isFinal ? 1 : 0);
  new Uint8Array(buf).set(new Uint8Array(pcmPayload), 5);
  return buf;
}

export const constants = { CHUNK_SIZE, SAMPLE_RATE, CHANNELS, BIT_DEPTH, PCM_FORMAT };

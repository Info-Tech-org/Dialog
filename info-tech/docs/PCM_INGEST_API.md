# PCM Ingest API Specification

> Note: This document describes the **HTTP POST** ingest API.
> For the **WebSocket streaming** protocol (binary chunks + JSON ACK + `audio_url`), see `docs/WS_PCM_STREAMING_PROTOCOL_v1.0.md`.

Status: Production Ready (Stable)

## Overview
- Purpose: Stream raw PCM audio chunks from devices to backend for processing and storage.
- Transport: HTTP POST with `application/octet-stream` body.
- Audio Format: 16 kHz, mono, 16-bit, `s16le` PCM.
- Chunking: 100 ms per chunk (3200 bytes). Final chunk flagged via header.
- Idempotency: Strict ordering enforcement with safe retries.

## Endpoint
- POST http://47.236.106.225:9000/api/ingest/pcm

## Required Headers
- X-Device-Token: Device token (required in production)
- X-Device-Id: Device identifier (recommended; used for filtering)
- X-Session-Id: Session UUID or unique string
- X-Chunk-Index: Non-negative integer starting at 0
- X-Is-Final: "0" or "1"
- X-Sample-Rate: "16000"
- X-Channels: "1"
- X-Bit-Depth: "16"
- X-PCM-Format: "s16le"

Optional:
- X-Filename: Client-provided name for traceability (e.g., "REC1.pcm")

## Idempotency & Ordering
- Duplicate: `chunk_index < expected` → `200 OK` (no duplicate write)
- Out-of-order: `chunk_index > expected` → `409 Conflict` with JSON `{expected_next_index: N}`
- Normal: `chunk_index == expected` → `200 OK` (append and increment)

## Responses
- Non-final chunk:
  ```json
  {"ok": true, "session_id": "...", "chunk": 5}
  ```
- Final chunk:
  ```json
  {"ok": true, "session_id": "...", "final": true, "audio_url": "http://..."}
  ```

## cURL Examples
- Send one chunk:
  ```bash
  curl -X POST \
    -H "Content-Type: application/octet-stream" \
    -H "X-Device-Token: <TOKEN>" \
    -H "X-Session-Id: <SESSION_UUID>" \
    -H "X-Chunk-Index: 0" \
    -H "X-Is-Final: 0" \
    -H "X-Sample-Rate: 16000" \
    -H "X-Channels: 1" \
    -H "X-Bit-Depth: 16" \
    -H "X-PCM-Format: s16le" \
    --data-binary @chunk0.pcm \
    http://47.236.106.225:9000/api/ingest/pcm
  ```
- Final chunk:
  ```bash
  curl -X POST \
    -H "Content-Type: application/octet-stream" \
    -H "X-Device-Token: <TOKEN>" \
    -H "X-Session-Id: <SESSION_UUID>" \
    -H "X-Chunk-Index: 12" \
    -H "X-Is-Final: 1" \
    -H "X-Sample-Rate: 16000" \
    -H "X-Channels: 1" \
    -H "X-Bit-Depth: 16" \
    -H "X-PCM-Format: s16le" \
    --data-binary @chunk12.pcm \
    http://47.236.106.225:9000/api/ingest/pcm
  ```

## Python Client Example
```python
import argparse
import os
import sys
import time
import uuid
import requests

BASE = "http://47.236.106.225:9000"
URL = BASE + "/api/ingest/pcm"

class PCMIngestClient:
    def __init__(self, device_token: str, session_id: str | None = None):
        self.device_token = device_token
        self.session_id = session_id or str(uuid.uuid4())
        self.expected = 0

    def send_chunk(self, data: bytes, idx: int, is_final: bool = False):
        headers = {
            "Content-Type": "application/octet-stream",
            "X-Device-Token": self.device_token,
            "X-Session-Id": self.session_id,
            "X-Chunk-Index": str(idx),
            "X-Is-Final": "1" if is_final else "0",
            "X-Sample-Rate": "16000",
            "X-Channels": "1",
            "X-Bit-Depth": "16",
            "X-PCM-Format": "s16le",
        }
        r = requests.post(URL, headers=headers, data=data, timeout=10)
        if r.status_code == 409:
            j = r.json()
            raise RuntimeError(f"Out-of-order: expected_next_index={j.get('expected_next_index')}")
        r.raise_for_status()
        return r.json()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--base", default=BASE)
    ap.add_argument("--duration", type=float, default=2.0)
    args = ap.parse_args()

    URL = args.base.rstrip("/") + "/api/ingest/pcm"
    client = PCMIngestClient(device_token=args.token)

    # Simulate PCM chunks: 2 seconds @ 16kHz mono s16le → 64,000 bytes
    total_bytes = int(args.duration * 16000 * 2)
    chunk_size = 3200
    buf = os.urandom(total_bytes)  # replace with real PCM

    idx = 0
    offset = 0
    while offset + chunk_size <= len(buf):
        j = client.send_chunk(buf[offset:offset+chunk_size], idx, False)
        idx += 1
        offset += chunk_size
        time.sleep(0.1)

    # Final chunk (remaining or empty)
    final = buf[offset:]
    j = client.send_chunk(final, idx, True)
    print("Final:", j)
```

## ESP32 C++ Example (Arduino)
- See `src/main.cpp` in this project. Core steps:
  - Configure I2S standard mono 16-bit at 16 kHz.
  - Buffer PCM and upload every 3200 bytes.
  - Send final marker with `X-Is-Final: 1`.
  - Include `X-Device-Token` and `X-Device-Id` headers.

```cpp
HTTPClient http;
http.begin(UPLOAD_API_URL);
http.addHeader("Content-Type", "application/octet-stream");
http.addHeader("X-Device-Token", DEVICE_TOKEN);
http.addHeader("X-Session-Id", sessionId);
http.addHeader("X-Chunk-Index", String(chunkIndex));
http.addHeader("X-Is-Final", is_final ? "1" : "0");
http.addHeader("X-Sample-Rate", "16000");
http.addHeader("X-Channels", "1");
http.addHeader("X-Bit-Depth", "16");
http.addHeader("X-PCM-Format", "s16le");
int code = http.POST(data, size);
```

## Sessions Query Filters
- Endpoint: `GET /api/sessions`
- Query params:
  - `device_id`: Filter by device identifier (e.g., `esp32c6-xiao-abcd`)
  - `has_harmful`: `true` to return sessions with harmful content, `false` otherwise
  - `limit`: Maximum number of records to return (default 100)
  - `offset`: Pagination offset (default 0)

### Examples
```bash
# Harmful sessions, max 5
curl "http://47.236.106.225:9000/api/sessions?has_harmful=true&limit=5"

# ESP32 device sessions
curl "http://47.236.106.225:9000/api/sessions?device_id=esp32&limit=10"

# Combined: ESP32 harmful sessions
curl "http://47.236.106.225:9000/api/sessions?device_id=esp32&has_harmful=true"

# Pagination
curl "http://47.236.106.225:9000/api/sessions?offset=0&limit=20"
```

## Testing
- Reference command:
  ```bash
  python tools/test_pcm_ingest.py \
    --base http://47.236.106.225:9000 \
    --duration 2.0 \
    --token <DEVICE_TOKEN>
  ```
- Expected results:
  - Final chunk response ~200–300 ms
  - Status: processing → completed (~9 s)
  - `audio_url` points to WAV on `/media/`

## FAQ
- Q: What if network drops mid-session?
  - A: Resume from last acknowledged `expected_next_index`; duplicates are safely ignored.
- Q: Is `X-Filename` required?
  - A: No; it’s optional for tracing.
- Q: Do you accept other rates/channels?
  - A: Current production accepts 16k mono s16le. Contact backend team for changes.

## Changelog
- d90585e - feat(ingest): enforce idempotent chunking with ordering control
- 68ef920 - docs(ingest): add PCM ingest API specification with examples

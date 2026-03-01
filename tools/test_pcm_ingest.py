import argparse
import math
import struct
import time
import uuid
import httpx
import os


def generate_sine_pcm(duration_sec: float, sample_rate: int = 16000, freq: float = 440.0, amp: float = 0.3):
    total_samples = int(duration_sec * sample_rate)
    pcm = bytearray()
    for i in range(total_samples):
        t = i / sample_rate
        val = int(amp * 32767 * math.sin(2 * math.pi * freq * t))
        pcm.extend(struct.pack("<h", val))
    return bytes(pcm)


def chunk_bytes(data: bytes, chunk_size: int):
    for i in range(0, len(data), chunk_size):
        yield data[i : i + chunk_size]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000", help="Base URL, e.g. http://localhost:8000")
    parser.add_argument("--session", default=str(uuid.uuid4()))
    parser.add_argument("--duration", type=float, default=2.0)
    parser.add_argument("--token", help="Device ingest token (overrides DEVICE_INGEST_TOKEN env)")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    session_id = args.session
    pcm = generate_sine_pcm(args.duration)
    chunk_size = 3200  # 100ms @ 16kHz, 16-bit mono

    # Get device token from args or environment
    device_token = args.token or os.getenv("DEVICE_INGEST_TOKEN")

    headers_common = {
        "X-Session-Id": session_id,
        "X-Sample-Rate": "16000",
        "X-Channels": "1",
        "X-Bit-Depth": "16",
        "X-PCM-Format": "s16le",
        "Content-Type": "application/octet-stream",
    }

    # Add device token if provided
    if device_token:
        headers_common["X-Device-Token"] = device_token
        print(f"Using device token: {device_token[:8]}..." if len(device_token) > 8 else device_token)

    with httpx.Client(timeout=30.0, trust_env=False) as client:
        total_chunks = 0
        final_start_time = None
        final_end_time = None

        for idx, chunk in enumerate(chunk_bytes(pcm, chunk_size)):
            is_final = 1 if (idx + 1) * chunk_size >= len(pcm) else 0
            headers = headers_common | {
                "X-Chunk-Index": str(idx),
                "X-Is-Final": str(is_final),
            }

            if is_final:
                final_start_time = time.time()

            resp = client.post(f"{base}/api/ingest/pcm", headers=headers, content=chunk)
            resp.raise_for_status()

            if is_final:
                final_end_time = time.time()
                final_response_ms = int((final_end_time - final_start_time) * 1000)
                print(f"Final chunk response time: {final_response_ms}ms")

            total_chunks += 1

        # Poll status with status transitions tracking
        status_url = f"{base}/api/ingest/status/{session_id}"
        print(f"\nPolling status for session {session_id}...")
        status_history = []
        poll_start = time.time()

        # Build headers for status check (need token if enabled)
        status_headers = {}
        if device_token:
            status_headers["X-Device-Token"] = device_token

        for i in range(30):
            resp = client.get(status_url, headers=status_headers)
            if resp.status_code == 404:
                print(f"  [{i}] Status: 404 (not found yet)")
                time.sleep(1)
                continue
            resp.raise_for_status()
            status = resp.json()
            current_status = status.get("status")

            # Track status transitions
            if not status_history or status_history[-1] != current_status:
                elapsed = int((time.time() - poll_start) * 1000)
                print(f"  [{i}] Status transition: {current_status} (+{elapsed}ms)")
                status_history.append(current_status)

            if current_status in {"completed", "error"}:
                break
            time.sleep(1)

        if status.get("status") != "completed":
            raise SystemExit(f"status not completed: {status}")

        # Verify session detail
        detail = client.get(f"{base}/api/sessions/{session_id}").json()
        audio_url = detail.get("audio_url")
        if not audio_url:
            raise SystemExit("audio_url is empty")

        head = client.head(audio_url)
        if head.status_code not in (200, 206):
            raise SystemExit(f"audio_url HEAD status {head.status_code}")
        content_type = head.headers.get("content-type", "")
        content_length = int(head.headers.get("content-length", "0"))
        if "text/html" in content_type or content_length < 10000:
            raise SystemExit(f"invalid content type/length: {content_type} {content_length}")

        print(f"OK session_id={session_id}")
        print(f"audio_url={audio_url}")
        print(f"head_status={head.status_code} content_length={content_length}")


if __name__ == "__main__":
    main()

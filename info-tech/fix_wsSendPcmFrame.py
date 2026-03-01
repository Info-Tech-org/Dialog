import os

filepath = r"c:\Users\charlie\Documents\platformIO\Projects\Info-tech\src\main.cpp"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lines 320-385 (0-indexed) = the old wsSendPcmFrame body (after the if block closing brace on line 318)
# We replace lines 320 through 385 (inclusive) with the new implementation

new_body = """\
  // Frame: [0..3] chunk_index(u32 BE) [4] flags(bit0=is_final) [5..] payload
  const size_t headerSize = 5;
  uint8_t frameHeader[headerSize];
  frameHeader[0] = (uint8_t)((chunk_idx >> 24) & 0xFF);
  frameHeader[1] = (uint8_t)((chunk_idx >> 16) & 0xFF);
  frameHeader[2] = (uint8_t)((chunk_idx >> 8) & 0xFF);
  frameHeader[3] = (uint8_t)(chunk_idx & 0xFF);
  frameHeader[4] = is_final ? 0x01 : 0x00;

  if (size > (size_t)CHUNK_SIZE) {
    wsClose();
    return false;
  }

  static uint8_t* frameBuf = NULL;
  if (frameBuf == NULL) {
    frameBuf = (uint8_t*)malloc(CHUNK_SIZE + 5);
    if (frameBuf == NULL) { wsClose(); return false; }
  }
  memcpy(frameBuf, frameHeader, headerSize);
  if (size > 0 && data != NULL) {
    memcpy(frameBuf + headerSize, data, size);
  }

  const size_t frameLen = headerSize + size;
#if DEBUG_WS_LOG
  Serial.printf("WS send chunk %lu size=%u final=%d\\n",
                (unsigned long)chunk_idx, (unsigned int)size, (int)is_final);
#endif

  // Pre-send loop: digest stale ACKs / pings to keep connection healthy
  wsClient.loop();
  if (!wsConnected) return false;

  if (!wsClient.sendBIN(frameBuf, frameLen)) {
    wsClose();
    return false;
  }

  if (!is_final) {
    // ===== Non-final: fire-and-forget =====
    // Quick loops to flush TCP send buffer, don't block waiting for ACK
    for (int i = 0; i < 3; i++) {
      wsClient.loop();
      if (!wsConnected) return false;
      delay(1);
    }
    return true;
  }

  // ===== Final chunk: wait for server ACK (with audio_url) =====
  wsResetAckState();
  const unsigned long ackTimeout = 10000;  // 10s for final
  unsigned long start = millis();
  while (millis() - start < ackTimeout) {
    wsClient.loop();
    if (!wsConnected) return false;
    if (wsAckReceived) {
      if (wsAckOk) {
        if (wsLastAudioUrl.length() > 0) {
          Serial.print("WS final audio_url: ");
          Serial.println(wsLastAudioUrl);
        }
        if (wsAckChunkIndex == chunk_idx) {
          return true;  // Perfect match for final ACK
        }
        // Got a delayed ACK for an earlier data chunk, keep waiting for final
        wsResetAckState();
        continue;
      }
      Serial.println("WS final ack error from server");
      return false;
    }
    delay(5);
  }
#if DEBUG_WS_LOG
  Serial.printf("WS final ack timeout chunk %lu\\n", (unsigned long)chunk_idx);
#endif
  return false;
}
"""

new_lines = [line + '\n' for line in new_body.split('\n')]

# Replace lines 320-385 (0-indexed, inclusive)
result = lines[:320] + new_lines + lines[386:]

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(result)

print(f"Done. Old lines: {len(lines)}, New lines: {len(result)}")
print(f"Replaced lines 321-386 (1-indexed) with {len(new_lines)} new lines")

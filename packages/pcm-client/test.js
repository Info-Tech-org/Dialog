// Smoke test: import and encode one frame
import { encodeWsFrame, constants } from "./index.js";
const payload = new ArrayBuffer(3200);
const frame = encodeWsFrame(0, false, payload);
console.assert(frame.byteLength === 3205, "frame size");
console.log("OK: @info-tech/pcm-client");

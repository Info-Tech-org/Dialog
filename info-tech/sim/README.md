# Local WS PCM Simulator

This folder contains a minimal WebSocket server and client to simulate the PCM ingest protocol locally.

## Setup

```powershell
cd sim
npm install
```

## Run server

```powershell
npm run server
```

## Run client (in another terminal)

```powershell
npm run client
```

## Notes
- Server listens at `ws://localhost:9000/ws/ingest/pcm`.
- Client sends frames with `[u32 BE chunk_index][flags][pcm payload]`.
- Final ACK includes a fake `audio_url`.

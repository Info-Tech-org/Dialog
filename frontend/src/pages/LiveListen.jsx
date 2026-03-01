import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

// ─── AudioWorklet inline processor ───────────────────────────────────────────
const WORKLET_CODE = `
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._chunks = [];
    this._totalSamples = 0;
    this._dropped = 0;
    this._pos = 0;
    this.port.onmessage = (e) => {
      if (e.data.type === 'samples') {
        this._chunks.push(e.data.samples);
        this._totalSamples += e.data.samples.length;
      } else if (e.data.type === 'getStats') {
        this.port.postMessage({ type: 'stats', queueDepth: this._totalSamples, dropped: this._dropped });
      }
    };
  }
  process(inputs, outputs) {
    const output = outputs[0][0];
    const len = output.length;
    let written = 0;
    while (written < len) {
      if (this._chunks.length === 0) {
        output.fill(0, written);
        if (written > 0) this._dropped++;
        break;
      }
      const chunk = this._chunks[0];
      const avail = chunk.length - this._pos;
      const need = len - written;
      if (avail <= need) {
        output.set(chunk.subarray(this._pos), written);
        written += avail;
        this._totalSamples -= avail;
        this._chunks.shift();
        this._pos = 0;
      } else {
        output.set(chunk.subarray(this._pos, this._pos + need), written);
        this._pos += need;
        this._totalSamples -= need;
        written = len;
      }
    }
    return true;
  }
}
registerProcessor('pcm-player-processor', PCMPlayerProcessor);
`;

// ─── Utilities ────────────────────────────────────────────────────────────────
function linearResample(input, fromRate, toRate) {
  if (fromRate === toRate) return input;
  const ratio = toRate / fromRate;
  const outLen = Math.round(input.length * ratio);
  const output = new Float32Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const pos = i / ratio;
    const idx = Math.floor(pos);
    const frac = pos - idx;
    const a = idx < input.length ? input[idx] : 0;
    const b = (idx + 1) < input.length ? input[idx + 1] : a;
    output[i] = a + (b - a) * frac;
  }
  return output;
}

function fmtBytes(b) {
  if (b < 1024) return b + ' B';
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
  return (b / 1048576).toFixed(2) + ' MB';
}

function fmtTime(ms) {
  if (!ms) return '';
  return new Date(ms).toLocaleTimeString('zh-CN', { hour12: false });
}

// ─── Component ────────────────────────────────────────────────────────────────
function LiveListen() {
  const navigate = useNavigate();

  // UI state
  const [devices, setDevices] = useState([]);
  const [activeDeviceIds, setActiveDeviceIds] = useState(new Set());
  const [selectedDevice, setSelectedDevice] = useState(null);
  const [phase, setPhase] = useState('idle'); // idle | selected | running
  const [audioCtxState, setAudioCtxState] = useState('');
  const [audioMethod, setAudioMethod] = useState('');
  const [ctxSampleRate, setCtxSampleRate] = useState(0);
  const [status, setStatus] = useState('idle'); // idle | waiting | live
  const [subtitles, setSubtitles] = useState([]);
  const [partialText, setPartialText] = useState('');
  const [alerts, setAlerts] = useState([]);
  const [firstCaptionLatency, setFirstCaptionLatency] = useState(null);
  const [debugStats, setDebugStats] = useState({
    framesPerSec: 0, totalBytes: 0, lastSize: 0, queueDepth: 0, dropped: 0,
    inputRms: 0, oddFrames: 0, nonBinaryFrames: 0,
  });
  const [recentFrames, setRecentFrames] = useState([]);
  const [playGain, setPlayGain] = useState(1.0);
  const [ambientMode, setAmbientMode] = useState(true);
  const [showDebug, setShowDebug] = useState(false);
  const [reconnectMsg, setReconnectMsg] = useState('');

  // Stable refs
  const audioCtxRef = useRef(null);
  const workletNodeRef = useRef(null);
  const scriptProcRef = useRef(null);
  const gainNodeRef = useRef(null);
  const audioQueueRef = useRef(new Float32Array(0));
  const audioMethodRef = useRef('none');
  const wsAudioRef = useRef(null);
  const wsAsrRef = useRef(null);
  const isRunningRef = useRef(false);
  const firstCaptionTimeRef = useRef(null);
  const subtitleIdRef = useRef(0);
  const audioReconnDelayRef = useRef(1000);
  const asrReconnDelayRef = useRef(1000);
  const audioReconnTimerRef = useRef(null);
  const asrReconnTimerRef = useRef(null);
  const debugTimerRef = useRef(null);
  const rawStatsRef = useRef({
    frames: 0, totalBytes: 0, lastSize: 0, dropped: 0, lastFramesSnap: 0,
    inputRms: 0, oddFrames: 0, nonBinaryFrames: 0, recentFrames: [],
  });
  const subtitlesEndRef = useRef(null);
  const ambientRef = useRef(null);

  // ── Stop (defined early for cleanup effect) ───────────────────────────────
  const stopListening = useCallback(() => {
    isRunningRef.current = false;
    if (debugTimerRef.current) { clearInterval(debugTimerRef.current); debugTimerRef.current = null; }
    if (audioReconnTimerRef.current) { clearTimeout(audioReconnTimerRef.current); audioReconnTimerRef.current = null; }
    if (asrReconnTimerRef.current) { clearTimeout(asrReconnTimerRef.current); asrReconnTimerRef.current = null; }
    if (wsAudioRef.current) { wsAudioRef.current.close(); wsAudioRef.current = null; }
    if (wsAsrRef.current) { wsAsrRef.current.close(); wsAsrRef.current = null; }
    if (workletNodeRef.current) { workletNodeRef.current.disconnect(); workletNodeRef.current = null; }
    if (scriptProcRef.current) { scriptProcRef.current.disconnect(); scriptProcRef.current = null; }
    gainNodeRef.current = null;
    if (audioCtxRef.current) { audioCtxRef.current.close(); audioCtxRef.current = null; }
    audioQueueRef.current = new Float32Array(0);
    audioMethodRef.current = 'none';
    setPhase('selected');
    setStatus('idle');
    setAudioCtxState('');
    setAudioMethod('');
    setCtxSampleRate(0);
    setReconnectMsg('');
    setPartialText('');
    setRecentFrames([]);
    setShowDebug(false);
  }, []); // eslint-disable-line

  // ── PCM frame handler ─────────────────────────────────────────────────────
  const pushRecentFrame = useCallback((frame) => {
    const s = rawStatsRef.current;
    s.recentFrames.push(frame);
    if (s.recentFrames.length > 10) s.recentFrames.shift();
  }, []);

  const handlePCMFrame = useCallback((arrayBuffer) => {
    const ctx = audioCtxRef.current;
    if (!ctx) return;
    if (ctx.state === 'suspended') ctx.resume();

    const frameBytes = arrayBuffer.byteLength;
    const alignedBytes = frameBytes - (frameBytes % 2);
    if (frameBytes % 2 !== 0) rawStatsRef.current.oddFrames++;
    if (alignedBytes <= 0) return;

    const int16 = new Int16Array(arrayBuffer, 0, alignedBytes / 2);
    const float32 = new Float32Array(int16.length);
    let sumSq = 0;
    for (let i = 0; i < int16.length; i++) {
      const v = int16[i] / 32768.0;
      float32[i] = v;
      sumSq += v * v;
    }
    const inputRms = float32.length > 0 ? Math.sqrt(sumSq / float32.length) : 0;

    const samples = ctx.sampleRate !== 16000
      ? linearResample(float32, 16000, ctx.sampleRate)
      : float32;

    if (audioMethodRef.current === 'worklet' && workletNodeRef.current) {
      workletNodeRef.current.port.postMessage({ type: 'samples', samples }, [samples.buffer]);
    } else if (audioMethodRef.current === 'scriptproc') {
      const prev = audioQueueRef.current;
      const combined = new Float32Array(prev.length + samples.length);
      combined.set(prev);
      combined.set(samples, prev.length);
      audioQueueRef.current = combined;
    }

    const s = rawStatsRef.current;
    s.frames++;
    s.totalBytes += alignedBytes;
    s.lastSize = frameBytes;
    s.inputRms = inputRms;
    pushRecentFrame({
      ts: Date.now(),
      bytes: frameBytes,
      isArrayBuffer: true,
      rms: Number(inputRms.toFixed(5)),
    });
  }, [pushRecentFrame]); // eslint-disable-line

  // ── Audio setup ───────────────────────────────────────────────────────────
  const setupAudio = useCallback(async () => {
    const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
    const ctx = new AudioCtxClass();
    audioCtxRef.current = ctx;
    const gainNode = ctx.createGain();
    gainNode.gain.value = playGain;
    gainNodeRef.current = gainNode;
    ctx.onstatechange = () => setAudioCtxState(ctx.state);
    if (ctx.state === 'suspended') await ctx.resume();
    setAudioCtxState(ctx.state);
    setCtxSampleRate(ctx.sampleRate);

    let method = 'scriptproc';
    try {
      const blob = new Blob([WORKLET_CODE], { type: 'application/javascript' });
      const blobUrl = URL.createObjectURL(blob);
      await ctx.audioWorklet.addModule(blobUrl);
      URL.revokeObjectURL(blobUrl);
      const node = new AudioWorkletNode(ctx, 'pcm-player-processor');
      node.port.onmessage = (e) => {
        if (e.data.type === 'stats') {
          const s = rawStatsRef.current;
          const fps = s.frames - s.lastFramesSnap;
          s.lastFramesSnap = s.frames;
          setDebugStats({
            framesPerSec: fps,
            totalBytes: s.totalBytes,
            lastSize: s.lastSize,
            queueDepth: e.data.queueDepth,
            dropped: e.data.dropped,
            inputRms: s.inputRms,
            oddFrames: s.oddFrames,
            nonBinaryFrames: s.nonBinaryFrames,
          });
          setRecentFrames([...s.recentFrames]);
        }
      };
      node.connect(gainNode);
      gainNode.connect(ctx.destination);
      workletNodeRef.current = node;
      method = 'worklet';
    } catch (err) {
      console.warn('[Audio] AudioWorklet unavailable, falling back to ScriptProcessor:', err);
      const sp = ctx.createScriptProcessor(4096, 0, 1);
      sp.onaudioprocess = (event) => {
        const output = event.outputBuffer.getChannelData(0);
        const queue = audioQueueRef.current;
        if (queue.length >= output.length) {
          output.set(queue.subarray(0, output.length));
          audioQueueRef.current = queue.subarray(output.length).slice();
        } else {
          if (queue.length > 0) output.set(queue);
          output.fill(0, queue.length);
          if (queue.length > 0) rawStatsRef.current.dropped++;
          audioQueueRef.current = new Float32Array(0);
        }
      };
      sp.connect(gainNode);
      gainNode.connect(ctx.destination);
      scriptProcRef.current = sp;
    }
    audioMethodRef.current = method;
    setAudioMethod(method);
  }, [playGain]); // eslint-disable-line

  // ── Connect audio WS ──────────────────────────────────────────────────────
  const connectAudioWS = useCallback((deviceId) => {
    if (!isRunningRef.current) return;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/ingest/device-listen?device_id=${deviceId}`);
    ws.binaryType = 'arraybuffer';
    wsAudioRef.current = ws;

    ws.onopen = () => {
      audioReconnDelayRef.current = 1000;
      setStatus('waiting');
      setReconnectMsg('');
    };
    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        setStatus('live');
        handlePCMFrame(event.data);
      } else if (event.data instanceof Blob) {
        event.data.arrayBuffer()
          .then((buf) => {
            if (!isRunningRef.current) return;
            setStatus('live');
            handlePCMFrame(buf);
          })
          .catch(() => {
            rawStatsRef.current.nonBinaryFrames++;
          });
      } else {
        rawStatsRef.current.nonBinaryFrames++;
        try {
          const msg = JSON.parse(event.data);
          pushRecentFrame({
            ts: Date.now(),
            bytes: String(event.data || '').length,
            isArrayBuffer: false,
            rms: 0,
          });
          if (msg.type === 'boundary') setStatus('waiting');
        } catch (e) { /* ignore */ }
      }
    };
    ws.onerror = () => {};
    ws.onclose = () => {
      if (!isRunningRef.current) return;
      setStatus('idle');
      const delay = audioReconnDelayRef.current;
      audioReconnDelayRef.current = Math.min(delay * 2, 30000);
      setReconnectMsg(`音频流断开，${(delay / 1000).toFixed(0)}s 后重连...`);
      audioReconnTimerRef.current = setTimeout(() => connectAudioWS(deviceId), delay);
    };
  }, [handlePCMFrame, pushRecentFrame]); // eslint-disable-line

  // ── Connect ASR WS ────────────────────────────────────────────────────────
  const connectAsrWS = useCallback((deviceId) => {
    if (!isRunningRef.current) return;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${window.location.host}/ws/realtime/subscribe?device_id=${deviceId}`);
    wsAsrRef.current = ws;

    ws.onopen = () => {
      asrReconnDelayRef.current = 1000;
      firstCaptionTimeRef.current = performance.now();
    };
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'asr') {
          if (msg.is_final) {
            if (firstCaptionTimeRef.current !== null) {
              const latency = Math.round(performance.now() - firstCaptionTimeRef.current);
              setFirstCaptionLatency(prev => prev === null ? latency : prev);
              firstCaptionTimeRef.current = null;
            }
            subtitleIdRef.current++;
            setSubtitles(prev => [...prev.slice(-99), {
              id: subtitleIdRef.current,
              text: msg.text,
              ts_ms: msg.ts_ms,
              speaker: msg.speaker || null,
            }]);
            setPartialText('');
          } else {
            setPartialText(msg.text);
          }
        } else if (msg.type === 'harmful_alert') {
          setAlerts(prev => [...prev.slice(-19), {
            text: msg.text,
            severity: msg.severity,
            keywords: msg.keywords || [],
          }]);
        }
      } catch (e) { /* ignore */ }
    };
    ws.onerror = (e) => console.error('[ASR WS] error', e);
    ws.onclose = () => {
      if (!isRunningRef.current) return;
      const delay = asrReconnDelayRef.current;
      asrReconnDelayRef.current = Math.min(delay * 2, 30000);
      asrReconnTimerRef.current = setTimeout(() => connectAsrWS(deviceId), delay);
    };
  }, []); // eslint-disable-line

  const playTestTone = useCallback(async () => {
    const ctx = audioCtxRef.current;
    if (!ctx) return;
    if (ctx.state === 'suspended') await ctx.resume();
    const outputNode = gainNodeRef.current || ctx.destination;
    const osc = ctx.createOscillator();
    const env = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.value = 440;
    env.gain.setValueAtTime(0.0001, ctx.currentTime);
    env.gain.exponentialRampToValueAtTime(0.2, ctx.currentTime + 0.02);
    env.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 1.0);
    osc.connect(env);
    env.connect(outputNode);
    osc.start();
    osc.stop(ctx.currentTime + 1.05);
  }, []);

  // ── Start listening ───────────────────────────────────────────────────────
  const startListening = useCallback(async (deviceId) => {
    isRunningRef.current = true;
    setPhase('running');
    setStatus('idle');
    setSubtitles([]);
    setPartialText('');
    setAlerts([]);
    setFirstCaptionLatency(null);
    setReconnectMsg('');
    setShowDebug(false);
    setAmbientMode(true);
    rawStatsRef.current = {
      frames: 0, totalBytes: 0, lastSize: 0, dropped: 0, lastFramesSnap: 0,
      inputRms: 0, oddFrames: 0, nonBinaryFrames: 0, recentFrames: [],
    };
    setRecentFrames([]);
    audioQueueRef.current = new Float32Array(0);
    subtitleIdRef.current = 0;
    audioReconnDelayRef.current = 1000;
    asrReconnDelayRef.current = 1000;

    await setupAudio();
    connectAudioWS(deviceId);
    connectAsrWS(deviceId);

    debugTimerRef.current = setInterval(() => {
      if (audioMethodRef.current === 'worklet' && workletNodeRef.current) {
        // Worklet reports stats async; setDebugStats happens in node.port.onmessage
        workletNodeRef.current.port.postMessage({ type: 'getStats' });
      } else {
        const s = rawStatsRef.current;
        const fps = s.frames - s.lastFramesSnap;
        s.lastFramesSnap = s.frames;
        setDebugStats({
          framesPerSec: fps,
          totalBytes: s.totalBytes,
          lastSize: s.lastSize,
          queueDepth: audioQueueRef.current.length,
          dropped: s.dropped,
          inputRms: s.inputRms,
          oddFrames: s.oddFrames,
          nonBinaryFrames: s.nonBinaryFrames,
        });
        setRecentFrames([...s.recentFrames]);
      }
    }, 1000);
  }, [setupAudio, connectAudioWS, connectAsrWS]); // eslint-disable-line

  useEffect(() => {
    if (gainNodeRef.current) gainNodeRef.current.gain.value = playGain;
  }, [playGain]);

  // Lightweight visualization driven by rAF (avoid React state updates in hot path)
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const el = ambientRef.current;
      if (el) {
        const rms = Number(rawStatsRef.current?.inputRms || 0);
        const p = Math.max(0, Math.min(1, rms * 6.0)); // map ~0.0-0.16 to 0-1
        el.style.setProperty('--pulse', String(p.toFixed(3)));
      }
      raf = requestAnimationFrame(tick);
    };
    if (phase === 'running') raf = requestAnimationFrame(tick);
    return () => { if (raf) cancelAnimationFrame(raf); };
  }, [phase]);

  // ── Select device (stop current if running) ───────────────────────────────
  const selectDevice = useCallback((deviceId) => {
    if (isRunningRef.current) stopListening();
    setSelectedDevice(deviceId);
    setPhase('selected');
    setSubtitles([]);
    setPartialText('');
    setAlerts([]);
    setFirstCaptionLatency(null);
  }, [stopListening]);

  // ── Device polling ────────────────────────────────────────────────────────
  const loadDevices = useCallback(async () => {
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch('/api/devices', { headers: { Authorization: `Bearer ${token}` } });
      if (res.ok) setDevices(await res.json());
    } catch (e) { console.error('loadDevices', e); }
  }, []);

  const pollActive = useCallback(async () => {
    try {
      const res = await fetch('/ws/ingest/active');
      if (res.ok) {
        const data = await res.json();
        setActiveDeviceIds(new Set((data.active || []).map(s => s.device_id).filter(Boolean)));
      }
    } catch (e) { console.error('pollActive', e); }
  }, []);

  useEffect(() => {
    loadDevices();
    pollActive();
    let t = null;
    const start = () => { if (!t) t = setInterval(pollActive, 5000); };
    const stop = () => { if (t) { clearInterval(t); t = null; } };
    const onVis = () => (document.hidden ? stop() : start());
    start();
    document.addEventListener('visibilitychange', onVis);
    return () => { stop(); document.removeEventListener('visibilitychange', onVis); };
  }, [loadDevices, pollActive]);

  useEffect(() => {
    return () => { if (isRunningRef.current) stopListening(); };
  }, [stopListening]);

  useEffect(() => {
    if (subtitlesEndRef.current) {
      subtitlesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [subtitles, partialText]);

  // ── Status label ──────────────────────────────────────────────────────────
  const statusLabel = { idle: '空闲', waiting: '等待设备录音...', live: '正在收音' };
  const statusColor = { idle: '#555', waiting: '#faad14', live: '#00ff88' };

  const selectedDeviceInfo = devices.find(d => d.device_id === selectedDevice);

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="live-page">
      <div className="live-layout">
        {/* ── 左侧设备列表 ── */}
        <aside className="live-sidebar card-bar">
          <h3 className="live-section-title">我的设备</h3>
          {devices.length === 0 ? (
            <div className="live-empty">
              暂无绑定设备
              <button type="button" className="btn-secondary" onClick={() => navigate('/devices')}>
                去绑定设备
              </button>
            </div>
          ) : (
            <div className="live-device-list">
              {devices.map((d) => {
                const isActive = activeDeviceIds.has(d.device_id);
                const isSelected = selectedDevice === d.device_id;
                return (
                  <button
                    type="button"
                    key={d.device_id}
                    className={`live-device-item ${isSelected ? 'live-device-item--active' : ''}`}
                    onClick={() => selectDevice(d.device_id)}
                  >
                    <span
                      className={`live-device-indicator live-device-indicator--${isActive ? 'recording' : d.is_online ? 'online' : 'offline'}`}
                    />
                    <div className="live-device-info">
                      <span className="live-device-id">{d.name || d.device_id}</span>
                      <span className="live-device-meta">
                        {isActive ? '录音中' : (d.is_online ? '在线' : '离线')}
                      </span>
                    </div>
                    {isSelected && phase === 'running' && <span className="live-device-badge">监听中</span>}
                  </button>
                );
              })}
            </div>
          )}
        </aside>

        {/* ── 右侧主面板 ── */}
        <div className="live-player">
          {/* 空状态 */}
          {phase === 'idle' && (
            <div className="live-placeholder" style={{ margin: 'auto' }}>
              选择左侧设备开始监听
              <span style={{ fontSize: 13, color: '#888', marginTop: 8, display: 'block' }}>
                选择设备后点击"开始监听"
              </span>
            </div>
          )}

          {/* 已选设备，未开始 */}
          {phase === 'selected' && selectedDevice && (
            <div className="live-start-panel">
              <div className="live-start-device">
                {selectedDeviceInfo?.name || selectedDevice}
              </div>
              <div className="live-start-device-id">
                {selectedDeviceInfo?.name ? selectedDevice : ''}
              </div>
              <p className="live-start-hint">
                点击下方按钮开始实时监听。首次使用需允许浏览器播放音频。
              </p>
              <button
                className="live-start-btn"
                onClick={() => startListening(selectedDevice)}
              >
                开始监听
              </button>
            </div>
          )}

          {/* 运行中 */}
          {phase === 'running' && selectedDevice && (
            <div className="live-playing">
              {/* 状态行 */}
              <div className={`live-status live-status--${status}`}>
                <span className="live-dot" />
                <span className="live-status-text">
                  {statusLabel[status] || ''}
                </span>
                {reconnectMsg && (
                  <span className="live-reconnect-info">{reconnectMsg}</span>
                )}
              </div>

              {/* AudioContext 状态行 */}
              <div className="live-ctx-row">
                <span className="live-ctx-label">AudioContext</span>
                <span className={`live-ctx-state live-ctx-state--${audioCtxState}`}>
                  {audioCtxState || '—'}
                </span>
                {audioMethod && (
                  <span className="live-ctx-method">[{audioMethod}]</span>
                )}
                {ctxSampleRate > 0 && (
                  <span className="live-ctx-rate">{ctxSampleRate.toLocaleString()} Hz</span>
                )}
              </div>

              <div className="live-audio-controls">
                <button className="live-test-tone-btn" onClick={playTestTone}>
                  播放测试音(440Hz)
                </button>
                <label className="live-gain-wrap">
                  增益
                  <input
                    type="range"
                    min="0"
                    max="3"
                    step="0.1"
                    value={playGain}
                    onChange={(e) => setPlayGain(Number(e.target.value))}
                  />
                  <span className="live-gain-value">{playGain.toFixed(1)}x</span>
                </label>
              </div>

              <div className="live-mode-row">
                <button
                  className={`live-mode-btn${ambientMode ? ' active' : ''}`}
                  onClick={() => setAmbientMode(true)}
                >
                  氛围模式
                </button>
                <button
                  className={`live-mode-btn${!ambientMode ? ' active' : ''}`}
                  onClick={() => setAmbientMode(false)}
                >
                  详细模式
                </button>
                <button
                  className={`live-mode-btn live-mode-btn--ghost${showDebug ? ' active' : ''}`}
                  onClick={() => setShowDebug(v => !v)}
                >
                  调试
                </button>
              </div>

              {ambientMode && (
                <div className="live-ambient" ref={ambientRef}>
                  <div className="live-ambient-top">Ambient Emotional Flow (Live)</div>
                  <div className="live-ambient-orb" />
                  <div className="live-ambient-center">
                    <div className="live-ambient-line1">Just listening to the rhythm</div>
                    <div className="live-ambient-line2">of our thoughts</div>
                  </div>
                  <div className="live-ambient-subtitles">
                    {subtitles.slice(-3).map(s => (
                      <div key={s.id} className="live-ambient-subtitle">
                        <span className="live-ambient-subtime">{fmtTime(s.ts_ms)}</span>
                        <span className="live-ambient-subtext">{s.text}</span>
                      </div>
                    ))}
                    {partialText && (
                      <div className="live-ambient-subtitle live-ambient-subtitle--partial">
                        <span className="live-ambient-subtime">…</span>
                        <span className="live-ambient-subtext">{partialText}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {showDebug && (
                <div className="live-debug-panel">
                  <div className="live-debug-title">调试面板</div>
                  <div className="live-debug-grid">
                    <div className="live-debug-item">
                      <span className="live-debug-label">帧/s</span>
                      <span className="live-debug-value">{debugStats.framesPerSec}</span>
                    </div>
                    <div className="live-debug-item">
                      <span className="live-debug-label">累计</span>
                      <span className="live-debug-value">{fmtBytes(debugStats.totalBytes)}</span>
                    </div>
                    <div className="live-debug-item">
                      <span className="live-debug-label">末帧</span>
                      <span className="live-debug-value">{debugStats.lastSize} B</span>
                    </div>
                    <div className="live-debug-item">
                      <span className="live-debug-label">队列</span>
                      <span className="live-debug-value">{debugStats.queueDepth} smp</span>
                    </div>
                    <div className="live-debug-item">
                      <span className="live-debug-label">丢帧</span>
                      <span className={`live-debug-value${debugStats.dropped > 0 ? ' live-debug-warn' : ''}`}>
                        {debugStats.dropped}
                      </span>
                    </div>
                    <div className="live-debug-item">
                      <span className="live-debug-label">输入RMS</span>
                      <span className={`live-debug-value${debugStats.inputRms < 0.001 ? ' live-debug-warn' : ''}`}>
                        {debugStats.inputRms.toFixed(5)}
                      </span>
                    </div>
                    <div className="live-debug-item">
                      <span className="live-debug-label">奇数字节帧</span>
                      <span className={`live-debug-value${debugStats.oddFrames > 0 ? ' live-debug-warn' : ''}`}>
                        {debugStats.oddFrames}
                      </span>
                    </div>
                    <div className="live-debug-item">
                      <span className="live-debug-label">非二进制帧</span>
                      <span className={`live-debug-value${debugStats.nonBinaryFrames > 0 ? ' live-debug-warn' : ''}`}>
                        {debugStats.nonBinaryFrames}
                      </span>
                    </div>
                  </div>
                  <div className="live-debug-frames">
                    <div className="live-debug-frames-title">最近10帧</div>
                    {recentFrames.length === 0 ? (
                      <div className="live-debug-frames-empty">暂无数据</div>
                    ) : (
                      recentFrames.map((f, idx) => (
                        <div key={`${f.ts}-${idx}`} className="live-debug-frame-row">
                          <span>{new Date(f.ts).toLocaleTimeString('zh-CN', { hour12: false })}</span>
                          <span>{f.bytes}B</span>
                          <span>{f.isArrayBuffer ? 'ArrayBuffer' : 'Text/JSON'}</span>
                          <span>RMS {Number(f.rms || 0).toFixed(5)}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}

              {!ambientMode && (
                <div className="live-subtitles card-bar">
                  <h4 className="live-subtitles-title">
                    实时字幕
                    {firstCaptionLatency !== null && (
                      <span className="live-caption-latency">首字延迟 {firstCaptionLatency} ms</span>
                    )}
                  </h4>
                  <div className="live-subtitles-scroll">
                    {subtitles.length === 0 && !partialText && (
                      <div className="live-subtitles-empty">等待语音识别结果...</div>
                    )}
                    {subtitles.map(s => (
                      <div key={s.id} className="live-subtitle-line final">
                        <span className="live-subtitle-meta">
                          {fmtTime(s.ts_ms)}{' · '}{s.speaker || '—'}
                        </span>
                        <span>{s.text}</span>
                      </div>
                    ))}
                    {partialText && (
                      <div className="live-subtitle-line partial">{partialText}</div>
                    )}
                    <div ref={subtitlesEndRef} />
                  </div>
                </div>
              )}

              {/* 有害告警 */}
              {alerts.length > 0 && (
                <div className="live-alerts card-bar">
                  <h4 className="live-alerts-title">有害语句告警</h4>
                  {alerts.slice(-5).map((a, i) => (
                    <div key={i} className="live-alert-item">
                      <span className="live-alert-severity">{'★'.repeat(Math.min(a.severity, 5))}</span>
                      <span className="live-alert-text">{a.text}</span>
                      {a.keywords.length > 0 && (
                        <span className="live-alert-kw">{a.keywords.join(', ')}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {/* 停止按钮 */}
              <button type="button" className="btn-secondary live-stop-btn" onClick={stopListening}>
                停止监听
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default LiveListen;

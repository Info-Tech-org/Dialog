const DEVICE_ID = 'web-extension';
let wsIngest = null;
let wsSubscribe = null;
let audioContext = null;
let mediaStream = null;
let processor = null;
let source = null;
let isRunning = false;

function setStatus(text, isError = false) {
  const el = document.getElementById('status');
  el.textContent = text;
  el.className = isError ? 'error' : '';
}

function appendCaption(text, isFinal) {
  const wrap = document.getElementById('captions');
  const span = document.createElement('div');
  span.className = isFinal ? 'final' : 'partial';
  span.textContent = text || '(识别中…)';
  wrap.appendChild(span);
  wrap.scrollTop = wrap.scrollHeight;
  if (isFinal) {
    const partials = wrap.querySelectorAll('.partial');
    partials.forEach(p => p.remove());
  }
}

function showHarmful(msg) {
  const el = document.getElementById('harmful');
  el.textContent = msg;
  el.classList.add('visible');
}

function hideHarmful() {
  document.getElementById('harmful').classList.remove('visible');
}

function floatToS16(float32Array) {
  const s16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    s16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return s16.buffer;
}

async function start() {
  const { baseUrl, deviceToken } = await new Promise(r => chrome.storage.local.get(['baseUrl', 'deviceToken'], r));
  if (!baseUrl) {
    setStatus('请先在扩展选项中设置后端地址', true);
    return;
  }
  const wsBase = baseUrl.replace(/^http/, 'ws');
  setStatus('正在连接…');

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaStream = stream;
    audioContext = new AudioContext({ sampleRate: 16000 });
    const src = audioContext.createMediaStreamSource(stream);
    const bufferSize = 2048;
    processor = audioContext.createScriptProcessor(bufferSize, 1, 1);
    source = src;

    const ingestUrl = `${wsBase}/ws/ingest/pcm?device_id=${encodeURIComponent(DEVICE_ID)}&raw=1${deviceToken ? '&device_token=' + encodeURIComponent(deviceToken) : ''}`;
    wsIngest = new WebSocket(ingestUrl);
    wsIngest.binaryType = 'arraybuffer';
    wsIngest.onopen = () => setStatus('已连接，正在采集麦克风…');
    wsIngest.onerror = () => setStatus('Ingest 连接失败', true);
    wsIngest.onclose = () => { if (isRunning) setStatus('Ingest 已断开', true); };

    const subscribeUrl = `${wsBase}/ws/realtime/subscribe?device_id=${encodeURIComponent(DEVICE_ID)}`;
    wsSubscribe = new WebSocket(subscribeUrl);
    wsSubscribe.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'status') setStatus(msg.message || '实时字幕已连接');
        else if (msg.type === 'asr') appendCaption(msg.text, msg.is_final);
        else if (msg.type === 'harmful_alert') showHarmful(`⚠ ${msg.text} (严重度 ${msg.severity})`);
      } catch (_) {}
    };
    wsSubscribe.onerror = () => setStatus('Subscribe 连接失败', true);
    wsSubscribe.onclose = () => { if (isRunning) setStatus('Subscribe 已断开', true); };

    processor.onaudioprocess = (e) => {
      if (!wsIngest || wsIngest.readyState !== WebSocket.OPEN) return;
      const input = e.inputBuffer.getChannelData(0);
      const s16 = floatToS16(input);
      wsIngest.send(s16);
    };
    src.connect(processor);
    processor.connect(audioContext.destination);
    isRunning = true;
    document.getElementById('btnToggle').textContent = '停止监听';
  } catch (err) {
    setStatus('错误: ' + (err.message || '无法访问麦克风'), true);
  }
}

function stop() {
  isRunning = false;
  if (processor && source) {
    try { source.disconnect(); processor.disconnect(); } catch (_) {}
  }
  if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
  mediaStream = null;
  processor = null;
  source = null;
  if (wsIngest) { wsIngest.close(); wsIngest = null; }
  if (wsSubscribe) { wsSubscribe.close(); wsSubscribe = null; }
  if (audioContext) audioContext.close();
  audioContext = null;
  document.getElementById('btnToggle').textContent = '开始监听';
  setStatus('已停止');
  hideHarmful();
}

document.getElementById('btnToggle').addEventListener('click', () => {
  if (isRunning) stop();
  else start();
});

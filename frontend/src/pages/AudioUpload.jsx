import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

function AudioUpload() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [error, setError] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef(null);
  const navigate = useNavigate();

  const handleFile = (file) => {
    if (!file || !file.type.startsWith('audio/')) {
      setError('请选择音频文件 (WAV, MP3 等)');
      return;
    }
    setSelectedFile(file);
    setError(null);
  };

  const handleFileSelect = (event) => {
    const file = event.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) handleFile(file);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => setDragOver(false);

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('请先选择文件');
      return;
    }

    setUploading(true);
    setProgress(0);
    setStatus('上传中...');
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('device_id', 'web_upload');

      const token = localStorage.getItem('access_token');
      if (!token) {
        setError('请先登录');
        setUploading(false);
        return;
      }

      const uploadResponse = await fetch('/api/audio/upload', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!uploadResponse.ok) throw new Error('上传失败');

      const uploadData = await uploadResponse.json();
      const uploadedSessionId = uploadData.session_id;
      setSessionId(uploadedSessionId);
      setStatus('处理中...');
      setProgress(20);

      const pollInterval = setInterval(async () => {
        try {
          const statusResponse = await fetch(`/api/audio/upload/status/${uploadedSessionId}`, {
            headers: { Authorization: `Bearer ${token}` },
          });

          if (statusResponse.ok) {
            const statusData = await statusResponse.json();
            setProgress(statusData.progress || 0);
            setStatus(statusData.message || '处理中...');

            if (statusData.status === 'completed') {
              clearInterval(pollInterval);
              setUploading(false);
              setStatus(`完成，检测到 ${statusData.harmful_count ?? 0} 条有害语句`);
            } else if (statusData.status === 'error') {
              clearInterval(pollInterval);
              setUploading(false);
              setError(statusData.message);
            }
          }
        } catch (err) {
          console.error('Error polling status:', err);
        }
      }, 1000);

      setTimeout(() => {
        clearInterval(pollInterval);
        setUploading((u) => {
          if (u) setError('处理超时');
          return false;
        });
      }, 5 * 60 * 1000);
    } catch (err) {
      setError(err.message || '上传失败');
      setUploading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setUploading(false);
    setProgress(0);
    setStatus('');
    setSessionId(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="upload-page">
      <div className="upload-zone-card card-bar">
        <h2 className="detail-section-title">上传音频</h2>
        <p className="upload-page-desc">上传音频文件进行语音识别与有害语检测</p>

        {!sessionId ? (
          <>
            <div
              className={`upload-dropzone ${dragOver ? 'upload-dropzone--active' : ''} ${selectedFile ? 'upload-dropzone--has-file' : ''}`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="audio/*"
                onChange={handleFileSelect}
                disabled={uploading}
                className="upload-dropzone-input"
                aria-label="选择音频文件"
              />
              {selectedFile ? (
                <div className="upload-dropzone-file">
                  <span className="upload-filename">{selectedFile.name}</span>
                  <span className="upload-filesize">{(selectedFile.size / 1024 / 1024).toFixed(2)} MB</span>
                </div>
              ) : (
                <p className="upload-dropzone-text">拖拽音频文件到此处，或点击选择文件</p>
              )}
            </div>

            {error && <p className="error-message">{error}</p>}

            {uploading && (
              <div className="upload-progress-wrap">
                <div className="upload-progress-bar">
                  <div className="upload-progress-fill" style={{ width: `${progress}%` }} />
                </div>
                <p className="upload-progress-status">{status}</p>
              </div>
            )}

            <div className="upload-actions">
              <button
                type="button"
                className="upload-primary-btn"
                onClick={handleUpload}
                disabled={!selectedFile || uploading}
              >
                {uploading ? '处理中...' : '开始上传'}
              </button>
              {selectedFile && !uploading && (
                <button type="button" className="btn-secondary" onClick={handleReset}>
                  重新选择
                </button>
              )}
              <button type="button" className="btn-secondary" onClick={() => navigate('/sessions')}>
                返回列表
              </button>
            </div>
          </>
        ) : (
          <div className="upload-success-card">
            <p className="upload-success-title">处理完成</p>
            <p className="upload-success-status">{status}</p>
            <p className="upload-success-id">会话 ID: {sessionId}</p>
            <button
              type="button"
              className="upload-primary-btn"
              onClick={() => navigate(`/sessions/${sessionId}`)}
            >
              查看会话
            </button>
          </div>
        )}
      </div>

      <div className="upload-tips card-bar">
        <h3 className="upload-tips-title">使用说明</h3>
        <ul className="upload-tips-list">
          <li>支持 WAV、MP3、M4A、AAC 等常见格式</li>
          <li>建议文件小于 100MB，16kHz 采样率</li>
          <li>处理时间约 1–3 分钟</li>
        </ul>
      </div>
    </div>
  );
}

export default AudioUpload;

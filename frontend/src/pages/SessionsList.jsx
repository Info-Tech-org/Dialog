import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchSessions, fetchDevices, formatDateTime, formatTime } from '../api/fetch';

function SessionsList() {
  const [sessions, setSessions] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterDevice, setFilterDevice] = useState('');
  const [filterHarmful, setFilterHarmful] = useState(''); // '' | 'yes' | 'no'
  const navigate = useNavigate();

  useEffect(() => {
    loadDevices();
  }, []);

  useEffect(() => {
    loadSessions();
  }, [filterDevice, filterHarmful]);

  const loadDevices = async () => {
    try {
      const data = await fetchDevices().catch(() => []);
      setDevices(Array.isArray(data) ? data : []);
    } catch (_) {}
  };

  const loadSessions = async () => {
    try {
      setLoading(true);
      const params = {};
      if (filterDevice) params.device_id = filterDevice;
      if (filterHarmful === 'yes') params.has_harmful = 'true';
      if (filterHarmful === 'no') params.has_harmful = 'false';
      const data = await fetchSessions(params);
      setSessions(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSessionClick = (sessionId) => {
    navigate(`/sessions/${sessionId}`);
  };

  if (loading && sessions.length === 0) {
    return (
      <div className="page-content page-content--center">
        <span className="loading-text">加载中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-content page-content--center">
        <p className="error-message">错误: {error}</p>
      </div>
    );
  }

  return (
    <div className="sessions-page">
      <div className="sessions-filters card-bar">
        <div className="sessions-filters-inner">
          <label className="filter-label">
            <span>设备</span>
            <select
              value={filterDevice}
              onChange={(e) => setFilterDevice(e.target.value)}
              className="filter-select"
              aria-label="按设备筛选"
            >
              <option value="">全部</option>
              {devices.map((d) => (
                <option key={d.device_id} value={d.device_id}>
                  {d.name || d.device_id}
                </option>
              ))}
            </select>
          </label>
          <label className="filter-label">
            <span>风险</span>
            <select
              value={filterHarmful}
              onChange={(e) => setFilterHarmful(e.target.value)}
              className="filter-select"
              aria-label="按是否含风险筛选"
            >
              <option value="">全部</option>
              <option value="yes">仅含风险</option>
              <option value="no">仅无风险</option>
            </select>
          </label>
        </div>
        <div className="sessions-actions">
          <button type="button" className="btn-secondary" onClick={() => navigate('/upload')}>
            上传
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate('/live')}>
            实时监听
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate('/devices')}>
            设备管理
          </button>
          <button type="button" className="btn-secondary" onClick={() => navigate('/review')}>
            复盘流
          </button>
        </div>
      </div>

      {sessions.length === 0 ? (
        <div className="empty-state">
          <p>暂无会话记录</p>
        </div>
      ) : (
        <div className="sessions-grid">
          {sessions.map((session) => (
            <button
              type="button"
              key={session.session_id}
              className="session-card"
              onClick={() => handleSessionClick(session.session_id)}
            >
              <div className="session-card-header">
                <span className="session-card-id">{session.session_id.slice(0, 8)}…</span>
                {session.harmful_count > 0 && (
                  <span className="harmful-badge">{session.harmful_count} 条有害</span>
                )}
              </div>
              <div className="session-card-meta">
                <span>设备: {session.device_id}</span>
                <span>{formatDateTime(session.start_time)}</span>
                {session.duration_seconds != null && (
                  <span>时长: {formatTime(session.duration_seconds)}</span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default SessionsList;

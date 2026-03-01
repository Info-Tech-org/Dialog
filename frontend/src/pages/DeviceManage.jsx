import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatDateTime } from '../api/fetch';

const API = '/api/devices';

function getAuthHeaders() {
  const token = localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
}

function DeviceManage() {
  const [devices, setDevices] = useState([]);
  const [unclaimed, setUnclaimed] = useState([]);
  const [recordingDeviceIds, setRecordingDeviceIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newDeviceId, setNewDeviceId] = useState('');
  const [newDeviceName, setNewDeviceName] = useState('');
  const [adding, setAdding] = useState(false);
  const [claiming, setClaiming] = useState(null); // device_id being claimed
  const [claimToken, setClaimToken] = useState(''); // shared token for claiming
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');
  const navigate = useNavigate();

  const loadDevices = async () => {
    try {
      const res = await fetch(API, { headers: getAuthHeaders() });
      if (!res.ok) throw new Error('获取设备列表失败');
      const data = await res.json();
      setDevices(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const loadUnclaimed = async () => {
    try {
      const res = await fetch(`${API}/unclaimed`, { headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        // Only show devices not already in my list
        const myIds = new Set(devices.map(d => d.device_id));
        setUnclaimed(data.filter(d => !myIds.has(d.device_id)));
      }
    } catch (e) {}
  };

  const pollActive = async () => {
    try {
      const res = await fetch('/ws/ingest/active');
      if (res.ok) {
        const data = await res.json();
        const ids = new Set((data.active || []).map(s => s.device_id).filter(Boolean));
        setRecordingDeviceIds(ids);
      }
    } catch (e) {}
  };

  const pollAll = async () => {
    await Promise.all([loadDevices(), pollActive()]);
    // loadUnclaimed depends on devices state, call separately
    await loadUnclaimed();
  };

  useEffect(() => {
    pollAll();
    const timer = setInterval(pollAll, 5000);
    return () => clearInterval(timer);
  }, []);

  const handleClaim = async (deviceId) => {
    if (!claimToken.trim()) {
      setError('请先输入设备 Token（烧录时配置的 DEVICE_INGEST_TOKEN）');
      return;
    }
    setClaiming(deviceId);
    setError(null);
    try {
      const res = await fetch(API, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'X-Device-Token': claimToken.trim() },
        body: JSON.stringify({ device_id: deviceId, name: '' }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || '认领失败');
      }
      await pollAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setClaiming(null);
    }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newDeviceId.trim()) return;
    setAdding(true);
    setError(null);
    try {
      const res = await fetch(API, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({ device_id: newDeviceId.trim(), name: newDeviceName.trim() }),
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || '绑定失败');
      }
      setNewDeviceId('');
      setNewDeviceName('');
      await pollAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (deviceId) => {
    if (!window.confirm(`确定解绑设备 ${deviceId}？`)) return;
    try {
      const res = await fetch(`${API}/${deviceId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error('解绑失败');
      await pollAll();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleEdit = async (deviceId) => {
    try {
      const res = await fetch(`${API}/${deviceId}`, {
        method: 'PATCH',
        headers: getAuthHeaders(),
        body: JSON.stringify({ name: editName }),
      });
      if (!res.ok) throw new Error('更新失败');
      setEditingId(null);
      await loadDevices();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="devices-page">
      {error && <p className="error-message">{error}</p>}

      {/* 待认领设备 */}
      {unclaimed.length > 0 && (
        <div className="device-unclaimed-card card-bar">
          <h3 className="devices-section-title">
            <span className="device-unclaimed-badge">{unclaimed.length}</span>
            发现新设备
          </h3>
          <p className="device-unclaimed-hint">
            输入设备 Token 后点击「认领」绑定到你的账号。
          </p>
          <div className="device-claim-token-row">
            <input
              type="password"
              className="device-claim-token-input"
              placeholder="设备 Token（DEVICE_INGEST_TOKEN）"
              value={claimToken}
              onChange={(e) => setClaimToken(e.target.value)}
              aria-label="设备 Token"
            />
          </div>
          <div className="device-cards">
            {unclaimed.map((d) => (
              <div key={d.device_id} className="device-card device-card--unclaimed">
                <span className="device-card-dot device-card-dot--online" />
                <div className="device-card-body">
                  <span className="device-card-name">{d.device_id}</span>
                  <span className="device-card-meta">在线 · {d.last_seen ? formatDateTime(d.last_seen) : '—'}</span>
                </div>
                <button
                  type="button"
                  className="device-claim-btn"
                  onClick={() => handleClaim(d.device_id)}
                  disabled={claiming === d.device_id}
                >
                  {claiming === d.device_id ? '认领中...' : '认领'}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 手动绑定 */}
      <div className="device-add-card card-bar">
        <h3 className="devices-section-title">手动绑定设备</h3>
        <form className="device-add-form" onSubmit={handleAdd}>
          <label className="device-form-label">
            <span>设备 ID</span>
            <input
              type="text"
              placeholder="与硬件配置一致"
              value={newDeviceId}
              onChange={(e) => setNewDeviceId(e.target.value)}
              required
            />
          </label>
          <label className="device-form-label">
            <span>设备名称（可选）</span>
            <input
              type="text"
              placeholder='如"客厅设备"'
              value={newDeviceName}
              onChange={(e) => setNewDeviceName(e.target.value)}
            />
          </label>
          <button type="submit" className="upload-primary-btn" disabled={adding || !newDeviceId.trim()}>
            {adding ? '绑定中...' : '绑定设备'}
          </button>
        </form>
      </div>

      {/* 已绑定设备 */}
      <div className="device-list-card card-bar">
        <h3 className="devices-section-title">已绑定设备</h3>
        {loading ? (
          <p className="loading-text">加载中...</p>
        ) : devices.length === 0 ? (
          <p className="empty-state">暂未绑定任何设备</p>
        ) : (
          <div className="device-cards">
            {devices.map((d) => (
              <div key={d.device_id} className="device-card">
                <span className={`device-card-dot device-card-dot--${recordingDeviceIds.has(d.device_id) ? 'recording' : d.is_online ? 'online' : 'offline'}`} />
                <div className="device-card-body">
                  {editingId === d.device_id ? (
                    <div className="device-edit-row">
                      <input
                        type="text"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        autoFocus
                        className="device-edit-input"
                      />
                      <button type="button" className="btn-secondary" onClick={() => handleEdit(d.device_id)}>保存</button>
                      <button type="button" className="btn-secondary" onClick={() => setEditingId(null)}>取消</button>
                    </div>
                  ) : (
                    <>
                      <span className="device-card-name">{d.name || d.device_id}</span>
                      <span className="device-card-id">{d.device_id}</span>
                      <span className="device-card-meta">
                        {recordingDeviceIds.has(d.device_id) ? '录音中' : d.is_online ? '在线' : '离线'}
                        {d.last_seen && ` · ${formatDateTime(d.last_seen)}`}
                      </span>
                    </>
                  )}
                </div>
                {editingId !== d.device_id && (
                  <div className="device-card-actions">
                    <button type="button" className="btn-secondary" onClick={() => { setEditingId(d.device_id); setEditName(d.name); }}>
                      编辑
                    </button>
                    <button type="button" className="device-delete-btn" onClick={() => handleDelete(d.device_id)}>
                      解绑
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default DeviceManage;

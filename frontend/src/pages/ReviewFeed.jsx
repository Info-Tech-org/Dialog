import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { formatDateTime, formatTime } from '../api/fetch';

function authHeaders() {
  const t = localStorage.getItem('access_token');
  return { Authorization: `Bearer ${t}` };
}

function ReviewFeed() {
  const [utterances, setUtterances] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [harmful, setHarmful] = useState(true);
  const [deviceId, setDeviceId] = useState('');
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const navigate = useNavigate();
  const LIMIT = 20;

  useEffect(() => { setOffset(0); }, [harmful, deviceId]);
  useEffect(() => { load(); }, [harmful, deviceId, offset]);

  const load = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: LIMIT, offset });
      if (harmful !== null) params.set('harmful', harmful);
      if (deviceId.trim()) params.set('device_id', deviceId.trim());
      const res = await fetch(`/api/utterances?${params}`, { headers: authHeaders() });
      if (!res.ok) throw new Error('加载失败');
      const data = await res.json();
      setUtterances(offset === 0 ? data : prev => [...prev, ...data]);
      setHasMore(data.length === LIMIT);
      setError(null);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  return (
    <div className="review-feed-page">
      <div className="feed-filters card-bar">
        <label className="feed-filter-item">
          <span>类型</span>
          <select
            value={String(harmful)}
            onChange={e => setHarmful(e.target.value === 'null' ? null : e.target.value === 'true')}
            className="filter-select"
            aria-label="按有害/正常筛选"
          >
            <option value="true">仅有害</option>
            <option value="false">仅正常</option>
            <option value="null">全部</option>
          </select>
        </label>
        <label className="feed-filter-item">
          <span>设备</span>
          <input
            value={deviceId}
            onChange={e => setDeviceId(e.target.value)}
            placeholder="全部设备"
            className="feed-filter-input"
            aria-label="按设备 ID 筛选"
          />
        </label>
      </div>

      {error && <p className="error-message">{error}</p>}

      {loading && utterances.length === 0 ? (
        <p className="loading-text">加载中...</p>
      ) : utterances.length === 0 ? (
        <p className="empty-state">暂无记录</p>
      ) : (
        <div className="feed-list">
          {utterances.map(utt => (
            <button
              type="button"
              key={utt.id}
              className={`feed-item ${utt.harmful_flag ? 'feed-item--harmful' : ''}`}
              onClick={() => navigate(`/sessions/${utt.session_id}?utt=${utt.id}`)}
            >
              <div className="feed-item-header">
                <span className="feed-speaker">{utt.speaker === 'A' ? '家长' : '孩子'}</span>
                <span className="feed-time">{formatTime(utt.start)}</span>
                {utt.harmful_flag && <span className="harmful-badge">有害</span>}
                <span className="feed-session">会话 {utt.session_id.slice(0, 8)}…</span>
              </div>
              <div className="feed-text">{utt.text}</div>
            </button>
          ))}
        </div>
      )}

      {hasMore && !loading && (
        <div className="feed-load-more">
          <button type="button" className="btn-secondary" onClick={() => setOffset(o => o + LIMIT)}>
            加载更多
          </button>
        </div>
      )}
    </div>
  );
}

export default ReviewFeed;

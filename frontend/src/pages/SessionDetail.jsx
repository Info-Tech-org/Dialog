import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { fetchSessionDetail, formatDateTime, formatTime } from '../api/fetch';

const API = '/api';
function authHeaders() {
  const t = localStorage.getItem('access_token');
  return { 'Content-Type': 'application/json', ...(t && { Authorization: `Bearer ${t}` }) };
}

function SummaryCard({ session, review, onGenerate, generating }) {
  const hasSummary = review?.generated;
  const s = review?.summary || {};
  const speakerSet = new Set((session.utterances || []).map(u => u.speaker));
  return (
    <div className="review-summary-card">
      <div className="review-summary-stats">
        <div className="stat-item">
          <span className="stat-val">{session.duration_seconds ? formatTime(session.duration_seconds) : '—'}</span>
          <span className="stat-label">时长</span>
        </div>
        <div className="stat-item">
          <span className="stat-val">{speakerSet.size}</span>
          <span className="stat-label">说话人</span>
        </div>
        <div className="stat-item">
          <span className={`stat-val ${session.harmful_count > 0 ? 'stat-val--risk' : 'stat-val--success'}`}>
            {session.harmful_count}
          </span>
          <span className="stat-label">风险片段</span>
        </div>
        {hasSummary && s.top_category && (
          <div className="stat-item">
            <span className="stat-val stat-val--small">{s.top_category}</span>
            <span className="stat-label">主要类别</span>
          </div>
        )}
        {hasSummary && s.max_severity > 0 && (
          <div className="stat-item">
            <span className={`stat-val ${s.max_severity >= 4 ? 'stat-val--risk' : 'stat-val--warning'}`}>
              {'★'.repeat(s.max_severity)}{'☆'.repeat(5 - s.max_severity)}
            </span>
            <span className="stat-label">最高严重度</span>
          </div>
        )}
      </div>
      {hasSummary && s.text && <div className="review-summary-text">💬 {s.text}</div>}
      {!hasSummary && (
        <button className="generate-btn" onClick={onGenerate} disabled={generating}>
          {generating ? '⏳ 生成中...' : '✨ 生成 AI 复盘摘要'}
        </button>
      )}
    </div>
  );
}

function HighlightsPanel({ highlights, utterances, analyses, onScrollTo }) {
  if (!highlights?.length) return null;
  const uttMap = Object.fromEntries((utterances || []).map(u => [u.id, u]));
  return (
    <div className="review-highlights">
      <h3 className="review-section-title">⚡ 关键片段</h3>
      {highlights.map((h, i) => {
        const utt = uttMap[h.utterance_id];
        const ana = analyses?.[h.utterance_id];
        if (!utt) return null;
        return (
          <div key={h.utterance_id} className="highlight-item" onClick={() => onScrollTo(h.utterance_id)}>
            <span className="highlight-rank">#{h.rank || i + 1}</span>
            <div className="highlight-body">
              <div className="highlight-text">"{utt.text}"</div>
              <div className="highlight-meta">
                {h.reason && <span className="highlight-reason">{h.reason}</span>}
                {ana?.suggestion && (
                  <span className="highlight-suggestion" title="点击复制"
                    onClick={e => { e.stopPropagation(); navigator.clipboard.writeText(ana.suggestion).catch(()=>{}); }}>
                    💡 {ana.suggestion}
                  </span>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RoleplayModal({ utt, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/utterances/${utt.id}/roleplay`, {
        method: 'POST', headers: authHeaders(),
      });
      if (!res.ok) throw new Error(`${res.status}: ${(await res.json().catch(() => ({}))).detail || '生成失败'}`);
      const result = await res.json();
      setData(result.content);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { generate(); }, [utt.id]);

  const copyAll = () => {
    if (!data) return;
    const lines = [];
    if (data.impact?.length) {
      lines.push('## 影响分析', ...data.impact.map(s => `- ${s}`), '');
    }
    if (data.rewrites?.length) {
      lines.push('## 替代表达', ...data.rewrites.map((s, i) => `${i + 1}. ${s}`), '');
    }
    if (data.rehearsal?.length) {
      lines.push('## 情景演练', ...data.rehearsal.map(t =>
        `${t.role === 'parent' ? '家长' : '孩子'}：${t.text}`
      ));
    }
    navigator.clipboard.writeText(lines.join('\n')).catch(() => {});
  };

  return (
    <div className="roleplay-overlay" onClick={onClose}>
      <div className="roleplay-modal" onClick={e => e.stopPropagation()}>
        <div className="roleplay-header">
          <h3>AI 演绎</h3>
          <button className="roleplay-close" onClick={onClose}>&times;</button>
        </div>
        <div className="roleplay-original">
          <span className="roleplay-label">原句：</span>"{utt.text}"
        </div>

        {loading && <div className="roleplay-loading">正在生成 AI 演绎...</div>}
        {error && (
          <div className="roleplay-error">
            <p>{error}</p>
            <button className="generate-btn-small" onClick={generate}>重试</button>
          </div>
        )}
        {!loading && !error && data && (
          <div className="roleplay-content">
            {data.impact?.length > 0 && (
              <div className="roleplay-section">
                <h4>影响分析</h4>
                <ul>{data.impact.map((s, i) => <li key={i}>{s}</li>)}</ul>
              </div>
            )}
            {data.rewrites?.length > 0 && (
              <div className="roleplay-section">
                <h4>替代表达</h4>
                <ol>{data.rewrites.map((s, i) => <li key={i}>{s}</li>)}</ol>
              </div>
            )}
            {data.rehearsal?.length > 0 && (
              <div className="roleplay-section">
                <h4>情景演练</h4>
                <div className="rehearsal-dialogue">
                  {data.rehearsal.map((t, i) => (
                    <div key={i} className={`rehearsal-turn ${t.role}`}>
                      <span className="rehearsal-role">{t.role === 'parent' ? '家长' : '孩子'}</span>
                      <span className="rehearsal-text">{t.text}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="roleplay-actions">
              <button className="copy-btn" onClick={copyAll}>复制全部</button>
              <button className="generate-btn-small" onClick={generate}>重新生成</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function UtteranceRow({ utt, analysis, feedback, highlighted, onFeedbackChange, onGenerateSuggestion }) {
  const [showNote, setShowNote] = useState(false);
  const [noteText, setNoteText] = useState(feedback?.note || '');
  const [showAnalysis, setShowAnalysis] = useState(false);
  const [genLoading, setGenLoading] = useState(false);
  const [showRoleplay, setShowRoleplay] = useState(false);

  useEffect(() => { setNoteText(feedback?.note || ''); }, [feedback?.note]);

  const toggleFeedback = (field) => onFeedbackChange(utt.id, { [field]: !feedback?.[field] });
  const saveNote = async () => { await onFeedbackChange(utt.id, { note: noteText }); setShowNote(false); };
  const handleGenSuggestion = async () => { setGenLoading(true); await onGenerateSuggestion(utt.id); setGenLoading(false); };
  const sevClass = (s) => s >= 4 ? 'analysis-sev--high' : s >= 2 ? 'analysis-sev--mid' : 'analysis-sev--low';

  return (
    <div id={`utt-${utt.id}`}
      className={`utterance-row speaker-${utt.speaker}${utt.harmful_flag ? ' harmful' : ''}${highlighted ? ' utt-highlighted' : ''}`}
    >
      <div className="utt-header">
        <span className="utt-speaker">{utt.speaker === 'A' ? '👨‍👩‍👧 家长' : '👦 孩子'}</span>
        <span className="utt-time">[{formatTime(utt.start)}]</span>
        {utt.harmful_flag && <span className="utt-harmful-badge">⚠ 有害</span>}
        {feedback?.is_false_positive && <span className="utt-fp-badge">✓ 误报</span>}
        {feedback?.is_starred && <span className="utt-star-badge">★</span>}
      </div>
      <div className="utt-text">{utt.text}</div>

      {utt.harmful_flag && analysis && (
        <div className="utt-analysis">
          {!showAnalysis ? (
            <button className="utt-link-btn" onClick={() => setShowAnalysis(true)}>查看解释 ▸</button>
          ) : (
            <div className="analysis-panel">
              <button className="utt-link-btn" onClick={() => setShowAnalysis(false)}>收起 ▴</button>
              <div className="analysis-row">
                <span className={sevClass(analysis.severity)}>
                  {'★'.repeat(Math.max(0,analysis.severity))}{'☆'.repeat(Math.max(0,5-analysis.severity))}
                </span>
                <span className="analysis-category">{analysis.category}</span>
              </div>
              {analysis.explanation && <div className="analysis-explanation">{analysis.explanation}</div>}
              {analysis.suggestion ? (
                <div className="analysis-suggestion">
                  💡 <strong>替代：</strong>{analysis.suggestion}
                  <button className="copy-btn" onClick={() => navigator.clipboard.writeText(analysis.suggestion).catch(()=>{})}>复制</button>
                </div>
              ) : (
                <button className="generate-btn-small" onClick={handleGenSuggestion} disabled={genLoading}>
                  {genLoading ? '生成中...' : '生成替代说法'}
                </button>
              )}
            </div>
          )}
        </div>
      )}

      <div className="utt-feedback-bar">
        <button className={`fb-btn${feedback?.is_false_positive ? ' active' : ''}`} onClick={() => toggleFeedback('is_false_positive')}>
          {feedback?.is_false_positive ? '✓误报' : '误报?'}
        </button>
        <button className={`fb-btn${feedback?.is_flagged ? ' active flagged' : ''}`} onClick={() => toggleFeedback('is_flagged')}>
          {feedback?.is_flagged ? '🚩已标记' : '🚩标记'}
        </button>
        <button className={`fb-btn${feedback?.is_starred ? ' active starred' : ''}`} onClick={() => toggleFeedback('is_starred')}>
          {feedback?.is_starred ? '★收藏' : '☆收藏'}
        </button>
        <button className={`fb-btn${showNote ? ' active' : ''}`} onClick={() => setShowNote(!showNote)}>
          📝{feedback?.note ? '有笔记' : '笔记'}
        </button>
        <button className="fb-btn roleplay-btn" onClick={() => setShowRoleplay(true)}>
          AI 演绎
        </button>
      </div>

      {showRoleplay && <RoleplayModal utt={utt} onClose={() => setShowRoleplay(false)} />}

      {showNote && (
        <div className="note-editor">
          <textarea value={noteText} onChange={e => setNoteText(e.target.value)} placeholder="添加笔记..." rows={2} />
          <div className="note-actions">
            <button className="upload-button" style={{ padding:'4px 12px',fontSize:13 }} onClick={saveNote}>保存</button>
            <button className="back-button" style={{ padding:'4px 12px',fontSize:13 }} onClick={() => setShowNote(false)}>取消</button>
          </div>
          {feedback?.note && <div className="note-existing">当前笔记：{feedback.note}</div>}
        </div>
      )}
    </div>
  );
}

function SessionDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [session, setSession] = useState(null);
  const [review, setReview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [highlightedUtt, setHighlightedUtt] = useState(null);
  const hlTimer = useRef(null);
  const jumpToUtt = new URLSearchParams(location.search).get('utt');

  useEffect(() => { loadAll(); }, [id]);
  useEffect(() => { if (jumpToUtt && session) setTimeout(() => scrollToUtt(jumpToUtt), 400); }, [jumpToUtt, session]);

  const fetchReview = async (sid) => {
    const res = await fetch(`${API}/sessions/${sid}/review`, { headers: authHeaders() });
    if (!res.ok) return { generated: false, summary: {}, highlights: [], analyses: {}, feedbacks: {} };
    return res.json();
  };

  const loadAll = async () => {
    try {
      setLoading(true);
      const [sessionData, reviewData] = await Promise.all([fetchSessionDetail(id), fetchReview(id)]);
      setSession(sessionData);
      setReview(reviewData);
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`${API}/sessions/${id}/generate`, { method: 'POST', headers: authHeaders() });
      if (!res.ok) throw new Error('生成失败');
      setReview(await fetchReview(id));
    } catch (e) { alert(e.message); }
    finally { setGenerating(false); }
  };

  const scrollToUtt = (uttId) => {
    const el = document.getElementById(`utt-${uttId}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setHighlightedUtt(uttId);
      if (hlTimer.current) clearTimeout(hlTimer.current);
      hlTimer.current = setTimeout(() => setHighlightedUtt(null), 3000);
    }
  };

  const handleFeedbackChange = async (uttId, patch) => {
    await fetch(`${API}/utterances/${uttId}/feedback`, { method: 'POST', headers: authHeaders(), body: JSON.stringify(patch) });
    setReview(await fetchReview(id));
  };

  const handleGenerateSuggestion = async (uttId) => {
    const res = await fetch(`${API}/utterances/${uttId}/suggestion`, { method: 'POST', headers: authHeaders() });
    if (!res.ok) { alert('生成失败'); return; }
    setReview(await fetchReview(id));
  };

  if (loading) return <div className="page-content page-content--center"><span className="loading-text">加载中...</span></div>;
  if (error) return <div className="detail-page"><button className="btn-secondary" onClick={() => navigate('/sessions')}>← 返回</button><p className="error-message">错误: {error}</p></div>;
  if (!session) return <div className="page-content page-content--center"><p className="empty-state">会话未找到</p></div>;

  const analyses = review?.analyses || {};
  const feedbacks = review?.feedbacks || {};

  return (
    <div className="detail-page">
      <div className="detail-toolbar">
        <button type="button" className="btn-secondary" onClick={() => navigate('/sessions')}>← 返回列表</button>
      </div>
      <div className="detail-overview-card card-bar">
        <h2 className="detail-section-title">本会话概览</h2>
        <div className="detail-meta-row">
          <span>{session.device_id}</span>
          <span>{formatDateTime(session.start_time)}</span>
        </div>
        <SummaryCard session={session} review={review} onGenerate={handleGenerate} generating={generating} />

        {session.audio_url && (
          <div className="audio-player-wrap">
            <audio controls src={session.audio_url} className="detail-audio" />
          </div>
        )}
      </div>

      {review?.highlights?.length > 0 && (
        <div className="detail-highlights-wrap card-bar">
          <HighlightsPanel highlights={review.highlights} utterances={session.utterances || []} analyses={analyses} onScrollTo={scrollToUtt} />
        </div>
      )}

      <div className="detail-utterances card-bar">
        <div className="utterances-title-row">
          <h2 className="detail-section-title">对话内容</h2>
          <span className="utterances-count">
            共 {session.utterances?.length || 0} 条{session.harmful_count > 0 && `，${session.harmful_count} 条风险`}
          </span>
        </div>
        {!session.utterances?.length ? (
          <p className="empty-state">暂无对话记录</p>
        ) : (
          <div className="utterances-list">
            {(session.utterances || []).map(utt => (
              <UtteranceRow key={utt.id} utt={utt} analysis={analyses[utt.id]} feedback={feedbacks[utt.id]}
                highlighted={highlightedUtt === utt.id} onFeedbackChange={handleFeedbackChange}
                onGenerateSuggestion={handleGenerateSuggestion} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default SessionDetail;

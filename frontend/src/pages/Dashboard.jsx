import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchSessions, fetchDevices } from '../api/fetch';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';

const QUICK_LINKS = [
  { to: '/upload', label: '上传音频', key: 'upload' },
  { to: '/live', label: '实时监听', key: 'live' },
  { to: '/devices', label: '设备管理', key: 'devices' },
  { to: '/review', label: '复盘流', key: 'review' },
];

const COLORS = ['#2563eb', '#dc2626', '#16a34a', '#6b7280'];

function Dashboard() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState([]);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [sessionsRes, devicesRes] = await Promise.all([
          fetchSessions({ limit: '500' }),
          fetchDevices().catch(() => []),
        ]);
        if (!cancelled) {
          setSessions(Array.isArray(sessionsRes) ? sessionsRes : []);
          setDevices(Array.isArray(devicesRes) ? devicesRes : []);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="dashboard dashboard--loading">
        <span>加载中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard dashboard--error">
        <p>加载失败: {error}</p>
      </div>
    );
  }

  const totalSessions = sessions.length;
  const sessionsWithHarmful = sessions.filter((s) => (s.harmful_count || 0) > 0).length;
  const totalHarmful = sessions.reduce((acc, s) => acc + (s.harmful_count || 0), 0);
  const deviceCount = devices.length;

  const last7Days = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    d.setHours(0, 0, 0, 0);
    last7Days.push(d);
  }
  const dayKeys = last7Days.map((d) => d.toISOString().slice(0, 10));
  const sessionsByDay = dayKeys.map((day) => {
    const count = sessions.filter((s) => {
      const t = s.start_time;
      const sessionDay = typeof t === 'string' ? t.slice(0, 10) : (t && t.toISOString?.().slice(0, 10));
      return sessionDay === day;
    }).length;
    return { date: day.slice(5), 会话数: count };
  });

  const pieData = [
    { name: '含风险', value: sessionsWithHarmful, color: COLORS[1] },
    { name: '无风险', value: Math.max(0, totalSessions - sessionsWithHarmful), color: COLORS[2] },
  ].filter((d) => d.value > 0);
  if (totalSessions === 0) pieData.push({ name: '暂无数据', value: 1, color: COLORS[3] });

  return (
    <div className="dashboard">
      <section className="dashboard-kpis">
        <div className="kpi-card">
          <div className="kpi-value">{totalSessions}</div>
          <div className="kpi-label">会话总数</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{sessionsWithHarmful}</div>
          <div className="kpi-label">含风险会话</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value kpi-value--risk">{totalHarmful}</div>
          <div className="kpi-label">风险片段总数</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{deviceCount}</div>
          <div className="kpi-label">已绑定设备</div>
        </div>
      </section>

      <section className="dashboard-charts">
        <div className="chart-card">
          <h3 className="chart-title">近 7 日会话数量</h3>
          <div className="chart-inner">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={sessionsByDay} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="会话数" fill="var(--accent)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="chart-card">
          <h3 className="chart-title">风险会话占比</h3>
          <div className="chart-inner chart-inner--pie">
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={90}
                  paddingAngle={2}
                  dataKey="value"
                  nameKey="name"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v) => [v, '']} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="dashboard-actions">
        <h3 className="dashboard-section-title">快捷操作</h3>
        <div className="quick-actions">
          {QUICK_LINKS.map(({ to, label }) => (
            <button
              key={to}
              type="button"
              className="quick-action-btn"
              onClick={() => navigate(to)}
            >
              {label}
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}

export default Dashboard;

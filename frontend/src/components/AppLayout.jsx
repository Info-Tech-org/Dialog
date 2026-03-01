import React from 'react';
import { NavLink, useNavigate, useLocation, Outlet } from 'react-router-dom';

const OFFICIAL_SITE = 'https://infotech-launch.vercel.app/';

const navItems = [
  { to: '/dashboard', label: '仪表盘', icon: 'M4 6h16M4 12h16M4 18h16' },
  { to: '/sessions', label: '会话列表', icon: 'M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2' },
  { to: '/upload', label: '上传', icon: 'M4 16v1a2 2 0 002 2h12a2 2 0 002-2v-1M8 12l4 4 4-4M12 8v8' },
  { to: '/live', label: '实时监听', icon: 'M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0V8m0 4a4 4 0 01-4-4' },
  { to: '/devices', label: '设备管理', icon: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
  { to: '/review', label: '复盘流', icon: 'M4 6h16M4 10h16M4 14h16M4 18h16' },
];

function Icon({ path }) {
  return (
    <svg className="app-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}

const PAGE_TITLES = {
  '/dashboard': '仪表盘',
  '/sessions': '会话列表',
  '/upload': '上传音频',
  '/live': '实时监听',
  '/devices': '设备管理',
  '/review': '复盘流',
};

function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const pathname = location.pathname;
  let currentTitle = PAGE_TITLES[pathname];
  if (!currentTitle && pathname.startsWith('/sessions/') && pathname !== '/sessions') {
    currentTitle = '会话详情';
  }
  if (!currentTitle) currentTitle = PAGE_TITLES['/' + pathname.split('/')[1]] || '';

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    navigate('/login');
  };

  return (
    <div className="app-shell">
      <a href="#app-main" className="skip-nav">跳过导航，进入主内容</a>
      <aside className="app-sidebar">
        <a href={OFFICIAL_SITE} target="_blank" rel="noopener noreferrer" className="app-sidebar-logo" aria-label="官网">
          <img src="/logo.svg" alt="Info-Tech 语镜" />
        </a>
        <nav className="app-nav" aria-label="主导航">
          {navItems.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `app-nav-item ${isActive ? 'app-nav-item--active' : ''}`}
            >
              <Icon path={icon} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="app-sidebar-footer">
          <a href={OFFICIAL_SITE} target="_blank" rel="noopener noreferrer" className="app-nav-item">
            <span>官网</span>
          </a>
          <button type="button" className="app-nav-item app-nav-item--logout" onClick={handleLogout}>
            <span>退出</span>
          </button>
        </div>
      </aside>
      <div className="app-main-wrap">
        <header className="app-topbar">
          <h1 className="app-topbar-title">{currentTitle}</h1>
          <div className="app-topbar-experiment" aria-hidden="true">
            <div className="app-experiment-orb" />
          </div>
        </header>
        <main id="app-main" className="app-main" role="main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default AppLayout;

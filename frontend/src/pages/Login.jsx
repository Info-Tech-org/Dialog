import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';

function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        throw new Error('登录失败，请检查用户名和密码');
      }

      const data = await response.json();

      // Save token to localStorage
      localStorage.setItem('access_token', data.access_token);

      // Redirect to sessions list
      navigate('/dashboard');
    } catch (err) {
      setError(err.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  const handleQuickLogin = () => {
    setUsername('test');
    setPassword('test123456');
  };

  const officialSite = 'https://infotech-launch.vercel.app/';

  return (
    <div className="login-container">
      <div className="login-box">
        <a href={officialSite} target="_blank" rel="noopener noreferrer" className="login-logo-link" aria-label="官网">
          <img src="/logo.svg" alt="Info-Tech 语镜" className="login-logo" />
        </a>
        <h1>家庭情绪交互系统</h1>
        <p className="login-subtitle">Family Emotion Interaction System</p>
        <p className="login-official">
          <a href={officialSite} target="_blank" rel="noopener noreferrer">官网</a>
        </p>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username">用户名</label>
            <input
              type="text"
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="请输入用户名"
              required
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">密码</label>
            <input
              type="password"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="请输入密码"
              required
            />
          </div>

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="login-button"
            disabled={loading}
          >
            {loading ? '登录中...' : '登录'}
          </button>

          <div className="quick-login">
            <button
              type="button"
              onClick={handleQuickLogin}
              className="quick-login-button"
            >
              使用测试账号登录
            </button>
          </div>

          <div className="login-tips">
            <p>💡 测试账号</p>
            <p>用户名: <code>test</code></p>
            <p>密码: <code>test123456</code></p>
          </div>

          <div className="login-footer">
            <p>
              还没有账号？<Link to="/register" className="register-link">立即注册</Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}

export default Login;

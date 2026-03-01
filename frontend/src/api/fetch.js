const API_BASE_URL = '/api';

/**
 * Get authorization headers with token
 * @returns {Object} Headers object with authorization
 */
function getAuthHeaders() {
  const token = localStorage.getItem('access_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` })
  };
}

/**
 * Fetch all sessions
 * @returns {Promise<Array>} List of sessions
 */
function handleUnauthorized(response) {
  if (response.status === 401 || response.status === 403) {
    localStorage.removeItem('access_token');
    window.location.href = '/login';
    throw new Error('登录已过期，请重新登录');
  }
}

export async function fetchSessions(params = {}) {
  const q = new URLSearchParams(params).toString();
  const url = `${API_BASE_URL}/sessions` + (q ? `?${q}` : '');
  const response = await fetch(url, { headers: getAuthHeaders() });
  if (!response.ok) {
    handleUnauthorized(response);
    throw new Error('Failed to fetch sessions');
  }
  return response.json();
}

/**
 * Fetch devices list
 * @returns {Promise<Array>} List of devices
 */
export async function fetchDevices() {
  const response = await fetch(`${API_BASE_URL}/devices`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) {
    handleUnauthorized(response);
    throw new Error('Failed to fetch devices');
  }
  return response.json();
}

/**
 * Fetch session detail by ID
 * @param {string} sessionId - Session ID
 * @returns {Promise<Object>} Session detail with utterances
 */
export async function fetchSessionDetail(sessionId) {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
    headers: getAuthHeaders()
  });
  if (!response.ok) {
    handleUnauthorized(response);
    throw new Error('Failed to fetch session detail');
  }
  return response.json();
}

/**
 * Format timestamp to HH:MM:SS
 * @param {number} seconds - Seconds
 * @returns {string} Formatted time
 */
export function formatTime(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return '—';
  const n = Math.max(0, Math.floor(Number(seconds)));
  const mins = Math.floor(n / 60);
  const secs = n % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Format datetime to readable string
 * @param {string} datetime - ISO datetime string
 * @returns {string} Formatted datetime
 */
export function formatDateTime(datetime) {
  if (datetime == null) return '—';
  const date = new Date(datetime);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

import * as SecureStore from 'expo-secure-store';
import { LoginResponse, SessionDetailResponse, SessionResponse, UploadResponse, UploadStatus } from '../types';

const API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://47.236.106.225:9000';
const TOKEN_KEY = 'auth_token';

export const tokenStorage = {
  get: () => SecureStore.getItemAsync(TOKEN_KEY),
  set: (value: string) => SecureStore.setItemAsync(TOKEN_KEY, value),
  remove: () => SecureStore.deleteItemAsync(TOKEN_KEY),
};

async function withAuthHeaders(init: RequestInit = {}): Promise<RequestInit> {
  const token = await tokenStorage.get();
  const headers = new Headers(init.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return { ...init, headers };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const opts = await withAuthHeaders(init);
  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<string> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  const data: LoginResponse = await res.json();
  return data.access_token;
}

export function fetchSessions(): Promise<SessionResponse[]> {
  return request<SessionResponse[]>('/api/sessions');
}

export function fetchSessionDetail(id: string): Promise<SessionDetailResponse> {
  return request<SessionDetailResponse>(`/api/sessions/${id}`);
}

export async function uploadAudio(file: { uri: string; name: string; type: string | null }, deviceId?: string): Promise<UploadResponse> {
  const form = new FormData();
  form.append('file', {
    uri: file.uri,
    name: file.name,
    type: file.type || 'audio/mpeg',
  } as any);
  if (deviceId) {
    form.append('device_id', deviceId);
  }
  const opts = await withAuthHeaders({
    method: 'POST',
    body: form,
  });
  const res = await fetch(`${API_BASE}/api/audio/upload`, opts);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export function fetchUploadStatus(sessionId: string): Promise<UploadStatus> {
  return request<UploadStatus>(`/api/audio/upload/status/${sessionId}`);
}

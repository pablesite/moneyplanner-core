import axios from 'axios';
import {
  clearAuthTokens,
  getAccessToken,
  getRefreshToken,
  setAccessToken,
  setRefreshToken,
} from '@/lib/authSession';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const api = axios.create({ baseURL });
// Compatibility alias used by SaaS-derived views that call Core endpoints explicitly.
export const coreApi = api;
const refreshClient = axios.create({ baseURL });

type PendingCallback = (token: string | null) => void;
let isRefreshing = false;
let pending: PendingCallback[] = [];

function logAuthDebug(event: string, context: Record<string, unknown>) {
  if (typeof console === 'undefined') return;
  console.warn(`[auth] ${event}`, context);
}

function redirectToLoginWithSessionExpiredReason() {
  if (typeof window !== 'undefined') {
    window.location.href = '/login?reason=session_expired';
  }
}

function notifyPending(token: string | null) {
  pending.forEach((cb) => cb(token));
  pending = [];
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) return null;

  try {
    const res = await refreshClient.post('/api/auth/refresh/', { refresh });
    const access = res.data?.access;
    const nextRefresh = res.data?.refresh;
    if (access) {
      setAccessToken(access);
      if (typeof nextRefresh === 'string' && nextRefresh.length > 0) {
        setRefreshToken(nextRefresh);
      }
      return access;
    }
    logAuthDebug('refresh_missing_access', {
      url: '/api/auth/refresh/',
    });
    return null;
  } catch (error) {
    const status = (error as { response?: { status?: number } } | undefined)?.response?.status;
    logAuthDebug('refresh_failed', {
      url: '/api/auth/refresh/',
      status: status ?? null,
    });
    return null;
  }
}

// Attach access token
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const status = error.response?.status;
    const original = error.config || {};
    const requestUrl = String(original.url ?? '');
    const isRefreshCall = requestUrl.includes('/api/auth/refresh/');
    const isTokenCall = requestUrl.includes('/api/auth/token/');

    if (status !== 401 || isRefreshCall || isTokenCall || original._retry) {
      return Promise.reject(error);
    }

    logAuthDebug('request_401', {
      source: 'core',
      url: requestUrl,
      method: String(original.method ?? 'get').toUpperCase(),
    });

    const refresh = getRefreshToken();
    if (!refresh) {
      logAuthDebug('logout_no_refresh_token', {
        source: 'core',
        url: requestUrl,
      });
      clearAuthTokens();
      redirectToLoginWithSessionExpiredReason();
      return Promise.reject(error);
    }

    original._retry = true;

    if (!isRefreshing) {
      isRefreshing = true;
      const newToken = await refreshAccessToken();
      isRefreshing = false;

      if (!newToken) {
        logAuthDebug('logout_refresh_failed', {
          source: 'core',
          url: requestUrl,
        });
        clearAuthTokens();
        notifyPending(null);
        redirectToLoginWithSessionExpiredReason();
        return Promise.reject(error);
      }

      notifyPending(newToken);
      original.headers = original.headers || {};
      original.headers.Authorization = `Bearer ${newToken}`;
      return api(original);
    }

    return new Promise((resolve, reject) => {
      pending.push((token) => {
        if (!token) {
          reject(error);
          return;
        }
        original.headers = original.headers || {};
        original.headers.Authorization = `Bearer ${token}`;
        resolve(api(original));
      });
    });
  },
);

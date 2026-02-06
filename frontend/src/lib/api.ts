import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const api = axios.create({ baseURL });
const refreshClient = axios.create({ baseURL });

type PendingCallback = (token: string | null) => void;
let isRefreshing = false;
let pending: PendingCallback[] = [];

function clearAuth() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

function notifyPending(token: string | null) {
  pending.forEach((cb) => cb(token));
  pending = [];
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = localStorage.getItem("refresh_token");
  if (!refresh) return null;

  try {
    const res = await refreshClient.post("/api/auth/refresh/", { refresh });
    const access = res.data?.access;
    if (access) {
      localStorage.setItem("access_token", access);
      return access;
    }
    return null;
  } catch {
    return null;
  }
}

// Attach access token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const status = error.response?.status;
    const original = error.config || {};
    const isRefreshCall = original.url?.includes("/api/auth/refresh/");

    if (status !== 401 || isRefreshCall || original._retry) {
      return Promise.reject(error);
    }

    const refresh = localStorage.getItem("refresh_token");
    if (!refresh) {
      clearAuth();
      window.location.href = "/login";
      return Promise.reject(error);
    }

    original._retry = true;

    if (!isRefreshing) {
      isRefreshing = true;
      const newToken = await refreshAccessToken();
      isRefreshing = false;

      if (!newToken) {
        clearAuth();
        notifyPending(null);
        window.location.href = "/login";
        return Promise.reject(error);
      }

      notifyPending(newToken);
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
  }
);

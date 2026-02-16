import type { Router } from 'vue-router';
import { authApi } from '@/domains/auth/api';
import { clearAuthTokens, getAccessToken } from '@/domains/auth/session';

let authChecked = false;
let authCheckPromise: Promise<boolean> | null = null;

async function ensureAuthValid(): Promise<boolean> {
  const token = getAccessToken();
  if (!token) return false;
  if (authChecked) return true;

  if (!authCheckPromise) {
    authCheckPromise = authApi
      .validateSession()
      .then(() => {
        authChecked = true;
        return true;
      })
      .catch(() => {
        clearAuthTokens();
        authChecked = false;
        return false;
      })
      .finally(() => {
        authCheckPromise = null;
      });
  }

  return authCheckPromise ?? false;
}

export function registerAuthGuard(router: Router) {
  router.beforeEach(async (to) => {
    const token = getAccessToken();

    if (!token && to.path !== '/login') {
      return { path: '/login' };
    }

    if (token) {
      const ok = await ensureAuthValid();
      if (!ok && to.path !== '/login') {
        return { path: '/login' };
      }
      if (ok && to.path === '/login') {
        return { path: '/' };
      }
    }

    return true;
  });
}

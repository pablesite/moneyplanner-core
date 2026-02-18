import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useLoginForm } from '@/domains/auth/composables';

const mocks = vi.hoisted(() => ({
  login: vi.fn(),
  setAccessToken: vi.fn(),
  setRefreshToken: vi.fn(),
  toApiErrorMessage: vi.fn(() => 'mapped-error'),
  push: vi.fn(),
  route: { query: {} as Record<string, unknown> },
}));

vi.mock('@/domains/auth/api', () => ({
  authApi: {
    login: mocks.login,
  },
}));

vi.mock('@/domains/auth/session', () => ({
  setAccessToken: mocks.setAccessToken,
  setRefreshToken: mocks.setRefreshToken,
}));

vi.mock('@/lib/errors', () => ({
  toApiErrorMessage: mocks.toApiErrorMessage,
}));

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mocks.push }),
  useRoute: () => mocks.route,
}));

describe('useLoginForm (core)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.route.query = {};
  });

  it('shows session notice and logs in successfully', async () => {
    mocks.route.query = { reason: 'session_expired' };
    mocks.login.mockResolvedValueOnce({ data: { access: 'a1', refresh: 'r1' } });
    const form = useLoginForm();
    form.username.value = 'u';
    form.password.value = 'p';

    expect(form.sessionNotice.value).toContain('sesion expiro');

    await form.login();

    expect(mocks.login).toHaveBeenCalledWith({ username: 'u', password: 'p' });
    expect(mocks.setAccessToken).toHaveBeenCalledWith('a1');
    expect(mocks.setRefreshToken).toHaveBeenCalledWith('r1');
    expect(mocks.push).toHaveBeenCalledWith('/');
    expect(form.loading.value).toBe(false);
    expect(form.error.value).toBeNull();
  });

  it('maps login errors', async () => {
    mocks.login.mockRejectedValueOnce(new Error('boom'));
    const form = useLoginForm();
    await form.login();
    expect(form.error.value).toBe('mapped-error');
    expect(form.loading.value).toBe(false);
  });
});

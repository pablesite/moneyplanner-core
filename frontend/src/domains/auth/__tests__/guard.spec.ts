import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  getAccessToken: vi.fn(),
  clearAuthTokens: vi.fn(),
  validateSession: vi.fn(),
}));

vi.mock('@/domains/auth/session', () => ({
  getAccessToken: mocks.getAccessToken,
  clearAuthTokens: mocks.clearAuthTokens,
}));

vi.mock('@/domains/auth/api', () => ({
  authApi: {
    validateSession: mocks.validateSession,
  },
}));

describe('auth guard', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it('keeps session when validateSession fails without auth status', async () => {
    mocks.getAccessToken.mockReturnValue('token');
    mocks.validateSession.mockRejectedValue(new Error('network down'));

    const { registerAuthGuard } = await import('@/domains/auth/guard');
    let guard: ((to: { path: string }) => Promise<unknown>) | undefined;
    registerAuthGuard({
      beforeEach(fn: unknown) {
        guard = fn as typeof guard;
      },
    } as unknown as Parameters<typeof registerAuthGuard>[0]);

    expect(guard).toBeTypeOf('function');
    const result = await guard!({ path: '/presupuesto' });

    expect(result).toBe(true);
    expect(mocks.clearAuthTokens).not.toHaveBeenCalled();
  });

  it('clears session when validateSession returns 401', async () => {
    mocks.getAccessToken.mockReturnValue('token');
    mocks.validateSession.mockRejectedValue({ response: { status: 401 }, isAxiosError: true });

    const { registerAuthGuard } = await import('@/domains/auth/guard');
    let guard: ((to: { path: string }) => Promise<unknown>) | undefined;
    registerAuthGuard({
      beforeEach(fn: unknown) {
        guard = fn as typeof guard;
      },
    } as unknown as Parameters<typeof registerAuthGuard>[0]);

    expect(guard).toBeTypeOf('function');
    const result = await guard!({ path: '/presupuesto' });

    expect(result).toEqual({ path: '/login' });
    expect(mocks.clearAuthTokens).toHaveBeenCalledTimes(1);
  });
});

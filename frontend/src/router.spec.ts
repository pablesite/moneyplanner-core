import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  registerAuthGuard: vi.fn(),
  createRouter: vi.fn(),
  createWebHistory: vi.fn(() => 'history'),
}));

vi.mock('vue-router', () => ({
  createRouter: mocks.createRouter,
  createWebHistory: mocks.createWebHistory,
}));

vi.mock('@/domains/auth', () => ({
  registerAuthGuard: mocks.registerAuthGuard,
}));

describe('router (core)', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mocks.createRouter.mockReturnValue({ __router: true });
  });

  it('registers auth guard and mounts core routes', async () => {
    const mod = await import('./router');

    expect(mod.router).toEqual({ __router: true });
    expect(mocks.createRouter).toHaveBeenCalledWith(
      expect.objectContaining({
        history: 'history',
        routes: expect.arrayContaining([
          expect.objectContaining({ path: '/login' }),
          expect.objectContaining({ path: '/presupuesto' }),
          expect.objectContaining({ path: '/' }),
          expect.objectContaining({ path: '/data' }),
        ]),
      }),
    );
    expect(mocks.registerAuthGuard).toHaveBeenCalledWith({ __router: true });
  }, 15000);
});

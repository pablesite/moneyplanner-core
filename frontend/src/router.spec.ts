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

vi.mock('./views/NetWorthView.vue', () => ({ default: { name: 'NetWorthView' } }));
vi.mock('./views/LoginView.vue', () => ({ default: { name: 'LoginView' } }));
vi.mock('./views/RegisterView.vue', () => ({ default: { name: 'RegisterView' } }));
vi.mock('./views/HomeView.vue', () => ({ default: { name: 'HomeView' } }));
vi.mock('./views/GuidePhaseDetailView.vue', () => ({ default: { name: 'GuidePhaseDetailView' } }));
vi.mock('./views/BudgetView.vue', () => ({ default: { name: 'BudgetView' } }));
vi.mock('./views/MonthlyCloseView.vue', () => ({ default: { name: 'MonthlyCloseView' } }));
vi.mock('./views/AuxDataView.vue', () => ({ default: { name: 'AuxDataView' } }));
vi.mock('./views/AccountView.vue', () => ({ default: { name: 'AccountView' } }));
vi.mock('./views/PeopleView.vue', () => ({ default: { name: 'PeopleView' } }));
vi.mock('./views/AccountingMovementsView.vue', () => ({
  default: { name: 'AccountingMovementsView' },
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
  }, 30000);
});

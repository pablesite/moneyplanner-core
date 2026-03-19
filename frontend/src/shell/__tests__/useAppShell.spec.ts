import { beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import { useAppShell } from '@/shell/useAppShell';

const mocks = vi.hoisted(() => ({
  clearAuthTokens: vi.fn(),
  hasAccessToken: { value: false },
  route: {
    name: 'home',
    path: '/',
    fullPath: '/',
  },
  router: {
    push: vi.fn(),
  },
}));

vi.mock('vue-router', () => ({
  useRoute: () => mocks.route,
  useRouter: () => mocks.router,
}));

vi.mock('@/domains/auth/session', () => ({
  clearAuthTokens: mocks.clearAuthTokens,
  hasAccessToken: mocks.hasAccessToken,
}));

describe('useAppShell', () => {
  beforeEach(() => {
    mocks.clearAuthTokens.mockReset();
    mocks.router.push.mockReset();
    mocks.hasAccessToken.value = false;
    mocks.route.name = 'home';
    mocks.route.path = '/';
    mocks.route.fullPath = '/';
    document.body.style.overflow = '';
  });

  it('tracks login route and navigation state', async () => {
    const { shell, unmount } = mountShell();

    expect(shell.isLoginRoute.value).toBe(false);
    expect(shell.navItems.value).toHaveLength(6);
    expect(shell.isNavItemActive(shell.navItems.value[0]!)).toBe(true);

    mocks.route.path = '/guia/fases/2';
    expect(shell.isNavItemActive(shell.navItems.value[0]!)).toBe(true);

    shell.toggleSidebar();
    await nextTick();
    expect(shell.sidebarOpen.value).toBe(true);
    expect(document.body.style.overflow).toBe('hidden');

    unmount();
  });

  it('computes account initials and clears session on logout', async () => {
    mocks.hasAccessToken.value = true;
    const { shell, unmount } = mountShell();

    await nextTick();
    expect(shell.hasToken.value).toBe(true);
    expect(shell.accountInitials.value).toBe('MC');

    shell.accountLabel.value = 'Pablo Perez';
    expect(shell.accountInitials.value).toBe('PP');

    shell.toggleAccountMenu();
    shell.toggleSidebar();
    shell.logout();

    expect(mocks.clearAuthTokens).toHaveBeenCalledTimes(1);
    expect(shell.accountMenuOpen.value).toBe(false);
    expect(shell.sidebarOpen.value).toBe(false);
    expect(mocks.router.push).toHaveBeenCalledWith('/login');

    unmount();
  });
});

function mountShell() {
  let shell: ReturnType<typeof useAppShell> | null = null;
  const Host = defineComponent({
    setup() {
      shell = useAppShell();
      return () => null;
    },
  });

  const wrapper = mount(Host);
  if (!shell) {
    throw new Error('Failed to mount useAppShell host');
  }
  const mountedShell = shell as ReturnType<typeof useAppShell>;

  return {
    shell: mountedShell,
    unmount: () => wrapper.unmount(),
  };
}

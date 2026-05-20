/** @vitest-environment jsdom */
import { ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import LoginView from '../LoginView.vue';

const mockUseLoginForm = vi.fn();

vi.mock('@/domains/auth', () => ({
  useLoginForm: () => mockUseLoginForm(),
}));

function makeState(overrides: Record<string, unknown> = {}) {
  return {
    username: ref(''),
    password: ref(''),
    error: ref<string | null>(null),
    sessionNotice: ref<string | null>(null),
    loading: ref(false),
    login: vi.fn(async () => {}),
    ...overrides,
  };
}

describe('LoginView', () => {
  beforeEach(() => {
    mockUseLoginForm.mockReset();
  });

  it('renders login form with expected labels', () => {
    mockUseLoginForm.mockReturnValue(makeState());
    const wrapper = mount(LoginView);

    expect(wrapper.text()).toContain('Acceso');
    expect(wrapper.text()).toContain('Usuario');
    expect(wrapper.text()).toContain('Contraseña');
    expect(wrapper.get('button[type="submit"]').text()).toContain('Entrar');
  });

  it('renders loading and error states', () => {
    mockUseLoginForm.mockReturnValue(
      makeState({
        loading: ref(true),
        error: ref('Credenciales inválidas'),
      }),
    );
    const wrapper = mount(LoginView);

    expect(wrapper.text()).toContain('Entrando...');
    expect(wrapper.text()).toContain('Credenciales inválidas');
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined();
  });

  it('renders session expired notice', () => {
    mockUseLoginForm.mockReturnValue(
      makeState({
        sessionNotice: ref('Tu sesión expiró. Inicia sesión nuevamente.'),
      }),
    );
    const wrapper = mount(LoginView);
    expect(wrapper.text()).toContain('Tu sesión expiró. Inicia sesión nuevamente.');
  });

  it('submits credentials through composable login action', async () => {
    const state = makeState({
      username: ref('demo'),
      password: ref('secret'),
      login: vi.fn(async () => {}),
    });
    mockUseLoginForm.mockReturnValue(state);
    const wrapper = mount(LoginView);

    await wrapper.get('form').trigger('submit.prevent');
    expect(state.login).toHaveBeenCalledTimes(1);
  });
});

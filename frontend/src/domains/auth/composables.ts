import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { authApi } from '@/domains/auth/api';
import { setAccessToken, setRefreshToken } from '@/domains/auth/session';
import { toApiErrorMessage } from '@/lib/errors';

export function useLoginForm() {
  const router = useRouter();
  const route = useRoute();
  const username = ref('');
  const password = ref('');
  const error = ref<string | null>(null);
  const loading = ref(false);
  const sessionNotice = ref<string | null>(null);

  if (route.query.reason === 'session_expired') {
    sessionNotice.value = 'Tu sesion expiro. Inicia sesion nuevamente.';
  }

  async function login() {
    loading.value = true;
    error.value = null;
    try {
      const res = await authApi.login({ username: username.value, password: password.value });

      setAccessToken(res.data.access);
      if (res.data.refresh) setRefreshToken(res.data.refresh);

      await router.push('/');
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }
  }

  return {
    username,
    password,
    error,
    loading,
    sessionNotice,
    login,
  };
}

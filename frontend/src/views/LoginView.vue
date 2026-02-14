<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { api } from '@/lib/api';

const router = useRouter();

const username = ref('');
const password = ref('');
const error = ref<string | null>(null);
const loading = ref(false);

async function login() {
  loading.value = true;
  error.value = null;
  try {
    const res = await api.post('/api/auth/token/', {
      username: username.value,
      password: password.value,
    });

    localStorage.setItem('access_token', res.data.access);
    if (res.data.refresh) localStorage.setItem('refresh_token', res.data.refresh);

    await router.push('/');
  } catch (e: any) {
    error.value = e?.response?.data ? JSON.stringify(e.response.data) : e?.message || 'Error';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-shell">
      <div class="login-card">
        <h1 class="login-title">Acceso</h1>
        <div class="login-subtitle">Gestiona tu patrimonio familiar con claridad.</div>

        <div v-if="error" class="alert login-alert">
          {{ error }}
        </div>

        <form class="login-form" @submit.prevent="login">
          <label class="login-field">
            <span class="login-label">Usuario</span>
            <input v-model="username" autocomplete="username" class="input" />
          </label>

          <label class="login-field">
            <span class="login-label">Contrasena</span>
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              class="input"
            />
          </label>

          <button :disabled="loading" type="submit" class="btn btn-primary login-submit">
            {{ loading ? 'Entrando...' : 'Entrar' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: calc(100vh - 60px);
  display: grid;
  align-items: start;
  justify-items: center;
  padding: 24px;
  background:
    radial-gradient(800px 400px at 10% 0%, rgba(255, 255, 255, 0.06), transparent 60%),
    radial-gradient(600px 300px at 90% 20%, rgba(255, 255, 255, 0.04), transparent 60%);
}

.login-shell {
  width: min(520px, 100%);
  margin-top: 96px;
}

.login-card {
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 24px;
  background: var(--panel);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.35);
}

.login-title {
  margin: 0 0 6px 0;
  font-size: 24px;
}

.login-subtitle {
  color: var(--muted);
  margin-bottom: 18px;
}

.login-form {
  display: grid;
  gap: 14px;
}

.login-field {
  display: grid;
  gap: 6px;
}

.login-label {
  font-size: 13px;
  color: var(--muted);
}

.login-submit {
  margin-top: 6px;
  width: 100%;
}

.login-alert {
  margin-bottom: 12px;
}
</style>

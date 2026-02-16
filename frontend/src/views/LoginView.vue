<script setup lang="ts">
import { useLoginForm } from '@/domains/auth';

const { username, password, error, loading, login } = useLoginForm();
</script>

<template>
  <div class="ui-auth-page">
    <div class="ui-auth-shell">
      <div class="ui-auth-card">
        <h1 class="ui-auth-title">Acceso</h1>
        <div class="ui-auth-subtitle">Gestiona tu patrimonio familiar con claridad.</div>

        <div v-if="error" class="alert ui-auth-alert">
          {{ error }}
        </div>

        <form class="ui-auth-form" @submit.prevent="login">
          <label class="ui-auth-field">
            <span class="ui-auth-label">Usuario</span>
            <input v-model="username" autocomplete="username" class="input" />
          </label>

          <label class="ui-auth-field">
            <span class="ui-auth-label">Contrasena</span>
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              class="input"
            />
          </label>

          <button :disabled="loading" type="submit" class="btn btn-primary ui-auth-submit">
            {{ loading ? 'Entrando...' : 'Entrar' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRegisterForm } from '@/domains/auth';
import { RouterLink } from 'vue-router';

const { username, password, passwordConfirm, error, loading, register } = useRegisterForm();
</script>

<template>
  <div class="ui-auth-page">
    <div class="ui-auth-shell">
      <div class="ui-auth-card">
        <h1 class="ui-auth-title">Crear cuenta</h1>
        <div class="ui-auth-subtitle">Gestiona tu patrimonio familiar con claridad.</div>

        <div v-if="error" class="alert ui-auth-alert">
          {{ error }}
        </div>

        <form class="ui-auth-form" @submit.prevent="register">
          <label class="ui-auth-field">
            <span class="ui-auth-label">Usuario</span>
            <input v-model="username" autocomplete="username" class="input" />
          </label>

          <label class="ui-auth-field">
            <span class="ui-auth-label">Contraseña</span>
            <input
              v-model="password"
              type="password"
              autocomplete="new-password"
              class="input"
            />
          </label>

          <label class="ui-auth-field">
            <span class="ui-auth-label">Confirmar contraseña</span>
            <input
              v-model="passwordConfirm"
              type="password"
              autocomplete="new-password"
              class="input"
            />
          </label>

          <button :disabled="loading" type="submit" class="btn btn-primary ui-auth-submit">
            {{ loading ? 'Creando cuenta...' : 'Crear cuenta' }}
          </button>
        </form>

        <div class="ui-auth-footer">
          ¿Ya tienes cuenta?
          <RouterLink to="/login" class="ui-auth-link">Inicia sesión</RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>

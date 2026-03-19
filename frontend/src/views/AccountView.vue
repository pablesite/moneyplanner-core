<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { authApi, toAuthErrorMessage } from '@/domains/auth';

const route = useRoute();

const loading = ref(true);
const error = ref<string | null>(null);
const baseCurrency = ref<string>('');

const permissionNotice =
  route.query.reason === 'permission_denied'
    ? 'No tienes permisos para acceder a esa seccion.'
    : null;

async function load() {
  loading.value = true;
  error.value = null;
  try {
    const res = await authApi.validateSession();
    baseCurrency.value = res.data?.base_currency ?? '';
  } catch (e: unknown) {
    error.value = toAuthErrorMessage(e);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="container ui-pro-page">
    <h1 class="h1 ui-profile-title">Perfil</h1>

    <div v-if="error" class="alert mt-3">
      {{ error }}
    </div>

    <div v-if="permissionNotice" class="alert mt-3">
      {{ permissionNotice }}
    </div>

    <div v-if="loading" class="ui-status-line mt-3">Cargando cuenta...</div>

    <div v-else class="grid gap-3.5">
      <section class="card ui-pro-panel ui-profile-panel">
        <div class="ui-profile-head">
          <h2 class="ui-profile-head-title">Cuenta Core</h2>
        </div>

        <div class="ui-profile-layout">
          <div class="ui-profile-list">
            <div class="ui-profile-row">
              <span class="ui-profile-label">Deployment</span>
              <strong class="ui-profile-value">Core (self-hosted)</strong>
            </div>
            <div class="ui-profile-row">
              <span class="ui-profile-label">Moneda base</span>
              <strong class="ui-profile-value">{{ baseCurrency || 'no configurada' }}</strong>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

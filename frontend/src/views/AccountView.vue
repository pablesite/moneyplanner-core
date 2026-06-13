<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { authApi, toAuthErrorMessage } from '@/domains/auth';
import { clearAuthTokens } from '@/domains/auth/session';
import { coreApi } from '@/lib/api';

const route = useRoute();

const loading = ref(true);
const error = ref<string | null>(null);
const baseCurrency = ref<string>('');

const backupBusy = ref(false);
const backupError = ref<string | null>(null);
const restoreBusy = ref(false);
const restoreError = ref<string | null>(null);
const restoreStatus = ref<string | null>(null);
const restoreFileInputRef = ref<HTMLInputElement | null>(null);

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

async function downloadBackup() {
  backupBusy.value = true;
  backupError.value = null;
  try {
    const res = await coreApi.get('/api/core/db-backup/', { responseType: 'blob' });
    const today = new Date().toISOString().slice(0, 10);
    const filename = `the_arkenstone_backup_${today}.dump`;
    const url = URL.createObjectURL(res.data as Blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch {
    backupError.value = 'No se pudo generar el backup. Comprueba que eres administrador.';
  } finally {
    backupBusy.value = false;
  }
}

function triggerRestoreDialog() {
  restoreError.value = null;
  restoreStatus.value = null;
  restoreFileInputRef.value?.click();
}

async function handleRestoreFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input?.files?.[0];
  if (!file) return;

  const confirmed = window.confirm(
    `¿Restaurar la base de datos desde "${file.name}"?\n\n` +
      'ATENCIÓN: Esto reemplazará TODOS los datos actuales sin posibilidad de deshacer desde la app.\n\n' +
      'Asegúrate de tener un backup reciente antes de continuar.',
  );
  if (!confirmed) {
    input.value = '';
    return;
  }

  restoreBusy.value = true;
  restoreError.value = null;
  restoreStatus.value = null;

  try {
    const formData = new FormData();
    formData.append('file', file);
    await coreApi.post('/api/core/db-restore/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    clearAuthTokens();
    window.location.replace('/login?reason=db_restored');
  } catch {
    restoreError.value =
      'La restauración falló. Comprueba que el archivo es un .dump válido y que eres administrador.';
  } finally {
    restoreBusy.value = false;
    input.value = '';
  }
}
</script>

<template>
  <div class="container ui-page-shell">
    <header class="ui-page-head">
      <div>
        <p class="ui-page-eyebrow">Cuenta</p>
        <h1 class="ui-page-title ui-profile-title">Perfil</h1>
      </div>
    </header>

    <div v-if="error" class="ui-state-block ui-state-error" role="alert">
      {{ error }}
    </div>

    <div v-if="permissionNotice" class="ui-state-block ui-state-error" role="alert">
      {{ permissionNotice }}
    </div>

    <div v-if="loading" class="ui-state-block ui-state-loading">Cargando cuenta...</div>

    <div v-else class="grid gap-3.5">
      <section class="ui-section-card ui-profile-panel">
        <div class="ui-section-head ui-profile-head">
          <div class="ui-section-copy">
            <h2 class="ui-section-title ui-profile-head-title">Cuenta Core</h2>
          </div>
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

      <section class="ui-section-card ui-section-card-padded grid gap-2.5">
        <div class="ui-section-head ui-profile-head">
          <div class="ui-section-copy">
            <h2 class="ui-section-title ui-profile-head-title">Base de datos</h2>
          </div>
        </div>
        <p class="ui-section-subtitle m-0">
          Exporta o restaura la base de datos completa. Solo disponible para administradores.
        </p>
        <div class="ui-action-bar m-0">
          <button
            class="btn btn-ghost"
            type="button"
            :disabled="backupBusy || restoreBusy"
            @click="downloadBackup"
          >
            {{ backupBusy ? 'Generando...' : 'Exportar base de datos' }}
          </button>
          <button
            class="btn btn-ghost"
            type="button"
            :disabled="backupBusy || restoreBusy"
            @click="triggerRestoreDialog"
          >
            {{ restoreBusy ? 'Restaurando...' : 'Restaurar base de datos' }}
          </button>
          <input
            ref="restoreFileInputRef"
            type="file"
            accept=".dump"
            class="sr-only"
            @change="handleRestoreFile"
          />
        </div>
        <p v-if="restoreStatus" class="ui-state-block ui-state-success m-0">{{ restoreStatus }}</p>
        <p v-if="backupError" class="ui-state-block ui-state-error m-0">{{ backupError }}</p>
        <p v-if="restoreError" class="ui-state-block ui-state-error m-0">{{ restoreError }}</p>
      </section>
    </div>
  </div>
</template>

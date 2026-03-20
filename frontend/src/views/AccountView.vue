<script setup lang="ts">
import { computed, onMounted, ref, type ComponentPublicInstance } from 'vue';
import { useRoute } from 'vue-router';
import { authApi, toAuthErrorMessage } from '@/domains/auth';
import { usePortableDataTransfer } from '@/domains/data-input';

const route = useRoute();

const loading = ref(true);
const error = ref<string | null>(null);
const baseCurrency = ref<string>('');
const {
  dataTransferUiBusy,
  dataTransferBusy,
  dataTransferBusyLabel,
  dataTransferStatus,
  dataTransferError,
  dataTransferToastKind,
  dataTransferToastMessage,
  importFileInputRef,
  triggerImportDialog,
  exportDataBundle,
  importDataFromFile,
} = usePortableDataTransfer({
  externalBusy: loading,
  onImportCompleted: load,
});

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

const setImportFileInputRef = (el: Element | ComponentPublicInstance | null): void => {
  importFileInputRef.value = el as HTMLInputElement | null;
};
const portableDataToastClass = computed(() =>
  dataTransferToastKind.value === 'error'
    ? 'border border-rose-300/30 bg-rose-950/90 text-rose-100'
    : 'border border-emerald-300/30 bg-emerald-950/90 text-emerald-100',
);
const portableDataToastDotClass = computed(() =>
  dataTransferToastKind.value === 'error' ? 'bg-rose-300' : 'bg-emerald-300',
);
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

      <section class="card ui-pro-panel grid gap-2.5">
        <div class="ui-profile-head">
          <h2 class="ui-profile-head-title">Portable data</h2>
        </div>
        <p class="subtle m-0">
          Exporta, importa o reemplaza tus datos para mover tu entorno entre instancias.
        </p>
        <div class="actions m-0">
          <button
            class="btn btn-ghost"
            type="button"
            :disabled="dataTransferUiBusy"
            @click="exportDataBundle"
          >
            Exportar datos
          </button>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="dataTransferUiBusy"
            @click="triggerImportDialog('append')"
          >
            Importar datos
          </button>
          <button
            class="btn btn-ghost"
            type="button"
            :disabled="dataTransferUiBusy"
            @click="triggerImportDialog('replace')"
          >
            Reemplazar datos
          </button>
          <input
            :ref="setImportFileInputRef"
            type="file"
            accept="application/json,.json"
            class="sr-only"
            @change="importDataFromFile"
          />
        </div>
        <p v-if="dataTransferStatus" class="subtle m-0">{{ dataTransferStatus }}</p>
        <p v-if="dataTransferError" class="alert m-0">{{ dataTransferError }}</p>
      </section>
    </div>
  </div>

  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="-translate-y-2 opacity-0"
    enter-to-class="translate-y-0 opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="translate-y-0 opacity-100"
    leave-to-class="-translate-y-2 opacity-0"
  >
    <div
      v-if="dataTransferToastMessage"
      class="fixed right-4 top-4 z-[80] max-w-[min(92vw,560px)] rounded-xl px-4 py-3 text-sm shadow-2xl backdrop-blur"
      :class="portableDataToastClass"
      role="status"
      aria-live="polite"
    >
      <div class="flex items-start gap-2.5">
        <span
          class="mt-0.5 inline-block h-2.5 w-2.5 rounded-full"
          :class="portableDataToastDotClass"
        />
        <span>{{ dataTransferToastMessage }}</span>
      </div>
    </div>
  </Transition>

  <div
    v-if="dataTransferBusy"
    class="fixed inset-0 z-[70] flex items-center justify-center bg-black/45 px-4 backdrop-blur-[2px]"
    role="status"
    aria-live="polite"
    aria-busy="true"
  >
    <div class="w-full max-w-md rounded-2xl border border-white/15 bg-[#111827f2] p-4 shadow-2xl">
      <div class="flex items-center gap-3">
        <span
          class="inline-block h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-teal-300"
          aria-hidden="true"
        />
        <div>
          <p class="m-0 text-sm font-medium text-white">
            {{ dataTransferBusyLabel ?? 'Procesando datos...' }}
          </p>
          <p class="m-0 text-xs text-white/65">No cierres la pestaña hasta que termine.</p>
        </div>
      </div>
    </div>
  </div>
</template>

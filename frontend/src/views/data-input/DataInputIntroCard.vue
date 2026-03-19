<script setup lang="ts">
import type { ComponentPublicInstance } from 'vue';

const props = defineProps<{
  page: any;
}>();

const page = props.page;

const setImportFileInputRef = (el: Element | ComponentPublicInstance | null): void => {
  // Keep the hidden file input connected to the parent view.
  // The parent owns the actual ref so the import flow stays centralized.
  page.importFileInputRef.value = el as HTMLInputElement | null;
};
</script>

<template>
  <section class="card ui-pro-panel grid gap-2.5">
    <p class="ui-pro-kicker">Introduccion de datos</p>
    <h1 class="h1 m-0">{{ page.dataInputCheckTitle }}</h1>
    <p class="subtle m-0">
      {{ page.dataInputSummary }}
    </p>
    <p class="subtle m-0">
      Gestiona aqui la base financiera anual: ingresos, gastos, activos y pasivos para el analisis
      patrimonial.
    </p>
    <div class="actions m-0">
      <button
        class="btn btn-ghost"
        type="button"
        :disabled="page.dataTransferUiBusy"
        @click="page.exportDataBundle"
      >
        Exportar datos
      </button>
      <button
        class="btn btn-primary"
        type="button"
        :disabled="page.dataTransferUiBusy"
        @click="page.triggerImportDialog('append')"
      >
        Importar datos
      </button>
      <button
        class="btn btn-ghost"
        type="button"
        :disabled="page.dataTransferUiBusy"
        @click="page.triggerImportDialog('replace')"
      >
        Reemplazar datos
      </button>
      <input
        :ref="setImportFileInputRef"
        type="file"
        accept="application/json,.json"
        class="sr-only"
        @change="page.importDataFromFile"
      />
    </div>
    <p v-if="page.dataTransferStatus" class="subtle m-0">{{ page.dataTransferStatus }}</p>
    <p v-if="page.dataTransferError" class="alert m-0">{{ page.dataTransferError }}</p>
  </section>

  <Transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="-translate-y-2 opacity-0"
    enter-to-class="translate-y-0 opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="translate-y-0 opacity-100"
    leave-to-class="-translate-y-2 opacity-0"
  >
    <div
      v-if="page.dataTransferToastMessage"
      class="fixed right-4 top-4 z-[80] max-w-[min(92vw,560px)] rounded-xl px-4 py-3 text-sm shadow-2xl backdrop-blur"
      :class="
        page.dataTransferToastKind === 'error'
          ? 'border border-rose-300/30 bg-rose-950/90 text-rose-100'
          : 'border border-emerald-300/30 bg-emerald-950/90 text-emerald-100'
      "
      role="status"
      aria-live="polite"
    >
      <div class="flex items-start gap-2.5">
        <span
          class="mt-0.5 inline-block h-2.5 w-2.5 rounded-full"
          :class="page.dataTransferToastKind === 'error' ? 'bg-rose-300' : 'bg-emerald-300'"
        />
        <span>{{ page.dataTransferToastMessage }}</span>
      </div>
    </div>
  </Transition>

  <div
    v-if="page.dataTransferBusy"
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
            {{ page.dataTransferBusyLabel ?? 'Procesando datos...' }}
          </p>
          <p class="m-0 text-xs text-white/65">No cierres la pestaña hasta que termine.</p>
        </div>
      </div>
    </div>
  </div>
</template>

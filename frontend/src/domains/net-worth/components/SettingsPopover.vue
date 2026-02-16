<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue';

type CurrencyOption = { value: string; label: string };

type Props = {
  loading: boolean;

  // moneda base (store)
  baseCurrency: string;
  currencies: CurrencyOption[];

  // modo nominal/real (vista)
  valueMode: 'nominal' | 'real';
  canShowReal: boolean;
  modeHelp: string; // texto tipo: "Nominal (euros de hoy)" / "IPC: euros..."
  realBaseLabel?: string; // "Base: 2024-01" etc.

  // acciones
  showRefresh?: boolean; // por defecto true
  showSnapshot?: boolean; // por defecto true
  iconOnly?: boolean;
};

const props = withDefaults(defineProps<Props>(), {
  showRefresh: true,
  showSnapshot: true,
  iconOnly: false,
});

const emit = defineEmits<{
  (e: 'update:baseCurrency', value: string): void;
  (e: 'update:valueMode', value: 'nominal' | 'real'): void;
  (e: 'snapshot'): void;
  (e: 'refresh'): void;
}>();

const open = ref(false);
const rootEl = ref<HTMLElement | null>(null);

function toggle() {
  open.value = !open.value;
}
function close() {
  open.value = false;
}

function onDocClick(e: MouseEvent) {
  if (!open.value) return;
  const t = e.target as Node | null;
  if (!t) return;
  if (rootEl.value && !rootEl.value.contains(t)) close();
}

function onKeydown(e: KeyboardEvent) {
  if (!open.value) return;
  if (e.key === 'Escape') close();
}

onMounted(() => {
  document.addEventListener('click', onDocClick);
  window.addEventListener('keydown', onKeydown);
});
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick);
  window.removeEventListener('keydown', onKeydown);
});

function onSelectBaseCurrency(e: Event) {
  const v = (e.target as HTMLSelectElement).value;
  emit('update:baseCurrency', v);
}

function onSelectMode(e: Event) {
  const v = (e.target as HTMLSelectElement).value as 'nominal' | 'real';
  emit('update:valueMode', v);
}
</script>

<template>
  <div ref="rootEl" class="nw-settings-root">
    <button
      class="btn"
      :class="{ 'nw-settings-icon-only': iconOnly }"
      type="button"
      :disabled="loading"
      aria-label="Ajustes"
      @click="toggle"
    >
      <span class="nw-settings-btn-icon" aria-hidden="true">&#9881;&#65039;</span>
      <span v-if="!iconOnly">Ajustes</span>
    </button>

    <div v-if="open" class="nw-settings-panel">
      <div class="nw-settings-title">Ajustes</div>

      <div class="nw-settings-block">
        <div class="nw-settings-field">
          <div class="nw-settings-label">Moneda base</div>
          <select
            class="input nw-settings-select-currency"
            :value="baseCurrency"
            :disabled="loading"
            @change="onSelectBaseCurrency"
          >
            <option v-for="c in currencies" :key="c.value" :value="c.value">
              {{ c.label }}
            </option>
          </select>
          <div class="nw-settings-hint">Totales y snapshots en esta moneda</div>
        </div>
      </div>

      <div class="nw-settings-block">
        <div class="nw-settings-field">
          <div class="nw-settings-label">Modo</div>
          <select
            class="input nw-settings-select-mode"
            :value="valueMode"
            :disabled="loading"
            @change="onSelectMode"
          >
            <option value="nominal">Nominal</option>
            <option value="real" :disabled="!canShowReal">IPC (euros mes base)</option>
          </select>

          <div class="nw-settings-hint">
            {{ modeHelp }}
            <span v-if="valueMode === 'real' && realBaseLabel">. {{ realBaseLabel }}</span>
          </div>

          <div v-if="!canShowReal" class="nw-settings-hint nw-settings-hint-error">
            El modo IPC solo esta disponible cuando se puede calcular (EUR + IPC cargado).
          </div>
        </div>
      </div>

      <div class="nw-settings-block nw-settings-actions">
        <button
          v-if="showSnapshot"
          class="btn btn-primary"
          type="button"
          :disabled="loading"
          @click="emit('snapshot')"
        >
          Guardar snapshot
        </button>

        <button
          v-if="showRefresh"
          class="btn"
          type="button"
          :disabled="loading"
          @click="emit('refresh')"
        >
          Refrescar
        </button>

        <button class="btn nw-settings-close" type="button" @click="close">Cerrar</button>
      </div>
    </div>
  </div>
</template>

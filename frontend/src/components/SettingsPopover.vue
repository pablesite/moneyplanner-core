<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

type CurrencyOption = { value: string; label: string };

type Props = {
  loading: boolean;

  // moneda base (store)
  baseCurrency: string;
  currencies: CurrencyOption[];

  // modo nominal/real (vista)
  valueMode: "nominal" | "real";
  canShowReal: boolean;
  modeHelp: string; // texto tipo: "Nominal (euros de hoy)" / "IPC: euros..."
  realBaseLabel?: string; // "Base: 2024-01" etc.

  // acciones
  showRefresh?: boolean; // por defecto true
  iconOnly?: boolean;
};

const props = withDefaults(defineProps<Props>(), {
  showRefresh: true,
  iconOnly: false,
});

const emit = defineEmits<{
  (e: "update:baseCurrency", value: string): void;
  (e: "update:valueMode", value: "nominal" | "real"): void;
  (e: "snapshot"): void;
  (e: "refresh"): void;
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
  if (e.key === "Escape") close();
}

onMounted(() => {
  document.addEventListener("click", onDocClick);
  window.addEventListener("keydown", onKeydown);
});
onBeforeUnmount(() => {
  document.removeEventListener("click", onDocClick);
  window.removeEventListener("keydown", onKeydown);
});

function onSelectBaseCurrency(e: Event) {
  const v = (e.target as HTMLSelectElement).value;
  emit("update:baseCurrency", v);
}

function onSelectMode(e: Event) {
  const v = (e.target as HTMLSelectElement).value as "nominal" | "real";
  emit("update:valueMode", v);
}
</script>

<template>
  <div ref="rootEl" class="popover-root">
    <button
      class="btn"
      :class="{ 'icon-only': iconOnly }"
      type="button"
      @click="toggle"
      :disabled="loading"
      aria-label="Ajustes"
    >
      <span class="btn-icon" aria-hidden="true">&#9881;&#65039;</span>
      <span v-if="!iconOnly">Ajustes</span>
    </button>

    <div v-if="open" class="popover-panel">
      <div class="popover-title">Ajustes</div>

      <div class="popover-block">
        <div class="field">
          <div class="label">Moneda base</div>
          <select class="input" style="width: 140px;" :value="baseCurrency" @change="onSelectBaseCurrency" :disabled="loading">
            <option v-for="c in currencies" :key="c.value" :value="c.value">
              {{ c.label }}
            </option>
          </select>
          <div class="hint">Totales y snapshots en esta moneda</div>
        </div>
      </div>

      <div class="popover-block">
        <div class="field">
          <div class="label">Modo</div>
          <select class="input" style="width: 180px;" :value="valueMode" @change="onSelectMode" :disabled="loading">
            <option value="nominal">Nominal</option>
            <option value="real" :disabled="!canShowReal">IPC (euros mes base)</option>
          </select>

          <div class="hint">
            {{ modeHelp }}
            <span v-if="valueMode === 'real' && realBaseLabel"> · {{ realBaseLabel }}</span>
          </div>

          <div v-if="!canShowReal" class="hint" style="color: rgba(255, 140, 160, 0.95);">
            El modo IPC solo está disponible cuando se puede calcular (EUR + IPC cargado).
          </div>
        </div>
      </div>

      <div class="popover-block" style="display:flex; gap:10px; flex-wrap: wrap;">
        <button class="btn btn-primary" type="button" @click="emit('snapshot')" :disabled="loading">
          Guardar snapshot
        </button>

        <button v-if="showRefresh" class="btn" type="button" @click="emit('refresh')" :disabled="loading">
          Refrescar
        </button>

        <button class="btn" type="button" @click="close">
          Cerrar
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.popover-root {
  position: relative;
  display: inline-block;
}

.icon-only{
  padding: 8px 10px;
  border-radius: 10px;
}

.btn-icon{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
}

/* panel con fondo sólido/legible */
.popover-panel {
  position: absolute;
  right: 0;
  top: calc(100% + 10px);
  width: min(360px, 92vw);
  padding: 14px;

  z-index: 2000;

  /* clave: fondo real (no transparente) */
  background: rgba(20, 20, 22, 0.96);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);

  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 14px;

  /* sombra para separar del contenido de atrás */
  box-shadow:
    0 16px 40px rgba(0, 0, 0, 0.55),
    0 0 0 1px rgba(0, 0, 0, 0.35);

  /* evita que "herede" estilos raros de .card */
  text-align: left;
}

/* título */
.popover-title {
  font-size: 14px;
  opacity: 0.9;
  margin-bottom: 10px;
}

.popover-block {
  padding: 10px 0;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.popover-block:first-of-type {
  border-top: none;
  padding-top: 0;
}

.field {
  display: grid;
  gap: 8px;
}

.label {
  font-size: 13px;
  opacity: 0.85;
}

.hint {
  font-size: 12px;
  opacity: 0.72;
}
</style>


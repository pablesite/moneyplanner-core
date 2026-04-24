<script setup lang="ts">
import { computed, ref } from 'vue';
import { formatMoney } from '@/lib/format';
import type { FiscalReportPayload } from '@/domains/fiscal-report/api';

const props = defineProps<{
  report: FiscalReportPayload;
}>();

const copied = ref<string | null>(null);

const casilla029 = computed(() => props.report.resumen.total_capital_mobiliario_eur);
const casilla332 = computed(() => props.report.resumen.neto_ganancias_perdidas_eur);

async function copyValue(label: string, value: number) {
  const text = `${label}: ${formatMoney(value, 'EUR')}`;
  try {
    await navigator.clipboard.writeText(text);
    copied.value = label;
    window.setTimeout(() => {
      copied.value = null;
    }, 1400);
  } catch {
    copied.value = null;
  }
}
</script>

<template>
  <section class="ui-section-card fiscal-section fiscal-summary-card">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h3 class="ui-section-title">Resumen para declaración</h3>
        <p class="ui-section-subtitle">Valores listos para copiar a Hacienda</p>
      </div>
    </header>

    <div class="fiscal-summary-list">
      <div class="fiscal-summary-row">
        <div>
          <strong>Casilla 029 (Capital mobiliario)</strong>
          <p>{{ formatMoney(casilla029, 'EUR') }}</p>
        </div>
        <button class="btn btn-sm" type="button" @click="copyValue('Casilla 029', casilla029)">
          {{ copied === 'Casilla 029' ? 'Copiado' : 'Copiar' }}
        </button>
      </div>

      <div class="fiscal-summary-row">
        <div>
          <strong>Casilla 332 (Ganancias/perdidas)</strong>
          <p>{{ formatMoney(casilla332, 'EUR') }}</p>
        </div>
        <button class="btn btn-sm" type="button" @click="copyValue('Casilla 332', casilla332)">
          {{ copied === 'Casilla 332' ? 'Copiado' : 'Copiar' }}
        </button>
      </div>
    </div>
  </section>
</template>

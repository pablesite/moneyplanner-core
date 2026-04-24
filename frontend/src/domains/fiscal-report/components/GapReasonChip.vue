<script setup lang="ts">
import { computed } from 'vue';
import type { GapReason } from '@/domains/fiscal-report/api';

const props = defineProps<{
  value: GapReason | null;
}>();

const label = computed(() => {
  if (!props.value) return 'Sin gap';
  if (props.value === 'pre_period_buy') return 'Compra pre-periodo';
  if (props.value === 'missing_data') return 'Datos incompletos';
  return 'Transferencia externa';
});

const tooltip = computed(() => {
  if (!props.value) return 'No hay gap FIFO en esta venta.';
  if (props.value === 'pre_period_buy') {
    return 'Hay compras anteriores al periodo sin coste fiscal trazado. Usa coste manual.';
  }
  if (props.value === 'missing_data') {
    return 'Faltan movimientos de origen para cubrir la venta completa.';
  }
  return 'Saldo de entrada externo sin trazabilidad de lote de compra.';
});
</script>

<template>
  <span v-if="props.value" class="badge fiscal-gap-chip" :title="tooltip">
    {{ label }}
  </span>
</template>

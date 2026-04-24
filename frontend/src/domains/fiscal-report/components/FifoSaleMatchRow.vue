<script setup lang="ts">
import { computed, ref } from 'vue';
import { formatAmount, formatMoney } from '@/lib/format';
import type { FifoSaleMatch } from '@/domains/fiscal-report/api';
import GapReasonChip from './GapReasonChip.vue';

const props = defineProps<{
  asset: string;
  sale: FifoSaleMatch;
}>();

const emit = defineEmits<{
  manualCostBasis: [asset: string];
}>();

const expanded = ref(false);

const lotsCount = computed(() => props.sale.matched_lots.length);
</script>

<template>
  <tbody>
    <tr>
      <td>{{ props.sale.sell_date }}</td>
      <td>{{ props.sale.sell_exchange }}</td>
      <td>{{ props.sale.sell_symbol }}</td>
      <td>{{ formatAmount(props.sale.quantity_sold, { maxDecimals: 8 }) }}</td>
      <td>{{ formatMoney(props.sale.proceeds_eur, 'EUR') }}</td>
      <td>{{ formatMoney(props.sale.fee_eur, 'EUR') }}</td>
      <td>
        <GapReasonChip :value="props.sale.gap_reason" />
      </td>
      <td>
        <button class="btn btn-sm" type="button" @click="expanded = !expanded">
          {{ expanded ? 'Ocultar lotes' : `Ver lotes (${lotsCount})` }}
        </button>
      </td>
    </tr>
    <tr v-if="expanded" class="fiscal-lot-row">
      <td colspan="8">
        <table class="fiscal-lot-table">
          <thead>
            <tr>
              <th>Fecha compra</th>
              <th>Exchange compra</th>
              <th>Cantidad</th>
              <th>Precio unitario EUR</th>
              <th>Coste EUR</th>
              <th>Comisión EUR</th>
              <th>G/P EUR</th>
              <th>Días tenencia</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(lot, index) in props.sale.matched_lots" :key="index">
              <td>{{ lot.buy_date ?? 'N/A' }}</td>
              <td>{{ lot.buy_exchange ?? 'N/A' }}</td>
              <td>{{ formatAmount(lot.quantity_consumed, { maxDecimals: 8 }) }}</td>
              <td>{{ formatMoney(lot.unit_price_eur, 'EUR') }}</td>
              <td>{{ formatMoney(lot.cost_eur, 'EUR') }}</td>
              <td>{{ formatMoney(lot.fee_eur_allocated, 'EUR') }}</td>
              <td>{{ formatMoney(lot.gain_loss_eur, 'EUR') }}</td>
              <td>{{ lot.hold_days }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="props.sale.gap_quantity > 0" class="fiscal-sale-gap">
          <span class="fiscal-text-warning">
            Gap sin cobertura: {{ formatAmount(props.sale.gap_quantity, { maxDecimals: 8 }) }}
            {{ props.asset }}
          </span>
          <button
            v-if="props.sale.gap_reason === 'pre_period_buy'"
            class="btn btn-sm"
            type="button"
            @click="emit('manualCostBasis', props.asset)"
          >
            Asignar coste manual
          </button>
        </div>
      </td>
    </tr>
  </tbody>
</template>

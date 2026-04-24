<script setup lang="ts">
import { formatMoney } from '@/lib/format';
import type { FiscalBotResultRow } from '@/domains/fiscal-report/api';

defineProps<{
  rows: FiscalBotResultRow[];
}>();
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h3 class="ui-section-title">Ganancias/perdidas bots</h3>
        <p class="ui-section-subtitle">Resultado neto simplificado por bot</p>
      </div>
    </header>

    <div v-if="!rows.length" class="ui-state-block ui-state-empty">
      No hay resultados de bots para el año seleccionado.
    </div>

    <table v-else class="fiscal-table">
      <thead>
        <tr>
          <th>Bot</th>
          <th>Tipo</th>
          <th>Periodo</th>
          <th>Ganancia neta EUR</th>
          <th>Casilla</th>
          <th>⚠</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="index">
          <td>{{ row.bot_label }}</td>
          <td>{{ row.bot_type }}</td>
          <td>{{ row.periodo }}</td>
          <td>{{ formatMoney(row.ganancia_neta_eur, 'EUR') }}</td>
          <td>{{ row.casilla }}</td>
          <td>
            <span
              v-if="row.aviso_simplificacion"
              class="badge"
              title="Simplificacion: ver nota fiscal"
            >
              ⚠
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

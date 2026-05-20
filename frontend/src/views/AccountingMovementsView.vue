<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue';
import { onBeforeRouteLeave, useRoute } from 'vue-router';
import '@/domains/accounting/styles/movements.css';
import { useAccountingMovementsPage } from '@/domains/accounting/useAccountingMovementsPage';
import AccountingMovementsHero from '@/domains/accounting/components/AccountingMovementsHero.vue';
import AccountingAccountCatalog from '@/domains/accounting/components/AccountingAccountCatalog.vue';
import AccountingMovementsAllTransactions from '@/domains/accounting/components/AccountingMovementsAllTransactions.vue';
import AccountingBalances from '@/domains/accounting/components/AccountingBalances.vue';
import AccountingMovementsActivationModal from '@/domains/accounting/components/AccountingMovementsActivationModal.vue';
import AccountingMovementsEditTransactionModal from '@/domains/accounting/components/AccountingMovementsEditTransactionModal.vue';
import AccountingMovementsQuickEntryModal from '@/domains/accounting/components/AccountingMovementsQuickEntryModal.vue';
import { NetWorthDeltaChart, NetWorthTimelineChart } from '@/domains/net-worth';
import { BaseModal } from '@/domains/ui';

const route = useRoute();
const page = useAccountingMovementsPage();
const dailyTimelineExpanded = ref(false);

function formatNumber(value: number, decimals = 2): string {
  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

function closeDailyTimelineModal() {
  dailyTimelineExpanded.value = false;
}

onMounted(async () => {
  const { tab, date_from, date_to, kind, category_key, subcategory_key } = route.query;
  if (tab === 'todos') {
    page.activeTab = 'todos';
  }
  if (date_from || date_to) {
    page.todosDatePreset = 'custom';
    page.todosDateFrom = String(date_from ?? '');
    page.todosDateTo = String(date_to ?? '');
  }
  if (kind && kind !== 'all') {
    page.activityFilters.kind = String(kind) as typeof page.activityFilters.kind;
    // Wait for the watcher on filterCategoryOptions (triggered by kind change) to fire
    // before setting categoryKey, otherwise it would be cleared.
    await nextTick();
  }
  if (category_key) {
    page.activityFilters.categoryKey = String(category_key);
    // Wait for the watcher on categoryKey (which resets subcategoryKey) to fire
    // before setting subcategoryKey.
    await nextTick();
  }
  if (subcategory_key) {
    page.activityFilters.subcategoryKey = String(subcategory_key);
  }
});

onBeforeRouteLeave(() => {
  closeDailyTimelineModal();
});

onBeforeUnmount(() => {
  closeDailyTimelineModal();
});
</script>

<template>
  <div class="container ui-page-shell">
    <AccountingMovementsHero :page="page" />

    <div class="ui-section-card ui-accounting-unified-card">
      <div class="ui-accounting-daily-chart">
        <div v-if="page.dailyBalanceSeriesLoading" class="ui-state-block ui-state-loading">
          Cargando evolucion diaria...
        </div>
        <div v-else-if="page.dailyBalanceSeriesError" class="ui-state-block ui-state-error">
          {{ page.dailyBalanceSeriesError }}
        </div>
        <div v-else-if="!page.dailyBalanceSeriesRows.length" class="ui-state-block ui-state-empty">
          No hay movimientos suficientes para construir la serie diaria.
        </div>
        <div v-else class="ui-accounting-timeline-main">
          <div class="ui-accounting-timeline-toolbar">
            <div
              class="ui-accounting-timeline-range-group"
              role="group"
              aria-label="Rango temporal"
            >
              <button
                v-for="preset in page.dailyTimelinePresetOptions"
                :key="preset"
                class="ui-accounting-timeline-range-button"
                :class="{
                  'ui-accounting-timeline-range-button-active':
                    page.dailyTimelineCustomWindow === null &&
                    page.selectedDailyTimelinePreset === preset,
                }"
                type="button"
                @click="page.setDailyTimelinePreset(preset)"
              >
                {{ preset }}
              </button>
            </div>

            <div class="ui-accounting-timeline-toolbar-actions">
              <span class="ui-accounting-timeline-range-caption">{{
                page.dailyBalanceSeriesRangeLabel
              }}</span>
              <button
                class="ui-accounting-timeline-expand-button"
                type="button"
                @click="dailyTimelineExpanded = true"
              >
                Expandir
              </button>
            </div>
          </div>

          <div class="ui-accounting-timeline-chart-shell">
            <NetWorthTimelineChart
              :points="page.dailyBalanceSeriesChartPoints"
              :unit="page.dailyBalanceSeriesUnit"
              series-label="Saldo neto contable"
              aria-label="Evolución diaria del saldo neto contable"
            />
            <NetWorthDeltaChart
              :rows="page.dailyBalanceSeriesMonthlyRows"
              :unit="page.dailyBalanceSeriesUnit"
            />
          </div>
        </div>
      </div>

      <BaseModal
        :open="dailyTimelineExpanded"
        title="Evolución contable diaria"
        panel-class="max-w-[1080px]"
        :close-on-backdrop="true"
        @close="dailyTimelineExpanded = false"
      >
        <div class="ui-accounting-timeline-modal">
          <div class="ui-accounting-timeline-modal-head">
            <div>
              <div class="ui-accounting-timeline-modal-title">Saldo neto contable</div>
              <div class="ui-accounting-timeline-modal-copy">
                {{ page.dailyBalanceSeriesRangeLabel }}
              </div>
            </div>
            <div class="ui-accounting-timeline-modal-value">
              {{ formatNumber(page.dailyBalanceLatestChartPoint?.value ?? 0, 2) }}
              {{ page.dailyBalanceSeriesUnit }}
            </div>
          </div>

          <div class="ui-accounting-timeline-modal-ranges">
            <label class="ui-accounting-timeline-slider-group">
              <span>Inicio</span>
              <input
                class="ui-accounting-timeline-slider"
                type="range"
                min="0"
                :max="Math.max(0, page.dailyBalanceSeriesRows.length - 1)"
                :value="page.dailyTimelineWindow.start"
                @input="
                  page.updateDailyTimelineWindowStart(($event.target as HTMLInputElement).value)
                "
              />
              <strong>{{ page.dailyBalanceSeriesChartPoints[0]?.fullLabel ?? '-' }}</strong>
            </label>

            <label class="ui-accounting-timeline-slider-group">
              <span>Fin</span>
              <input
                class="ui-accounting-timeline-slider"
                type="range"
                min="0"
                :max="Math.max(0, page.dailyBalanceSeriesRows.length - 1)"
                :value="page.dailyTimelineWindow.end"
                @input="
                  page.updateDailyTimelineWindowEnd(($event.target as HTMLInputElement).value)
                "
              />
              <strong>{{ page.dailyBalanceLatestChartPoint?.fullLabel ?? '-' }}</strong>
            </label>
          </div>

          <div class="ui-accounting-timeline-chart-shell">
            <NetWorthTimelineChart
              :points="page.dailyBalanceSeriesChartPoints"
              :unit="page.dailyBalanceSeriesUnit"
              series-label="Saldo neto contable"
              aria-label="Evolución diaria del saldo neto contable expandida"
              expanded
            />
            <NetWorthDeltaChart
              :rows="page.dailyBalanceSeriesMonthlyRows"
              :unit="page.dailyBalanceSeriesUnit"
            />
          </div>
        </div>
      </BaseModal>

      <div class="ui-accounting-incard-tabs">
        <div class="ui-view-tabs">
          <button
            class="ui-view-tab"
            :class="{ 'ui-view-tab-active': page.activeTab === 'cuentas' }"
            type="button"
            @click="page.activeTab = 'cuentas'"
          >
            Cuentas
          </button>
          <button
            class="ui-view-tab"
            :class="{ 'ui-view-tab-active': page.activeTab === 'todos' }"
            type="button"
            @click="page.activeTab = 'todos'"
          >
            Todos los movimientos
          </button>
          <button
            class="ui-view-tab"
            :class="{ 'ui-view-tab-active': page.activeTab === 'estadisticas' }"
            type="button"
            @click="page.activeTab = 'estadisticas'"
          >
            Estadisticas
          </button>
        </div>
        <button
          v-if="page.activeTab === 'cuentas' && page.hasAvailableManualPositions"
          class="btn ui-accounting-cta-secondary"
          type="button"
          aria-label="Añadir cuenta al libro contable"
          title="Añadir cuenta al libro contable"
          @click="page.openActivationModal"
        >
          ⊕
        </button>
        <button
          class="btn btn-primary ui-accounting-cta"
          type="button"
          aria-label="Registrar movimiento diario"
          title="Registrar movimiento diario"
          :disabled="!page.liquidityAccounts.length"
          @click="page.showQuickEntryModal = true"
        >
          +
        </button>
      </div>
      <AccountingAccountCatalog v-if="page.activeTab === 'cuentas'" :page="page" />
      <AccountingMovementsAllTransactions v-else-if="page.activeTab === 'todos'" :page="page" />
      <AccountingBalances v-else-if="page.activeTab === 'estadisticas'" :page="page" />
    </div>

    <AccountingMovementsActivationModal :page="page" />
    <AccountingMovementsEditTransactionModal :page="page" />
    <AccountingMovementsQuickEntryModal :page="page" />
  </div>
</template>

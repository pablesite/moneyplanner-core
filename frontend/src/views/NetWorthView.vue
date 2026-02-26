<script setup lang="ts">
import { computed } from 'vue';
import { NetWorthDonut, SettingsPopover, useNetWorthViewState } from '@/domains/net-worth';

const {
  store,
  valueMode,
  currencies,
  prettyError,
  canShowReal,
  confirmDeleteSnapshot,
  formatMoney,
  unitLabel,
  modeLabel,
  realBaseLabel,
  summaryAssets,
  summaryLiabilities,
  summaryNetWorth,
  byCategoryLabels,
  byCategoryAssets,
  byCategoryLiabilities,
  summaryAssetBackedLiabilities,
  summaryUnbackedLiabilities,
} = useNetWorthViewState();

function toNumber(raw: unknown): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const value = Number(normalized);
  return Number.isFinite(value) ? value : 0;
}

function formatNumber(n: number, decimals = 2): string {
  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function formatPct(n: number | null, decimals = 0): string {
  if (n == null || !Number.isFinite(n)) return '-';
  return new Intl.NumberFormat('es-ES', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

const assetsValue = computed(() => Math.max(0, toNumber(summaryAssets.value)));
const liabilitiesValue = computed(() => Math.max(0, toNumber(summaryLiabilities.value)));
const netWorthValue = computed(() => toNumber(summaryNetWorth.value));
const backedDebtValue = computed(() => Math.max(0, toNumber(summaryAssetBackedLiabilities.value)));
const unbackedDebtValue = computed(() => Math.max(0, toNumber(summaryUnbackedLiabilities.value)));

const debtRatioValue = computed(() =>
  assetsValue.value > 0 ? liabilitiesValue.value / assetsValue.value : null,
);
const equityRatioValue = computed(() =>
  assetsValue.value > 0 ? netWorthValue.value / assetsValue.value : null,
);

const liquidityAssetsValue = computed(() => {
  const liquidityCategoryIndex = byCategoryLabels.value.findIndex(
    (label) => label.toLowerCase() === 'liquidez',
  );
  if (liquidityCategoryIndex < 0) return 0;
  return Math.max(0, byCategoryAssets.value[liquidityCategoryIndex] ?? 0);
});

const liquidityToDebtRatioValue = computed(() =>
  liabilitiesValue.value > 0 ? liquidityAssetsValue.value / liabilitiesValue.value : null,
);

const analysis = computed(() => ({
  assets: assetsValue.value,
  liabilities: liabilitiesValue.value,
  netWorth: netWorthValue.value,
  backedDebt: backedDebtValue.value,
  unbackedDebt: unbackedDebtValue.value,
  debtRatio: debtRatioValue.value,
  equityRatio: equityRatioValue.value,
  liquidityAssets: liquidityAssetsValue.value,
  liquidityToDebtRatio: liquidityToDebtRatioValue.value,
}));
</script>

<template>
  <div class="container ui-pro-page relative">
    <section class="card ui-pro-panel grid gap-2.5 mb-2">
      <p class="ui-pro-kicker">Patrimonio</p>
      <div class="mt-1 flex items-center justify-between gap-3">
        <div class="flex items-center gap-2.5">
          <button
            class="icon-btn disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            :disabled="store.loading"
            aria-label="Refrescar"
            @click="store.refreshAll()"
          >
            <span class="icon" aria-hidden="true">&#8635;</span>
          </button>
          <button
            class="icon-btn disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            :disabled="store.loading"
            aria-label="Guardar snapshot"
            title="Guardar snapshot"
            @click="store.createTodaySnapshot()"
          >
            <span class="icon" aria-hidden="true">&#128190;</span>
          </button>
        </div>

        <div class="ui-pro-toolbar">
          <SettingsPopover
            :loading="store.loading"
            :base-currency="store.baseCurrency ?? 'EUR'"
            :currencies="currencies"
            :value-mode="valueMode"
            :can-show-real="canShowReal()"
            :mode-help="modeLabel()"
            :real-base-label="realBaseLabel"
            :show-refresh="false"
            :show-snapshot="false"
            :icon-only="true"
            @update:base-currency="store.updateBaseCurrency"
            @update:value-mode="(v) => (valueMode = v)"
            @snapshot="store.createTodaySnapshot()"
            @refresh="store.refreshAll()"
          />
        </div>
      </div>

      <div class="ui-nw-balance-kpi-grid mt-2">
        <article class="ui-nw-balance-kpi ui-nw-balance-kpi-main">
          <div class="ui-nw-kpi-label">Patrimonio neto</div>
          <div class="ui-nw-kpi-value">
            {{ formatNumber(analysis.netWorth, 2) }} {{ unitLabel() }}
          </div>
          <div class="ui-nw-kpi-sub">
            Capital propio sobre activos: <strong>{{ formatPct(analysis.equityRatio, 0) }}</strong>
          </div>

          <div class="ui-nw-kpi-inline-grid">
            <div class="ui-nw-kpi-inline">
              <div class="ui-nw-kpi-inline-label">Activos</div>
              <div class="ui-nw-kpi-inline-value">
                {{ formatNumber(analysis.assets, 2) }} {{ unitLabel() }}
              </div>
            </div>
            <div class="ui-nw-kpi-inline">
              <div class="ui-nw-kpi-inline-label">Pasivos</div>
              <div class="ui-nw-kpi-inline-value">
                {{ formatNumber(analysis.liabilities, 2) }} {{ unitLabel() }}
              </div>
            </div>
            <div class="ui-nw-kpi-inline">
              <div class="ui-nw-kpi-inline-label">Ratio deuda / activos</div>
              <div class="ui-nw-kpi-inline-value">{{ formatPct(analysis.debtRatio, 0) }}</div>
            </div>
            <div class="ui-nw-kpi-inline">
              <div class="ui-nw-kpi-inline-label">Liquidez</div>
              <div class="ui-nw-kpi-inline-value">
                {{ formatNumber(analysis.liquidityAssets, 2) }} {{ unitLabel() }}
              </div>
              <div class="ui-nw-kpi-inline-meta">
                Cobertura: <strong>{{ formatPct(analysis.liquidityToDebtRatio, 0) }}</strong>
              </div>
            </div>
            <div class="ui-nw-kpi-inline">
              <div class="ui-nw-kpi-inline-label">Deuda sin respaldo</div>
              <div class="ui-nw-kpi-inline-value">
                {{ formatNumber(analysis.unbackedDebt, 2) }} {{ unitLabel() }}
              </div>
              <div class="ui-nw-kpi-inline-meta">
                {{
                  formatPct(
                    analysis.liabilities > 0 ? analysis.unbackedDebt / analysis.liabilities : null,
                    0,
                  )
                }}
                del pasivo
              </div>
            </div>
            <div class="ui-nw-kpi-inline">
              <div class="ui-nw-kpi-inline-label">Deuda con respaldo</div>
              <div class="ui-nw-kpi-inline-value">
                {{ formatNumber(analysis.backedDebt, 2) }} {{ unitLabel() }}
              </div>
            </div>
          </div>
        </article>
      </div>
    </section>

    <div v-if="store.error" class="alert mt-3">
      {{ prettyError() }}
    </div>

    <div class="card ui-pro-panel ui-nw-balance-panel section">
      <div class="ui-pro-divider mt-4">
        <NetWorthDonut
          :total-assets="summaryAssets"
          :total-liabilities="summaryLiabilities"
          :asset-backed-liabilities="summaryAssetBackedLiabilities"
          :unbacked-liabilities="summaryUnbackedLiabilities"
          :net-worth="summaryNetWorth"
          :unit="unitLabel()"
          :category-labels="byCategoryLabels"
          :category-assets="byCategoryAssets"
          :category-liabilities="byCategoryLiabilities"
        />
      </div>
    </div>

    <div class="section card ui-pro-panel">
      <h2 class="mt-0 text-base">Snapshots</h2>

      <ul v-if="store.snapshots.length" class="m-0 grid list-none gap-2 pl-0">
        <li v-for="s in store.snapshots" :key="s.id" class="ui-nw-snapshot-row">
          <div class="min-w-0">
            {{ s.snapshot_date }} - neto: {{ formatMoney(s.net_worth, 2) }} {{ s.base_currency }}
            <span class="subtle">
              (activos {{ formatMoney(s.total_assets, 2) }} {{ s.base_currency }}, pasivos
              {{ formatMoney(s.total_liabilities, 2) }} {{ s.base_currency }})
            </span>
          </div>
          <button
            class="icon-btn disabled:cursor-not-allowed disabled:opacity-50"
            type="button"
            :disabled="store.loading"
            aria-label="Eliminar snapshot"
            title="Eliminar snapshot"
            @click="confirmDeleteSnapshot(s.id)"
          >
            <span class="icon" aria-hidden="true">&#128465;</span>
          </button>
        </li>
      </ul>

      <div v-else class="subtle">No hay snapshots todavia.</div>
    </div>

    <div v-if="store.loading" class="ui-status-line">Cargando...</div>
  </div>
</template>

<style scoped>
.ui-nw-balance-panel {
  padding: 14px;
}

.ui-nw-balance-kpi-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(12, minmax(0, 1fr));
}

.ui-nw-balance-kpi {
  grid-column: span 4;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.02);
}

.ui-nw-balance-kpi-main {
  grid-column: span 12;
  text-align: center;
  background:
    linear-gradient(90deg, rgba(45, 212, 191, 0.12), rgba(56, 189, 248, 0.08)),
    rgba(7, 14, 26, 0.92);
  border-color: rgba(45, 212, 191, 0.3);
}

.ui-nw-kpi-inline-grid {
  margin-top: 12px;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(12, minmax(0, 1fr));
}

.ui-nw-kpi-inline {
  grid-column: span 2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 8px 6px;
  min-height: 96px;
}

.ui-nw-kpi-inline-label {
  font-size: 11px;
  color: rgba(255, 255, 255, 0.72);
}

.ui-nw-kpi-inline-value {
  margin-top: 3px;
  font-size: 20px;
  line-height: 1.2;
  font-weight: 700;
}

.ui-nw-kpi-inline-meta {
  margin-top: 3px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.75);
}

.ui-nw-kpi-label {
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--muted);
}

.ui-nw-kpi-value {
  margin-top: 6px;
  font-size: 26px;
  line-height: 1.15;
  font-weight: 700;
}

.ui-nw-kpi-sub {
  margin-top: 6px;
  font-size: 12px;
  color: var(--muted);
}

@media (max-width: 1024px) {
  .ui-nw-balance-kpi-main {
    grid-column: span 12;
    grid-row: auto;
  }

  .ui-nw-kpi-inline {
    grid-column: span 4;
  }
}

@media (max-width: 720px) {
  .ui-nw-balance-kpi,
  .ui-nw-balance-kpi-main {
    grid-column: span 12;
    grid-row: auto;
  }

  .ui-nw-kpi-inline {
    grid-column: span 12;
  }

  .ui-nw-kpi-value {
    font-size: 22px;
  }
}
</style>

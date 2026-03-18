<script setup lang="ts">
import { NetWorthDonut, SettingsPopover } from '@/domains/net-worth';

type OwnershipFilterValue = 'all' | number;
type ValueMode = 'nominal' | 'real';

type OwnershipOption = {
  value: OwnershipFilterValue;
  label: string;
};

type CurrencyOption = {
  value: string;
  label: string;
};

type InflationRegion = {
  code: string;
  label: string;
};

type HeroAnalysis = {
  assets: number;
  liabilities: number;
  backedDebt: number;
  unbackedDebt: number;
  netWorth: number;
  liquidityToDebtRatio: number | null;
  equityRatio: number | null;
};

type StoreLike = {
  loading: boolean;
  baseCurrency?: string | null;
  inflationRegion?: string | null;
  refreshAll: () => void;
  createTodaySnapshot: () => void;
  updateBaseCurrency: (value: string) => void;
  updateInflationRegion: (value: string) => void;
};

const props = defineProps<{
  store: StoreLike;
  currencies: CurrencyOption[];
  inflationRegions: InflationRegion[];
  valueMode: ValueMode;
  setValueMode: (value: ValueMode) => void;
  canShowReal: boolean;
  modeLabel: string;
  realBaseLabel: string;
  heroUnitLabel: string;
  analysis: HeroAnalysis;
  ownershipFilter: OwnershipFilterValue;
  setOwnershipFilter: (value: OwnershipFilterValue) => void;
  ownershipOptions: OwnershipOption[];
  ownershipFilterDisabled: boolean;
  selectedOwnershipFilterLabel: string;
  formatNumber: (value: number, decimals?: number) => string;
  formatPct: (value: number | null, decimals?: number) => string;
  resetTimelineSelection: () => void;
}>();

function closePopoverFromClick(event: Event): void {
  const target = event.currentTarget as HTMLElement | null;
  const details = target?.closest('details') as HTMLDetailsElement | null;
  if (details) details.open = false;
}

function selectOwnershipFilterOption(value: OwnershipFilterValue, event: Event): void {
  props.setOwnershipFilter(value);
  closePopoverFromClick(event);
}
</script>

<template>
  <section class="card ui-pro-panel ui-nw-hero-shell grid gap-2.5 mb-2">
    <p class="ui-pro-kicker">Patrimonio</p>
    <div class="ui-nw-topbar mt-1">
      <div class="ui-nw-topbar-actions">
        <button
          class="icon-btn ui-nw-topbar-action disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          :disabled="store.loading"
          aria-label="Refrescar"
          @click="store.refreshAll()"
        >
          <span class="icon" aria-hidden="true">&#8635;</span>
        </button>
        <button
          class="icon-btn ui-nw-topbar-action disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          :disabled="store.loading"
          aria-label="Guardar snapshot"
          title="Guardar snapshot"
          @click="store.createTodaySnapshot()"
        >
          <span class="icon" aria-hidden="true">&#128190;</span>
        </button>
      </div>

      <div class="ui-pro-toolbar ui-nw-toolbar">
        <SettingsPopover
          :loading="store.loading"
          :base-currency="store.baseCurrency ?? 'EUR'"
          :currencies="currencies"
          :inflation-region="store.inflationRegion ?? 'ES'"
          :inflation-regions="inflationRegions"
          :value-mode="valueMode"
          :can-show-real="canShowReal"
          :mode-help="modeLabel"
          :real-base-label="realBaseLabel"
          :show-refresh="false"
          :show-snapshot="false"
          :icon-only="true"
          @update:base-currency="store.updateBaseCurrency"
          @update:inflation-region="store.updateInflationRegion"
          @update:value-mode="setValueMode"
          @snapshot="store.createTodaySnapshot()"
          @refresh="store.refreshAll()"
        />
      </div>
    </div>

    <div class="ui-nw-hero mt-2">
      <div class="ui-nw-hero-main">
        <div class="ui-nw-hero-donut">
          <div class="ui-nw-hero-donut-frame">
            <NetWorthDonut
              :total-assets="analysis.assets"
              :total-liabilities="analysis.liabilities"
              :asset-backed-liabilities="analysis.backedDebt"
              :unbacked-liabilities="analysis.unbackedDebt"
              :net-worth="analysis.netWorth"
              :unit="heroUnitLabel"
              :show-composition="false"
            />
          </div>
        </div>
        <article class="ui-nw-hero-summary">
          <div class="ui-nw-hero-summary-head">
            <div class="ui-nw-hero-badge">Balance actual</div>
            <label class="ui-nw-hero-context" data-test="ownership-filter">
              <span class="ui-nw-hero-context-label">Titularidad</span>
              <details
                class="ui-select-popover ui-nw-hero-context-popover"
                :class="{ 'opacity-60': ownershipFilterDisabled }"
              >
                <summary
                  class="ui-select-popover-trigger ui-nw-hero-context-trigger"
                  :aria-disabled="ownershipFilterDisabled"
                  @click="ownershipFilterDisabled ? $event.preventDefault() : undefined"
                >
                  <span class="ui-select-popover-text">{{ selectedOwnershipFilterLabel }}</span>
                  <span class="ui-select-popover-caret" aria-hidden="true">&#8964;</span>
                </summary>
                <div class="ui-select-popover-menu" role="listbox" aria-label="Titularidad">
                  <button
                    type="button"
                    class="ui-select-popover-option"
                    :class="{ 'ui-select-popover-option-active': ownershipFilter === 'all' }"
                    data-test="ownership-filter-option-all"
                    :disabled="ownershipFilterDisabled"
                    @click="selectOwnershipFilterOption('all', $event)"
                  >
                    Todos
                  </button>
                  <button
                    v-for="option in ownershipOptions"
                    :key="String(option.value)"
                    type="button"
                    class="ui-select-popover-option"
                    :class="{ 'ui-select-popover-option-active': ownershipFilter === option.value }"
                    :data-test="`ownership-filter-option-${String(option.value)}`"
                    :disabled="ownershipFilterDisabled"
                    @click="selectOwnershipFilterOption(option.value, $event)"
                  >
                    {{ option.label }}
                  </button>
                </div>
              </details>
            </label>
          </div>
          <div class="ui-nw-hero-summary-body">
            <div class="ui-nw-hero-primary">
              <div class="ui-nw-hero-title">Patrimonio neto</div>
              <button class="ui-nw-hero-value-button" type="button" @click="resetTimelineSelection">
                <div class="ui-nw-hero-value">
                  {{ formatNumber(analysis.netWorth, 2) }} {{ heroUnitLabel }}
                </div>
              </button>
              <div class="ui-nw-hero-metrics">
                <div class="ui-nw-hero-metric">
                  <span class="ui-nw-hero-metric-label">Cobertura liquida</span>
                  <strong class="ui-nw-hero-metric-value">
                    {{ formatPct(analysis.liquidityToDebtRatio, 0) }}
                  </strong>
                </div>
                <div class="ui-nw-hero-metric">
                  <span class="ui-nw-hero-metric-label">Capital propio</span>
                  <strong class="ui-nw-hero-metric-value">
                    {{ formatPct(analysis.equityRatio, 0) }}
                  </strong>
                </div>
              </div>
            </div>

            <div class="ui-nw-hero-side">
              <div class="ui-nw-hero-stats">
                <div class="ui-nw-hero-stat ui-nw-hero-stat-assets">
                  <span class="ui-nw-hero-stat-label">Activos</span>
                  <strong class="ui-nw-hero-stat-value">
                    {{ formatNumber(analysis.assets, 2) }} {{ heroUnitLabel }}
                  </strong>
                </div>
                <div class="ui-nw-hero-stat ui-nw-hero-stat-liabilities">
                  <span class="ui-nw-hero-stat-label">Pasivos</span>
                  <strong class="ui-nw-hero-stat-value">
                    {{ formatNumber(analysis.liabilities, 2) }} {{ heroUnitLabel }}
                  </strong>
                </div>
              </div>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

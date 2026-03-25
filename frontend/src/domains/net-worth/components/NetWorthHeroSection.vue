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
  monthlyDelta?: { value: number; pct: number | null; lastLabel: string; prevLabel: string } | null;
  categoryKeys?: string[];
  categoryLabels?: string[];
  categoryAssets?: number[];
  categoryLiabilities?: number[];
  categoryAssetCounts?: number[];
  categoryLiabilityCounts?: number[];
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
    <div class="ui-nw-topbar">
      <div class="ui-nw-topbar-actions">
        <p class="ui-pro-kicker ui-nw-topbar-kicker">Patrimonio</p>
        <button
          class="icon-btn ui-nw-topbar-action disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          :disabled="store.loading"
          aria-label="Refrescar"
          @click="store.refreshAll()"
        >
          <span class="icon" aria-hidden="true">&#8635;</span>
        </button>
      </div>
    </div>

    <div class="ui-nw-hero">
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
              :category-keys="props.categoryKeys"
              :category-labels="props.categoryLabels"
              :category-assets="props.categoryAssets"
              :category-liabilities="props.categoryLiabilities"
              :category-asset-counts="props.categoryAssetCounts"
              :category-liability-counts="props.categoryLiabilityCounts"
            />
          </div>
        </div>
        <article class="ui-nw-hero-summary">
          <div class="ui-nw-hero-summary-head">
            <div class="ui-nw-hero-title">Patrimonio neto</div>
            <div class="ui-nw-hero-summary-controls">
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
              <div class="ui-nw-toolbar ui-nw-toolbar-inline">
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
                  :icon-only="true"
                  @update:base-currency="store.updateBaseCurrency"
                  @update:inflation-region="store.updateInflationRegion"
                  @update:value-mode="setValueMode"
                  @refresh="store.refreshAll()"
                />
              </div>
            </div>
          </div>
          <div class="ui-nw-hero-summary-body">
            <button class="ui-nw-hero-value-button" type="button" @click="resetTimelineSelection">
              <div class="ui-nw-hero-value">
                {{ formatNumber(analysis.netWorth, 2) }} {{ heroUnitLabel }}
              </div>
            </button>
            <div
              v-if="monthlyDelta"
              class="ui-nw-hero-delta"
              :class="{
                'ui-nw-hero-delta-pos': monthlyDelta.value > 0,
                'ui-nw-hero-delta-neg': monthlyDelta.value < 0,
                'ui-nw-hero-delta-zero': monthlyDelta.value === 0,
              }"
            >
              <span>{{ monthlyDelta.value > 0 ? '+' : '' }}{{ formatNumber(monthlyDelta.value, 0) }} {{ heroUnitLabel }}</span>
              <span v-if="monthlyDelta.pct !== null">({{ monthlyDelta.value > 0 ? '+' : '' }}{{ formatPct(monthlyDelta.pct, 1) }})</span>
              <span class="ui-nw-hero-delta-range">{{ monthlyDelta.prevLabel }} → {{ monthlyDelta.lastLabel }}</span>
            </div>
            <div class="ui-nw-hero-bottom-row">
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
              <div class="ui-nw-hero-stat">
                <span class="ui-nw-hero-stat-label">Cobertura liquida</span>
                <strong class="ui-nw-hero-stat-value">
                  {{ formatPct(analysis.liquidityToDebtRatio, 0) }}
                </strong>
              </div>
              <div class="ui-nw-hero-stat">
                <span class="ui-nw-hero-stat-label">Capital propio</span>
                <strong class="ui-nw-hero-stat-value">
                  {{ formatPct(analysis.equityRatio, 0) }}
                </strong>
              </div>
            </div>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>

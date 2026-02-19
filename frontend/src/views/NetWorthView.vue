<script setup lang="ts">
import { computed } from 'vue';
import {
  ItemForm,
  ItemList,
  NetWorthDonut,
  SettingsPopover,
  useNetWorthViewExtensions,
  useNetWorthViewState,
} from '@/domains/net-worth';
import { BaseModal } from '@/domains/ui';

const {
  store,
  valueMode,
  currencies,
  assetCategories,
  assetSubcategories,
  liabilityCategories,
  prettyError,
  showAssetModal,
  showLiabilityModal,
  showEditModal,
  editKind,
  canShowReal,
  submitAsset,
  submitLiability,
  openEdit,
  closeEdit,
  confirmDeleteSnapshot,
  editTitle,
  editCategories,
  editInitial,
  submitEdit,
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

const { HeaderActions, itemFormProps, itemListProps } = useNetWorthViewExtensions(store);

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

type CategoryRow = { label: string; assets: number; liabilities: number };
type InsightTone = 'stable' | 'warn' | 'danger';

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

const categoryRows = computed<CategoryRow[]>(() =>
  byCategoryLabels.value.map((label, index) => ({
    label,
    assets: Math.max(0, byCategoryAssets.value[index] ?? 0),
    liabilities: Math.max(0, byCategoryLiabilities.value[index] ?? 0),
  })),
);

const topAssetCategoryValue = computed(
  () => categoryRows.value.filter((row) => row.assets > 0).sort((a, b) => b.assets - a.assets)[0],
);
const topLiabilityCategoryValue = computed(
  () =>
    categoryRows.value
      .filter((row) => row.liabilities > 0)
      .sort((a, b) => b.liabilities - a.liabilities)[0],
);

const assetConcentrationValue = computed(() => {
  if (assetsValue.value <= 0 || !topAssetCategoryValue.value) return null;
  return topAssetCategoryValue.value.assets / assetsValue.value;
});

const liabilityConcentrationValue = computed(() => {
  if (liabilitiesValue.value <= 0 || !topLiabilityCategoryValue.value) return null;
  return topLiabilityCategoryValue.value.liabilities / liabilitiesValue.value;
});

const unbackedDebtShareValue = computed(() =>
  liabilitiesValue.value > 0 ? unbackedDebtValue.value / liabilitiesValue.value : null,
);

type CurvePoint = { x: number; y: number };

function interpolatePenalty(value: number | null, curve: CurvePoint[], fallback = 12.5): number {
  if (value == null || !Number.isFinite(value) || curve.length === 0) return fallback;
  const sorted = [...curve].sort((a, b) => a.x - b.x);
  const first = sorted[0];
  const last = sorted[sorted.length - 1];
  if (!first || !last) return fallback;
  if (value <= first.x) return first.y;
  if (value >= last.x) return last.y;

  for (let i = 0; i < sorted.length - 1; i++) {
    const left = sorted[i];
    const right = sorted[i + 1];
    if (!left || !right) continue;
    if (value >= left.x && value <= right.x) {
      const range = right.x - left.x;
      if (range <= 0) return left.y;
      const t = (value - left.x) / range;
      return left.y + (right.y - left.y) * t;
    }
  }

  return fallback;
}

const scorePenaltiesValue = computed(() => ({
  leverage: interpolatePenalty(debtRatioValue.value, [
    { x: 0, y: 0 },
    { x: 0.2, y: 0 },
    { x: 0.4, y: 6.7 },
    { x: 0.6, y: 15 },
    { x: 0.8, y: 25 },
    { x: 1.2, y: 25 },
  ]),
  unbacked: interpolatePenalty(unbackedDebtShareValue.value, [
    { x: 0, y: 0 },
    { x: 0.05, y: 0 },
    { x: 0.15, y: 7.5 },
    { x: 0.3, y: 17.5 },
    { x: 0.5, y: 25 },
    { x: 1, y: 25 },
  ]),
  concentration: interpolatePenalty(assetConcentrationValue.value, [
    { x: 0, y: 0 },
    { x: 0.35, y: 0 },
    { x: 0.5, y: 6.25 },
    { x: 0.7, y: 15 },
    { x: 0.85, y: 22.5 },
    { x: 1, y: 25 },
  ]),
  liquidity: interpolatePenalty(liquidityToDebtRatioValue.value, [
    { x: 0, y: 25 },
    { x: 0.25, y: 22.5 },
    { x: 0.5, y: 15 },
    { x: 0.8, y: 7.5 },
    { x: 1.2, y: 0 },
    { x: 2, y: 0 },
  ]),
}));

const healthScoreValue = computed(() => {
  const totalPenalty =
    scorePenaltiesValue.value.leverage +
    scorePenaltiesValue.value.unbacked +
    scorePenaltiesValue.value.concentration +
    scorePenaltiesValue.value.liquidity;
  return Math.max(0, Math.min(100, 100 - totalPenalty));
});

function healthToneFromScore(score: number) {
  if (score <= 20) return 'critico';
  if (score <= 40) return 'alto';
  if (score <= 60) return 'medio';
  if (score <= 80) return 'bajo';
  return 'solido';
}

const healthToneValue = computed(() => healthToneFromScore(healthScoreValue.value));

const healthLabelValue = computed(() => {
  if (healthToneValue.value === 'critico') return 'Riesgo patrimonial critico';
  if (healthToneValue.value === 'alto') return 'Riesgo patrimonial alto';
  if (healthToneValue.value === 'medio') return 'Riesgo patrimonial medio';
  if (healthToneValue.value === 'bajo') return 'Riesgo patrimonial bajo';
  return 'Patrimonio solido';
});

function toneByThreshold(
  value: number | null,
  warnAt: number,
  dangerAt: number,
  reverse = false,
): InsightTone {
  if (value == null) return 'warn';
  if (reverse) {
    if (value <= dangerAt) return 'danger';
    if (value <= warnAt) return 'warn';
    return 'stable';
  }
  if (value >= dangerAt) return 'danger';
  if (value >= warnAt) return 'warn';
  return 'stable';
}

const riskDimensions = computed<
  { id: string; label: string; value: string; tone: InsightTone; hint: string }[]
>(() => [
  {
    id: 'debt',
    label: 'Apalancamiento',
    value: formatPct(debtRatioValue.value, 0),
    tone: toneByThreshold(debtRatioValue.value, 0.4, 0.65),
    hint: 'Pasivo sobre activo total',
  },
  {
    id: 'unbacked',
    label: 'Deuda sin respaldo',
    value: formatPct(unbackedDebtShareValue.value, 0),
    tone: toneByThreshold(unbackedDebtShareValue.value, 0.1, 0.35),
    hint: 'Pasivo no ligado a activos',
  },
  {
    id: 'concentration',
    label: 'Concentracion activo',
    value: formatPct(assetConcentrationValue.value, 0),
    tone: toneByThreshold(assetConcentrationValue.value, 0.7, 0.85),
    hint: topAssetCategoryValue.value?.label ?? 'Sin categoria dominante',
  },
  {
    id: 'liquidity',
    label: 'Cobertura liquidez',
    value: formatPct(liquidityToDebtRatioValue.value, 0),
    tone: toneByThreshold(liquidityToDebtRatioValue.value, 0.6, 0.35, true),
    hint: 'Liquidez / pasivo total',
  },
]);

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
  topAssetCategory: topAssetCategoryValue.value,
  topLiabilityCategory: topLiabilityCategoryValue.value,
  assetConcentration: assetConcentrationValue.value,
  liabilityConcentration: liabilityConcentrationValue.value,
  unbackedDebtShare: unbackedDebtShareValue.value,
  healthTone: healthToneValue.value,
  healthLabel: healthLabelValue.value,
  healthScore: healthScoreValue.value,
}));
</script>

<template>
  <div class="container ui-pro-page relative">
    <div class="mb-1 flex items-center justify-between gap-3">
      <div class="flex items-center gap-2.5">
        <h1 class="h1 m-0">Patrimonio</h1>
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
        <component :is="HeaderActions" v-if="HeaderActions" />

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

    <div v-if="store.error" class="alert mt-3">
      {{ prettyError() }}
    </div>

    <div class="card ui-pro-panel ui-nw-balance-panel section">
      <div class="ui-nw-balance-kpi-grid">
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
                {{ formatPct(analysis.unbackedDebtShare, 0) }} del pasivo
              </div>
            </div>
          </div>
        </article>
      </div>

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

    <div class="card ui-pro-panel ui-nw-risk-panel section">
      <div class="ui-nw-risk-top">
        <div class="ui-nw-health-badge" :class="`ui-nw-health-${analysis.healthTone}`">
          {{ analysis.healthLabel }}
        </div>
        <div class="ui-nw-risk-score-wrap">
          <div class="ui-nw-risk-score-label">Score de balance</div>
          <div class="ui-nw-risk-score-value">{{ formatNumber(analysis.healthScore, 0) }}/100</div>
        </div>
        <div class="ui-nw-health-copy">
          <strong>Diagnostico:</strong> estado actual del balance por apalancamiento, respaldo de
          deuda, concentracion y liquidez.
        </div>
      </div>

      <div class="ui-nw-risk-meter" :class="`ui-nw-risk-meter-${analysis.healthTone}`">
        <span class="ui-nw-risk-meter-fill" :style="{ width: `${analysis.healthScore}%` }"></span>
      </div>

      <div class="ui-nw-dimensions-grid">
        <article
          v-for="dimension in riskDimensions"
          :key="dimension.id"
          class="ui-nw-dimension"
          :class="`ui-nw-dimension-${dimension.tone}`"
        >
          <div class="ui-nw-dimension-head">
            <span>{{ dimension.label }}</span>
            <strong>{{ dimension.value }}</strong>
          </div>
          <div class="ui-nw-dimension-hint">{{ dimension.hint }}</div>
        </article>
      </div>
    </div>

    <div class="grid-2 section">
      <ItemList
        title="Activos"
        :items="store.assets"
        :categories="assetCategories"
        :subcategories="assetSubcategories"
        :base-currency="store.baseCurrency ?? store.summary?.base_currency ?? 'EUR'"
        :category-totals-base="store.summary?.assets_by_category ?? {}"
        :subcategory-totals-base="store.summary?.assets_by_subcategory ?? {}"
        :total-base="store.summary?.total_assets ?? '0'"
        v-bind="itemListProps"
        :on-update="store.updateAsset"
        :on-archive="store.archiveAsset"
        :on-add="() => (showAssetModal = true)"
        :on-edit="(it) => openEdit(it, 'asset')"
      />

      <ItemList
        title="Pasivos"
        :items="store.liabilities"
        :categories="liabilityCategories"
        :base-currency="store.baseCurrency ?? store.summary?.base_currency ?? 'EUR'"
        :category-totals-base="store.summary?.liabilities_by_category ?? {}"
        :total-base="store.summary?.total_liabilities ?? '0'"
        v-bind="itemListProps"
        :assets="store.assets"
        :on-update="store.updateLiability"
        :on-archive="store.archiveLiability"
        :on-add="() => (showLiabilityModal = true)"
        :on-edit="(it) => openEdit(it, 'liability')"
      />
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

    <BaseModal :open="showAssetModal" title="Nuevo activo" @close="showAssetModal = false">
      <ItemForm
        title="Nuevo activo"
        :categories="assetCategories"
        :subcategories="assetSubcategories"
        v-bind="itemFormProps"
        :allow-negative="true"
        :on-submit="submitAsset"
        :on-cancel="() => (showAssetModal = false)"
      />
    </BaseModal>

    <BaseModal :open="showLiabilityModal" title="Nuevo pasivo" @close="showLiabilityModal = false">
      <ItemForm
        title="Nuevo pasivo"
        :categories="liabilityCategories"
        v-bind="itemFormProps"
        :assets="store.assets"
        :show-financed-asset="true"
        :on-submit="submitLiability"
        :on-cancel="() => (showLiabilityModal = false)"
      />
    </BaseModal>

    <BaseModal :open="showEditModal" :title="editTitle" @close="closeEdit">
      <ItemForm
        v-if="editInitial"
        :title="editTitle"
        :categories="editCategories"
        :subcategories="editKind === 'asset' ? assetSubcategories : undefined"
        v-bind="itemFormProps"
        :assets="editKind === 'liability' ? store.assets : []"
        :show-financed-asset="editKind === 'liability'"
        :allow-negative="editKind === 'asset'"
        mode="edit"
        :initial="editInitial"
        :on-submit="submitEdit"
        :on-cancel="closeEdit"
      />
    </BaseModal>
  </div>
</template>

<style scoped>
.ui-nw-balance-panel,
.ui-nw-risk-panel {
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
  grid-template-columns: repeat(10, minmax(0, 1fr));
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

.ui-nw-health-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 7px 11px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(255, 255, 255, 0.18);
}

.ui-nw-health-solido {
  background: rgba(74, 222, 128, 0.16);
  color: rgba(134, 239, 172, 0.95);
}

.ui-nw-health-bajo {
  background: rgba(163, 230, 53, 0.18);
  color: rgba(190, 242, 100, 0.95);
}

.ui-nw-health-medio {
  background: rgba(250, 204, 21, 0.16);
  color: rgba(253, 224, 71, 0.95);
}

.ui-nw-health-alto {
  background: rgba(251, 146, 60, 0.18);
  color: rgba(251, 191, 36, 0.95);
}

.ui-nw-health-critico {
  background: rgba(251, 113, 133, 0.16);
  color: rgba(251, 113, 133, 0.95);
}

.ui-nw-health-copy {
  font-size: 13px;
  color: var(--muted);
}

.ui-nw-risk-top {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr);
  gap: 14px;
  align-items: center;
}

.ui-nw-risk-score-wrap {
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 11px;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.03);
}

.ui-nw-risk-score-label {
  font-size: 11px;
  color: var(--muted);
}

.ui-nw-risk-score-value {
  margin-top: 1px;
  font-size: 20px;
  font-weight: 700;
}

.ui-nw-risk-meter {
  margin-top: 12px;
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.ui-nw-risk-meter-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(74, 222, 128, 0.95), rgba(45, 212, 191, 0.95));
}

.ui-nw-risk-meter-bajo .ui-nw-risk-meter-fill {
  background: linear-gradient(90deg, rgba(132, 204, 22, 0.95), rgba(163, 230, 53, 0.95));
}

.ui-nw-risk-meter-medio .ui-nw-risk-meter-fill {
  background: linear-gradient(90deg, rgba(250, 204, 21, 0.95), rgba(251, 191, 36, 0.95));
}

.ui-nw-risk-meter-alto .ui-nw-risk-meter-fill {
  background: linear-gradient(90deg, rgba(251, 146, 60, 0.95), rgba(249, 115, 22, 0.95));
}

.ui-nw-risk-meter-critico .ui-nw-risk-meter-fill {
  background: linear-gradient(90deg, rgba(251, 113, 133, 0.95), rgba(244, 63, 94, 0.95));
}

.ui-nw-dimensions-grid {
  margin-top: 12px;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.ui-nw-dimension {
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.02);
  padding: 10px 11px;
}

.ui-nw-dimension-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.ui-nw-dimension-head strong {
  font-size: 15px;
}

.ui-nw-dimension-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted);
}

.ui-nw-dimension-stable {
  border-color: rgba(74, 222, 128, 0.28);
}

.ui-nw-dimension-warn {
  border-color: rgba(250, 204, 21, 0.34);
}

.ui-nw-dimension-danger {
  border-color: rgba(251, 113, 133, 0.36);
}

@media (max-width: 1024px) {
  .ui-nw-balance-kpi-main {
    grid-column: span 12;
    grid-row: auto;
  }

  .ui-nw-kpi-inline {
    grid-column: span 5;
  }

  .ui-nw-dimensions-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .ui-nw-balance-kpi,
  .ui-nw-balance-kpi-main {
    grid-column: span 12;
    grid-row: auto;
  }

  .ui-nw-kpi-inline {
    grid-column: span 10;
  }

  .ui-nw-risk-top {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .ui-nw-dimensions-grid {
    grid-template-columns: 1fr;
  }

  .ui-nw-kpi-value {
    font-size: 22px;
  }
}
</style>
